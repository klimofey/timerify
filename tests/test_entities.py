"""The timer as the user meets it: the "Run for" number on the target's device."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_state_report_event,
)
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import TARGET_ID, FakeTarget, SetupTarget

NUMBER = "number.boiler_run_for"
TURN_ON = ("turn_on", TARGET_ID)
TURN_OFF = ("turn_off", TARGET_ID)


async def set_number(hass: HomeAssistant, entity_id: str, value: float) -> None:
    """Move the slider, as the dashboard does, and let the target's report settle."""
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": value},
        blocking=True,
    )
    await hass.async_block_till_done()


async def advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, **delta: float
) -> None:
    """Let time pass and run everything that falls due."""
    freezer.tick(timedelta(**delta))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def state_of(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


def record_writes(hass: HomeAssistant, entity_id: str) -> list[str]:
    """The state every write to `entity_id` carried, changed or not."""
    writes: list[str] = []

    @callback
    def record(
        event: Event[Any],
    ) -> None:
        writes.append(event.data["new_state"].state)

    async_track_state_change_event(hass, entity_id, record)
    async_track_state_report_event(hass, entity_id, record)
    return writes


async def test_setting_run_for_turns_target_on(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Setting a duration switches the target on and the number shows it."""
    await setup_target()

    await set_number(hass, NUMBER, 45)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "45"
    assert state_of(hass, TARGET_ID) == "on"


async def test_timer_expiry_turns_target_off(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """When the countdown reaches zero the target is switched off."""
    await setup_target()
    await set_number(hass, NUMBER, 45)

    await advance(hass, freezer, minutes=44)
    assert fake_target.calls == [TURN_ON]

    await advance(hass, freezer, minutes=1)

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, NUMBER) == "0"
    assert state_of(hass, TARGET_ID) == "off"


async def test_number_counts_down_once_a_minute(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The remaining minutes drop when the rounded-up value changes, never between."""
    await setup_target()
    await set_number(hass, NUMBER, 45)
    writes = record_writes(hass, NUMBER)

    await advance(hass, freezer, seconds=30)
    assert writes == []
    assert state_of(hass, NUMBER) == "45"

    await advance(hass, freezer, seconds=31)
    assert writes == ["44"]
    assert state_of(hass, NUMBER) == "44"

    await advance(hass, freezer, seconds=30)
    assert writes == ["44"]

    await advance(hass, freezer, seconds=30)
    assert writes == ["44", "43"]


async def test_setting_zero_turns_target_off(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Setting zero stops a running countdown and switches the target off."""
    await setup_target()
    await set_number(hass, NUMBER, 45)

    await set_number(hass, NUMBER, 0)

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, NUMBER) == "0"


async def test_manual_off_resets_run_for_to_zero(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Switching the target off by hand ends the countdown without any service call."""
    await setup_target()
    await set_number(hass, NUMBER, 45)

    await fake_target.set_state("off")

    assert state_of(hass, NUMBER) == "0"
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=45)
    assert fake_target.calls == [TURN_ON]


async def test_manual_on_in_strict_runs_default_duration(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A target switched on by hand in strict mode gets the default duration."""
    await setup_target(mode="strict", default_duration=45)

    await fake_target.set_state("on")

    assert state_of(hass, NUMBER) == "45"
    assert fake_target.calls == []
    await advance(hass, freezer, minutes=45)
    assert fake_target.calls == [TURN_OFF]


async def test_manual_on_in_loose_keeps_zero(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A target switched on by hand in loose mode simply runs, with no countdown."""
    await setup_target(mode="loose")

    await fake_target.set_state("on")

    assert state_of(hass, NUMBER) == "0"
    await advance(hass, freezer, hours=2)
    assert fake_target.calls == []
    assert state_of(hass, TARGET_ID) == "on"


async def test_failed_turn_on_is_retried(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A device that rejects turn_on keeps the timer; the command is sent again."""
    await setup_target()
    fake_target.fail_next_call()

    await set_number(hass, NUMBER, 10)

    assert "Could not turn switch.boiler on" in caplog.text
    assert state_of(hass, NUMBER) == "10"
    assert fake_target.calls == [TURN_ON]

    await fake_target.set_state("unavailable")
    await fake_target.set_state("off")

    assert fake_target.calls == [TURN_ON, TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, NUMBER) == "10"


async def test_failed_turn_on_is_retried_on_the_next_report(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Any report of a target that never switched on makes Timerify ask again."""
    await setup_target()
    fake_target.fail_next_call()
    await set_number(hass, NUMBER, 10)

    await fake_target.set_state("off", signal=70)

    assert fake_target.calls == [TURN_ON, TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"


async def test_expiry_while_target_unavailable_is_applied_when_it_is_back(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A Wi-Fi drop around expiry is not "off": the target is switched off on return."""
    caplog.set_level(logging.INFO, logger="custom_components.timerify")
    await setup_target()
    await set_number(hass, NUMBER, 45)
    await fake_target.set_state("unavailable")

    await advance(hass, freezer, minutes=45)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "0"
    assert (
        "switch.boiler is unavailable; it will be turned off when it is back"
        in caplog.text
    )

    await fake_target.set_state("on")

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"


async def test_dragging_the_slider_turns_the_target_on_once(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Several quick slider moves are applied one after another and switch on once."""
    await setup_target()

    await asyncio.gather(*(set_number(hass, NUMBER, value) for value in (10, 20, 30)))

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "30"


async def test_stopping_while_the_target_is_still_switching_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A slow device is not overtaken: the stop waits, then the target ends up off."""
    controller = (await setup_target()).runtime_data
    slow = fake_target.hold_next_call()
    start = asyncio.ensure_future(controller.async_set_minutes(30))
    await slow.reached.wait()
    stop = asyncio.ensure_future(controller.async_set_minutes(0))
    hass.loop.call_soon(slow.release.set)  # after `stop` has queued behind `start`

    await asyncio.gather(start, stop)
    await hass.async_block_till_done()

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"
    assert state_of(hass, NUMBER) == "0"
    await advance(hass, freezer, hours=2)  # the report of turn_on started no timer
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_starting_again_while_the_target_is_still_switching_off(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The report of our own turn_off does not cancel a timer started after it."""
    controller = (await setup_target()).runtime_data
    await set_number(hass, NUMBER, 10)
    slow = fake_target.hold_next_call()
    stop = asyncio.ensure_future(controller.async_set_minutes(0))
    await slow.reached.wait()
    start = asyncio.ensure_future(controller.async_set_minutes(30))
    hass.loop.call_soon(slow.release.set)  # after `start` has queued behind `stop`

    await asyncio.gather(stop, start)
    await hass.async_block_till_done()

    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, NUMBER) == "30"


async def test_timer_across_dst_change(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The clocks going back in the middle of a countdown do not stretch it."""
    await hass.config.async_set_time_zone("Asia/Jerusalem")
    # 01:45 local time, still summer time: the clocks go back at 02:00.
    freezer.move_to(datetime(2026, 10, 24, 22, 45, tzinfo=UTC))
    assert dt_util.now().strftime("%H:%M") == "01:45"
    await setup_target()
    await set_number(hass, NUMBER, 30)

    await advance(hass, freezer, minutes=20)  # the wall clock reads 01:05 now
    assert state_of(hass, NUMBER) == "10"
    assert fake_target.calls == [TURN_ON]

    await advance(hass, freezer, minutes=9)
    assert fake_target.calls == [TURN_ON]

    await advance(hass, freezer, minutes=1)

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, NUMBER) == "0"


async def test_entities_attach_to_target_device(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The number lives on the target's own device; no second device appears."""
    await setup_target()

    entry = er.async_get(hass).async_get(NUMBER)

    assert entry is not None
    assert entry.device_id == fake_target.device_id
    assert len(dr.async_get(hass).devices) == 1


async def test_unloading_the_entry_leaves_the_target_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Once the integration is unloaded its countdown no longer touches the target."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 45)

    await hass.config_entries.async_unload(entry.entry_id)
    await advance(hass, freezer, minutes=60)
    await fake_target.set_state("off")

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "unavailable"


async def test_adding_time_extends_a_running_countdown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Adding time moves the end: 5 minutes left plus 30 is 35."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 15)
    await advance(hass, freezer, minutes=10)
    assert state_of(hass, NUMBER) == "5"

    await entry.runtime_data.async_add_minutes(30)

    assert state_of(hass, NUMBER) == "35"
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=34)
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=1)
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_run_in_loose_mode_switches_on_without_countdown(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """An open-ended run turns the target on and leaves the timer at zero."""
    entry = await setup_target(mode="loose")

    await entry.runtime_data.async_run()

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "0"
