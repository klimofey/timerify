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
    freeze_settings,
)
from custom_components.timerify.core import (
    ApplySettings,
    Arm,
    Changed,
    Disarm,
    Effect,
    GaveUp,
    Snapshot,
    TimerCore,
    TurnOff,
    TurnOn,
    remaining_minutes,
)
from custom_components.timerify.domains import Actual

NOW = datetime(2026, 1, 5, 7, 0, tzinfo=UTC)
COOL24 = freeze_settings({"hvac_mode": "cool", "temperature": 24.0})


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
    assert c.snapshot == Snapshot(end=NOW + minutes(10), last_actual="on")


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
    c: TimerCore, count: int, actual: Actual = "on"
) -> list[list[Effect]]:
    """The effects of `count` reports in a row that repeat the target's state, from a
    device that refuses every call: each send comes back as not delivered."""
    results: list[list[Effect]] = []
    for step in range(count):
        now = NOW + minutes(1 + step)
        effects = c.observe(now, actual, by_us=False)
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


def test_a_change_of_the_targets_state_gives_a_full_allowance_again() -> None:
    """A target that went away and came back is a new chance, and the answer to that
    report does not count against the limit."""
    c = refused_turn_off()
    repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)

    c.observe(NOW + minutes(10), "unavailable", by_us=False)
    back = c.observe(NOW + minutes(11), "on", by_us=False)

    assert TurnOff() in back
    c.call_failed(NOW + minutes(11))
    again = repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)
    assert again == [[TurnOff()]] * MAX_AUTOMATIC_RESENDS + [[GaveUp("off")]]


def test_the_first_report_after_a_start_gives_a_full_allowance() -> None:
    """A stored wish found unsent at start-up is sent, then limited like any other."""
    c = TimerCore("strict", minutes(45), Snapshot(end=None, pending="off"))

    start = c.observe(NOW, "on", by_us=False)
    c.call_failed(NOW)
    again = repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)

    assert start == [TurnOff(), Changed()]
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


def test_apply_if_on_false_leaves_running_target_alone() -> None:
    """A command that must not push settings onto a running target sends none."""
    c = core("strict", "on")

    fx = c.set_duration(NOW, minutes(60), COOL24, apply_if_on=False)

    assert fx == [Arm(NOW + minutes(60)), Changed()]
    assert c.snapshot.owed_settings == NO_SETTINGS


def test_apply_if_on_false_still_sends_settings_with_the_turn_on_it_causes() -> None:
    """The settings go to a target that is switched on by the command itself."""
    c = core("strict", "off")

    fx = c.set_duration(NOW, minutes(60), COOL24, apply_if_on=False)

    assert fx == [Arm(NOW + minutes(60)), TurnOn(COOL24), Changed()]


def test_apply_if_on_false_keeps_settings_for_a_turn_on_that_waits() -> None:
    """The command causes a turn-on that waits for the target; the settings wait too."""
    c = core("strict", "unavailable")

    c.set_duration(NOW, minutes(60), COOL24, apply_if_on=False)

    assert c.snapshot.owed_settings == COOL24
    assert c.observe(NOW, "off", by_us=False) == [TurnOn(COOL24), Changed()]


def test_apply_if_on_false_sends_no_settings_while_a_turn_on_is_in_flight() -> None:
    """A turn-on that another command started is not this command's: no settings."""
    c = core("strict", "off")
    c.set_duration(NOW, minutes(10))

    fx = c.set_duration(NOW, minutes(60), COOL24, apply_if_on=False)

    assert fx == [Arm(NOW + minutes(60)), Changed()]
    assert c.snapshot.owed_settings == NO_SETTINGS


def test_loose_open_run_with_settings_on_running_target_applies_them() -> None:
    """Running without a countdown on a target that is on still sets the settings."""
    c = core("loose", "on")

    fx = c.run_open(NOW, COOL24)

    assert fx == [Disarm(), ApplySettings(COOL24), Changed()]


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
        pytest.param(lambda c, now: c.expire(now + minutes(60)), id="expiry"),
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


def test_a_change_of_state_gives_settings_a_full_allowance_again() -> None:
    """The target goes away and comes back: that is a new chance for the settings."""
    c = owing("strict", "on")
    c.call_failed(NOW)
    repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)

    c.observe(NOW + minutes(10), "unavailable", by_us=False)
    back = c.observe(NOW + minutes(11), "on", by_us=False)
    c.call_failed(NOW + minutes(11))
    again = repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)

    assert back == [ApplySettings(COOL24), Changed()]
    assert again == [[ApplySettings(COOL24)]] * MAX_AUTOMATIC_RESENDS + [
        [GaveUp("settings")]
    ]


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


def test_zero_automatic_resends_answers_only_changes() -> None:
    """A device that must not be told twice is told again only after its state moved."""
    c = TimerCore(
        "strict", minutes(45), Snapshot(last_actual="off"), automatic_resends=0
    )
    c.set_duration(NOW, minutes(10))
    c.call_failed(NOW)

    repeated = c.observe(NOW + minutes(1), "off", by_us=False)
    c.observe(NOW + minutes(2), "unavailable", by_us=False)
    back = c.observe(NOW + minutes(3), "off", by_us=False)

    assert repeated == [GaveUp("on")]
    assert back == [TurnOn(), Changed()]


NAIVE = datetime(2026, 1, 5, 7, 0)


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda c: c.set_duration(NAIVE, minutes(5)), id="set"),
        pytest.param(lambda c: c.add(NAIVE, minutes(5)), id="add"),
        pytest.param(lambda c: c.stop(NAIVE), id="stop"),
        pytest.param(lambda c: c.run_open(NAIVE), id="run-open"),
        pytest.param(lambda c: c.expire(NAIVE), id="expire"),
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
