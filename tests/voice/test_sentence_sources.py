"""The sentence sources Timerify ships for the built-in agent, and the handlers behind
them: what the files hold, in every language, before a user's names are added to them.
"""

from typing import Any

import pytest
import yaml
from hassil.intents import Intents, RangeFractionType, RangeSlotList
from hassil.util import merge_dict
from home_assistant_intents import get_intents
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from custom_components.timerify.const import (
    LIST_TARGET,
    MAX_DELAY_MINUTES,
    MAX_MINUTES,
    SENTENCES_DIR,
    VOICE_LANGUAGES,
)
from custom_components.timerify.voice import HANDLER_TYPES
from custom_components.timerify.voice.base import TimerifyIntentHandler
from custom_components.timerify.voice.sentences import load_sources

from ..conftest import FakeTarget, SetupTarget
from . import helpers
from .helpers import every_text, samples

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
        for takeover in (False, True):
            assert (
                samples(language, name, names=(), numbers=ranges, takeover=takeover)
                == []
            ), (name, takeover)


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_a_duration_can_be_said_past_the_longest_timer(language: str) -> None:
    """The counts of hours and of minutes reach as far as a week, the longest delay a
    command takes, in every language: a timer never runs for more than a day, and a
    duration beyond it must reach the handler, which clamps it when time is added and
    refuses it when the timer is run, rather than be answered as not understood.

    Minutes up to a day can be said as words as well as in digits; the minutes beyond
    a day only in digits, a list of their own that fills the same slot, so that no
    language has to build its table of number words for a week of minutes."""
    lists = timerify_intents(language).slot_lists
    hours = lists["timerify_hours"]
    minutes = lists["timerify_minutes"]
    long_minutes = lists["timerify_long_minutes"]

    assert isinstance(hours, RangeSlotList)
    assert isinstance(minutes, RangeSlotList)
    assert isinstance(long_minutes, RangeSlotList)
    assert (hours.start, hours.stop) == (1, MAX_DELAY_MINUTES // 60)
    assert hours.stop * 60 > MAX_MINUTES
    assert (minutes.start, minutes.stop) == (1, MAX_MINUTES)
    assert (long_minutes.start, long_minutes.stop) == (
        MAX_MINUTES + 1,
        MAX_DELAY_MINUTES,
    )
    assert minutes.words
    assert not long_minutes.words
    assert long_minutes.digits


def costly_words(slot_list: RangeSlotList) -> list[str]:
    """What makes the words of a range cost more than a day of minutes would: the first
    request in a language builds a table of the number words of every number a range
    holds (fractions as well as whole numbers), so it grows with how many there are and,
    since a larger number is more words, with how large the largest is."""
    problems = []
    if sum(1 for _ in slot_list.get_numbers()) > MAX_MINUTES:
        problems.append("holds more numbers than a day has minutes")
    if slot_list.stop > MAX_MINUTES:
        problems.append("goes past the number of minutes in a day")
    return problems


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_numbers_said_as_words_stay_within_a_day(language: str) -> None:
    """The first request in a language builds a table of the number words of every
    range that may be said as words, and what it costs grows with the size of the
    ranges: about 0.3 s for a day of minutes in Russian, and 4.5 s and 120 MB for a
    week. So the range lists of Timerify that allow words neither hold more numbers
    than a day has minutes nor go past that number, whatever they count; a longer one
    has to be said in digits only."""
    spoken = {
        name: slot_list
        for name, slot_list in timerify_intents(language).slot_lists.items()
        if name.startswith(PREFIX)
        and isinstance(slot_list, RangeSlotList)
        and slot_list.words
    }

    assert {"timerify_hours", "timerify_minutes", "timerify_temperature"} <= set(spoken)
    for name, slot_list in spoken.items():
        assert isinstance(slot_list, RangeSlotList)
        assert costly_words(slot_list) == [], name


def test_the_cost_of_words_is_bounded_by_where_a_range_ends_as_well_as_its_size() -> (
    None
):
    """A range of few numbers that begins late is as costly as one that begins at one:
    its words are long. And a range with fractions holds twice the numbers it seems
    to."""
    assert costly_words(RangeSlotList(start=1, stop=MAX_MINUTES, name="a")) == []
    assert costly_words(RangeSlotList(start=5000, stop=5100, name="b")) == [
        "goes past the number of minutes in a day"
    ]
    halves = RangeSlotList(
        start=1,
        stop=MAX_MINUTES // 2 + 1,
        fraction_type=RangeFractionType.HALVES,
        name="c",
    )
    assert costly_words(halves) == ["holds more numbers than a day has minutes"]


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_a_temperature_can_be_said_as_high_as_a_water_heater_is_set(
    language: str,
) -> None:
    """A water heater that counts in Fahrenheit is set at 110 to 140 degrees, and water
    boils at 212, so a temperature is understood up to 250, the bound of the service
    form's selector, in halves, and as words as well as digits: that is 500 numbers,
    well within what a day of minutes costs. What the device cannot take is refused by
    the controller, which knows the device."""
    temperature = timerify_intents(language).slot_lists["timerify_temperature"]

    assert isinstance(temperature, RangeSlotList)
    assert (temperature.start, temperature.stop) == (1, 250)
    assert temperature.fraction_type is RangeFractionType.HALVES
    assert temperature.words
    assert temperature.digits


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
    assert "is being overwritten" not in caplog.text


ADD_TIME_NUMBERS = {
    "timerify_hours": 1,
    "timerify_minutes": 1,
    "timerify_long_minutes": MAX_MINUTES + 1,
    "timerify_minutes_of_hour": 1,
}
"""The numbers with which the sentences that add time can be said."""


def test_every_text_has_every_alternative_and_every_word_of_a_list() -> None:
    """The sentences of an intent are expanded in full: each of the three phrases of
    the list of duration words, each article, and the sentence once."""
    texts = [
        text
        for text, _ in every_text("en", "TimerifyAddTime", numbers=ADD_TIME_NUMBERS)
    ]

    assert len(texts) == len(set(texts))
    for phrase in ("an hour", "half an hour", "an hour and a half"):
        for article in ("the ", "my ", "our ", ""):
            assert f"add {phrase} to {article}Boiler" in texts


def test_every_text_says_what_a_block_fixes() -> None:
    fixed = {
        text: slots
        for text, slots in every_text("en", "TimerifyCancelCommands")
        if "next" in text
    }

    assert fixed
    assert all(slots == {"which": "next"} for slots in fixed.values())


def test_every_text_does_not_leave_out_what_it_cannot_say() -> None:
    """A list of numbers it is not given, and a list of words with nothing in it, are
    refused: a smaller set of texts would pass for the whole one."""
    with pytest.raises(AssertionError, match="timerify_hours: give its number"):
        every_text("en", "TimerifyAddTime")
    with pytest.raises(AssertionError, match="timerify_mode, which has none"):
        every_text(
            "en",
            "TimerifyRun",
            numbers={
                "timerify_hours": 1,
                "timerify_minutes": 1,
                "timerify_long_minutes": MAX_MINUTES + 1,
                "timerify_minutes_of_hour": 1,
                "timerify_percent": 1,
                "timerify_temperature": 1,
            },
        )


def test_every_text_refuses_an_intent_it_cannot_expand_in_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(helpers, "EVERY_TEXT_LIMIT", 5)

    with pytest.raises(AssertionError, match="too many texts"):
        every_text("en", "TimerifyListCommands")
