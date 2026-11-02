"""Pure timer state machine: commands, pending commands, schedule windows and expiry
become effects for a controller.

Nothing here touches Home Assistant, the clock or the event loop. Every command
and every observation of the target takes the current time, updates the snapshot
and returns the effects the caller must carry out, in order. What happened to the
countdown and to the pending commands is told apart from the effects, as announcements
that the caller takes (`TimerCore.take_announcements`).
"""

from collections.abc import Callable, Iterable
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import IntEnum
from functools import wraps
from math import ceil
from typing import Concatenate, Final, Literal, assert_never

from .const import MAX_AUTOMATIC_RESENDS, MAX_MINUTES, NO_SETTINGS, Mode, Settings
from .domains import Actual

_MAX_DURATION: Final = timedelta(minutes=MAX_MINUTES)
"""The longest countdown from now, whichever command starts or extends it."""


@dataclass(frozen=True)
class Command:
    """A pending command: at `at`, turn the target on or off, whatever state it is in
    then (P1). Only an explicit cancel removes it (P2)."""

    id: str
    at: datetime
    """When the command is due (timezone-aware UTC)."""
    action: Literal["on", "off"]
    minutes: int | None = None
    """How long an "on" runs, counted from `at`; None runs the default duration in
    strict mode and without a countdown in loose mode. Never set for "off"."""
    settings: Settings = NO_SETTINGS
    """What an "on" turns the target on with. Never set for "off"."""


@dataclass(frozen=True)
class Window:
    """One occurrence of a schedule interval: the target is to run from `start` to
    `end`. The caller works the occurrence out; the core only folds it into the timer
    (S1 to S4)."""

    interval_id: str
    start: datetime
    """When the window opens (timezone-aware UTC)."""
    end: datetime
    """When it closes (timezone-aware UTC): after `start`, at most a day later."""
    settings: Settings = NO_SETTINGS
    """What a target that is off is turned on with when the window opens."""
    started: bool = False
    """The opening has been dealt with: it set the timer, left it alone because the
    timer ends later, or found the window over. It never applies again, so a target
    that was turned off during the window stays off until the next one (S4)."""
    suppressed: bool = False
    """The timer was zeroed after the window started (S4): the window no longer wants
    the target running, so the timer is never handed to it. Only a started window can
    be suppressed."""


@dataclass(frozen=True)
class Snapshot:
    """The state of the timer; a store keeps everything but `last_actual`."""

    end: datetime | None = None
    """When the countdown reaches zero (timezone-aware UTC); None while idle."""
    started_at: datetime | None = None
    """When the current countdown began (timezone-aware UTC); None while idle, while
    running without a countdown, and for a countdown stored before 0.5.0. Always before
    `end` while both are set."""
    pending: Literal["on", "off"] | None = None
    """The switch the core asked for and has not yet seen the target confirm."""
    owed_settings: Settings = NO_SETTINGS
    """The settings the target was asked to run with and has not yet confirmed to
    have taken. Never set while `pending` is "off"."""
    owed_turn_on_only: bool = False
    """The owed settings may reach the target only inside a `TurnOn`: a schedule window
    owes them, and a target that is already on was set up by someone (§5.4). Never set
    without owed settings."""
    commands: tuple[Command, ...] = ()
    """The pending commands, ordered by `at` and then by when they were added."""
    scheduled_by: str | None = None
    """The interval whose window end the timer carries, while nobody has changed the
    timer since (S2, S3). Always None while `end` is."""
    windows: tuple[Window, ...] = ()
    """The current or next window of every interval, ordered by `start`; at most one
    per interval, and none for a disabled one."""
    disabled_intervals: frozenset[str] = frozenset()
    """The intervals the user switched off. Only intervals that exist stay in it; an
    interval is on until it is named here."""
    last_actual: Actual | None = None
    """The target's last observed state; None until it has been observed, and until
    then it is treated as away, like "unavailable"."""


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
    """Schedule the wake-up alarm for `at` (see `next_wakeup`), replacing any earlier
    one."""

    at: datetime


@dataclass(frozen=True)
class Disarm:
    """Cancel the wake-up alarm: there is nothing to wake up for."""


@dataclass(frozen=True)
class Changed:
    """The snapshot changed: persist it and refresh the entities."""


@dataclass(frozen=True)
class GaveUp:
    """Something was sent again as often as reports alone may send it, and the target
    still does not show it: the switch to "on" or "off", or the owed settings. Said
    once per piece of work; it is not sent again until new work asks for it (see
    `_Allowance`)."""

    what: Literal["on", "off", "settings"]


@dataclass(frozen=True)
class CommandDropped:
    """A command came due after the run it asked for was over (§5.7): it was removed
    without touching the timer. The caller says so, as nothing else shows it."""

    command: Command


type Effect = (
    TurnOn | ApplySettings | TurnOff | Arm | Disarm | Changed | GaveUp | CommandDropped
)

type EndReason = Literal["expired", "stopped", "turned_off"]
"""Why a countdown ended: its end was reached, Timerify stopped it (Run for 0, Stop, a
pending "off", Add time down to zero, a schedule interval switched off while its window
ran), or the target was switched off outside Timerify."""


@dataclass(frozen=True)
class CountdownStarted:
    """A countdown began where none ran, to end at `end`."""

    end: datetime


@dataclass(frozen=True)
class CountdownEnded:
    """The countdown that ran is over, for `reason`."""

    reason: EndReason


@dataclass(frozen=True)
class CommandCameDue:
    """A pending command was carried out at its time. A command dropped for coming too
    late (`CommandDropped`) did nothing and is not announced."""

    command: Command


type Announcement = CountdownStarted | CountdownEnded | CommandCameDue
"""Something that happened to the timer which others may want to hear of. Unlike an
`Effect` it switches nothing."""


def next_wakeup(snapshot: Snapshot) -> datetime | None:
    """When the timer must next be looked at: the earliest of the end, the first
    command, the start of every window not yet started and the end of every window;
    None when there is none."""
    times = [snapshot.end] if snapshot.end is not None else []
    if snapshot.commands:
        times.append(snapshot.commands[0].at)
    for window in snapshot.windows:
        if not window.started:
            times.append(window.start)
        times.append(window.end)
    return min(times, default=None)


def _utc(moment: datetime, what: str = "now") -> datetime:
    """`moment` in UTC, so every end and every command's time is UTC whatever zone the
    caller works in. A naive one is refused, naming it `what`."""
    if moment.utcoffset() is None:
        raise ValueError(f"{what} must be timezone-aware")
    return moment.astimezone(UTC)


def _capped(now: datetime, end: datetime) -> datetime:
    """`end`, but at most a day from `now`."""
    return min(end, now + _MAX_DURATION)


def checked_window(window: Window) -> Window:
    """`window` in UTC, so every start and end is UTC whatever zone the caller works
    in. A naive time, or a window that does not start before it ends or lasts longer
    than a day, is refused with a ValueError, whoever made it: the caller of
    `set_windows`, or the file that a timer is read from."""
    start = _utc(window.start, "the window's start")
    end = _utc(window.end, "the window's end")
    if not start < end <= start + _MAX_DURATION:
        raise ValueError(
            f"the window of {window.interval_id} must start before it ends and last"
            " at most a day"
        )
    return replace(window, start=start, end=end)


def _active(window: Window, now: datetime) -> bool:
    return window.start <= now < window.end


def _inheriting(window: Window, old: Window | None, now: datetime) -> Window:
    """`window`, started and suppressed as `old` is if it is the occurrence that `old`
    already started."""
    if old is None or not (old.started and _active(old, now) and _active(window, now)):
        return window
    return replace(window, started=True, suppressed=window.suppressed or old.suppressed)


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


class _Rank(IntEnum):
    """Which of the items that fall due at one instant goes first. A command goes after
    a window that starts, as P3 makes it the same as setting the timer by hand, and
    before the end of the timer, as it may move it; a window that starts as the timer
    ends extends it, so the end of the timer goes last."""

    WINDOW_END = 0
    WINDOW_START = 1
    COMMAND = 2
    TIMER_END = 3


@dataclass(frozen=True)
class _WindowEnds:
    window: Window


@dataclass(frozen=True)
class _WindowStarts:
    window: Window


type _Item = _WindowEnds | _WindowStarts | Command | Literal["end"]
"""Something that fell due and is folded into the timer: the end of a window, the
start of one, a pending command or the end of the timer."""


class _Allowance:
    """How often reports may send a piece of work again: the pending wish, or the owed
    settings. The first delivery, then `limit` re-sends prompted by reports of any
    kind (a repeat, a change of state, a return from unavailable), then one give-up,
    then nothing. The piece of work has one allowance for its whole life; only new
    work, which `renew` starts, has a new one.

    A device that refuses a command may answer every call with a report, and a device
    that drops off the network comes back with one, so without the bound it would be
    commanded for ever.
    """

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self.renew()

    def renew(self) -> None:
        """New work: nothing of it has been delivered, and nothing is used."""
        self._delivered = False
        self._used = 0
        self._gave_up = False

    def delivered(self) -> None:
        """The work went out in a call: the first delivery is made."""
        self._delivered = True

    def take(self) -> Literal["send", "give_up", "silent"]:
        """What a report that finds the work still not shown may do now. The first
        delivery by this core is free: the work was restored, or made while the target
        was away."""
        if not self._delivered:
            self._delivered = True
            return "send"
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
        """`automatic_resends` is how often reports send a wish, or the owed settings,
        again after the first delivery, before the core gives up."""
        self._mode = mode
        self._default_duration = default_duration
        # Only the first command is ever looked at, so a snapshot that comes from
        # elsewhere is put in order: by time, equal times as they came. Windows are
        # folded by their start, so they are put in order too.
        self._snapshot = replace(
            snapshot,
            commands=tuple(sorted(snapshot.commands, key=lambda c: c.at)),
            windows=tuple(sorted(snapshot.windows, key=lambda w: w.start)),
        )
        self._unsent = False
        """The pending wish has not reached the target (its call failed or changed
        nothing, or the target was away). Only true while a wish is pending; never
        persisted, because a restart sends every stored wish again."""
        self._settings_unsent = False
        """The owed settings have not reached the target, as `_unsent` says of the
        wish. Only true while settings are owed; never persisted either."""
        self._correction: Literal["on", "off"] | None = None
        """The state that a late report of our own call may be corrected to, once. Set
        when the last wish was settled with nothing sent, because the target already
        showed it: a call of ours that the target had not shown yet can still land and
        leave the target the opposite. Any call sent for a wish clears it, so a wish is
        corrected at most once, and so does a change by someone else. It is never set
        while a wish is pending: every wish that is sent or waits starts by clearing
        it. Never persisted, because only the core that made a call can be answered
        by it."""
        self._wish_allowance = _Allowance(automatic_resends)
        """The sends of the pending wish. Only meaningful while a wish is pending: it
        has one for its whole life, and every new wish starts a new one. Never
        persisted: a core starts with a new one, and the first report that finds a
        stored wish unsent makes its free first delivery."""
        self._settings_allowance = _Allowance(automatic_resends)
        """The same for the owed settings: new settings, a command that sends the ones
        owed, and a new wish to turn on while they are owed start a new one."""
        self._announcements: list[Announcement] = []
        """What has happened since the caller last took it (`take_announcements`). Only
        `_set_end` records a start or an end. Never persisted: a core starts with
        nothing to say, so a countdown restored from the file is not announced again."""

    @property
    def snapshot(self) -> Snapshot:
        """The current state, safe to persist."""
        return self._snapshot

    def take_announcements(self) -> list[Announcement]:
        """What happened to the timer since the last call, in the order it happened,
        and forget it. A step returns its effects and leaves its announcements here,
        so the caller takes them once it has saved the snapshot."""
        announced, self._announcements = self._announcements, []
        return announced

    def wanted_running(self, now: datetime) -> bool:
        """Whether the target is wanted running as of `now`: a countdown is under way,
        or else the wish that the target has not confirmed yet says so, or else the
        target was last seen on.

        This is the desired state, as `_runs_as_of` judges it, not what has reached the
        target: a target that is away while its timer counts, and a turn-on that is in
        flight, are running; a turn-off in flight is not. A countdown whose end is `now`
        or earlier is over, whether or not its alarm was handled yet.
        """
        return self._wants_running(_utc(now), None)

    @_reports_change
    def set_duration(
        self,
        now: datetime,
        duration: timedelta,
        settings: Settings = NO_SETTINGS,
    ) -> list[Effect]:
        """Count down `duration` from now; zero or less stops the timer.

        Non-empty `settings` replace the ones that are owed, whoever owed them, and are
        sent with the turn-on, or on their own to a target that is on (P1).
        """
        now = _utc(now)
        return self._run_until(now, now + duration, settings, began=now)

    @_reports_change
    def add(self, now: datetime, delta: timedelta) -> list[Effect]:
        """Move the end by `delta`; on an idle timer only a positive delta starts it.

        An end that is not ahead is no countdown, as `wanted_running` judges it, though
        nothing folded it yet (a command that waited for its turn until after the end,
        #42): the timer is idle.
        """
        now = _utc(now)
        end = self._snapshot.end
        if end is not None and end <= now:
            end = None
        if end is None:
            if delta <= timedelta(0):
                return []
            return self._run_until(now, now + delta, began=now)
        return self._run_until(now, end + delta, began=self._kept_beginning(now))

    @_reports_change
    def stop(self, now: datetime) -> list[Effect]:
        """End the countdown and switch the target off."""
        _utc(now)  # unused, but every command rejects a naive time alike
        return self._stop()

    @_reports_change
    def run_open(self, now: datetime, settings: Settings = NO_SETTINGS) -> list[Effect]:
        """Switch the target on without a duration, with `settings` as `set_duration`
        takes them.

        R9 is for a target that is off: strict mode applies the default duration, and
        loose mode runs with the timer at zero. A target that is wanted running
        already (`wanted_running`) keeps what it has, in either mode: its countdown, or
        its run without one, is not touched, and the timer still belongs to whoever set
        it (S2, S3). The turn-on is asked for again if it has not reached the target,
        and `settings` are set.
        """
        now = _utc(now)
        if self._wants_running(now, None):
            return self._want("on", settings)
        if self._mode == "strict":
            return self._run_until(
                now, now + self._default_duration, settings, began=now
            )
        self._expire_stale_end(now)
        return [self._wakeup(), *self._want("on", settings)]

    @_reports_change
    def add_command(self, now: datetime, command: Command) -> list[Effect]:
        """Keep `command` until its time, after those that are due at the same time."""
        _utc(now)  # unused, but every command rejects a naive time alike
        command = replace(command, at=_utc(command.at, "the command's time"))
        commands = sorted((*self._snapshot.commands, command), key=lambda c: c.at)
        self._snapshot = replace(self._snapshot, commands=tuple(commands))
        return [self._wakeup()]

    def cancel_commands(
        self, now: datetime, command_ids: Iterable[str]
    ) -> tuple[tuple[Command, ...], list[Effect]]:
        """Forget the commands with those ids in one step, and return them, in the order
        they were due, with the effects of the change: those of the timer that is left,
        carried out once.

        `KeyError` for an id that is not there, and nothing changes: a step is all or
        nothing. No ids is a step that changes nothing.
        """
        _utc(now)  # unused, but every command rejects a naive time alike
        wanted = frozenset(command_ids)
        gone = tuple(c for c in self._snapshot.commands if c.id in wanted)
        if unknown := wanted - {c.id for c in gone}:
            raise KeyError(min(unknown))
        return gone, self._forget(wanted)

    @_reports_change
    def _forget(self, command_ids: AbstractSet[str]) -> list[Effect]:
        """Take the commands with those ids, all of them there, out of the snapshot."""
        if not command_ids:
            return []
        kept = tuple(c for c in self._snapshot.commands if c.id not in command_ids)
        self._snapshot = replace(self._snapshot, commands=kept)
        return [self._wakeup()]

    @_reports_change
    def set_windows(
        self,
        now: datetime,
        windows: Iterable[Window],
        *,
        configured: AbstractSet[str],
        keep: AbstractSet[str] = frozenset(),
    ) -> list[Effect]:
        """Replace the windows with the current or next one of each interval.

        `configured` names the intervals that exist: the windows of any other go, and
        so does the flag of any other that is switched off. A switched off interval has
        no window, whatever is given for it. An interval in `keep` keeps the window it
        has, started or not, whatever is given for it: its occurrence could not be
        worked out this time. A new window that is open now and replaces a started one
        that is open now is the same occurrence, perhaps edited, so it does not start
        again. Any other new window is a new occurrence and starts at its start.

        This only merges: the alarm is re-armed, and the next `tick` or `observe`
        folds what the new windows make due and follows an edit (S2).
        """
        now = _utc(now)
        fresh: dict[str, Window] = {}
        for window in map(checked_window, windows):
            if window.interval_id in fresh:
                raise ValueError(f"two windows of the interval {window.interval_id}")
            fresh[window.interval_id] = window
        old = {window.interval_id: window for window in self._snapshot.windows}
        disabled = frozenset(
            interval_id
            for interval_id in self._snapshot.disabled_intervals
            if interval_id in configured
        )

        def runs(interval_id: str) -> bool:
            return interval_id in configured and interval_id not in disabled

        kept = [
            window
            for window in old.values()
            if window.interval_id in keep and runs(window.interval_id)
        ]
        merged = [
            _inheriting(window, old.get(window.interval_id), now)
            for window in fresh.values()
            if window.interval_id not in keep and runs(window.interval_id)
        ]
        self._snapshot = replace(
            self._snapshot,
            windows=tuple(sorted(kept + merged, key=lambda w: w.start)),
            disabled_intervals=disabled,
        )
        return [self._wakeup()]

    @_reports_change
    def set_interval_enabled(
        self, now: datetime, interval_id: str, enabled: bool
    ) -> list[Effect]:
        """Switch an interval on or off.

        Switching off removes its window, which is an edit for S2: the next `tick`
        realigns the timer, or leaves it if somebody changed it since (S3). Switching
        on brings no window back: the caller works it out and merges it with
        `set_windows`.

        Like `set_windows`, this only merges: the alarm is re-armed, and the caller
        follows with `tick`.
        """
        _utc(now)  # unused, but every command rejects a naive time alike
        state = self._snapshot
        if enabled:
            self._snapshot = replace(
                state, disabled_intervals=state.disabled_intervals - {interval_id}
            )
        else:
            self._snapshot = replace(
                state,
                disabled_intervals=state.disabled_intervals | {interval_id},
                windows=tuple(w for w in state.windows if w.interval_id != interval_id),
            )
        return [self._wakeup()]

    @_reports_change
    def tick(self, now: datetime) -> list[Effect]:
        """Handle the wake-up alarm: carry out the end, the commands and the windows
        that are due, and follow an edited window.

        An alarm that fires with nothing due and nothing to follow is a stale leftover
        and does nothing.
        """
        effects, _ = self._catch_up(_utc(now))
        return effects

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
        report of the target, within the limit of `automatic_resends` for the piece of
        work. The caller reports a failure right after executing the effects, before
        anything else reaches the core.
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

        `by_us` says the change came from a service call the core asked for. Such an
        answer may be late: a newer wish can have been settled by the state the target
        showed before the call landed, and the answer then leaves the target the
        opposite of what the timer wants. The core corrects that once for the wish.
        Any later change of the target that is credited to a call of ours is not
        answered: a device that undoes a command by itself, or a switch pressed on the
        wall within the seconds in which Home Assistant credits the entity's writes to
        the last call, would otherwise be commanded again at every change.
        """
        now = _utc(now)
        previous = self._snapshot.last_actual
        repeated = actual == previous
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
        effects, caught_up = self._catch_up(now)
        if actual == "unavailable":
            return effects
        pending = self._snapshot.pending
        if pending is not None and self._unsent:
            if pending == actual:
                self._settle()
                if by_us and actual == "on":
                    # Our own call switched the target on, but the list did not get
                    # through: the settings that did not follow are no longer
                    # turn-on-only, and are sent again on their own.
                    self._snapshot = replace(self._snapshot, owed_turn_on_only=False)
            else:
                effects += self._resend(pending)
        elif by_us:
            if pending == actual:
                self._settle()
            elif (correction := self._correction) is not None and correction != actual:
                effects += self._ask_again(correction)
        elif not repeated and not caught_up:
            # What was due has just decided what the target is to do; it outranks
            # what someone else did to the target.
            effects += self._follow_external_change(now, actual)
        return effects + self._deliver_settings(by_report=True)

    def _wakeup(self) -> Effect:
        """The alarm for what the snapshot waits for next, or none."""
        at = next_wakeup(self._snapshot)
        return Disarm() if at is None else Arm(at)

    def _catch_up(self, now: datetime) -> tuple[list[Effect], bool]:
        """Fold everything that is due by `now` into the timer, in the order it fell
        due: the ends and starts of windows, the commands and the end of the timer at
        or before `now`; then realign the timer with the windows (S2).

        Items that fall due together go in the order of `_Rank`. The end is an item
        only if it is still `<= now` once the items before it are folded in. Each item
        leaves the timer as it would have if it had been carried out when it fell due,
        but the target is asked once, for the last wish: a turn-on and an off that
        were due together switch nothing.

        The realignment is not only the last step. The end of a window realigns the
        timer as of that instant too, but only to hand it to a window that is still
        open, never to stop it: the end of the timer that follows decides, and a window
        that opens just then extends it without an off. The last step, as of `now`, may
        stop the timer.

        Returns the effects, and whether the timer was moved: by the end, an executed
        command, a window that set it or the realignment. A window that left it alone,
        one that was over before it was noticed, a window end and a command dropped
        for coming too late leave it as it was.
        """
        effects: list[Effect] = []
        wish: Literal["on", "off"] | None = None
        due = False
        while (item := self._next_due(now)) is not None:
            due = True
            match item:
                case _WindowEnds(window):
                    self._remove_window(window)
                    handed = self._realign(window.end, may_stop=False)
                    if handed is not None:
                        wish = handed
                case _WindowStarts(window):
                    if self._start_window(now, window, wish):
                        wish = "on"
                case Command():
                    commands = self._snapshot.commands[1:]
                    self._snapshot = replace(self._snapshot, commands=commands)
                    if (command_wish := self._run_command(now, item, wish)) is None:
                        effects.append(CommandDropped(item))
                    else:
                        wish = command_wish
                case "end":
                    self._end_timer(ended_by="expired")
                    wish = "off"
                case unreachable:
                    assert_never(unreachable)
        if (aligned := self._realign(now, may_stop=True)) is not None:
            wish = aligned
        if not due and wish is None:
            return [], False
        effects.append(self._wakeup())
        if wish is not None:
            effects += self._want(wish)
        return effects, wish is not None

    def _next_due(self, now: datetime) -> _Item | None:
        """The item to fold in next: the one that fell due first, by `_Rank` on a tie;
        None when nothing is due."""
        state = self._snapshot
        items: list[tuple[datetime, _Rank, _Item]] = []
        for window in state.windows:
            if window.end <= now:
                items.append((window.end, _Rank.WINDOW_END, _WindowEnds(window)))
            if not window.started and window.start <= now:
                items.append((window.start, _Rank.WINDOW_START, _WindowStarts(window)))
        if state.commands and state.commands[0].at <= now:
            items.append((state.commands[0].at, _Rank.COMMAND, state.commands[0]))
        if state.end is not None and state.end <= now:
            items.append((state.end, _Rank.TIMER_END, "end"))
        if not items:
            return None
        return min(items, key=lambda entry: entry[:2])[2]

    def _remove_window(self, window: Window) -> None:
        """The window is over."""
        windows = tuple(w for w in self._snapshot.windows if w != window)
        self._snapshot = replace(self._snapshot, windows=windows)

    def _start_window(
        self, now: datetime, window: Window, wish: Literal["on", "off"] | None
    ) -> bool:
        """Apply S1 to a window that opens: the timer is set to the window's end,
        unless it ends later, or the window is already over. Returns whether it was
        set; the window never starts again either way.

        The window's settings are owed only if the target does not run as of this item
        (§5.4: a window that opens on a running target pushes nothing), and only to go
        with a turn-on: a target that is found running before one goes out never gets
        them.
        """
        windows = tuple(
            replace(w, started=True) if w == window else w
            for w in self._snapshot.windows
        )
        self._snapshot = replace(self._snapshot, windows=windows)
        end = self._snapshot.end
        if window.end <= now or (end is not None and end >= window.end):
            return False
        self._set_end(window.end, began=window.start, by=window.interval_id)
        if not self._runs_as_of(wish):
            self._owe(window.settings, turn_on_only=True)
        return True

    def _realign(self, at: datetime, *, may_stop: bool) -> Literal["on", "off"] | None:
        """Apply S2: while the timer is the schedule's (`scheduled_by` is set: nobody
        has changed it since, S3), its end is the latest end among the windows that are
        open at `at` and not suppressed, whichever interval was edited; the interval of
        that window carries it. A timer that someone changed is never realigned.

        With no such window the timer stops, but only if `may_stop`: when a window
        ends, the end of the timer that follows it decides (and a window that opens
        just then extends it without an off).

        Returns the wish this leaves, None when the timer's end stays as it is.
        """
        interval_id = self._snapshot.scheduled_by
        if interval_id is None:
            return None
        # Only a window whose start has been folded counts: in the middle of a fold, a
        # window that opens later is not one yet.
        open_windows = [
            w
            for w in self._snapshot.windows
            if w.started and not w.suppressed and _active(w, at)
        ]
        if not open_windows:
            if not may_stop:
                return None
            self._end_timer()
            return "off"
        latest = max(open_windows, key=lambda w: (w.end, w.interval_id == interval_id))
        moved = latest.end != self._snapshot.end
        self._set_end(latest.end, began=self._kept_beginning(at), by=latest.interval_id)
        return "on" if moved else None

    def _run_command(
        self, now: datetime, command: Command, wish: Literal["on", "off"] | None
    ) -> Literal["on", "off"] | None:
        """Fold a command that is due into the timer and return the wish it leaves;
        None if its run was over before it was noticed, which drops it (§5.7). `wish` is
        the wish of the items folded before it.

        A command that turns on sets its settings even when the target is running
        (P1), and is the same as setting the timer by hand (P3): one without minutes is
        a bare turn-on, which leaves the countdown of a target that was wanted running
        at its time as it is (`run_open`).
        """
        if command.action == "off":
            self._announce(CommandCameDue(command))
            self._end_timer()
            return "off"
        end = self._command_end(command)
        if end is not None and end <= now:
            return None
        self._announce(CommandCameDue(command))
        if command.minutes is None and self._wants_running(command.at, wish):
            self._owe(command.settings)
            return "on"
        # With no end to write, this clears an end that the command's time reached.
        self._set_end(
            None if end is None else _capped(now, end),
            began=command.at,
            ended_by="expired",
        )
        self._owe(command.settings)
        return "on"

    def _command_end(self, command: Command) -> datetime | None:
        """When the run of a command that turns on is over, counted from its time;
        None for a run without a countdown (loose mode, no minutes)."""
        if command.minutes is not None:
            return command.at + timedelta(minutes=command.minutes)
        if self._mode == "strict":
            return command.at + self._default_duration
        return None

    def _follow_external_change(
        self, now: datetime, actual: Literal["on", "off"]
    ) -> list[Effect]:
        """Someone else switched the target: the timer follows (R3 to R5)."""
        self._settle()
        # What our own calls said no longer decides: manual wins.
        self._correction = None
        if actual == "off":
            self._clear_settings()  # a target that is off runs with nothing
            self._suppress_windows()
            if self._snapshot.end is None:
                return []
            self._clear_end(ended_by="turned_off")
            return [self._wakeup()]
        if self._mode == "strict" and self._snapshot.end is None:
            return self._run_until(now, now + self._default_duration, began=now)
        return []

    def _run_until(
        self,
        now: datetime,
        end: datetime,
        settings: Settings = NO_SETTINGS,
        *,
        began: datetime | None,
    ) -> list[Effect]:
        """Count down to `end`, at most a day from now, or stop if it is not ahead.
        The countdown began at `began`: now, or when the one that was running did.

        A countdown whose end is not ahead is over, folded or not (#42): it is
        announced as expired before anything new, so a stop that follows has none to
        end, and a new end is a start, not a move.
        """
        self._expire_stale_end(now)
        if end <= now:
            return self._stop()
        self._set_end(_capped(now, end), began=began)
        return [self._wakeup(), *self._want("on", settings)]

    def _stop(self) -> list[Effect]:
        self._end_timer()
        return [self._wakeup(), *self._want("off")]

    def _end_timer(self, *, ended_by: EndReason = "stopped") -> None:
        """The countdown is over, for `ended_by`: there is no end, and nothing to run
        with."""
        self._clear_end(ended_by=ended_by)
        self._clear_settings()
        self._suppress_windows()

    def _suppress_windows(self) -> None:
        """The target is wanted off: a window that has started does not turn it on
        again before its next occurrence (S4), whoever stopped it."""
        windows = tuple(
            replace(w, suppressed=True) if w.started else w
            for w in self._snapshot.windows
        )
        self._snapshot = replace(self._snapshot, windows=windows)

    def _set_end(
        self,
        end: datetime | None,
        *,
        began: datetime | None,
        by: str | None = None,
        ended_by: EndReason = "stopped",
    ) -> None:
        """The only writer of the end and of the beginning of the countdown it counts
        down to, and so the only place that announces a start or an end. `by` names the
        interval whose window end it is (S1, S2); every other write, whoever made it,
        leaves the timer to nobody's schedule (S3), and a timer with no end is nobody's.

        `began` is when the countdown began: the caller works it out, a countdown that
        goes on with a new end through `_kept_beginning`. None where there is none to
        say, and always None for a timer with no end.

        Going from no end to an end announces a start; going from an end to none
        announces an end, for `ended_by`. Moving the end announces nothing: it is the
        same countdown.
        """
        before = self._snapshot.end
        if before is None and end is not None:
            self._announce(CountdownStarted(end))
        elif before is not None and end is None:
            self._announce(CountdownEnded(ended_by))
        self._snapshot = replace(
            self._snapshot,
            end=end,
            started_at=None
            if end is None or began is None
            else _utc(began, "the beginning"),
            scheduled_by=None if end is None else by,
        )

    def _kept_beginning(self, at: datetime) -> datetime | None:
        """The beginning of the running countdown for a write of its end as of `at`:
        no later than `at`, so that a clock that stepped back cannot leave it at or
        after an end that is ahead. None where it has none (it never had one, or
        nothing runs)."""
        kept = self._snapshot.started_at
        return None if kept is None else min(kept, at)

    def _clear_end(self, *, ended_by: EndReason = "stopped") -> None:
        """There is no countdown: no end, no beginning, nobody's schedule."""
        self._set_end(None, began=None, ended_by=ended_by)

    def _expire_stale_end(self, now: datetime) -> None:
        """Clear an end that is not ahead of `now`, announcing it as expired: it is no
        countdown, as `wanted_running` judges it, though nothing folded it yet."""
        end = self._snapshot.end
        if end is not None and end <= now:
            self._clear_end(ended_by="expired")

    def _announce(self, announcement: Announcement) -> None:
        self._announcements.append(announcement)

    def _want(
        self,
        target: Literal["on", "off"],
        settings: Settings = NO_SETTINGS,
    ) -> list[Effect]:
        """Ask for the target to be switched, once per direction, and for the settings
        to be set when the target is wanted on.

        A command can arrive while the opposite service call is still in flight,
        so both directions share this one algorithm. A wish that never reached
        the target is not in flight: it is sent again, or dropped if the target
        is already where the new wish wants it. Settings go with the turn-on this
        causes; a target that needs none, because it is on or its turn-on is on its
        way, gets them alone, unless they may only go with a turn-on.

        A target that is away, or has not been seen yet, is sent nothing: the wish is
        recorded as unsent, and the report that shows the target sends it.
        """
        state = self._snapshot
        self._correction = None  # a new wish ends the permission given by the last
        in_flight = state.pending is not None and not self._unsent
        if in_flight and state.pending == target:
            return self._settings_for_running_target(settings)
        if not in_flight and state.last_actual == target:
            self._settle()
            # Nothing is sent, but an older call of ours may still land and show the
            # opposite (see `_correction`).
            self._correction = target
            return self._settings_for_running_target(settings)
        self._snapshot = replace(state, pending=target)  # replaces an opposite wish
        self._wish_allowance.renew()  # new work, whatever became of the last wish
        if target == "on" and state.owed_settings:
            # Asking to run the target again asks for the settings it owes: they are
            # delivered with this turn-on, or on the target's return if it is away.
            self._settings_allowance.renew()
        self._owe(settings)  # they ride with the turn-on this causes
        if state.last_actual in (None, "unavailable"):
            self._unsent = True
            return []  # applied when the target is seen, or back
        return self._send(target)

    def _settings_for_running_target(self, settings: Settings) -> list[Effect]:
        """The settings of a command that needs no turn-on: owed and sent to a target
        that runs. Settings that may only go with a turn-on, owed earlier and still
        owed, are dropped by `_deliver_settings`, not sent."""
        self._owe(settings)
        return self._deliver_settings(by_report=False)

    def _send(self, target: Literal["on", "off"]) -> list[Effect]:
        self._unsent = False
        self._correction = None  # a call is on its way: it is what reports answer
        self._wish_allowance.delivered()
        if target == "off":
            return [TurnOff()]
        self._settings_unsent = False  # a turn-on takes the owed settings along
        self._settings_allowance.delivered()
        return [TurnOn(self._snapshot.owed_settings)]

    def _resend(self, wish: Literal["on", "off"]) -> list[Effect]:
        """Send a wish again because the target reported and does not show it.

        The first delivery by this core costs nothing. After it a report of any kind
        is answered `automatic_resends` times in all, whatever the target did in
        between, then the core gives up once and sends nothing more until new work
        wants the wish (see `_Allowance`).
        """
        match self._wish_allowance.take():
            case "give_up":
                return [GaveUp(wish)]
            case "silent":
                return []
        return self._send(wish)

    def _ask_again(self, correction: Literal["on", "off"]) -> list[Effect]:
        """Make the wished state the pending wish again, and send it. An answer to a
        call of ours shows the opposite and nothing was pending, because the wish was
        settled by the state the target had before that call landed.

        Sending uses up the permission (`_correction`), so this is the one correction
        of the wish. The correction is new work, and so is always sent. If the new call
        does not land either, the wish is pending like any other that did not reach
        the target, and the reports that follow are answered within the allowance that
        the correction started.
        """
        self._snapshot = replace(self._snapshot, pending=correction)
        self._wish_allowance.renew()
        return self._send(correction)

    def _owe(self, settings: Settings, *, turn_on_only: bool = False) -> None:
        """Make `settings`, if there are any, the ones the target has yet to take, and
        say whether they may only go with a turn-on. Empty settings change nothing."""
        if settings:
            self._snapshot = replace(
                self._snapshot, owed_settings=settings, owed_turn_on_only=turn_on_only
            )
            self._settings_unsent = True
            self._settings_allowance.renew()

    def _deliver_settings(self, *, by_report: bool) -> list[Effect]:
        """Send the owed settings that have not reached the target, if it can take them.

        A target that is away, or has not been seen yet, gets nothing: a wish restored
        from the file counts as in flight, but its target is not known to be there. A
        turn-on that is yet to go out takes the settings itself. Settings that may only
        go with a turn-on are never sent on their own: a target that runs without the
        turn-on that was to carry them (it came back on, someone switched it on, the
        one on its way carries none) has been set up by someone, so they are dropped
        (§5.4). Only a turn-on of ours that switched the target on but did not get its
        settings through releases them (`observe`). `by_report` says a report of the
        target asked: it is answered within the allowance, like a wish. A command that
        asks sends them and starts a new allowance.
        """
        state = self._snapshot
        if not (state.owed_settings and self._settings_unsent):
            return []
        runs = state.last_actual == "on" or (state.pending == "on" and not self._unsent)
        if state.last_actual in (None, "unavailable") or not runs:
            return []
        if state.owed_turn_on_only:
            self._clear_settings()
            return []
        if by_report:
            match self._settings_allowance.take():
                case "give_up":
                    return [GaveUp("settings")]
                case "silent":
                    return []
        else:
            self._settings_allowance.renew()  # a command always sends
            self._settings_allowance.delivered()
        self._settings_unsent = False
        return [ApplySettings(state.owed_settings)]

    def _wants_running(self, at: datetime, wish: Literal["on", "off"] | None) -> bool:
        """Whether the target is wanted running at `at`, the instant an item falls due
        or a command gets its turn: a countdown that ends after `at`, or, with none
        under way, what `_runs_as_of` says of `wish`.

        A countdown that ends at `at` or before is over, whether or not it was folded
        yet, so a command that falls due as it ends meets a target that is about to be
        off, and so does one that gets its turn after a slow call.
        """
        end = self._snapshot.end
        if end is not None:
            return end > at
        return self._runs_as_of(wish)

    def _runs_as_of(self, wish: Literal["on", "off"] | None) -> bool:
        """Whether the target is wanted running as of a fold item: the wish so far says
        so or, with no wish yet, the pending wish does, or, with none pending, the
        target is on.

        This is the desired state, not what has reached the target: a turn-on that
        failed, or waits for an unavailable target, or is a restored wish, is still
        wanted, and what it carries (P1, R8) is not for a window to replace. Whether
        owed settings can be sent now is another question, which `_deliver_settings`
        answers.
        """
        if wish is not None:
            return wish == "on"
        state = self._snapshot
        if state.pending is not None:
            return state.pending == "on"
        return state.last_actual == "on"

    def _clear_settings(self) -> None:
        """Nothing is owed: the target took the settings, or they no longer apply."""
        self._snapshot = replace(
            self._snapshot, owed_settings=NO_SETTINGS, owed_turn_on_only=False
        )
        self._settings_unsent = False

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
