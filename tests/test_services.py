"""The services of a timer: add time to it, run the target, make and cancel commands."""

import logging
from typing import Any

import probatio
import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.setup import async_setup_component

from custom_components.timerify.const import DOMAIN, MAX_DELAY_MINUTES, MAX_MINUTES

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    NEXT,
    NUMBER,
    SENSOR,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    add_command,
    advance,
    call_service,
    set_number,
    state_of,
)


async def test_add_time_extends_running_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """At 07:10 with 5 minutes left, adding 30 moves the end to 07:45."""
    await setup_target()
    await set_number(hass, NUMBER, 15)
    await advance(hass, freezer, minutes=10)
    assert state_of(hass, NUMBER) == "5"

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=30)

    assert state_of(hass, SENSOR) == "2026-01-05T07:45:00+00:00"
    assert state_of(hass, NUMBER) == "35"
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=34)
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=1)
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_add_time_on_idle_target_starts_it(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Adding time to a target that is not running turns it on for that long."""
    await setup_target()

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=20)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "20"
    assert state_of(hass, SENSOR) == "2026-01-05T07:20:00+00:00"
    assert state_of(hass, TARGET_ID) == "on"


async def test_negative_add_time_shortens_running_timer(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Taking minutes off leaves the target running for the rest."""
    await setup_target()
    await set_number(hass, NUMBER, 30)

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=-10)

    assert state_of(hass, NUMBER) == "20"
    assert fake_target.calls == [TURN_ON]


@pytest.mark.parametrize("minutes", [-15, -40])
async def test_negative_add_time_to_zero_turns_off(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    minutes: int,
) -> None:
    """Taking off all the time that is left, or more, switches the target off."""
    await setup_target()
    await set_number(hass, NUMBER, 15)

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=minutes)

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, NUMBER) == "0"
    assert state_of(hass, SENSOR) == "unknown"
    assert state_of(hass, TARGET_ID) == "off"


async def test_negative_add_time_on_idle_target_does_nothing(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """There is nothing to take time from, so the target stays off."""
    await setup_target()

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=-5)

    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "0"


async def test_add_time_accepts_up_to_a_day(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The longest timer is one day, and a service call may ask for all of it."""
    await setup_target()

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=MAX_MINUTES)

    assert state_of(hass, NUMBER) == str(MAX_MINUTES)
    assert fake_target.calls == [TURN_ON]


async def test_add_time_never_passes_a_day(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Adding a day twice still leaves a day: the timer is capped, not doubled."""
    await setup_target()

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=MAX_MINUTES)
    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=MAX_MINUTES)

    assert state_of(hass, NUMBER) == str(MAX_MINUTES)
    assert state_of(hass, SENSOR) == "2026-01-06T07:00:00+00:00"
    assert fake_target.calls == [TURN_ON]


@pytest.mark.parametrize("minutes", [15.0, "15", "15.0"], ids=repr)
async def test_add_time_accepts_whole_numbers_in_any_form(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    minutes: float | str,
) -> None:
    """A template may hand over 15.0 or "15", as an input_number's state does."""
    await setup_target()

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=minutes)

    assert state_of(hass, NUMBER) == "15"
    assert fake_target.calls == [TURN_ON]


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"minutes": MAX_MINUTES + 1},
        {"minutes": -MAX_MINUTES - 1},
        {"minutes": 2.5},
        {"minutes": "2.5"},
        {"minutes": True},
        {"minutes": "soon"},
    ],
    ids=[
        "missing",
        "above_a_day",
        "below_minus_a_day",
        "not_whole",
        "not_whole_text",
        "boolean",
        "text",
    ],
)
async def test_add_time_rejects_invalid_minutes(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    data: dict[str, Any],
) -> None:
    """A call without a whole number of minutes within a day changes nothing."""
    await setup_target()

    with pytest.raises(probatio.Invalid):
        await call_service(hass, "add_time", {"entity_id": NUMBER}, **data)

    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "0"


async def test_run_strict_uses_default_duration(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """In strict mode running without a duration counts down the default one."""
    await setup_target(mode="strict", default_duration=45)

    await call_service(hass, "run", {"entity_id": NUMBER})

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "45"
    assert state_of(hass, SENSOR) == "2026-01-05T07:45:00+00:00"


async def test_run_loose_turns_on_without_countdown(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """In loose mode running without a duration leaves the timer at zero."""
    await setup_target(mode="loose")

    await call_service(hass, "run", {"entity_id": NUMBER})

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, NUMBER) == "0"
    assert state_of(hass, SENSOR) == "unknown"


@pytest.mark.parametrize(
    ("service", "data", "left"),
    [("add_time", {"minutes": 20}, "20"), ("run", {}, "45")],
)
async def test_services_record_the_timer_of_an_unavailable_target(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    service: str,
    data: dict[str, Any],
    left: str,
) -> None:
    """The timer does not go unavailable with its target, so the services still
    reach it; the target is switched on once it is back."""
    await setup_target(default_duration=45)
    await fake_target.set_state("unavailable")

    await call_service(hass, service, {"entity_id": NUMBER}, **data)

    assert state_of(hass, NUMBER) == left
    assert fake_target.calls == []

    await fake_target.set_state("off")

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, NUMBER) == left


async def test_services_accept_the_device_of_the_target(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Picking the device in the UI reaches the timer on it."""
    await setup_target()

    await call_service(
        hass, "add_time", {"device_id": fake_target.device_id}, minutes=10
    )

    assert state_of(hass, NUMBER) == "10"
    assert fake_target.calls == [TURN_ON]


async def test_services_on_unloaded_timer_do_nothing(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A timer that is not loaded is skipped, as Home Assistant skips any
    unavailable entity, and the target is left alone."""
    entry = await setup_target()
    await hass.config_entries.async_unload(entry.entry_id)
    caplog.set_level(logging.WARNING)

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=10)
    await call_service(hass, "run", {"entity_id": NUMBER})
    await call_service(hass, "add_command", {"entity_id": NUMBER}, action="on", delay=5)
    await call_service(hass, "cancel_command", {"entity_id": NUMBER}, command_id="c1")

    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "unavailable"
    assert f"Referenced entities {NUMBER} are missing" in caplog.text


async def test_add_command_asking_for_a_response_on_unloaded_timer_fails(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Home Assistant has nothing to answer for with: a call that wants the new
    command's id from a timer that is not loaded is an error, not a warning."""
    entry = await setup_target()
    await hass.config_entries.async_unload(entry.entry_id)

    with pytest.raises(HomeAssistantError, match="did not match any entities"):
        await add_command(hass, NUMBER, action="on", delay=5)

    assert fake_target.calls == []


@pytest.mark.parametrize("delay", [15.0, "15", "15.0"], ids=repr)
async def test_add_command_accepts_a_delay_in_any_whole_form(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    delay: float | str,
) -> None:
    """A template may hand over 15.0 or "15" as the delay, as it does for minutes."""
    await setup_target()

    await add_command(hass, NUMBER, action="on", delay=delay)

    assert state_of(hass, NEXT) == "2026-01-05T07:15:00+00:00"


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"action": "pause", "delay": 5},
        {"action": "on", "delay": 0},
        {"action": "on", "delay": MAX_DELAY_MINUTES + 1},
        {"action": "on", "delay": 2.5},
        {"action": "on", "delay": True},
        {"action": "on", "delay": 5, "minutes": 0},
        {"action": "on", "delay": 5, "minutes": MAX_MINUTES + 1},
        {"action": "on", "delay": 5, "minutes": 2.5},
        {"action": "on", "at": "tomorrow evening"},
        {"action": "on", "delay": 5, "temperature": "warm"},
    ],
    ids=[
        "missing",
        "unknown_action",
        "delay_zero",
        "delay_above_a_week",
        "delay_not_whole",
        "delay_boolean",
        "minutes_zero",
        "minutes_above_a_day",
        "minutes_not_whole",
        "at_not_a_time",
        "setting_of_the_wrong_type",
    ],
)
async def test_add_command_rejects_invalid_values(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    data: dict[str, Any],
) -> None:
    """A call with a value out of range or of the wrong kind makes no command."""
    await setup_target()

    with pytest.raises(probatio.Invalid):
        await add_command(hass, NUMBER, **data)

    assert state_of(hass, NEXT) == "unknown"
    assert fake_target.calls == []


async def test_cancel_command_needs_the_command_id(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Cancelling without saying which command is not guessed at."""
    await setup_target()
    await add_command(hass, NUMBER, action="on", delay=5)

    with pytest.raises(probatio.Invalid):
        await call_service(hass, "cancel_command", {"entity_id": NUMBER})

    assert state_of(hass, NEXT) == "2026-01-05T07:05:00+00:00"


async def test_services_are_described_for_the_ui(hass: HomeAssistant) -> None:
    """The UI offers the services for Timerify's "Run for" numbers only, and the
    range it lets the user pick is the range the service accepts."""
    assert await async_setup_component(hass, DOMAIN, {})

    descriptions = (await async_get_all_descriptions(hass))[DOMAIN]

    target = {"entity": [{"integration": DOMAIN, "domain": ["number"]}]}
    assert descriptions["add_time"]["target"] == target
    assert descriptions["run"]["target"] == target
    minutes = descriptions["add_time"]["fields"]["minutes"]
    assert minutes["required"] is True
    assert minutes["selector"]["number"]["min"] == -MAX_MINUTES
    assert minutes["selector"]["number"]["max"] == MAX_MINUTES
    run_for = descriptions["run"]["fields"]["minutes"]
    assert run_for["selector"]["number"]["min"] == 1
    assert run_for["selector"]["number"]["max"] == MAX_MINUTES
    settings = descriptions["run"]["fields"]["settings"]
    assert settings["collapsed"] is True
    assert settings["fields"].keys() == {
        "hvac_mode",
        "temperature",
        "fan_mode",
        "preset_mode",
        "mode",
        "operation_mode",
        "brightness_pct",
        "percentage",
        "humidity",
    }

    assert descriptions["add_command"]["target"] == target
    command = descriptions["add_command"]["fields"]
    assert command.keys() == {"action", "delay", "at", "minutes", "settings"}
    assert command["action"]["required"] is True
    assert command["action"]["selector"]["select"]["options"] == ["on", "off"]
    assert command["delay"]["selector"]["number"]["min"] == 1
    assert command["delay"]["selector"]["number"]["max"] == MAX_DELAY_MINUTES
    assert command["at"]["selector"].keys() == {"datetime"}
    assert command["minutes"]["selector"]["number"]["min"] == 1
    assert command["minutes"]["selector"]["number"]["max"] == MAX_MINUTES
    assert command["settings"] == settings

    assert descriptions["cancel_command"]["target"] == target
    cancel = descriptions["cancel_command"]["fields"]["command_id"]
    assert cancel["required"] is True
    assert cancel["selector"].keys() == {"text"}
