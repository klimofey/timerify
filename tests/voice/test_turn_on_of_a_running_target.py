"""A bare "turn on" of a target that the timer already wants running.

R9 turns a target that is off on, with no countdown in loose mode and for the default
duration in strict mode. A target that is already wanted running keeps its countdown,
whoever asks without a duration (the voice, the name alone, a tool, the service or a
pending command), and the answer says how long is left; a pending command still sets
what it turns the target on with. Every scenario talks to the real built-in agent, the
real Assist API or the real services, and the clock is moved explicitly.
"""

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.const import Mode

from ..conftest import FakeTarget, SetupTarget
from ..helpers import (
    AC_ID,
    AC_NUMBER,
    NEXT,
    NUMBER,
    SENSOR,
    START,
    SUNDAY,
    TURN_OFF,
    TURN_ON,
    add_command,
    add_interval,
    advance,
    advance_to,
    call_service,
    edit_interval,
    iso,
    local,
    open_sunday,
    state_of,
)
from .helpers import (
    assist_api,
    call_tool,
    converse,
    copy_sentences,
    reached,
    speech,
)

RUN = "TimerifyRun"
COOL_24 = [
    ("set_hvac_mode", {"hvac_mode": "cool"}),
    ("set_temperature", {"temperature": 24.0}),
]
"""The calls that put the air conditioner into cooling at 24 degrees."""
MODES: list[Mode] = ["strict", "loose"]


def at_hour(hours: int) -> str:
    """What the "Ends at" sensor shows for `hours` after the start of the scenario."""
    return (START + timedelta(hours=hours)).isoformat()


# --- The words of a bare turn-on ---------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "turn on the boiler",
        "turn the boiler on",
        "activate the boiler",
        "boiler",
    ],
)
async def test_strict_a_bare_turn_on_keeps_a_two_hour_run(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    text: str,
) -> None:
    """Ten minutes into a run of two hours, the boiler is asked to turn on again: it
    runs until eleven, as it was told, and the answer says what is left. It was cut to
    the default duration before."""
    await converse(hass, "turn on the boiler for 2 hours")
    await advance(hass, freezer, minutes=10)

    response = await converse(hass, text)

    assert reached(response) == RUN
    assert speech(response) == "Boiler runs for 1 hour and 50 minutes, until 11:00."
    assert state_of(hass, NUMBER) == "110"
    assert state_of(hass, SENSOR) == at_hour(2)
    await advance(hass, freezer, minutes=109)
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=1)
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_loose_a_bare_turn_on_keeps_a_run_of_twenty_minutes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """In loose mode the bare turn-on used to run the boiler with no countdown, which
    took away the auto-off that was asked for."""
    await setup_target(mode="loose")
    await copy_sentences(hass, ["Boiler"])
    await converse(hass, "turn on the boiler for 20 minutes")
    await advance(hass, freezer, minutes=5)

    response = await converse(hass, "turn on the boiler")

    assert speech(response) == "Boiler runs for 15 minutes, until 09:20."
    assert state_of(hass, NUMBER) == "15"
    await advance(hass, freezer, minutes=15)
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_loose_a_bare_turn_on_of_a_run_without_a_countdown_changes_nothing(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    await setup_target(mode="loose")
    await copy_sentences(hass, ["Boiler"])
    await converse(hass, "turn on the boiler")

    response = await converse(hass, "turn on the boiler")

    assert speech(response) == "Boiler is on."
    assert state_of(hass, NUMBER) == "0"
    assert fake_target.calls == [TURN_ON]


async def test_a_bare_turn_on_after_a_stop_is_the_default_run_again(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """R9 is for a target that is off: once the run was stopped, a bare turn-on runs the
    boiler for its default duration."""
    await converse(hass, "turn on the boiler for 2 hours")
    await converse(hass, "stop the boiler timer")

    response = await converse(hass, "turn on the boiler")

    assert speech(response) == "Boiler runs for 45 minutes, until 09:45."
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]


async def test_a_bare_turn_on_of_an_unavailable_target_keeps_its_countdown_and_its_wish(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
) -> None:
    """R10: the boiler is away while its countdown runs, and the wish is kept; asking
    again changes neither, and it is turned on once when it is back."""
    await fake_target.set_state("unavailable")
    await converse(hass, "turn on the boiler for 30 minutes")
    await advance(hass, freezer, minutes=5)

    response = await converse(hass, "turn on the boiler")

    assert speech(response) == "Boiler runs for 25 minutes, until 09:30."
    await fake_target.set_state("off")
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "25"


# --- Through an LLM's tools and the service ----------------------------------------


@pytest.mark.parametrize("mode", MODES)
async def test_llm_run_without_a_duration_keeps_a_running_countdown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
    mode: Mode,
) -> None:
    """The tool says the same as the voice: how long is left, and the countdown is
    the one that was asked for."""
    await setup_target(mode=mode)
    api = await assist_api(hass)
    await call_tool(api, "timerify__run", {"name": "Boiler", "hours": 2})
    await advance(hass, freezer, minutes=10)

    ran = await call_tool(api, "timerify__run", {"name": "Boiler"})

    assert ran["speech_slots"]["state"] == "counting"
    assert ran["speech_slots"]["left_total"] == 110
    assert ran["speech_slots"]["ends_at"] == "11:00"
    assert fake_target.calls == [TURN_ON]


async def test_llm_run_without_a_duration_of_an_open_run_says_it_is_on(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    await setup_target(mode="loose")
    api = await assist_api(hass)
    await call_tool(api, "timerify__run", {"name": "Boiler"})

    ran = await call_tool(api, "timerify__run", {"name": "Boiler"})

    assert ran["speech_slots"]["state"] == "open"
    assert fake_target.calls == [TURN_ON]


async def test_llm_run_with_settings_and_no_duration_sets_them_and_keeps_the_countdown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """The air conditioner runs for two hours. Asked to cool at 24 with no duration, it
    is set to that and runs as long as it was told."""
    await setup_target(target=AC_ID)
    api = await assist_api(hass)
    await call_tool(api, "timerify__run", {"name": "AC", "hours": 2})
    await advance(hass, freezer, minutes=10)
    fake_climate.call_data.clear()

    ran = await call_tool(
        api, "timerify__run", {"name": "AC", "hvac_mode": "cool", "temperature": 24}
    )

    assert fake_climate.call_data == COOL_24
    assert ran["speech_slots"]["left_total"] == 110
    assert state_of(hass, AC_NUMBER) == "110"


@pytest.mark.parametrize("mode", MODES)
async def test_the_run_service_without_minutes_keeps_a_running_countdown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    mode: Mode,
) -> None:
    await setup_target(mode=mode)
    await call_service(hass, "run", {"entity_id": NUMBER}, minutes=120)
    await advance(hass, freezer, minutes=10)

    await call_service(hass, "run", {"entity_id": NUMBER})

    assert state_of(hass, NUMBER) == "110"
    assert fake_target.calls == [TURN_ON]


# --- Inside a schedule window ------------------------------------------------------


@pytest.mark.parametrize("mode", MODES)
async def test_a_bare_turn_on_inside_a_window_leaves_its_end_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
    mode: Mode,
) -> None:
    """The window runs from half past six to ten. At twenty to seven the boiler is
    asked to turn on: it still ends at ten, it is not cut to the default duration
    (which the manual off would then have held until the next window), and the
    schedule still owns the countdown, so editing the interval realigns it."""
    await open_sunday(hass, freezer)
    entry = await setup_target(mode=mode)
    await copy_sentences(hass, ["Boiler"])
    interval = await add_interval(hass, entry, start="06:30", end="10:00")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "06:40"))

    response = await converse(hass, "turn on the boiler")

    assert speech(response) == "Boiler runs for 3 hours and 20 minutes, until 10:00."
    assert state_of(hass, SENSOR) == iso(SUNDAY, "10:00")
    await advance_to(hass, freezer, local(SUNDAY, "07:30"))
    assert fake_target.calls == [TURN_ON]
    await edit_interval(hass, entry, interval, end="09:00")
    assert state_of(hass, SENSOR) == iso(SUNDAY, "09:00")
    await advance_to(hass, freezer, local(SUNDAY, "09:00"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


# --- A pending command to turn on, without a duration ------------------------------


@pytest.mark.parametrize("mode", MODES)
async def test_a_planned_turn_on_without_a_duration_leaves_a_running_countdown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
    mode: Mode,
) -> None:
    """ "Turn on the boiler in 15 minutes", with the boiler running for two hours: when
    it comes due it finds the boiler wanted running and changes nothing about when it
    ends, which would otherwise have been the default duration or no end at all."""
    await setup_target(mode=mode)
    await copy_sentences(hass, ["Boiler"])
    await converse(hass, "turn on the boiler for 2 hours")
    planned = await converse(hass, "turn on the boiler in 15 minutes")
    assert speech(planned) == "Boiler turns on at 09:15."

    await advance(hass, freezer, minutes=15)

    assert state_of(hass, NEXT) == "unknown"
    assert state_of(hass, NUMBER) == "105"
    asked = await converse(hass, "how long is left on the boiler")
    assert (
        speech(asked) == "1 hour and 45 minutes left on Boiler, it turns off at 11:00."
    )
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=105)
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_a_planned_turn_on_with_settings_still_sets_them_on_a_running_ac(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """P1: the command is a firm promise. It does not change when the air conditioner
    stops, and it puts it into cooling at 24 degrees."""
    await setup_target(target=AC_ID)
    await call_service(hass, "run", {"entity_id": AC_NUMBER}, minutes=120)
    await add_command(
        hass, AC_NUMBER, action="on", delay=15, hvac_mode="cool", temperature=24
    )
    fake_climate.call_data.clear()

    await advance(hass, freezer, minutes=15)

    assert fake_climate.call_data == COOL_24
    assert state_of(hass, AC_NUMBER) == "105"
