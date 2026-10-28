"""The timer core turns commands and expiry into effects, without Home Assistant."""

from datetime import UTC, datetime, timedelta

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


def test_core_resumes_from_a_stored_snapshot() -> None:
    """A snapshot restored after a restart carries on where it left off."""
    stored = Snapshot(end=NOW + minutes(5), pending="on", last_actual="on")
    c = TimerCore("strict", minutes(45), stored)

    assert c.snapshot == stored
    assert c.add(NOW, minutes(5)) == [Arm(NOW + minutes(10)), Changed()]


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
