"""Helpers of the voice tests: talking to the built-in agent, and its sentences.

Russian is tested without a Russian letter in a test: the inputs are sampled from the
sentence files (`samples`), and the answers are compared with each other, not with
words (`without_digits`, `PluralClasses`).
"""

import json
import re
import shutil
from collections.abc import Awaitable, Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from functools import cache
from itertools import islice
from pathlib import Path
from typing import Any, Final

import yaml
from freezegun.api import FrozenDateTimeFactory
from hassil.expression import RuleReference, Sentence
from hassil.intents import Intents, RangeSlotList, SlotList, TextSlotList
from hassil.sample import sample_expression, sample_sentence
from hassil.util import merge_dict
from home_assistant_intents import get_intents
from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import (
    async_expose_entity,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.core import Context, Event, HomeAssistant, ServiceCall, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import intent, llm
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component

from custom_components.timerify.const import (
    CONF_LANGUAGES,
    CONF_WRITE_SENTENCES,
    DOMAIN,
    LIST_INTERVAL,
    LIST_TARGET,
    MANUAL_SENTENCES_DIR,
    SENTENCES_DIR,
    VOICE_LANGUAGES,
)
from custom_components.timerify.voice.sentences import read_back, references
from scripts.generate_core_commands import FILE_NAME as CORE_COMMANDS

from ..conftest import FakeTarget, SetupTarget
from ..helpers import advance_to, local

ASSISTANT: Final = "conversation"
"""The assistant the built-in agent asks Home Assistant about exposure as."""
NAMES_FILE: Final = "timerify_names.yaml"
"""The file of the manual installation that lists the targets' names."""
OWN_SENTENCES: Final = "timerify.yaml"
"""The shipped file of the sentences that Timerify's own intents are said with, besides
`CORE_COMMANDS`, the file of those that take over Home Assistant's."""
TRANSLATIONS: Final = (
    Path(__file__).parents[2] / "custom_components" / DOMAIN / "translations"
)
"""Where the translations of the integration are."""
LATE_EVENING: Final = local(date(2026, 1, 5), "23:00")
"""From this time every count of hours up to 24 ends the next day, and every count of
minutes below 60 ends the same day, so that answers to different counts differ in
nothing but the count."""


@dataclass(frozen=True)
class PluralClasses:
    """Counts of a unit, grouped by the plural form a language says them with.

    Russian has three forms (`one`, `few`, `many`), English two (`one` and `other`),
    and the counts here are only those that can be spoken for the unit.
    """

    one: tuple[int, ...]
    few: tuple[int, ...]
    many: tuple[int, ...]
    other: tuple[int, ...]
    """The English plural: every count but `one`."""
    minutes_each: int = 1
    """How many minutes a timer runs for each counted unit: 60 for hours."""

    @property
    def russian(self) -> tuple[tuple[int, ...], ...]:
        """The three Russian classes."""
        return (self.one, self.few, self.many)

    @property
    def english(self) -> tuple[tuple[int, ...], ...]:
        """The two English classes."""
        return (self.one[:1], self.other)


MINUTE_CLASSES: Final = PluralClasses(
    one=(1, 21, 31, 41, 51),
    few=(2, 3, 4, 22, 23, 24, 32, 54),
    many=(5, 9, 11, 12, 13, 14, 15, 20, 25, 30, 59),
    other=(2, 5, 11, 21, 59),
)
HOUR_CLASSES: Final = PluralClasses(
    one=(1, 21),
    few=(2, 3, 4, 22, 23, 24),
    many=(5, 11, 12, 14, 20),
    other=(2, 5, 11, 24),
    minutes_each=60,
)
COMMAND_CLASSES: Final = PluralClasses(
    one=(1,),
    few=(2, 3, 4),
    many=(5, 11, 12, 14, 20),
    other=(2, 5, 20),
)


async def talk(
    hass: HomeAssistant,
    text: str,
    language: str = "en",
    *,
    conversation_id: str | None = None,
) -> conversation.ConversationResult:
    """Say `text` to the built-in agent, in the conversation `conversation_id` (a new
    one without), and return its result: the answer and the conversation's id."""
    return await conversation.async_converse(
        hass, text, conversation_id, Context(), language=language
    )


async def converse(
    hass: HomeAssistant, text: str, language: str = "en"
) -> intent.IntentResponse:
    """Say `text` to the built-in agent, as the first thing of a conversation, and
    return its answer."""
    return (await talk(hass, text, language)).response


def speech(response: intent.IntentResponse) -> str:
    """What the answer says."""
    return str(response.speech["plain"]["speech"])


def expose(
    hass: HomeAssistant, entity_id: str, exposed: bool, assistant: str = ASSISTANT
) -> None:
    """Expose the entity to Assist (the assistant `assistant`), or stop doing it."""
    async_expose_entity(hass, assistant, entity_id, exposed)


async def assist_api(
    hass: HomeAssistant,
    language: str | None = "en",
    assistant: str = ASSISTANT,
) -> llm.APIInstance:
    """The Assist API as an LLM agent is given it: the tools and the prompt of every
    integration, for a request in `language` that `assistant` makes.

    The LLM integration is set up first, as it is in a house that has an LLM agent.
    """
    assert await async_setup_component(hass, "llm", {})
    return await llm.async_get_api(
        hass,
        llm.LLM_API_ASSIST,
        llm.LLMContext(
            platform="test",
            context=Context(),
            language=language,
            assistant=assistant,
            device_id=None,
        ),
    )


async def call_tool(
    api: llm.APIInstance, name: str, args: Mapping[str, Any]
) -> dict[str, Any]:
    """Call the tool `name` as the agent does, with the arguments `args`, and return
    what it gives back: the data of the result, which is not an error."""
    result = await api.async_call_tool(llm.ToolInput(name, dict(args)))
    assert not result.error
    return dict(result.data)


def counting(
    *, hours: int = 0, minutes: int = 0, days: int = 0, target: str = "Boiler"
) -> dict[str, Any]:
    """The slots a handler gives to the answer about a timer that counts: `hours` and
    `minutes` left, ending `days` dates from today."""
    return {
        "state": "counting",
        "target": target,
        "left_total": hours * 60 + minutes,
        "left_hours": hours,
        "left_minutes": minutes,
        "ends_at": "11:00",
        "ends_in_days": days,
    }


TIMER_CASES: Final[Sequence[Mapping[str, Any]]] = (
    counting(minutes=1),
    counting(minutes=2),
    counting(minutes=5),
    counting(minutes=21),
    counting(hours=1),
    counting(hours=1, minutes=30),
    counting(hours=2, days=1),
    counting(hours=5, days=2),
    counting(hours=2, days=5),
    counting(hours=2, days=21),
    {"state": "open", "target": "Boiler"},
    {"state": "off", "target": "Boiler"},
    {"state": "unavailable", "target": "Boiler"},
)
"""The slots a handler gives to an answer about a timer, in the cases it tells apart:
every counting form of the language's plural rules, a day, and the states without a
countdown."""

LATER_CASES: Final[Sequence[Mapping[str, Any]]] = (
    {"outcome": "command_added", "target": "Boiler", "at": "10:15", "in_days": 0},
    {"outcome": "command_added", "target": "Boiler", "at": "10:15", "in_days": 1},
    {"outcome": "command_added", "target": "Boiler", "at": "10:15", "in_days": 2},
    {"outcome": "command_added", "target": "Boiler", "at": "10:15", "in_days": 21},
    {"outcome": "timer_set", "target": "Boiler", "ends_at": "10:15", "ends_in_days": 0},
    {"outcome": "timer_set", "target": "Boiler", "ends_at": "10:15", "ends_in_days": 1},
    {"outcome": "timer_set", "target": "Boiler", "ends_at": "10:15", "ends_in_days": 5},
    {"outcome": "not_running", "target": "Boiler"},
)
"""The slots a handler gives to the answer about a command for later, in the cases it
tells apart: a command to turn on that was kept, the countdown that was set to turn
off (each today and on another date), and a turn off of a target that is not running."""


def planned(
    action: str = "on", *, at: str = "09:15", days: int = 0, minutes: int | None = None
) -> dict[str, Any]:
    """The slots a handler gives to a planned command: `days` dates from today, and for
    a command to turn on, the `minutes` it then runs."""
    return {
        "id": "c1",
        "action": action,
        "at": at,
        "in_days": days,
        "minutes": minutes,
        "settings": {},
    }


def listing(*commands: Mapping[str, Any], count: int | None = None) -> dict[str, Any]:
    """The slots a handler gives to the answer about what is planned: the `commands`,
    and a `count` of them (as many as there are unless a case says otherwise)."""
    return {
        "target": "Boiler",
        "count": len(commands) if count is None else count,
        "commands": list(commands),
    }


def cancelling(which: str, *commands: Mapping[str, Any]) -> dict[str, Any]:
    """The slots a handler gives to the answer about cancelling the `commands`, the way
    `which` says: `next`, `all`, or `id` (one by its id)."""
    return {
        "target": "Boiler",
        "which": which,
        "cancelled": len(commands),
        "commands": list(commands),
    }


LIST_CASES: Final[Sequence[Mapping[str, Any]]] = (
    listing(),
    listing(planned()),
    listing(planned(minutes=1)),
    listing(planned(minutes=60), planned("off", at="11:00")),
    listing(planned(minutes=90, days=1)),
    listing(planned("off", days=2), planned(days=3), planned(days=21, minutes=45)),
    *(
        listing(*[planned(at=f"09:{n:02d}") for n in range(count)])
        for count in (3, 5, 11, 21)
    ),
)
"""The slots a handler gives to the answer about what is planned, in the cases it tells
apart: nothing, a command to turn on with a time of its own and without, to turn off,
each of the days words, and the counts of commands of each plural form."""
CANCEL_CASES: Final[Sequence[Mapping[str, Any]]] = (
    cancelling("all"),
    cancelling("next"),
    cancelling("all", planned()),
    cancelling("all", planned(), planned("off")),
    *(
        cancelling("all", *[planned(at=f"09:{n:02d}") for n in range(count)])
        for count in (3, 5, 11, 21)
    ),
    cancelling("next", planned()),
    cancelling("next", planned(minutes=60, days=1)),
    cancelling("next", planned("off", days=2)),
    cancelling("id", planned()),
)
"""The slots a handler gives to the answer about cancelling commands, in the cases it
tells apart: none, the next one (each of the ways a command is said), every one, with
the counts of each plural form, and one by its id."""


def scheduling(
    enabled: bool, interval: str | None = None, count: int = 2
) -> dict[str, Any]:
    """The slots a handler gives to the answer about switching a schedule: the
    schedule of the target, or the one `interval` of it, `enabled` or not, with the
    `count` of intervals switched."""
    return {
        "target": "Boiler",
        "enabled": enabled,
        "interval": interval,
        "count": count,
    }


SCHEDULE_CASES: Final[Sequence[Mapping[str, Any]]] = (
    scheduling(True),
    scheduling(False),
    scheduling(True, count=1),
    scheduling(True, "Morning", count=1),
    scheduling(False, "Morning", count=1),
    scheduling(False, "Morning", count=3),
)
"""The slots a handler gives to the answer about switching a schedule, in the cases it
tells apart: the whole schedule, or an interval by its title, on and off."""

RESPONSE_SLOTS: Final[Mapping[tuple[str, str], Sequence[Mapping[str, Any]]]] = {
    ("TimerifyTimeLeft", "default"): TIMER_CASES,
    ("TimerifyRun", "default"): TIMER_CASES,
    ("TimerifyAddTime", "default"): TIMER_CASES,
    ("TimerifyStop", "default"): TIMER_CASES,
    ("TimerifyDelayedCommand", "delayed"): LATER_CASES,
    ("TimerifyListCommands", "default"): LIST_CASES,
    ("TimerifyCancelCommands", "default"): CANCEL_CASES,
    ("TimerifySetSchedule", "default"): SCHEDULE_CASES,
}
"""For each answer of the sentence files, by intent and response key, the slots a
handler gives it in the cases it tells apart. A task that adds an answer adds its slots
here."""


def translated(language: str, *path: str) -> str:
    """A text of `translations/<language>.json`, by its path."""
    node: Any = json.loads((TRANSLATIONS / f"{language}.json").read_text("utf-8"))
    for key in path:
        node = node[key]
    return str(node)


def reached(response: intent.IntentResponse) -> str | None:
    """The intent the agent handed the sentence to, if it got as far as a handler."""
    return None if response.intent is None else response.intent.intent_type


def refusal_of(response: intent.IntentResponse) -> str:
    """What the answer says when the timer refused: asserts that it did."""
    assert response.response_type is intent.IntentResponseType.ERROR
    assert response.error_code is intent.IntentResponseErrorCode.FAILED_TO_HANDLE
    return speech(response)


async def assert_one_form_per_class(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    language: str,
    classes: PluralClasses,
    say: Callable[[int, int], Awaitable[str]],
) -> None:
    """Within a class of counts the answer `say` gives is the same one (the numbers
    aside), and between the classes no two answers are alike.

    `say(count, minutes_each)` makes the timer count `count` units of `minutes_each`
    minutes, and gives the answer. The clock is moved first to where every count ends
    on the same side of midnight (`LATE_EVENING`).
    """
    await advance_to(hass, freezer, LATE_EVENING)
    forms = []
    for group in classes.russian if language == "ru" else classes.english:
        answers = [
            without_digits(await say(count, classes.minutes_each)) for count in group
        ]
        assert len(set(answers)) == 1, answers
        forms.append(answers[0])
    assert len(set(forms)) == len(forms), forms


def render_response(
    hass: HomeAssistant, template: str, slots: Mapping[str, Any]
) -> str:
    """What the built-in agent says for an answer template and the slots of a handler:
    the template rendered with the variables the agent gives it, and its whitespace
    normalised as the agent does."""
    rendered = Template(template, hass).async_render(
        {
            "slots": dict(slots),
            "state": None,
            "query": {"matched": [], "unmatched": []},
        }
    )
    return " ".join(str(rendered).strip().split())


def without_digits(text: str) -> str:
    """`text` with its numbers taken out, so that two answers that differ only in the
    count compare equal."""
    return re.sub(r"\d+", "", text)


def words(text: str) -> frozenset[str]:
    """The words `text` is made of, without numbers and punctuation: two answers can be
    compared by the words one has and the other has not."""
    return frozenset(re.findall(r"[^\W\d_]+", text))


async def add_voice_entry(
    hass: HomeAssistant,
    *,
    write: bool = True,
    languages: Sequence[str] = VOICE_LANGUAGES,
) -> ConfigEntry:
    """Add the Voice settings entry the way the integrations page does: "Add entry",
    "Voice settings" in the menu, and the form filled in. Returns the entry, set up."""
    menu = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    form = await hass.config_entries.flow.async_configure(
        menu["flow_id"], {"next_step_id": "voice_settings"}
    )
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {CONF_WRITE_SENTENCES: write, CONF_LANGUAGES: list(languages)},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]


async def with_voice_settings(
    hass: HomeAssistant, setup_target: SetupTarget, *targets: FakeTarget
) -> None:
    """Timers on `targets`, which Assist knows by the Voice settings entry: their
    names, and the words for the modes and the presets that they have."""
    for target in targets:
        await setup_target(target=target.entity_id)
    await add_voice_entry(hass)


def managed_file(hass: HomeAssistant, language: str) -> Path:
    """Where the Voice settings entry writes the sentences of `language`."""
    return Path(hass.config.path("custom_sentences", language, "timerify.yaml"))


async def put_file(hass: HomeAssistant, language: str, content: str | bytes) -> Path:
    """Put a file at the path where the Voice settings entry writes the sentences of
    `language`, as a user does who got there first. Returns its path."""
    path = managed_file(hass, language)
    data = content.encode("utf-8") if isinstance(content, str) else content

    def put() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    await hass.async_add_executor_job(put)
    return path


def listed(
    hass: HomeAssistant, language: str, list_name: str = LIST_TARGET
) -> list[dict[str, Any]]:
    """The values of the list `list_name` in the managed file of `language`."""
    written = yaml.safe_load(managed_file(hass, language).read_text("utf-8"))
    values: list[dict[str, Any]] = written["lists"][list_name]["values"]
    return values


def conversation_reloads(hass: HomeAssistant) -> list[ServiceCall]:
    """Start recording the calls of `conversation.reload`; the list fills as they are
    made."""
    calls: list[ServiceCall] = []

    @callback
    def record(event: Event[dict[str, Any]]) -> None:
        if (event.data["domain"], event.data["service"]) == (
            "conversation",
            "reload",
        ):
            calls.append(
                ServiceCall(
                    hass,
                    event.data["domain"],
                    event.data["service"],
                    event.data["service_data"],
                    event.context,
                )
            )

    hass.bus.async_listen(EVENT_CALL_SERVICE, record)
    return calls


async def copy_sentences(
    hass: HomeAssistant,
    names: Sequence[str],
    domains: Mapping[str, str] | None = None,
    intervals: Sequence[str] = (),
) -> None:
    """Install the sentences the manual way: every source file of each language into
    `custom_sentences/<lang>/timerify_manual/`, with a file listing the targets'
    `names` as they are said and shown, and for each name in `domains` the domain of
    its target, which the words for an HVAC mode and a temperature need, and the
    `intervals` titles of the schedules.

    Before the built-in agent's first request in a language, which reads the files
    once.
    """

    def install() -> None:
        for language in VOICE_LANGUAGES:
            directory = Path(
                hass.config.path("custom_sentences", language, MANUAL_SENTENCES_DIR)
            )
            directory.mkdir(parents=True, exist_ok=True)
            for source in (SENTENCES_DIR / language).glob("*.yaml"):
                shutil.copy(source, directory / source.name)
            listed = {
                "language": language,
                "lists": {
                    LIST_TARGET: {
                        "values": [
                            {
                                "in": name,
                                "out": name,
                                **(
                                    {"context": {"domain": domains[name]}}
                                    if name in (domains or {})
                                    else {}
                                ),
                            }
                            for name in names
                        ]
                    },
                    LIST_INTERVAL: {
                        "values": [{"in": title, "out": title} for title in intervals]
                    },
                },
            }
            (directory / NAMES_FILE).write_text(
                yaml.safe_dump(listed, allow_unicode=True), "utf-8"
            )

    await hass.async_add_executor_job(install)


@cache
def _intents_of(language: str, takeover: bool = False) -> Intents:
    """The core sentences of `language` with the shipped sentences of Timerify on top
    and no target listed: those of `OWN_SENTENCES`, or, for `takeover`, the intents of
    `CORE_COMMANDS` in their place, which are said with the lists and rules of the
    first and those of their own file."""
    merged = get_intents(language)
    assert merged is not None, f"home-assistant-intents has no {language}"
    shipped = SENTENCES_DIR / language
    own = read_back((shipped / OWN_SENTENCES).read_text("utf-8"))
    if takeover:
        taken = read_back((shipped / CORE_COMMANDS).read_text("utf-8"))
        own["intents"] = taken["intents"]
        own["expansion_rules"] = {
            **own.get("expansion_rules", {}),
            **taken.get("expansion_rules", {}),
        }
    merge_dict(merged, own)
    return Intents.from_dict(merged)


def _one_value(
    slot_lists: Mapping[str, SlotList],
    names: Sequence[str],
    numbers: Mapping[str, int],
    texts: Mapping[str, str],
    absent: Collection[str],
) -> dict[str, SlotList]:
    """The lists with each cut down to one value, which makes the sampling bounded.

    The target list gets the first of `names` (none: no value); a number list gets its
    number from `numbers`, and no value when `numbers` has none, so that a sentence, or
    a way of saying it, that needs the number cannot be said; a text list gets its
    value from `texts` or else its first, and no value when it is one of `absent`.
    """
    bounded: dict[str, SlotList] = {}
    for name, slot_list in slot_lists.items():
        if name == LIST_TARGET:
            bounded[name] = TextSlotList.from_strings(names[:1], name=name)
        elif isinstance(slot_list, RangeSlotList):
            bounded[name] = TextSlotList.from_strings(
                [str(numbers[name])] if name in numbers else [], name=name
            )
        elif isinstance(slot_list, TextSlotList):
            if name in absent:
                bounded[name] = TextSlotList(name=name, values=[])
            elif name in texts:
                bounded[name] = TextSlotList.from_strings([texts[name]], name=name)
            else:
                bounded[name] = TextSlotList(name=name, values=slot_list.values[:1])
        else:
            bounded[name] = slot_list
    return bounded


def samples(
    language: str,
    intent_type: str,
    *,
    names: Sequence[str] = ("Boiler",),
    numbers: Mapping[str, int],
    texts: Mapping[str, str] | None = None,
    absent: Collection[str] = (),
    takeover: bool = False,
    optionals: bool = True,
) -> list[str]:
    """Sentences of the intent as a user would say them, a bounded number: those of
    `OWN_SENTENCES`, or of `CORE_COMMANDS` for `takeover`.

    Every list is cut down to one value (see `_one_value`) and every sentence
    template is sampled twice: once as its first expansion with the optional parts
    said and the first order of a permutation, once with the optional parts left out;
    a sentence that cannot be said even with them left out is skipped, and with
    `optionals` false only that second sampling is done, which a sentence with many
    optional parts needs: they expand to thousands of texts. The same text is returned
    once. Sampling all expansions of the core's number lists runs to hundreds of
    thousands of sentences.
    """
    intents = _intents_of(language, takeover)
    if intent_type not in intents.intents:
        return []
    found: list[str] = []
    for data in intents.intents[intent_type].data:
        slot_lists = _one_value(
            {**intents.slot_lists, **data.slot_lists},
            names,
            numbers,
            texts or {},
            absent,
        )
        rules = {**intents.expansion_rules, **data.expansion_rules}
        for sentence in data.sentences:
            if (
                minimal := _first_sample(sentence, slot_lists, rules, language, True)
            ) is None:
                continue
            said = (
                _first_sample(sentence, slot_lists, rules, language, False)
                if optionals
                else None
            )
            for text in (said, minimal):
                if text is not None and text not in found:
                    found.append(text)
    return found


EVERY_TEXT_LIMIT: Final = 2000
"""The most texts `every_text` returns, so that an intent with a long list of values is
refused where a bounded sample (`samples`) is meant."""


def _lists_said(sentence: Sentence, rules: Mapping[str, Sentence]) -> set[str]:
    """The names of the lists a sentence says a value of, through the rules it uses and
    the rules those use."""
    names: set[str] = set()
    used: set[str] = set()
    pending = [sentence]
    while pending:
        for reference in references(pending.pop().expression):
            if isinstance(reference, RuleReference):
                if reference.rule_name not in used:
                    used.add(reference.rule_name)
                    pending.append(rules[reference.rule_name])
            elif not (reference.is_inline_range or reference.is_capture):
                names.add(reference.list_name)
    return names


def every_text(
    language: str,
    intent_type: str,
    *,
    name: str = "Boiler",
    interval: str = "Morning",
    numbers: Mapping[str, int] | None = None,
) -> list[tuple[str, Mapping[str, Any]]]:
    """Every text the shipped sentences of the intent can be said as, each with the
    slots its data block fixes.

    Every alternative of every sentence is taken in turn, optional parts said and left
    out, and every value of every list of words: the sentences of the intent are
    expanded in full. The target is the one `name`, the title of a schedule interval
    the one `interval`, and a list of numbers has the one number `numbers` gives it by
    the name of the list. Nothing is left out quietly: a list that a sentence says a
    value of and that has none (a list of numbers that `numbers` does not name, a list
    of words with no values) is an error, and so is an intent that expands to more than
    `EVERY_TEXT_LIMIT` texts, for which `samples` is the bounded sampler.
    """
    intents = _intents_of(language)
    found: list[tuple[str, Mapping[str, Any]]] = []
    for data in intents.intents[intent_type].data:
        slot_lists = {**intents.slot_lists, **data.slot_lists}
        rules = {**intents.expansion_rules, **data.expansion_rules}
        said = {
            list_name
            for sentence in data.sentences
            for list_name in _lists_said(sentence, rules)
        }
        for list_name in sorted(said):
            slot_list = slot_lists[list_name]
            if list_name in (LIST_TARGET, LIST_INTERVAL):
                slot_lists[list_name] = TextSlotList.from_strings(
                    [name if list_name == LIST_TARGET else interval], name=list_name
                )
            elif isinstance(slot_list, RangeSlotList):
                given = (numbers or {}).get(list_name)
                assert given is not None, (
                    f"{intent_type} says a value of {list_name}: give its number"
                )
                slot_lists[list_name] = TextSlotList.from_strings(
                    [str(given)], name=list_name
                )
            else:
                assert isinstance(slot_list, TextSlotList)
                assert slot_list.values, (
                    f"{intent_type} says a value of {list_name}, which has none"
                )
        for sentence in data.sentences:
            found.extend(
                (text.strip(), dict(data.slots))
                for text in islice(
                    sample_sentence(
                        sentence, slot_lists, dict(rules), language=language
                    ),
                    EVERY_TEXT_LIMIT + 1,
                )
            )
    assert len(found) <= EVERY_TEXT_LIMIT, f"{intent_type} expands to too many texts"
    return found


def _first_sample(
    sentence: Sentence,
    slot_lists: Mapping[str, SlotList],
    rules: Mapping[str, Sentence],
    language: str,
    skip_optionals: bool,
) -> str | None:
    """The first text the sentence expands to, if it can be said."""
    first = next(
        iter(
            sample_sentence(
                sentence,
                dict(slot_lists),
                dict(rules),
                language=language,
                skip_optionals=skip_optionals,
            )
        ),
        None,
    )
    return None if first is None else first.strip()


def spoken_values(language: str, list_name: str) -> dict[str, list[str]]:
    """What the shipped list `list_name` of `language` says for each of its values: the
    words that mean it, by what it means. The words of a language are read from the
    sentence files, so that a test can say them without writing them."""
    slot_list = _intents_of(language).slot_lists[list_name]
    assert isinstance(slot_list, TextSlotList)
    return {
        str(value.value_out): list(sample_expression(value.text_in, language=language))
        for value in slot_list.values
    }
