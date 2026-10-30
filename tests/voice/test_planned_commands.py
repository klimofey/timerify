"""Asking by voice what is planned for a device, and cancelling it, in English and
Russian, and through an LLM's tools.

A command is planned the way a user plans it: by voice ("turn on the boiler in 15
minutes for an hour"), or with the service, as an automation does. Every scenario talks
to the real built-in agent, or calls a tool of the real Assist API. Planned commands are
firm promises, so what the answer lists is what will happen, and a cancelled command
never does.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.const import MAX_COMMANDS

from ..conftest import FakeTarget, SetupTarget
from ..helpers import (
    AC_NEXT,
    NEXT,
    NUMBER,
    TURN_ON,
    add_command,
    advance,
    call_service,
    state_of,
)
from .helpers import (
    COMMAND_CLASSES,
    assert_one_form_per_class,
    assist_api,
    call_tool,
    converse,
    every_text,
    reached,
    samples,
    speech,
    translated,
    with_voice_settings,
    without_digits,
    words,
)

LIST = "TimerifyListCommands"
CANCEL = "TimerifyCancelCommands"
PLAN_ON = "turn on the boiler in 15 minutes for an hour"
"""A command that turns the boiler on at 09:15 for an hour."""
PLAN_ON_BARE = "turn on the boiler in 15 minutes"
"""One that turns it on at 09:15 and says nothing more."""
TWO_COMMANDS = (
    "Boiler has 2 planned commands: turn on at 09:15 for 1 hour; turn off at 11:00."
)
LIST_TEXTS = [
    "what is planned for the boiler",
    "what is scheduled for the boiler",
    "what commands are pending for the boiler",
    "what is pending on the boiler",
    "what is planned for boiler",
]
CANCEL_ALL_TEXTS = [
    "cancel the planned commands for the boiler",
    "cancel all planned commands for the boiler",
    "cancel all pending commands of the boiler",
    "cancel the pending commands for boiler",
]
CANCEL_NEXT_TEXTS = [
    "cancel the next planned command for the boiler",
    "cancel the next pending command of the boiler",
    "cancel the next planned command for boiler",
]


def commands_of(hass: HomeAssistant, entity_id: str = NEXT) -> list[dict[str, Any]]:
    """The commands a "Next command" sensor lists in its attributes."""
    state = hass.states.get(entity_id)
    assert state is not None
    commands: list[dict[str, Any]] = state.attributes["commands"]
    return commands


async def plan_two(hass: HomeAssistant) -> None:
    """Plan the boiler to turn on at 09:15 for an hour (by voice) and to turn off at
    11:00 (with the service)."""
    await converse(hass, PLAN_ON)
    await add_command(hass, NUMBER, action="off", delay=120)


class Planner:
    """Keeps exactly as many commands planned for the boiler as a scenario wants."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def plan(self, count: int) -> None:
        """Add commands, or cancel the last ones, until `count` are planned."""
        commands = commands_of(self._hass)
        for command in commands[count:]:
            await call_service(
                self._hass,
                "cancel_command",
                {"entity_id": NUMBER},
                command_id=command["id"],
            )
        for number in range(len(commands), count):
            await add_command(self._hass, NUMBER, action="on", delay=number + 1)


# --- What is planned ---------------------------------------------------------------


async def test_what_is_scheduled_lists_the_commands(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """The answer lists the commands in the order they are due, each with its time and
    how long a turn on runs; what they turn the device on with is not spoken."""
    await plan_two(hass)

    response = await converse(hass, "what is scheduled for the boiler")

    assert reached(response) == LIST
    assert response.response_type is intent.IntentResponseType.QUERY_ANSWER
    assert speech(response) == TWO_COMMANDS


@pytest.mark.parametrize("text", LIST_TEXTS)
async def test_list_phrasings(
    hass: HomeAssistant, boiler: MockConfigEntry, text: str
) -> None:
    await converse(hass, PLAN_ON_BARE)

    response = await converse(hass, text)

    assert reached(response) == LIST, speech(response)
    assert speech(response) == "Boiler has 1 planned command: turn on at 09:15."


async def test_what_is_planned_without_commands(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    response = await converse(hass, "what is planned for the boiler")

    assert response.response_type is intent.IntentResponseType.QUERY_ANSWER
    assert speech(response) == "Boiler has no planned commands."


@pytest.mark.parametrize(
    ("days", "minutes", "said"),
    [
        (1, None, "turn on at 09:00 tomorrow"),
        (1, 90, "turn on at 09:00 tomorrow for 1 hour and 30 minutes"),
        (2, None, "turn on at 09:00 the day after tomorrow"),
        (3, None, "turn on at 09:00 in 3 days"),
        (7, None, "turn on at 09:00 in 7 days"),
    ],
)
async def test_planned_command_tomorrow_says_tomorrow(
    hass: HomeAssistant,
    boiler: MockConfigEntry,
    days: int,
    minutes: int | None,
    said: str,
) -> None:
    """A command that is not due today says on which day, as every answer of Timerify
    does, and the day comes before how long the device then runs."""
    extra = {} if minutes is None else {"minutes": minutes}
    await add_command(hass, NUMBER, action="on", delay=days * 24 * 60, **extra)

    response = await converse(hass, "what is planned for the boiler")

    assert speech(response) == f"Boiler has 1 planned command: {said}."


@pytest.mark.parametrize("language", ["en", "ru"])
async def test_the_day_is_said_only_when_a_command_is_not_due_today(
    hass: HomeAssistant, boiler: MockConfigEntry, language: str
) -> None:
    """A command due today says no day; one due tomorrow adds a word for it, and one
    due two dates on another, in the words of the language."""
    ask = samples(language, LIST, numbers={})[0]
    planner = Planner(hass)

    async def said_for(days: int) -> frozenset[str]:
        await planner.plan(0)
        await add_command(hass, NUMBER, action="on", delay=days * 24 * 60 + 60)
        return words(speech(await converse(hass, ask, language)))

    today = await said_for(0)
    tomorrow = await said_for(1)
    day_after = await said_for(2)

    assert tomorrow > today
    assert day_after > today
    assert tomorrow - today != day_after - today


@pytest.mark.parametrize(
    ("language", "classes"),
    [
        pytest.param("en", ((3, 4, 5, 6, 7),), id="en"),
        pytest.param("ru", ((3, 4), (5, 6, 7)), id="ru"),
    ],
)
async def test_days_ahead_are_counted_by_the_plural_rules(
    hass: HomeAssistant,
    boiler: MockConfigEntry,
    language: str,
    classes: tuple[tuple[int, ...], ...],
) -> None:
    """A command can be planned up to a week ahead, so the days it is away are counted
    with the form of the language: Russian says three and four days one way and five
    to seven another, English every count the same way (the wording is that of every
    answer that names a day)."""
    ask = samples(language, LIST, numbers={})[0]
    planner = Planner(hass)

    async def said_for(days: int) -> str:
        await planner.plan(0)
        await add_command(hass, NUMBER, action="on", delay=days * 24 * 60)
        return without_digits(speech(await converse(hass, ask, language)))

    forms = []
    for group in classes:
        answers = {await said_for(days) for days in group}
        assert len(answers) == 1, answers
        forms.append(answers.pop())

    assert len(set(forms)) == len(forms), forms


async def test_commands_are_listed_in_the_order_they_are_due(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    await add_command(hass, NUMBER, action="off", delay=180)
    await add_command(hass, NUMBER, action="on", delay=30, minutes=10)
    await add_command(hass, NUMBER, action="on", delay=60)

    response = await converse(hass, "what is planned for the boiler")

    assert speech(response) == (
        "Boiler has 3 planned commands: turn on at 09:30 for 10 minutes;"
        " turn on at 10:00; turn off at 12:00."
    )


@pytest.mark.usefixtures("assist")
async def test_what_a_command_turns_the_device_on_with_is_not_spoken(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The cooling and the 24 degrees are kept with the command (and an LLM is told
    them), but the answer says only when, and for how long."""
    await with_voice_settings(hass, setup_target, fake_climate)
    await converse(hass, "turn on the AC in 15 minutes for an hour, cooling, 24")

    response = await converse(hass, "what is planned for the AC")

    assert speech(response) == "AC has 1 planned command: turn on at 09:15 for 1 hour."
    assert commands_of(hass, AC_NEXT)[0]["settings"] == {
        "hvac_mode": "cool",
        "temperature": 24.0,
    }


async def test_planning_lists_and_cancelling_in_one_conversation(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """What a person does: plans two things, asks what is planned, drops the first,
    asks again."""
    await plan_two(hass)

    await converse(hass, "cancel the next planned command for the boiler")
    response = await converse(hass, "what is planned for the boiler")

    assert speech(response) == "Boiler has 1 planned command: turn off at 11:00."


# --- Cancelling --------------------------------------------------------------------


async def test_cancel_all_planned_commands(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """Each way to say it cancels every command, and says how many."""
    for text in CANCEL_ALL_TEXTS:
        await plan_two(hass)

        response = await converse(hass, text)

        assert reached(response) == CANCEL, text
        assert response.response_type is intent.IntentResponseType.ACTION_DONE, text
        assert speech(response) == "Cancelled 2 planned commands for Boiler.", text
        assert commands_of(hass) == [], text
        assert state_of(hass, NEXT) == "unknown", text


async def test_cancel_the_next_planned_command(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """Each way to say it cancels the command that is due first, whatever order they
    were planned in, and says which."""
    for text in CANCEL_NEXT_TEXTS:
        await add_command(hass, NUMBER, action="off", delay=120)
        await converse(hass, PLAN_ON_BARE)

        response = await converse(hass, text)

        assert reached(response) == CANCEL, text
        assert response.response_type is intent.IntentResponseType.ACTION_DONE, text
        assert speech(response) == (
            "Cancelled the next planned command for Boiler: turn on at 09:15."
        ), text
        assert [c["action"] for c in commands_of(hass)] == ["off"], text
        await Planner(hass).plan(0)


async def test_cancelling_the_only_command_says_so_in_the_singular(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    await converse(hass, PLAN_ON_BARE)

    response = await converse(hass, "cancel all planned commands for the boiler")

    assert speech(response) == "Cancelled 1 planned command for Boiler."
    assert commands_of(hass) == []


@pytest.mark.parametrize("text", [CANCEL_ALL_TEXTS[0], CANCEL_NEXT_TEXTS[0]])
async def test_cancel_without_commands_says_so(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry, text: str
) -> None:
    """Cancelling what is not there is not a failure, and it changes nothing."""
    response = await converse(hass, text)

    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert (
        speech(response) == "Boiler has no planned commands, so nothing was cancelled."
    )
    assert fake_target.calls == []


@pytest.mark.parametrize(
    ("text", "calls_at_half_past"),
    [
        pytest.param(CANCEL_NEXT_TEXTS[0], [TURN_ON], id="the-next"),
        pytest.param(CANCEL_ALL_TEXTS[0], [], id="all"),
    ],
)
async def test_cancelled_command_does_not_run(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    text: str,
    calls_at_half_past: list[tuple[str, str]],
) -> None:
    """A command is a promise (P1) that only an explicit cancel breaks: the one that is
    cancelled does not turn the boiler on, and the one that is not, does."""
    await converse(hass, PLAN_ON_BARE)
    await converse(hass, "turn on the boiler in 30 minutes")

    await converse(hass, text)
    await advance(hass, freezer, minutes=15)
    assert fake_target.calls == []
    await advance(hass, freezer, minutes=15)

    assert fake_target.calls == calls_at_half_past
    assert state_of(hass, NEXT) == "unknown"


async def test_a_command_planned_after_cancelling_runs(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
) -> None:
    await converse(hass, PLAN_ON_BARE)
    await converse(hass, "cancel all planned commands for the boiler")
    await converse(hass, "turn on the boiler in 5 minutes")

    await advance(hass, freezer, minutes=5)

    assert fake_target.calls == [TURN_ON]


# --- Words that are not about a timer ----------------------------------------------


@pytest.mark.parametrize(
    "text", [LIST_TEXTS[0], CANCEL_ALL_TEXTS[1], CANCEL_NEXT_TEXTS[0]]
)
async def test_the_same_words_about_a_device_without_a_timer_do_nothing(
    hass: HomeAssistant,
    fake_fan: FakeTarget,
    boiler: MockConfigEntry,
    text: str,
) -> None:
    """The names Timerify is told are the only ones its phrases are about: another
    device is not asked about, and nothing is cancelled for it."""
    text = text.replace("boiler", "fan")
    await converse(hass, PLAN_ON_BARE)

    response = await converse(hass, text)

    assert response.response_type is intent.IntentResponseType.ERROR
    assert fake_fan.calls == []
    assert len(commands_of(hass)) == 1


# --- Russian -----------------------------------------------------------------------


async def assert_every_sentence_reaches_its_intent(
    hass: HomeAssistant, language: str, intent_type: str
) -> None:
    """Every way the sentence files have to say `intent_type` reaches its handler with
    the target's name and, for a cancel, with the commands it means."""
    texts = every_text(language, intent_type)
    assert texts

    for text, fixed in texts:
        response = await converse(hass, text, language)

        assert reached(response) == intent_type, text
        assert response.intent is not None
        assert response.intent.slots["name"]["value"] == "Boiler", text
        assert {
            slot: response.intent.slots[slot]["value"] for slot in fixed
        } == fixed, text
    if intent_type == CANCEL:
        assert {fixed["which"] for _, fixed in texts} == {"all", "next"}


@pytest.mark.parametrize("intent_type", [LIST, CANCEL])
async def test_russian_sentences_reach_their_intent(
    hass: HomeAssistant, boiler: MockConfigEntry, intent_type: str
) -> None:
    """The Russian sentences, in every way they can be said, reach their handler."""
    await assert_every_sentence_reaches_its_intent(hass, "ru", intent_type)


@pytest.mark.parametrize("intent_type", [LIST, CANCEL])
async def test_english_sentences_reach_their_intent(
    hass: HomeAssistant, boiler: MockConfigEntry, intent_type: str
) -> None:
    await assert_every_sentence_reaches_its_intent(hass, "en", intent_type)


async def test_russian_answer_names_the_target_and_lists_the_times_in_order(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    await plan_two(hass)
    ask = samples("ru", LIST, numbers={})[0]

    response = await converse(hass, ask, language="ru")

    assert response.response_type is intent.IntentResponseType.QUERY_ANSWER
    said = speech(response)
    assert said.startswith("Boiler: ")
    assert " 2 " in said
    assert said.index("09:15") < said.index("11:00")


async def test_russian_answer_without_commands_has_no_count(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    ask = samples("ru", LIST, numbers={})[0]

    response = await converse(hass, ask, language="ru")

    assert speech(response).startswith("Boiler: ")
    assert not any(digit in speech(response) for digit in "0123456789")


def count_of_the_list(answer: str) -> str:
    """The part of the answer to "what is planned" that says how many commands there
    are: what comes before the list, which follows the last colon and a space (the
    times in it have colons of their own, and its items are set apart by semicolons)."""
    return answer.rsplit(": ", 1)[0]


async def counted_in_the_list(
    hass: HomeAssistant, language: str
) -> Callable[[int, int], Awaitable[str]]:
    """What the answer to "what is planned" says of the count, once that many commands
    are planned, as `assert_one_form_per_class` asks for it."""
    ask = samples(language, LIST, numbers={})[0]
    planner = Planner(hass)

    async def say(count: int, minutes_each: int) -> str:
        await planner.plan(count)
        return count_of_the_list(speech(await converse(hass, ask, language)))

    return say


async def test_russian_planned_commands_follow_the_plural_rules(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, boiler: MockConfigEntry
) -> None:
    """Russian says one command, two to four and five or more in three ways, by the
    last digits of the number, and a count the same way wherever it is in the list's
    reach (at most `MAX_COMMANDS`). The test proves the split, not which word each
    class takes."""
    assert max(sum(COMMAND_CLASSES.russian, ())) <= MAX_COMMANDS
    say = await counted_in_the_list(hass, "ru")

    await assert_one_form_per_class(hass, freezer, "ru", COMMAND_CLASSES, say)


async def test_english_planned_commands_follow_the_plural_rules(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, boiler: MockConfigEntry
) -> None:
    say = await counted_in_the_list(hass, "en")

    await assert_one_form_per_class(hass, freezer, "en", COMMAND_CLASSES, say)


def cancel_all_sentence(language: str) -> str:
    """A sentence of `language` that cancels every command."""
    return next(
        text for text, fixed in every_text(language, CANCEL) if fixed["which"] == "all"
    )


@pytest.mark.parametrize("language", ["en", "ru"])
async def test_cancelled_commands_follow_the_plural_rules(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    boiler: MockConfigEntry,
    language: str,
) -> None:
    cancel_all = cancel_all_sentence(language)
    planner = Planner(hass)

    async def say(count: int, minutes_each: int) -> str:
        await planner.plan(count)
        return speech(await converse(hass, cancel_all, language))

    await assert_one_form_per_class(hass, freezer, language, COMMAND_CLASSES, say)


# --- Through an LLM's tools --------------------------------------------------------


async def test_llm_lists_and_cancels_by_id(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """The agent lists the commands and gets an id for each; it cancels one by its id
    and is told which, and an id that is not there is explained."""
    api = await assist_api(hass)
    await call_tool(
        api,
        "timerify__delayed_command",
        {"name": "Boiler", "action": "on", "delay_minutes": 15, "minutes": 60},
    )
    await add_command(hass, NUMBER, action="off", delay=120)

    listed = await call_tool(api, "timerify__list_commands", {"name": "Boiler"})

    assert listed["response_type"] == "query_answer"
    slots = listed["speech_slots"]
    assert slots["target"] == "Boiler"
    assert slots["count"] == 2
    first, second = slots["commands"]
    assert [first["action"], second["action"]] == ["on", "off"]
    assert (first["at"], first["in_days"], first["minutes"]) == ("09:15", 0, 60)
    assert (second["at"], second["in_days"], second["minutes"]) == ("11:00", 0, None)
    assert first["settings"] == second["settings"] == {}
    assert first["id"] != second["id"]

    cancelled = await call_tool(
        api, "timerify__cancel_commands", {"name": "Boiler", "command_id": first["id"]}
    )

    assert cancelled["response_type"] == "action_done"
    assert cancelled["speech_slots"]["cancelled"] == 1
    assert cancelled["speech_slots"]["commands"] == [first]
    assert [c["id"] for c in commands_of(hass)] == [second["id"]]

    refused = await call_tool(
        api, "timerify__cancel_commands", {"name": "Boiler", "command_id": first["id"]}
    )

    assert refused["response_type"] == "error"
    assert refused["speech"]["plain"]["speech"] == translated(
        "en", "exceptions", "unknown_command", "message"
    ).format(command_id=first["id"])
    assert [c["id"] for c in commands_of(hass)] == [second["id"]]


@pytest.mark.usefixtures("assist")
async def test_llm_is_told_what_a_command_turns_the_device_on_with(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    await with_voice_settings(hass, setup_target, fake_climate)
    api = await assist_api(hass)
    await call_tool(
        api,
        "timerify__delayed_command",
        {
            "name": "AC",
            "action": "on",
            "delay_minutes": 15,
            "minutes": 60,
            "hvac_mode": "cool",
            "temperature": 24,
        },
    )

    listed = await call_tool(api, "timerify__list_commands", {"name": "AC"})

    (command,) = listed["speech_slots"]["commands"]
    assert command["settings"] == {"hvac_mode": "cool", "temperature": 24.0}


async def test_llm_cancel_without_which_cancels_all(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """`which` is optional and means all, as the tool's description says."""
    api = await assist_api(hass)
    await plan_two(hass)

    cancelled = await call_tool(api, "timerify__cancel_commands", {"name": "Boiler"})

    slots = cancelled["speech_slots"]
    assert slots["which"] == "all"
    assert slots["cancelled"] == 2
    assert [c["action"] for c in slots["commands"]] == ["on", "off"]
    assert commands_of(hass) == []


@pytest.mark.parametrize(
    ("args", "which", "left"),
    [
        ({"which": "next"}, "next", ["off"]),
        ({"which": "all"}, "all", []),
    ],
)
async def test_llm_cancels_the_next_or_all(
    hass: HomeAssistant,
    boiler: MockConfigEntry,
    args: dict[str, str],
    which: str,
    left: list[str],
) -> None:
    api = await assist_api(hass)
    await plan_two(hass)

    cancelled = await call_tool(
        api, "timerify__cancel_commands", {"name": "Boiler", **args}
    )

    assert cancelled["speech_slots"]["which"] == which
    assert [c["action"] for c in commands_of(hass)] == left


async def test_llm_cancels_nothing_when_nothing_is_planned(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    api = await assist_api(hass)

    listed = await call_tool(api, "timerify__list_commands", {"name": "Boiler"})
    cancelled = await call_tool(api, "timerify__cancel_commands", {"name": "Boiler"})

    assert listed["speech_slots"]["count"] == 0
    assert listed["speech_slots"]["commands"] == []
    assert cancelled["response_type"] == "action_done"
    assert cancelled["speech_slots"]["cancelled"] == 0
    assert cancelled["speech_slots"]["commands"] == []


async def test_llm_is_told_in_the_language_of_the_request(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    api = await assist_api(hass, language="ru")

    refused = await call_tool(
        api, "timerify__cancel_commands", {"name": "Boiler", "command_id": "gone"}
    )

    assert refused["speech"]["plain"]["speech"] == translated(
        "ru", "exceptions", "unknown_command", "message"
    ).format(command_id="gone")
