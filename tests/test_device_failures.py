"""Devices that do not do what they were asked, and what the timer does about it.

A device can take a command and ignore it (out of reach of its hub, a cloud that only
acknowledges), or its integration can blow up. Either way the timer must not believe
the device obeyed: the command goes out again the next time there is a chance.
"""

import logging

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant

from custom_components.timerify.const import MAX_AUTOMATIC_RESENDS

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    NUMBER,
    SENSOR,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    advance,
    set_number,
    state_of,
    timerify_warnings,
)


async def test_ignored_turn_off_at_expiry_is_sent_again_on_the_next_report(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A boiler that did not switch off when the countdown ended is told again."""
    await setup_target(mode="strict")
    await set_number(hass, NUMBER, 10)
    fake_target.ignore_next_call()

    await advance(hass, freezer, minutes=10)

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, NUMBER) == "0"

    await fake_target.set_state("on", rssi=-80)

    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"


async def test_stop_after_an_ignored_turn_off_switches_off_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The timer shows 0 but the boiler runs: pressing stop switches it off."""
    await setup_target(mode="strict")
    await set_number(hass, NUMBER, 10)
    fake_target.ignore_next_call()
    await advance(hass, freezer, minutes=10)
    assert state_of(hass, TARGET_ID) == "on"

    await set_number(hass, NUMBER, 0)

    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"


async def test_starting_again_after_an_ignored_turn_on_switches_on_again(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The timer counts down but the target stayed off: asking again switches it on."""
    await setup_target()
    fake_target.ignore_next_call()
    await set_number(hass, NUMBER, 45)
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, TARGET_ID) == "off"

    await set_number(hass, NUMBER, 45)

    assert fake_target.calls == [TURN_ON, TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, NUMBER) == "45"


async def test_device_that_confirms_later_is_not_asked_twice(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A device that reports `on` some time after turn_on got the command in time."""
    await setup_target()
    fake_target.ignore_next_call()
    await set_number(hass, NUMBER, 45)

    await fake_target.set_state("on")

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "45"

    await fake_target.set_state("on", rssi=-80)

    assert fake_target.calls == [TURN_ON]


async def test_target_that_raises_does_not_freeze_the_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An integration that crashes on turn_off is logged, the entities move on, and
    the command is sent again on the next report."""
    await setup_target(mode="strict")
    await set_number(hass, NUMBER, 10)
    fake_target.fail_next_call(ConnectionError("The hub is unreachable"))

    await advance(hass, freezer, minutes=10)

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, NUMBER) == "0"
    assert state_of(hass, SENSOR) == "unknown"
    assert state_of(hass, TARGET_ID) == "on"
    assert "Could not turn switch.boiler off" in caplog.text
    assert "ConnectionError: The hub is unreachable" in caplog.text

    await fake_target.set_state("on", rssi=-80)

    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"


async def test_ignored_call_is_not_a_warning(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Devices that confirm later are normal, so an unconfirmed call is not noisy."""
    await setup_target()
    fake_target.ignore_next_call()

    await set_number(hass, NUMBER, 45)

    noisy = [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("custom_components.timerify")
        and record.levelno >= logging.WARNING
    ]
    assert noisy == []


async def run_into_a_refusing_device(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, fake_target: FakeTarget
) -> None:
    """A boiler timer ends, and the boiler refuses turn_off while it reports its
    unchanged state, with a new attribute, in answer to every call."""
    await set_number(hass, NUMBER, 10)
    fake_target.ignore_calls(echo_attribute=True)
    await advance(hass, freezer, minutes=10)


async def test_device_that_refuses_and_echoes_is_commanded_a_limited_number_of_times(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The answer of a refusing device must not set off the next command: Timerify
    asks 3 times after the first, says so once, and then leaves the device alone."""
    await setup_target(mode="strict")

    await run_into_a_refusing_device(hass, freezer, fake_target)

    assert fake_target.calls == [TURN_ON] + [TURN_OFF] * (1 + MAX_AUTOMATIC_RESENDS)
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, NUMBER) == "0"
    assert timerify_warnings(caplog) == [
        "switch.boiler did not turn off after 4 attempts; Timerify will try again"
        " when it reports a change or on the next command"
    ]

    await fake_target.set_state("on", rssi=-80)
    await advance(hass, freezer, hours=1)
    await fake_target.set_state("on", rssi=-70)

    assert fake_target.calls == [TURN_ON] + [TURN_OFF] * (1 + MAX_AUTOMATIC_RESENDS)
    assert len(timerify_warnings(caplog)) == 1


@pytest.mark.parametrize("what_happens", ["it_comes_back", "stop"])
async def test_refusing_device_is_commanded_again_when_it_changes_or_on_a_command(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    what_happens: str,
) -> None:
    """After Timerify gave up, a change of the device's state or a stop reaches it."""
    await setup_target(mode="strict")
    await run_into_a_refusing_device(hass, freezer, fake_target)
    asked = 1 + MAX_AUTOMATIC_RESENDS
    assert fake_target.calls == [TURN_ON] + [TURN_OFF] * asked
    fake_target.obey_calls()

    if what_happens == "it_comes_back":
        await fake_target.set_state("unavailable")
        await fake_target.set_state("on")
    else:
        await set_number(hass, NUMBER, 0)

    assert fake_target.calls == [TURN_ON] + [TURN_OFF] * (asked + 1)
    assert state_of(hass, TARGET_ID) == "off"


async def test_service_that_keeps_raising_logs_its_traceback_once_per_wish(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A bug in the target's integration is shown in full the first time, then as a
    line for each retry; a later wish that fails again gets the traceback again."""
    await setup_target(mode="strict")
    await set_number(hass, NUMBER, 10)
    fake_target.fail_next_call(ConnectionError("The hub is unreachable"))
    await advance(hass, freezer, minutes=10)
    fake_target.fail_next_call(ConnectionError("The hub is unreachable"))

    await fake_target.set_state("on", rssi=-80)

    tracebacks = [record for record in caplog.records if record.exc_info]
    assert len(tracebacks) == 1
    assert timerify_warnings(caplog)[-1] == (
        "Could not turn switch.boiler off: its service raised"
        " ConnectionError('The hub is unreachable') again"
    )
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_OFF]

    await fake_target.set_state("on", rssi=-70)
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_OFF, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"

    await set_number(hass, NUMBER, 10)
    fake_target.fail_next_call(ConnectionError("The hub is unreachable"))
    await advance(hass, freezer, minutes=10)

    assert len([record for record in caplog.records if record.exc_info]) == 2
