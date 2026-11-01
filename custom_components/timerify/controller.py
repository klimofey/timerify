"""Home Assistant glue around the timer core: events go in, effects are carried out.

The core decides; this module owns everything that touches Home Assistant. Commands,
target state changes, alarms and the refresh of the schedule windows all run under one
lock, so the core sees them strictly one after another and an effect is finished before
the next event is looked at.
"""

import asyncio
import logging
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import replace
from datetime import date, datetime, timedelta
from functools import cached_property
from typing import Any, Literal, assert_never
from uuid import uuid4

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    Event,
    EventStateChangedData,
    HomeAssistant,
    ServiceResponse,
    callback,
)
from homeassistant.exceptions import (
    ConfigEntryError,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
    async_track_state_report_event,
)
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

from .const import (
    CONF_MODE,
    CONF_TARGET,
    CONF_WORKDAY_SENSOR,
    DOMAIN,
    MAX_COMMAND_AHEAD,
    MAX_COMMANDS,
    MAX_LISTED_INTERVALS,
    MAX_MINUTES,
    SERVICE_CALL_TIMEOUT,
    SUBENTRY_INTERVAL,
    WORKDAY_DOMAIN,
    SettingValue,
    default_duration_minutes,
    freeze_settings,
)
from .core import (
    ApplySettings,
    Arm,
    Changed,
    Command,
    CommandDropped,
    Disarm,
    Effect,
    GaveUp,
    Snapshot,
    TimerCore,
    TurnOff,
    TurnOn,
    Window,
    remaining_minutes,
)
from .domains import TargetCall, actual_state, behaviour_for, validate_settings
from .schedule import Interval, title_key, weekday_window, workday_window
from .store import TimerStore
from .target import target_name

_LOGGER = logging.getLogger(__name__)

_REMEMBERED_CONTEXTS = 16
"""How many of our own service calls are still recognised when the target reports
them. Commands run one at a time, so only the calls of the last few can have a report
in flight."""

type Label = Literal["on", "off", "settings"]
"""What a list of service calls is for: switching the target on or off, or setting
what it runs with."""

type TimerifyConfigEntry = ConfigEntry[TargetController]


def _local_time(moment: datetime) -> str:
    """`moment` the way the user reads the clock: Home Assistant's time zone, with its
    offset."""
    return dt_util.as_local(moment).isoformat(sep=" ", timespec="seconds")


def duration_out_of_range() -> ServiceValidationError:
    """The refusal of a timer that would run for no time or for more than a day."""
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="duration_out_of_range",
        translation_placeholders={"max_hours": str(MAX_MINUTES // 60)},
    )


def command_too_far() -> ServiceValidationError:
    """The refusal of a command set more than `MAX_COMMAND_AHEAD` ahead."""
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="command_too_far",
        translation_placeholders={"days": str(MAX_COMMAND_AHEAD.days)},
    )


def command_when(delay: timedelta | None, at: datetime | None) -> datetime | timedelta:
    """When a command is due, as exactly one of a delay from now and a moment is given.

    Raises ServiceValidationError (`delay_or_at`) for both and for neither.
    """
    if delay is not None and at is None:
        return delay
    if at is not None and delay is None:
        return at
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="delay_or_at"
    )


def _refuse_a_run_of_off(
    minutes: int | None, settings: Mapping[str, Any] | None
) -> None:
    """Raise ServiceValidationError (`off_takes_no_duration_or_settings`) for a command
    to turn off that is given minutes to run or settings to run with."""
    if minutes is not None or settings:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="off_takes_no_duration_or_settings",
        )


def _due(
    now: datetime,
    when: datetime | timedelta,
    ahead: timedelta,
    too_far: Callable[[], ServiceValidationError],
) -> datetime:
    """The moment a command that gets its turn at `now` is due: `when`, or `when` from
    now.

    Raises ServiceValidationError (`command_in_past`) for a moment that is not ahead,
    and the error `too_far` makes for one more than `ahead` ahead. A delay is compared
    with `ahead` before it is added to `now`: one of centuries is no date at all.
    """
    if isinstance(when, timedelta) and when > ahead:
        raise too_far()
    at = now + when if isinstance(when, timedelta) else when
    if at <= now:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="command_in_past",
            translation_placeholders={"at": _local_time(at)},
        )
    if at > now + ahead:
        raise too_far()
    return at


def _unloaded_error() -> HomeAssistantError:
    return HomeAssistantError(
        translation_domain=DOMAIN, translation_key="timer_unloaded"
    )


class _WorkdayUnknown(Exception):
    """The Workday sensor could not say whether a day is a working day; the reason is
    logged where it is found."""


def _workday_answer(response: ServiceResponse, sensor: str) -> bool | None:
    """Whether `workday.check_date` called the day a working day, in its answer about
    `sensor`; None when the answer says nothing of the kind."""
    about_sensor = (response or {}).get(sensor)
    answer = about_sensor.get("workday") if isinstance(about_sensor, dict) else None
    return answer if isinstance(answer, bool) else None


class TargetController:
    """Runs the timer of one target entity.

    Every command (`async_set_minutes`, `async_add_minutes`, `async_run`,
    `async_add_command`, `async_turn_off_in`, `async_cancel_command`,
    `async_cancel_commands`, `async_set_interval_enabled`,
    `async_set_schedule_enabled`) waits for its turn and raises HomeAssistantError
    (`timer_unloaded`) if the timer was unloaded meanwhile. While Home Assistant is
    still starting, a command first folds what fell due before it, without the target
    (`_async_catch_up_while_starting_locked`).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TimerifyConfigEntry,
        store: TimerStore,
        snapshot: Snapshot,
    ) -> None:
        options = entry.options
        self._hass = hass
        self._entry = entry
        self._store = store
        target = er.async_resolve_entity_id(er.async_get(hass), options[CONF_TARGET])
        if target is None:
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="target_not_found"
            )
        self.target_entity_id = target
        self._behaviour = behaviour_for(target)
        # The store keeps no `last_actual`: nothing is known about the target after
        # a restart, so its first report counts as the target coming back.
        self._core = TimerCore(
            options[CONF_MODE],
            timedelta(minutes=default_duration_minutes(options)),
            snapshot,
            automatic_resends=self._behaviour.automatic_resends,
        )
        self._intervals = {
            interval.id: interval
            for interval in map(
                Interval.from_subentry, entry.get_subentries_of_type(SUBENTRY_INTERVAL)
            )
        }
        self._workday_sensor: str | None = options.get(CONF_WORKDAY_SENSOR)
        if self._workday_sensor is None and any(
            interval.days != "weekdays" for interval in self._intervals.values()
        ):
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="workday_sensor_missing"
            )
        self._workday_unanswered = False
        """Whether the last question to the Workday sensor went unanswered, so that an
        outage is logged once, not at every question."""
        self._left_out: dict[str, frozenset[str]] = {}
        """For each interval, the names of the settings that the target could not take
        when its window was last worked out, so that they are said once, not at every
        refresh."""
        self._lock = asyncio.Lock()
        self._stopped = False
        self._started = False
        """Whether start-up has taken stock of the target (`_handle_started`). Until it
        has, nothing is sent to the target, no alarm is armed and no report of the
        target is answered, because the target has not been seen. A command given
        meanwhile still takes effect at its own moment, after what fell due before it
        (`_async_catch_up_while_starting_locked`), and its outcome is saved."""
        self._own_contexts = deque[str](maxlen=_REMEMBERED_CONTEXTS)
        self._listeners: list[Callable[[], None]] = []
        self._notified_end = self.snapshot.end
        self._notified_started_at = self.snapshot.started_at
        self._notified_commands = self.snapshot.commands
        self._notified_disabled = self.snapshot.disabled_intervals
        self._wakeup_alarm: CALLBACK_TYPE | None = None
        self._refresh_alarm: CALLBACK_TYPE | None = None
        self._raised_for: tuple[Label, object] | None = None
        """The work of a list of calls (see `_work_of`) whose failure was logged with a
        traceback, with the label of the list."""

    @cached_property
    def device_name(self) -> str:
        """The name of the device made for a target that is on none: the name the
        user knows the target by, looked up once per timer."""
        return target_name(self._hass, self.target_entity_id)

    @property
    def snapshot(self) -> Snapshot:
        """The timer's current state."""
        return self._core.snapshot

    def wanted_running(self, now: datetime) -> bool:
        """Whether the target is wanted running as of `now`, by the one judgement that
        every answer and every decision shares (`TimerCore.wanted_running`)."""
        return self._core.wanted_running(now)

    async def async_start(self) -> None:
        """Follow the target; once Home Assistant is running, take stock of it."""
        self._entry.async_on_unload(self._stop)
        self._entry.async_on_unload(
            async_track_state_change_event(
                self._hass, self.target_entity_id, self._handle_state_change
            )
        )
        self._entry.async_on_unload(async_at_started(self._hass, self._handle_started))

    async def async_set_minutes(self, minutes: int) -> None:
        """Count down `minutes` from now; zero stops the timer.

        Raises ServiceValidationError (`duration_out_of_range`), before anything runs,
        for fewer than 0 minutes or more than a day.
        """
        if not 0 <= minutes <= MAX_MINUTES:
            raise duration_out_of_range()
        await self._command(
            lambda now: self._core.set_duration(now, timedelta(minutes=minutes))
        )

    async def async_add_minutes(self, minutes: int) -> None:
        """Move the end of the countdown by `minutes`, which may be negative.

        The end is never more than a day ahead: adding past it runs for a day, and
        taking off as much as a day leaves nothing, whoever asks and however much. The
        count is bounded before it becomes a time, as a delay is (`_due`): a day either
        way is all that can change the end, and a count of centuries is no time.
        """
        bounded = max(-MAX_MINUTES, min(minutes, MAX_MINUTES))
        await self._command(lambda now: self._core.add(now, timedelta(minutes=bounded)))

    async def async_run(
        self, minutes: int | None = None, settings: Mapping[str, Any] | None = None
    ) -> None:
        """Switch the target on for `minutes`, or without a duration, with `settings` if
        there are any.

        Without a duration, a target that is off runs for the default one in strict
        mode and without a countdown in loose mode (R9); one that is wanted running
        keeps its countdown (`TimerCore.run_open`).

        Raises ServiceValidationError, before anything runs, for `minutes` outside 1 to
        a day (`duration_out_of_range`) and for settings that the target cannot take.
        """
        if minutes is not None and not 1 <= minutes <= MAX_MINUTES:
            raise duration_out_of_range()
        owed = validate_settings(self._hass, self.target_entity_id, settings or {})
        if minutes is None:
            await self._command(lambda now: self._core.run_open(now, owed))
        else:
            duration = timedelta(minutes=minutes)
            await self._command(
                lambda now: self._core.set_duration(now, duration, owed)
            )

    async def async_add_command(
        self,
        action: Literal["on", "off"],
        when: datetime | timedelta,
        minutes: int | None,
        settings: Mapping[str, Any] | None,
    ) -> str:
        """Keep a command to turn the target `action` and return its id.

        `when` is the moment it is due, or how long from now: a delay is counted from
        the moment the command gets its turn, so a call that waits behind a slow
        device is not found to be late. `minutes` is how long an "on" runs and
        `settings` what it turns the target on with; an "off" takes neither.

        Raises ServiceValidationError, before anything is kept, for an "off" with
        either, for `minutes` outside 1 to a day (`duration_out_of_range`), for settings
        that the target cannot take, for a time that is not ahead or is more than
        `MAX_COMMAND_AHEAD` ahead (`command_too_far`, whatever the delay is), and when
        the timer already keeps `MAX_COMMANDS`.
        """
        if action == "off":
            _refuse_a_run_of_off(minutes, settings)
        if minutes is not None and not 1 <= minutes <= MAX_MINUTES:
            raise duration_out_of_range()
        owed = validate_settings(self._hass, self.target_entity_id, settings or {})
        command_id = uuid4().hex

        def add(now: datetime) -> list[Effect]:
            at = _due(now, when, MAX_COMMAND_AHEAD, command_too_far)
            if len(self.snapshot.commands) >= MAX_COMMANDS:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="too_many_commands",
                    translation_placeholders={
                        "target": target_name(self._hass, self.target_entity_id),
                        "limit": str(MAX_COMMANDS),
                    },
                )
            return self._core.add_command(
                now, Command(command_id, at, action, minutes, owed)
            )

        await self._command(add)
        return command_id

    async def async_turn_off_in(
        self,
        when: datetime | timedelta,
        minutes: int | None = None,
        settings: Mapping[str, Any] | None = None,
    ) -> bool:
        """Have the target turned off at `when`, a moment or how long from now, and say
        whether it was: set the countdown to end then if the target is wanted running,
        change nothing if it is not.

        Whether it is wanted running is judged when the call gets its turn, from the
        desired state (see `TimerCore.wanted_running`), so a turn-on or a turn-off that
        the target has not confirmed yet counts, and a target that is away while its
        timer counts is running (R10). The countdown is set as by hand: whatever time
        was left is replaced, shorter or longer.

        Raises ServiceValidationError, before anything runs, for `minutes` or `settings`
        (an "off" has neither: `off_takes_no_duration_or_settings`), and when the call
        gets its turn, for a moment that is not ahead (`command_in_past`, which a zero
        delay is) or is more than a day ahead (`duration_out_of_range`, whatever the
        delay is), whether or not the target is running.
        """
        _refuse_a_run_of_off(minutes, settings)
        running = False

        def turn_off_at(now: datetime) -> list[Effect]:
            nonlocal running
            at = _due(now, when, timedelta(minutes=MAX_MINUTES), duration_out_of_range)
            running = self._core.wanted_running(now)
            if not running:
                return []
            return self._core.set_duration(now, at - now)

        await self._command(turn_off_at)
        return running

    async def async_cancel_command(self, command_id: str) -> Command:
        """Forget the pending command with that id and return it.

        Raises ServiceValidationError (`unknown_command`) when this timer keeps no such
        command.
        """
        cancelled: tuple[Command, ...] = ()

        def cancel(now: datetime) -> list[Effect]:
            nonlocal cancelled
            try:
                cancelled, effects = self._core.cancel_commands(now, [command_id])
            except KeyError as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unknown_command",
                    translation_placeholders={"command_id": command_id},
                ) from err
            return effects

        await self._command(cancel)
        return cancelled[0]

    async def async_cancel_commands(
        self, which: Literal["next", "all"]
    ) -> tuple[Command, ...]:
        """Forget the pending command that is due first, or every one, and return what
        was forgotten, in the order the commands are due; nothing when none is pending.

        Which commands there are is judged when the call gets its turn, so a command
        that was added while it waited is cancelled with the rest. Of commands that are
        due together the first to be added is the first.
        """
        cancelled: tuple[Command, ...] = ()

        def cancel(now: datetime) -> list[Effect]:
            nonlocal cancelled
            pending = self.snapshot.commands
            chosen = pending[:1] if which == "next" else pending
            cancelled, effects = self._core.cancel_commands(
                now, [command.id for command in chosen]
            )
            return effects

        await self._command(cancel)
        return cancelled

    async def async_set_interval_enabled(self, interval_id: str, enabled: bool) -> None:
        """Switch a schedule interval on or off.

        Switching off is an edit of the schedule (S2): the window goes and the timer,
        if the schedule's, follows at once. Switching on works the interval's window
        out and, if it is open, the target runs for the rest of it. The flag is kept in
        the timer's file; nothing is reloaded.

        Switching on is one change: the flag is recorded and shown with the window, once
        the window is known, which may mean waiting for the Workday sensor. A timer that
        is unloaded meanwhile changes nothing and says so. An interval that is on
        already is left as it is: nothing is worked out and nobody is asked. While Home
        Assistant is still starting, the switch comes after what fell due before it
        (`_async_catch_up_while_starting_locked`), and the target is switched at
        start-up.
        """
        async with self._lock:
            self._raise_if_unloaded()
            await self._async_catch_up_while_starting_locked()
            await self._async_set_interval_enabled_locked(interval_id, enabled)

    async def async_set_schedule_enabled(
        self, enabled: bool, interval: str | None = None
    ) -> tuple[str, ...]:
        """Switch the whole schedule on or off, or the intervals that carry the title
        `interval` (compared as `title_key` compares), and return the titles of the
        intervals that are now as asked, in the order of the schedule, whether or not
        they were already.

        Each interval is switched as its own switch switches it
        (`async_set_interval_enabled`), one after the other under one hold of the lock,
        so that no other command comes between them. The intervals are those the entry
        has: one that was deleted is no interval, even before the timer has reloaded
        and let go of it.

        Raises ServiceValidationError, before anything is switched, when the timer has
        no interval (`no_schedule`) and when none has the title (`unknown_interval`,
        which lists the titles that can be asked for, and says how many it leaves out
        when it is long; `no_interval_titles` when there is none, every title being
        nothing but punctuation). A timer that is unloaded part-way says so
        (`timer_unloaded`); the intervals switched until then stay switched.
        """
        async with self._lock:
            self._raise_if_unloaded()
            every_title = {
                interval_id: subentry.title
                for interval_id in self._intervals
                if (subentry := self._entry.subentries.get(interval_id)) is not None
            }
            if not every_title:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="no_schedule",
                    translation_placeholders={
                        "target": target_name(self._hass, self.target_entity_id)
                    },
                )
            titles = every_title
            if interval is not None:
                wanted = title_key(interval)
                titles = {
                    interval_id: title
                    for interval_id, title in every_title.items()
                    if wanted and title_key(title) == wanted
                }
                if not titles:
                    raise self._unknown_interval(interval, every_title.values())
            await self._async_catch_up_while_starting_locked()
            for interval_id in titles:
                self._raise_if_unloaded()
                await self._async_set_interval_enabled_locked(interval_id, enabled)
            return tuple(titles.values())

    def _unknown_interval(
        self, asked: str, titles: Iterable[str]
    ) -> ServiceValidationError:
        """The refusal of a title that no interval has. It lists the titles that can be
        asked for, so that the one who asked can ask again: those that are not nothing
        but punctuation, each once (titles that `title_key` makes one are one, and the
        first of them is written), the first `MAX_LISTED_INTERVALS` of them and the
        number of the others.

        The titles go into the message bare, apart by semicolons (a title may have a
        comma, as the one an interval is made with does): the quotes around them are
        for the translation of each language to choose.
        """
        target = target_name(self._hass, self.target_entity_id)
        first_of_each: dict[str, str] = {}
        for title in titles:
            if key := title_key(title):
                first_of_each.setdefault(key, title)
        askable = list(first_of_each.values())
        if not askable:
            return ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_interval_titles",
                translation_placeholders={"target": target},
            )
        listed = askable[:MAX_LISTED_INTERVALS]
        placeholders = {
            "target": target,
            "interval": asked,
            "intervals": "; ".join(listed),
        }
        key = "unknown_interval"
        if len(listed) < len(askable):
            key = "unknown_interval_and_more"
            placeholders["more"] = str(len(askable) - len(listed))
        return ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=key,
            translation_placeholders=placeholders,
        )

    async def _async_set_interval_enabled_locked(
        self, interval_id: str, enabled: bool
    ) -> None:
        """Switch a schedule interval on or off, as `async_set_interval_enabled` says;
        the caller holds the lock, has seen that the timer is not unloaded and, while
        Home Assistant is still starting, has folded what fell due before the switch
        (`_async_catch_up_while_starting_locked`)."""
        now = dt_util.utcnow()
        if enabled and interval_id not in self.snapshot.disabled_intervals:
            return
        if enabled:
            effects = self._core.set_interval_enabled(now, interval_id, True)
            if not await self._async_refresh_windows_locked(effects):
                raise _unloaded_error()
        else:
            effects = self._core.set_interval_enabled(now, interval_id, False)
            # The tick folds what fell due while this call waited for its turn. A
            # window that it finds over is replaced like any other (the interval that
            # was switched off is not: its window left with the flag).
            await self._fold_due(now, effects)

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Call `listener` whenever what the entities show may have changed."""
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            self._listeners.remove(listener)

        return remove

    async def _command(self, command: Callable[[datetime], list[Effect]]) -> None:
        """Run `command` with the time now and carry out its effects; while Home
        Assistant is still starting, after what fell due before it
        (`_async_catch_up_while_starting_locked`).

        Raises HomeAssistantError, having done nothing, if the timer was unloaded
        before its turn came: the call reached the timer, so returning as if the
        change had been made would be a lie.
        """
        async with self._lock:
            self._raise_if_unloaded()
            await self._async_catch_up_while_starting_locked()
            await self._execute(command(dt_util.utcnow()))

    async def _async_catch_up_while_starting_locked(self) -> None:
        """Before start-up has taken stock, bring the timer up to now as start-up
        would, so that a command given now comes after what fell due before it, as it
        would with Home Assistant running: the windows are worked out and merged, and
        the stored end, the commands and the windows that fell due while Home Assistant
        was down are folded in, in the order they fell due. Once start-up has taken
        stock, the alarms do that, and this does nothing.

        The fold changes the timer only. The target has not been seen, so nothing is
        sent to it (`TimerCore` treats it as away), and no alarm is armed (`_arm`):
        the target is switched at start-up, once. The caller holds the lock and has
        seen that the timer is not unloaded. Raises HomeAssistantError
        (`timer_unloaded`) if it was unloaded while the windows were worked out: the
        command is not made.
        """
        if self._started:
            return
        await self._async_refresh_windows_locked()
        self._raise_if_unloaded()

    def _raise_if_unloaded(self) -> None:
        """Raise HomeAssistantError (`timer_unloaded`) if the timer was unloaded: a call
        that reached it and waited for its turn would otherwise be reported as done."""
        if self._stopped:
            raise _unloaded_error()

    async def _async_windows(
        self, now: datetime
    ) -> tuple[list[Window], frozenset[str]]:
        """The window of each interval that is switched on and open at `now` or comes
        next, in the time zone of Home Assistant, and the ids of the intervals whose
        occurrence could not be worked out, whose windows are then left as they are.

        An interval that is switched off has no window, and nothing is asked to work one
        out. An interval of working days or days off asks the Workday sensor about the
        days it looks at, each day once however many intervals look at it. The first
        question that gets no answer ends the questions: every such interval of this
        round is unknown, since what is wrong with the sensor is wrong for them all.
        """
        zone = dt_util.get_default_time_zone()
        disabled = self.snapshot.disabled_intervals
        answers: dict[date, bool] = {}
        unanswered = False

        async def is_workday(day: date) -> bool:
            if day not in answers:
                answers[day] = await self._async_is_workday(day)
            return answers[day]

        windows: list[Window] = []
        unknown: set[str] = set()
        for configured in self._intervals.values():
            if configured.id in disabled:
                continue
            interval = self._with_settings_the_target_takes(configured)
            if interval.days == "weekdays":
                window = weekday_window(interval, now, zone)
            elif unanswered:
                unknown.add(interval.id)
                continue
            else:
                try:
                    window = await workday_window(interval, now, zone, is_workday)
                except _WorkdayUnknown:
                    unanswered = True
                    unknown.add(interval.id)
                    continue
            if window is not None:
                windows.append(window)
        return windows, frozenset(unknown)

    def _with_settings_the_target_takes(self, interval: Interval) -> Interval:
        """`interval` with only the settings the target can be turned on with now.

        They were checked when the interval was saved, and what the target takes can
        change after that: an update of its integration renames a mode, or the device
        is replaced. A setting it no longer takes would fail its call, and the window
        would turn nothing on. Each setting is judged alone, as the form offers them.
        What is left out is said once, for as long as it is.
        """
        taken: dict[str, SettingValue] = {}
        for name, value in interval.settings.items():
            try:
                validate_settings(self._hass, self.target_entity_id, {name: value})
            except ServiceValidationError:
                continue
            taken[name] = value
        left_out = frozenset(interval.settings) - frozenset(taken)
        if left_out != self._left_out.get(interval.id, frozenset()):
            if left_out:
                self._left_out[interval.id] = left_out
                # An interval deleted since the timer was loaded is named by its id:
                # its title went with it, and the reload that follows lets it go.
                subentry = self._entry.subentries.get(interval.id)
                _LOGGER.warning(
                    "The schedule interval %s of %s asks for settings that the target"
                    " cannot take now (%s); it is turned on without them",
                    interval.id if subentry is None else subentry.title,
                    self.target_entity_id,
                    ", ".join(sorted(left_out)),
                )
            else:
                del self._left_out[interval.id]
        return (
            replace(interval, settings=freeze_settings(taken)) if left_out else interval
        )

    async def _async_is_workday(self, day: date) -> bool:
        """Ask the Workday sensor whether `day` is a working day, as the sensor says it:
        its day offset, if it has one, is included.

        Raises _WorkdayUnknown, having logged why (once per outage), when the sensor
        cannot say: the call fails, which it does for a sensor that is unavailable or
        gone, or takes longer than a service call may, or the answer is not one. A call
        that raises something else, a bug in the integration or a change to its service,
        is a call that fails too: it must not stop the timer.
        """
        sensor = self._workday_sensor
        assert sensor is not None  # An interval that asks has a sensor: see __init__.
        reason: object
        unexpected: Exception | None = None
        try:
            async with asyncio.timeout(SERVICE_CALL_TIMEOUT.total_seconds()):
                response = await self._hass.services.async_call(
                    WORKDAY_DOMAIN,
                    "check_date",
                    {ATTR_ENTITY_ID: sensor, "check_date": day},
                    blocking=True,
                    return_response=True,
                )
        except HomeAssistantError as err:
            reason = err
        except TimeoutError:
            reason = f"no answer within {SERVICE_CALL_TIMEOUT.total_seconds():g} s"
        except Exception as err:
            reason = f"{type(err).__name__}: {err}"
            unexpected = err
        else:
            if (answer := _workday_answer(response, sensor)) is not None:
                self._workday_unanswered = False
                return answer
            reason = f"it answered {response!r}"
        self._log_workday_unknown(day, reason, unexpected)
        raise _WorkdayUnknown

    def _log_workday_unknown(
        self, day: date, reason: object, unexpected: Exception | None
    ) -> None:
        """Say that the Workday sensor could not be asked about `day`, once for as long
        as it cannot be: the next answer ends the outage, and a later one is logged
        again. An error nobody expected is logged with its traceback."""
        if not self._workday_unanswered:
            self._workday_unanswered = True
            _LOGGER.warning(
                "Could not ask %s whether %s is a working day (%s);"
                " the schedule of %s waits until it reports",
                self._workday_sensor,
                day,
                reason,
                self.target_entity_id,
                exc_info=unexpected,
            )

    def _set_windows(
        self, now: datetime, windows: list[Window], unknown: frozenset[str]
    ) -> list[Effect]:
        """Merge the freshly worked out `windows` into the timer, which holds only the
        windows of the intervals there are."""
        return self._core.set_windows(
            now, windows, configured=self._intervals.keys(), keep=unknown
        )

    async def _async_refresh_windows_locked(
        self, effects: Sequence[Effect] = ()
    ) -> bool:
        """Work out the windows again and fold them into the timer: the new windows are
        merged and followed at once, so that the timer does not rest, or is stored,
        between an edited window and the timer that follows it (S2). `effects` are those
        of a change that is made with them, and are carried out with them.

        The caller holds the lock. Returns False, with the timer untouched but for
        what `effects` are of, when the timer was unloaded while the windows were worked
        out: its entry is being replaced, and the new timer would find this one's stale
        save. A window that is over by the time they are worked out, which asking the
        Workday sensor may take that long, is replaced like any other that a fold finds
        over.
        """
        windows, unknown = await self._async_windows(dt_util.utcnow())
        if self._stopped:
            return False
        now = dt_util.utcnow()
        await self._fold_due(now, [*effects, *self._set_windows(now, windows, unknown)])
        return True

    async def _refresh_windows(self) -> None:
        """Work out the windows again, for an event that does not hold the lock."""
        async with self._lock:
            if not self._stopped:
                await self._async_refresh_windows_locked()

    async def _handle_core_config_update(self, event: Event[Mapping[str, Any]]) -> None:
        """A window is a moment in the time zone it was worked out in: when the zone
        changes, the windows are worked out again."""
        if "time_zone" in event.data:
            await self._refresh_windows()

    async def _handle_started(self, _hass: HomeAssistant) -> None:
        """Take stock of the target once, with Home Assistant fully started.

        The windows come first: the stored ones are merged with the ones worked out
        now, so that the first observation folds both in one catch-up (§5.7). Until
        then no report of the target was answered (`_started`), so the target is read
        here, not from the reports it made on the way. A command given meanwhile has
        already folded what fell due before it; this folds what fell due since.
        """
        async with self._lock:
            if self._stopped:
                return
            # The zone and the Workday sensor are followed from here on: a change
            # meanwhile is not lost, and waits for the lock, so it folds windows only
            # after the first observation.
            self._entry.async_on_unload(
                self._hass.bus.async_listen(
                    EVENT_CORE_CONFIG_UPDATE, self._handle_core_config_update
                )
            )
            self._follow_workday_sensor()
            windows, unknown = await self._async_windows(dt_util.utcnow())
            if self._stopped:
                return
            now = dt_util.utcnow()
            # Merging the windows arms the alarm for the next thing the timer waits for,
            # which the observation does not do for a timer restored unchanged. Nothing
            # is armed earlier (`_arm` waits for `_started`): an alarm would fold a
            # stored end, command or window that has long passed without the windows of
            # now. A command given meanwhile folds them after working the windows out,
            # and the first observation folds the rest.
            effects = self._set_windows(now, windows, unknown)
            self._schedule_refresh()
            before = self.snapshot
            state = self._hass.states.get(self.target_entity_id)
            effects += self._core.observe(now, actual_state(state), by_us=False)
            self._started = True  # the alarms in `effects` are armed from here
            await self._execute_fold(before, effects)

    def _follow_workday_sensor(self) -> None:
        """Work the windows out again whenever the Workday sensor changes or reports.

        A report that repeats its state counts too: Workday writes its state at every
        midnight of the house, which is how a question that failed while the sensor
        stayed as it was is asked again within a day.
        """
        if (sensor := self._workday_sensor) is None:
            return
        for track in (async_track_state_change_event, async_track_state_report_event):
            self._entry.async_on_unload(
                track(self._hass, sensor, self._handle_workday_report)
            )

    async def _handle_workday_report(self, _event: Event[Any]) -> None:
        await self._refresh_windows()

    async def _handle_state_change(self, event: Event[EventStateChangedData]) -> None:
        async with self._lock:
            if self._stopped or not self._started:
                return  # `_handle_started` reads the state itself
            before = self.snapshot
            effects = self._core.observe(
                dt_util.utcnow(),
                actual_state(event.data["new_state"]),
                by_us=event.context.id in self._own_contexts,
            )
            await self._execute_fold(before, effects)

    async def _handle_wakeup(self, _scheduled: datetime) -> None:
        async with self._lock:
            if self._stopped:
                return
            await self._fold_due(dt_util.utcnow(), [])

    async def _fold_due(self, now: datetime, effects: list[Effect]) -> None:
        """Carry out `effects`, which the caller has just made the core produce, and
        whatever falls due at `now` on top of them, and say what came due while the
        target is unavailable. Every event that folds what is due goes through here:
        the alarm, the refresh of the windows and the switching off of an interval."""
        before = self.snapshot
        effects = effects + self._core.tick(now)
        self._log_due_while_unavailable(before, now, effects)
        await self._execute_fold(before, effects)

    async def _execute_fold(self, before: Snapshot, effects: list[Effect]) -> None:
        """Carry out the effects of a fold of what fell due, which `tick` and `observe`
        make; the snapshot before it is `before`.

        A window the fold found over is replaced by the next one of its interval. That
        goes for whichever event folds it: a report of the target may get the lock
        before the alarm of the end does, and the alarm then finds nothing due. It goes
        for the fold of a refresh too, since asking the Workday sensor may take until a
        window that was just worked out is over.
        """
        ended = {w.interval_id for w in before.windows} - {
            w.interval_id for w in self.snapshot.windows
        }
        await self._execute(effects)
        if ended and not self._stopped:
            await self._async_refresh_windows_locked()

    def _log_due_while_unavailable(
        self, before: Snapshot, now: datetime, effects: list[Effect]
    ) -> None:
        """Say what came due while the target is away, worded by what it was: nothing
        else shows that a switch waits for the target to come back (R10)."""
        after = self.snapshot
        if after.last_actual != "unavailable":
            return
        # A window whose start set the timer wants the target on, if its window is
        # still open when it is back; one that left the timer alone, or was over, did
        # not.
        if any(
            not window.started
            and window.start <= now
            and after.scheduled_by == window.interval_id
            and after.end == window.end
            for window in before.windows
        ):
            _LOGGER.info(
                "A schedule window of %s started while it is unavailable;"
                " it is turned on when it is back, if the window is still open then",
                self.target_entity_id,
            )
        # A countdown that ended is one that wants the target off; a command that was
        # due with it may have moved the end or made the target wanted on instead.
        if (
            before.end is not None
            and before.end <= now
            and after.end is None
            and after.pending == "off"
        ):
            _LOGGER.info(
                "The timer of %s ended while it is unavailable;"
                " it is turned off when it is back",
                self.target_entity_id,
            )
        dropped = {e.command.id for e in effects if isinstance(e, CommandDropped)}
        kept = {command.id for command in after.commands}
        if any(c.id not in kept and c.id not in dropped for c in before.commands):
            # What it wants is applied when the target is back, if still relevant
            # then (R10): a run that is over by then starts nothing.
            _LOGGER.info(
                "A pending command for %s came due while it is unavailable;"
                " it is applied when it is back, if it is still relevant then",
                self.target_entity_id,
            )

    @callback
    def _handle_refresh(self, _scheduled: datetime) -> None:
        self._schedule_refresh()
        self._notify()

    async def _execute(self, effects: list[Effect]) -> None:
        self._forget_settled_failure()
        if any(isinstance(effect, Changed) for effect in effects):
            # Saved ahead of the effects: a service call may take up to
            # SERVICE_CALL_TIMEOUT, and a restart meanwhile must find the new timer.
            await self._store.async_save(self.snapshot)
            if not self._stopped:
                # Shown at once too: the entities must not wait for a slow device.
                self._refresh_entities()
        for effect in effects:
            if self._stopped:
                return  # Unloaded while an earlier effect was under way.
            match effect:
                case TurnOn(settings):
                    await self._carry_out(
                        "on",
                        self._behaviour.turn_on_calls(settings),
                        with_settings=bool(settings),
                    )
                case ApplySettings(settings):
                    await self._carry_out(
                        "settings",
                        self._behaviour.apply_calls(settings),
                        with_settings=True,
                    )
                case TurnOff():
                    await self._carry_out(
                        "off",
                        (TargetCall(*self._behaviour.off_service, {}),),
                        with_settings=False,
                    )
                case Arm(at):
                    self._arm(at)
                case Disarm():
                    self._disarm()
                case Changed():
                    pass  # Saved and shown ahead of the other effects.
                case GaveUp(what):
                    self._log_gave_up(what)
                case CommandDropped(command):
                    self._log_dropped(command)
                case _:
                    assert_never(effect)

    def _refresh_entities(self) -> None:
        self._schedule_refresh()
        # The entities show the end of the countdown and when it began, the pending
        # commands and which intervals are switched off; the rest of the snapshot is
        # bookkeeping that needs no state write.
        if (
            self.snapshot.end != self._notified_end
            or self.snapshot.started_at != self._notified_started_at
            or self.snapshot.commands != self._notified_commands
            or self.snapshot.disabled_intervals != self._notified_disabled
        ):
            self._notify()

    def _log_dropped(self, command: Command) -> None:
        _LOGGER.info(
            "Dropped the pending command to turn %s %s at %s:"
            " the run it asked for was already over",
            self.target_entity_id,
            command.action,
            _local_time(command.at),
        )

    def _log_gave_up(self, what: Label) -> None:
        attempts = self._behaviour.automatic_resends + 1
        noun = "attempt" if attempts == 1 else "attempts"
        if what == "settings":
            _LOGGER.warning(
                "%s did not take its settings after %d %s; Timerify will not send"
                " them again until it is asked again",
                self.target_entity_id,
                attempts,
                noun,
            )
        else:
            _LOGGER.warning(
                "%s did not turn %s after %d %s; Timerify will not send it again"
                " until it is asked again",
                self.target_entity_id,
                what,
                attempts,
                noun,
            )

    async def _carry_out(
        self, label: Label, calls: Sequence[TargetCall], *, with_settings: bool
    ) -> None:
        """Make the calls one after the other and tell the core how it went.

        The first call that fails ends the list. A list that switches the target must
        also leave it in the state it was meant to: accepted but ignored counts as
        failed, so the core sends it again. A list that carried settings and did not
        fail has delivered them.
        """
        for call in calls:
            if not await self._call(label, call):
                await self._not_delivered()
                return
            if self._stopped:
                return  # Unloaded while the call was under way.
        if label != "settings":
            actual = actual_state(self._hass.states.get(self.target_entity_id))
            if actual != label:
                # Accepted, but nothing changed (yet): a device out of reach, or one
                # that confirms later. Not worth a warning; the core sends it again
                # on a later report, within its limit of automatic re-sends.
                _LOGGER.debug(
                    "%s accepted the calls to turn %s but reports %s",
                    self.target_entity_id,
                    label,
                    actual,
                )
                await self._not_delivered()
                return
        if with_settings:
            await self._execute(self._core.settings_applied(dt_util.utcnow()))

    async def _call(self, label: Label, call: TargetCall) -> bool:
        """Make one service call as ourselves; False, after logging why, if it fails."""
        context = Context()
        self._own_contexts.append(context.id)
        try:
            async with asyncio.timeout(SERVICE_CALL_TIMEOUT.total_seconds()):
                await self._hass.services.async_call(
                    call.domain,
                    call.service,
                    {ATTR_ENTITY_ID: self.target_entity_id, **call.data},
                    blocking=True,
                    context=context,
                )
        except HomeAssistantError as err:
            self._log_failure(label, err)
            return False
        except TimeoutError:
            self._log_failure(
                label, f"no answer within {SERVICE_CALL_TIMEOUT.total_seconds():g} s"
            )
            return False
        except Exception as err:
            # Another integration's bug. It must not stop the effects that follow
            # or leave the work counted as on its way: it is sent again like one
            # the device rejected.
            self._log_raised(label, err)
            return False
        return True

    def _what_failed(self, label: Label) -> str:
        if label == "settings":
            return f"Could not apply settings to {self.target_entity_id}"
        return f"Could not turn {self.target_entity_id} {label}"

    def _log_failure(self, label: Label, reason: object) -> None:
        _LOGGER.warning("%s: %s", self._what_failed(label), reason)

    def _work_of(self, label: Label) -> object:
        """What a label's calls are for: the wish for a switch, the owed settings for
        settings. A failure lasts as long as its work does."""
        return (
            self.snapshot.owed_settings
            if label == "settings"
            else self.snapshot.pending
        )

    def _log_raised(self, label: Label, err: Exception) -> None:
        """Log what another integration's service raised: the traceback the first time
        for a piece of work, a line for each repeat, as a bug that persists repeats on
        every report of the target."""
        work = (label, self._work_of(label))
        if self._raised_for == work:
            _LOGGER.warning(
                "%s: its service raised %r again", self._what_failed(label), err
            )
            return
        self._raised_for = work
        _LOGGER.error(
            "%s: its service raised an unexpected error",
            self._what_failed(label),
            exc_info=err,
        )

    def _forget_settled_failure(self) -> None:
        """Let a failure that was logged with a traceback be logged with one again once
        its work is settled: the wish is no longer pending, or the settings are
        cleared or replaced."""
        if self._raised_for is not None:
            label, work = self._raised_for
            if self._work_of(label) != work:
                self._raised_for = None

    async def _not_delivered(self) -> None:
        """Tell the core the target did not get the wish or the settings, so they are
        sent again."""
        await self._execute(self._core.call_failed(dt_util.utcnow()))

    def _arm(self, at: datetime) -> None:
        """Wake up at `at` to carry out what is due, replacing any earlier alarm.

        Nothing is armed until start-up has taken stock; it arms the first alarm."""
        if self._stopped or not self._started:
            return
        self._disarm()
        self._wakeup_alarm = async_track_point_in_utc_time(
            self._hass, self._handle_wakeup, at
        )

    def _disarm(self) -> None:
        """Cancel the wake-up alarm; there may be none."""
        if self._wakeup_alarm is not None:
            self._wakeup_alarm()
            self._wakeup_alarm = None

    def _schedule_refresh(self) -> None:
        """Wake up when the rounded-up remaining minutes next change."""
        self._cancel_refresh()
        end = self.snapshot.end
        if self._stopped or end is None:
            return
        remaining = remaining_minutes(self.snapshot, dt_util.utcnow())
        if remaining <= 1:
            return  # The wake-up comes at the end, and its change notifies.
        self._refresh_alarm = async_track_point_in_utc_time(
            self._hass,
            self._handle_refresh,
            end - timedelta(minutes=remaining - 1),
        )

    def _cancel_refresh(self) -> None:
        if self._refresh_alarm is not None:
            self._refresh_alarm()
            self._refresh_alarm = None

    def _stop(self) -> None:
        """Make an unloaded controller inert: work already waiting is dropped."""
        self._stopped = True
        self._disarm()
        self._cancel_refresh()

    def _notify(self) -> None:
        self._notified_end = self.snapshot.end
        self._notified_started_at = self.snapshot.started_at
        self._notified_commands = self.snapshot.commands
        self._notified_disabled = self.snapshot.disabled_intervals
        for listener in list(self._listeners):
            listener()
