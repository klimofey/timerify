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
from typing import Concatenate, Literal

from .const import Mode
from .domains import Actual


@dataclass(frozen=True)
class Snapshot:
    """The part of the timer that is persisted and restored."""

    end: datetime | None = None
    """When the countdown reaches zero (timezone-aware UTC); None while idle."""
    pending: Literal["on", "off"] | None = None
    """The switch the core asked for and has not yet seen the target confirm."""
    last_actual: Actual | None = None
    """The target's last observed state; None until it has been observed."""


@dataclass(frozen=True)
class TurnOn:
    """Switch the target on."""


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


type Effect = TurnOn | TurnOff | Arm | Disarm | Changed


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


class TimerCore:
    """Decides what to switch and when to wake up; the caller executes the effects."""

    def __init__(
        self, mode: Mode, default_duration: timedelta, snapshot: Snapshot
    ) -> None:
        self._mode = mode
        self._default_duration = default_duration
        self._snapshot = snapshot
        self._unsent = False
        """The pending wish has not reached the target (its call failed, or the
        target was away). Only true while a wish is pending; never persisted,
        because a restart sends every stored wish again."""

    @property
    def snapshot(self) -> Snapshot:
        """The current state, safe to persist."""
        return self._snapshot

    @_reports_change
    def set_duration(self, now: datetime, duration: timedelta) -> list[Effect]:
        """Count down `duration` from now; zero or less stops the timer."""
        now = _utc(now)
        return self._run_until(now, now + duration)

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
    def run_open(self, now: datetime) -> list[Effect]:
        """Switch the target on without a duration.

        Strict mode applies the default duration; loose mode runs with the timer
        at zero.
        """
        now = _utc(now)
        if self._mode == "strict":
            return self._run_until(now, now + self._default_duration)
        self._snapshot = replace(self._snapshot, end=None)
        return [Disarm(), *self._want("on")]

    @_reports_change
    def expire(self, now: datetime) -> list[Effect]:
        """Handle the alarm; one that fires before the end is a stale leftover."""
        if not self._due(_utc(now)):
            return []
        return self._stop()

    def call_failed(self, now: datetime) -> list[Effect]:
        """The service call for the pending wish failed.

        The wish is sent again by the next report of the target or the next
        command that wants the same thing. The caller reports a failure right
        after executing the effects, before anything else reaches the core.
        """
        _utc(now)  # unused, but every command rejects a naive time alike
        if self._snapshot.pending is not None:
            self._unsent = True
        return []

    @_reports_change
    def observe(self, now: datetime, actual: Actual, *, by_us: bool) -> list[Effect]:
        """React to the target's state: on every change and once at startup.

        `by_us` says the change came from a service call the core asked for.
        """
        now = _utc(now)
        previous = self._snapshot.last_actual
        if previous in (None, "unavailable") and self._snapshot.pending is not None:
            self._unsent = True  # a target that is back has not received the wish
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
                effects += self._send(pending)
        elif by_us:
            if pending == actual:
                self._settle()
        elif actual != previous and not expired:
            # Our own expiry is already switching the target off; it outranks this.
            effects += self._follow_external_change(now, actual)
        return effects

    def _due(self, now: datetime) -> bool:
        end = self._snapshot.end
        return end is not None and end <= now

    def _follow_external_change(
        self, now: datetime, actual: Literal["on", "off"]
    ) -> list[Effect]:
        """Someone else switched the target: the timer follows (R3 to R5)."""
        self._settle()
        if actual == "off":
            if self._snapshot.end is None:
                return []
            self._snapshot = replace(self._snapshot, end=None)
            return [Disarm()]
        if self._mode == "strict" and self._snapshot.end is None:
            return self._run_until(now, now + self._default_duration)
        return []

    def _run_until(self, now: datetime, end: datetime) -> list[Effect]:
        """Count down to `end`, or stop when it is not in the future."""
        if end <= now:
            return self._stop()
        self._snapshot = replace(self._snapshot, end=end)
        return [Arm(end), *self._want("on")]

    def _stop(self) -> list[Effect]:
        self._snapshot = replace(self._snapshot, end=None)
        return [Disarm(), *self._want("off")]

    def _want(self, target: Literal["on", "off"]) -> list[Effect]:
        """Ask for the target to be switched, once per direction.

        A command can arrive while the opposite service call is still in flight,
        so both directions share this one algorithm. A wish that never reached
        the target is not in flight: it is sent again, or dropped if the target
        is already where the new wish wants it.
        """
        state = self._snapshot
        in_flight = state.pending is not None and not self._unsent
        if in_flight and state.pending == target:
            return []  # already on its way
        if not in_flight and state.last_actual == target:
            self._settle()
            return []  # already there
        self._snapshot = replace(state, pending=target)  # replaces an opposite wish
        if state.last_actual == "unavailable":
            self._unsent = True
            return []  # applied when the target is back
        return self._send(target)

    def _send(self, target: Literal["on", "off"]) -> list[Effect]:
        self._unsent = False
        return [TurnOn() if target == "on" else TurnOff()]

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
