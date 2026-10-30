"""Helpers of the voice tests: talking to the built-in agent, and its sentences.

Russian is tested without a Russian letter in a test: the inputs are sampled from the
sentence files (`samples`), and the answers are compared with each other, not with
words (`without_digits`, `PluralClasses`).
"""

import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Final

import yaml
from hassil.intents import Intents, RangeSlotList, SlotList, TextSlotList
from hassil.sample import sample_sentence
from hassil.util import merge_dict
from home_assistant_intents import get_intents
from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import (
    async_expose_entity,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent

from custom_components.timerify.const import (
    LIST_TARGET,
    SENTENCES_DIR,
    VOICE_LANGUAGES,
)

ASSISTANT: Final = "conversation"
"""The assistant the built-in agent asks Home Assistant about exposure as."""
MANUAL_DIR: Final = "timerify_manual"
"""The directory of `custom_sentences/<lang>/` that the manual installation copies the
sentence files into."""
NAMES_FILE: Final = "timerify_names.yaml"
"""The file of the manual installation that lists the targets' names."""


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


def expose(hass: HomeAssistant, entity_id: str, exposed: bool) -> None:
    """Expose the entity to Assist, or stop doing it."""
    async_expose_entity(hass, ASSISTANT, entity_id, exposed)


def without_digits(text: str) -> str:
    """`text` with its numbers taken out, so that two answers that differ only in the
    count compare equal."""
    return re.sub(r"\d+", "", text)


def words(text: str) -> frozenset[str]:
    """The words `text` is made of, without numbers and punctuation: two answers can be
    compared by the words one has and the other has not."""
    return frozenset(re.findall(r"[^\W\d_]+", text))


def load_sources(language: str) -> dict[str, Any]:
    """The sentence sources of `language` as the built-in agent reads them: every file
    of the language's directory, merged, the YAML read by the agent's own loader."""
    sources: dict[str, Any] = {}
    for path in sorted((SENTENCES_DIR / language).glob("*.yaml")):
        merge_dict(sources, yaml.safe_load(path.read_text("utf-8")))
    return sources


async def copy_sentences(hass: HomeAssistant, names: Sequence[str]) -> None:
    """Install the sentences the manual way: every source file of each language into
    `custom_sentences/<lang>/timerify_manual/`, with a file listing the targets'
    `names` as they are said and shown.

    Before the built-in agent's first request in a language, which reads the files
    once.
    """

    def install() -> None:
        for language in VOICE_LANGUAGES:
            directory = Path(hass.config.path("custom_sentences", language, MANUAL_DIR))
            directory.mkdir(parents=True, exist_ok=True)
            for source in (SENTENCES_DIR / language).glob("*.yaml"):
                shutil.copy(source, directory / source.name)
            listed = {
                "language": language,
                "lists": {
                    LIST_TARGET: {
                        "values": [{"in": name, "out": name} for name in names]
                    }
                },
            }
            (directory / NAMES_FILE).write_text(
                yaml.safe_dump(listed, allow_unicode=True), "utf-8"
            )

    await hass.async_add_executor_job(install)


@cache
def _intents_of(language: str) -> Intents:
    """The core sentences of `language` with the Timerify sources on top and no
    target listed."""
    merged = get_intents(language)
    assert merged is not None, f"home-assistant-intents has no {language}"
    merge_dict(merged, load_sources(language))
    return Intents.from_dict(merged)


def _one_value(
    slot_lists: Mapping[str, SlotList],
    names: Sequence[str],
    numbers: Mapping[str, int],
    texts: Mapping[str, str],
) -> dict[str, SlotList]:
    """The lists with each cut down to one value, which makes the sampling bounded.

    The target list gets the first of `names` (none: no value); a number list gets its
    number from `numbers`, and is left out, so that a sentence that uses it fails to
    sample, when `numbers` has none; a text list gets its value from `texts` or else
    its first.
    """
    bounded: dict[str, SlotList] = {}
    for name, slot_list in slot_lists.items():
        if name == LIST_TARGET:
            bounded[name] = TextSlotList.from_strings(names[:1], name=name)
        elif isinstance(slot_list, RangeSlotList):
            if name in numbers:
                bounded[name] = TextSlotList.from_strings(
                    [str(numbers[name])], name=name
                )
        elif isinstance(slot_list, TextSlotList):
            if name in texts:
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
) -> list[str]:
    """Sentences of the intent as a user would say them, a bounded number.

    Every list is cut down to one value (see `_one_value`) and every sentence
    template is sampled twice: once as its first expansion with the optional parts
    said and the first order of a permutation, once with the optional parts left out.
    The same text is returned once. Sampling all expansions of the core's number
    lists runs to hundreds of thousands of sentences.
    """
    intents = _intents_of(language)
    found: list[str] = []
    for data in intents.intents[intent_type].data:
        slot_lists = _one_value(
            {**intents.slot_lists, **data.slot_lists}, names, numbers, texts or {}
        )
        rules = {**intents.expansion_rules, **data.expansion_rules}
        for sentence in data.sentences:
            for skip_optionals in (False, True):
                first = next(
                    iter(
                        sample_sentence(
                            sentence,
                            slot_lists,
                            rules,
                            language=language,
                            skip_optionals=skip_optionals,
                        )
                    ),
                    None,
                )
                if first is not None and (text := first.strip()) not in found:
                    found.append(text)
    return found
