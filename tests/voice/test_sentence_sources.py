"""The sentence sources Timerify ships for the built-in agent, and the handlers behind
them: what the files hold, in every language, before a user's names are added to them.
"""

from typing import Any

import pytest
import yaml
from hassil.intents import Intents, RangeSlotList
from hassil.util import merge_dict
from home_assistant_intents import get_intents
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from custom_components.timerify.const import (
    LIST_TARGET,
    SENTENCES_DIR,
    VOICE_LANGUAGES,
)
from custom_components.timerify.voice import HANDLER_TYPES
from custom_components.timerify.voice.base import TimerifyIntentHandler

from ..conftest import FakeTarget, SetupTarget
from .helpers import load_sources, samples

PREFIX = "timerify_"
INTENDED_SLOT_VALUES: dict[str, tuple[type, tuple[Any, ...]]] = {
    "action": (str, ("on", "off")),
    "which": (str, ("all", "next")),
    "enabled": (bool, (True, False)),
}
"""For each slot that a data block of the sources may fix: the type and the values it
is meant to have. YAML 1.1 reads an unquoted on or off as a boolean."""


def timerify_intents(language: str) -> Intents:
    """The core sentences of the language with Timerify's sources merged in."""
    merged = get_intents(language)
    assert merged is not None
    merge_dict(merged, load_sources(language))
    return Intents.from_dict(merged)


def misplaced_slots(sources: dict[str, Any]) -> list[str]:
    """The fixed slot values of the sources that are not of the type and value they
    are meant to be, or that are not meant to be there at all."""
    problems = []
    for name, intent_dict in sources.get("intents", {}).items():
        for data in intent_dict["data"]:
            for slot, value in data.get("slots", {}).items():
                if slot not in INTENDED_SLOT_VALUES:
                    problems.append(f"{name}: slot {slot} has no intended type")
                    continue
                kind, allowed = INTENDED_SLOT_VALUES[slot]
                if type(value) is not kind or value not in allowed:
                    problems.append(f"{name}: slot {slot} is {value!r}")
    return problems


def test_voice_languages_are_the_sentence_directories() -> None:
    """A language is offered exactly when sentences are shipped for it."""
    directories = {path.name for path in SENTENCES_DIR.iterdir() if path.is_dir()}

    assert directories == set(VOICE_LANGUAGES)


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_sources_load_with_core_and_without_names(language: str) -> None:
    """The sources are valid next to the core sentences of their language, every
    sentence of every Timerify intent parses, and with no target listed nothing can be
    said."""
    intents = timerify_intents(language)
    ranges = {
        name: 1
        for name, slot_list in intents.slot_lists.items()
        if isinstance(slot_list, RangeSlotList)
    }
    timerify = {
        name: parsed
        for name, parsed in intents.intents.items()
        if name.startswith("Timerify")
    }

    assert timerify
    for name, parsed in timerify.items():
        for data in parsed.data:
            assert data.sentences, name
        assert samples(language, name, names=(), numbers=ranges) == [], name


def test_every_language_has_the_same_intents_and_responses() -> None:
    """Each language answers every sentence it understands, and understands the same
    intents."""
    intents_of = {}
    for language in VOICE_LANGUAGES:
        sources = load_sources(language)
        responses = sources["responses"]["intents"]
        for name, intent_dict in sources["intents"].items():
            for data in intent_dict["data"]:
                key = data.get("response", "default")
                assert responses.get(name, {}).get(key), (language, name, key)
        intents_of[language] = set(sources["intents"])

    assert len(set(map(frozenset, intents_of.values()))) == 1, intents_of


def test_source_lists_and_rules_are_prefixed() -> None:
    """Whatever the sources define shares a namespace with the core's lists and
    expansion rules, and with the other custom sentences of the house."""
    for language in VOICE_LANGUAGES:
        sources = load_sources(language)
        defined = set(sources.get("lists", {})) | set(
            sources.get("expansion_rules", {})
        )
        for intent_dict in sources["intents"].values():
            for data in intent_dict["data"]:
                defined |= set(data.get("lists", {})) | set(
                    data.get("expansion_rules", {})
                )

        assert LIST_TARGET in defined
        assert all(name.startswith(PREFIX) for name in defined), (language, defined)


def test_fixed_slot_values_have_their_intended_types() -> None:
    """A slot a sentence fixes is a quoted string or a real boolean, never what YAML
    1.1 makes of an unquoted on or off."""
    for language in VOICE_LANGUAGES:
        assert misplaced_slots(load_sources(language)) == [], language


def test_an_unquoted_on_would_be_caught() -> None:
    """The check above sees the surprise it is there for."""
    unquoted = yaml.safe_load(
        "intents:\n  X:\n    data:\n      - sentences: [a]\n        slots: {action: on}"
    )
    unknown = yaml.safe_load(
        "intents:\n  X:\n    data:\n      - sentences: [a]\n        slots: {mood: calm}"
    )

    assert misplaced_slots(unquoted) == ["X: slot action is True"]
    assert misplaced_slots(unknown) == ["X: slot mood has no intended type"]


async def test_handlers_are_registered_once_per_intent(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Setting up timers, one after another, registers each handler once: a second
    registration would replace the first and warn."""
    await setup_target()
    await hass.config_entries.async_reload(
        hass.config_entries.async_entries("timerify")[0].entry_id
    )
    await hass.async_block_till_done()

    registered = sorted(
        handler.intent_type
        for handler in intent.async_get(hass)
        if isinstance(handler, TimerifyIntentHandler)
    )
    assert registered == sorted(handler.intent_type for handler in HANDLER_TYPES)
    assert len(set(registered)) == len(registered)
    assert "is being overwritten" not in caplog.text
