"""The timer core turns commands and expiry into effects, without Home Assistant."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

import pytest

from custom_components.timerify.const import Mode
from custom_components.timerify.core import (
    Arm,
    Changed,
    Disarm,
    Snapshot,
    TimerCore,
    TurnOff,
    TurnOn,
    remaining_minutes,
)
from custom_components.timerify.domains import Actual

NOW = datetime(2026, 1, 5, 7, 0, tzinfo=UTC)


def core(mode: Mode, actual: Actual | None) -> TimerCore:
    """An idle core whose target was last seen in the given state."""
    return TimerCore(mode, timedelta(minutes=45), Snapshot(last_actual=actual))


def minutes(count: int) -> timedelta:
    return timedelta(minutes=count)


def test_set_duration_on_off_target_turns_on_and_arms() -> None:
    """Starting a countdown on an idle, switched-off target turns it on."""
    c = core("strict", "off")

    fx = c.set_duration(NOW, minutes(45))

    assert fx == [Arm(NOW + minutes(45)), TurnOn(), Changed()]
    assert c.snapshot.end == NOW + minutes(45)
    assert c.snapshot.pending == "on"


def test_set_duration_on_running_target_only_rearms() -> None:
    """A target that is already on needs no service call, only the alarm."""
    c = core("strict", "on")

    fx = c.set_duration(NOW, minutes(45))

    assert fx == [Arm(NOW + minutes(45)), Changed()]
    assert c.snapshot.pending is None


def test_set_zero_stops_and_turns_off() -> None:
    """A zero duration ends the countdown and switches the running target off."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))

    fx = c.set_duration(NOW, timedelta(0))

    assert fx == [Disarm(), TurnOff(), Changed()]
    assert c.snapshot.end is None
    assert c.snapshot.pending == "off"


def test_set_negative_duration_stops() -> None:
    """A duration below zero cannot count down, so it ends the timer like zero."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))

    assert c.set_duration(NOW, minutes(-5)) == [Disarm(), TurnOff(), Changed()]


def test_set_again_with_same_duration_changes_nothing() -> None:
    """Repeating a command that leaves the state as it was reports no change."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))

    assert Changed() not in c.set_duration(NOW, minutes(10))


def test_stop_on_idle_off_target_changes_nothing() -> None:
    """Stopping an idle timer whose target is already off does nothing visible."""
    c = core("strict", "off")

    fx = c.stop(NOW)

    assert fx == [Disarm()]
    assert c.snapshot == Snapshot(last_actual="off")


def test_add_extends_running_timer() -> None:
    """Adding time moves the end by the delta (07:05 plus 30 minutes is 07:35)."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(5))

    fx = c.add(NOW, minutes(30))

    assert fx == [Arm(NOW + minutes(35)), Changed()]
    assert c.snapshot.end == NOW + minutes(35)


def test_add_below_now_stops() -> None:
    """Taking away more time than is left ends the timer."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(5))

    fx = c.add(NOW, minutes(-10))

    assert fx == [Disarm(), TurnOff(), Changed()]
    assert c.snapshot.end is None


def test_add_exactly_the_time_left_stops() -> None:
    """Taking away exactly what is left reaches zero, which is a stop."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(5))

    assert c.add(NOW, minutes(-5)) == [Disarm(), TurnOff(), Changed()]


def test_add_on_idle_starts_timer() -> None:
    """Adding time to an idle timer starts it, as setting that duration would."""
    added = core("strict", "off")
    set_ = core("strict", "off")

    fx = added.add(NOW, minutes(30))

    assert fx == set_.set_duration(NOW, minutes(30))
    assert added.snapshot == set_.snapshot


def test_add_negative_on_idle_does_nothing() -> None:
    """There is nothing to take time from on an idle timer."""
    c = core("strict", "off")
    before = c.snapshot

    assert c.add(NOW, minutes(-10)) == []
    assert c.snapshot == before


def test_run_open_strict_uses_default_duration() -> None:
    """Strict mode has no open-ended run, so the default duration applies."""
    c = core("strict", "off")

    fx = c.run_open(NOW)

    assert fx == [Arm(NOW + minutes(45)), TurnOn(), Changed()]
    assert c.snapshot.end == NOW + minutes(45)


def test_run_open_loose_turns_on_without_countdown() -> None:
    """Loose mode turns the target on and leaves the timer at zero."""
    c = core("loose", "off")

    fx = c.run_open(NOW)

    assert fx == [Disarm(), TurnOn(), Changed()]
    assert c.snapshot.end is None


def test_run_open_loose_drops_a_running_countdown() -> None:
    """An open-ended run replaces a countdown instead of keeping its end."""
    c = core("loose", "on")
    c.set_duration(NOW, minutes(10))

    fx = c.run_open(NOW)

    assert fx == [Disarm(), Changed()]
    assert c.snapshot.end is None


def test_expire_at_end_turns_off() -> None:
    """When the alarm fires at the end time, the target is switched off."""
    c = core("strict", "on")
    c.set_duration(NOW - minutes(10), minutes(10))

    fx = c.expire(NOW)

    assert fx == [Disarm(), TurnOff(), Changed()]
    assert c.snapshot.end is None
    assert c.snapshot.pending == "off"


def test_stale_expire_is_ignored() -> None:
    """An alarm that fires before the (extended) end is a leftover and is ignored."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(5))
    before = c.snapshot

    assert c.expire(NOW) == []
    assert c.snapshot == before


def test_expire_on_idle_timer_is_ignored() -> None:
    """An alarm that fires after the timer was stopped has nothing to expire."""
    c = core("strict", "off")

    assert c.expire(NOW) == []


def test_repeated_set_while_turning_on_emits_one_turn_on() -> None:
    """A second command while the first turn-on is in flight must not repeat it."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(10))

    assert TurnOn() not in c.set_duration(NOW, minutes(20))


def test_stop_while_turn_on_in_flight_turns_off() -> None:
    """Stopping before the target reported on still switches it off."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(10))

    assert TurnOff() in c.stop(NOW)
    assert c.snapshot.pending == "off"


def test_set_while_turn_off_in_flight_turns_on() -> None:
    """Starting again before the target reported off switches it back on."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))
    c.stop(NOW)

    assert TurnOn() in c.set_duration(NOW, minutes(5))
    assert c.snapshot.pending == "on"


def test_set_while_unavailable_records_pending_without_service_call() -> None:
    """An unavailable target cannot be commanded; the wish waits for it."""
    c = core("strict", "unavailable")

    fx = c.set_duration(NOW, minutes(10))

    assert TurnOn() not in fx
    assert c.snapshot.pending == "on"


def test_expire_while_unavailable_records_pending_without_service_call() -> None:
    """An expiry during an outage clears the timer and waits to switch off."""
    c = core("strict", "unavailable")
    c.set_duration(NOW - minutes(10), minutes(10))

    fx = c.expire(NOW)

    assert TurnOff() not in fx
    assert c.snapshot.end is None
    assert c.snapshot.pending == "off"


def test_repeated_stop_while_turning_off_emits_one_turn_off() -> None:
    """A second stop while the first turn-off is in flight must not repeat it."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))
    assert TurnOff() in c.stop(NOW)

    assert TurnOff() not in c.stop(NOW)
    assert c.snapshot.pending == "off"


def test_repeated_expire_while_turning_off_emits_one_turn_off() -> None:
    """A second alarm while the first turn-off is in flight must not repeat it."""
    c = core("strict", "on")
    c.set_duration(NOW - minutes(10), minutes(10))
    assert TurnOff() in c.expire(NOW)

    assert TurnOff() not in c.expire(NOW)
    assert c.snapshot.pending == "off"


def test_add_after_an_open_run_in_loose_mode_starts_a_countdown() -> None:
    """Adding time to a target running without a countdown starts one."""
    c = core("loose", "on")
    c.run_open(NOW)

    fx = c.add(NOW, minutes(30))

    assert fx == [Arm(NOW + minutes(30)), Changed()]
    assert c.snapshot.end == NOW + minutes(30)


def test_core_resumes_from_a_stored_snapshot() -> None:
    """A snapshot restored after a restart carries on where it left off."""
    stored = Snapshot(end=NOW + minutes(5), pending="on", last_actual="on")
    c = TimerCore("strict", minutes(45), stored)

    assert c.snapshot == stored
    assert c.add(NOW, minutes(5)) == [Arm(NOW + minutes(10)), Changed()]


@pytest.mark.parametrize("mode", ["strict", "loose"])
def test_manual_off_clears_timer(mode: Mode) -> None:
    """Someone else switching the target off ends the countdown in either mode (R3)."""
    c = core(mode, "on")
    c.set_duration(NOW, minutes(10))

    fx = c.observe(NOW + minutes(1), "off", by_us=False)

    assert fx == [Disarm(), Changed()]
    assert c.snapshot == Snapshot(last_actual="off")


def test_manual_on_in_strict_starts_default_duration() -> None:
    """In strict mode a target switched on by hand gets the default countdown (R4)."""
    c = core("strict", "off")

    fx = c.observe(NOW, "on", by_us=False)

    assert fx == [Arm(NOW + minutes(45)), Changed()]
    assert c.snapshot == Snapshot(end=NOW + minutes(45), last_actual="on")


def test_manual_on_in_loose_leaves_timer_idle() -> None:
    """In loose mode a target switched on by hand just runs, with no countdown (R5)."""
    c = core("loose", "off")

    fx = c.observe(NOW, "on", by_us=False)

    assert fx == [Changed()]
    assert c.snapshot == Snapshot(last_actual="on")


def test_own_turn_on_clears_pending() -> None:
    """The target confirming our own turn-on is not a manual change (R6)."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(10))

    fx = c.observe(NOW, "on", by_us=True)

    assert fx == [Changed()]
    assert c.snapshot == Snapshot(end=NOW + minutes(10), last_actual="on")


def test_own_turn_off_clears_pending() -> None:
    """The target confirming our own turn-off settles the wish and nothing else."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))
    c.stop(NOW)

    fx = c.observe(NOW, "off", by_us=True)

    assert fx == [Changed()]
    assert c.snapshot == Snapshot(last_actual="off")


def test_late_confirmation_of_the_opposite_switch_keeps_pending() -> None:
    """A turn-off report that lands after a newer turn-on wish does not cancel it."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))
    c.stop(NOW)
    c.set_duration(NOW, minutes(5))

    c.observe(NOW, "off", by_us=True)
    assert c.snapshot.pending == "on"

    c.observe(NOW, "on", by_us=True)
    assert c.snapshot.pending is None


def test_state_update_without_a_change_does_nothing() -> None:
    """An attribute-only update repeats the state and is not a manual change."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))
    before = c.snapshot

    assert c.observe(NOW + minutes(1), "on", by_us=False) == []
    assert c.snapshot == before


def test_expired_timer_is_not_restarted_by_a_state_update() -> None:
    """The target still reads on while our turn-off is in flight; that is not R4."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))
    c.expire(NOW + minutes(10))

    fx = c.observe(NOW + minutes(10), "on", by_us=False)

    assert fx == []
    assert c.snapshot == Snapshot(pending="off", last_actual="on")


def test_observing_after_the_end_expires_the_timer_once() -> None:
    """A state change that arrives after the end applies the expiry first (rule 1)."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))

    fx = c.observe(NOW + minutes(11), "on", by_us=False)

    assert fx == [Disarm(), TurnOff(), Changed()]
    assert c.snapshot == Snapshot(pending="off", last_actual="on")


def test_manual_off_after_the_end_does_not_switch_again() -> None:
    """A target already off when the expiry is noticed needs no turn-off."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))

    fx = c.observe(NOW + minutes(11), "off", by_us=False)

    assert fx == [Disarm(), Changed()]
    assert c.snapshot == Snapshot(last_actual="off")


def test_expiry_while_unavailable_turns_off_when_back() -> None:
    """A timer that ran out during an outage switches the target off on its return."""
    c = TimerCore("strict", minutes(45), Snapshot(end=NOW, last_actual="unavailable"))

    fx = c.observe(NOW + minutes(3), "on", by_us=False)

    assert fx == [Disarm(), TurnOff(), Changed()]
    assert c.snapshot == Snapshot(pending="off", last_actual="on")


def test_expiry_while_unavailable_needs_no_turn_off_when_back_off() -> None:
    """A target that returns already off needs no switching after an outage expiry."""
    c = TimerCore("strict", minutes(45), Snapshot(end=NOW, last_actual="unavailable"))

    fx = c.observe(NOW + minutes(3), "off", by_us=False)

    assert fx == [Disarm(), Changed()]
    assert c.snapshot == Snapshot(last_actual="off")


def test_expiry_noticed_with_the_outage_waits_for_the_target() -> None:
    """An unavailable target is not switched; the turn-off waits until it reports."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))

    gone = c.observe(NOW + minutes(10), "unavailable", by_us=False)
    back = c.observe(NOW + minutes(12), "on", by_us=False)

    assert gone == [Disarm(), Changed()]
    assert c.snapshot.pending == "off"
    assert back == [TurnOff(), Changed()]


def test_set_while_unavailable_turns_on_when_back() -> None:
    """A start requested during an outage is applied when the target returns (R10)."""
    c = core("strict", "unavailable")
    c.set_duration(NOW, minutes(10))

    back = c.observe(NOW + minutes(1), "off", by_us=False)
    confirmed = c.observe(NOW + minutes(2), "on", by_us=True)

    assert back == [TurnOn(), Changed()]
    assert confirmed == [Changed()]
    assert c.snapshot == Snapshot(end=NOW + minutes(10), last_actual="on")


def test_set_while_unavailable_needs_no_turn_on_when_back_on() -> None:
    """A target that returns already on settles the wish without a service call."""
    c = core("strict", "unavailable")
    c.set_duration(NOW, minutes(10))

    fx = c.observe(NOW + minutes(1), "on", by_us=False)

    assert fx == [Changed()]
    assert c.snapshot == Snapshot(end=NOW + minutes(10), last_actual="on")


def test_wifi_drop_does_not_clear_timer() -> None:
    """Unavailable is not off: a drop and a return leave the countdown alone (R10)."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))

    gone = c.observe(NOW + minutes(1), "unavailable", by_us=False)
    back = c.observe(NOW + minutes(2), "on", by_us=False)

    assert gone == [Changed()]
    assert back == [Changed()]
    assert c.snapshot == Snapshot(end=NOW + minutes(10), last_actual="on")


def test_startup_with_running_timer_and_target_on_rearms_nothing_else() -> None:
    """After a restart a running timer on a running target needs no switching."""
    c = TimerCore("strict", minutes(45), Snapshot(end=NOW + minutes(20)))

    fx = c.observe(NOW, "on", by_us=False)

    assert fx == [Changed()]
    assert c.snapshot == Snapshot(end=NOW + minutes(20), last_actual="on")


def test_startup_target_off_with_running_timer_clears_it() -> None:
    """A target found off after a restart means the timer is over (§5.7, R3)."""
    c = TimerCore("strict", minutes(45), Snapshot(end=NOW + minutes(20)))

    fx = c.observe(NOW, "off", by_us=False)

    assert fx == [Disarm(), Changed()]
    assert c.snapshot == Snapshot(last_actual="off")


def test_startup_after_expiry_turns_off() -> None:
    """A timer that ran out while Home Assistant was down switches the target off."""
    c = TimerCore("strict", minutes(45), Snapshot(end=NOW - minutes(5)))

    fx = c.observe(NOW, "on", by_us=False)

    assert fx == [Disarm(), TurnOff(), Changed()]
    assert c.snapshot == Snapshot(pending="off", last_actual="on")


def test_startup_target_on_in_strict_starts_default_duration() -> None:
    """A strict target found on without a timer is handled as a manual turn-on."""
    c = TimerCore("strict", minutes(45), Snapshot())

    fx = c.observe(NOW, "on", by_us=False)

    assert fx == [Arm(NOW + minutes(45)), Changed()]


@pytest.mark.parametrize(
    ("pending", "actual", "expected"),
    [("on", "off", TurnOn()), ("off", "on", TurnOff())],
)
def test_startup_enforces_a_stored_pending_command(
    pending: Literal["on", "off"], actual: Actual, expected: TurnOn | TurnOff
) -> None:
    """A command that never reached the target before the restart is sent again."""
    stored = Snapshot(end=NOW + minutes(20), pending=pending)
    c = TimerCore("strict", minutes(45), stored)

    fx = c.observe(NOW, actual, by_us=False)

    assert fx == [expected, Changed()]
    assert c.snapshot == Snapshot(
        end=NOW + minutes(20), pending=pending, last_actual=actual
    )


def test_startup_with_unavailable_target_waits_for_it() -> None:
    """A target that is not there yet is not switched; the stored wish waits."""
    stored = Snapshot(end=NOW + minutes(20), pending="on")
    c = TimerCore("strict", minutes(45), stored)

    gone = c.observe(NOW, "unavailable", by_us=False)
    back = c.observe(NOW + minutes(1), "off", by_us=False)

    assert gone == [Changed()]
    assert back == [TurnOn(), Changed()]


@pytest.mark.parametrize(
    "start",
    [
        pytest.param(lambda c, now: c.set_duration(now, minutes(90)), id="set"),
        pytest.param(lambda c, now: c.add(now, minutes(90)), id="add"),
        pytest.param(lambda c, now: c.run_open(now), id="run-open"),
        pytest.param(lambda c, now: c.observe(now, "on", by_us=False), id="manual-on"),
    ],
)
def test_end_is_utc_for_a_local_time_across_a_dst_change(
    start: Callable[[TimerCore, datetime], object],
) -> None:
    """90 real minutes from 00:30 local, 01:30 before the clocks go back, is 23:00 UTC.

    Adding to a local datetime moves the wall clock, which would end an hour late.
    """
    now = datetime(2026, 10, 25, 0, 30, tzinfo=ZoneInfo("Asia/Jerusalem"))
    c = TimerCore("strict", minutes(90), Snapshot(last_actual="off"))

    start(c, now)

    assert c.snapshot.end == datetime(2026, 10, 24, 23, 0, tzinfo=UTC)
    assert c.snapshot.end.tzinfo is UTC


@pytest.mark.parametrize(
    ("end_offset", "expected"),
    [
        (timedelta(seconds=61), 2),
        (timedelta(seconds=60), 1),
        (timedelta(seconds=1), 1),
        (timedelta(0), 0),
        (timedelta(seconds=-30), 0),
        (timedelta(seconds=-61), 0),
        (None, 0),
    ],
)
def test_remaining_minutes_rounds_up(
    end_offset: timedelta | None, expected: int
) -> None:
    """The countdown shows whole minutes, rounded up, and never below zero."""
    end = None if end_offset is None else NOW + end_offset

    assert remaining_minutes(Snapshot(end=end), NOW) == expected


def test_remaining_minutes_accepts_a_local_time() -> None:
    """The caller's timezone does not matter, only the instant."""
    local = NOW.astimezone(ZoneInfo("Asia/Jerusalem"))

    assert remaining_minutes(Snapshot(end=NOW + minutes(5)), local) == 5
