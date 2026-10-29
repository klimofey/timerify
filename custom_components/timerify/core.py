"""Pure timer state machine: commands and expiry become effects for a controller.

Nothing here touches Home Assistant, the clock or the event loop. Every command
and every observation of the target takes the current time, updates the snapshot
and returns the effects the caller must carry out, in order.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from functools import wraps
from math import ceil
from typing import Concatenate, Final, Literal

from .const import MAX_AUTOMATIC_RESENDS, MAX_MINUTES, NO_SETTINGS, Mode, Settings
from .domains import Actual

_MAX_DURATION: Final = timedelta(minutes=MAX_MINUTES)
"""The longest countdown from now, whichever command starts or extends it."""


@dataclass(frozen=True)
class Snapshot:
    """The state of the timer; a store keeps everything but `last_actual`."""

    end: datetime | None = None
    """When the countdown reaches zero (timezone-aware UTC); None while idle."""
    pending: Literal["on", "off"] | None = None
    """The switch the core asked for and has not yet seen the target confirm."""
    owed_settings: Settings = NO_SETTINGS
    """The settings the target was asked to run with and has not yet confirmed to
    have taken. Never set while `pending` is "off"."""
    last_actual: Actual | None = None
    """The target's last observed state; None until it has been observed."""


@dataclass(frozen=True)
class TurnOn:
    """Switch the target on, with `settings` if there are any."""

    settings: Settings = NO_SETTINGS


@dataclass(frozen=True)
class ApplySettings:
    """Set `settings` on a target that is on or on its way to it, switching nothing."""

    settings: Settings


@dataclass(frozen=True)
class TurnOff:
    """Switch the target off."""


@dataclass(frozen=True)
class Arm:
    """Schedule the expiry alarm for `at`, replacing any earlier one."""

    at: datetime


@dataclass(frozen=True)
class Disarm:
    """Cancel the expiry alarm."""


@dataclass(frozen=True)
class Changed:
    """The snapshot changed: persist it and refresh the entities."""


@dataclass(frozen=True)
class GaveUp:
    """Something was sent again as often as reports alone may send it, and the target
    still does not show it: the switch to "on" or "off", or the owed settings. Said
    once per allowance; nothing is sent until the target's state changes or a command
    wants it again."""

    what: Literal["on", "off", "settings"]


type Effect = TurnOn | ApplySettings | TurnOff | Arm | Disarm | Changed | GaveUp


def _utc(now: datetime) -> datetime:
    """`now` in UTC, so every end is UTC whatever zone the caller works in."""
    if now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(UTC)


def _reports_change[**P](
    command: Callable[Concatenate[TimerCore, P], list[Effect]],
) -> Callable[Concatenate[TimerCore, P], list[Effect]]:
    """Append `Changed()` to the effects of a command that changed the snapshot."""

    @wraps(command)
    def wrapper(core: TimerCore, /, *args: P.args, **kwargs: P.kwargs) -> list[Effect]:
        before = core.snapshot
        effects = command(core, *args, **kwargs)
        if core.snapshot != before:
            effects.append(Changed())
        return effects

    return wrapper


class _Allowance:
    """How often reports that merely repeat the target's state may send something
    again: `limit` times, then one give-up, then nothing until `reset`.

    A device that refuses a command may answer every call with such a report, so
    without the bound it would be commanded for ever.
    """

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._used = 0
        self._gave_up = False

    def reset(self) -> None:
        self._used = 0
        self._gave_up = False

    def take(self) -> Literal["send", "give_up", "silent"]:
        """What a report that repeats the target's state may do now."""
        if self._used < self._limit:
            self._used += 1
            return "send"
        if self._gave_up:
            return "silent"
        self._gave_up = True
        return "give_up"


class TimerCore:
    """Decides what to switch and when to wake up; the caller executes the effects."""

    def __init__(
        self,
        mode: Mode,
        default_duration: timedelta,
        snapshot: Snapshot,
        *,
        automatic_resends: int = MAX_AUTOMATIC_RESENDS,
    ) -> None:
        """`automatic_resends` is how often reports that repeat the target's state send
        a wish, or the owed settings, again before the core gives up."""
        self._mode = mode
        self._default_duration = default_duration
        self._snapshot = snapshot
        self._unsent = False
        """The pending wish has not reached the target (its call failed or changed
        nothing, or the target was away). Only true while a wish is pending; never
        persisted, because a restart sends every stored wish again."""
        self._settings_unsent = False
        """The owed settings have not reached the target, as `_unsent` says of the
        wish. Only true while settings are owed; never persisted either."""
        self._wish_allowance = _Allowance(automatic_resends)
        """Re-sends of the pending wish by reports. Only meaningful while a wish is
        pending: every command that wants one starts it from zero, and so does a
        change of the target's state. Never persisted."""
        self._settings_allowance = _Allowance(automatic_resends)
        """The same for the owed settings: new settings, a change of the target's
        state and any command that sends them start it from zero."""

    @property
    def snapshot(self) -> Snapshot:
        """The current state, safe to persist."""
        return self._snapshot

    @_reports_change
    def set_duration(
        self,
        now: datetime,
        duration: timedelta,
        settings: Settings = NO_SETTINGS,
        *,
        apply_if_on: bool = True,
    ) -> list[Effect]:
        """Count down `duration` from now; zero or less stops the timer.

        Non-empty `settings` replace the ones that are owed and are sent with the
        turn-on, or on their own to a target that is on. With `apply_if_on` false they
        are sent only with a turn-on this command causes.
        """
        now = _utc(now)
        return self._run_until(now, now + duration, settings, apply_if_on=apply_if_on)

    @_reports_change
    def add(self, now: datetime, delta: timedelta) -> list[Effect]:
        """Move the end by `delta`; on an idle timer only a positive delta starts it."""
        now = _utc(now)
        end = self._snapshot.end
        if end is None:
            if delta <= timedelta(0):
                return []
            return self._run_until(now, now + delta)
        return self._run_until(now, end + delta)

    @_reports_change
    def stop(self, now: datetime) -> list[Effect]:
        """End the countdown and switch the target off."""
        _utc(now)  # unused, but every command rejects a naive time alike
        return self._stop()

    @_reports_change
    def run_open(
        self,
        now: datetime,
        settings: Settings = NO_SETTINGS,
        *,
        apply_if_on: bool = True,
    ) -> list[Effect]:
        """Switch the target on without a duration, with `settings` as `set_duration`
        takes them.

        Strict mode applies the default duration; loose mode runs with the timer
        at zero.
        """
        now = _utc(now)
        if self._mode == "strict":
            return self._run_until(
                now, now + self._default_duration, settings, apply_if_on=apply_if_on
            )
        self._snapshot = replace(self._snapshot, end=None)
        return [Disarm(), *self._want("on", settings, apply_if_on=apply_if_on)]

    @_reports_change
    def expire(self, now: datetime) -> list[Effect]:
        """Handle the alarm; one that fires before the end is a stale leftover."""
        if not self._due(_utc(now)):
            return []
        return self._stop()

    @_reports_change
    def settings_applied(self, now: datetime) -> list[Effect]:
        """The calls that carried the owed settings all went through: nothing is owed
        any more. The caller reports it right after executing the effects."""
        _utc(now)  # unused, but every command rejects a naive time alike
        self._clear_settings()
        return []

    def call_failed(self, now: datetime) -> list[Effect]:
        """The pending wish or the owed settings did not reach the target: a service
        call failed, or succeeded without the target changing.

        They are sent again by the next command that wants the same thing, or by a
        report of the target, within the limit of `automatic_resends` for reports that
        repeat its state. The caller reports a failure right after executing the
        effects, before anything else reaches the core.
        """
        _utc(now)  # unused, but every command rejects a naive time alike
        if self._snapshot.pending is not None:
            self._unsent = True
        if self._snapshot.owed_settings:
            self._settings_unsent = True
        return []

    @_reports_change
    def observe(self, now: datetime, actual: Actual, *, by_us: bool) -> list[Effect]:
        """React to the target's state: on every change and once at startup.

        `by_us` says the change came from a service call the core asked for.
        """
        now = _utc(now)
        previous = self._snapshot.last_actual
        repeated = actual == previous
        if not repeated:
            # The target moved, so asking again is not a loop.
            self._wish_allowance.reset()
            self._settings_allowance.reset()
        if previous in (None, "unavailable"):
            # A target that is back has not received the wish or the settings.
            if self._snapshot.pending is not None:
                self._unsent = True
            if self._snapshot.owed_settings:
                self._settings_unsent = True
        # Record the observation first: everything below reasons about the state
        # the target is in now, so an unavailable target is never switched and
        # one that is already where a wish wants it needs no service call.
        self._snapshot = replace(self._snapshot, last_actual=actual)
        expired = self._due(now)
        effects = self._stop() if expired else []
        if actual == "unavailable":
            return effects
        pending = self._snapshot.pending
        if pending is not None and self._unsent:
            if pending == actual:
                self._settle()
            else:
                effects += self._resend(pending, repeated=repeated)
        elif by_us:
            if pending == actual:
                self._settle()
        elif not repeated and not expired:
            # Our own expiry is already switching the target off; it outranks this.
            effects += self._follow_external_change(now, actual)
        return effects + self._deliver_settings(repeated=repeated)

    def _due(self, now: datetime) -> bool:
        end = self._snapshot.end
        return end is not None and end <= now

    def _follow_external_change(
        self, now: datetime, actual: Literal["on", "off"]
    ) -> list[Effect]:
        """Someone else switched the target: the timer follows (R3 to R5)."""
        self._settle()
        if actual == "off":
            self._clear_settings()  # a target that is off runs with nothing
            if self._snapshot.end is None:
                return []
            self._snapshot = replace(self._snapshot, end=None)
            return [Disarm()]
        if self._mode == "strict" and self._snapshot.end is None:
            return self._run_until(now, now + self._default_duration)
        return []

    def _run_until(
        self,
        now: datetime,
        end: datetime,
        settings: Settings = NO_SETTINGS,
        *,
        apply_if_on: bool = True,
    ) -> list[Effect]:
        """Count down to `end`, at most a day from now, or stop if it is not ahead."""
        if end <= now:
            return self._stop()
        end = min(end, now + _MAX_DURATION)
        self._snapshot = replace(self._snapshot, end=end)
        return [Arm(end), *self._want("on", settings, apply_if_on=apply_if_on)]

    def _stop(self) -> list[Effect]:
        self._snapshot = replace(self._snapshot, end=None)
        self._clear_settings()  # a timer that stops has nothing to run with
        return [Disarm(), *self._want("off")]

    def _want(
        self,
        target: Literal["on", "off"],
        settings: Settings = NO_SETTINGS,
        *,
        apply_if_on: bool = True,
    ) -> list[Effect]:
        """Ask for the target to be switched, once per direction, and for the settings
        to be set when the target is wanted on.

        A command can arrive while the opposite service call is still in flight,
        so both directions share this one algorithm. A wish that never reached
        the target is not in flight: it is sent again, or dropped if the target
        is already where the new wish wants it. Settings go with the turn-on this
        causes; a target that needs none, because it is on or its turn-on is on its
        way, gets them alone, unless `apply_if_on` is false.
        """
        state = self._snapshot
        in_flight = state.pending is not None and not self._unsent
        if in_flight and state.pending == target:
            return self._settings_for_running_target(settings, apply_if_on)
        if not in_flight and state.last_actual == target:
            self._settle()
            return self._settings_for_running_target(settings, apply_if_on)
        self._snapshot = replace(state, pending=target)  # replaces an opposite wish
        self._wish_allowance.reset()  # a command always sends, whatever reports did
        self._owe(settings)  # they ride with the turn-on this causes
        if state.last_actual == "unavailable":
            self._unsent = True
            return []  # applied when the target is back
        return self._send(target)

    def _settings_for_running_target(
        self, settings: Settings, apply_if_on: bool
    ) -> list[Effect]:
        """The settings of a command that needs no turn-on: owed and sent to a target
        that runs, unless the command must not push them onto a running target."""
        if apply_if_on:
            self._owe(settings)
        return self._deliver_settings(repeated=False)

    def _send(self, target: Literal["on", "off"]) -> list[Effect]:
        self._unsent = False
        if target == "off":
            return [TurnOff()]
        self._settings_unsent = False  # a turn-on takes the owed settings along
        return [TurnOn(self._snapshot.owed_settings)]

    def _resend(self, wish: Literal["on", "off"], *, repeated: bool) -> list[Effect]:
        """Send a wish again because the target reported and does not show it.

        A report that moved the target's state is always answered. One that only
        repeats it is answered `automatic_resends` times, then the core gives up
        once and waits for a change or a command.
        """
        if repeated:
            match self._wish_allowance.take():
                case "give_up":
                    return [GaveUp(wish)]
                case "silent":
                    return []
        return self._send(wish)

    def _owe(self, settings: Settings) -> None:
        """Make `settings`, if there are any, the ones the target has yet to take."""
        if settings:
            self._snapshot = replace(self._snapshot, owed_settings=settings)
            self._settings_unsent = True
            self._settings_allowance.reset()

    def _deliver_settings(self, *, repeated: bool) -> list[Effect]:
        """Send the owed settings that have not reached the target, if it can take them.

        A target that is away gets nothing, and a turn-on that is yet to go out takes
        the settings itself. `repeated` says a report that merely repeated the target's
        state asked: it is answered within the allowance, like a wish.
        """
        state = self._snapshot
        if not (state.owed_settings and self._settings_unsent):
            return []
        runs = state.last_actual == "on" or (state.pending == "on" and not self._unsent)
        if state.last_actual == "unavailable" or not runs:
            return []
        if repeated:
            match self._settings_allowance.take():
                case "give_up":
                    return [GaveUp("settings")]
                case "silent":
                    return []
        else:
            self._settings_allowance.reset()  # a command or a change always sends
        self._settings_unsent = False
        return [ApplySettings(state.owed_settings)]

    def _clear_settings(self) -> None:
        """Nothing is owed: the target took the settings, or they no longer apply."""
        self._snapshot = replace(self._snapshot, owed_settings=NO_SETTINGS)
        self._settings_unsent = False
        self._settings_allowance.reset()

    def _settle(self) -> None:
        """Drop the pending wish: it was fulfilled or no longer applies."""
        self._snapshot = replace(self._snapshot, pending=None)
        self._unsent = False


def remaining_minutes(snapshot: Snapshot, now: datetime) -> int:
    """Whole minutes left, rounded up; 0 when idle or past the end."""
    now = _utc(now)
    if snapshot.end is None:
        return 0
    return max(0, ceil((snapshot.end - now) / timedelta(minutes=1)))
