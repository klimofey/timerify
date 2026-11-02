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
    COMMAND,
    COMMAND_RULE,
    COMMAND_RULE_NAME,
    COMMAND_SLOT,
    DELAY_AFTER_RULE_NAME,
    DELAY_BEFORE_RULE_NAME,
    DELAYED_COMMAND,
    EXTRAS,
    FILE_NAME,
    SOURCE_FILE,
    TIMERIFY_COMMANDS,
    CommandBlock,
    command_blocks,
    command_group,
    delay_rules,
    delayed_shapes,
    render,
    run_scopes,
)

from ..conftest import FakeTarget, SetupTarget
from ..helpers import (
    AC_ID,
    AC_NEXT,
    AC_NUMBER,
    NEXT,
    NUMBER,
    SENSOR,
    START,
    TURN_OFF,
    TURN_ON,
    advance,
    call_service,
    set_number,
    state_of,
)
from .helpers import (
    assist_api,
    call_tool,
    converse,
    copy_sentences,
    reached,
    readings,
    refusal_of,
    speech,
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


def pending(hass: HomeAssistant, entity_id: str) -> list[dict[str, Any]]:
    """The commands a "Next command" sensor lists in its attributes."""
    state = hass.states.get(entity_id)
    assert state is not None
    commands: list[dict[str, Any]] = state.attributes["commands"]
    return commands


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
    seconds of the delay in slots of their own, and a command to turn on followed by how
    long it runs and the settings, if the delay comes after it, or before the delay, or
    after it; or, if the delay comes first, followed by them."""
    sentences: set[str] = set()
    for shape in shapes:
        named = re.sub(r"\{timer_(\w+):\1\}", r"{timer_\1:delay_\1}", shape)
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
        delay_rules(data)


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
    """P-5: a tool takes the time of day that the service takes, on the clock of the
    house, which voice does not say."""
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
