"""Devices that do not do what they were asked, and what the timer does about it.

A device can take a command and ignore it (out of reach of its hub, a cloud that only
acknowledges), or its integration can blow up. Either way the timer must not believe
the device obeyed: the command goes out again the next time there is a chance.
"""

import logging

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant

from custom_components.timerify.const import MAX_AUTOMATIC_RESENDS, Mode

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    NUMBER,
    SENSOR,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    advance,
    call_service,
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
        "switch.boiler did not turn off after 4 attempts; Timerify will not send it"
        " again until it is asked again"
    ]

    await fake_target.set_state("on", rssi=-80)
    await advance(hass, freezer, hours=1)
    await fake_target.set_state("on", rssi=-70)

    assert fake_target.calls == [TURN_ON] + [TURN_OFF] * (1 + MAX_AUTOMATIC_RESENDS)
    assert len(timerify_warnings(caplog)) == 1


async def test_unknown_then_the_old_state_is_commanded_a_limited_number_of_times(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A device that answers each refused call by dropping to `unknown` and showing its
    old state again looks like a device that goes away and comes back at every call.
    That is no new chance: Timerify asks 3 times after the first and says so once."""
    await setup_target(mode="strict")
    await set_number(hass, NUMBER, 10)
    fake_target.ignore_calls(echo_unknown=True)

    await advance(hass, freezer, minutes=10)

    assert fake_target.calls == [TURN_ON] + [TURN_OFF] * (1 + MAX_AUTOMATIC_RESENDS)
    assert state_of(hass, TARGET_ID) == "on"
    assert timerify_warnings(caplog) == [
        "switch.boiler did not turn off after 4 attempts; Timerify will not send it"
        " again until it is asked again"
    ]


async def test_refusing_device_that_keeps_dropping_off_is_not_commanded_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A device that dropped off the network and came back, again and again, after
    Timerify gave up on it, is neither commanded nor warned about a second time."""
    await setup_target(mode="strict")
    await run_into_a_refusing_device(hass, freezer, fake_target)
    calls = list(fake_target.calls)

    for _ in range(3):
        await fake_target.set_state("unavailable")
        await fake_target.set_state("on")

    assert fake_target.calls == calls
    assert len(timerify_warnings(caplog)) == 1


async def test_refusing_device_is_commanded_again_on_a_command(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """After Timerify gave up, a stop is a new request: it is sent, and a device that
    refuses it again is asked 3 times more."""
    await setup_target(mode="strict")
    await run_into_a_refusing_device(hass, freezer, fake_target)
    asked = 1 + MAX_AUTOMATIC_RESENDS
    assert fake_target.calls == [TURN_ON] + [TURN_OFF] * asked
    fake_target.obey_calls()

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


async def test_media_player_is_not_turned_on_again_by_repeated_reports(
    hass: HomeAssistant,
    fake_media_player: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A player that is slow to wake, or a toggle that a second turn_on would switch
    off again, is told once: reports that repeat its state send nothing, and the
    timer says so in the log."""
    await setup_target(target="media_player.tv")
    fake_media_player.ignore_calls()

    await set_number(hass, "number.tv_run_for", 30)

    assert fake_media_player.calls == [("turn_on", "media_player.tv")]

    for signal in range(3):
        await fake_media_player.set_state("off", signal=signal)

    assert fake_media_player.calls == [("turn_on", "media_player.tv")]
    assert timerify_warnings(caplog) == [
        "media_player.tv did not turn on after 1 attempt; Timerify will not send it"
        " again until it is asked again"
    ]

    await fake_media_player.set_state("unavailable")
    await fake_media_player.set_state("off")

    assert fake_media_player.calls == [("turn_on", "media_player.tv")]


# --- A device that reports after the call returned -----------------------------------
#
# Most cloud integrations take a command and show its result a second or two later. The
# report carries the context of the call, so Timerify knows it as its own. When the user
# changes their mind in between, the report that arrives is the opposite of what the
# timer wants, and the boiler must still end up as the timer says.


@pytest.mark.parametrize("mode", ["strict", "loose"])
async def test_run_for_zero_and_at_once_run_for_thirty_leaves_the_boiler_running(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    mode: Mode,
) -> None:
    """The boiler runs for half an hour. The user stops it and, before the cloud has
    shown it off, starts it again. The late "off" must not leave it off while the
    countdown runs: it is turned on again and goes off at the end."""
    await setup_target(mode=mode)
    await set_number(hass, NUMBER, 30)
    fake_target.report_next_call_late()
    await set_number(hass, NUMBER, 0)
    await set_number(hass, NUMBER, 30)
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "on"

    await fake_target.report_late()

    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, NUMBER) == "30"
    await advance(hass, freezer, minutes=30)
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"


async def test_start_and_at_once_stop_leave_a_strict_boiler_off(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The user starts the boiler and, before the cloud has shown it on, stops it. The
    late "on" would leave it running with the timer at zero, which strict mode forbids:
    it is turned off."""
    await setup_target(mode="strict")
    fake_target.report_next_call_late()
    await set_number(hass, NUMBER, 30)
    await set_number(hass, NUMBER, 0)
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, TARGET_ID) == "off"

    await fake_target.report_late()

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"
    assert state_of(hass, NUMBER) == "0"
    assert state_of(hass, SENSOR) == "unknown"


async def test_open_run_and_at_once_stop_leave_a_loose_boiler_off(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A loose boiler may run with the timer at zero, but the user's last word was to
    stop it: the late "on" of the open-ended run is answered with an off."""
    await setup_target(mode="loose")
    fake_target.report_next_call_late()
    await call_service(hass, "run", {"entity_id": NUMBER})
    await set_number(hass, NUMBER, 0)
    assert fake_target.calls == [TURN_ON]

    await fake_target.report_late()

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"


async def test_boiler_that_switches_itself_back_after_a_command_is_not_commanded_again(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A relay with an auto-off time of a few seconds takes the turn-on and shows it
    off again before Home Assistant stops crediting its writes to the call: both changes
    are reported as answers to our own call. The call was sent for the wish, and the
    wish was answered, so Timerify does not command the boiler at every revert."""
    await setup_target(mode="strict")
    fake_target.revert_next_calls(20)

    await set_number(hass, NUMBER, 30)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, TARGET_ID) == "off"
    assert state_of(hass, NUMBER) == "30"


async def test_late_correction_for_a_boiler_that_switches_itself_back_is_sent_once(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The user stops the boiler and starts it again before the cloud has shown it off.
    The late "off" is corrected with one turn-on; the boiler, which switches itself back
    after a command, shows off once more as an answer to that call, and is left as it
    is: a wish is corrected once."""
    await setup_target(mode="strict")
    await set_number(hass, NUMBER, 30)
    fake_target.report_next_call_late()
    await set_number(hass, NUMBER, 0)
    await set_number(hass, NUMBER, 30)
    fake_target.revert_next_calls(20)

    await fake_target.report_late()

    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]
    assert state_of(hass, TARGET_ID) == "off"


async def test_wall_switch_pressed_just_after_a_turn_on_is_not_overridden(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A switch pressed on the wall within the five seconds in which Home Assistant
    credits the entity's writes to the last call carries the context of Timerify's
    turn-on, so it looks like an answer to it. The boiler is not turned back on, not
    after the first press and not after the next."""
    await setup_target(mode="strict")
    await set_number(hass, NUMBER, 30)
    assert fake_target.calls == [TURN_ON]

    await fake_target.set_state_credited_to_last_call("off")
    await fake_target.set_state_credited_to_last_call("on")
    await fake_target.set_state_credited_to_last_call("off")

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, TARGET_ID) == "off"


async def test_boiler_that_goes_on_refusing_late_is_asked_a_limited_number_of_times(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The correction is sent like any wish: a boiler that answers each one with the
    old state, as its own, is asked 3 times more, and Timerify says so once."""
    await setup_target(mode="strict")
    await set_number(hass, NUMBER, 30)
    fake_target.report_next_call_late()
    await set_number(hass, NUMBER, 0)
    await set_number(hass, NUMBER, 30)
    fake_target.ignore_calls(echo_attribute=True)

    await fake_target.report_late()

    assert fake_target.calls == [TURN_ON, TURN_OFF] + [TURN_ON] * (
        1 + MAX_AUTOMATIC_RESENDS
    )
    assert state_of(hass, TARGET_ID) == "off"
    assert timerify_warnings(caplog) == [
        "switch.boiler did not turn on after 4 attempts; Timerify will not send it"
        " again until it is asked again"
    ]
