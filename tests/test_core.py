"""The timer core turns commands and expiry into effects, without Home Assistant."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

import pytest

from custom_components.timerify.const import (
    MAX_AUTOMATIC_RESENDS,
    MAX_MINUTES,
    NO_SETTINGS,
    Mode,
    Settings,
    freeze_settings,
)
from custom_components.timerify.core import (
    ApplySettings,
    Arm,
    Changed,
    Command,
    CommandCameDue,
    CommandDropped,
    CountdownEnded,
    CountdownStarted,
    Disarm,
    Effect,
    GaveUp,
    Snapshot,
    TimerCore,
    TurnOff,
    TurnOn,
    Window,
    next_wakeup,
    remaining_minutes,
)
from custom_components.timerify.domains import Actual

NOW = datetime(2026, 1, 5, 7, 0, tzinfo=UTC)
COOL24 = freeze_settings({"hvac_mode": "cool", "temperature": 24.0})
HEAT22 = freeze_settings({"hvac_mode": "heat", "temperature": 22.0})


def core(mode: Mode, actual: Actual | None) -> TimerCore:
    """An idle core whose target was last seen in the given state."""
    return TimerCore(mode, timedelta(minutes=45), Snapshot(last_actual=actual))


def minutes(count: int) -> timedelta:
    return timedelta(minutes=count)


def cmd(
    minutes_from_now: int,
    action: Literal["on", "off"] = "on",
    minutes: int | None = None,
    settings: Settings = NO_SETTINGS,
    id: str = "c1",
) -> Command:
    """A pending command due `minutes_from_now` minutes after `NOW`; negative: late."""
    at = NOW + timedelta(minutes=minutes_from_now)
    return Command(id, at, action, minutes, settings)


def window(
    interval_id: str,
    start_minutes: int,
    end_minutes: int,
    settings: Settings = NO_SETTINGS,
    started: bool = False,
    suppressed: bool = False,
) -> Window:
    """A window of an interval that opens `start_minutes` after `NOW` and closes
    `end_minutes` after it; negative: before."""
    return Window(
        interval_id,
        NOW + timedelta(minutes=start_minutes),
        NOW + timedelta(minutes=end_minutes),
        settings,
        started,
        suppressed,
    )


def holding(
    mode: Mode,
    actual: Actual | None,
    *commands: Command,
    end: datetime | None = None,
) -> TimerCore:
    """A core that waits for `commands` (in order of time), as one restored from the
    store does, with its target last seen in the given state."""
    return TimerCore(
        mode,
        timedelta(minutes=45),
        Snapshot(end=end, commands=commands, last_actual=actual),
    )


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


def test_add_cannot_take_the_timer_past_a_day() -> None:
    """The time left never exceeds a day, counted from now and not from the old end."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(1000))
    later = NOW + minutes(10)

    fx = c.add(later, minutes(1000))

    assert fx == [Arm(later + minutes(MAX_MINUTES)), Changed()]
    assert c.snapshot.end == later + minutes(MAX_MINUTES)


def test_add_to_a_full_day_changes_nothing() -> None:
    """A timer that already has a day left keeps its end and is not saved again."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(MAX_MINUTES))
    before = c.snapshot

    fx = c.add(NOW, minutes(100))

    assert fx == [Arm(NOW + minutes(MAX_MINUTES))]
    assert c.snapshot == before


def test_add_on_idle_is_capped_at_a_day() -> None:
    """Starting a timer by adding more than a day gives it a day."""
    c = core("strict", "off")

    c.add(NOW, minutes(MAX_MINUTES + 100))

    assert c.snapshot.end == NOW + minutes(MAX_MINUTES)


def test_set_duration_is_capped_at_a_day() -> None:
    """No command can start a countdown longer than a day."""
    c = core("strict", "off")

    c.set_duration(NOW, minutes(MAX_MINUTES + 100))

    assert c.snapshot.end == NOW + minutes(MAX_MINUTES)


def test_add_negative_on_idle_does_nothing() -> None:
    """There is nothing to take time from on an idle timer."""
    c = core("strict", "off")
    before = c.snapshot

    assert c.add(NOW, minutes(-10)) == []
    assert c.snapshot == before


@pytest.mark.parametrize("ended", [-40, -10, 0])
def test_add_to_a_countdown_that_has_ended_counts_from_now(ended: int) -> None:
    """An end that is not ahead is no countdown, as `wanted_running` judges it, though
    nothing folded it yet (start-up has not taken stock): adding time starts one from
    now, as on an idle timer."""
    stale = Snapshot(end=NOW + minutes(ended), started_at=NOW - minutes(70))
    c = TimerCore("strict", minutes(45), stale)
    idle = TimerCore("strict", minutes(45), Snapshot())

    fx = c.add(NOW, minutes(30))

    assert fx == idle.add(NOW, minutes(30))
    assert c.snapshot == idle.snapshot


def test_add_negative_to_a_countdown_that_has_ended_does_nothing() -> None:
    """There is no time to take from a countdown that is over; what folds it later
    still does."""
    c = TimerCore("strict", minutes(45), Snapshot(end=NOW - minutes(10)))
    before = c.snapshot

    assert c.add(NOW, minutes(-5)) == []
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


@pytest.mark.parametrize("mode", ["strict", "loose"])
def test_run_open_keeps_a_running_countdown(mode: Mode) -> None:
    """R9 starts a target that is off. A target the timer already wants running is
    left as it is, in either mode: the countdown keeps its end, and nothing is sent."""
    c = core(mode, "on")
    c.set_duration(NOW, minutes(120))

    fx = c.run_open(NOW + minutes(10))

    assert fx == []
    assert c.snapshot.end == NOW + minutes(120)


def test_run_open_loose_keeps_a_run_without_a_countdown() -> None:
    """A target that runs without a countdown is wanted running: nothing changes."""
    c = core("loose", "off")
    c.run_open(NOW)
    c.observe(NOW + minutes(1), "on", by_us=True)

    fx = c.run_open(NOW + minutes(10))

    assert fx == []
    assert c.snapshot.end is None


def test_run_open_leaves_the_schedule_in_charge_of_its_countdown() -> None:
    """A run that changes nothing is not a change of the timer (S3): the interval whose
    window end the timer carries still owns it, and an edit of it still realigns."""
    c = core("strict", "on")
    c.set_windows(NOW, [window("x", -30, 180)], configured={"x"})
    c.tick(NOW)

    fx = c.run_open(NOW + minutes(10))
    c.set_windows(NOW + minutes(10), [window("x", -30, 60)], configured={"x"})
    c.tick(NOW + minutes(10))

    assert fx == []
    assert c.snapshot.end == NOW + minutes(60)
    assert c.snapshot.scheduled_by == "x"


def test_run_open_waits_with_a_wish_that_has_not_reached_the_target() -> None:
    """A turn-on that did not go through is wanted, so a bare turn-on sends it again
    and leaves the countdown where it was."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(30))
    c.call_failed(NOW)

    fx = c.run_open(NOW + minutes(5))

    assert fx == [TurnOn()]
    assert c.snapshot.end == NOW + minutes(30)


@pytest.mark.parametrize("mode", ["strict", "loose"])
def test_run_open_after_the_countdown_ran_out_starts_it_again(mode: Mode) -> None:
    """A countdown that ran out is over, whether or not its alarm was handled yet: a
    command that gets its turn first meets a target that is about to be turned off,
    which is R9's."""
    c = core(mode, "on")
    c.set_duration(NOW, minutes(10))

    fx = c.run_open(NOW + minutes(11))

    if mode == "strict":
        assert fx == [Arm(NOW + minutes(56)), Changed()]
        assert c.snapshot.end == NOW + minutes(56)
    else:
        assert fx == [Disarm(), Changed()]
        assert c.snapshot.end is None
    assert c.tick(NOW + minutes(11)) == []


def test_run_open_with_settings_on_a_running_countdown_sets_only_the_settings() -> None:
    """The settings of a bare turn-on still go to a target that runs (P1); its
    countdown is not what they are for."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(120))

    fx = c.run_open(NOW + minutes(10), COOL24)

    assert fx == [ApplySettings(COOL24), Changed()]
    assert c.snapshot.end == NOW + minutes(120)


def test_tick_at_end_turns_off() -> None:
    """When the alarm fires at the end time, the target is switched off."""
    c = core("strict", "on")
    c.set_duration(NOW - minutes(10), minutes(10))

    fx = c.tick(NOW)

    assert fx == [Disarm(), TurnOff(), Changed()]
    assert c.snapshot.end is None
    assert c.snapshot.pending == "off"


def test_stale_tick_is_ignored() -> None:
    """An alarm that fires before the (extended) end is a leftover and is ignored."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(5))
    before = c.snapshot

    assert c.tick(NOW) == []
    assert c.snapshot == before


def test_tick_on_idle_timer_is_ignored() -> None:
    """An alarm that fires after the timer was stopped has nothing to expire."""
    c = core("strict", "off")

    assert c.tick(NOW) == []


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


def test_tick_at_end_while_unavailable_records_pending_without_service_call() -> None:
    """An expiry during an outage clears the timer and waits to switch off."""
    c = core("strict", "unavailable")
    c.set_duration(NOW - minutes(10), minutes(10))

    fx = c.tick(NOW)

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


def test_repeated_tick_at_end_while_turning_off_emits_one_turn_off() -> None:
    """A second alarm while the first turn-off is in flight must not repeat it."""
    c = core("strict", "on")
    c.set_duration(NOW - minutes(10), minutes(10))
    assert TurnOff() in c.tick(NOW)

    assert TurnOff() not in c.tick(NOW)
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
    assert c.snapshot == Snapshot(
        end=NOW + minutes(45), started_at=NOW, last_actual="on"
    )


def test_manual_on_in_loose_leaves_timer_idle() -> None:
    """In loose mode a target switched on by hand just runs, with no countdown (R5),
    unless a window is open
    (`test_manual_on_in_loose_during_a_window_gets_a_countdown_to_its_end`)."""
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
    assert c.snapshot == Snapshot(
        end=NOW + minutes(10), started_at=NOW, last_actual="on"
    )


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
    c.tick(NOW + minutes(10))

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
    assert c.snapshot == Snapshot(
        end=NOW + minutes(10), started_at=NOW, last_actual="on"
    )


def test_set_while_unavailable_needs_no_turn_on_when_back_on() -> None:
    """A target that returns already on settles the wish without a service call."""
    c = core("strict", "unavailable")
    c.set_duration(NOW, minutes(10))

    fx = c.observe(NOW + minutes(1), "on", by_us=False)

    assert fx == [Changed()]
    assert c.snapshot == Snapshot(
        end=NOW + minutes(10), started_at=NOW, last_actual="on"
    )


def test_wifi_drop_does_not_clear_timer() -> None:
    """Unavailable is not off: a drop and a return leave the countdown alone (R10)."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))

    gone = c.observe(NOW + minutes(1), "unavailable", by_us=False)
    back = c.observe(NOW + minutes(2), "on", by_us=False)

    assert gone == [Changed()]
    assert back == [Changed()]
    assert c.snapshot == Snapshot(
        end=NOW + minutes(10), started_at=NOW, last_actual="on"
    )


def test_expiry_noticed_with_a_manual_on_does_not_start_a_new_timer() -> None:
    """The turn-off that follows the expiry outranks a manual on seen with it."""
    c = TimerCore(
        "strict",
        minutes(45),
        Snapshot(end=NOW, pending="on", last_actual="off"),
    )

    fx = c.observe(NOW + minutes(1), "on", by_us=False)

    assert fx == [Disarm(), TurnOff(), Changed()]
    assert c.snapshot == Snapshot(pending="off", last_actual="on")


def test_startup_after_expiry_needs_no_turn_off_for_a_target_already_off() -> None:
    """A wish that expired unsent is dropped when the target already shows off."""
    c = TimerCore("strict", minutes(45), Snapshot(end=NOW, pending="on"))

    fx = c.observe(NOW + minutes(1), "off", by_us=False)

    assert fx == [Disarm(), Changed()]
    assert c.snapshot == Snapshot(last_actual="off")


def test_failed_turn_on_is_sent_again_when_the_target_reports() -> None:
    """A rejected turn-on is retried by the next report of a target still off."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(10))
    assert c.call_failed(NOW) == []

    fx = c.observe(NOW + minutes(1), "off", by_us=False)

    assert fx == [TurnOn()]
    assert c.snapshot.pending == "on"


def test_failed_turn_on_is_sent_again_only_once() -> None:
    """Once resent, the turn-on is in flight again and further reports leave it."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(10))
    c.call_failed(NOW)
    c.observe(NOW + minutes(1), "off", by_us=False)

    assert c.observe(NOW + minutes(2), "off", by_us=False) == []


def test_failed_turn_on_is_sent_again_by_the_next_command() -> None:
    """Setting the timer again after a rejected turn-on tries the target again."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(10))
    c.call_failed(NOW)

    fx = c.set_duration(NOW + minutes(1), minutes(20))

    assert fx == [Arm(NOW + minutes(21)), TurnOn(), Changed()]


def test_failed_turn_off_is_sent_again_when_the_target_reports() -> None:
    """A rejected turn-off is retried by the next report of a target still on."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))
    c.stop(NOW)
    c.call_failed(NOW)

    fx = c.observe(NOW + minutes(1), "on", by_us=False)

    assert fx == [TurnOff()]
    assert c.snapshot.pending == "off"


def test_turn_on_in_flight_is_not_repeated_by_a_state_report() -> None:
    """A report queued behind the call (attributes, same state) must not repeat it."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(10))

    assert c.observe(NOW + minutes(1), "off", by_us=False) == []


def test_stop_after_a_failed_turn_on_needs_no_turn_off() -> None:
    """A turn-on that never reached the target leaves nothing to switch back."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(10))
    c.call_failed(NOW)

    fx = c.stop(NOW + minutes(1))

    assert fx == [Disarm(), Changed()]
    assert c.snapshot == Snapshot(last_actual="off")


def test_failed_turn_on_waits_for_an_unavailable_target() -> None:
    """The retry waits for the target to report a usable state."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(10))
    c.call_failed(NOW)

    gone = c.observe(NOW + minutes(1), "unavailable", by_us=False)
    back = c.observe(NOW + minutes(2), "off", by_us=False)

    assert gone == [Changed()]
    assert back == [TurnOn(), Changed()]


def test_target_found_on_after_a_failed_turn_on_settles_it() -> None:
    """If the target ended up on anyway, there is nothing left to send."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(10))
    c.call_failed(NOW)

    fx = c.observe(NOW + minutes(1), "on", by_us=False)

    assert fx == [Changed()]
    assert c.snapshot == Snapshot(
        end=NOW + minutes(10), started_at=NOW, last_actual="on"
    )


def test_call_failed_without_a_pending_wish_changes_nothing() -> None:
    """A failure report with nothing pending must not make a later wish look unsent."""
    c = core("strict", "off")
    assert c.call_failed(NOW) == []

    c.set_duration(NOW, minutes(10))

    assert c.observe(NOW + minutes(1), "off", by_us=False) == []


def refused_turn_off() -> TimerCore:
    """A running timer stopped, and a target that stays on although it took turn_off:
    the call has been made and reported as not delivered."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))
    c.stop(NOW)
    c.call_failed(NOW)
    return c


def repeat_reports(
    c: TimerCore,
    count: int,
    actual: Actual = "on",
    *,
    by_us: bool = False,
    since: timedelta = timedelta(0),
) -> list[list[Effect]]:
    """The effects of `count` reports in a row that repeat the target's state, from a
    device that refuses every call: each send comes back as not delivered. They are
    answers to our own calls if `by_us`. The first is a minute after `since`, counted
    from `NOW`."""
    results: list[list[Effect]] = []
    for step in range(count):
        now = NOW + since + minutes(1 + step)
        effects = c.observe(now, actual, by_us=by_us)
        if any(isinstance(e, TurnOn | TurnOff | ApplySettings) for e in effects):
            c.call_failed(now)
        results.append(effects)
    return results


def test_repeated_reports_send_a_refused_wish_a_limited_number_of_times() -> None:
    """A target that keeps showing the old state is asked 3 times by its reports,
    told so once, and left alone after that."""
    c = refused_turn_off()

    reports = repeat_reports(c, MAX_AUTOMATIC_RESENDS + 3)

    assert reports[:MAX_AUTOMATIC_RESENDS] == [[TurnOff()]] * MAX_AUTOMATIC_RESENDS
    assert reports[MAX_AUTOMATIC_RESENDS] == [GaveUp("off")]
    assert reports[MAX_AUTOMATIC_RESENDS + 1 :] == [[], []]
    assert c.snapshot.pending == "off"


def test_a_target_that_comes_back_gets_no_new_allowance_for_the_same_wish() -> None:
    """A target that went away and came back is not a new chance: Timerify gave up on
    the wish, and it is not sent again until it is asked again."""
    c = refused_turn_off()
    repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)

    c.observe(NOW + minutes(10), "unavailable", by_us=False)
    back = c.observe(NOW + minutes(11), "on", by_us=False)

    assert back == [Changed()]
    assert repeat_reports(c, 2) == [[], []]
    assert c.snapshot.pending == "off"


def test_unknown_then_the_old_state_is_asked_a_limited_number_of_times() -> None:
    """A device that answers each refused call with `unknown` and then the state it
    had is a target that goes away and comes back at every call. It is still asked a
    limited number of times, and told so once."""
    c = refused_turn_off()
    sent: list[Effect] = []
    for cycle in range(10):
        at = NOW + minutes(1 + 2 * cycle)
        c.observe(at, "unavailable", by_us=True)
        effects = c.observe(at + minutes(1), "on", by_us=True)
        if any(isinstance(e, TurnOff) for e in effects):
            c.call_failed(at + minutes(1))
        sent += [e for e in effects if isinstance(e, TurnOff | GaveUp)]

    assert sent == [TurnOff()] * MAX_AUTOMATIC_RESENDS + [GaveUp("off")]
    assert c.snapshot.pending == "off"


def test_the_first_report_after_a_start_gives_a_full_allowance() -> None:
    """A stored wish found unsent at start-up is sent, then limited like any other."""
    c = TimerCore("strict", minutes(45), Snapshot(end=None, pending="off"))

    start = c.observe(NOW, "on", by_us=False)
    c.call_failed(NOW)
    again = repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)

    assert start == [TurnOff(), Changed()]
    assert again == [[TurnOff()]] * MAX_AUTOMATIC_RESENDS + [[GaveUp("off")]]


def test_a_wish_made_while_away_is_delivered_on_return_and_then_limited() -> None:
    """The first delivery of a wish that waited for the target costs no re-send; the
    re-sends after it are limited like any other."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))
    c.observe(NOW + minutes(1), "unavailable", by_us=False)
    assert TurnOff() not in c.stop(NOW + minutes(2))

    back = c.observe(NOW + minutes(3), "on", by_us=False)
    assert TurnOff() in back
    c.call_failed(NOW + minutes(3))
    again = repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)

    assert again == [[TurnOff()]] * MAX_AUTOMATIC_RESENDS + [[GaveUp("off")]]


def test_a_command_wanting_the_same_wish_always_sends_and_gives_a_full_allowance() -> (
    None
):
    """Stop after the core gave up sends turn_off again, and it may be repeated."""
    c = refused_turn_off()
    repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)

    stop = c.stop(NOW + minutes(10))
    c.call_failed(NOW + minutes(10))
    again = repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)

    assert stop == [Disarm(), TurnOff()]
    assert again == [[TurnOff()]] * MAX_AUTOMATIC_RESENDS + [[GaveUp("off")]]


def test_a_wish_in_the_other_direction_replaces_the_one_given_up() -> None:
    """After giving up on turn_off, starting the timer needs no call (the target is
    on), and stopping it again is a new wish with its own allowance."""
    c = refused_turn_off()
    repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)

    start = c.set_duration(NOW + minutes(10), minutes(20))
    stop = c.stop(NOW + minutes(11))
    c.call_failed(NOW + minutes(11))
    again = repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)

    assert TurnOn() not in start
    assert c.snapshot.pending == "off"
    assert stop == [Disarm(), TurnOff(), Changed()]
    assert again == [[TurnOff()]] * MAX_AUTOMATIC_RESENDS + [[GaveUp("off")]]


def test_the_end_of_a_new_countdown_sends_the_turn_off_after_a_give_up() -> None:
    """The timer switching the target itself is new work, not a report: a countdown
    that ends is turned off, and a device that refuses it is asked 3 times again."""
    c = refused_turn_off()
    repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)
    c.set_duration(NOW + minutes(10), minutes(20))

    ended = c.tick(NOW + minutes(30))
    c.call_failed(NOW + minutes(30))
    again = repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)

    assert TurnOff() in ended
    assert again == [[TurnOff()]] * MAX_AUTOMATIC_RESENDS + [[GaveUp("off")]]


def test_the_start_of_a_window_sends_the_turn_on_after_a_give_up() -> None:
    """A schedule interval that starts is new work for the target too."""
    c = core("loose", "off")
    c.run_open(NOW)
    c.call_failed(NOW)
    gave_up = repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1, actual="off")
    assert gave_up[-1] == [GaveUp("on")]
    c.set_windows(NOW, [window("a", 10, 40)], configured={"a"})

    opened = c.tick(NOW + minutes(10))
    c.call_failed(NOW + minutes(10))
    again = repeat_reports(
        c, MAX_AUTOMATIC_RESENDS + 1, actual="off", since=minutes(10)
    )

    assert TurnOn() in opened
    assert again == [[TurnOn()]] * MAX_AUTOMATIC_RESENDS + [[GaveUp("on")]]


def test_a_settled_wish_leaves_the_next_one_a_full_allowance() -> None:
    """The target finally obeys; the next refused wish is asked 3 times again."""
    c = refused_turn_off()
    repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)
    c.observe(NOW + minutes(10), "off", by_us=False)
    assert c.snapshot.pending is None

    c.set_duration(NOW + minutes(11), minutes(5))
    c.call_failed(NOW + minutes(11))
    again = repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1, actual="off")

    assert again == [[TurnOn()]] * MAX_AUTOMATIC_RESENDS + [[GaveUp("on")]]


def test_startup_with_running_timer_and_target_on_rearms_nothing_else() -> None:
    """After a restart a running timer on a running target needs no switching.

    Arming the alarm for the stored end is the controller's job, not an effect here.
    """
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


def owing(mode: Mode, actual: Actual | None) -> TimerCore:
    """A core whose target was last seen as given and that was asked, for an hour,
    to run with `COOL24`; the effects of that command are dropped."""
    c = core(mode, actual)
    c.set_duration(NOW, minutes(60), COOL24)
    return c


def test_settings_ride_with_turn_on() -> None:
    """A target that is off gets its settings in the very call that turns it on."""
    c = core("strict", "off")

    fx = c.set_duration(NOW, minutes(60), COOL24)

    assert fx == [Arm(NOW + minutes(60)), TurnOn(COOL24), Changed()]
    assert c.snapshot.owed_settings == COOL24


def test_settings_on_running_target_are_applied() -> None:
    """A target that already runs is not turned on, but the settings are still set."""
    c = core("strict", "on")

    fx = c.set_duration(NOW, minutes(60), COOL24)

    assert fx == [Arm(NOW + minutes(60)), ApplySettings(COOL24), Changed()]
    assert c.snapshot.owed_settings == COOL24


def test_loose_open_run_with_settings_on_running_target_applies_them() -> None:
    """Running without a countdown on a target that is on still sets the settings."""
    c = core("loose", "on")

    fx = c.run_open(NOW, COOL24)

    assert fx == [ApplySettings(COOL24), Changed()]


def test_strict_open_run_carries_settings_with_the_default_duration() -> None:
    """The default duration and the settings are one command."""
    c = core("strict", "off")

    fx = c.run_open(NOW, COOL24)

    assert fx == [Arm(NOW + minutes(45)), TurnOn(COOL24), Changed()]


def test_settings_with_a_zero_duration_are_not_owed() -> None:
    """A command that ends the timer has nothing to turn on, so it keeps no settings."""
    c = core("strict", "on")

    fx = c.set_duration(NOW, timedelta(0), COOL24)

    assert fx == [Disarm(), TurnOff(), Changed()]
    assert c.snapshot.owed_settings == NO_SETTINGS


def test_settings_applied_clears_them() -> None:
    """Once the target took the settings nothing is owed any more."""
    c = owing("strict", "on")

    fx = c.settings_applied(NOW)

    assert fx == [Changed()]
    assert c.snapshot.owed_settings == NO_SETTINGS
    assert c.observe(NOW + minutes(1), "on", by_us=False) == []


def test_settings_in_flight_are_not_sent_by_a_report() -> None:
    """A report that arrives while the settings are on their way sends nothing."""
    c = owing("strict", "off")

    assert c.observe(NOW + minutes(1), "off", by_us=False) == []


def test_failed_settings_are_resent_on_next_report() -> None:
    """Settings the target refused go out again when it next reports."""
    c = owing("strict", "on")
    c.call_failed(NOW)

    fx = c.observe(NOW + minutes(1), "on", by_us=False)

    assert fx == [ApplySettings(COOL24)]
    assert c.snapshot.owed_settings == COOL24


def test_failed_settings_are_resent_by_the_next_command() -> None:
    """Asking again for the same timer tries the settings again."""
    c = owing("strict", "on")
    c.call_failed(NOW)

    fx = c.set_duration(NOW + minutes(1), minutes(30))

    assert fx == [Arm(NOW + minutes(31)), ApplySettings(COOL24), Changed()]


def test_failed_turn_on_resends_settings_with_it() -> None:
    """A turn-on that did not reach the target takes the settings along again."""
    c = owing("strict", "off")
    c.call_failed(NOW)

    fx = c.observe(NOW + minutes(1), "off", by_us=False)

    assert fx == [TurnOn(COOL24)]


def test_turn_on_that_took_but_not_its_settings_resends_only_the_settings() -> None:
    """The target is on now, so the settings alone are sent."""
    c = owing("strict", "off")
    c.call_failed(NOW)

    fx = c.observe(NOW + minutes(1), "on", by_us=True)

    assert fx == [ApplySettings(COOL24), Changed()]
    assert c.snapshot.pending is None


def test_settings_wait_for_unavailable_target() -> None:
    """Nothing is sent to a target that is away; it gets the turn-on and the
    settings together when it is back."""
    c = core("strict", "unavailable")

    asked = c.set_duration(NOW, minutes(60), COOL24)
    back = c.observe(NOW + minutes(1), "off", by_us=False)

    assert asked == [Arm(NOW + minutes(60)), Changed()]
    assert back == [TurnOn(COOL24), Changed()]


def test_settings_wait_for_unavailable_target_that_comes_back_on() -> None:
    """A target that returns already running needs the settings alone."""
    c = core("strict", "unavailable")
    c.set_duration(NOW, minutes(60), COOL24)

    back = c.observe(NOW + minutes(1), "on", by_us=False)

    assert back == [ApplySettings(COOL24), Changed()]
    assert c.snapshot.pending is None


def test_settings_wait_while_a_running_target_drops_off() -> None:
    """A running target that is away when asked gets the settings once it is back."""
    c = core("strict", "unavailable")
    c.set_duration(NOW, minutes(10))
    c.observe(NOW, "on", by_us=False)
    c.observe(NOW, "unavailable", by_us=False)

    assert c.set_duration(NOW, minutes(60), COOL24) == [
        Arm(NOW + minutes(60)),
        Changed(),
    ]
    assert c.observe(NOW, "on", by_us=False) == [ApplySettings(COOL24), Changed()]


def test_settings_wait_while_a_turn_on_in_flight_loses_the_target() -> None:
    """A turn-on on its way does not reach a target that drops off meanwhile; the
    settings wait for it as the turn-on does."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(10))
    c.observe(NOW, "unavailable", by_us=False)

    asked = c.set_duration(NOW, minutes(60), COOL24)
    back = c.observe(NOW + minutes(1), "on", by_us=False)

    assert asked == [Arm(NOW + minutes(60)), Changed()]
    assert back == [ApplySettings(COOL24), Changed()]


def test_settings_while_turn_on_in_flight_are_applied() -> None:
    """A turn-on that is already on its way is not repeated; the settings follow."""
    c = core("strict", "off")
    assert c.set_duration(NOW, minutes(10)) == [
        Arm(NOW + minutes(10)),
        TurnOn(),
        Changed(),
    ]

    fx = c.set_duration(NOW, minutes(60), COOL24)

    assert fx == [Arm(NOW + minutes(60)), ApplySettings(COOL24), Changed()]


def test_newer_settings_replace_owed() -> None:
    """Of two commands that wait for the target, the later one's settings count."""
    c = core("strict", "unavailable")
    c.set_duration(NOW, minutes(60), COOL24)
    heat = freeze_settings({"hvac_mode": "heat"})

    c.set_duration(NOW, minutes(60), heat)

    assert c.snapshot.owed_settings == heat
    assert c.observe(NOW, "off", by_us=False) == [TurnOn(heat), Changed()]


def test_command_without_settings_keeps_owed() -> None:
    """A plain command neither invents settings nor drops those that are owed."""
    c = core("strict", "unavailable")
    c.set_duration(NOW, minutes(60), COOL24)

    c.set_duration(NOW, minutes(30))

    assert c.snapshot.owed_settings == COOL24
    assert c.observe(NOW, "off", by_us=False) == [TurnOn(COOL24), Changed()]


def test_manual_off_drops_owed_settings() -> None:
    """Someone switching the target off ends the timer and what it was to run with."""
    c = owing("strict", "on")
    c.call_failed(NOW)

    fx = c.observe(NOW + minutes(1), "off", by_us=False)

    assert fx == [Disarm(), Changed()]
    assert c.snapshot.owed_settings == NO_SETTINGS
    assert c.snapshot.end is None


@pytest.mark.parametrize(
    "ending",
    [
        pytest.param(lambda c, now: c.stop(now), id="stop"),
        pytest.param(lambda c, now: c.set_duration(now, timedelta(0)), id="zero"),
        pytest.param(lambda c, now: c.tick(now + minutes(60)), id="expiry"),
    ],
)
def test_every_end_of_the_timer_drops_owed_settings(
    ending: Callable[[TimerCore, datetime], object],
) -> None:
    """A timer that stops runs with nothing: its settings are not applied later."""
    c = owing("strict", "unavailable")

    ending(c, NOW + minutes(1))

    assert c.snapshot.owed_settings == NO_SETTINGS
    assert c.snapshot.pending == "off"
    assert c.observe(NOW + minutes(70), "on", by_us=False) == [TurnOff(), Changed()]


def test_manual_on_pushes_no_settings() -> None:
    """Someone else switching the target on starts the default timer, nothing more."""
    c = core("strict", "off")

    fx = c.observe(NOW, "on", by_us=False)

    assert fx == [Arm(NOW + minutes(45)), Changed()]
    assert c.snapshot.owed_settings == NO_SETTINGS


def test_restored_owed_settings_are_resent() -> None:
    """Settings owed when Home Assistant stopped are sent on the first report."""
    c = TimerCore(
        "strict", minutes(45), Snapshot(end=NOW + minutes(30), owed_settings=COOL24)
    )

    fx = c.observe(NOW, "on", by_us=False)

    assert fx == [ApplySettings(COOL24), Changed()]


def test_restored_owed_settings_wait_for_an_unavailable_target() -> None:
    """A target that is not there at start-up gets them when it is."""
    c = TimerCore(
        "strict", minutes(45), Snapshot(end=NOW + minutes(30), owed_settings=COOL24)
    )

    assert c.observe(NOW, "unavailable", by_us=False) == [Changed()]
    assert c.observe(NOW + minutes(1), "on", by_us=False) == [
        ApplySettings(COOL24),
        Changed(),
    ]


def test_a_command_before_the_first_report_is_sent_by_that_report() -> None:
    """Nothing is known of a target that has not reported yet, so it is treated as one
    that is away: the wish and its settings are recorded, and go out with the first
    report."""
    c = TimerCore("strict", minutes(45), Snapshot())

    fx = c.set_duration(NOW, minutes(30), COOL24)

    assert not [e for e in fx if isinstance(e, TurnOn | TurnOff | ApplySettings)]
    assert c.snapshot.pending == "on"
    assert c.snapshot.owed_settings == COOL24
    assert TurnOn(COOL24) in c.observe(NOW + minutes(1), "off", by_us=False)


@pytest.mark.parametrize(
    "command",
    [
        lambda c: c.run_open(NOW, COOL24),
        lambda c: c.set_duration(NOW, minutes(20), COOL24),
    ],
    ids=["run_open", "set_duration"],
)
def test_settings_given_before_the_first_report_wait_for_it(
    command: Callable[[TimerCore], list[Effect]],
) -> None:
    """A wish restored from the file counts as in flight until the target is seen, but
    the target has not been seen: settings given with a command are held back, not
    applied to an entity that may not exist yet. The first report applies them."""
    stored = Snapshot(end=NOW + minutes(30), started_at=NOW - minutes(5), pending="on")
    c = TimerCore("strict", minutes(45), stored)

    fx = command(c)

    assert not [e for e in fx if isinstance(e, TurnOn | TurnOff | ApplySettings)]
    assert c.snapshot.owed_settings == COOL24
    assert c.observe(NOW + minutes(1), "on", by_us=False) == [
        ApplySettings(COOL24),
        Changed(),
    ]


def test_refused_settings_are_resent_a_limited_number_of_times() -> None:
    """Reports that repeat the target's state send refused settings 3 times, say so
    once, and then leave the target alone."""
    c = owing("strict", "on")
    c.call_failed(NOW)

    reports = repeat_reports(c, MAX_AUTOMATIC_RESENDS + 3)

    assert reports == [[ApplySettings(COOL24)]] * MAX_AUTOMATIC_RESENDS + [
        [GaveUp("settings")],
        [],
        [],
    ]
    assert c.snapshot.owed_settings == COOL24


def test_a_target_that_comes_back_gets_no_new_allowance_for_the_same_settings() -> None:
    """The target goes away and comes back: that is not a new chance for settings
    that Timerify gave up on."""
    c = owing("strict", "on")
    c.call_failed(NOW)
    repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)

    c.observe(NOW + minutes(10), "unavailable", by_us=False)
    back = c.observe(NOW + minutes(11), "on", by_us=False)

    assert back == [Changed()]
    assert repeat_reports(c, 1) == [[]]
    assert c.snapshot.owed_settings == COOL24


def test_new_settings_start_a_full_allowance_again() -> None:
    """After the core gave up on settings, a command with new ones sends them."""
    c = owing("strict", "on")
    c.call_failed(NOW)
    repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)
    heat = freeze_settings({"hvac_mode": "heat"})

    asked = c.set_duration(NOW + minutes(10), minutes(60), heat)
    c.call_failed(NOW + minutes(10))
    again = repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)

    assert ApplySettings(heat) in asked
    assert again == [[ApplySettings(heat)]] * MAX_AUTOMATIC_RESENDS + [
        [GaveUp("settings")]
    ]


def test_new_settings_riding_a_turn_on_have_an_allowance_of_their_own() -> None:
    """Timerify gave up on settings, the target was stopped and started again with
    others. The turn-on switched it on but not the settings: the turn-on was their
    first delivery, so the report of the target is the first of the 3 re-sends."""
    c = owing("strict", "on")
    c.call_failed(NOW)
    repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)
    c.stop(NOW + minutes(10))
    c.observe(NOW + minutes(11), "off", by_us=True)
    assert c.snapshot.pending is None

    c.set_duration(NOW + minutes(12), minutes(30), HEAT22)
    c.call_failed(NOW + minutes(12))
    on = c.observe(NOW + minutes(13), "on", by_us=True)
    c.call_failed(NOW + minutes(13))
    again = repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1, by_us=True, since=minutes(13))

    assert on == [ApplySettings(HEAT22), Changed()]
    assert again == [[ApplySettings(HEAT22)]] * (MAX_AUTOMATIC_RESENDS - 1) + [
        [GaveUp("settings")],
        [],
    ]


def test_a_command_made_while_away_sends_given_up_settings_on_return() -> None:
    """Timerify gave up on the settings. The target drops off, and the user asks to run
    it again. That is asking again: when the target is back on, the settings go out
    once, and are limited like any others."""
    c = owing("strict", "on")
    c.call_failed(NOW)
    repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)
    c.observe(NOW + minutes(10), "unavailable", by_us=False)
    c.set_duration(NOW + minutes(11), minutes(30))

    back = c.observe(NOW + minutes(12), "on", by_us=False)
    c.call_failed(NOW + minutes(12))
    again = repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1, since=minutes(12))

    assert back == [ApplySettings(COOL24), Changed()]
    assert again == [[ApplySettings(COOL24)]] * MAX_AUTOMATIC_RESENDS + [
        [GaveUp("settings")]
    ]


def test_a_command_gives_refused_settings_a_full_allowance_again() -> None:
    """Asking for the timer again after the core gave up sends the settings once more,
    and they may be repeated as before."""
    c = owing("strict", "on")
    c.call_failed(NOW)
    repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)

    asked = c.set_duration(NOW + minutes(10), minutes(30))
    c.call_failed(NOW + minutes(10))
    again = repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)

    assert ApplySettings(COOL24) in asked
    assert again == [[ApplySettings(COOL24)]] * MAX_AUTOMATIC_RESENDS + [
        [GaveUp("settings")]
    ]


def test_the_limit_of_the_core_is_the_limit_of_its_settings_too() -> None:
    """A core built with fewer re-sends gives up on settings sooner."""
    c = TimerCore(
        "strict", minutes(45), Snapshot(last_actual="on"), automatic_resends=1
    )
    c.set_duration(NOW, minutes(60), COOL24)
    c.call_failed(NOW)

    reports = repeat_reports(c, 3)

    assert reports == [[ApplySettings(COOL24)], [GaveUp("settings")], []]


def test_zero_automatic_resends_answers_no_report() -> None:
    """A device that must not be told twice is told again only when it is asked again,
    not by a repeat of its state and not by its return from unavailable."""
    c = TimerCore(
        "strict", minutes(45), Snapshot(last_actual="off"), automatic_resends=0
    )
    c.set_duration(NOW, minutes(10))
    c.call_failed(NOW)

    repeated = c.observe(NOW + minutes(1), "off", by_us=False)
    c.observe(NOW + minutes(2), "unavailable", by_us=False)
    back = c.observe(NOW + minutes(3), "off", by_us=False)
    asked = c.set_duration(NOW + minutes(4), minutes(10))

    assert repeated == [GaveUp("on")]
    assert back == [Changed()]
    assert TurnOn() in asked


# --- Pending commands -------------------------------------------------------------


def test_add_command_arms_wakeup() -> None:
    """A command on an idle timer is the only reason to wake up."""
    c = core("strict", "off")

    fx = c.add_command(NOW, cmd(15))

    assert fx == [Arm(NOW + minutes(15)), Changed()]
    assert c.snapshot.commands == (cmd(15),)
    assert c.snapshot.end is None
    assert next_wakeup(c.snapshot) == NOW + minutes(15)


def test_wakeup_is_earliest_of_end_and_commands() -> None:
    """The one alarm sits at whichever comes first: the end or the next command."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(45))

    added = c.add_command(NOW, cmd(15))

    assert added == [Arm(NOW + minutes(15)), Changed()]
    assert next_wakeup(c.snapshot) == NOW + minutes(15)

    _, cancelled = c.cancel_commands(NOW, ["c1"])

    assert cancelled == [Arm(NOW + minutes(45)), Changed()]
    assert next_wakeup(c.snapshot) == NOW + minutes(45)


def test_a_command_after_the_end_does_not_move_the_wakeup() -> None:
    """The end is earlier, so the alarm stays there until it has passed."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))

    fx = c.add_command(NOW, cmd(30))

    assert fx == [Arm(NOW + minutes(10)), Changed()]
    assert next_wakeup(c.snapshot) == NOW + minutes(10)


def test_nothing_to_wake_up_for() -> None:
    """An idle timer without commands has no wake-up."""
    assert next_wakeup(Snapshot()) is None


def test_commands_ordered_by_time_then_insertion() -> None:
    """Commands wait in order of time; those at the same time keep insertion order."""
    c = core("strict", "off")

    for command in (cmd(20, id="c2"), cmd(10, id="c1"), cmd(10, id="c3")):
        c.add_command(NOW, command)

    assert tuple(command.id for command in c.snapshot.commands) == ("c1", "c3", "c2")


def test_command_time_is_kept_in_utc() -> None:
    """A command made for a moment in another zone is stored, and armed, in UTC: the
    end and the commands share one representation."""
    c = core("strict", "off")
    local = (NOW + minutes(15)).astimezone(ZoneInfo("Asia/Jerusalem"))

    fx = c.add_command(NOW, Command("c1", local, "on"))

    assert c.snapshot.commands == (cmd(15),)
    assert c.snapshot.commands[0].at.tzinfo is UTC
    arm = fx[0]
    assert isinstance(arm, Arm)
    assert arm.at.tzinfo is UTC


def test_restored_commands_are_ordered_by_time_then_by_their_order() -> None:
    """A timer that starts with its commands in any order still wakes up, and runs,
    the earliest first; commands at the same time keep the order they came in."""
    late, first, second = cmd(30, id="late"), cmd(10, id="a"), cmd(10, id="b")

    c = holding("strict", "off", late, first, second)

    assert [command.id for command in c.snapshot.commands] == ["a", "b", "late"]
    assert next_wakeup(c.snapshot) == NOW + minutes(10)
    c.tick(NOW + minutes(10))
    assert [command.id for command in c.snapshot.commands] == ["late"]


def test_cancel_unknown_command_raises() -> None:
    """Cancelling what is not there is an error, and changes nothing."""
    c = core("strict", "off")
    c.add_command(NOW, cmd(10))
    before = c.snapshot

    with pytest.raises(KeyError):
        c.cancel_commands(NOW, ["unknown"])

    assert c.snapshot == before


def test_cancel_last_command_on_idle_timer_disarms() -> None:
    """With nothing left to wake up for, the alarm is cancelled."""
    c = core("strict", "off")
    c.add_command(NOW, cmd(10))

    _, fx = c.cancel_commands(NOW, ["c1"])

    assert fx == [Disarm(), Changed()]
    assert c.snapshot.commands == ()


def test_cancelling_one_command_keeps_the_others() -> None:
    """Each command is cancelled on its own."""
    c = core("strict", "off")
    c.add_command(NOW, cmd(10, id="c1"))
    c.add_command(NOW, cmd(20, id="c2"))

    gone, fx = c.cancel_commands(NOW, ["c1"])

    assert gone == (cmd(10, id="c1"),)
    assert fx == [Arm(NOW + minutes(20)), Changed()]
    assert c.snapshot.commands == (cmd(20, id="c2"),)


def test_cancelling_several_commands_is_one_change_with_one_set_of_effects() -> None:
    """Every command asked for goes in one step, and the effects are those of the
    timer that is left, once: nothing is carried out for a state that was passed on
    the way. What goes is given back in the order the commands were due."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(45))
    for number in (30, 10, 20, 40):
        c.add_command(NOW, cmd(number, id=f"c{number}"))

    gone, fx = c.cancel_commands(NOW, ["c30", "c10", "c20"])

    assert [command.id for command in gone] == ["c10", "c20", "c30"]
    assert fx == [Arm(NOW + minutes(40)), Changed()]
    assert [command.id for command in c.snapshot.commands] == ["c40"]


def test_cancelling_all_commands_leaves_the_end_of_the_countdown_as_the_alarm() -> None:
    c = core("strict", "on")
    c.set_duration(NOW, minutes(45))
    c.add_command(NOW, cmd(10, id="c1"))
    c.add_command(NOW, cmd(20, id="c2"))

    gone, fx = c.cancel_commands(NOW, ["c1", "c2"])

    assert len(gone) == 2
    assert fx == [Arm(NOW + minutes(45)), Changed()]
    assert c.snapshot.commands == ()


def test_cancelling_no_command_changes_nothing() -> None:
    c = core("strict", "off")
    c.add_command(NOW, cmd(10))
    before = c.snapshot

    gone, fx = c.cancel_commands(NOW, [])

    assert (gone, fx) == ((), [])
    assert c.snapshot == before


def test_cancelling_commands_with_one_unknown_cancels_none() -> None:
    """The step is all or nothing: an id that is not there refuses the whole of it."""
    c = core("strict", "off")
    c.add_command(NOW, cmd(10, id="c1"))
    c.add_command(NOW, cmd(20, id="c2"))
    before = c.snapshot

    with pytest.raises(KeyError, match="unknown"):
        c.cancel_commands(NOW, ["c1", "unknown"])

    assert c.snapshot == before


def test_cancelling_the_same_id_twice_cancels_it_once() -> None:
    c = core("strict", "off")
    c.add_command(NOW, cmd(10, id="c1"))

    gone, _ = c.cancel_commands(NOW, ["c1", "c1"])

    assert [command.id for command in gone] == ["c1"]


def test_stopping_the_timer_keeps_the_commands() -> None:
    """A pending command is not part of the countdown: stopping leaves it (P2)."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(45))
    c.add_command(NOW, cmd(15))

    fx = c.stop(NOW + minutes(1))

    assert fx == [Arm(NOW + minutes(15)), TurnOff(), Changed()]
    assert c.snapshot.commands == (cmd(15),)


def test_every_start_of_a_countdown_arms_the_earliest_wakeup() -> None:
    """The alarm follows the commands wherever the timer used to be armed alone."""
    c = holding("strict", "off", cmd(15))

    assert c.set_duration(NOW, minutes(45)) == [
        Arm(NOW + minutes(15)),
        TurnOn(),
        Changed(),
    ]
    assert c.set_duration(NOW, minutes(5)) == [Arm(NOW + minutes(5)), Changed()]
    assert c.set_duration(NOW, timedelta(0)) == [
        Arm(NOW + minutes(15)),
        TurnOff(),
        Changed(),
    ]
    loose = holding("loose", "off", cmd(15))
    assert loose.run_open(NOW) == [Arm(NOW + minutes(15)), TurnOn(), Changed()]


def test_ac_command_resets_timer_and_applies_settings() -> None:
    """A command is a firm promise: a running AC gets cooling 24 and a new hour (P1)."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(45))
    c.add_command(NOW, cmd(15, minutes=60, settings=COOL24))

    fx = c.tick(NOW + minutes(15))

    assert fx == [Arm(NOW + minutes(75)), ApplySettings(COOL24), Changed()]
    assert c.snapshot.end == NOW + minutes(75)
    assert c.snapshot.commands == ()


def test_command_on_off_target_turns_on_with_settings() -> None:
    """The turn-on of a command carries its settings."""
    c = holding("strict", "off", cmd(15, minutes=60, settings=COOL24))

    fx = c.tick(NOW + minutes(15))

    assert fx == [Arm(NOW + minutes(75)), TurnOn(COOL24), Changed()]
    assert c.snapshot.pending == "on"
    assert c.snapshot.owed_settings == COOL24


def test_command_without_minutes_strict_runs_default_from_at() -> None:
    """Strict mode has no open run: the default duration counts from the command's
    time, not from when the core noticed."""
    c = holding("strict", "off", cmd(10))

    fx = c.tick(NOW + minutes(12))

    assert fx == [Arm(NOW + minutes(55)), TurnOn(), Changed()]
    assert c.snapshot.end == NOW + minutes(10) + minutes(45)


def test_command_without_minutes_loose_runs_open() -> None:
    """Loose mode runs the target with the timer at zero."""
    c = holding("loose", "off", cmd(10))

    fx = c.tick(NOW + minutes(10))

    assert fx == [Disarm(), TurnOn(), Changed()]
    assert c.snapshot.end is None
    assert c.snapshot.pending == "on"


@pytest.mark.parametrize("mode", ["strict", "loose"])
def test_command_without_minutes_keeps_a_running_countdown(mode: Mode) -> None:
    """As a bare turn-on by hand does, the command leaves a target that is wanted
    running as it is: the default duration or the open run is for a target that is
    off."""
    c = holding(mode, "on", cmd(10), end=NOW + minutes(120))

    fx = c.tick(NOW + minutes(10))

    assert fx == [Arm(NOW + minutes(120)), Changed()]
    assert c.snapshot.end == NOW + minutes(120)
    assert c.snapshot.commands == ()


@pytest.mark.parametrize("mode", ["strict", "loose"])
def test_command_without_minutes_still_sets_its_settings_on_a_running_target(
    mode: Mode,
) -> None:
    """P1: the command is a firm promise, and what it turns the target on with is
    set although its countdown is not."""
    c = holding(
        mode,
        "on",
        cmd(10, settings=COOL24),
        end=NOW + minutes(120),
    )

    fx = c.tick(NOW + minutes(10))

    assert fx == [Arm(NOW + minutes(120)), ApplySettings(COOL24), Changed()]
    assert c.snapshot.end == NOW + minutes(120)


def test_command_without_minutes_keeps_a_loose_run_without_a_countdown() -> None:
    c = holding("loose", "on", cmd(10))

    fx = c.tick(NOW + minutes(10))

    assert fx == [Disarm(), Changed()]
    assert c.snapshot.end is None
    assert c.snapshot.pending is None


@pytest.mark.parametrize("mode", ["strict", "loose"])
def test_command_without_minutes_at_the_end_runs_the_target_again(mode: Mode) -> None:
    """The countdown reaches zero at the instant the command is due: as the end goes
    after a command on a tie, the command finds a target that is about to be off, and
    turns it on as R9 says, so it is never switched off and on."""
    c = holding(mode, "on", cmd(10), end=NOW + minutes(10))

    fx = c.tick(NOW + minutes(10))

    assert TurnOff() not in fx
    assert c.snapshot.end == (NOW + minutes(55) if mode == "strict" else None)


def test_command_without_minutes_keeps_the_countdown_it_found_when_it_was_due() -> None:
    """A command that was due while Home Assistant was down is folded as if it ran
    then: the countdown that was under way at its time is kept, and goes on to end
    when it did."""
    c = holding("strict", "on", cmd(-30), end=NOW - minutes(10))

    fx = c.tick(NOW)

    assert fx == [Disarm(), TurnOff(), Changed()]
    assert c.snapshot.end is None


def test_off_command_stops() -> None:
    """A command to turn off ends the countdown and switches the target off."""
    c = holding("strict", "on", cmd(10, "off"), end=NOW + minutes(60))

    fx = c.tick(NOW + minutes(10))

    assert fx == [Disarm(), TurnOff(), Changed()]
    assert c.snapshot.end is None
    assert c.snapshot.pending == "off"


def test_off_command_drops_the_settings_that_are_owed() -> None:
    """A timer that stops runs with nothing, as for any other end."""
    c = holding("strict", "unavailable", cmd(10, "off"))
    c.set_duration(NOW, minutes(60), COOL24)

    c.tick(NOW + minutes(10))

    assert c.snapshot.owed_settings == NO_SETTINGS


def test_manual_off_keeps_commands() -> None:
    """Switching the target off by hand ends the countdown, not the promises (P2)."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(45))
    c.add_command(NOW, cmd(15))

    fx = c.observe(NOW + minutes(1), "off", by_us=False)

    assert fx == [Arm(NOW + minutes(15)), Changed()]
    assert c.snapshot.commands == (cmd(15),)
    assert c.snapshot.end is None


def test_manual_on_keeps_commands() -> None:
    """The default timer a manual start makes does not replace the commands (P2); the
    alarm stays at the command, which is earlier."""
    c = core("strict", "off")
    c.add_command(NOW, cmd(15))

    fx = c.observe(NOW + minutes(1), "on", by_us=False)

    assert fx == [Arm(NOW + minutes(15)), Changed()]
    assert c.snapshot.commands == (cmd(15),)
    assert c.snapshot.end == NOW + minutes(46)


def test_late_command_runs_for_the_remainder() -> None:
    """A command noticed late counts its duration from the time it was due."""
    c = holding("strict", "off", cmd(-20, minutes=60))

    fx = c.tick(NOW)

    assert fx == [Arm(NOW + minutes(40)), TurnOn(), Changed()]
    assert c.snapshot.end == NOW + minutes(40)


@pytest.mark.parametrize(
    ("late_by", "dropped"),
    [(61, True), (60, True), (59, False)],
    ids=["past", "to-the-minute", "one-minute-left"],
)
def test_late_command_past_its_duration_is_dropped(late_by: int, dropped: bool) -> None:
    """With nothing left of the run, the command is dropped and the timer untouched."""
    late = cmd(-late_by, minutes=60)
    c = holding("strict", "on", late, end=NOW + minutes(30))

    fx = c.tick(NOW)

    assert c.snapshot.commands == ()
    if dropped:
        assert fx == [CommandDropped(late), Arm(NOW + minutes(30)), Changed()]
        assert c.snapshot.end == NOW + minutes(30)
    else:
        assert fx == [Arm(NOW + minutes(1)), Changed()]
        assert c.snapshot.end == NOW + minutes(1)


@pytest.mark.parametrize(
    ("late_by", "dropped"),
    [(46, True), (45, True), (44, False)],
    ids=["past", "to-the-minute", "one-minute-left"],
)
def test_late_strict_open_run_past_default_is_dropped(
    late_by: int, dropped: bool
) -> None:
    """The default duration of strict mode is the run an open command asked for."""
    late = cmd(-late_by)
    c = holding("strict", "off", late)

    fx = c.tick(NOW)

    assert (CommandDropped(late) in fx) is dropped
    assert (TurnOn() in fx) is not dropped


def test_command_never_runs_past_the_longest_countdown() -> None:
    """A command may ask for more than a day, but no countdown lasts longer than that
    from now, whichever command starts it."""
    c = holding("strict", "off", cmd(0, minutes=MAX_MINUTES + 60))

    c.tick(NOW)

    assert c.snapshot.end == NOW + minutes(MAX_MINUTES)


def test_late_loose_open_run_and_late_off_still_execute() -> None:
    """Neither has a duration that can have run out: they are carried out, however
    late."""
    opening = holding("loose", "off", cmd(-600))
    closing = holding("strict", "on", cmd(-600, "off"), end=NOW + minutes(30))

    assert opening.tick(NOW) == [Disarm(), TurnOn(), Changed()]
    assert closing.tick(NOW) == [Disarm(), TurnOff(), Changed()]


def test_due_on_then_off_switches_nothing() -> None:
    """Both were due while nobody was looking: only their net result counts, and on
    an off target that is nothing."""
    c = holding("strict", "off", cmd(0, id="c1"), cmd(0, "off", id="c2"))

    fx = c.tick(NOW)

    assert fx == [Disarm(), Changed()]
    assert c.snapshot == Snapshot(last_actual="off")


def test_due_off_then_on_switches_on_once() -> None:
    """The last wish wins: an off that was due before an on is never sent."""
    c = holding(
        "strict",
        "on",
        cmd(-20, "off", id="c1"),
        cmd(-10, minutes=60, id="c2"),
        end=NOW + minutes(30),
    )

    fx = c.tick(NOW)

    assert fx == [Arm(NOW + minutes(50)), Changed()]
    assert c.snapshot.end == NOW + minutes(50)


def test_several_due_commands_leave_the_last_settings() -> None:
    """Of commands that were all due, the one nearest to now sets what the target
    runs with, and its run is the one that counts."""
    heat = freeze_settings({"hvac_mode": "heat"})
    c = holding(
        "strict",
        "off",
        cmd(-20, minutes=60, settings=heat, id="c1"),
        cmd(-10, minutes=60, settings=COOL24, id="c2"),
    )

    fx = c.tick(NOW)

    assert fx == [Arm(NOW + minutes(50)), TurnOn(COOL24), Changed()]
    assert c.snapshot.owed_settings == COOL24


def test_command_at_timer_end_extends_without_flap() -> None:
    """A command due at the very end moves it, so the target is never switched off."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))
    c.add_command(NOW, cmd(10, minutes=30))

    fx = c.tick(NOW + minutes(10))

    assert fx == [Arm(NOW + minutes(40)), Changed()]
    assert c.snapshot.end == NOW + minutes(40)
    assert c.snapshot.commands == ()


def test_command_at_the_end_keeps_the_settings_that_are_owed() -> None:
    """The command goes before the end on a tie: the timer never stops, so what it
    was to run with is still owed."""
    c = TimerCore(
        "strict",
        minutes(45),
        Snapshot(
            end=NOW + minutes(10),
            owed_settings=COOL24,
            commands=(cmd(10, minutes=30),),
            last_actual="on",
        ),
    )

    c.tick(NOW + minutes(10))

    assert c.snapshot.owed_settings == COOL24


def test_command_after_the_end_runs_after_the_timer_stopped() -> None:
    """Due items go in time order: the end at 06:55 stops the timer, and the command
    at 06:57 starts a new one, with one switch for the pair."""
    c = holding("strict", "off", cmd(-3, minutes=60), end=NOW - minutes(5))

    fx = c.tick(NOW)

    assert fx == [Arm(NOW + minutes(57)), TurnOn(), Changed()]
    assert c.snapshot.end == NOW + minutes(57)


def test_off_command_before_the_end_stops_once() -> None:
    """The end that the command removes is not an item of its own."""
    c = holding("strict", "on", cmd(-10, "off"), end=NOW - minutes(5))

    fx = c.tick(NOW)

    assert fx == [Disarm(), TurnOff(), Changed()]


def test_command_due_while_unavailable_changes_timer_at_once() -> None:
    """The timer follows the command now; the target gets it when it is back (R10)."""
    c = holding("strict", "unavailable", cmd(10, minutes=30, settings=COOL24))

    fx = c.tick(NOW + minutes(10))

    assert fx == [Arm(NOW + minutes(40)), Changed()]
    assert c.snapshot.end == NOW + minutes(40)

    back = c.observe(NOW + minutes(12), "off", by_us=False)

    assert back == [TurnOn(COOL24), Changed()]


def test_restart_with_expired_timer_and_late_command_does_not_flap() -> None:
    """After a restart the timer that ran out and the command that came due before it
    are folded together: the target stays on, and runs for the rest of the command."""
    c = TimerCore(
        "strict",
        timedelta(minutes=45),
        Snapshot(
            end=NOW - timedelta(minutes=5),
            commands=(cmd(-10, minutes=60, settings=COOL24),),
        ),
    )

    fx = c.observe(NOW, "on", by_us=False)

    # No TurnOff and no TurnOn: the settings alone reach the target that kept running.
    assert fx == [Arm(NOW + minutes(50)), ApplySettings(COOL24), Changed()]
    assert c.snapshot.end == NOW + timedelta(minutes=50)
    assert c.snapshot.commands == ()


def test_command_due_with_a_manual_off_still_runs() -> None:
    """The report of a target switched off is not allowed to undo a command that came
    due with it: the due items outrank it."""
    c = holding("strict", "on", cmd(-1, minutes=30))

    fx = c.observe(NOW, "off", by_us=False)

    assert fx == [Arm(NOW + minutes(29)), TurnOn(), Changed()]
    assert c.snapshot.end == NOW + minutes(29)


def test_dropped_command_leaves_a_manual_start_to_strict_mode() -> None:
    """A command that was dropped did nothing to the timer, so a target found on is
    still given its default countdown (R4)."""
    late = cmd(-61, minutes=60)
    c = holding("strict", None, late)

    fx = c.observe(NOW, "on", by_us=False)

    assert fx == [CommandDropped(late), Disarm(), Arm(NOW + minutes(45)), Changed()]
    assert c.snapshot.end == NOW + minutes(45)
    assert c.snapshot.commands == ()


def test_observations_never_touch_commands() -> None:
    """Whatever the target reports, commands that are not due stay (P2)."""
    c = holding("strict", "off", cmd(30), cmd(60, "off", id="c2"))
    before = c.snapshot.commands

    for step, actual in enumerate(("on", "off", "unavailable", "on", "off"), 1):
        c.observe(NOW + minutes(step), actual, by_us=False)

    assert c.snapshot.commands == before


def test_tick_with_nothing_due_is_stale() -> None:
    """An alarm that fires before anything is due is a leftover and does nothing."""
    c = holding("strict", "on", cmd(30), end=NOW + minutes(10))
    before = c.snapshot

    assert c.tick(NOW + minutes(5)) == []
    assert c.snapshot == before


def test_tick_on_idle_timer_without_commands_is_stale() -> None:
    assert core("strict", "off").tick(NOW) == []


def test_command_with_a_naive_time_is_rejected() -> None:
    """Commands are kept in UTC: a time without a zone is refused, not guessed."""
    c = core("strict", "off")

    with pytest.raises(ValueError, match="timezone-aware"):
        c.add_command(NOW, Command("c1", datetime(2026, 1, 5, 7, 15), "on"))

    assert c.snapshot == Snapshot(last_actual="off")


NAIVE = datetime(2026, 1, 5, 7, 0)


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda c: c.set_duration(NAIVE, minutes(5)), id="set"),
        pytest.param(lambda c: c.add(NAIVE, minutes(5)), id="add"),
        pytest.param(lambda c: c.stop(NAIVE), id="stop"),
        pytest.param(lambda c: c.run_open(NAIVE), id="run-open"),
        pytest.param(lambda c: c.tick(NAIVE), id="tick"),
        pytest.param(
            lambda c: c.set_interval_enabled(NAIVE, "x", False), id="set-interval"
        ),
        pytest.param(lambda c: c.add_command(NAIVE, cmd(10)), id="add-command"),
        pytest.param(lambda c: c.cancel_commands(NAIVE, ["c1"]), id="cancel-commands"),
        pytest.param(lambda c: c.observe(NAIVE, "on", by_us=False), id="observe"),
        pytest.param(lambda c: c.call_failed(NAIVE), id="call-failed"),
        pytest.param(lambda c: c.settings_applied(NAIVE), id="settings-applied"),
        pytest.param(lambda c: remaining_minutes(c.snapshot, NAIVE), id="remaining"),
    ],
)
def test_naive_time_is_rejected(call: Callable[[TimerCore], object]) -> None:
    """A time without a timezone is ambiguous, so it is refused, not guessed."""
    c = core("strict", "off")
    before = c.snapshot

    with pytest.raises(ValueError, match="timezone-aware"):
        call(c)

    assert c.snapshot == before


# Schedule windows (S1 to S4): they are folded into the timer with the commands and
# the end, so the target is asked once, for the last wish.


def following(
    mode: Mode, actual: Actual | None, *windows: Window, end: datetime | None = None
) -> TimerCore:
    """A core restored from the store with `windows`; its timer, if it has an `end`,
    is the one the first window that has started set."""
    scheduled_by = next((w.interval_id for w in windows if w.started), None)
    return TimerCore(
        mode,
        minutes(45),
        Snapshot(
            end=end,
            scheduled_by=None if end is None else scheduled_by,
            windows=windows,
            last_actual=actual,
        ),
    )


def test_set_windows_arms_the_first_start() -> None:
    """The windows are only merged; the alarm waits for the first of them."""
    c = core("strict", "off")

    fx = c.set_windows(
        NOW, [window("x", 30, 75), window("y", 5, 20)], configured={"x", "y"}
    )

    assert fx == [Arm(NOW + minutes(5)), Changed()]
    assert [w.interval_id for w in c.snapshot.windows] == ["y", "x"]
    assert c.snapshot.end is None


def test_set_windows_to_none_disarms() -> None:
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 30, 75)], configured={"x"})

    assert c.set_windows(NOW, [], configured={"x"}) == [Disarm(), Changed()]
    assert c.snapshot.windows == ()


def test_set_windows_with_the_same_windows_changes_nothing() -> None:
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 30, 75)], configured={"x"})

    assert c.set_windows(NOW, [window("x", 30, 75)], configured={"x"}) == [
        Arm(NOW + minutes(30))
    ]


def test_windows_are_kept_in_utc() -> None:
    jerusalem = ZoneInfo("Asia/Jerusalem")
    c = core("strict", "off")

    c.set_windows(
        NOW,
        [Window("x", (NOW + minutes(30)).astimezone(jerusalem), NOW + minutes(75))],
        configured={"x"},
    )

    assert c.snapshot.windows[0].start == NOW + minutes(30)
    assert c.snapshot.windows[0].start.utcoffset() == timedelta(0)


def test_restored_windows_are_ordered_by_their_start() -> None:
    c = TimerCore(
        "strict",
        minutes(45),
        Snapshot(windows=(window("late", 30, 75), window("early", 5, 20))),
    )

    assert [w.interval_id for w in c.snapshot.windows] == ["early", "late"]


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(
            Window("x", datetime(2026, 1, 5, 7, 30), NOW + minutes(75)), id="naive"
        ),
        pytest.param(window("x", 30, 30), id="empty"),
        pytest.param(window("x", 30, 20), id="backwards"),
        pytest.param(window("x", 0, MAX_MINUTES + 1), id="longer-than-a-day"),
    ],
)
def test_a_window_that_cannot_be_one_is_refused(bad: Window) -> None:
    c = core("strict", "off")
    before = c.snapshot

    with pytest.raises(ValueError, match="window"):
        c.set_windows(NOW, [bad], configured={"x"})

    assert c.snapshot == before


def test_two_windows_of_one_interval_are_refused() -> None:
    c = core("strict", "off")

    with pytest.raises(ValueError, match="two windows of the interval x"):
        c.set_windows(NOW, [window("x", 5, 20), window("x", 30, 45)], configured={"x"})

    assert c.snapshot == Snapshot(last_actual="off")


def test_a_window_of_a_full_day_is_allowed() -> None:
    c = core("strict", "off")

    c.set_windows(NOW, [window("x", 0, MAX_MINUTES)], configured={"x"})

    assert c.snapshot.windows == (window("x", 0, MAX_MINUTES),)


def test_window_start_runs_the_timer_to_its_end() -> None:
    """S1: a window that opens on an idle target runs it to the window's end."""
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 5, 45)], configured={"x"})

    fx = c.tick(NOW + minutes(5))

    assert fx == [Arm(NOW + minutes(45)), TurnOn(), Changed()]
    assert c.snapshot.end == NOW + minutes(45)
    assert c.snapshot.scheduled_by == "x"
    assert c.snapshot.windows[0].started


def test_window_start_leaves_a_later_end_alone() -> None:
    """S1: a manual extension wins, and the timer is not the window's."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(60))
    c.set_windows(NOW, [window("x", 0, 45)], configured={"x"})

    fx = c.tick(NOW)

    assert fx == [Arm(NOW + minutes(45)), Changed()]
    assert c.snapshot.end == NOW + minutes(60)
    assert c.snapshot.scheduled_by is None
    assert c.snapshot.windows[0].started


def test_window_start_leaves_an_end_that_is_the_same_alone() -> None:
    """The timer already ends where the window does: it is the user's, not the
    window's, so editing the interval will not move it (S3)."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(45))
    c.set_windows(NOW, [window("x", 0, 45)], configured={"x"})

    c.tick(NOW)

    assert c.snapshot.end == NOW + minutes(45)
    assert c.snapshot.scheduled_by is None


def test_window_start_extends_an_earlier_end() -> None:
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))
    c.set_windows(NOW, [window("x", 0, 45)], configured={"x"})

    fx = c.tick(NOW)

    assert fx == [Arm(NOW + minutes(45)), Changed()]
    assert c.snapshot.end == NOW + minutes(45)
    assert c.snapshot.scheduled_by == "x"


def test_window_settings_go_with_the_turn_on() -> None:
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 0, 45, COOL24)], configured={"x"})

    fx = c.tick(NOW)

    assert fx == [Arm(NOW + minutes(45)), TurnOn(COOL24), Changed()]
    assert c.snapshot.owed_settings == COOL24
    assert c.snapshot.owed_turn_on_only


def test_window_settings_skip_a_running_target() -> None:
    """§5.4: someone chose the settings the running target has; a window that opens
    on it only extends the timer."""
    c = core("strict", "on")
    c.set_windows(NOW, [window("x", 0, 45, COOL24)], configured={"x"})

    fx = c.tick(NOW)

    assert fx == [Arm(NOW + minutes(45)), Changed()]
    assert c.snapshot.owed_settings == NO_SETTINGS


def test_window_after_a_command_in_the_same_fold_pushes_no_settings() -> None:
    """The command turns the target on as of 06:20, so by 06:30 it is running with the
    command's settings (P1), and the window does not push its own."""
    c = core("strict", "off")
    c.add_command(NOW, cmd(-40, minutes=60, settings=COOL24))
    c.set_windows(NOW, [window("x", -30, 45, HEAT22)], configured={"x"})

    fx = c.tick(NOW)

    assert fx == [Arm(NOW + minutes(45)), TurnOn(COOL24), Changed()]
    assert c.snapshot.owed_settings == COOL24
    assert c.snapshot.scheduled_by == "x"


def test_window_start_while_a_turn_on_is_in_flight_keeps_the_commands_settings() -> (
    None
):
    """A turn-on that went out but is not yet confirmed counts as the target running:
    the window must not replace the settings that ride with it."""
    c = core("strict", "off")
    assert c.set_duration(NOW, minutes(30), COOL24) == [
        Arm(NOW + minutes(30)),
        TurnOn(COOL24),
        Changed(),
    ]
    c.set_windows(NOW, [window("x", 5, 45, HEAT22)], configured={"x"})

    fx = c.tick(NOW + minutes(5))

    assert fx == [Arm(NOW + minutes(45)), Changed()]
    assert c.snapshot.owed_settings == COOL24
    assert not c.snapshot.owed_turn_on_only
    assert c.snapshot.scheduled_by == "x"


def test_window_start_while_a_plain_turn_on_is_in_flight_pushes_no_settings() -> None:
    """A turn-on on its way already wants the target running, whoever asked for it:
    the window only extends the timer."""
    c = core("strict", "off")
    assert c.set_duration(NOW, minutes(10)) == [
        Arm(NOW + minutes(10)),
        TurnOn(),
        Changed(),
    ]
    c.set_windows(NOW, [window("x", 5, 45, COOL24)], configured={"x"})

    fx = c.tick(NOW + minutes(5))

    assert fx == [Arm(NOW + minutes(45)), Changed()]
    assert c.snapshot.owed_settings == NO_SETTINGS
    assert not c.snapshot.owed_turn_on_only


def test_window_start_after_a_failed_turn_on_keeps_the_settings_that_are_owed() -> None:
    """A turn-on that never reached the target is still wanted (R8: the set was made by
    hand, and it wins): the window does not replace its settings, and the turn-on that
    is sent again carries them."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(30), COOL24)
    c.call_failed(NOW)
    c.set_windows(NOW, [window("x", 5, 45, HEAT22)], configured={"x"})

    fx = c.tick(NOW + minutes(5))

    assert fx == [Arm(NOW + minutes(45)), TurnOn(COOL24), Changed()]
    assert c.snapshot.owed_settings == COOL24


def test_window_start_while_a_turn_on_waits_for_the_target_keeps_its_settings() -> None:
    """P1, R10: the 06:20 command turned the target on first, so the 06:30 window found
    it wanted on and pushes nothing, however the folds fall; when the target is back,
    it gets cooling 24, never heating 22."""
    c = core("strict", "unavailable")
    c.add_command(NOW, cmd(-40, minutes=15, settings=COOL24))
    c.set_windows(NOW, [window("x", -30, 15, HEAT22)], configured={"x"})
    c.tick(NOW + minutes(-40))

    c.tick(NOW + minutes(-30))

    assert c.snapshot.owed_settings == COOL24
    assert c.snapshot.end == NOW + minutes(15)
    back = c.observe(NOW + minutes(-20), "off", by_us=False)
    assert back == [TurnOn(COOL24), Changed()]


def test_command_and_window_folded_while_the_target_is_away_keep_the_settings() -> None:
    """The same, when Home Assistant was down and both fall due in one fold."""
    c = core("strict", "unavailable")
    c.add_command(NOW, cmd(-40, minutes=15, settings=COOL24))
    c.set_windows(NOW, [window("x", -30, 15, HEAT22)], configured={"x"})

    c.tick(NOW + minutes(-30))

    assert c.snapshot.owed_settings == COOL24
    back = c.observe(NOW + minutes(-20), "off", by_us=False)
    assert back == [TurnOn(COOL24), Changed()]


def test_window_start_after_a_restart_keeps_the_settings_of_an_unconfirmed_on() -> None:
    """A restored wish counts as not delivered, which must not make the window win:
    the command ran before the restart, the window opens in the start-up fold, and the
    target that comes back off gets cooling 24."""
    c = TimerCore(
        "strict",
        minutes(45),
        Snapshot(
            end=NOW + minutes(-10),
            pending="on",
            owed_settings=COOL24,
            windows=(window("x", -30, 15, HEAT22),),
        ),
    )

    assert c.observe(NOW + minutes(-25), "unavailable", by_us=False) == [
        Arm(NOW + minutes(15)),
        Changed(),
    ]
    back = c.observe(NOW + minutes(-20), "off", by_us=False)

    assert c.snapshot.owed_settings == COOL24
    assert back == [TurnOn(COOL24), Changed()]


def test_window_start_while_a_turn_off_is_in_flight_turns_on_with_its_settings() -> (
    None
):
    """The timer ended and its turn-off is on its way, so the target is wanted off:
    the window that opens now turns it on with its own settings, though the target
    still reports on."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(10))
    c.tick(NOW + minutes(10))
    c.set_windows(NOW, [window("x", 11, 45, HEAT22)], configured={"x"})

    fx = c.tick(NOW + minutes(11))

    assert fx == [Arm(NOW + minutes(45)), TurnOn(HEAT22), Changed()]
    assert c.snapshot.owed_settings == HEAT22


def test_window_start_while_the_target_is_unavailable_turns_on_when_it_is_back() -> (
    None
):
    """R10: the timer follows the window now, the target gets the turn-on and the
    settings when it is back."""
    c = core("strict", "unavailable")
    c.set_windows(NOW, [window("x", 0, 45, COOL24)], configured={"x"})

    assert c.tick(NOW) == [Arm(NOW + minutes(45)), Changed()]
    assert c.snapshot.end == NOW + minutes(45)

    back = c.observe(NOW + minutes(2), "off", by_us=False)

    assert back == [TurnOn(COOL24), Changed()]


def away_until_the_window_owes(settings: Settings = COOL24) -> TimerCore:
    """A core whose target is away when the window of `x` opens, so the window's
    settings are owed to a turn-on that waits (R10)."""
    c = core("strict", "unavailable")
    c.set_windows(NOW, [window("x", 0, 45, settings)], configured={"x"})
    assert c.tick(NOW) == [Arm(NOW + minutes(45)), Changed()]
    assert c.snapshot.owed_settings == settings
    assert c.snapshot.owed_turn_on_only
    return c


def test_turn_on_only_settings_are_dropped_when_the_target_comes_back_on() -> None:
    """§5.4: the AC was away when the window opened and comes back running, so someone
    chose its settings; the window's are not pushed onto it."""
    c = away_until_the_window_owes()

    back = c.observe(NOW + minutes(2), "on", by_us=False)

    assert back == [Changed()]
    assert c.snapshot.owed_settings == NO_SETTINGS
    assert not c.snapshot.owed_turn_on_only
    assert c.snapshot.pending is None
    assert c.snapshot.end == NOW + minutes(45)


def test_turn_on_only_settings_go_with_the_turn_on_when_the_target_comes_back_off() -> (
    None
):
    """The same window, the AC back off: it is turned on with the window's settings."""
    c = away_until_the_window_owes()

    back = c.observe(NOW + minutes(2), "off", by_us=False)

    assert back == [TurnOn(COOL24), Changed()]
    assert c.snapshot.owed_settings == COOL24


def test_settings_applied_clears_the_marker_with_the_settings() -> None:
    """Once the turn-on that carried them went through, nothing is owed any more."""
    c = away_until_the_window_owes()
    c.observe(NOW + minutes(2), "off", by_us=False)

    fx = c.settings_applied(NOW + minutes(2))

    assert fx == [Changed()]
    assert c.snapshot.owed_settings == NO_SETTINGS
    assert not c.snapshot.owed_turn_on_only


def test_a_turn_on_that_failed_takes_turn_on_only_settings_again() -> None:
    """The target is still off, so the settings still have a turn-on to ride on."""
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 0, 45, COOL24)], configured={"x"})
    assert c.tick(NOW) == [Arm(NOW + minutes(45)), TurnOn(COOL24), Changed()]
    c.call_failed(NOW)

    fx = c.observe(NOW + minutes(1), "off", by_us=False)

    assert fx == [TurnOn(COOL24)]
    assert c.snapshot.owed_settings == COOL24
    assert c.snapshot.owed_turn_on_only


def test_manual_on_after_a_failed_turn_on_drops_turn_on_only_settings() -> None:
    """The window's turn-on never reached the AC and someone switched it on by hand:
    its settings were chosen, and the window's are not pushed onto it."""
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 0, 45, COOL24)], configured={"x"})
    assert c.tick(NOW) == [Arm(NOW + minutes(45)), TurnOn(COOL24), Changed()]
    c.call_failed(NOW)

    fx = c.observe(NOW + minutes(1), "on", by_us=False)

    assert fx == [Changed()]
    assert c.snapshot.owed_settings == NO_SETTINGS
    assert not c.snapshot.owed_turn_on_only
    assert c.snapshot.pending is None


@pytest.mark.parametrize(
    "ask",
    [
        pytest.param(
            lambda c: c.set_duration(NOW + minutes(1), minutes(30), HEAT22), id="set"
        ),
        pytest.param(lambda c: c.run_open(NOW + minutes(1), HEAT22), id="run-open"),
        pytest.param(
            lambda c: (
                c.add_command(NOW, cmd(1, minutes=30, settings=HEAT22)),
                c.tick(NOW + minutes(1)),
            ),
            id="pending-command",
        ),
    ],
)
def test_a_command_with_settings_replaces_the_marker(
    ask: Callable[[TimerCore], object],
) -> None:
    """P1: what a command asks the target to run with is never turn-on-only, so the AC
    that comes back running gets heating 22 and not cooling 24."""
    c = away_until_the_window_owes()

    ask(c)

    assert c.snapshot.owed_settings == HEAT22
    assert not c.snapshot.owed_turn_on_only
    back = c.observe(NOW + minutes(2), "on", by_us=False)
    assert back == [ApplySettings(HEAT22), Changed()]
    assert c.snapshot.owed_settings == HEAT22


def test_a_command_without_settings_leaves_the_marker_alone() -> None:
    """A plain command neither invents settings nor makes the window's go anywhere
    else than with a turn-on."""
    c = away_until_the_window_owes()

    c.set_duration(NOW + minutes(1), minutes(60))

    assert c.snapshot.owed_settings == COOL24
    assert c.snapshot.owed_turn_on_only
    assert c.observe(NOW + minutes(2), "on", by_us=False) == [Changed()]
    assert c.snapshot.owed_settings == NO_SETTINGS


@pytest.mark.parametrize(
    "ending",
    [
        pytest.param(lambda c, now: c.stop(now), id="stop"),
        pytest.param(lambda c, now: c.set_duration(now, timedelta(0)), id="zero"),
        pytest.param(lambda c, now: c.tick(now + minutes(45)), id="expiry"),
    ],
)
def test_every_end_of_the_timer_drops_turn_on_only_settings(
    ending: Callable[[TimerCore, datetime], object],
) -> None:
    """A timer that stops runs with nothing: the window's settings go with it."""
    c = away_until_the_window_owes()

    ending(c, NOW + minutes(1))

    assert c.snapshot.owed_settings == NO_SETTINGS
    assert not c.snapshot.owed_turn_on_only


def test_window_turn_on_that_took_but_not_its_settings_resends_the_settings() -> None:
    """The window's turn-on switched the AC on and a later settings call failed: the AC
    runs because of our own turn-on, so what did not follow is retried on its own, as
    a command's would be, and is no longer turn-on-only."""
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 0, 45, HEAT22)], configured={"x"})
    assert c.tick(NOW) == [Arm(NOW + minutes(45)), TurnOn(HEAT22), Changed()]
    c.call_failed(NOW)

    fx = c.observe(NOW + minutes(1), "on", by_us=True)

    assert fx == [ApplySettings(HEAT22), Changed()]
    assert c.snapshot.owed_settings == HEAT22
    assert not c.snapshot.owed_turn_on_only
    assert c.snapshot.pending is None
    c.call_failed(NOW + minutes(1))
    assert c.observe(NOW + minutes(2), "on", by_us=False) == [ApplySettings(HEAT22)]
    assert c.settings_applied(NOW + minutes(2)) == [Changed()]
    assert c.snapshot.owed_settings == NO_SETTINGS


def test_restored_turn_on_only_settings_skip_a_running_target() -> None:
    """Home Assistant restarted with the window's settings owed to a turn-on; the AC
    is found running, so nothing is pushed onto it."""
    c = TimerCore(
        "strict",
        minutes(45),
        Snapshot(
            end=NOW + minutes(30),
            pending="on",
            owed_settings=COOL24,
            owed_turn_on_only=True,
        ),
    )

    assert c.observe(NOW, "on", by_us=False) == [Changed()]
    assert c.snapshot.owed_settings == NO_SETTINGS
    assert not c.snapshot.owed_turn_on_only


def test_restored_turn_on_only_settings_go_with_the_turn_on_of_an_off_target() -> None:
    """The same restart finds the AC off: the wish goes out with the settings, which
    stay turn-on-only until the turn-on lands."""
    c = TimerCore(
        "strict",
        minutes(45),
        Snapshot(
            end=NOW + minutes(30),
            pending="on",
            owed_settings=COOL24,
            owed_turn_on_only=True,
        ),
    )

    assert c.observe(NOW, "off", by_us=False) == [TurnOn(COOL24), Changed()]
    assert c.snapshot.owed_turn_on_only


def test_restored_turn_on_only_settings_without_a_wish_skip_a_running_target() -> None:
    """Whatever left them behind, settings that may only ride on a turn-on never wait
    for a target that already runs."""
    c = TimerCore(
        "strict",
        minutes(45),
        Snapshot(end=NOW + minutes(30), owed_settings=COOL24, owed_turn_on_only=True),
    )

    assert c.observe(NOW, "on", by_us=False) == [Changed()]
    assert c.snapshot.owed_settings == NO_SETTINGS
    assert not c.snapshot.owed_turn_on_only


def test_window_start_cuts_a_loose_open_run_at_the_window_end() -> None:
    """A timer above zero means off at zero, so the window that opens on a loose
    target that runs without a countdown gives it one."""
    c = core("loose", "on")
    c.run_open(NOW)
    c.set_windows(NOW, [window("x", 5, 45)], configured={"x"})

    c.tick(NOW + minutes(5))

    assert c.snapshot.end == NOW + minutes(45)
    assert c.snapshot.scheduled_by == "x"


def test_window_that_ended_before_it_was_noticed_does_nothing() -> None:
    """R10, §5.7: a window that was over before anyone looked has nothing left to run,
    and must not cut a run that is going on."""
    c = TimerCore(
        "loose",
        minutes(45),
        Snapshot(windows=(window("x", -90, -45),), last_actual=None),
    )

    fx = c.observe(NOW, "on", by_us=False)

    assert fx == [Disarm(), Changed()]
    assert c.snapshot == Snapshot(last_actual="on")


def test_window_end_removes_the_window() -> None:
    c = following("strict", "on", window("x", -45, 0, started=True))

    fx = c.tick(NOW)

    assert fx == [Disarm(), Changed()]
    assert c.snapshot.windows == ()


def test_window_end_leaves_a_manual_extension_running() -> None:
    """The window's end is not the timer's: a "+30" made during it stays."""
    c = core("strict", "on")
    c.set_windows(NOW, [window("x", 0, 45)], configured={"x"})
    c.tick(NOW)
    c.add(NOW + minutes(40), minutes(30))

    fx = c.tick(NOW + minutes(45))

    assert fx == [Arm(NOW + minutes(75)), Changed()]
    assert c.snapshot.end == NOW + minutes(75)
    assert c.snapshot.windows == ()


def test_realign_shortens_extends_and_stops() -> None:
    """S2: while the timer's end is the window's, editing the window moves the end,
    and a window that is no longer open stops the timer."""
    c = following(
        "strict", "on", window("x", -15, 45, started=True), end=NOW + minutes(45)
    )

    c.set_windows(NOW, [window("x", -60, 30)], configured={"x"})
    shortened = c.tick(NOW)

    assert shortened == [Arm(NOW + minutes(30)), Changed()]
    assert c.snapshot.end == NOW + minutes(30)
    assert c.snapshot.scheduled_by == "x"

    c.set_windows(NOW, [window("x", -60, 90)], configured={"x"})
    extended = c.tick(NOW)

    assert extended == [Arm(NOW + minutes(90)), Changed()]
    assert c.snapshot.end == NOW + minutes(90)
    assert c.snapshot.scheduled_by == "x"

    c.set_windows(NOW, [window("x", 600, 645)], configured={"x"})
    stopped = c.tick(NOW)

    assert stopped == [Arm(NOW + minutes(600)), TurnOff(), Changed()]
    assert c.snapshot.end is None
    assert c.snapshot.scheduled_by is None
    assert c.snapshot.pending == "off"


def test_realign_that_stops_drops_the_settings_that_are_owed() -> None:
    """The timer is over, so what it was to run with is no longer owed."""
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 0, 45, COOL24)], configured={"x"})
    c.tick(NOW)
    assert c.snapshot.owed_settings == COOL24

    c.set_windows(NOW, [window("x", 600, 645)], configured={"x"})
    c.tick(NOW)

    assert c.snapshot.owed_settings == NO_SETTINGS


def test_realign_after_a_move_ahead_stops_then_starts_at_the_new_start() -> None:
    """S2: the window was moved to start later than now, so the target stops now and
    runs from the new start."""
    c = following(
        "strict", "on", window("x", -15, 45, started=True), end=NOW + minutes(45)
    )

    c.set_windows(NOW, [window("x", 20, 80)], configured={"x"})
    stopped = c.tick(NOW)

    assert stopped == [Arm(NOW + minutes(20)), TurnOff(), Changed()]
    c.observe(NOW + minutes(1), "off", by_us=True)

    started = c.tick(NOW + minutes(20))

    assert started == [Arm(NOW + minutes(80)), TurnOn(), Changed()]
    assert c.snapshot.end == NOW + minutes(80)
    assert c.snapshot.scheduled_by == "x"


def overlapping() -> TimerCore:
    """Two intervals started in turn: a (07:00 to 08:00) and b (07:30 to 09:00), whose
    end the timer carries."""
    c = core("strict", "on")
    c.set_windows(
        NOW,
        [window("a", 0, 60), window("b", 30, 120)],
        configured={"a", "b"},
    )
    c.tick(NOW)
    c.tick(NOW + minutes(30))
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(120), "b")
    return c


def test_removing_the_interval_that_carries_the_end_hands_the_timer_to_the_other() -> (
    None
):
    """S2 stops the timer only when no window is open: with a still open, the target
    keeps running to a's end, which a now carries."""
    c = overlapping()

    c.set_windows(
        NOW + minutes(40), [window("a", 0, 60, started=True)], configured={"a"}
    )
    fx = c.tick(NOW + minutes(40))

    assert fx == [Arm(NOW + minutes(60)), Changed()]
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(60), "a")


def test_shortening_the_interval_that_carries_the_end_follows_the_latest_open_one() -> (
    None
):
    c = overlapping()

    c.set_windows(
        NOW + minutes(40),
        [window("a", 0, 60, started=True), window("b", 30, 50, started=True)],
        configured={"a", "b"},
    )
    c.tick(NOW + minutes(40))

    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(60), "a")


def test_shortening_the_carrier_to_a_later_end_than_the_other_keeps_it() -> None:
    c = overlapping()

    c.set_windows(
        NOW + minutes(40),
        [window("a", 0, 60, started=True), window("b", 30, 90, started=True)],
        configured={"a", "b"},
    )
    fx = c.tick(NOW + minutes(40))

    assert fx == [Arm(NOW + minutes(60)), Changed()]  # a's window still ends first
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(90), "b")


def a_carries_b_is_open() -> TimerCore:
    """Interval a (07:00 to 08:00) carries the timer; b (07:30 to 07:50) started while
    it ran and was left alone."""
    c = core("strict", "on")
    c.set_windows(NOW, [window("a", 0, 60), window("b", 30, 50)], configured={"a", "b"})
    c.tick(NOW)
    c.tick(NOW + minutes(30))
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(60), "a")
    return c


def test_extending_an_interval_that_does_not_carry_the_end_takes_the_timer() -> None:
    """A schedule-owned timer ends with the latest open window, whichever interval it
    was edited in: b, open until 07:50, is extended to 09:00 at 07:40."""
    c = a_carries_b_is_open()

    c.set_windows(
        NOW + minutes(40),
        [window("a", 0, 60), window("b", 30, 120)],
        configured={"a", "b"},
    )
    fx = c.tick(NOW + minutes(40))

    assert fx == [Arm(NOW + minutes(60)), Changed()]
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(120), "b")


def test_shortening_an_interval_that_does_not_carry_the_end_leaves_the_timer() -> None:
    c = overlapping()

    c.set_windows(
        NOW + minutes(40),
        [window("a", 0, 45), window("b", 30, 120)],
        configured={"a", "b"},
    )

    assert c.tick(NOW + minutes(40)) == []
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(120), "b")


def test_a_manual_timer_is_not_realigned_when_an_open_window_is_edited() -> None:
    """S3: once the timer was changed by hand, no edit of any interval touches it."""
    c = core("strict", "on")
    c.set_windows(NOW, [window("x", 0, 60)], configured={"x"})
    c.tick(NOW)
    c.add(NOW + minutes(10), minutes(30))
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(90), None)

    c.set_windows(NOW + minutes(20), [window("x", 0, 150)], configured={"x"})

    assert c.tick(NOW + minutes(20)) == []
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(90), None)


def test_the_carriers_window_end_hands_the_timer_to_the_open_window_that_lasts() -> (
    None
):
    """The carrier's window ends at 08:00 while b, extended since, is open until
    09:00: the target keeps running to b's end and b is not suppressed, though the
    timer's own end falls at the same instant (the window end goes first)."""
    c = a_carries_b_is_open()
    c.set_windows(
        NOW + minutes(40),
        [window("a", 0, 60), window("b", 30, 120)],
        configured={"a", "b"},
    )

    fx = c.tick(NOW + minutes(60))

    assert fx == [Arm(NOW + minutes(120)), Changed()]
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(120), "b")
    assert c.snapshot.windows == (window("b", 30, 120, started=True),)
    assert c.snapshot.pending is None


def test_hand_over_at_a_window_end_is_judged_as_of_that_instant() -> None:
    """Home Assistant was down until 08:40: a's window ended at 08:00 while b (extended
    since) was open until 08:10, and c opened at 08:05 in between. As of 08:00 the
    target kept running, so c pushes no settings onto it."""
    c = TimerCore(
        "strict",
        minutes(45),
        Snapshot(
            end=NOW + minutes(60),
            scheduled_by="a",
            windows=(
                window("a", 0, 60, started=True),
                window("b", 30, 70, started=True),
                window("c", 65, 120, HEAT22),
            ),
            last_actual="on",
        ),
    )

    fx = c.tick(NOW + minutes(100))

    assert fx == [Arm(NOW + minutes(120)), Changed()]
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(120), "c")
    assert c.snapshot.owed_settings == NO_SETTINGS


def test_a_hand_over_found_after_downtime_turns_a_target_that_is_off_back_on() -> None:
    """a's window ended at 08:00 while c, extended since, was open until 09:00; Home
    Assistant is back at 08:40 and finds the boiler off. The hand over is what is due:
    the timer goes on to c's end and the boiler is turned on, not read as someone
    switching it off (R3)."""
    c = TimerCore(
        "strict",
        minutes(45),
        Snapshot(
            end=NOW + minutes(60),
            scheduled_by="a",
            windows=(
                window("a", 0, 60, started=True),
                window("c", 30, 120, started=True),
            ),
        ),
    )

    fx = c.observe(NOW + minutes(100), "off", by_us=False)

    assert fx == [Arm(NOW + minutes(120)), TurnOn(), Changed()]
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(120), "c")
    assert c.snapshot.pending == "on"
    assert not any(w.suppressed for w in c.snapshot.windows)


def test_the_carriers_window_end_with_no_other_window_open_turns_the_target_off() -> (
    None
):
    c = core("strict", "on")
    c.set_windows(
        NOW, [window("a", 0, 60), window("c", 100, 160)], configured={"a", "c"}
    )
    c.tick(NOW)

    fx = c.tick(NOW + minutes(60))

    assert fx == [Arm(NOW + minutes(100)), TurnOff(), Changed()]
    assert c.snapshot.end is None
    assert c.snapshot.scheduled_by is None


def test_window_starting_as_the_carrier_ends_extends_without_flap_or_settings() -> None:
    """At 07:30 a ends and b opens: the timer goes on to b's end, nothing is switched,
    and b pushes no settings onto a target that is running."""
    c = core("strict", "on")
    c.set_windows(
        NOW,
        [window("a", 0, 30), window("b", 30, 75, HEAT22)],
        configured={"a", "b"},
    )
    c.tick(NOW)

    fx = c.tick(NOW + minutes(30))

    assert fx == [Arm(NOW + minutes(75)), Changed()]
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(75), "b")
    assert c.snapshot.owed_settings == NO_SETTINGS


def test_a_window_opening_at_a_hand_over_owes_its_settings_to_an_away_ac() -> None:
    """a ends at 07:30 as b opens, while the AC is away. Nothing is known to run, so
    b's settings are owed to the turn-on that waits for the AC, as a window that opens
    on its own would owe them. (Were b taken for open before its start is folded, the
    hand over would give it the timer without ever owing its settings.)"""
    c = following(
        "strict",
        "unavailable",
        window("a", 0, 30, started=True),
        window("b", 30, 75, HEAT22),
        end=NOW + minutes(30),
    )

    c.tick(NOW + minutes(30))

    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(75), "b")
    assert c.snapshot.owed_settings == HEAT22
    assert c.snapshot.owed_turn_on_only
    back = c.observe(NOW + minutes(31), "off", by_us=False)
    assert back == [TurnOn(HEAT22), Changed()]


def test_shortening_the_carrier_to_where_the_other_ends_keeps_it_the_carrier() -> None:
    """On a tie the interval that was edited stays the one S2 follows."""
    c = overlapping()

    c.set_windows(
        NOW + minutes(40),
        [window("a", 0, 60, started=True), window("b", 30, 60, started=True)],
        configured={"a", "b"},
    )
    c.tick(NOW + minutes(40))

    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(60), "b")


def test_a_window_that_starts_after_the_stop_is_handed_the_timer() -> None:
    """Only windows that had started when the target was switched off are suppressed
    (S4): c, which starts later, is as good as any."""
    c = core("strict", "on")
    c.set_windows(
        NOW,
        [window("a", 0, 60), window("b", 30, 120), window("c", 35, 100)],
        configured={"a", "b", "c"},
    )
    c.tick(NOW)
    c.observe(NOW + minutes(10), "off", by_us=False)
    c.tick(NOW + minutes(30))
    c.tick(NOW + minutes(35))
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(120), "b")

    c.set_windows(
        NOW + minutes(40),
        [window("a", 0, 60), window("c", 35, 100)],
        configured={"a", "c"},
    )
    c.tick(NOW + minutes(40))

    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(100), "c")


def test_removing_the_only_open_interval_stops_the_timer() -> None:
    """The other interval is not open yet, so there is nothing to hand the timer to."""
    c = overlapping()

    c.set_windows(
        NOW + minutes(40),
        [window("a", 100, 160)],
        configured={"a"},
    )
    fx = c.tick(NOW + minutes(40))

    assert fx == [Arm(NOW + minutes(100)), TurnOff(), Changed()]
    assert c.snapshot.end is None
    assert c.snapshot.scheduled_by is None


def test_a_window_that_was_stopped_is_not_handed_the_timer() -> None:
    """S4: the user switched the target off during a, so a stays off however b comes
    and goes."""
    c = core("strict", "on")
    c.set_windows(
        NOW, [window("a", 0, 60), window("b", 30, 120)], configured={"a", "b"}
    )
    c.tick(NOW)
    c.observe(NOW + minutes(10), "off", by_us=False)
    c.tick(NOW + minutes(30))
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(120), "b")

    c.set_windows(NOW + minutes(40), [window("a", 0, 90)], configured={"a"})
    fx = c.tick(NOW + minutes(40))

    assert TurnOff() in fx
    assert c.snapshot.end is None
    assert c.snapshot.scheduled_by is None


def test_the_timer_changes_hands_without_a_wish_when_both_windows_end_together() -> (
    None
):
    """The carrier is gone, but the other window ends with it: the timer does not move,
    b carries it from now on, and S2 follows b's edits."""
    c = core("strict", "on")
    c.set_windows(NOW, [window("a", 0, 60), window("b", 30, 60)], configured={"a", "b"})
    c.tick(NOW)
    c.tick(NOW + minutes(30))
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(60), "a")

    c.set_windows(
        NOW + minutes(40), [window("b", 30, 60, started=True)], configured={"b"}
    )
    fx = c.tick(NOW + minutes(40))

    assert fx == [Changed()]
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(60), "b")


def test_a_new_window_that_is_open_now_does_not_start_again_after_an_edit() -> None:
    """The same occurrence, edited, was started already: a timer the user changed
    stays as they left it (S3)."""
    c = core("strict", "on")
    c.set_windows(NOW, [window("x", 0, 60)], configured={"x"})
    c.tick(NOW)
    c.set_duration(NOW + minutes(10), minutes(5))

    c.set_windows(NOW + minutes(10), [window("x", -30, 90)], configured={"x"})

    assert c.snapshot.windows[0].started
    assert c.tick(NOW + minutes(10)) == []
    assert c.snapshot.end == NOW + minutes(15)


def test_a_new_window_that_is_not_open_now_is_a_new_occurrence() -> None:
    """Only an occurrence that is open now is the one that started: moved away from
    now, it is a new one and starts at its start (S2)."""
    c = following("strict", "on", window("x", -15, 45, started=True))

    c.set_windows(NOW, [window("x", 20, 80)], configured={"x"})

    assert not c.snapshot.windows[0].started


def _due_on_command(c: TimerCore) -> datetime:
    c.add_command(NOW, cmd(10, minutes=30))
    c.tick(NOW + minutes(10))
    return NOW + minutes(10)


def _due_off_command(c: TimerCore) -> datetime:
    c.add_command(NOW, cmd(10, "off"))
    c.tick(NOW + minutes(10))
    return NOW + minutes(10)


def _end_reached(c: TimerCore) -> datetime:
    c.tick(NOW + minutes(60))
    return NOW + minutes(60)


def _at_now(change: Callable[[TimerCore], object]) -> Callable[[TimerCore], datetime]:
    def change_at_now(c: TimerCore) -> datetime:
        change(c)
        return NOW

    return change_at_now


@pytest.mark.parametrize(
    ("mode", "change"),
    [
        pytest.param(
            "strict", _at_now(lambda c: c.set_duration(NOW, minutes(30))), id="set"
        ),
        pytest.param(
            "strict", _at_now(lambda c: c.add(NOW, minutes(10))), id="add-plus"
        ),
        pytest.param(
            "strict", _at_now(lambda c: c.add(NOW, minutes(-10))), id="add-minus"
        ),
        pytest.param("strict", _at_now(lambda c: c.stop(NOW)), id="stop"),
        pytest.param("strict", _due_on_command, id="due-on-command"),
        pytest.param("strict", _due_off_command, id="due-off-command"),
        pytest.param(
            "strict",
            _at_now(lambda c: c.observe(NOW, "off", by_us=False)),
            id="manual-off",
        ),
        pytest.param("strict", _end_reached, id="end-reached"),
    ],
)
def test_every_other_change_ends_realignment(
    mode: Mode, change: Callable[[TimerCore], datetime]
) -> None:
    """S3: once anyone but the schedule changes the timer (a command that is due is
    the same as setting it by hand, P3), editing the interval no longer touches it. A
    run without a duration of a target that is running changes nothing, so it is not
    here: `test_run_open_leaves_the_schedule_in_charge_of_its_countdown`."""
    c = core(mode, "on")
    c.set_windows(NOW, [window("x", 0, 60)], configured={"x"})
    c.tick(NOW)
    assert c.snapshot.scheduled_by == "x"

    changed_at = change(c)

    assert c.snapshot.scheduled_by is None
    end = c.snapshot.end
    shorter = Window(
        "x", changed_at - minutes(10), changed_at + minutes(10), started=True
    )
    c.set_windows(changed_at, [shorter], configured={"x"})
    c.tick(changed_at)
    assert c.snapshot.end == end
    assert c.snapshot.scheduled_by is None


def test_target_off_during_a_window_stays_off_until_the_next_window() -> None:
    """S4: the window that was turned off by hand does not turn the target on again,
    not even when the interval is edited; the next occurrence does."""
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 0, 45)], configured={"x"})
    c.tick(NOW)
    c.observe(NOW, "on", by_us=True)
    c.observe(NOW + minutes(10), "off", by_us=False)
    assert c.snapshot.end is None

    c.set_windows(NOW + minutes(10), [window("x", 0, 45)], configured={"x"})

    assert c.snapshot.windows[0].started
    assert c.tick(NOW + minutes(10)) == []
    assert c.tick(NOW + minutes(45)) == [Disarm(), Changed()]

    c.set_windows(NOW + minutes(45), [window("x", 1440, 1485)], configured={"x"})
    fx = c.tick(NOW + minutes(1440))

    assert fx == [Arm(NOW + minutes(1485)), TurnOn(), Changed()]


@pytest.mark.parametrize(
    "stop",
    [
        pytest.param(lambda c: c.stop(NOW + minutes(10)), id="stop"),
        pytest.param(
            lambda c: c.set_duration(NOW + minutes(10), timedelta(0)), id="run-for-zero"
        ),
        pytest.param(
            lambda c: (
                c.add_command(NOW, cmd(10, "off")),
                c.tick(NOW + minutes(10)),
            ),
            id="off-command",
        ),
    ],
)
def test_any_stop_during_a_window_keeps_the_target_off_until_the_next_window(
    stop: Callable[[TimerCore], object],
) -> None:
    """S4 is not only about the target switched off by hand: whoever zeroes the timer
    during a window, the window does not turn it on again (not even after an edit)."""
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 0, 45)], configured={"x"})
    c.tick(NOW)
    c.observe(NOW, "on", by_us=True)

    stop(c)

    assert c.snapshot.end is None
    c.set_windows(NOW + minutes(10), [window("x", 0, 45)], configured={"x"})
    assert c.tick(NOW + minutes(10)) == []
    assert c.tick(NOW + minutes(45)) == [Disarm(), Changed()]
    c.set_windows(NOW + minutes(45), [window("x", 1440, 1485)], configured={"x"})
    assert c.tick(NOW + minutes(1440)) == [
        Arm(NOW + minutes(1485)),
        TurnOn(),
        Changed(),
    ]


def test_restored_started_window_does_not_start_again() -> None:
    """§5.7: a restart does not bring back a window that was started already, whatever
    became of the timer since."""
    c = TimerCore(
        "strict",
        minutes(45),
        Snapshot(windows=(window("x", 0, 45, started=True),)),
    )

    fx = c.observe(NOW, "off", by_us=False)

    assert fx == [Changed()]
    assert c.snapshot.end is None


def idle_in_a_window(
    mode: Mode, default: int, *windows: Window, actual: Actual = "off"
) -> TimerCore:
    """A core with no countdown and `windows` that have started, with a default duration
    of `default` minutes: the state in which a person switches the target on by hand
    while a window is open."""
    return TimerCore(
        mode, minutes(default), Snapshot(windows=windows, last_actual=actual)
    )


def test_manual_on_during_a_window_runs_to_its_end() -> None:
    """#58: a target switched on by hand while a window is open runs to the window's
    end, which is later than the end of the default duration. The run is the user's
    (S3): no interval carries it."""
    c = idle_in_a_window("strict", 20, window("x", 0, 45, started=True))

    fx = c.observe(NOW + minutes(10), "on", by_us=False)

    assert fx == [Arm(NOW + minutes(45)), Changed()]
    assert c.snapshot.end == NOW + minutes(45)
    assert c.snapshot.started_at == NOW + minutes(10)
    assert c.snapshot.scheduled_by is None


def test_manual_on_during_a_window_keeps_a_default_duration_that_ends_later() -> None:
    """The window never shortens a run: the default duration of 45 minutes from ten
    past ends after the window does."""
    c = idle_in_a_window("strict", 45, window("x", 0, 45, started=True))

    c.observe(NOW + minutes(10), "on", by_us=False)

    assert c.snapshot.end == NOW + minutes(55)
    assert c.snapshot.scheduled_by is None


def test_manual_on_in_loose_during_a_window_gets_a_countdown_to_its_end() -> None:
    """Loose mode gives a target that is switched on by hand no countdown, but one that
    runs inside a window has one to the window's end, announced as a start."""
    c = idle_in_a_window("loose", 20, window("x", 0, 45, started=True))

    fx = c.observe(NOW + minutes(10), "on", by_us=False)

    assert fx == [Arm(NOW + minutes(45)), Changed()]
    assert c.snapshot.end == NOW + minutes(45)
    assert c.snapshot.started_at == NOW + minutes(10)
    assert c.snapshot.scheduled_by is None
    assert c.take_announcements() == [CountdownStarted(NOW + minutes(45))]


@pytest.mark.parametrize("mode", ["strict", "loose"])
def test_manual_on_after_a_manual_off_in_a_window_runs_to_its_end(mode: Mode) -> None:
    """S4 holds the target off after a manual off, but the window still counts as open
    for the next turn-on by hand, which runs to its end and leaves the mark of the
    window alone: nothing but the next occurrence turns the target on by itself."""
    c = TimerCore(mode, minutes(20), Snapshot(last_actual="off"))
    c.set_windows(NOW, [window("x", 0, 45)], configured={"x"})
    c.tick(NOW)
    c.observe(NOW, "on", by_us=True)
    c.observe(NOW + minutes(10), "off", by_us=False)
    assert c.snapshot.end is None
    assert c.snapshot.windows[0].suppressed

    c.observe(NOW + minutes(20), "on", by_us=False)

    assert c.snapshot.end == NOW + minutes(45)
    assert c.snapshot.scheduled_by is None
    assert c.snapshot.windows[0].suppressed
    assert c.tick(NOW + minutes(45)) == [Disarm(), TurnOff(), Changed()]


def test_manual_on_inside_overlapping_windows_runs_to_the_latest_end() -> None:
    """With two windows open the run ends with the later one; a window that is over, and
    one that has not opened, are not counted."""
    c = idle_in_a_window(
        "strict",
        20,
        window("over", -60, -10, started=True),
        window("a", 0, 60, started=True),
        window("b", 30, 120, started=True),
        window("later", 90, 180),
    )

    c.observe(NOW + minutes(40), "on", by_us=False)

    assert c.snapshot.end == NOW + minutes(120)
    assert c.snapshot.scheduled_by is None


@pytest.mark.parametrize(
    ("mode", "end"), [("strict", NOW + minutes(55)), ("loose", None)]
)
def test_manual_on_before_a_window_opens_is_as_it_always_was(
    mode: Mode, end: datetime | None
) -> None:
    """A window that opens later is no window yet: the default duration in Strict mode,
    no countdown in Loose mode."""
    c = idle_in_a_window(mode, 45, window("x", 30, 75))

    c.observe(NOW + minutes(10), "on", by_us=False)

    assert c.snapshot.end == end


@pytest.mark.parametrize(
    ("mode", "end"), [("strict", NOW + minutes(55)), ("loose", None)]
)
def test_manual_on_as_a_window_closes_is_as_it_always_was(
    mode: Mode, end: datetime | None
) -> None:
    """A window is open until the instant of its end, not at it."""
    c = idle_in_a_window(mode, 45, window("x", -30, 10, started=True))

    c.observe(NOW + minutes(10), "on", by_us=False)

    assert c.snapshot.end == end


def test_manual_on_while_a_countdown_runs_in_a_window_changes_nothing() -> None:
    """Only a target with no countdown gets one: a run of the user's own keeps its end
    when the target is reported on."""
    c = TimerCore(
        "strict",
        minutes(20),
        Snapshot(windows=(window("x", 0, 45, started=True),), last_actual="off"),
    )
    c.set_duration(NOW + minutes(10), minutes(5))

    c.observe(NOW + minutes(11), "on", by_us=False)

    assert c.snapshot.end == NOW + minutes(15)


def test_a_report_as_a_window_opens_leaves_the_window_in_charge() -> None:
    """The window that opens in the instant of the report sets the timer first, so the
    turn-on seen with it is not followed: the interval carries the run."""
    c = TimerCore("strict", minutes(20), Snapshot(last_actual="off"))
    c.set_windows(NOW, [window("x", 10, 45)], configured={"x"})

    c.observe(NOW + minutes(10), "on", by_us=False)

    assert c.snapshot.end == NOW + minutes(45)
    assert c.snapshot.scheduled_by == "x"


@pytest.mark.parametrize("before", [None, "unavailable"])
@pytest.mark.parametrize("mode", ["strict", "loose"])
def test_a_target_found_on_inside_a_window_runs_to_its_end(
    mode: Mode, before: Actual | None
) -> None:
    """A target seen on for the first time, at start-up or back from unavailable, is
    followed like one switched on from outside: inside a window it runs to its end."""
    c = TimerCore(
        mode,
        minutes(20),
        Snapshot(
            windows=(window("x", 0, 45, started=True, suppressed=True),),
            last_actual=before,
        ),
    )

    c.observe(NOW + minutes(10), "on", by_us=False)

    assert c.snapshot.end == NOW + minutes(45)
    assert c.snapshot.scheduled_by is None


@pytest.mark.parametrize("mode", ["strict", "loose"])
def test_run_open_inside_a_window_runs_to_its_end(mode: Mode) -> None:
    """A turn-on without a duration is the same act as one by hand, so it runs to the
    window's end too. It is still the user's run."""
    c = idle_in_a_window(mode, 20, window("x", 0, 45, started=True, suppressed=True))

    fx = c.run_open(NOW + minutes(10))

    assert fx == [Arm(NOW + minutes(45)), TurnOn(), Changed()]
    assert c.snapshot.end == NOW + minutes(45)
    assert c.snapshot.started_at == NOW + minutes(10)
    assert c.snapshot.scheduled_by is None


def test_run_open_inside_a_window_sets_its_settings() -> None:
    """The settings of a bare turn-on go with it, as with one that names a duration."""
    c = idle_in_a_window("loose", 20, window("x", 0, 45, started=True))

    fx = c.run_open(NOW + minutes(10), COOL24)

    assert fx == [Arm(NOW + minutes(45)), TurnOn(COOL24), Changed()]
    assert c.snapshot.owed_settings == COOL24


def test_run_open_inside_a_window_keeps_what_a_running_target_has() -> None:
    """A target that is wanted running keeps its countdown, in a window too."""
    c = TimerCore("strict", minutes(20), Snapshot(last_actual="off"))
    c.set_windows(NOW, [window("x", 0, 45)], configured={"x"})
    c.tick(NOW)
    c.observe(NOW, "on", by_us=True)
    c.set_duration(NOW + minutes(5), minutes(10))

    fx = c.run_open(NOW + minutes(8))

    assert fx == []
    assert c.snapshot.end == NOW + minutes(15)


@pytest.mark.parametrize("mode", ["strict", "loose"])
def test_a_command_to_turn_on_without_minutes_inside_a_window_runs_to_its_end(
    mode: Mode,
) -> None:
    """A pending turn-on with no duration is a bare turn-on when it falls due, so it
    runs to the end of the window that is open then."""
    c = TimerCore(
        mode,
        minutes(20),
        Snapshot(
            windows=(window("x", 0, 45, started=True, suppressed=True),),
            commands=(cmd(10),),
            last_actual="off",
        ),
    )

    fx = c.tick(NOW + minutes(10))

    assert fx == [Arm(NOW + minutes(45)), TurnOn(), Changed()]
    assert c.snapshot.end == NOW + minutes(45)
    assert c.snapshot.started_at == NOW + minutes(10)
    assert c.snapshot.scheduled_by is None


def test_a_command_to_turn_on_with_minutes_inside_a_window_keeps_them() -> None:
    """A duration that is named is kept, whatever the window says."""
    c = TimerCore(
        "strict",
        minutes(20),
        Snapshot(
            windows=(window("x", 0, 45, started=True),),
            commands=(cmd(10, minutes=5),),
            last_actual="off",
        ),
    )

    c.tick(NOW + minutes(10))

    assert c.snapshot.end == NOW + minutes(15)


def test_a_late_command_to_turn_on_runs_to_the_end_of_the_window_it_fell_in() -> None:
    """A command that came due ten minutes in and is found forty minutes in would have
    run for twenty minutes and be over; the window it fell in is open until the 45th, so
    the run goes on to there."""
    c = TimerCore(
        "strict",
        minutes(20),
        Snapshot(
            windows=(window("x", 0, 45, started=True),),
            commands=(cmd(10),),
            last_actual="off",
        ),
    )

    c.tick(NOW + minutes(40))

    assert c.snapshot.end == NOW + minutes(45)


@pytest.mark.parametrize("mode", ["strict", "loose"])
def test_a_late_command_whose_window_has_ended_too_is_dropped(mode: Mode) -> None:
    """The same command found after the window that was open at its time has ended:
    nothing is left of its run, so it is dropped, in Loose mode as well."""
    c = TimerCore(
        mode,
        minutes(20),
        Snapshot(
            windows=(window("x", 0, 45, started=True),),
            commands=(cmd(10),),
            last_actual="off",
        ),
    )

    fx = c.tick(NOW + minutes(50))

    assert CommandDropped(cmd(10)) in fx
    assert c.snapshot.end is None
    assert c.snapshot.commands == ()


def test_overlapping_windows_follow_the_later_end() -> None:
    """The timer's end follows S1 for each start, and the interval whose end it carries
    is the one S2 follows."""
    c = core("strict", "on")
    c.set_windows(
        NOW, [window("a", 0, 60), window("b", 30, 120)], configured={"a", "b"}
    )
    c.tick(NOW)
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(60), "a")

    c.tick(NOW + minutes(30))
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(120), "b")

    c.set_windows(
        NOW + minutes(30),
        [window("a", 0, 90), window("b", 30, 120)],
        configured={"a", "b"},
    )

    assert c.tick(NOW + minutes(30)) == []
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(120), "b")


def test_command_at_a_window_start_wins() -> None:
    """P3: an on-command is the same as setting the timer by hand, so it moves the
    timer after the window that opens at the same moment."""
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 5, 45)], configured={"x"})
    c.add_command(NOW, cmd(5, minutes=10))

    fx = c.tick(NOW + minutes(5))

    assert fx == [Arm(NOW + minutes(15)), TurnOn(), Changed()]
    assert c.snapshot.end == NOW + minutes(15)
    assert c.snapshot.scheduled_by is None
    assert c.snapshot.commands == ()


def test_window_start_at_the_timer_end_extends_without_flap() -> None:
    """A window that opens as the timer ends carries it on: no off, then on."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(30))
    c.set_windows(NOW, [window("x", 30, 75)], configured={"x"})

    fx = c.tick(NOW + minutes(30))

    assert fx == [Arm(NOW + minutes(75)), Changed()]
    assert c.snapshot.end == NOW + minutes(75)
    assert c.snapshot.scheduled_by == "x"


def test_tie_order_at_one_instant() -> None:
    """One window ends, another starts, an off-command and the end of the timer all
    fall at 07:30: they go in that order, the target is asked once, to be off."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(30))
    c.set_windows(
        NOW,
        [window("a", 0, 30, started=True), window("b", 30, 75)],
        configured={"a", "b"},
    )
    c.add_command(NOW, cmd(30, "off"))

    fx = c.tick(NOW + minutes(30))

    assert fx == [Arm(NOW + minutes(75)), TurnOff(), Changed()]
    assert c.snapshot.end is None
    assert c.snapshot.scheduled_by is None
    assert c.snapshot.windows == (window("b", 30, 75, started=True, suppressed=True),)


def test_fold_across_window_end_and_next_start_has_one_wish() -> None:
    """Home Assistant was down overnight: Monday's window ended and Tuesday's has
    started since. The target stays on; it is not switched off and on again."""
    monday = window("x", -30, 15, started=True)
    c = TimerCore(
        "strict",
        minutes(45),
        Snapshot(
            end=NOW + minutes(15),
            scheduled_by="x",
            windows=(monday,),
            last_actual="on",
        ),
    )
    tuesday = window("x", 1410, 1455)
    c.set_windows(NOW + minutes(1425), [tuesday], configured={"x"})

    fx = c.observe(NOW + minutes(1425), "on", by_us=False)

    assert fx == [Arm(NOW + minutes(1455)), Changed()]
    assert c.snapshot.end == NOW + minutes(1455)
    assert c.snapshot.scheduled_by == "x"
    assert c.snapshot.pending is None


def test_fold_across_window_end_and_next_start_pushes_no_settings_onto_the_target() -> (
    None
):
    """The same night with a window that carries settings: the timer ended and the
    next window opened in one fold, which sees the target as wanted off at that
    moment, but it stayed on all night and nobody asked it to turn on."""
    monday = window("x", -30, 15, started=True)
    c = TimerCore(
        "strict",
        minutes(45),
        Snapshot(
            end=NOW + minutes(15),
            scheduled_by="x",
            windows=(monday,),
            last_actual="on",
        ),
    )
    tuesday = window("x", 1410, 1455, COOL24)
    c.set_windows(NOW + minutes(1425), [tuesday], configured={"x"})

    fx = c.observe(NOW + minutes(1425), "on", by_us=False)

    assert fx == [Arm(NOW + minutes(1455)), Changed()]
    assert c.snapshot.end == NOW + minutes(1455)
    assert c.snapshot.scheduled_by == "x"
    assert c.snapshot.pending is None
    assert c.snapshot.owed_settings == NO_SETTINGS
    assert not c.snapshot.owed_turn_on_only


def test_window_start_that_leaves_the_timer_alone_lets_a_manual_off_clear_it() -> None:
    """A window that moved nothing does not hide R3 from the report that came along."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(60))
    c.set_windows(NOW, [window("x", 5, 45)], configured={"x"})

    c.observe(NOW + minutes(5), "off", by_us=False)

    assert c.snapshot.end is None
    assert c.snapshot.pending is None


def test_window_end_alone_lets_a_manual_on_start_the_default_duration() -> None:
    """A window that only ended did not move the timer, so R4 still gives a target
    found running its default countdown."""
    c = TimerCore(
        "strict",
        minutes(45),
        Snapshot(windows=(window("x", -45, -5, started=True),), last_actual="off"),
    )

    c.observe(NOW, "on", by_us=False)

    assert c.snapshot.end == NOW + minutes(45)
    assert c.snapshot.windows == ()


def test_realign_that_stops_hides_the_startup_report() -> None:
    """The timer was stopped because its window is gone: the target found running
    after the restart is turned off, not given the default countdown (R4)."""
    c = following(
        "strict", None, window("x", -15, 30, started=True), end=NOW + minutes(30)
    )
    c.set_windows(NOW, [window("x", 600, 645)], configured={"x"})

    fx = c.observe(NOW, "on", by_us=False)

    assert fx == [Arm(NOW + minutes(600)), TurnOff(), Changed()]
    assert c.snapshot.end is None
    assert c.snapshot.scheduled_by is None


def test_kept_window_is_not_realigned() -> None:
    """An interval whose occurrence could not be worked out this time keeps the window
    it has, so the timer it set is left as it is."""
    c = following(
        "strict", "on", window("x", -15, 30, started=True), end=NOW + minutes(30)
    )
    before = c.snapshot

    fx = c.set_windows(NOW, [], configured={"x"}, keep={"x"})

    assert fx == [Arm(NOW + minutes(30))]
    assert c.snapshot == before
    assert c.tick(NOW) == []


def test_kept_window_that_is_not_started_still_starts() -> None:
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 30, 75)], configured={"x"})

    c.set_windows(NOW, [], configured={"x"}, keep={"x"})

    assert c.tick(NOW + minutes(30)) == [Arm(NOW + minutes(75)), TurnOn(), Changed()]


def test_kept_window_wins_over_a_new_one() -> None:
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 30, 75)], configured={"x"})

    c.set_windows(NOW, [window("x", 90, 120)], configured={"x"}, keep={"x"})

    assert c.snapshot.windows == (window("x", 30, 75),)


def test_configured_beats_keep() -> None:
    """An interval that no longer exists loses its window even when its occurrence
    could not be worked out this time, and the timer that window carried stops."""
    c = following(
        "strict", "on", window("x", -15, 30, started=True), end=NOW + minutes(30)
    )

    c.set_windows(NOW, [], configured=set(), keep={"x"})
    fx = c.tick(NOW)

    assert c.snapshot.windows == ()
    assert fx == [Disarm(), TurnOff(), Changed()]


def test_window_of_an_unconfigured_interval_is_dropped_and_its_timer_stops() -> None:
    """An interval that no longer exists takes its window with it, and the timer that
    carried the window's end stops (S2)."""
    c = following(
        "strict", "on", window("x", -15, 30, started=True), end=NOW + minutes(30)
    )

    c.set_windows(NOW, [window("x", -15, 30)], configured=set())
    fx = c.tick(NOW)

    assert c.snapshot.windows == ()
    assert fx == [Disarm(), TurnOff(), Changed()]
    assert c.snapshot.end is None


def test_only_the_windows_of_unconfigured_intervals_are_dropped() -> None:
    c = core("strict", "off")
    c.set_windows(
        NOW, [window("x", 10, 20), window("y", 30, 40)], configured={"x", "y"}
    )

    c.set_windows(NOW, [window("x", 10, 20), window("y", 30, 40)], configured={"y"})

    assert [w.interval_id for w in c.snapshot.windows] == ["y"]


def test_tick_with_nothing_due_and_an_aligned_schedule_returns_nothing() -> None:
    """The stale tick of phase 2, with a schedule the timer already follows."""
    c = following(
        "strict", "on", window("x", -15, 30, started=True), end=NOW + minutes(30)
    )
    before = c.snapshot

    assert c.tick(NOW) == []
    assert c.snapshot == before


@pytest.mark.parametrize(
    ("snapshot", "expected"),
    [
        pytest.param(Snapshot(), None, id="nothing"),
        pytest.param(
            Snapshot(windows=(window("x", 30, 75),)), NOW + minutes(30), id="start"
        ),
        pytest.param(
            Snapshot(windows=(window("x", 30, 75, started=True),)),
            NOW + minutes(75),
            id="end-of-a-started-window",
        ),
        pytest.param(
            Snapshot(
                end=NOW + minutes(45),
                windows=(window("x", 20, 75),),
            ),
            NOW + minutes(20),
            id="start-before-the-end",
        ),
        pytest.param(
            Snapshot(
                end=NOW + minutes(45),
                windows=(window("x", -20, 10, started=True),),
            ),
            NOW + minutes(10),
            id="window-end-before-the-end",
        ),
        pytest.param(
            Snapshot(
                end=NOW + minutes(45),
                commands=(cmd(25),),
                windows=(window("x", 30, 75), window("y", -20, 40, started=True)),
            ),
            NOW + minutes(25),
            id="command-first",
        ),
        pytest.param(
            Snapshot(
                end=NOW + minutes(15),
                windows=(window("x", 30, 75), window("y", 20, 25)),
            ),
            NOW + minutes(15),
            id="end-first",
        ),
    ],
)
def test_next_wakeup_includes_window_starts_and_ends(
    snapshot: Snapshot, expected: datetime | None
) -> None:
    assert next_wakeup(snapshot) == expected


# Disabled intervals: the flag is kept in the snapshot, and disabling is an edit for S2.


def test_disabling_the_scheduling_interval_stops_the_timer() -> None:
    """S2: the interval whose window carries the timer is switched off, so the window
    is gone and the timer, which nobody changed by hand, stops with it."""
    c = following(
        "strict", "on", window("x", -15, 45, started=True), end=NOW + minutes(45)
    )

    disabled = c.set_interval_enabled(NOW, "x", False)

    assert disabled == [Arm(NOW + minutes(45)), Changed()]
    assert c.snapshot.disabled_intervals == frozenset({"x"})
    assert c.snapshot.windows == ()
    assert c.snapshot.end == NOW + minutes(45)

    stopped = c.tick(NOW)

    assert stopped == [Disarm(), TurnOff(), Changed()]
    assert c.snapshot.end is None
    assert c.snapshot.scheduled_by is None
    assert c.snapshot.pending == "off"


def test_disabling_takes_only_the_window_of_that_interval() -> None:
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 5, 45), window("y", 30, 75)], configured={"x", "y"})

    fx = c.set_interval_enabled(NOW, "x", False)

    assert fx == [Arm(NOW + minutes(30)), Changed()]
    assert c.snapshot.windows == (window("y", 30, 75),)


def test_disabling_after_a_manual_change_leaves_the_timer() -> None:
    """S3: once the timer was changed by hand, switching an interval off does not touch
    it, whichever interval's window it once followed."""
    c = core("strict", "on")
    c.set_windows(NOW, [window("x", 0, 60)], configured={"x"})
    c.tick(NOW)
    c.add(NOW + minutes(10), minutes(30))

    c.set_interval_enabled(NOW + minutes(20), "x", False)

    assert c.tick(NOW + minutes(20)) == []
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(90), None)


def test_disabling_the_interval_that_carries_the_timer_hands_it_to_the_other() -> None:
    """S2 stops the timer only when no window is open: with a still open, the target
    keeps running to a's end, which a now carries."""
    c = overlapping()

    c.set_interval_enabled(NOW + minutes(40), "b", False)
    fx = c.tick(NOW + minutes(40))

    assert fx == [Arm(NOW + minutes(60)), Changed()]
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(60), "a")


def test_disabling_an_interval_that_does_not_carry_the_timer_leaves_it() -> None:
    c = overlapping()

    c.set_interval_enabled(NOW + minutes(40), "a", False)

    assert c.tick(NOW + minutes(40)) == []
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(120), "b")


def test_disabling_an_interval_whose_window_is_not_open_leaves_the_timer() -> None:
    """A manual run goes on when an interval that was to start later is switched off."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(30))
    c.set_windows(NOW, [window("x", 60, 120)], configured={"x"})

    c.set_interval_enabled(NOW, "x", False)

    assert c.tick(NOW) == []
    assert c.snapshot.end == NOW + minutes(30)
    assert c.snapshot.windows == ()


def test_enabling_forgets_the_flag_and_adds_no_window() -> None:
    """Which window an interval has is worked out by the caller, and merged with
    `set_windows`; the flag alone brings none back."""
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 5, 45)], configured={"x"})
    c.set_interval_enabled(NOW, "x", False)

    fx = c.set_interval_enabled(NOW, "x", True)

    assert fx == [Disarm(), Changed()]
    assert c.snapshot.disabled_intervals == frozenset()
    assert c.snapshot.windows == ()


@pytest.mark.parametrize("enabled", [False, True])
def test_setting_a_flag_to_where_it_is_changes_nothing(enabled: bool) -> None:
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 5, 45)], configured={"x"})
    c.set_interval_enabled(NOW, "x", enabled)
    before = c.snapshot

    fx = c.set_interval_enabled(NOW, "x", enabled)

    assert Changed() not in fx
    assert c.snapshot == before


def test_a_flag_is_kept_by_what_changes_the_timer() -> None:
    c = core("strict", "off")
    c.set_interval_enabled(NOW, "x", False)

    c.set_duration(NOW, minutes(30))
    c.add(NOW, minutes(5))
    c.add_command(NOW, cmd(10))
    c.observe(NOW + minutes(20), "on", by_us=True)
    c.set_duration(NOW + minutes(20), minutes(0))

    assert c.snapshot.disabled_intervals == frozenset({"x"})


def test_disabled_intervals_are_pruned_to_configured() -> None:
    """The flag of an interval that was deleted goes when the windows are merged."""
    c = TimerCore(
        "strict",
        minutes(45),
        Snapshot(disabled_intervals=frozenset({"x", "gone"}), last_actual="off"),
    )

    fx = c.set_windows(NOW, [], configured={"x": None, "y": None}.keys())

    assert fx == [Disarm(), Changed()]
    assert c.snapshot.disabled_intervals == frozenset({"x"})
    assert isinstance(c.snapshot.disabled_intervals, frozenset)


def test_windows_of_disabled_intervals_are_not_kept() -> None:
    """The core holds the invariant: a disabled interval has no window, whoever
    computed one, and whether it asked for the old one to be kept."""
    c = TimerCore(
        "strict",
        minutes(45),
        Snapshot(
            windows=(window("old", 10, 50),),
            disabled_intervals=frozenset({"x", "old"}),
            last_actual="off",
        ),
    )

    fx = c.set_windows(
        NOW,
        [window("x", 5, 45), window("y", 30, 75)],
        configured={"x", "y", "old"},
        keep={"old"},
    )

    assert fx == [Arm(NOW + minutes(30)), Changed()]
    assert c.snapshot.windows == (window("y", 30, 75),)
    assert c.snapshot.disabled_intervals == frozenset({"x", "old"})


# --- A report of our own call that contradicts the timer ---------------------------
#
# A device that confirms after the call returned makes the call count as not delivered
# while it is still on its way. A newer wish that asks for the state the target shows
# is then settled with nothing sent, and the answer to the older call, which comes
# later, leaves the target the opposite of the timer: the core asks again.


def stopped_behind_a_slow_device(mode: Mode) -> TimerCore:
    """A timer that ran a target that is on and was stopped. The device took turn_off
    but has not reported it, so the call counts as not delivered while the target
    reads on."""
    c = core(mode, "on")
    c.set_duration(NOW, minutes(30))
    assert c.stop(NOW) == [Disarm(), TurnOff(), Changed()]
    c.call_failed(NOW)
    return c


@pytest.mark.parametrize("mode", ["strict", "loose"])
def test_run_for_zero_then_run_for_thirty_before_the_device_reports_turns_it_on(
    mode: Mode,
) -> None:
    """ "Run for 0" and at once "Run for 30": the second asks for nothing, as the target
    still reads on. When the report of the first arrives, the target is off while the
    timer runs, and the core turns it on."""
    c = stopped_behind_a_slow_device(mode)

    again = c.set_duration(NOW, minutes(30))
    late = c.observe(NOW + minutes(1), "off", by_us=True)

    assert again == [Arm(NOW + minutes(30)), Changed()]
    assert late == [TurnOn(), Changed()]
    assert c.snapshot.pending == "on"
    assert c.snapshot.end == NOW + minutes(30)
    assert c.observe(NOW + minutes(2), "on", by_us=True) == [Changed()]
    assert c.snapshot == Snapshot(
        end=NOW + minutes(30), started_at=NOW, last_actual="on"
    )


def test_start_then_stop_before_the_device_reports_turns_it_off_in_strict_mode() -> (
    None
):
    """A start and at once a stop: the stop asks for nothing, as the target still reads
    off. When the report of the start arrives, the target runs with the timer at zero,
    which strict mode does not allow, and the core turns it off."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(30))
    c.call_failed(NOW)

    stopped = c.stop(NOW)
    late = c.observe(NOW + minutes(1), "on", by_us=True)

    assert stopped == [Disarm(), Changed()]
    assert late == [TurnOff(), Changed()]
    assert c.snapshot.pending == "off"
    assert c.observe(NOW + minutes(2), "off", by_us=True) == [Changed()]
    assert c.snapshot == Snapshot(last_actual="off")


def test_open_run_then_stop_before_the_device_reports_turns_it_off_in_loose_mode() -> (
    None
):
    """Loose mode allows a target that runs with the timer at zero, but not one that
    the last thing the user did was to stop."""
    c = core("loose", "off")
    c.run_open(NOW)
    c.call_failed(NOW)
    c.stop(NOW)

    late = c.observe(NOW + minutes(1), "on", by_us=True)

    assert late == [TurnOff(), Changed()]


def test_stop_then_open_run_before_the_device_reports_turns_it_on_in_loose_mode() -> (
    None
):
    """The user's last word was to run the target, with no countdown: the timer is at
    zero either way, and the target is to run."""
    c = core("loose", "on")
    c.stop(NOW)
    c.call_failed(NOW)
    assert c.run_open(NOW) == [Disarm(), Changed()]

    late = c.observe(NOW + minutes(1), "off", by_us=True)

    assert late == [TurnOn(), Changed()]


def flipped_off_and_on_behind_a_slow_device(
    settings: Settings = NO_SETTINGS,
) -> TimerCore:
    """The target is on in the window of interval a, which carries the timer. The
    interval is switched off, and on again before the device that took turn_off reports
    it: the window starts again and asks for nothing, as the target reads on."""
    c = core("strict", "on")
    c.set_windows(NOW, [window("a", -15, 45, settings)], configured={"a"})
    c.tick(NOW)
    assert c.snapshot.scheduled_by == "a"
    c.set_interval_enabled(NOW, "a", False)
    assert c.tick(NOW) == [Disarm(), TurnOff(), Changed()]
    c.call_failed(NOW)
    c.set_interval_enabled(NOW, "a", True)
    c.set_windows(NOW, [window("a", -15, 45, settings)], configured={"a"})
    assert c.tick(NOW) == [Arm(NOW + minutes(45)), Changed()]
    return c


def test_interval_switched_off_and_on_before_the_device_reports_turns_it_on() -> None:
    """The report of the turn-off arrives after the window runs again: the core turns
    the target on, and the window still carries the timer."""
    c = flipped_off_and_on_behind_a_slow_device()

    late = c.observe(NOW + minutes(1), "off", by_us=True)

    assert late == [TurnOn(), Changed()]
    assert (c.snapshot.end, c.snapshot.scheduled_by) == (NOW + minutes(45), "a")
    assert c.observe(NOW + minutes(2), "on", by_us=True) == [Changed()]
    assert c.snapshot.pending is None


def test_the_turn_on_after_a_late_report_does_not_carry_the_window_settings() -> None:
    """The window's settings were dropped when it started again on a target that read
    on, as they may only go with a turn-on (§5.4); the turn-on that follows the late
    report is plain. A device that remembers its last mode runs in it."""
    c = flipped_off_and_on_behind_a_slow_device(HEAT22)

    late = c.observe(NOW + minutes(1), "off", by_us=True)

    assert late == [TurnOn(), Changed()]
    assert c.snapshot.owed_settings == NO_SETTINGS


def test_the_correction_of_a_late_report_has_an_allowance_of_its_own() -> None:
    """Timerify gave up on a refused turn-off, and the user started the target again,
    which needed no call as it still read on. The late report of the turn-off is
    corrected with a turn-on, and a device that refuses that is asked 3 times more."""
    c = refused_turn_off()
    repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)
    c.set_duration(NOW + minutes(10), minutes(30))

    late = c.observe(NOW + minutes(11), "off", by_us=True)
    c.call_failed(NOW + minutes(11))
    again = repeat_reports(
        c, MAX_AUTOMATIC_RESENDS + 1, actual="off", by_us=True, since=minutes(11)
    )

    assert late == [TurnOn(), Changed()]
    assert again == [[TurnOn()]] * MAX_AUTOMATIC_RESENDS + [[GaveUp("on")]]


def test_a_contradicting_report_is_answered_a_limited_number_of_times() -> None:
    """A device that keeps answering the turn-on with an off, each time as an answer
    to our own call, is asked again like any that refuses: 3 more times, told so once,
    then left alone."""
    c = stopped_behind_a_slow_device("strict")
    c.set_duration(NOW, minutes(30))
    assert c.observe(NOW + minutes(1), "off", by_us=True) == [TurnOn(), Changed()]
    c.call_failed(NOW + minutes(1))

    reports = repeat_reports(c, MAX_AUTOMATIC_RESENDS + 2, actual="off", by_us=True)

    assert reports[:MAX_AUTOMATIC_RESENDS] == [[TurnOn()]] * MAX_AUTOMATIC_RESENDS
    assert reports[MAX_AUTOMATIC_RESENDS:] == [[GaveUp("on")], []]
    assert c.snapshot.pending == "on"


def calls_in(effects: list[Effect]) -> list[Effect]:
    """The service calls among `effects`."""
    return [e for e in effects if isinstance(e, TurnOn | TurnOff | ApplySettings)]


def flips_credited_to_our_calls(
    c: TimerCore, first: Literal["on", "off"], rounds: int = 20
) -> list[Effect]:
    """The service calls that `c` sends while the target changes `rounds` times in each
    direction, every change carrying the context of a call of ours: what a device that
    undoes commands by itself does, or a switch pressed on the wall within the seconds
    in which Home Assistant credits the writes of the entity to the last call."""
    other: Literal["on", "off"] = "off" if first == "on" else "on"
    sent: list[Effect] = []
    for step in range(rounds):
        at = NOW + timedelta(seconds=2 * step)
        sent += calls_in(c.observe(at, first, by_us=True))
        sent += calls_in(c.observe(at + timedelta(seconds=1), other, by_us=True))
    return sent


def test_a_device_that_undoes_a_command_by_itself_is_not_commanded_again() -> None:
    """The call was sent for the wish and its answer arrived, so every later change that
    is credited to our call is the device's own, or a user's within the seconds of
    attribution: the wish is not sent again at each one."""
    c = core("strict", "off")
    assert calls_in(c.set_duration(NOW, minutes(30))) == [TurnOn()]

    sent = flips_credited_to_our_calls(c, "on")

    assert sent == []
    assert c.snapshot.end == NOW + minutes(30)
    assert c.snapshot.pending is None


def test_a_wall_switch_pressed_just_after_a_sent_turn_on_is_not_turned_back_on() -> (
    None
):
    """The press carries the context of our call, which Home Assistant keeps crediting
    the entity's writes to for five seconds. Answering it would override the user, and
    again at every press."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(30))
    assert c.observe(NOW + timedelta(seconds=1), "on", by_us=True) == [Changed()]

    pressed = c.observe(NOW + timedelta(seconds=3), "off", by_us=True)
    pressed_again = c.observe(NOW + timedelta(seconds=5), "on", by_us=True)
    pressed_off = c.observe(NOW + timedelta(seconds=7), "off", by_us=True)

    assert pressed == [Changed()]
    assert calls_in(pressed_again) == []
    assert pressed_off == [Changed()]


@pytest.mark.parametrize("first", ["on", "off"])
def test_a_wish_settled_without_a_call_is_corrected_once_to_the_turn_on(
    first: Literal["on", "off"],
) -> None:
    """The first contradicting answer of our own call is corrected (I1); the changes
    that follow are credited to the correction and left alone, whichever way they go."""
    c = stopped_behind_a_slow_device("strict")
    c.set_duration(NOW, minutes(30))
    assert c.observe(NOW + minutes(1), "off", by_us=True) == [TurnOn(), Changed()]

    sent = flips_credited_to_our_calls(c, first)

    assert sent == []


@pytest.mark.parametrize("first", ["on", "off"])
def test_a_wish_settled_without_a_call_is_corrected_once_to_the_turn_off(
    first: Literal["on", "off"],
) -> None:
    """The same for the correction of a late start: the stop asked for nothing, as the
    target read off, the answer of the start is corrected once and then left alone."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(30))
    c.call_failed(NOW)
    c.stop(NOW)
    assert c.observe(NOW + minutes(1), "on", by_us=True) == [TurnOff(), Changed()]

    sent = flips_credited_to_our_calls(c, first)

    assert sent == []


def test_each_wish_settled_without_a_call_is_corrected_once() -> None:
    """The permission belongs to the wish: when the user stops and starts the target
    again behind a slow device, the answer that contradicts the new wish is corrected
    too."""
    c = stopped_behind_a_slow_device("strict")
    c.set_duration(NOW, minutes(30))
    assert c.observe(NOW + minutes(1), "off", by_us=True) == [TurnOn(), Changed()]
    c.observe(NOW + minutes(2), "on", by_us=True)
    assert c.stop(NOW + minutes(3)) == [Disarm(), TurnOff(), Changed()]
    c.call_failed(NOW + minutes(3))
    c.set_duration(NOW + minutes(3), minutes(30))

    again = c.observe(NOW + minutes(4), "off", by_us=True)

    assert again == [TurnOn(), Changed()]


def test_a_new_wish_ends_the_permission_to_correct_the_one_before() -> None:
    """The stop was settled with nothing sent, because the target read off. The target
    then went away, and a start waits for it. The answer of the first start, when the
    target is back, is the wish being met: it is not corrected to the old stop."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(30))
    c.call_failed(NOW)
    c.stop(NOW)
    c.observe(NOW + minutes(1), "unavailable", by_us=False)
    c.set_duration(NOW + minutes(2), minutes(30))
    c.observe(NOW + minutes(3), "on", by_us=True)
    assert c.snapshot.pending is None

    later = c.observe(NOW + minutes(4), "on", by_us=True)

    assert calls_in(later) == []


def test_a_late_report_after_someone_else_switched_the_target_asks_for_nothing() -> (
    None
):
    """Manual wins (R8): the user switched the target off by hand while the report of
    our own turn-off was on its way, and the timer follows the user. The report that
    arrives next is not a reason to turn the target on."""
    c = stopped_behind_a_slow_device("strict")
    c.set_duration(NOW, minutes(30))
    assert c.observe(NOW + minutes(1), "off", by_us=False) == [Disarm(), Changed()]

    late = c.observe(NOW + minutes(2), "off", by_us=True)

    assert late == []
    assert c.snapshot == Snapshot(last_actual="off")


def test_a_report_of_a_call_the_core_never_made_asks_for_nothing() -> None:
    """A timer restored from the store has asked for nothing yet, so there is no
    answer to it that could contradict anything."""
    c = TimerCore(
        "strict", minutes(45), Snapshot(end=NOW + minutes(20), last_actual="on")
    )

    assert c.observe(NOW, "off", by_us=True) == [Changed()]
    assert c.snapshot == Snapshot(end=NOW + minutes(20), last_actual="off")


@pytest.mark.parametrize(
    ("snapshot", "wanted"),
    [
        (Snapshot(last_actual="off"), False),
        (Snapshot(), False),
        (Snapshot(end=NOW + minutes(10), last_actual="on"), True),
        (Snapshot(end=NOW + minutes(10), last_actual="unavailable"), True),
        (Snapshot(last_actual="on"), True),
        (Snapshot(pending="on", last_actual="off"), True),
        (Snapshot(pending="on", last_actual="unavailable"), True),
        (Snapshot(pending="off", last_actual="on"), False),
        (Snapshot(last_actual="unavailable"), False),
    ],
    ids=[
        "idle",
        "never_seen",
        "counting",
        "counting_while_unavailable",
        "on_without_a_timer",
        "turn_on_in_flight",
        "turn_on_waiting_for_the_target",
        "turn_off_in_flight",
        "unavailable_without_a_wish",
    ],
)
def test_the_target_is_wanted_running_by_the_desired_state(
    snapshot: Snapshot, wanted: bool
) -> None:
    """A countdown means running, also while the target is away (R10). Without one the
    wish the target has not confirmed yet decides, and only then what it was last seen
    doing: a turn-on in flight is a run, a turn-off in flight is not."""
    assert TimerCore("strict", minutes(45), snapshot).wanted_running(NOW) is wanted


def test_a_countdown_that_ran_out_is_not_wanted_running() -> None:
    """The end is the instant the countdown reaches zero, folded or not yet."""
    snapshot = Snapshot(end=NOW + minutes(10), last_actual="on")
    c = TimerCore("strict", minutes(45), snapshot)

    assert c.wanted_running(NOW + minutes(10) - timedelta(seconds=1))
    assert not c.wanted_running(NOW + minutes(10))
    assert not c.wanted_running(NOW + minutes(11))


def test_wanted_running_refuses_a_naive_time() -> None:
    with pytest.raises(ValueError, match="now must be timezone-aware"):
        core("strict", "on").wanted_running(NAIVE)


# --- Announcements ------------------------------------------------------------------
#
# The core tells what happened to the countdown on a channel of its own, apart from the
# effects: a countdown that begins where none ran, one that is over and why, and a
# pending command that came due. A change of a running countdown tells nothing.


def test_a_countdown_from_idle_is_announced_as_started() -> None:
    c = core("strict", "off")

    c.set_duration(NOW, minutes(30))

    assert c.take_announcements() == [CountdownStarted(NOW + minutes(30))]
    assert c.take_announcements() == []


def test_a_core_that_is_restored_with_a_countdown_has_nothing_to_announce() -> None:
    """A countdown that was running before the restart is not started again."""
    restored = Snapshot(end=NOW + minutes(30), started_at=NOW, last_actual="on")

    c = TimerCore("strict", minutes(45), restored)
    c.observe(NOW + minutes(5), "on", by_us=False)

    assert c.take_announcements() == []


def test_changing_a_running_countdown_announces_nothing() -> None:
    """Moving the end, however it is done, keeps one countdown going: a pending
    command that comes due in the middle of it is the only thing announced."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(30))
    assert c.take_announcements() == [CountdownStarted(NOW + minutes(30))]

    c.set_duration(NOW + minutes(5), minutes(60))
    assert c.take_announcements() == []
    c.add(NOW + minutes(6), minutes(10))
    assert c.take_announcements() == []
    c.add(NOW + minutes(7), minutes(-5))
    assert c.take_announcements() == []
    c.run_open(NOW + minutes(8))
    assert c.take_announcements() == []

    c.set_windows(NOW + minutes(9), [window("x", 15, 90)], configured={"x"})
    c.tick(NOW + minutes(15))
    assert c.snapshot.end == NOW + minutes(90)  # the window carries the timer on
    assert c.take_announcements() == []

    later = cmd(20, "on", minutes=20)
    c.add_command(NOW + minutes(16), later)
    c.tick(NOW + minutes(20))
    assert c.snapshot.end == NOW + minutes(40)  # the command moved it
    assert c.take_announcements() == [CommandCameDue(later)]


def test_the_end_of_a_countdown_is_announced_as_expired() -> None:
    c = core("strict", "on")
    c.set_duration(NOW, minutes(30))
    c.take_announcements()

    c.tick(NOW + minutes(30))

    assert c.take_announcements() == [CountdownEnded("expired")]


def test_the_end_of_a_window_that_carries_the_timer_is_expired() -> None:
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 0, 30)], configured={"x"})
    c.tick(NOW)
    assert c.take_announcements() == [CountdownStarted(NOW + minutes(30))]

    c.tick(NOW + minutes(30))

    assert c.take_announcements() == [CountdownEnded("expired")]


STOPS: dict[str, Callable[[TimerCore], object]] = {
    "zero": lambda c: c.set_duration(NOW + minutes(10), timedelta(0)),
    "stop": lambda c: c.stop(NOW + minutes(10)),
    "add_past_the_end": lambda c: c.add(NOW + minutes(10), minutes(-40)),
    "pending_off": lambda c: (
        c.add_command(NOW, cmd(10, "off")),
        c.tick(NOW + minutes(10)),
    ),
}
"""Each way Timerify ends a countdown that started at `NOW` and runs for 30 minutes."""


@pytest.mark.parametrize("stop", STOPS)
def test_ending_a_countdown_by_timerify_is_announced_as_stopped(stop: str) -> None:
    c = core("strict", "on")
    c.set_duration(NOW, minutes(30))
    c.take_announcements()

    STOPS[stop](c)

    news = c.take_announcements()
    assert news[-1] == CountdownEnded("stopped")
    assert [n for n in news if isinstance(n, CountdownEnded)] == [news[-1]]


def test_disabling_the_interval_of_an_open_window_announces_a_stop() -> None:
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 0, 60)], configured={"x"})
    c.tick(NOW)
    c.take_announcements()

    c.set_interval_enabled(NOW + minutes(10), "x", False)
    c.tick(NOW + minutes(10))

    assert c.take_announcements() == [CountdownEnded("stopped")]


def test_editing_an_open_window_so_that_it_no_longer_runs_announces_a_stop() -> None:
    """The interval is changed while its window carries the timer, to one that is not
    open now: the timer is taken off, and it is Timerify that ended it."""
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 0, 60)], configured={"x"})
    c.tick(NOW)
    c.take_announcements()

    c.set_windows(NOW + minutes(10), [window("x", 120, 180)], configured={"x"})
    c.tick(NOW + minutes(10))

    assert c.take_announcements() == [CountdownEnded("stopped")]


def test_a_manual_off_is_announced_as_turned_off() -> None:
    c = core("strict", "on")
    c.set_duration(NOW, minutes(30))
    c.take_announcements()

    c.observe(NOW + minutes(5), "off", by_us=False)

    assert c.take_announcements() == [CountdownEnded("turned_off")]


def test_a_manual_off_of_a_timer_with_no_countdown_announces_nothing() -> None:
    c = core("loose", "on")

    c.observe(NOW, "off", by_us=False)

    assert c.take_announcements() == []


def test_a_report_after_the_end_is_announced_as_expired() -> None:
    """The countdown ran out before the target said it was off: the end decides, not
    the report that found it."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(30))
    c.take_announcements()

    c.observe(NOW + minutes(31), "off", by_us=False)

    assert c.take_announcements() == [CountdownEnded("expired")]


def test_a_pending_off_announces_the_command_then_the_stop() -> None:
    off = cmd(10, "off")
    c = holding("strict", "on", off, end=NOW + minutes(30))

    c.tick(NOW + minutes(10))

    assert c.take_announcements() == [CommandCameDue(off), CountdownEnded("stopped")]


def test_a_pending_off_of_a_timer_with_no_countdown_announces_the_command() -> None:
    off = cmd(10, "off")
    c = holding("loose", "on", off)

    c.tick(NOW + minutes(10))

    assert c.take_announcements() == [CommandCameDue(off)]


def test_a_pending_on_on_an_idle_timer_announces_the_command_then_the_start() -> None:
    on = cmd(10, "on", minutes=20)
    c = holding("strict", "off", on)

    c.tick(NOW + minutes(10))

    assert c.take_announcements() == [
        CommandCameDue(on),
        CountdownStarted(NOW + minutes(30)),
    ]


def test_an_on_with_minutes_due_as_the_countdown_ends_announces_no_end() -> None:
    """The command moves the end at the very instant the countdown reaches it: the
    target is not switched off and on, so it is one countdown that goes on."""
    on = cmd(10, "on", minutes=20)
    c = holding("strict", "on", on, end=NOW + minutes(10))

    fx = c.tick(NOW + minutes(10))

    assert TurnOff() not in fx
    assert c.snapshot.end == NOW + minutes(30)
    assert c.take_announcements() == [CommandCameDue(on)]


def test_a_bare_on_that_comes_due_as_the_countdown_ends_announces_the_end() -> None:
    """Loose mode: the command turns the target on with no countdown at the instant
    the countdown reaches zero, so the countdown is over though the target stays on."""
    on = cmd(10, "on")
    c = holding("loose", "on", on, end=NOW + minutes(10))

    fx = c.tick(NOW + minutes(10))

    assert TurnOff() not in fx
    assert c.take_announcements() == [CommandCameDue(on), CountdownEnded("expired")]


def test_two_windows_that_open_together_announce_the_end_they_leave() -> None:
    """The first window starts the countdown and the second, which ends later, moves
    its end within the same fold: the start is told with the end that is left, which the
    Ends at sensor shows."""
    c = core("strict", "off")
    c.set_windows(
        NOW, [window("a", 10, 40), window("b", 10, 70)], configured={"a", "b"}
    )

    c.tick(NOW + minutes(10))

    assert c.snapshot.end == NOW + minutes(70)
    assert c.take_announcements() == [CountdownStarted(NOW + minutes(70))]


def test_a_window_and_a_command_due_together_announce_the_end_they_leave() -> None:
    """The window starts the countdown to its end, and the command, due at the same
    instant, sets the timer for an hour: one countdown, told with its last end."""
    run = cmd(10, "on", minutes=60)
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 10, 55)], configured={"x"})
    c.add_command(NOW, run)

    c.tick(NOW + minutes(10))

    assert c.snapshot.end == NOW + minutes(70)
    assert c.take_announcements() == [
        CountdownStarted(NOW + minutes(70)),
        CommandCameDue(run),
    ]


def test_a_catch_up_with_a_command_and_a_window_announces_the_end_they_leave() -> None:
    """Home Assistant was down while a command and then a window began the countdown:
    what start-up tells is the end it leaves."""
    run = cmd(-10, "on", minutes=30)
    stored = Snapshot(
        commands=(run,), windows=(window("x", -5, 60),), last_actual="off"
    )
    c = TimerCore("strict", minutes(45), stored)

    c.tick(NOW)

    assert c.snapshot.end == NOW + minutes(60)
    assert c.take_announcements() == [
        CommandCameDue(run),
        CountdownStarted(NOW + minutes(60)),
    ]


def test_a_start_that_was_told_is_not_changed_by_a_later_move() -> None:
    """Announcements already taken are told as they were: the caller has them."""
    c = core("strict", "on")
    c.set_duration(NOW, minutes(30))
    assert c.take_announcements() == [CountdownStarted(NOW + minutes(30))]

    c.add(NOW + minutes(5), minutes(10))

    assert c.take_announcements() == []


def test_a_start_after_an_end_in_the_same_fold_carries_the_end_it_leaves() -> None:
    """A countdown that ran out and the one a window begins are two: the end is told,
    then the start, with the end that the second window leaves."""
    c = TimerCore("strict", minutes(45), Snapshot(end=NOW - minutes(5)))
    c.set_windows(NOW, [window("a", 0, 50), window("b", 0, 70)], configured={"a", "b"})

    c.tick(NOW)

    assert c.snapshot.end == NOW + minutes(70)
    assert c.take_announcements() == [
        CountdownEnded("expired"),
        CountdownStarted(NOW + minutes(70)),
    ]


def test_a_pending_off_due_as_the_countdown_ends_announces_it_expired() -> None:
    """The countdown ran out at the command's time, so there is nothing left for the
    command to stop: the same reason as for a bare "on" or a zero at that instant."""
    off = cmd(10, "off")
    c = holding("strict", "on", off, end=NOW + minutes(10))

    c.tick(NOW + minutes(10))

    assert c.take_announcements() == [CommandCameDue(off), CountdownEnded("expired")]


def test_a_pending_off_due_as_a_window_ends_announces_it_expired() -> None:
    """The window carries the timer to its end, and the command is due at that end."""
    off = cmd(30, "off")
    c = core("strict", "off")
    c.set_windows(NOW, [window("x", 0, 30)], configured={"x"})
    c.tick(NOW)
    c.add_command(NOW, off)
    c.take_announcements()

    c.tick(NOW + minutes(30))

    assert c.take_announcements() == [CommandCameDue(off), CountdownEnded("expired")]


def test_a_pending_off_a_minute_before_the_countdown_ends_stops_it() -> None:
    off = cmd(9, "off")
    c = holding("strict", "on", off, end=NOW + minutes(10))

    c.tick(NOW + minutes(9))

    assert c.take_announcements() == [CommandCameDue(off), CountdownEnded("stopped")]


def test_a_dropped_command_is_not_announced_as_due() -> None:
    """The run it asked for was over before it was folded: it did nothing."""
    late = cmd(-61, minutes=60)
    c = holding("strict", "off", late)

    fx = c.tick(NOW)

    assert CommandDropped(late) in fx
    assert c.take_announcements() == []


@pytest.mark.parametrize(
    ("mode", "news"),
    [("strict", [CountdownStarted(NOW + minutes(45))]), ("loose", [])],
)
def test_a_manual_on_announces_a_start_in_strict_mode_only(
    mode: Mode, news: list[CountdownStarted]
) -> None:
    """With no window open, strict mode gives a target that is switched on by hand its
    default countdown; loose mode lets it run with none."""
    c = core(mode, "off")

    c.observe(NOW, "on", by_us=False)

    assert c.take_announcements() == news


@pytest.mark.parametrize("ended", [-40, -1, 0])
def test_a_run_given_after_the_end_passed_announces_the_end_first(ended: int) -> None:
    """An end that is not ahead is no countdown (#42), but the countdown did run out:
    its end is told before the start of the new one, and the snapshot is the one the
    step gives to a timer that was folded."""
    stale = Snapshot(end=NOW + minutes(ended), started_at=NOW - minutes(70))
    c = TimerCore("strict", minutes(45), stale)
    idle = TimerCore("strict", minutes(45), Snapshot())

    fx = c.add(NOW, minutes(10))

    assert fx == idle.add(NOW, minutes(10))
    assert c.snapshot == idle.snapshot
    assert c.take_announcements() == [
        CountdownEnded("expired"),
        CountdownStarted(NOW + minutes(10)),
    ]


def test_a_duration_set_after_the_end_passed_announces_the_end_first() -> None:
    c = TimerCore("strict", minutes(45), Snapshot(end=NOW - minutes(1)))
    idle = TimerCore("strict", minutes(45), Snapshot())

    assert c.set_duration(NOW, minutes(10)) == idle.set_duration(NOW, minutes(10))

    assert c.snapshot == idle.snapshot
    assert c.take_announcements() == [
        CountdownEnded("expired"),
        CountdownStarted(NOW + minutes(10)),
    ]


def test_a_zero_given_after_the_end_passed_announces_that_it_expired() -> None:
    """There is no countdown left to stop: the one that ran out is what is told."""
    c = TimerCore("strict", minutes(45), Snapshot(end=NOW - minutes(1)))
    idle = TimerCore("strict", minutes(45), Snapshot())

    assert c.set_duration(NOW, timedelta(0)) == idle.set_duration(NOW, timedelta(0))

    assert c.snapshot == idle.snapshot
    assert c.take_announcements() == [CountdownEnded("expired")]


def test_stop_after_the_end_passed_announces_that_it_expired() -> None:
    """Like a zero: there is no countdown left to stop, the one that ran out is told."""
    c = TimerCore("strict", minutes(45), Snapshot(end=NOW - minutes(1)))
    idle = TimerCore("strict", minutes(45), Snapshot())

    assert c.stop(NOW) == idle.stop(NOW)

    assert c.snapshot == idle.snapshot
    assert c.take_announcements() == [CountdownEnded("expired")]


@pytest.mark.parametrize("mode", ["strict", "loose"])
def test_a_run_given_after_the_end_passed_in_either_mode_tells_the_end(
    mode: Mode,
) -> None:
    c = TimerCore(mode, minutes(45), Snapshot(end=NOW - minutes(1)))
    idle = TimerCore(mode, minutes(45), Snapshot())

    assert c.run_open(NOW) == idle.run_open(NOW)

    assert c.snapshot == idle.snapshot
    expected: list[CountdownEnded | CountdownStarted] = [CountdownEnded("expired")]
    if mode == "strict":
        expected.append(CountdownStarted(NOW + minutes(45)))
    assert c.take_announcements() == expected


def test_a_negative_add_after_the_end_passed_leaves_the_end_to_the_tick() -> None:
    """Nothing is written, so nothing is told yet: the tick that folds the end tells
    that it expired."""
    c = TimerCore("strict", minutes(45), Snapshot(end=NOW - minutes(1)))

    assert c.add(NOW, minutes(-5)) == []
    assert c.take_announcements() == []

    c.tick(NOW)
    assert c.take_announcements() == [CountdownEnded("expired")]


def test_a_catch_up_that_ends_and_starts_announces_both_in_order() -> None:
    """Home Assistant was down from before the end of a countdown to after a command:
    what ended, the command, and the countdown it began."""
    on = cmd(-10, "on", minutes=30)
    stored = Snapshot(end=NOW - minutes(60), commands=(on,), last_actual="off")
    c = TimerCore("strict", minutes(45), stored)

    c.observe(NOW, "on", by_us=False)

    assert c.take_announcements() == [
        CountdownEnded("expired"),
        CommandCameDue(on),
        CountdownStarted(NOW + minutes(20)),
    ]


def test_announcements_are_not_effects() -> None:
    """The effects of a step are what they were; what it announced is apart."""
    c = core("strict", "off")

    fx = c.set_duration(NOW, minutes(30))

    assert fx == [Arm(NOW + minutes(30)), TurnOn(), Changed()]
    assert c.take_announcements() == [CountdownStarted(NOW + minutes(30))]
