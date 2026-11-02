"""Turning a device that has a timer on or off, and planning that for later, with the
words Home Assistant already understands for any device.

Every scenario talks to the real built-in agent, or calls a tool of the real Assist API.
"Turn on the boiler" starts its timer instead of only switching it, "turn off the boiler
in ten minutes" sets the timer, "turn on the AC in 15 minutes for an hour, cooling, 24"
keeps a command that waits; and a device without a timer, or a sentence that is about
more than the device, stays with Home Assistant. What is said is taken from the intents
of Home Assistant, not retyped, so a Russian test needs no Russian letter.
"""

import copy
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import timedelta
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from hassil.intents import Intents, TextSlotList
from hassil.parse_expression import parse_sentence
from hassil.sample import sample_sentence
from home_assistant_intents import get_intents
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import intent
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.const import SENTENCES_DIR, VOICE_LANGUAGES
from custom_components.timerify.domains import SUPPORTED_DOMAINS
from custom_components.timerify.voice.sentences import read_back
from scripts.generate_core_commands import (
    CLOCK_AFTER_EXTRAS_RULE_NAME,
    CLOCK_AFTER_RULE_NAME,
    CLOCK_BEFORE_RULE_NAME,
    CLOCK_COMMAND,
    COMMAND,
    COMMAND_RULE,
    COMMAND_RULE_NAME,
    COMMAND_SLOT,
    DELAY_AFTER_RULE_NAME,
    DELAY_BEFORE_RULE_NAME,
    DELAY_LISTS,
    DELAYED_COMMAND,
    EXTRAS,
    FILE_NAME,
    OWN_DELAY_RULE,
    SOURCE_FILE,
    TIMERIFY_COMMANDS,
    CommandBlock,
    clock_blocks,
    command_blocks,
    command_group,
    delay_rules,
    delayed_shapes,
    render,
    run_scopes,
    timed_sentences,
)

from ..conftest import FakeTarget, SetupTarget
from ..helpers import (
    AC_ID,
    AC_NEXT,
    AC_NUMBER,
    NEXT,
    NUMBER,
    SENSOR,
    SMALL_AC_NEXT,
    START,
    TURN_OFF,
    TURN_ON,
    advance,
    at,
    call_service,
    set_number,
    state_of,
)
from .helpers import (
    SETTING_LISTS,
    assist_api,
    call_tool,
    converse,
    copy_sentences,
    pending,
    reached,
    readings,
    refusal_of,
    samples,
    speech,
    spoken_number,
    spoken_values,
    talk,
    translated,
    with_voice_settings,
)

RUN = TIMERIFY_COMMANDS["on"]
STOP = TIMERIFY_COMMANDS["off"]
CORE_INTENTS = {"on": "HassTurnOn", "off": "HassTurnOff"}
COOL = ("set_hvac_mode", {"hvac_mode": "cool"})
TEMPERATURE_24 = ("set_temperature", {"temperature": 24.0})
COOL_24 = [COOL, TEMPERATURE_24]
"""The calls that turn the air conditioner on cooling, at 24 degrees."""
TANK_NUMBER = "number.tank_run_for"
WITH_AND = "<timerify_duration_with_and>"
"""What a thermostat and a water heater make of how long a command runs."""
DELAY_VALUES = {"hours": 2, "minutes": 15, "seconds": 30}
"""What the samples say for each unit of a delay."""
DAYS_LIST = "timerify_delay_days"
WEEKS_LIST = "timerify_delay_weeks"
WORDS_LIST = "timerify_delay_words"
"""The lists of the delay in days and weeks: the days, the weeks, and the delays that
are said in words ("a day", "half a day", "a week")."""
DELAYED_TOOL = "timerify__delayed_command"


def said_after(text: str, delay: str, after: str) -> str:
    """`text` with the delay it says after "in" ended by `after` instead, in the same
    place: "turn on the boiler in 2 days" becomes "turn on the boiler 2 days from now"
    for "from now". `delay` is the pattern of the words that follow "in", and there must
    be one."""
    said, replaced = re.subn(rf"\bin ({delay})\b", rf"\1 {after}", text)
    assert replaced == 1, text
    return said


async def cancel_pending(hass: HomeAssistant, number: str, sensor: str) -> None:
    """Cancel every command the timer of `number` keeps."""
    for command in pending(hass, sensor):
        await call_service(
            hass, "cancel_command", {"entity_id": number}, command_id=command["id"]
        )


@pytest.fixture
async def loose_boiler(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> MockConfigEntry:
    """A timer on the Boiler in loose mode, which Assist knows by the sentences of the
    manual installation."""
    entry = await setup_target(mode="loose")
    await copy_sentences(hass, ["Boiler"])
    return entry


# --- Turning on and off ------------------------------------------------------------


async def test_turn_on_runs_the_default_time_in_strict_mode(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The words for any device start the timer: the boiler is on for as long as it is
    set to run, and the answer says when it turns off."""
    response = await converse(hass, "turn on the boiler")

    assert reached(response) == RUN
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "45"
    assert speech(response) == "Boiler runs for 45 minutes, until 09:45."


async def test_turn_on_in_loose_mode_runs_without_a_timer(
    hass: HomeAssistant, fake_target: FakeTarget, loose_boiler: MockConfigEntry
) -> None:
    response = await converse(hass, "turn on the boiler")

    assert reached(response) == RUN
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "0"
    assert speech(response) == "Boiler is on."


async def test_turn_off_stops_the_timer(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    await converse(hass, "turn on the boiler")

    response = await converse(hass, "turn off the boiler")

    assert reached(response) == STOP
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, NUMBER) == "0"
    assert speech(response) == "Boiler is off."


async def test_turn_on_of_an_unavailable_target_keeps_the_wish(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """R10: a target that is out of reach is not refused; it is turned on when it is
    back."""
    await fake_target.set_state("unavailable")

    response = await converse(hass, "turn on the boiler")

    assert reached(response) == RUN
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert fake_target.calls == []

    await fake_target.set_state("off")

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "45"


async def test_it_still_means_the_device_that_was_talked_about(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """A follow-up is the built-in agent's own: "turn it off" after the boiler was
    turned on is about the boiler (the agent switches it off, and the timer follows),
    and in a conversation of its own it is about nothing the agent knows. The words of
    the takeover do not take that away."""
    first = await talk(hass, "turn on the boiler")

    elsewhere = await talk(hass, "turn it off")
    assert reached(elsewhere.response) is None, speech(elsewhere.response)
    assert TURN_OFF not in fake_target.calls

    followed = await talk(hass, "turn it off", conversation_id=first.conversation_id)

    assert followed.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, NUMBER) == "0"


async def test_a_device_the_agent_does_not_know_is_refused_as_before(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    response = await converse(hass, "turn off the toaster")

    assert reached(response) is None
    assert response.response_type is intent.IntentResponseType.ERROR
    assert "toaster" in speech(response)
    assert fake_target.calls == []


async def test_turn_off_with_an_area_stays_with_home_assistant(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_lamp: FakeTarget,
    boiler: MockConfigEntry,
) -> None:
    """Only the sentences about a device by its name are taken over: "the lights in the
    kitchen" is Home Assistant's, and the boiler, which has a timer, is not touched."""
    kitchen = ar.async_get(hass).async_create("Kitchen")
    assert fake_lamp.device_id is not None
    dr.async_get(hass).async_update_device(fake_lamp.device_id, area_id=kitchen.id)
    await hass.async_block_till_done()

    response = await converse(hass, "turn off the lights in the kitchen")

    assert reached(response) == "HassTurnOff"
    assert fake_lamp.calls == [("turn_off", fake_lamp.entity_id)]
    assert fake_target.calls == []


@pytest.mark.usefixtures("assist")
async def test_a_kind_of_device_home_assistant_does_not_name_is_taken_over(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_humidifier: FakeTarget,
    fake_tank: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Home Assistant's own sentences to turn a device on or off name lights, switches,
    fans, media players, input booleans and thermostats; a water heater and a
    humidifier that have a timer are turned on and off with the same words, alone and
    for later, and with the settings they have."""
    await with_voice_settings(hass, setup_target, fake_humidifier, fake_tank)

    on = await converse(hass, "turn on the tank")
    stopped_soon = await converse(hass, "turn off the tank in 5 minutes")
    planned = await converse(hass, "turn on the humidifier in 10 minutes at 40 percent")

    assert [reached(response) for response in (on, stopped_soon, planned)] == [
        RUN,
        DELAYED_COMMAND,
        DELAYED_COMMAND,
    ]
    assert speech(on) == "Tank runs for 45 minutes, until 09:45."
    assert speech(stopped_soon) == "Tank turns off at 09:05."
    assert speech(planned) == "Humidifier turns on at 09:10."
    assert state_of(hass, TANK_NUMBER) == "5"
    assert fake_humidifier.call_data == []

    await advance(hass, freezer, minutes=5)

    assert fake_tank.call_data == [("turn_on", {}), ("turn_off", {})]

    await advance(hass, freezer, minutes=5)
    off = await converse(hass, "turn off the humidifier")

    assert reached(off) == STOP
    assert fake_humidifier.call_data == [
        ("turn_on", {}),
        ("set_humidity", {"humidity": 40.0}),
        ("turn_off", {}),
    ]


# --- Turning on later --------------------------------------------------------------


async def test_turn_on_in_minutes_keeps_a_command(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
) -> None:
    """The command waits for its time (P1), and at its time it runs the timer as
    turning on does (R9)."""
    response = await converse(hass, "turn on the boiler in 15 minutes")

    assert reached(response) == DELAYED_COMMAND
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert speech(response) == "Boiler turns on at 09:15."
    assert state_of(hass, NEXT) == "2026-01-05T07:15:00+00:00"
    assert fake_target.calls == []

    await advance(hass, freezer, minutes=15)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "45"
    assert state_of(hass, NEXT) == "unknown"


@pytest.mark.parametrize(
    "text",
    [
        "turn on the AC in 15 minutes for an hour, cooling, 24",
        "turn on the AC in 15 minutes for an hour cooling 24 degrees",
        "turn on the AC in 15 minutes, cooling, 24, for an hour",
        "turn on the AC for an hour, cooling, 24 in 15 minutes",
        "in 15 minutes turn on the AC for an hour, cooling, 24",
        "turn the AC on in 15 minutes for an hour, 24, cooling",
    ],
)
@pytest.mark.usefixtures("assist")
async def test_the_example_of_the_spec_and_the_ways_to_say_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    text: str,
) -> None:
    """How long, which mode and which temperature come before the delay or after it,
    and the command is the same: in 15 minutes the AC is put into cooling at 24, with
    an hour on the clock."""
    await with_voice_settings(hass, setup_target, fake_climate)

    response = await converse(hass, text)

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert speech(response) == "AC turns on at 09:15."
    assert state_of(hass, AC_NEXT) == "2026-01-05T07:15:00+00:00"
    assert fake_climate.call_data == []

    await advance(hass, freezer, minutes=15)

    assert fake_climate.call_data == COOL_24
    assert state_of(hass, AC_NUMBER) == "60"
    assert state_of(hass, AC_NEXT) == "unknown"


async def test_a_delayed_turn_on_runs_a_switch_for_hours_and_bare_minutes(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The way to say how long a boiler runs ("for 1 hour 30") is the same after the
    delay as it is alone."""
    response = await converse(hass, "turn on the boiler in 15 minutes for 1 hour 30")

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert [command["minutes"] for command in pending(hass, NEXT)] == [90]


@pytest.mark.usefixtures("assist")
@pytest.mark.parametrize(
    ("text", "minutes", "settings"),
    [
        ("turn on the AC in 15 minutes for 1 hour 30", 60, {"temperature": 30.0}),
        ("turn on the AC in 15 minutes for 1 hour and 30", 90, {}),
        ("turn on the AC for 1 hour 30 in 15 minutes", 60, {"temperature": 30.0}),
        ("turn on the AC for 1 hour and 30 in 15 minutes", 90, {}),
    ],
)
async def test_a_delayed_turn_on_of_a_thermostat_reads_hours_and_a_number(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    text: str,
    minutes: int,
    settings: dict[str, float],
) -> None:
    """After the delay, as alone, a thermostat reads the number right after the hours as
    its temperature, and the number after "and" as the minutes."""
    await with_voice_settings(hass, setup_target, fake_climate)
    assert len(readings("en", text, name="AC", domain="climate", takeover=True)) == 1

    response = await converse(hass, text)

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert [(c["minutes"], c["settings"]) for c in pending(hass, AC_NEXT)] == [
        (minutes, settings)
    ]


@pytest.mark.usefixtures("assist")
async def test_a_thermostat_is_turned_on_in_days_with_its_settings(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The sentences the Voice settings entry writes say the days too, and the settings
    of a thermostat follow them as they follow any other delay."""
    await with_voice_settings(hass, setup_target, fake_climate)

    response = await converse(hass, "turn on the AC in 2 days for an hour, cooling, 24")

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert state_of(hass, AC_NEXT) == (START + timedelta(hours=48)).isoformat()
    assert [(c["minutes"], c["settings"]) for c in pending(hass, AC_NEXT)] == [
        (60, {"hvac_mode": "cool", "temperature": 24.0})
    ]


@pytest.mark.usefixtures("assist")
async def test_a_word_for_a_mode_is_said_of_a_thermostat_only(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A delayed command to turn on takes the settings of its own kind of device: the
    thermostat is told to cool, and "cooling" after the boiler is not a command of
    Timerify's."""
    await with_voice_settings(hass, setup_target, fake_climate, fake_target)

    cooled = await converse(hass, "turn on the AC in 15 minutes cooling")
    boiled = await converse(hass, "turn on the boiler in 15 minutes cooling")

    assert reached(cooled) == DELAYED_COMMAND, speech(cooled)
    assert reached(boiled) != DELAYED_COMMAND
    assert pending(hass, NEXT) == []
    assert [c["settings"] for c in pending(hass, AC_NEXT)] == [{"hvac_mode": "cool"}]


@pytest.mark.usefixtures("assist")
async def test_a_delayed_turn_on_takes_only_the_hvac_modes_of_its_ac(
    hass: HomeAssistant,
    fake_full_ac: FakeTarget,
    fake_small_ac: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The small AC cannot heat: "heating" after its name keeps no command and
    switches nothing, while the mode it has is kept with the command; the AC that
    can heat is not put in its place."""
    await with_voice_settings(hass, setup_target, fake_full_ac, fake_small_ac)

    heated = await converse(hass, "turn on the small AC in 15 minutes heating")

    assert reached(heated) != DELAYED_COMMAND, speech(heated)
    assert pending(hass, SMALL_AC_NEXT) == []
    assert pending(hass, AC_NEXT) == []
    assert fake_small_ac.calls == []
    assert fake_full_ac.calls == []

    cooled = await converse(hass, "turn on the small AC in 15 minutes cooling")

    assert reached(cooled) == DELAYED_COMMAND, speech(cooled)
    assert [c["settings"] for c in pending(hass, SMALL_AC_NEXT)] == [
        {"hvac_mode": "cool"}
    ]
    assert pending(hass, AC_NEXT) == []
    assert fake_small_ac.calls == []
    assert fake_full_ac.calls == []


@pytest.mark.usefixtures("assist")
async def test_what_a_command_is_turned_on_with_is_not_left_half_said(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The extras of a command are a duration, settings or both, never a bare word that
    asks for neither: no command is kept for what was not understood."""
    await with_voice_settings(hass, setup_target, fake_climate)

    response = await converse(hass, "turn on the AC in 15 minutes for")

    assert reached(response) != DELAYED_COMMAND, speech(response)
    assert pending(hass, AC_NEXT) == []


async def test_a_command_by_voice_survives_manual_use(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
) -> None:
    """P2: someone switches the boiler on and off by hand before the command is due,
    and it still turns the boiler on at its time."""
    await converse(hass, "turn on the boiler in 10 minutes")

    await fake_target.set_state("on")
    await advance(hass, freezer, minutes=5)
    await fake_target.set_state("off")
    assert state_of(hass, NEXT) == "2026-01-05T07:10:00+00:00"

    await advance(hass, freezer, minutes=5)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "45"
    assert state_of(hass, NEXT) == "unknown"


async def test_a_delay_in_seconds_is_exact(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
) -> None:
    await converse(hass, "turn on the boiler in 30 seconds")

    assert state_of(hass, NEXT) == "2026-01-05T07:00:30+00:00"
    await advance(hass, freezer, seconds=29)
    assert fake_target.calls == []
    await advance(hass, freezer, seconds=1)
    assert fake_target.calls == [TURN_ON]


async def test_turn_on_in_2000_minutes_keeps_a_command(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
) -> None:
    """A delay is counted in Timerify's own minutes, which reach a week, not in the
    hundred of Home Assistant's: the command waits for a day and a third, and the answer
    names the time, on the next day."""
    response = await converse(hass, "turn on the boiler in 2000 minutes")

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert state_of(hass, NEXT) == at(2000)
    assert speech(response) == "Boiler turns on at 18:20 tomorrow."

    await advance(hass, freezer, minutes=2000)

    assert fake_target.calls == [TURN_ON]


async def test_turn_on_in_150_hours_keeps_a_command(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The hours of a delay reach a week too: 150 of them are six days and six hours."""
    response = await converse(hass, "turn on the boiler in 150 hours")

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert state_of(hass, NEXT) == at(150 * 60)
    assert speech(response) == "Boiler turns on at 15:00 in 6 days."


async def test_turn_on_a_week_and_a_minute_ahead_is_refused_with_the_limit(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """168 hours is the longest count of hours that can be said, and a minute more is
    a week and a minute: past what a command can wait. The answer names the limit and
    no command is kept."""
    response = await converse(hass, "turn on the boiler in 168 hours and 1 minute")

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert refusal_of(response) == translated(
        "en", "exceptions", "command_too_far", "message"
    ).format(days="7")
    assert state_of(hass, NEXT) == "unknown"


async def test_turn_on_in_one_hundred_twenty_minutes_keeps_a_command(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The minutes of a delay may be said as words, past a hundred as in a duration."""
    response = await converse(hass, "turn on the boiler in one hundred twenty minutes")

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert state_of(hass, NEXT) == at(120)
    assert speech(response) == "Boiler turns on at 11:00."


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
@pytest.mark.parametrize(
    ("counted", "slot"),
    [("timerify_hours", "delay_hours"), ("timerify_minutes", "delay_minutes")],
)
async def test_a_delay_past_100_can_be_said_in_words(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    language: str,
    counted: str,
    slot: str,
) -> None:
    """Each form of 120 in words (a language has several, for its cases) is heard as
    120 hours or minutes of a delay, as the digits are."""
    (text, *_) = samples(
        language,
        DELAYED_COMMAND,
        takeover=True,
        numbers={counted: 120},
        absent=SETTING_LISTS,
        admitting="switch",
    )
    forms = spoken_number(language, 120)
    assert forms

    for form in forms:
        spoken = text.replace("120", form)
        response = await converse(hass, spoken, language)

        assert reached(response) == DELAYED_COMMAND, spoken
        assert response.intent is not None, spoken
        assert response.intent.slots[slot]["value"] == 120, spoken
        await cancel_pending(hass, NUMBER, NEXT)


@pytest.mark.parametrize(
    "numbers",
    [{"timerify_hours": 169}, {"timerify_long_minutes": 10081}],
    ids=["169-hours", "10081-minutes"],
)
@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_a_delay_beyond_a_week_in_one_unit_is_not_understood(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    language: str,
    numbers: dict[str, int],
) -> None:
    """A count past a week in one unit matches nothing of Timerify's, as for a
    duration: no command is kept and nothing is switched, not even by the sentences of
    Home Assistant that a count past a week would otherwise fall to."""
    texts = samples(
        language,
        DELAYED_COMMAND,
        takeover=True,
        numbers=numbers,
        absent=SETTING_LISTS,
        admitting="switch",
    )
    assert texts

    for text in texts:
        response = await converse(hass, text, language)

        assert reached(response) != DELAYED_COMMAND, text
    assert fake_target.calls == []
    assert pending(hass, NEXT) == []
    assert state_of(hass, NUMBER) == "0"


@pytest.mark.parametrize(
    ("counted", "slot", "count"),
    [
        ("timerify_hours", "delay_hours", 120),
        ("timerify_minutes", "delay_minutes", 120),
        ("timerify_long_minutes", "delay_minutes", 2000),
    ],
)
async def test_russian_delays_past_100_reach_the_handler(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    counted: str,
    slot: str,
    count: int,
) -> None:
    """In Russian too, a delay of 120 hours, 120 minutes or 2000 minutes is counted by
    Timerify's own lists and reaches the handler with what was said, whatever the
    command, and whether it is kept, set or refused there."""
    texts = samples(
        "ru",
        DELAYED_COMMAND,
        takeover=True,
        numbers={counted: count},
        absent=SETTING_LISTS,
        admitting="switch",
    )
    assert texts
    said: set[tuple[str, int]] = set()

    for text in texts:
        response = await converse(hass, text, "ru")

        assert reached(response) == DELAYED_COMMAND, text
        assert response.intent is not None, text
        said |= {
            (key, heard["value"])
            for key, heard in response.intent.slots.items()
            if key.startswith("delay_")
        }
        await cancel_pending(hass, NUMBER, NEXT)

    assert said == {(slot, count)}


# --- Delays in days and weeks ------------------------------------------------------
# Core's gazetteer takes "in 2 days" or "in a week" for a bare turn on or off of the
# device, so the long delays are Timerify's own phrasings, understood up to what a
# person may say and refused with the limit past what a command can wait.


async def test_turn_on_in_2_days_keeps_a_command_two_days_ahead(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The gazetteer would turn the boiler on at once; the command is kept for the day
    after tomorrow, at the time it is now, and nothing is switched."""
    response = await converse(hass, "turn on the boiler in 2 days")

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert state_of(hass, NEXT) == (START + timedelta(hours=48)).isoformat()
    assert speech(response).endswith("the day after tomorrow.")
    assert fake_target.calls == []


async def test_turn_on_in_7_days_is_the_longest_delay_that_is_kept(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    response = await converse(hass, "turn on the boiler in 7 days")

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert state_of(hass, NEXT) == (START + timedelta(days=7)).isoformat()
    assert speech(response) == "Boiler turns on at 09:00 in 7 days."
    assert fake_target.calls == []


async def test_turn_on_in_8_days_is_refused_with_the_limit(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The longest a command waits is the week, and the answer says so: the gazetteer
    would have turned the boiler on."""
    response = await converse(hass, "turn on the boiler in 8 days")

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert refusal_of(response) == translated(
        "en", "exceptions", "command_too_far", "message"
    ).format(days="7")
    assert state_of(hass, NEXT) == "unknown"
    assert fake_target.calls == []


@pytest.mark.parametrize(
    "text",
    [
        "turn on the boiler in 365 days",
        "turn on the boiler in eight days",
        "turn on the boiler after three hundred sixty five days",
        "turn on the boiler in 2 weeks",
        "turn on the boiler in two weeks",
        "turn on the boiler after 52 weeks",
    ],
)
async def test_a_delay_in_more_days_or_weeks_is_refused_with_the_limit(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry, text: str
) -> None:
    """A year of days and a year of weeks are understood, in digits and in words, so
    that the answer is the limit and not the gazetteer's turn on."""
    response = await converse(hass, text)

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert refusal_of(response) == translated(
        "en", "exceptions", "command_too_far", "message"
    ).format(days="7")
    assert fake_target.calls == []


async def test_turn_off_in_2_days_is_refused_and_leaves_the_boiler_on(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """A countdown reaches a day, so two days are refused with that limit, and the
    boiler, which the gazetteer would have turned off, keeps its countdown."""
    await converse(hass, "turn on the boiler")

    response = await converse(hass, "turn off the boiler in 2 days")

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert refusal_of(response) == translated(
        "en", "exceptions", "duration_out_of_range", "message"
    ).format(max_hours="24")
    assert state_of(hass, NUMBER) == "45"
    assert fake_target.calls == [TURN_ON]


async def test_a_delay_in_days_can_be_followed_by_how_long_the_boiler_runs(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The days are one of the ways to say a delay, so the sentences that follow it with
    how long the device runs, or put that before it, say them with days too."""
    for text in (
        "turn on the boiler in 2 days for 30 minutes",
        "turn on the boiler for 30 minutes after 2 days",
        "in 2 days turn on the boiler for 30 minutes",
    ):
        response = await converse(hass, text)

        assert reached(response) == DELAYED_COMMAND, text
        assert state_of(hass, NEXT) == (START + timedelta(hours=48)).isoformat(), text
        assert [command["minutes"] for command in pending(hass, NEXT)] == [30], text
        await cancel_pending(hass, NUMBER, NEXT)
    assert fake_target.calls == []


@pytest.mark.parametrize("count", [2, 21])
@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_a_delay_in_days_can_be_said_in_words(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    language: str,
    count: int,
) -> None:
    """Each form of 2 and of 21 in words (a language has several, for its cases and
    genders) is heard as that many days, as the digits are. 21 is past what a command
    waits: it reaches the handler, which refuses it."""
    (text, *_) = samples(
        language,
        DELAYED_COMMAND,
        takeover=True,
        numbers={DAYS_LIST: count},
        absent=SETTING_LISTS,
        admitting="switch",
    )
    forms = spoken_number(language, count)
    assert forms

    for form in forms:
        spoken = text.replace(str(count), form)
        response = await converse(hass, spoken, language)

        assert reached(response) == DELAYED_COMMAND, spoken
        assert response.intent is not None, spoken
        assert response.intent.slots["delay_days"]["value"] == count, spoken
        await cancel_pending(hass, NUMBER, NEXT)
    assert fake_target.calls == []


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_every_sentence_that_says_a_delay_in_days_reaches_the_handler(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry, language: str
) -> None:
    """Every sentence that says a delay of two days, for any command, reaches the
    handler with two days and no other delay, whether the command is kept, set or
    refused there, and nothing is switched by any of them."""
    texts = samples(
        language,
        DELAYED_COMMAND,
        takeover=True,
        numbers={DAYS_LIST: 2},
        absent=SETTING_LISTS,
        admitting="switch",
    )
    assert texts
    said: set[tuple[str, int]] = set()

    for text in texts:
        response = await converse(hass, text, language)

        assert reached(response) == DELAYED_COMMAND, text
        assert response.intent is not None, text
        said |= {
            (key, heard["value"])
            for key, heard in response.intent.slots.items()
            if key.startswith("delay_")
        }
        await cancel_pending(hass, NUMBER, NEXT)

    assert said == {("delay_days", 2)}
    assert fake_target.calls == []


# "In a day", "in half a day" and "in a week" are fixed delays, in minutes; "in N weeks"
# counts weeks. The gazetteer takes each of them for a turn on or off at once.


@pytest.mark.parametrize(
    ("text", "ahead", "speech_ends"),
    [
        ("turn on the boiler in a day", timedelta(days=1), "09:00 tomorrow."),
        ("turn on the boiler in half a day", timedelta(hours=12), "21:00."),
        ("turn on the boiler after a week", timedelta(days=7), "09:00 in 7 days."),
        ("turn on the boiler in 1 week", timedelta(days=7), "09:00 in 7 days."),
    ],
)
async def test_turn_on_in_a_day_or_a_week_keeps_a_command(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    text: str,
    ahead: timedelta,
    speech_ends: str,
) -> None:
    response = await converse(hass, text)

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert state_of(hass, NEXT) == (START + ahead).isoformat()
    assert speech(response).endswith(speech_ends)
    assert fake_target.calls == []


async def test_turn_off_in_half_a_day_sets_the_timer_of_a_running_boiler(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    await converse(hass, "turn on the boiler")

    response = await converse(hass, "turn off the boiler in half a day")

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert state_of(hass, SENSOR) == (START + timedelta(hours=12)).isoformat()
    assert state_of(hass, NUMBER) == "720"
    assert fake_target.calls == [TURN_ON]


@pytest.mark.parametrize(
    "text", ["turn off the boiler in a week", "turn off the boiler in 2 weeks"]
)
async def test_turn_off_in_a_week_is_refused_and_leaves_the_boiler_on(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry, text: str
) -> None:
    await converse(hass, "turn on the boiler")

    response = await converse(hass, text)

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert refusal_of(response) == translated(
        "en", "exceptions", "duration_out_of_range", "message"
    ).format(max_hours="24")
    assert state_of(hass, NUMBER) == "45"
    assert fake_target.calls == [TURN_ON]


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_a_day_half_a_day_and_a_week_are_said_as_fixed_delays(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry, language: str
) -> None:
    """Each way the sentences have to say a day, half a day and a week, for any command,
    reaches the handler with that many minutes and no other delay, and nothing is
    switched. The words are read from the shipped lists, in each language."""
    forms = spoken_values(language, WORDS_LIST)
    assert set(forms) == {"720", "1440", "10080"}

    for minutes, words in forms.items():
        assert words
        for word in words:
            texts = samples(
                language,
                DELAYED_COMMAND,
                takeover=True,
                numbers={},
                texts={WORDS_LIST: word},
                absent=SETTING_LISTS,
                admitting="switch",
            )
            assert texts, word
            for text in texts:
                response = await converse(hass, text, language)

                assert reached(response) == DELAYED_COMMAND, text
                assert response.intent is not None, text
                delays = {
                    key: heard["value"]
                    for key, heard in response.intent.slots.items()
                    if key.startswith("delay_")
                }
                assert delays == {"delay_minutes": int(minutes)}, text
                await cancel_pending(hass, NUMBER, NEXT)
    assert fake_target.calls == []


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_every_sentence_that_says_a_delay_in_weeks_reaches_the_handler(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry, language: str
) -> None:
    """A delay of two weeks, said in any sentence of any command, reaches the handler
    with two weeks and no other delay, and is refused there with the limit."""
    texts = samples(
        language,
        DELAYED_COMMAND,
        takeover=True,
        numbers={WEEKS_LIST: 2},
        absent=SETTING_LISTS,
        admitting="switch",
    )
    assert texts

    for text in texts:
        response = await converse(hass, text, language)

        assert reached(response) == DELAYED_COMMAND, text
        assert response.intent is not None, text
        assert {
            key: heard["value"]
            for key, heard in response.intent.slots.items()
            if key.startswith("delay_")
        } == {"delay_weeks": 2}, text
    assert fake_target.calls == []
    assert pending(hass, NEXT) == []


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_a_week_is_kept_by_a_turn_on_and_two_weeks_are_refused(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry, language: str
) -> None:
    """In a week, said in any sentence of any command, a turn on is kept for 7 days
    ahead and a turn off is refused with the limit of a countdown; in two weeks both are
    refused with the limit of their own, in the language of the request. Nothing is
    switched, nothing is kept past the week."""
    too_far = translated(language, "exceptions", "command_too_far", "message")
    countdown = translated(language, "exceptions", "duration_out_of_range", "message")
    refusals = {too_far.format(days="7"), countdown.format(max_hours="24")}
    in_a_week = spoken_values(language, WORDS_LIST)["10080"]
    in_a_week_texts = [
        text
        for word in in_a_week
        for text in samples(
            language,
            DELAYED_COMMAND,
            takeover=True,
            numbers={},
            texts={WORDS_LIST: word},
            absent=SETTING_LISTS,
            admitting="switch",
        )
    ]
    in_two_weeks_texts = samples(
        language,
        DELAYED_COMMAND,
        takeover=True,
        numbers={WEEKS_LIST: 2},
        absent=SETTING_LISTS,
        admitting="switch",
    )
    kept = refused = 0

    for text in in_a_week_texts:
        response = await converse(hass, text, language)

        if pending(hass, NEXT):
            assert state_of(hass, NEXT) == (START + timedelta(days=7)).isoformat(), text
            kept += 1
            await cancel_pending(hass, NUMBER, NEXT)
        else:
            assert refusal_of(response) == countdown.format(max_hours="24"), text
            refused += 1
    for text in in_two_weeks_texts:
        response = await converse(hass, text, language)

        assert refusal_of(response) in refusals, text
        assert pending(hass, NEXT) == [], text

    assert kept
    assert refused
    assert fake_target.calls == []


# --- A delay ended by "from now", "from today" or "later" -------------------------
# The gazetteer takes "turn on the boiler 2 days from now" for a turn on at once too, as
# it does "2 days from today" and "2 days later". Only English has it, and only for
# days, weeks and the words for them: "5 minutes from now" and "2 hours from now" name
# no device to it. A bare "later" says no time and is not a delay.

AFTER_THE_DELAY = pytest.mark.parametrize(
    "after",
    ["from now", "from today", "later"],
    ids=["from-now", "from-today", "later"],
)
"""The words that end a delay in days, weeks or a word, in place of "in" before it."""


@AFTER_THE_DELAY
@pytest.mark.parametrize(
    ("text", "ahead"),
    [
        ("turn on the boiler 2 days {after}", timedelta(days=2)),
        ("turn on the boiler two days {after}", timedelta(days=2)),
        ("turn on the boiler a day {after}", timedelta(days=1)),
        ("turn on the boiler half a day {after}", timedelta(hours=12)),
        ("turn on the boiler a week {after}", timedelta(days=7)),
        ("turn on the boiler 1 week {after}", timedelta(days=7)),
        ("2 days {after} turn on the boiler", timedelta(days=2)),
    ],
)
async def test_turn_on_so_long_ahead_keeps_a_command(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    after: str,
    text: str,
    ahead: timedelta,
) -> None:
    """A delay ended by "from now", "from today" or "later", after the command or before
    it, keeps the command as "in" does, where the gazetteer would turn the boiler on at
    once."""
    response = await converse(hass, text.format(after=after))

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert state_of(hass, NEXT) == (START + ahead).isoformat()
    assert fake_target.calls == []


@AFTER_THE_DELAY
@pytest.mark.parametrize(
    "text",
    [
        "turn on the boiler 8 days {after}",
        "turn on the boiler 365 days {after}",
        "turn on the boiler 2 weeks {after}",
        "turn on the boiler 52 weeks {after}",
        "2 weeks {after} turn on the boiler",
    ],
)
async def test_turn_on_beyond_a_week_ahead_is_refused_with_the_limit(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    after: str,
    text: str,
) -> None:
    response = await converse(hass, text.format(after=after))

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert refusal_of(response) == translated(
        "en", "exceptions", "command_too_far", "message"
    ).format(days="7")
    assert pending(hass, NEXT) == []
    assert fake_target.calls == []


@AFTER_THE_DELAY
async def test_turn_off_half_a_day_ahead_sets_the_timer_of_a_running_boiler(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry, after: str
) -> None:
    await converse(hass, "turn on the boiler")

    response = await converse(hass, f"turn off the boiler half a day {after}")

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert state_of(hass, SENSOR) == (START + timedelta(hours=12)).isoformat()
    assert state_of(hass, NUMBER) == "720"
    assert fake_target.calls == [TURN_ON]


@AFTER_THE_DELAY
@pytest.mark.parametrize(
    "text",
    [
        "turn off the boiler 2 days {after}",
        "turn off the boiler a week {after}",
        "turn off the boiler 2 weeks {after}",
        "2 days {after} turn off the boiler",
    ],
)
async def test_turn_off_beyond_a_day_ahead_is_refused_and_leaves_the_boiler_on(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    after: str,
    text: str,
) -> None:
    await converse(hass, "turn on the boiler")

    response = await converse(hass, text.format(after=after))

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert refusal_of(response) == translated(
        "en", "exceptions", "duration_out_of_range", "message"
    ).format(max_hours="24")
    assert state_of(hass, NUMBER) == "45"
    assert fake_target.calls == [TURN_ON]


@AFTER_THE_DELAY
@pytest.mark.parametrize(
    ("numbers", "texts", "said", "slots"),
    [
        ({DAYS_LIST: 2}, {}, "2 days?", {"delay_days": 2}),
        ({WEEKS_LIST: 2}, {}, "2 weeks?", {"delay_weeks": 2}),
        ({}, {WORDS_LIST: "a day"}, "a day", {"delay_minutes": 1440}),
        ({}, {WORDS_LIST: "half a day"}, "half a day", {"delay_minutes": 720}),
        ({}, {WORDS_LIST: "a week"}, "a week", {"delay_minutes": 10080}),
    ],
    ids=["days", "weeks", "a-day", "half-a-day", "a-week"],
)
async def test_every_sentence_of_every_command_can_end_the_delay_in_other_words(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    after: str,
    numbers: dict[str, int],
    texts: dict[str, str],
    said: str,
    slots: dict[str, int],
) -> None:
    """Whichever sentence says a delay "in 2 days" (before the command, after it, with
    how long it runs, with the settings) says it "2 days from now", "2 days from today"
    or "2 days later" in the same place, and the handler hears the same delay and
    nothing else. Nothing is switched."""
    in_texts = samples(
        "en",
        DELAYED_COMMAND,
        takeover=True,
        numbers=numbers,
        texts=texts,
        absent=SETTING_LISTS,
        admitting="switch",
    )
    assert in_texts

    for in_text in in_texts:
        text = said_after(in_text, said, after)
        response = await converse(hass, text)

        assert reached(response) == DELAYED_COMMAND, text
        assert response.intent is not None, text
        assert {
            key: heard["value"]
            for key, heard in response.intent.slots.items()
            if key.startswith("delay_")
        } == slots, text
        await cancel_pending(hass, NUMBER, NEXT)
    assert fake_target.calls == []


def test_a_bare_later_is_not_a_delay() -> None:
    """ "Later" with a count of days or a word for it is a delay; "later" alone says no
    time, so no sentence reads it and it is left to Home Assistant (RULINGS.md)."""
    said = {"name": "Boiler", "domain": "switch", "takeover": True}

    assert readings("en", "turn on the boiler 2 days later", **said)
    assert readings("en", "turn on the boiler later", **said) == []


# --- What is too long to be understood --------------------------------------------
# Past a year of days, past a year of weeks, and in a month or a year: no sentence of
# Timerify's says it, and the gazetteer would turn the device on or off. It does not
# get the chance only because Timerify's sentences meet the phrase with an unmatched
# entity (the count or the words that did not match), and the built-in agent then
# answers that it did not understand rather than hand the sentence on
# (`default_agent.py:704-718` of Home Assistant 2026.10). These tests fail the day a
# release changes that.


async def assert_not_understood(
    hass: HomeAssistant, fake_target: FakeTarget, texts: Sequence[str], language: str
) -> None:
    """Every text is answered with an error before any handler is reached, Timerify's or
    Home Assistant's, and nothing is kept or switched."""
    assert texts
    for text in texts:
        response = await converse(hass, text, language)

        assert reached(response) is None, text
        assert response.response_type is intent.IntentResponseType.ERROR, text
    assert fake_target.calls == []
    assert pending(hass, NEXT) == []
    assert state_of(hass, NUMBER) == "0"


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
@pytest.mark.parametrize(
    "numbers",
    [{DAYS_LIST: 366}, {DAYS_LIST: 400}, {WEEKS_LIST: 53}],
    ids=["366-days", "400-days", "53-weeks"],
)
async def test_more_than_a_year_of_days_or_weeks_is_not_understood(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    language: str,
    numbers: dict[str, int],
) -> None:
    """In any sentence of any command, a count of days or weeks past the year is heard
    by no sentence, and the gazetteer's turn on or turn off does not take its place."""
    texts = samples(
        language,
        DELAYED_COMMAND,
        takeover=True,
        numbers=numbers,
        absent=SETTING_LISTS,
        admitting="switch",
    )

    await assert_not_understood(hass, fake_target, texts, language)


@AFTER_THE_DELAY
@pytest.mark.parametrize(
    ("numbers", "said"),
    [
        ({DAYS_LIST: 366}, "366 days?"),
        ({DAYS_LIST: 400}, "400 days?"),
        ({WEEKS_LIST: 53}, "53 weeks?"),
    ],
    ids=["366-days", "400-days", "53-weeks"],
)
async def test_more_than_a_year_ahead_is_not_understood(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    after: str,
    numbers: dict[str, int],
    said: str,
) -> None:
    texts = [
        said_after(text, said, after)
        for text in samples(
            "en",
            DELAYED_COMMAND,
            takeover=True,
            numbers=numbers,
            absent=SETTING_LISTS,
            admitting="switch",
        )
    ]

    await assert_not_understood(hass, fake_target, texts, "en")


@pytest.mark.parametrize(
    "text",
    [
        "turn on the boiler in a month",
        "turn off the boiler in a month",
        "turn on the boiler in a year",
        "turn off the boiler in a year",
    ],
)
async def test_in_a_month_or_a_year_is_not_understood(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry, text: str
) -> None:
    """The words for a month and a year are none of the words Timerify knows, so the
    phrase is not understood, and the boiler is not switched."""
    await assert_not_understood(hass, fake_target, [text], "en")


@AFTER_THE_DELAY
@pytest.mark.parametrize(
    "text",
    [
        "turn on the boiler a month {after}",
        "turn off the boiler a month {after}",
        "turn on the boiler a year {after}",
        "a month {after} turn on the boiler",
    ],
)
async def test_a_month_or_a_year_ahead_is_not_understood(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    after: str,
    text: str,
) -> None:
    await assert_not_understood(hass, fake_target, [text.format(after=after)], "en")


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_the_days_and_weeks_of_a_delay_have_slots_of_their_own(language: str) -> None:
    """Days and weeks are plain ranges that fill their own slots, and not a range of
    another unit's slot with a multiplier: hassil keeps the number words of a range by
    its bounds and not by its multiplier, so a multiplied range would be handed the
    words of any other range with its bounds, and hand out its own."""
    sources = read_back((SENTENCES_DIR / language / SOURCE_FILE).read_text("utf-8"))
    counted = {
        name: sources["lists"][name]["range"] for name in (DAYS_LIST, WEEKS_LIST)
    }

    assert counted[DAYS_LIST] == {"from": 1, "to": 365}
    assert counted[WEEKS_LIST] == {"from": 1, "to": 52}
    rules = sources["expansion_rules"]
    rule = " ".join(rules[name] for name in rules if name.startswith("timerify_own_"))
    assert OWN_DELAY_RULE in rules
    for said in (
        "{timerify_delay_days:delay_days}",
        "{timerify_delay_weeks:delay_weeks}",
        "{timerify_delay_words:delay_minutes}",
    ):
        assert said in rule
    assert f"<{OWN_DELAY_RULE}>" in alternatives(
        shipped(language)["expansion_rules"][DELAY_AFTER_RULE_NAME]
    )


def test_the_own_delay_rule_is_a_delay_only_when_the_sources_have_it() -> None:
    """The generator adds the days to each rule that says a delay, and only for a
    language whose sentences define them; the delays of core are not changed by it."""
    data = get_intents("en")
    assert data is not None
    own = f"<{OWN_DELAY_RULE}>"

    without = delay_rules(data, {"expansion_rules": {}})
    with_days = delay_rules(data, {"expansion_rules": {OWN_DELAY_RULE: "x"}})

    assert not any(own in rule for rule in without.values())
    assert (
        set(with_days)
        == set(without)
        == {
            DELAY_AFTER_RULE_NAME,
            DELAY_BEFORE_RULE_NAME,
        }
    )
    for name, rule in with_days.items():
        assert alternatives(rule)[-1] == own
        assert alternatives(rule)[:-1] == alternatives(without[name])


async def test_llm_plans_a_command_in_days_and_weeks(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The tool takes days and weeks as it takes hours: a model that means two days says
    so, and a delay past what a command waits is refused with the limit."""
    api = await assist_api(hass)

    planned = await call_tool(
        api, DELAYED_TOOL, {"name": "Boiler", "action": "on", "delay_days": 2}
    )
    too_far = await call_tool(
        api, DELAYED_TOOL, {"name": "Boiler", "action": "on", "delay_weeks": 2}
    )

    assert planned["speech_slots"]["in_days"] == 2
    assert state_of(hass, NEXT) == (START + timedelta(hours=48)).isoformat()
    assert too_far["response_type"] == "error"
    assert too_far["speech"]["plain"]["speech"] == translated(
        "en", "exceptions", "command_too_far", "message"
    ).format(days="7")
    assert fake_target.calls == []


# --- Turning off later -------------------------------------------------------------


async def test_turn_off_in_minutes_sets_the_timer_of_a_running_boiler(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
) -> None:
    """45 minutes were left; ten is what the boiler gets, and no command is kept: it is
    the countdown that turns the boiler off."""
    await converse(hass, "turn on the boiler")

    response = await converse(hass, "turn off the boiler in 10 minutes")

    assert reached(response) == DELAYED_COMMAND
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert speech(response) == "Boiler turns off at 09:10."
    assert state_of(hass, NUMBER) == "10"
    assert state_of(hass, SENSOR) == "2026-01-05T07:10:00+00:00"
    assert pending(hass, NEXT) == []

    await advance(hass, freezer, minutes=10)

    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_turn_off_in_minutes_replaces_a_shorter_timer(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """Turning off in ten minutes is ten minutes, not at most ten."""
    await converse(hass, "turn on the boiler for 5 minutes")

    await converse(hass, "turn off the boiler in 10 minutes")

    assert state_of(hass, NUMBER) == "10"


async def test_turn_off_in_minutes_changes_nothing_for_a_boiler_that_is_off(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    response = await converse(hass, "turn off the boiler in 10 minutes")

    assert reached(response) == DELAYED_COMMAND
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert speech(response) == "Boiler is already off; nothing changed."
    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "0"
    assert pending(hass, NEXT) == []


async def test_turn_off_in_minutes_ends_a_run_that_had_no_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    loose_boiler: MockConfigEntry,
) -> None:
    await converse(hass, "turn on the boiler")
    assert state_of(hass, NUMBER) == "0"

    response = await converse(hass, "turn off the boiler in 10 minutes")

    assert speech(response) == "Boiler turns off at 09:10."
    assert state_of(hass, NUMBER) == "10"
    await advance(hass, freezer, minutes=10)
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_turn_off_in_minutes_sets_the_timer_of_an_unavailable_target(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """R10: a countdown on a target that is out of reach is still running."""
    await converse(hass, "turn on the boiler")
    await fake_target.set_state("unavailable")

    response = await converse(hass, "turn off the boiler in 10 minutes")

    assert speech(response) == "Boiler turns off at 09:10."
    assert state_of(hass, NUMBER) == "10"


async def test_turn_off_in_minutes_follows_a_turn_on_the_boiler_has_not_shown_yet(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    loose_boiler: MockConfigEntry,
) -> None:
    """A cloud boiler confirms a command after the call returned. What Timerify has
    asked for is what counts: the boiler is on, so the countdown is set."""
    fake_target.report_next_call_late()
    await converse(hass, "turn on the boiler")
    assert fake_target.state == "off"

    response = await converse(hass, "turn off the boiler in 10 minutes")
    await fake_target.report_late()

    assert speech(response) == "Boiler turns off at 09:10."
    assert state_of(hass, NUMBER) == "10"
    await advance(hass, freezer, minutes=10)
    assert fake_target.calls.count(TURN_OFF) == 1
    assert fake_target.calls[-1] == TURN_OFF


async def test_turn_off_in_minutes_follows_a_stop_the_boiler_has_not_shown_yet(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The boiler is still on until it reports the stop; it is wanted off, and there is
    nothing to turn off later."""
    await converse(hass, "turn on the boiler")
    fake_target.report_next_call_late()
    await converse(hass, "stop the boiler timer")
    assert fake_target.state == "on"

    response = await converse(hass, "turn off the boiler in 10 minutes")
    await fake_target.report_late()

    assert speech(response) == "Boiler is already off; nothing changed."
    assert state_of(hass, NUMBER) == "0"
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_turn_off_in_a_minute_and_a_half_is_exact(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    await converse(hass, "turn on the boiler")

    await converse(hass, "turn off the boiler in 1 minute and 30 seconds")

    assert state_of(hass, SENSOR) == (START + timedelta(seconds=90)).isoformat()


async def test_turn_off_in_more_than_a_day_is_refused(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    await converse(hass, "turn on the boiler")

    response = await converse(hass, "turn off the boiler in 30 hours")

    assert refusal_of(response) == translated(
        "en", "exceptions", "duration_out_of_range", "message"
    ).format(max_hours="24")
    assert state_of(hass, NUMBER) == "45"


async def test_turn_off_in_120_minutes_sets_the_timer(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """Two hours is a count of minutes past Home Assistant's hundred, and within the
    day a countdown can run for."""
    await converse(hass, "turn on the boiler")

    response = await converse(hass, "turn off the boiler in 120 minutes")

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert state_of(hass, SENSOR) == (START + timedelta(minutes=120)).isoformat()
    assert state_of(hass, NUMBER) == "120"


async def test_turn_off_in_2000_minutes_is_refused_with_the_limit(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """2000 minutes is understood, so the answer is the controller's: a countdown runs
    for a day at most, and the one that was running is left as it was."""
    await converse(hass, "turn on the boiler")

    response = await converse(hass, "turn off the boiler in 2000 minutes")

    assert reached(response) == DELAYED_COMMAND, speech(response)
    assert refusal_of(response) == translated(
        "en", "exceptions", "duration_out_of_range", "message"
    ).format(max_hours="24")
    assert state_of(hass, NUMBER) == "45"


# --- What is taken over, and what is not -------------------------------------------


def core_intents(language: str) -> Intents:
    """The sentences of Home Assistant in `language`."""
    data = get_intents(language)
    assert data is not None
    return Intents.from_dict(data)


def said(
    language: str,
    intents: Intents,
    sentence: str,
    lists: Mapping[str, str],
) -> str:
    """The shortest way to say the sentence of Home Assistant, with each list that is
    named giving the one value."""
    slot_lists = {
        **intents.slot_lists,
        **{
            name: TextSlotList.from_strings([value], name=name)
            for name, value in lists.items()
        },
    }
    texts = sample_sentence(
        parse_sentence(sentence),
        slot_lists,
        intents.expansion_rules,
        language=language,
        skip_optionals=True,
    )
    return next(iter(texts)).strip()


def core_phrasings(language: str, name: str) -> list[tuple[str, str, str | None]]:
    """What a person says to turn the device called `name` on and off in Home
    Assistant, bounded: for each of its sentences to turn it on or off alone, and for
    each of those in each of its shapes of a delayed command, the shortest way to say
    it. Each is (text, action, shape), the shape None for a command said alone."""
    data = get_intents(language)
    assert data is not None
    intents = core_intents(language)
    blocks = [block for block in command_blocks(data) if block.generic]
    shapes = delayed_shapes(data)
    delays = {f"timer_{unit}": str(value) for unit, value in DELAY_VALUES.items()}
    found: list[tuple[str, str, str | None]] = []
    for block in blocks:
        for sentence in block.sentences:
            command = said(language, intents, sentence, {"name": name})
            found.append((command, block.action, None))
            for shape in shapes:
                text = said(
                    language, intents, shape, {**delays, "timer_command": command}
                )
                found.append((text, block.action, shape))
    return found


def delay_slots(shape: str) -> dict[str, int]:
    """The delay a sample of `shape` says, by the slots a handler reads it from."""
    return {
        f"delay_{unit}": value
        for unit, value in DELAY_VALUES.items()
        if f"{{timer_{unit}:" in shape
    }


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_every_way_to_turn_the_boiler_on_or_off_is_taken_over(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    language: str,
) -> None:
    """The sentences of Home Assistant to turn on and off, said alone and in each shape
    of a delayed command, reach Timerify, with what was said: the action and the
    delay. Never the intents of Home Assistant."""
    phrasings = core_phrasings(language, "Boiler")
    assert len({text for text, _, _ in phrasings}) > 20

    for text, action, shape in phrasings:
        response = await converse(hass, text, language)

        assert response.response_type is intent.IntentResponseType.ACTION_DONE, text
        assert response.intent is not None, text
        slots = {key: slot["value"] for key, slot in response.intent.slots.items()}
        if shape is None:
            assert reached(response) == TIMERIFY_COMMANDS[action], text
        else:
            assert reached(response) == DELAYED_COMMAND, text
            assert slots["action"] == action, text
            assert {
                key: value for key, value in slots.items() if key.startswith("delay_")
            } == delay_slots(shape), text
        await cancel_pending(hass, NUMBER, NEXT)


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_the_same_words_about_a_device_without_a_timer_stay_with_home_assistant(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_vent: FakeTarget,
    boiler: MockConfigEntry,
    language: str,
) -> None:
    """The vent has no timer: the same sentences reach the intents of Home Assistant,
    which runs them or keeps a command for later as it always did; Timerify keeps
    none, and the boiler is left alone."""
    phrasings = core_phrasings(language, "Vent")

    for text, action, shape in phrasings:
        response = await converse(hass, text, language)

        assert response.intent is not None, text
        expected = CORE_INTENTS[action] if shape is None else "HassStartTimer"
        assert reached(response) == expected, text
    assert fake_vent.calls == [
        ("turn_on" if action == "on" else "turn_off", fake_vent.entity_id)
        for _, action, shape in phrasings
        if shape is None
    ]
    assert pending(hass, NEXT) == []
    assert fake_target.calls == []


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_home_assistant_still_runs_its_delayed_command_for_a_device_with_no_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_vent: FakeTarget,
    boiler: MockConfigEntry,
    language: str,
) -> None:
    """Said about the vent, which has no timer, three delayed commands wait in Home
    Assistant and, when their time comes, it switches the vent as it always did; the
    boiler, which has a timer, is not touched and Timerify keeps no command."""
    delayed = [phrasing for phrasing in core_phrasings(language, "Vent") if phrasing[2]]
    chosen = [
        next(phrasing for phrasing in delayed if phrasing[1] == "on"),
        next(phrasing for phrasing in delayed if phrasing[1] == "off"),
        delayed[-1],
    ]
    switched: list[tuple[str, str]] = []

    for text, action, shape in chosen:
        assert shape is not None
        response = await converse(hass, text, language)
        assert reached(response) == "HassStartTimer", text
        assert fake_vent.calls == switched, text
        # Home Assistant waits for the time in a background task of its own: let it
        # begin to wait before the clock moves.
        await hass.async_block_till_done()

        delay = {
            key.removeprefix("delay_"): value
            for key, value in delay_slots(shape).items()
        }
        await advance(hass, freezer, **delay)
        # When the time is over that task starts a second one, which says the command
        # to the agent again. No other timer waits, so the background tasks left are
        # that one.
        await hass.async_block_till_done(wait_background_tasks=True)

        switched.append((f"turn_{action}", fake_vent.entity_id))
        assert fake_vent.calls == switched, text
    assert fake_target.calls == []
    assert pending(hass, NEXT) == []


# --- The generator -----------------------------------------------------------------


def shipped(language: str) -> dict[str, Any]:
    """The committed file of `language`, as the built-in agent reads it."""
    return read_back((SENTENCES_DIR / language / FILE_NAME).read_text("utf-8"))


def admits(block: Mapping[str, Any], domain: str) -> bool:
    """Whether a generated block is for the devices of `domain`."""
    required = block.get("requires_context", {}).get("domain")
    excluded = block.get("excludes_context", {}).get("domain", [])
    return (required is None or domain in required) and domain not in excluded


def admitted(block: CommandBlock, domain: str) -> bool:
    """Whether a block of Home Assistant is for the devices of `domain`. The generic
    block is for every device that has a timer, whatever its domain: it is Timerify that
    decides that a device is turned on and off the way the generic block says."""
    return block.generic or domain in block.domains


def alternatives(group: str) -> list[str]:
    """The alternatives of a group `(a|b|c)` that is a whole expansion rule."""
    parts = [""]
    depth = 0
    for character in group[1:-1]:
        if character in "([":
            depth += 1
        elif character in ")]":
            depth -= 1
        if character == "|" and depth == 0:
            parts.append("")
        else:
            parts[-1] += character
    return parts


def expanded(
    block: Mapping[str, Any], rules: Mapping[str, str], sentence: str
) -> set[str]:
    """The sentences that a sentence of a generated block of delayed commands stands
    for: with the command it says written out, and one for each of the delays that the
    rule it names says."""
    sentence = sentence.replace(
        COMMAND_RULE, block["expansion_rules"][COMMAND_RULE_NAME]
    )
    for name in (DELAY_AFTER_RULE_NAME, DELAY_BEFORE_RULE_NAME):
        if f"<{name}>" in sentence:
            return {sentence.replace(f"<{name}>", d) for d in alternatives(rules[name])}
    return {sentence}


def wanted_later(block: CommandBlock, shapes: Sequence[str]) -> set[str]:
    """The sentences that say the command of a block of Home Assistant in each shape of
    a delayed command it has, as the file should have them: the hours, minutes and
    seconds of the delay in slots of their own, counted by the lists that `DELAY_LISTS`
    gives, and the delay in days (`OWN_DELAY_RULE`, which the sentences of every
    language define) in the place of the delay of the shape; and a command to turn on
    followed by how long it runs and the settings, if the delay comes after it, or
    before the delay, or after it; or, if the delay comes first, followed by them."""
    sentences: set[str] = set()
    for shape in shapes:
        delay = shape.replace(COMMAND_SLOT, "").strip()
        counted = re.sub(
            r"\{timer_(\w+):\1\}", lambda found: DELAY_LISTS[found[1]], shape
        )
        for named in (counted, shape.replace(delay, f"<{OWN_DELAY_RULE}>")):
            alone = named.replace(COMMAND_SLOT, command_group(block))
            if block.action == "off":
                sentences.add(alone)
            elif shape.startswith(COMMAND_SLOT):
                sentences |= {
                    alone,
                    named.replace(COMMAND_SLOT, f"{command_group(block)} {EXTRAS}"),
                    f"{alone} {EXTRAS}",
                }
            else:
                sentences.add(f"{alone} [{EXTRAS}]")
    return sentences


def probes(blocks: Sequence[CommandBlock]) -> list[str]:
    """The domains to ask about: every kind of device that can have a timer, each one
    the blocks of Home Assistant name, and one that nothing names."""
    named = {d for block in blocks for d in block.domains}
    return sorted({*SUPPORTED_DOMAINS, *named, "kettle"})


def gaps(data: Mapping[str, Any], generated: Mapping[str, Any]) -> list[str]:
    """Where the generated file `generated` does not say what Home Assistant says in
    `data`, for any kind of device, or says more.

    For each kind of device (each that Timerify supports, each domain the blocks of Home
    Assistant name, and one that nothing names) and each of turning on and off: every
    sentence of Home Assistant that acts on the device by its name, said alone and in
    every shape of a delayed command, must be a sentence of a generated block that is
    for that kind of device, and nothing else may be. The sentences for every device
    (those of the generic block of Home Assistant) are the ones of every kind: a water
    heater or a humidifier is turned on and off with them though the block does not name
    it.
    """
    blocks = command_blocks(data)
    shapes = delayed_shapes(data)
    rules = generated["expansion_rules"]
    problems: list[str] = []
    for action in ("on", "off"):
        own = [block for block in blocks if block.action == action]
        bare = generated["intents"][TIMERIFY_COMMANDS[action]]["data"]
        later = [
            block
            for block in generated["intents"][DELAYED_COMMAND]["data"]
            if block["slots"]["action"] == action
        ]
        for domain in probes(blocks):
            for_domain = [block for block in own if admitted(block, domain)]
            alone = {
                s.replace("{name}", "{timerify_target}")
                for block in for_domain
                for s in block.sentences
            }
            said_alone = {
                s for block in bare if admits(block, domain) for s in block["sentences"]
            }
            problems += [
                f"{action} {domain}: {s!r} is not said alone"
                for s in alone - said_alone
            ]
            problems += [
                f"{action} {domain}: {s!r} is said alone" for s in said_alone - alone
            ]
            wanted = {s for block in for_domain for s in wanted_later(block, shapes)}
            said = {
                said_sentence
                for block in later
                if admits(block, domain)
                for s in block["sentences"]
                for said_sentence in expanded(block, rules, s)
            }
            problems += [
                f"{action} {domain}: {s!r} is not said later" for s in wanted - said
            ]
            problems += [
                f"{action} {domain}: {s!r} is said later" for s in said - wanted
            ]
    return problems


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_the_file_covers_every_command_of_home_assistant_for_every_kind_of_device(
    language: str,
) -> None:
    """P-6, from the data of Home Assistant itself."""
    data = get_intents(language)
    assert data is not None
    assert {block.action for block in command_blocks(data)} == {"on", "off"}
    assert any(not block.generic for block in command_blocks(data))
    assert delayed_shapes(data)

    assert gaps(data, shipped(language)) == []


def wanted_at(block: CommandBlock) -> set[str]:
    """The sentences that say the command of a block of Home Assistant at a clock time,
    as the file should have them: the time after the command, and a command to turn on
    may say how long it runs and its settings once, before the time or after it, and
    after the time that comes first; the time before the command too."""
    command = command_group(block)
    after = f"<{CLOCK_AFTER_RULE_NAME}>"
    after_extras = f"<{CLOCK_AFTER_EXTRAS_RULE_NAME}>"
    before = f"<{CLOCK_BEFORE_RULE_NAME}>"
    if block.action == "off":
        return {f"{command} {after}", f"{before} {command}"}
    return {
        f"{command} {after}",
        f"{command} {EXTRAS} {after_extras}",
        f"{command} {after} {EXTRAS}",
        f"{before} {command} [{EXTRAS}]",
    }


def clock_gaps(data: Mapping[str, Any], generated: Mapping[str, Any]) -> list[str]:
    """Where the generated file `generated` does not say at a clock time what Home
    Assistant says to turn a device on or off by its name, for any kind of device, or
    says more: the twin of `gaps` for the intent of the commands at a clock time, with
    the time in the place of the delay."""
    blocks = command_blocks(data)
    rules = generated["expansion_rules"]
    problems: list[str] = []
    for action in ("on", "off"):
        own = [block for block in blocks if block.action == action]
        at_a_time = [
            block
            for block in generated["intents"][CLOCK_COMMAND]["data"]
            if block["slots"]["action"] == action
        ]
        for domain in probes(blocks):
            wanted = {
                s for block in own if admitted(block, domain) for s in wanted_at(block)
            }
            said = {
                said_sentence
                for block in at_a_time
                if admits(block, domain)
                for s in block["sentences"]
                for said_sentence in expanded(block, rules, s)
            }
            problems += [
                f"{action} {domain}: {s!r} is not said at a time" for s in wanted - said
            ]
            problems += [
                f"{action} {domain}: {s!r} is said at a time" for s in said - wanted
            ]
    return problems


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_the_file_says_every_command_at_a_clock_time_for_every_kind_of_device(
    language: str,
) -> None:
    """Whatever Home Assistant says to turn a device on or off by its name, the file
    says at a clock time too, with the settings and how long it runs for a command to
    turn on, in the same places as after a delay, and for the same kinds of device. The
    answer of the intent is the one of a command for later."""
    data = get_intents(language)
    assert data is not None
    generated = shipped(language)

    assert clock_gaps(data, generated) == []
    for block in generated["intents"][CLOCK_COMMAND]["data"]:
        assert block["response"] == "delayed"
        assert block["slots"].keys() == {"action"}


def without_the_first_clock_sentence(generated: dict[str, Any]) -> None:
    block = generated["intents"][CLOCK_COMMAND]["data"][0]
    block["sentences"] = block["sentences"][1:]


def without_water_heaters_turned_on_at_a_time(generated: dict[str, Any]) -> None:
    blocks = generated["intents"][CLOCK_COMMAND]["data"]
    blocks[:] = [
        block
        for block in blocks
        if "water_heater" not in block.get("requires_context", {}).get("domain", [])
    ]


def with_the_last_stop_at_a_time_for_every_device(generated: dict[str, Any]) -> None:
    generated["intents"][CLOCK_COMMAND]["data"][-1].pop("requires_context")


def without_a_command_at_a_time_to_turn_off(generated: dict[str, Any]) -> None:
    blocks = generated["intents"][CLOCK_COMMAND]["data"]
    blocks[:] = [block for block in blocks if block["slots"]["action"] == "on"]


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
@pytest.mark.parametrize(
    "mutate",
    [
        without_the_first_clock_sentence,
        without_water_heaters_turned_on_at_a_time,
        with_the_last_stop_at_a_time_for_every_device,
        without_a_command_at_a_time_to_turn_off,
    ],
    ids=lambda mutate: mutate.__name__,
)
def test_a_file_that_leaves_a_clock_sentence_out_or_adds_one_is_caught(
    language: str, mutate: Callable[[dict[str, Any]], None]
) -> None:
    """The proof above sees what it is there for: a sentence at a clock time that is
    missing, a command for a kind of device that is not, a command to turn off that is
    not, and one for every device that was written for one kind only."""
    data = get_intents(language)
    assert data is not None
    generated = shipped(language)
    assert clock_gaps(data, generated) == []

    mutate(generated)

    assert clock_gaps(data, generated)


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_a_scope_carries_the_clock_rule_that_it_says_its_own_way(
    language: str,
) -> None:
    """In English a thermostat and a water heater say a time after their settings with
    minutes, "o'clock", "am", "pm", "noon" or "midnight" (a bare number there is their
    temperature), and the commands at a clock time of those two say it so. Russian says
    a time with a preposition of its own, so its commands say it one way everywhere."""
    thermostats = {"climate", "water_heater"}
    rule = CLOCK_AFTER_EXTRAS_RULE_NAME
    blocks = [
        block
        for block in shipped(language)["intents"][CLOCK_COMMAND]["data"]
        if block["slots"]["action"] == "on"
    ]

    narrowed = {
        domain
        for block in blocks
        if rule in block["expansion_rules"]
        for domain in block["requires_context"]["domain"]
    }

    assert narrowed == (thermostats if language == "en" else set())
    for block in blocks:
        if rule in block["expansion_rules"]:
            assert block["expansion_rules"][rule] == "<timerify_exact_clock>"


def test_a_time_is_said_only_in_the_places_it_has_a_rule_for() -> None:
    """The sentences of a block say the command with the time after it, after how long
    it runs and its settings, and before it, for each place that has a rule; a command
    to turn off has no extras."""
    on = CommandBlock("on", ("{name}",), ())
    off = CommandBlock("off", ("{name}",), ())
    command = COMMAND_RULE

    assert timed_sentences(on, None, None, None) == []
    assert timed_sentences(on, "a", "b", "c") == [
        f"{command} <a>",
        f"{command} {EXTRAS} <b>",
        f"{command} <a> {EXTRAS}",
        f"<c> {command} [{EXTRAS}]",
    ]
    assert timed_sentences(on, None, "b", None) == [f"{command} {EXTRAS} <b>"]
    assert timed_sentences(on, "a", None, None) == [
        f"{command} <a>",
        f"{command} <a> {EXTRAS}",
    ]
    assert timed_sentences(off, "a", "b", "c") == [f"{command} <a>", f"<c> {command}"]


@pytest.mark.parametrize(
    "missing",
    [CLOCK_AFTER_RULE_NAME, CLOCK_AFTER_EXTRAS_RULE_NAME, CLOCK_BEFORE_RULE_NAME],
)
def test_the_generator_refuses_sentences_that_lack_a_way_to_say_the_time(
    missing: str,
) -> None:
    """A language whose sentences cannot say a time would have a handler for a command
    at a clock time that no sentence reaches: the generator stops."""
    data = get_intents("en")
    assert data is not None
    sources = read_back((SENTENCES_DIR / "en" / SOURCE_FILE).read_text("utf-8"))
    blocks = command_blocks(data)
    scopes = run_scopes(sources)
    assert clock_blocks(blocks, scopes, sources)

    del sources["expansion_rules"][missing]

    with pytest.raises(ValueError, match=f"do not define {missing}"):
        clock_blocks(blocks, scopes, sources)


def without_the_first_sentence(generated: dict[str, Any]) -> None:
    block = generated["intents"][DELAYED_COMMAND]["data"][0]
    block["sentences"] = block["sentences"][1:]


def without_a_way_to_say_the_delay(generated: dict[str, Any]) -> None:
    rules = generated["expansion_rules"]
    rules[DELAY_BEFORE_RULE_NAME] = (
        "(" + "|".join(alternatives(rules[DELAY_BEFORE_RULE_NAME])[1:]) + ")"
    )


def without_the_last_stop(generated: dict[str, Any]) -> None:
    del generated["intents"][STOP]["data"][-1]


def with_the_last_stop_for_every_device(generated: dict[str, Any]) -> None:
    generated["intents"][STOP]["data"][-1].pop("requires_context")


def without_water_heaters_turned_on_later(generated: dict[str, Any]) -> None:
    blocks = generated["intents"][DELAYED_COMMAND]["data"]
    blocks[:] = [
        block
        for block in blocks
        if "water_heater" not in block.get("requires_context", {}).get("domain", [])
    ]


def with_more_kinds_left_out_of_turning_on_later(generated: dict[str, Any]) -> None:
    for block in generated["intents"][DELAYED_COMMAND]["data"]:
        if "excludes_context" in block:
            block["excludes_context"]["domain"] += [
                "humidifier",
                "siren",
                "group",
                "remote",
            ]


def with_turning_on_for_the_kinds_of_home_assistant_only(
    generated: dict[str, Any],
) -> None:
    generated["intents"][RUN]["data"][0]["requires_context"] = {
        "domain": ["light", "switch", "fan", "media_player", "input_boolean", "climate"]
    }


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
@pytest.mark.parametrize(
    "mutate",
    [
        without_the_first_sentence,
        without_a_way_to_say_the_delay,
        without_the_last_stop,
        with_the_last_stop_for_every_device,
        without_water_heaters_turned_on_later,
        with_more_kinds_left_out_of_turning_on_later,
        with_turning_on_for_the_kinds_of_home_assistant_only,
    ],
    ids=lambda mutate: mutate.__name__,
)
def test_a_file_that_leaves_something_out_or_adds_something_is_caught(
    language: str, mutate: Callable[[dict[str, Any]], None]
) -> None:
    """The proof above sees the surprises it is there for: a sentence of a delayed
    command or a way to say the delay that is missing, a command for a kind of device
    that is not, a sentence for every device that was written for one kind only, and,
    for a kind of device that Home Assistant's sentences do not name (a water heater, a
    humidifier), the sentences for every device that do not reach it."""
    data = get_intents(language)
    assert data is not None
    generated = shipped(language)
    assert gaps(data, generated) == []

    mutate(generated)

    assert gaps(data, generated)


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_a_scope_carries_every_rule_of_its_block(language: str) -> None:
    """The thermostat and the water heater need "and" before the minutes that follow the
    hours, since a bare number there is their temperature, and the delayed commands of
    those two kinds of device say it the same way; the other kinds do not."""
    sources = read_back((SENTENCES_DIR / language / SOURCE_FILE).read_text("utf-8"))
    thermostats = {"climate", "water_heater"}

    overriding = {
        domain
        for scope in run_scopes(sources)
        if scope.rules.get("timerify_duration") == WITH_AND
        for domain in scope.requires
    }
    delayed = [
        block
        for block in shipped(language)["intents"][DELAYED_COMMAND]["data"]
        if block["slots"]["action"] == "on"
    ]
    overridden = {
        domain
        for block in delayed
        if "timerify_duration" in block["expansion_rules"]
        for domain in block["requires_context"]["domain"]
    }

    assert overriding == thermostats
    assert overridden == thermostats
    for block in delayed:
        domains = set(block.get("requires_context", {}).get("domain", []))
        if domains and domains <= thermostats:
            assert block["expansion_rules"]["timerify_duration"] == WITH_AND
        else:
            assert "timerify_duration" not in block["expansion_rules"]


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_a_delay_counts_its_hours_and_minutes_as_a_duration_does(
    language: str,
) -> None:
    """The lists of a delay are those a duration is counted with, in the sources of the
    language: if the minutes are split in another way there, the delay follows in the
    same change, or a duration would hear a count that a delay does not."""
    rules = read_back((SENTENCES_DIR / language / SOURCE_FILE).read_text("utf-8"))[
        "expansion_rules"
    ]

    minutes = DELAY_LISTS["minutes"].replace(":delay_minutes}", ":minutes}")
    hours = DELAY_LISTS["hours"].replace(":delay_hours}", ":hours}")
    assert minutes == rules["timerify_minutes_count"]
    assert rules["timerify_hours_part"].startswith(hours)


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_the_committed_file_is_what_the_generator_writes(language: str) -> None:
    """The file is written from two sources: the sentences of the pinned
    home-assistant-intents, which a new release changes, and the rules for the settings
    in `sentences/<language>/src/timerify.yaml`, which an edit there changes."""
    text = (SENTENCES_DIR / language / FILE_NAME).read_text("utf-8")

    assert text == render(language), (
        f"sentences/{language}/{FILE_NAME} is not what the generator writes: either"
        " home-assistant-intents was updated, or the settings in"
        f" sentences/{language}/src/timerify.yaml were edited. Run `{COMMAND}` and"
        " commit the result"
    )


@pytest.mark.parametrize(
    ("intent_name", "change", "reader"),
    [
        ("HassTurnOn", {"excludes_context": {"domain": ["light"]}}, command_blocks),
        ("HassTurnOff", {"lists": {"extra": {"values": ["x"]}}}, command_blocks),
        ("HassTurnOn", {"expansion_rules": {"extra": "x"}}, command_blocks),
        ("HassTurnOff", {"requires_context": {"area": "kitchen"}}, command_blocks),
        ("HassTurnOn", {"new_key": True}, command_blocks),
        ("HassStartTimer", {"new_key": True}, delayed_shapes),
    ],
    ids=lambda value: value.__name__ if callable(value) else None,
)
def test_the_generator_refuses_what_it_has_not_been_taught(
    intent_name: str,
    change: dict[str, Any],
    reader: Callable[[Mapping[str, Any]], object],
) -> None:
    """A block of Home Assistant that the generator would read wrongly must stop the
    generator, not widen or narrow the takeover without a word."""
    data = copy.deepcopy(get_intents("en"))
    assert data is not None
    target = next(
        block
        for block in data["intents"][intent_name]["data"]
        if block.get("metadata", {}).get("slot_combination") == "name_only"
        or block.get("response") == "command"
    )
    target.update(change)

    with pytest.raises(ValueError, match=r"does not understand|requires context"):
        reader(data)


@pytest.mark.parametrize(
    "shape",
    [
        "in {timer_hours:hours} hours {timer_command:conversation_command} now",
        "in {timer_hours:hours} hours",
        "{timer_command:conversation_command} in {timer_hours:hours} hours"
        " {timer_command:conversation_command}",
        "{timer_command:conversation_command} in {timer_days:hours} hours",
        "{timer_command:conversation_command}in {timer_hours:hours} hours",
        "{timer_command:conversation_command} in {timer_hours:hours} hours|at noon",
    ],
    ids=[
        "command_in_the_middle",
        "no_command",
        "two_commands",
        "other_slot",
        "no_space",
        "alternative_outside_a_group",
    ],
)
def test_the_generator_refuses_a_delayed_command_it_cannot_split_into_command_and_delay(
    shape: str,
) -> None:
    """The delay is cut out of each shape of Home Assistant to be written once; a shape
    from which it cannot be cut must stop the generator."""
    data = copy.deepcopy(get_intents("en"))
    assert data is not None
    block = next(
        block
        for block in data["intents"]["HassStartTimer"]["data"]
        if block.get("response") == "command"
    )
    block["sentences"] = [shape]

    with pytest.raises(
        ValueError, match=r"delayed command|alternative outside a group"
    ):
        delay_rules(data, {})


# --- Through an LLM's tools --------------------------------------------------------


async def test_llm_plans_a_command_to_turn_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """The agent plans the AC to turn on in 15 minutes, for an hour, cooling at 24, and
    is told when."""
    await setup_target(target=AC_ID)
    api = await assist_api(hass)

    planned = await call_tool(
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

    assert planned["speech_slots"]["outcome"] == "command_added"
    assert planned["speech_slots"]["at"] == "09:15"
    assert planned["speech_slots"]["in_days"] == 0
    assert state_of(hass, AC_NEXT) == "2026-01-05T07:15:00+00:00"
    await advance(hass, freezer, minutes=15)
    assert fake_climate.call_data == COOL_24
    assert state_of(hass, AC_NUMBER) == "60"


async def test_llm_plans_a_command_to_turn_off(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """A running boiler gets the time; one that is off is left as it is, and the agent
    is told which."""
    api = await assist_api(hass)

    idle = await call_tool(
        api,
        "timerify__delayed_command",
        {"name": "Boiler", "action": "off", "delay_minutes": 10},
    )
    await call_tool(api, "timerify__run", {"name": "Boiler", "minutes": 45})
    running = await call_tool(
        api,
        "timerify__delayed_command",
        {"name": "Boiler", "action": "off", "delay_hours": 0, "delay_minutes": 10},
    )

    assert idle["speech_slots"]["outcome"] == "not_running"
    assert running["speech_slots"]["outcome"] == "timer_set"
    assert running["speech_slots"]["ends_at"] == "09:10"
    assert state_of(hass, NUMBER) == "10"


async def test_llm_plans_a_command_at_a_clock_time(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """P-5: a tool takes the date and time that the service takes, on the clock of the
    house; the sentences say a time of day in slots of their own, which no tool has."""
    api = await assist_api(hass)

    planned = await call_tool(
        api,
        "timerify__delayed_command",
        {"name": "Boiler", "action": "on", "at": "2026-01-05 10:30:00"},
    )

    assert planned["speech_slots"]["outcome"] == "command_added"
    assert planned["speech_slots"]["at"] == "10:30"
    assert state_of(hass, NEXT) == "2026-01-05T08:30:00+00:00"


@pytest.mark.parametrize(
    ("args", "key", "placeholders"),
    [
        (
            {"action": "on", "delay_minutes": 5, "at": "2026-01-05 10:30:00"},
            "delay_or_at",
            {},
        ),
        ({"action": "on"}, "delay_or_at", {}),
        ({"action": "on", "at": "soon"}, "invalid_command_time", {}),
        (
            {"action": "on", "delay_hours": 0, "delay_minutes": 0},
            "command_in_past",
            {"at": "09:00"},
        ),
        ({"action": "on", "delay_hours": 200}, "command_too_far", {"days": "7"}),
        ({"action": "on", "delay_hours": 10**8}, "command_too_far", {"days": "7"}),
        ({"action": "on", "delay_hours": 10**15}, "command_too_far", {"days": "7"}),
        (
            {"action": "off", "delay_hours": 10**8},
            "duration_out_of_range",
            {"max_hours": "24"},
        ),
        (
            {"action": "off", "delay_seconds": 10**18},
            "duration_out_of_range",
            {"max_hours": "24"},
        ),
        (
            {"action": "off", "delay_minutes": 10, "minutes": 5},
            "off_takes_no_duration_or_settings",
            {},
        ),
    ],
)
async def test_llm_is_told_why_a_command_cannot_be_planned(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    args: dict[str, Any],
    key: str,
    placeholders: dict[str, str],
) -> None:
    api = await assist_api(hass)

    refused = await call_tool(
        api, "timerify__delayed_command", {"name": "Boiler", **args}
    )

    assert refused["response_type"] == "error"
    assert refused["speech"]["plain"]["speech"] == translated(
        "en", "exceptions", key, "message"
    ).format(**placeholders)
    assert pending(hass, NEXT) == []


async def test_llm_zero_delay_leaves_a_running_boiler_as_it_is(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    await set_number(hass, NUMBER, 30)
    api = await assist_api(hass)

    refused = await call_tool(
        api,
        "timerify__delayed_command",
        {"name": "Boiler", "action": "off", "delay_minutes": 0},
    )

    assert refused["response_type"] == "error"
    assert fake_target.state == "on"
    assert state_of(hass, NUMBER) == "30"


async def test_llm_is_told_in_the_language_of_the_request(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    api = await assist_api(hass, language="ru")

    refused = await call_tool(
        api,
        "timerify__delayed_command",
        {"name": "Boiler", "action": "on", "at": "soon"},
    )

    assert refused["speech"]["plain"]["speech"] == translated(
        "ru", "exceptions", "invalid_command_time", "message"
    )
