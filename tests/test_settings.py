"""Turning a target on with settings: what `run` sends, what the device does with
it, and what happens when it does not take them."""

import asyncio
from typing import Any

import probatio
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.timerify.const import DOMAIN, MAX_AUTOMATIC_RESENDS, MAX_MINUTES

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    AC_ID,
    AC_NUMBER,
    NUMBER,
    TURN_ON,
    call_service,
    set_number,
    state_of,
    timerify_warnings,
)

COOL = ("set_hvac_mode", {"hvac_mode": "cool"})
COOL_24 = [COOL, ("set_temperature", {"temperature": 24.0})]
"""The calls that turn the air conditioner on cooling, at 24 degrees."""


def temperature_of(hass: HomeAssistant, entity_id: str) -> object:
    state = hass.states.get(entity_id)
    assert state is not None
    return state.attributes["temperature"]


async def test_run_with_settings_turns_ac_on_cooling(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """An air conditioner that is off is put straight into cooling at 24 degrees, for
    an hour; no plain turn-on comes first."""
    await setup_target(target=AC_ID)

    await call_service(
        hass,
        "run",
        {"entity_id": AC_NUMBER},
        minutes=60,
        hvac_mode="cool",
        temperature=24,
    )

    assert fake_climate.call_data == COOL_24
    assert state_of(hass, AC_ID) == "cool"
    assert temperature_of(hass, AC_ID) == 24.0
    assert state_of(hass, AC_NUMBER) == "60"


async def test_run_with_settings_on_running_ac_applies_them(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """An air conditioner that already runs is not turned on again; it is switched to
    the mode asked for, and its running timer stays."""
    await setup_target(target=AC_ID)
    await fake_climate.set_state("heat")
    assert state_of(hass, AC_NUMBER) == "45"

    await call_service(hass, "run", {"entity_id": AC_NUMBER}, hvac_mode="cool")

    assert fake_climate.calls == [("set_hvac_mode", AC_ID)]
    assert fake_climate.call_data == [COOL]
    assert state_of(hass, AC_ID) == "cool"
    assert state_of(hass, AC_NUMBER) == "45"


async def test_run_with_minutes_only_sets_the_timer(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A switch has no settings; asking for minutes alone is the plain timer."""
    await setup_target()

    await call_service(hass, "run", {"entity_id": NUMBER}, minutes=20)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "20"


async def test_failed_settings_call_is_retried_on_next_report(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A device that rejects the turn-on is asked again, with the settings, the next
    time it reports."""
    await setup_target(target=AC_ID)
    fake_climate.fail_next_call(service="set_hvac_mode")

    await call_service(
        hass,
        "run",
        {"entity_id": AC_NUMBER},
        minutes=60,
        hvac_mode="cool",
        temperature=24,
    )

    assert timerify_warnings(caplog) == [
        "Could not turn climate.ac on: The device rejected the command"
    ]
    assert fake_climate.call_data == [COOL]
    assert state_of(hass, AC_ID) == "off"
    assert state_of(hass, AC_NUMBER) == "60"

    await fake_climate.set_state("off", signal=70)

    assert fake_climate.call_data == [COOL, *COOL_24]
    assert state_of(hass, AC_ID) == "cool"
    assert temperature_of(hass, AC_ID) == 24.0


async def test_failed_apply_is_retried_on_the_targets_report(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The mode took but the temperature did not: the report of the mode change sends
    all the settings again, and the temperature follows."""
    await setup_target(target=AC_ID)
    await fake_climate.set_state("heat")
    fake_climate.fail_next_call(service="set_temperature")

    await call_service(
        hass, "run", {"entity_id": AC_NUMBER}, hvac_mode="cool", temperature=24
    )

    assert "Could not apply settings to climate.ac" in caplog.text
    assert fake_climate.call_data == [*COOL_24, *COOL_24]
    assert state_of(hass, AC_ID) == "cool"
    assert temperature_of(hass, AC_ID) == 24.0


async def test_ignored_turn_on_keeps_the_settings_owed(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """A device that accepts the calls and does nothing is told the turn-on again, with
    its settings, when it next reports."""
    await setup_target(target=AC_ID)
    fake_climate.ignore_calls()

    await call_service(
        hass,
        "run",
        {"entity_id": AC_NUMBER},
        minutes=60,
        hvac_mode="cool",
        temperature=24,
    )

    assert fake_climate.call_data == COOL_24
    assert state_of(hass, AC_ID) == "off"
    fake_climate.obey_calls()

    await fake_climate.set_state("off", signal=70)

    assert fake_climate.call_data == [*COOL_24, *COOL_24]
    assert state_of(hass, AC_ID) == "cool"
    assert temperature_of(hass, AC_ID) == 24.0


async def test_ignored_mode_change_is_repeated_when_the_rest_of_the_list_reports(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The device ignores the mode but takes the temperature, and says so: that report
    of its unchanged state is answered with the whole list again."""
    await setup_target(target=AC_ID)
    fake_climate.ignore_next_call()

    await call_service(
        hass,
        "run",
        {"entity_id": AC_NUMBER},
        minutes=60,
        hvac_mode="cool",
        temperature=24,
    )

    assert fake_climate.call_data == [*COOL_24, *COOL_24]
    assert state_of(hass, AC_ID) == "cool"


async def test_settings_wait_while_ac_unavailable(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """Nothing is sent to a device that is away; the settings are applied the moment
    it is back."""
    await setup_target(target=AC_ID)
    await fake_climate.set_state("unavailable")

    await call_service(
        hass,
        "run",
        {"entity_id": AC_NUMBER},
        minutes=60,
        hvac_mode="cool",
        temperature=24,
    )

    assert fake_climate.call_data == []
    assert state_of(hass, AC_NUMBER) == "60"

    await fake_climate.set_state("off")

    assert fake_climate.call_data == COOL_24
    assert state_of(hass, AC_ID) == "cool"


async def test_settings_are_not_resent_once_applied(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """A device that took the settings is left alone by its later reports."""
    await setup_target(target=AC_ID)
    await call_service(
        hass,
        "run",
        {"entity_id": AC_NUMBER},
        minutes=60,
        hvac_mode="cool",
        temperature=24,
    )

    await fake_climate.set_state("cool", signal=70)
    await fake_climate.set_state("cool", signal=60)

    assert fake_climate.call_data == COOL_24


async def test_stopping_the_timer_drops_the_settings_that_wait(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """A timer that was stopped before its device came back has nothing to run with."""
    await setup_target(target=AC_ID)
    await fake_climate.set_state("unavailable")
    await call_service(
        hass,
        "run",
        {"entity_id": AC_NUMBER},
        minutes=60,
        hvac_mode="cool",
        temperature=24,
    )

    await set_number(hass, AC_NUMBER, 0)
    await fake_climate.set_state("off")

    assert fake_climate.call_data == []
    assert state_of(hass, AC_ID) == "off"


async def test_restart_during_a_slow_call_still_delivers_the_settings(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """Home Assistant stopping while the device answers the first call of the list
    leaves the rest undone; they are sent when the timer is back."""
    entry = await setup_target(target=AC_ID)
    slow = fake_climate.hold_next_call()
    start = asyncio.ensure_future(
        entry.runtime_data.async_run(60, {"hvac_mode": "cool", "temperature": 24})
    )
    await slow.reached.wait()
    await hass.config_entries.async_unload(entry.entry_id)
    slow.release.set()  # the device switches the mode although nobody is listening
    await start

    assert fake_climate.call_data == [COOL]

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert fake_climate.call_data == [COOL, *COOL_24]
    assert temperature_of(hass, AC_ID) == 24.0
    assert state_of(hass, AC_NUMBER) == "60"


async def test_newer_settings_replace_the_ones_that_wait(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """Two runs while the device is away: it gets what the second one asked for."""
    await setup_target(target=AC_ID)
    await fake_climate.set_state("unavailable")
    await call_service(
        hass, "run", {"entity_id": AC_NUMBER}, minutes=60, hvac_mode="cool"
    )
    await call_service(
        hass, "run", {"entity_id": AC_NUMBER}, minutes=30, hvac_mode="heat"
    )

    await fake_climate.set_state("off")

    assert fake_climate.call_data == [("set_hvac_mode", {"hvac_mode": "heat"})]
    assert state_of(hass, AC_NUMBER) == "30"


async def test_settings_that_keep_failing_are_given_up_on(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A device that rejects the settings every time it reports is asked 3 times after
    the first, told so once in the log, and then left alone."""
    await setup_target(target=AC_ID)
    await fake_climate.set_state("heat")
    fake_climate.fail_next_call(service="set_hvac_mode")
    await call_service(hass, "run", {"entity_id": AC_NUMBER}, hvac_mode="cool")

    for signal in range(MAX_AUTOMATIC_RESENDS + 3):
        fake_climate.fail_next_call(service="set_hvac_mode")
        await fake_climate.set_state("heat", signal=signal)

    asked = 1 + MAX_AUTOMATIC_RESENDS
    assert fake_climate.call_data == [COOL] * asked
    assert timerify_warnings(caplog)[-1] == (
        "climate.ac did not take its settings after 4 attempts; Timerify will try"
        " again when it reports a change or on the next command"
    )
    assert len(timerify_warnings(caplog)) == asked + 1


async def test_service_that_keeps_raising_on_settings_logs_its_traceback_once(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A bug in the device's integration is shown in full for the first try of a set
    of settings, then as a line for each retry; other settings get their own."""
    await setup_target(target=AC_ID)
    await fake_climate.set_state("heat")
    bug = ConnectionError("The hub is unreachable")
    fake_climate.fail_next_call(bug, service="set_hvac_mode")
    await call_service(hass, "run", {"entity_id": AC_NUMBER}, hvac_mode="cool")
    fake_climate.fail_next_call(bug, service="set_hvac_mode")

    await fake_climate.set_state("heat", signal=70)

    assert len([record for record in caplog.records if record.exc_info]) == 1
    assert timerify_warnings(caplog)[-1] == (
        "Could not apply settings to climate.ac: its service raised"
        " ConnectionError('The hub is unreachable') again"
    )
    fake_climate.fail_next_call(bug, service="set_hvac_mode")

    await call_service(hass, "run", {"entity_id": AC_NUMBER}, hvac_mode="fan_only")

    assert len([record for record in caplog.records if record.exc_info]) == 2


@pytest.mark.parametrize(
    ("data", "key"),
    [
        ({"hvac_mode": "dry"}, "setting_not_an_option"),
        ({"temperature": 35}, "setting_out_of_range"),
        ({"brightness_pct": 50}, "setting_not_supported"),
        ({"fan_mode": "turbo"}, "setting_not_an_option"),
    ],
    ids=["unknown_mode", "too_warm", "not_a_light", "unknown_fan_mode"],
)
async def test_invalid_settings_are_rejected_before_anything_runs(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    data: dict[str, Any],
    key: str,
) -> None:
    """Settings the air conditioner cannot take are refused with the reason, and the
    timer does not start."""
    await setup_target(target=AC_ID)

    with pytest.raises(ServiceValidationError) as err:
        await call_service(hass, "run", {"entity_id": AC_NUMBER}, minutes=60, **data)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == key
    assert fake_climate.calls == []
    assert state_of(hass, AC_NUMBER) == "0"


async def test_settings_a_switch_cannot_take_are_rejected(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A plain switch has no settings at all."""
    await setup_target()

    with pytest.raises(ServiceValidationError) as err:
        await call_service(hass, "run", {"entity_id": NUMBER}, temperature=20)

    assert err.value.translation_key == "setting_not_supported"
    assert fake_target.calls == []


@pytest.mark.parametrize("minutes", [0, MAX_MINUTES + 1, 2.5])
async def test_run_minutes_outside_range_are_rejected(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    minutes: float,
) -> None:
    """A run is for a whole number of minutes between one and a day."""
    await setup_target()

    with pytest.raises(probatio.Invalid):
        await call_service(hass, "run", {"entity_id": NUMBER}, minutes=minutes)

    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "0"


@pytest.mark.parametrize(
    "data",
    [{"percentage": 50.5}, {"percentage": True}, {"temperature": "warm"}],
    ids=["fractional_speed", "boolean_speed", "text_temperature"],
)
async def test_settings_of_the_wrong_type_are_rejected(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    data: dict[str, Any],
) -> None:
    """A number that is not one, or not whole where it must be, never reaches the
    air conditioner."""
    await setup_target(target=AC_ID)

    with pytest.raises(probatio.Invalid):
        await call_service(hass, "run", {"entity_id": AC_NUMBER}, **data)

    assert fake_climate.calls == []


async def test_settings_given_as_text_are_understood(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """A template hands over "24" for a number; the air conditioner gets 24.0."""
    await setup_target(target=AC_ID)

    await call_service(
        hass, "run", {"entity_id": AC_NUMBER}, hvac_mode="cool", temperature="24"
    )

    assert fake_climate.call_data == COOL_24
