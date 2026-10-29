"""Devices that do not do what they were asked, and what the timer does about it.

A device can take a command and ignore it (out of reach of its hub, a cloud that only
acknowledges), or its integration can blow up. Either way the timer must not believe
the device obeyed: the command goes out again the next time there is a chance.
"""

import logging

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant

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
