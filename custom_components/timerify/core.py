"""Pure timer state machine: commands and expiry become effects for a controller.

Nothing here touches Home Assistant, the clock or the event loop. Every command
takes the current time, updates the snapshot and returns the effects the caller
must carry out, in order.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
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

    @property
    def snapshot(self) -> Snapshot:
        """The current state, safe to persist."""
        return self._snapshot

    @_reports_change
    def set_duration(self, now: datetime, duration: timedelta) -> list[Effect]:
        """Count down `duration` from now; zero or less stops the timer."""
        return self._run_until(now, now + duration)

    @_reports_change
    def add(self, now: datetime, delta: timedelta) -> list[Effect]:
        """Move the end by `delta`; on an idle timer only a positive delta starts it."""
        end = self._snapshot.end
        if end is None:
            if delta <= timedelta(0):
                return []
            return self._run_until(now, now + delta)
        return self._run_until(now, end + delta)

    @_reports_change
    def stop(self, now: datetime) -> list[Effect]:
        """End the countdown and switch the target off."""
        return self._stop()

    @_reports_change
    def run_open(self, now: datetime) -> list[Effect]:
        """Switch the target on without a duration.

        Strict mode applies the default duration; loose mode runs with the timer
        at zero.
        """
        if self._mode == "strict":
            return self._run_until(now, now + self._default_duration)
        self._snapshot = replace(self._snapshot, end=None)
        return [Disarm(), *self._want("on")]

    @_reports_change
    def expire(self, now: datetime) -> list[Effect]:
        """Handle the alarm; one that fires before the end is a stale leftover."""
        end = self._snapshot.end
        if end is None or end > now:
            return []
        return self._stop()

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
        so both directions share this one algorithm.
        """
        state = self._snapshot
        if state.pending == target:
            return []  # already on its way
        if state.pending is None and state.last_actual == target:
            return []  # already there
        self._snapshot = replace(state, pending=target)  # replaces an opposite wish
        if state.last_actual == "unavailable":
            return []  # applied when the target is back
        return [TurnOn() if target == "on" else TurnOff()]


def remaining_minutes(snapshot: Snapshot, now: datetime) -> int:
    """Whole minutes left, rounded up; 0 when idle or past the end."""
    if snapshot.end is None:
        return 0
    return max(0, ceil((snapshot.end - now) / timedelta(minutes=1)))
