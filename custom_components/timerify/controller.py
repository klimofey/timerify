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
from datetime import UTC, date, datetime, timedelta
from functools import cached_property
from typing import Any, Literal, assert_never
from uuid import uuid4

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import ATTR_ENTITY_ID, EVENT_CORE_CONFIG_UPDATE, Platform
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
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import dt as dt_util

from .const import (
    CONF_MODE,
    CONF_TARGET,
    CONF_WORKDAY_SENSOR,
    DOMAIN,
    EVENT_COMMAND_DUE,
    EVENT_COUNTDOWN_ENDED,
    EVENT_COUNTDOWN_STARTED,
    KEY_RUN_FOR,
    MAX_COMMAND_AHEAD,
    MAX_COMMANDS,
    MAX_LISTED_INTERVALS,
    MAX_MINUTES,
    SERVICE_CALL_TIMEOUT,
    SUBENTRY_INTERVAL,
    WORKDAY_DOMAIN,
    Settings,
    SettingValue,
    default_duration_minutes,
    freeze_settings,
    limit_minutes,
    timer_unique_id,
)
from .core import (
    Announcement,
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
    remaining_minutes,
)
from .domains import (
    TargetCall,
    actual_state,
    behaviour_for,
    settings_not_taken,
    validate_settings,
)
from .issues import (
    TARGET_DELETED,
    async_clear,
    async_clear_settings_not_taken,
    async_clear_settings_warnings,
    async_raise_settings_not_taken,
    async_raise_target_deleted,
    async_warned_settings,
)
from .schedule import (
    Interval,
    async_title_labels,
    spoken_aliases,
    title_key,
    weekday_window,
    workday_window,
)
from .store import TimerStore
from .target import target_name

_LOGGER = logging.getLogger(__name__)

_REMEMBERED_CONTEXTS = 16
"""How many of our own service calls are still recognised when the target reports
them. Commands run one at a time, so only the calls of the last few can have a report
in flight."""

_SETTING_LABELS = (
    f"component.{DOMAIN}.config_subentries.interval.step.user.sections.settings.data"
)
"""The start of the translation keys that label the settings in the form of an
interval, which the warning of an interval names its settings by."""

type Label = Literal["on", "off", "settings"]
"""What a list of service calls is for: switching the target on or off, or setting
what it runs with."""

type TimerifyConfigEntry = ConfigEntry[TargetController]


def _ends_at(end: datetime) -> str:
    """The end as the Ends at sensor states it: ISO 8601 in UTC, to the second."""
    return end.astimezone(UTC).isoformat(timespec="seconds")


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
    given: datetime,
    when: datetime | timedelta,
    ahead: timedelta,
    too_far: Callable[[], ServiceValidationError],
) -> datetime:
    """The moment a command given at `given` is due: `when`, or `when` after `given`.

    Raises ServiceValidationError (`command_in_past`) for a moment that was not ahead
    of `given`, and the error `too_far` makes for one more than `ahead` ahead of it. A
    delay is compared with `ahead` before it is added to `given`: one of centuries is
    no date at all.
    """
    if isinstance(when, timedelta) and when > ahead:
        raise too_far()
    at = given + when if isinstance(when, timedelta) else when
    if at <= given:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="command_in_past",
            translation_placeholders={"at": _local_time(at)},
        )
    if at > given + ahead:
        raise too_far()
    return at


def _unloaded_error() -> HomeAssistantError:
    return HomeAssistantError(
        translation_domain=DOMAIN, translation_key="timer_unloaded"
    )


def _name_keys(subentry: ConfigSubentry, labels: Mapping[str, str]) -> set[str]:
    """What an interval is meant by, as `title_key` compares: its title and, while it
    has the title Timerify gave it, the times it can be said by (`spoken_aliases`).
    `labels` are the words of a title in the language of the house."""
    return {
        title_key(name) for name in (subentry.title, *spoken_aliases(subentry, labels))
    }


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

    A command, a report of the target and an alarm take their moment when they are
    raised, before they wait for their turn, and have the outcome they would have had
    at that moment (`_command`, `_handle_state_change`, `_handle_wakeup`). The two
    switches of intervals, the start-up and the refresh of the windows take theirs when
    they get their turn: they learn the windows from the Workday sensor, and fold them
    to the time it answered.
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
        limit = limit_minutes(options)
        self._core = TimerCore(
            options[CONF_MODE],
            timedelta(minutes=default_duration_minutes(options)),
            snapshot,
            automatic_resends=self._behaviour.automatic_resends,
            limit=None if limit is None else timedelta(minutes=limit),
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
        self._left_out = set[tuple[str, SettingValue]]()
        """The settings, as (name, value), that the target could not take when they were
        last sent, so that each is said once for as long as it is left out, not at every
        call."""
        self._settings_warned = dict[str, tuple[str, ...]]()
        """The names of the settings that this load raised the warning of each interval
        with, by the id of its subentry (`_async_check_interval_settings`)."""
        self._settings_warned_before = dict[str, tuple[str, ...]]()
        """The warnings that an earlier load raised, or that Home Assistant kept through
        a restart, with the names they were raised with. This load judges each of them
        once, and it moves to `_settings_warned` or is taken away
        (`_reconcile_settings_warnings`)."""
        self._lock = asyncio.Lock()
        self._stopped = False
        self._target_deleted = False
        """Whether the target is deleted, so that a repair says the timer switches
        nothing (`_set_target_deleted`)."""
        self._started = False
        """Whether start-up has taken stock of the target (`_handle_started`). Until it
        has, nothing is sent to the target and no report of the target is answered,
        because the target has not been seen. A command given meanwhile still takes
        effect at its own moment, after what fell due before it
        (`_async_catch_up_while_starting_locked`), and its outcome is saved."""
        self._own_contexts = deque[str](maxlen=_REMEMBERED_CONTEXTS)
        self._listeners: list[Callable[[], None]] = []
        self._notified_end = self.snapshot.end
        self._notified_started_at = self.snapshot.started_at
        self._notified_limit_at = self.snapshot.limit_at
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
        """Follow the target; once Home Assistant is running, take stock of it.

        The repair of a deleted target lives with the loaded timer: it goes when the
        timer is unloaded, and start-up raises it again if the target is still gone. The
        warnings of the intervals outlive the unload (`_release_settings_warnings`).
        """
        self._entry.async_on_unload(self._stop)
        self._entry.async_on_unload(
            lambda: async_clear(self._hass, TARGET_DELETED, self._entry.entry_id)
        )
        self._reconcile_settings_warnings()
        self._entry.async_on_unload(self._release_settings_warnings)
        self._entry.async_on_unload(
            async_track_state_change_event(
                self._hass, self.target_entity_id, self._handle_state_change
            )
        )
        self._entry.async_on_unload(async_at_started(self._hass, self._handle_started))

    async def async_target_removed(self) -> None:
        """The target left the entity registry: the user deleted it, or its device.

        The timer stays loaded and keeps its countdown and its commands. It switches
        nothing until the target is back (`_set_target_deleted`), which its repair
        says. The state of the target goes with the entity, and the core takes that for
        a target that is away.
        """
        self._set_target_deleted(True)

    async def async_set_minutes(
        self, minutes: int, *, context: Context | None = None
    ) -> None:
        """Count down `minutes` from now; zero stops the timer.

        The events that it causes carry `context`, as do those of every command below
        that takes one: the context of the call, button, sentence or switch that gave
        it, None when nobody did (`_announce`).

        Raises ServiceValidationError (`duration_out_of_range`), before anything runs,
        for fewer than 0 minutes or more than a day.
        """
        if not 0 <= minutes <= MAX_MINUTES:
            raise duration_out_of_range()
        await self._command(
            lambda now: self._core.set_duration(now, timedelta(minutes=minutes)),
            context,
        )

    async def async_add_minutes(
        self, minutes: int, *, context: Context | None = None
    ) -> None:
        """Move the end of the countdown by `minutes`, which may be negative.

        The end is never more than a day ahead: adding past it runs for a day, and
        taking off as much as a day leaves nothing, whoever asks and however much. The
        count is bounded before it becomes a time, as a delay is (`_due`): a day either
        way is all that can change the end, and a count of centuries is no time.
        """
        bounded = max(-MAX_MINUTES, min(minutes, MAX_MINUTES))
        await self._command(
            lambda now: self._core.add(now, timedelta(minutes=bounded)), context
        )

    async def async_run(
        self,
        minutes: int | None = None,
        settings: Mapping[str, Any] | None = None,
        *,
        context: Context | None = None,
    ) -> None:
        """Switch the target on for `minutes`, or without a duration, with `settings` if
        there are any.

        Without a duration, a target that is off runs to the end of the schedule window
        that is open, if one is, and in strict mode the default duration is kept when it
        ends later (#58); otherwise it runs for the default duration in strict mode and
        without a countdown in loose mode (R9). One that is wanted running keeps its
        countdown (`TimerCore.run_open`).

        Raises ServiceValidationError, before anything runs, for `minutes` outside 1 to
        a day (`duration_out_of_range`) and for settings that the target cannot take.
        """
        if minutes is not None and not 1 <= minutes <= MAX_MINUTES:
            raise duration_out_of_range()
        owed = validate_settings(self._hass, self.target_entity_id, settings or {})
        if minutes is None:
            await self._command(lambda now: self._core.run_open(now, owed), context)
        else:
            duration = timedelta(minutes=minutes)
            await self._command(
                lambda now: self._core.set_duration(now, duration, owed), context
            )

    async def async_add_command(
        self,
        action: Literal["on", "off"],
        when: datetime | timedelta,
        minutes: int | None,
        settings: Mapping[str, Any] | None,
        *,
        context: Context | None = None,
    ) -> str:
        """Keep a command to turn the target `action` and return its id.

        `when` is the moment it is due, or how long from now: a delay is counted from
        the moment the command was given, so a call that waits behind a slow device is
        not found to be late, and one whose delay passed while it waited is carried out
        at once. `minutes` is how long an "on" runs and `settings` what it turns the
        target on with; an "off" takes neither.

        Raises ServiceValidationError, before anything is kept, for an "off" with
        either, for `minutes` outside 1 to a day (`duration_out_of_range`), for settings
        that the target cannot take, for a time that was not ahead when the command was
        given, though it may have passed while the call waited (`command_in_past`, which
        a zero delay is), or is more than `MAX_COMMAND_AHEAD` ahead of it
        (`command_too_far`, whatever the delay is), and when the timer already keeps
        `MAX_COMMANDS`.
        """
        if action == "off":
            _refuse_a_run_of_off(minutes, settings)
        if minutes is not None and not 1 <= minutes <= MAX_MINUTES:
            raise duration_out_of_range()
        owed = validate_settings(self._hass, self.target_entity_id, settings or {})
        command_id = uuid4().hex

        def add(given: datetime) -> list[Effect]:
            at = _due(given, when, MAX_COMMAND_AHEAD, command_too_far)
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
                given, Command(command_id, at, action, minutes, owed)
            )

        await self._command(add, context)
        return command_id

    async def async_turn_off_in(
        self,
        when: datetime | timedelta,
        minutes: int | None = None,
        settings: Mapping[str, Any] | None = None,
        *,
        context: Context | None = None,
    ) -> datetime | None:
        """Have the target turned off at `when`, a moment or how long from now: set the
        countdown to end then if the target is wanted running, and return that end;
        change nothing if it is not, and return None. The end may have passed by the
        time the call returns, when it waited behind a slow device: the target is then
        turned off at once.

        A delay is counted from the moment the call was given. Whether the target is
        wanted running is judged at that moment too, on the timer as the calls ahead of
        it left it, from the desired state (see `TimerCore.wanted_running`), so a
        turn-on or a turn-off that the target has not confirmed yet counts, and a target
        that is away while its timer counts is running (R10). The countdown is set as
        by hand: whatever time was left is replaced, shorter or longer.

        Raises ServiceValidationError, before anything runs, for `minutes` or `settings`
        (an "off" has neither: `off_takes_no_duration_or_settings`), and when the call
        gets its turn, for a moment that was not ahead when it was given
        (`command_in_past`, which a zero delay is) or is more than a day ahead of it
        (`duration_out_of_range`, whatever the delay is), whether or not the target is
        running.
        """
        _refuse_a_run_of_off(minutes, settings)
        end: datetime | None = None

        def turn_off_at(given: datetime) -> list[Effect]:
            nonlocal end
            at = _due(
                given, when, timedelta(minutes=MAX_MINUTES), duration_out_of_range
            )
            if not self._core.wanted_running(given):
                return []
            end = at
            return self._core.set_duration(given, at - given)

        await self._command(turn_off_at, context)
        return end

    async def async_cancel_command(
        self, command_id: str, *, context: Context | None = None
    ) -> Command:
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

        await self._command(cancel, context)
        return cancelled[0]

    async def async_cancel_commands(
        self, which: Literal["next", "all"], *, context: Context | None = None
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

        await self._command(cancel, context)
        return cancelled

    async def async_set_interval_enabled(
        self, interval_id: str, enabled: bool, *, context: Context | None = None
    ) -> None:
        """Switch a schedule interval on or off.

        Switching off is an edit of the schedule (S2): the window goes and the timer,
        if the schedule's, follows at once. Switching on works the interval's window
        out and, if it is open, the target runs for the rest of it. The flag is kept in
        the timer's file; nothing is reloaded.

        Switching on is one change: the flag is recorded and shown with the window, once
        the window is known, which may mean waiting for the Workday sensor. A timer that
        is unloaded meanwhile changes nothing and says so. An interval that is on
        already is left as it is: nothing is worked out and nobody is asked for it.

        While Home Assistant is still starting, the switch comes after the catch-up
        (`_async_catch_up_while_starting_locked`), which works the windows out and
        asks the Workday sensor as start-up would, whether or not the interval is on
        already. The target is switched at start-up.
        """
        async with self._lock:
            self._raise_if_unloaded()
            await self._async_catch_up_while_starting_locked()
            await self._async_set_interval_enabled_locked(interval_id, enabled, context)

    async def async_set_schedule_enabled(
        self,
        enabled: bool,
        interval: str | None = None,
        *,
        context: Context | None = None,
    ) -> tuple[str, ...]:
        """Switch the whole schedule on or off, or the intervals that carry the title
        `interval` (compared as `title_key` compares) or, while they still have the
        title Timerify gave them, start at the time `interval` says (`spoken_aliases`),
        and return the titles of the intervals that are now as asked, in the order of
        the schedule, whether or not they were already.

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
            every_interval = {
                interval_id: subentry
                for interval_id in self._intervals
                if (subentry := self._entry.subentries.get(interval_id)) is not None
            }
            if not every_interval:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="no_schedule",
                    translation_placeholders={
                        "target": target_name(self._hass, self.target_entity_id)
                    },
                )
            chosen = every_interval
            if interval is not None:
                wanted = title_key(interval)
                labels = await async_title_labels(
                    self._hass, self._hass.config.language
                )
                chosen = {
                    interval_id: subentry
                    for interval_id, subentry in every_interval.items()
                    if wanted and wanted in _name_keys(subentry, labels)
                }
                if not chosen:
                    raise self._unknown_interval(
                        interval,
                        (subentry.title for subentry in every_interval.values()),
                    )
            await self._async_catch_up_while_starting_locked()
            for interval_id in chosen:
                self._raise_if_unloaded()
                await self._async_set_interval_enabled_locked(
                    interval_id, enabled, context
                )
            return tuple(subentry.title for subentry in chosen.values())

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
        self, interval_id: str, enabled: bool, context: Context | None
    ) -> None:
        """Switch a schedule interval on or off, as `async_set_interval_enabled` says;
        the caller holds the lock, has seen that the timer is not unloaded and, while
        Home Assistant is still starting, has folded what fell due before the switch
        (`_async_catch_up_while_starting_locked`).

        The switch is the cause of what follows from it: the countdown that an interval
        switched on inside its open window starts, and the one that a switched off
        interval's window had running ends, carry `context` (`_execute_fold`)."""
        now = dt_util.utcnow()
        if enabled and interval_id not in self.snapshot.disabled_intervals:
            return
        if enabled:
            effects = self._core.set_interval_enabled(now, interval_id, True)
            if not await self._async_refresh_windows_locked(effects, context=context):
                raise _unloaded_error()
        else:
            effects = self._core.set_interval_enabled(now, interval_id, False)
            # The tick folds what fell due while this call waited for its turn. A
            # window that it finds over is replaced like any other (the interval that
            # was switched off is not: its window left with the flag).
            await self._fold_due(now, effects, context=context)

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Call `listener` whenever what the entities show may have changed."""
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            self._listeners.remove(listener)

        return remove

    async def _command(
        self, command: Callable[[datetime], list[Effect]], context: Context | None
    ) -> None:
        """Run `command` with the moment it was given and carry out its effects; while
        Home Assistant is still starting, after what fell due before that moment
        (`_async_catch_up_while_starting_locked`).

        The events of the command carry `context`, the cause that gave it. What is
        carried out before it, the catch-up and the pending commands that fell due, is
        time's doing and has none (`_announce`).

        The moment is read before the command waits for the lock, which a slow call to
        the target holds for up to the time the call may take, so the command has the
        outcome it would have had at that moment: time added to a countdown that ended
        while it waited still extends the countdown, and a delay counts from it. The
        lock serves its waiters in the order they came, so the moments of commands do
        not go back. The pending commands that fell due before that moment are carried
        out first, each batch on its own, as their alarm would
        (`TimerCore.fold_commands_due`): an alarm that is armed in the past is raised
        only when it is armed, so it would queue behind a command given later. What
        else falls due between that moment and the time the command gets its turn stays
        armed, and its alarm folds it after the command.

        Raises HomeAssistantError, having done nothing, if the timer was unloaded
        before its turn came: the call reached the timer, so returning as if the
        change had been made would be a lie. So does one that was unloaded while the
        pending commands were carried out: the command is then not made.
        """
        given = dt_util.utcnow()
        async with self._lock:
            self._raise_if_unloaded()
            await self._async_catch_up_while_starting_locked(given)
            # A pending command that fell due before `given` comes before this one,
            # though its alarm, armed in the past, queues behind it. It is carried out
            # as its alarm would, on its own, and the command after it: each has its
            # own save, announcements and calls to the target, and each answers for its
            # own failure. A command that is refused leaves what it folded carried out.
            # It goes through the sink of every fold, so that what came due while the
            # target is away is said (`_execute_fold`), and has no context: it is
            # time's doing.
            before = self.snapshot
            if folded := self._core.fold_commands_due(given):
                await self._execute_fold(before, given, folded)
                self._raise_if_unloaded()
            await self._execute(command(given), context)

    async def _async_catch_up_while_starting_locked(
        self, at: datetime | None = None
    ) -> None:
        """Before start-up has taken stock, bring the timer up to `at`, now when it is
        None, as start-up would, so that a command given then comes after what fell due
        before it, as it would with Home Assistant running: the windows are worked out
        and merged, and the stored end, the commands and the windows that fell due
        while Home Assistant was down are folded in, in the order they fell due. After
        start-up has taken stock this returns at once; after an earlier command while
        starting, the alarms it armed have folded what came due since, and this finds
        little to fold.

        The fold changes the timer only, and so do the alarms it arms: the target has
        not been seen, so nothing is sent to it (`TimerCore` treats it as away), and
        the target is switched at start-up, once. The caller holds the lock and has
        seen that the timer is not unloaded. Raises HomeAssistantError
        (`timer_unloaded`) if it was unloaded while the windows were worked out: the
        command is not made.
        """
        if self._started:
            return
        await self._async_refresh_windows_locked(at=at)
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
        for interval in self._intervals.values():
            if interval.id in disabled:
                continue
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
        self,
        effects: Sequence[Effect] = (),
        *,
        at: datetime | None = None,
        context: Context | None = None,
    ) -> bool:
        """Work out the windows again and fold them into the timer: the new windows are
        merged and followed at once, so that the timer does not rest, or is stored,
        between an edited window and the timer that follows it (S2). `effects` are those
        of a change that is made with them, and are carried out with them.

        With `at`, the windows are worked out for `at` and folded to it, and so is the
        refresh that follows a window that ended. `at` is the moment a command was given
        while Home Assistant is starting: what falls due after it comes after the
        command. Without `at` the clock is read twice, before and after the Workday
        sensor is asked, so that the timer is folded to the time the sensor answered.

        `context` is the cause of `effects`, as `_execute_fold` says: the switch that
        made them. The refresh that follows a window that ended has none.

        The caller holds the lock. Returns False, with the timer untouched but for
        what `effects` are of, when the timer was unloaded while the windows were worked
        out: its entry is being replaced, and the new timer would find this one's stale
        save. A window that is over by the time they are worked out, which asking the
        Workday sensor may take that long, is replaced like any other that a fold finds
        over.
        """
        windows, unknown = await self._async_windows(
            at if at is not None else dt_util.utcnow()
        )
        if self._stopped:
            return False
        now = at if at is not None else dt_util.utcnow()
        await self._fold_due(
            now,
            [*effects, *self._set_windows(now, windows, unknown)],
            refresh_at=at,
            context=context,
        )
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
            # which the observation does not do for a timer restored unchanged: a
            # restored timer arms nothing at set-up. Only a command given meanwhile
            # does, after it has worked the windows out and folded what was due.
            effects = self._set_windows(now, windows, unknown)
            self._schedule_refresh()
            before = self.snapshot
            self._set_target_deleted(not self._target_exists())
            state = self._hass.states.get(self.target_entity_id)
            effects += self._core.observe(now, actual_state(state), by_us=False)
            self._started = True  # reports are answered from here
            await self._execute_fold(before, now, effects)
            await self._async_check_interval_settings()

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
        # The report counts at the moment it arrived, not when it gets its turn behind a
        # slow call. Not `event.time_fired`: it can be earlier than a command that was
        # given before the report and is ahead of it in the queue.
        raised = dt_util.utcnow()
        async with self._lock:
            if self._stopped or not self._started:
                return  # `_handle_started` reads the state itself
            # What exists now counts, not only the event: a report that waited for the
            # lock may be one the target made before it was deleted. It is read as a
            # target that is gone, so the core sends it nothing.
            new_state = event.data["new_state"] if self._target_exists() else None
            if new_state is not None:
                self._set_target_deleted(False)
            before = self.snapshot
            by_us = event.context.id in self._own_contexts
            effects = self._core.observe(raised, actual_state(new_state), by_us=by_us)
            # The answer to one of our own calls is no person's doing, and all that its
            # fold announces came from time, so it has no context to give.
            await self._execute_fold(
                before, raised, effects, context=None if by_us else event.context
            )
            await self._async_check_interval_settings()

    def _target_exists(self) -> bool:
        """Whether the target is there: it has a registry entry or a state. Either is
        enough. A registered entity has no state until its integration has set up, and
        an entity of YAML without a unique id has no registry entry."""
        return (
            er.async_get(self._hass).async_get(self.target_entity_id) is not None
            or self._hass.states.get(self.target_entity_id) is not None
        )

    def _set_target_deleted(self, deleted: bool) -> None:
        """Note that the target is deleted, or back, and say so; it acts only on a
        change.

        A deleted target is an unavailable one for the core, which sends it nothing and
        keeps what it owes it (R10), so the timer needs no other change. The user is
        told by a repair, which deletes the timer, and by the log. When the target is
        back the repair goes away by itself.
        """
        if deleted == self._target_deleted:
            return
        self._target_deleted = deleted
        title = self._entry.title
        if deleted:
            async_raise_target_deleted(self._hass, self._entry, self.target_entity_id)
            _LOGGER.warning(
                "The entity %s of the timer %s was deleted;"
                " the timer switches nothing until it is back",
                self.target_entity_id,
                title,
            )
        else:
            async_clear(self._hass, TARGET_DELETED, self._entry.entry_id)
            _LOGGER.info(
                "The entity %s of the timer %s is back", self.target_entity_id, title
            )

    def _settings_verdict(self) -> dict[str, tuple[str, ...] | None]:
        """The settings of each interval that the target does not take now, by the id of
        the interval; None for an interval that cannot be judged now.

        The judgement is the one the settings are filtered by when they are sent
        (`_settings_the_target_takes`). There are none while the target is deleted,
        which its repair speaks for.

        An unavailable or unknown target may say nothing of what it takes, and sends
        wait for it. So its verdict stays as it was: the names of the warning of the
        interval, as far as the interval still holds them. An interval with no such
        warning cannot be judged until the target reports.
        """
        if not self._target_exists():
            return dict.fromkeys(self._intervals, ())
        if actual_state(self._hass.states.get(self.target_entity_id)) == "unavailable":
            return {
                interval.id: self._held(interval)
                for interval in self._intervals.values()
            }
        return {
            interval.id: settings_not_taken(
                self._hass, self.target_entity_id, interval.settings
            )
            for interval in self._intervals.values()
        }

    def _held(self, interval: Interval) -> tuple[str, ...] | None:
        """The names of the warning of `interval`, as far as it still has them as
        settings; None when it has no warning."""
        if (names := self._warned_with(interval.id)) is None:
            return None
        return tuple(name for name in names if name in interval.settings)

    def _warned_with(self, subentry_id: str) -> tuple[str, ...] | None:
        """The names of the settings that the warning of the interval was last raised
        with, by this load or an earlier one; None when there is none."""
        return self._settings_warned.get(
            subentry_id, self._settings_warned_before.get(subentry_id)
        )

    def _says(self, subentry_id: str, names: tuple[str, ...]) -> bool:
        """Whether the warning of the interval, or the lack of one, is already what
        `names` ask for, as this load made it. A warning of an earlier load is not: it
        may call the interval by an old title."""
        return (
            subentry_id not in self._settings_warned_before
            and self._settings_warned.get(subentry_id, ()) == names
        )

    async def _async_check_interval_settings(self) -> None:
        """Warn about each interval that turns the target on with settings it does not
        take, and take a warning away when the target takes them again.

        There is one warning per interval, which names all its settings by the labels
        of the interval form, in the language of the house; a name the form has no
        label for, which a hand edit of the stored interval can leave, stands for
        itself. It is changed only when its names or its interval do, so a report that
        changes nothing costs nothing. It is updated in place, which keeps an Ignore of
        the user, unless the interval gained a setting that the warning does not name:
        that one is raised as new, so that the Ignore does not hide it.
        """
        if self._settings_judged():
            return
        texts = await async_get_translations(
            self._hass, self._hass.config.language, "config_subentries", [DOMAIN]
        )
        if self._stopped:
            return
        # The target may have changed while the texts were read, so it is judged again:
        # nothing is awaited from here to the last warning.
        for subentry_id, names in self._settings_verdict().items():
            if names is None or self._says(subentry_id, names):
                continue
            raised_with = self._warned_with(subentry_id)
            self._settings_warned_before.pop(subentry_id, None)
            if not names:
                self._settings_warned.pop(subentry_id, None)
                async_clear_settings_not_taken(
                    self._hass, self._entry.entry_id, subentry_id
                )
                continue
            # An interval deleted since the timer loaded stays here until it reloads.
            if (subentry := self._entry.subentries.get(subentry_id)) is None:
                continue
            if raised_with is not None and not set(names) <= set(raised_with):
                async_clear_settings_not_taken(
                    self._hass, self._entry.entry_id, subentry_id
                )
            async_raise_settings_not_taken(
                self._hass,
                self._entry,
                subentry,
                names,
                ", ".join(
                    texts.get(f"{_SETTING_LABELS}.{name}", name) for name in names
                ),
            )
            self._settings_warned[subentry_id] = names

    def _settings_judged(self) -> bool:
        """Whether every warning, or lack of one, is as the target and the intervals
        ask for."""
        return all(
            names is None or self._says(subentry_id, names)
            for subentry_id, names in self._settings_verdict().items()
        )

    def _reconcile_settings_warnings(self) -> None:
        """Take the warnings of an earlier load into this one.

        A warning outlives the unload, so that an Ignore the user chose survives the
        reload that every change of an interval makes, and a restart of Home Assistant,
        which loads a persistent issue back whole. Home Assistant keeps the Ignore of
        an issue that is raised again, and forgets it when the issue is deleted. The
        warning of an interval that is gone is taken away now. The others are
        remembered, with the names they were raised with, and the first judgement of
        this load changes or takes them away.
        """
        for subentry_id, names in async_warned_settings(
            self._hass, self._entry.entry_id
        ).items():
            if subentry_id in self._intervals:
                self._settings_warned_before[subentry_id] = names
            else:
                async_clear_settings_not_taken(
                    self._hass, self._entry.entry_id, subentry_id
                )

    @callback
    def _release_settings_warnings(self) -> None:
        """Leave the warnings of the intervals in place as the timer is unloaded, for
        the load that follows a reload. A disabled timer is not loaded again, so its
        warnings go."""
        if self._entry.disabled_by is not None:
            async_clear_settings_warnings(self._hass, self._entry.entry_id)

    async def _handle_wakeup(self, _scheduled: datetime) -> None:
        # The alarm counts at the moment it went off, as a report does
        # (`_handle_state_change`).
        raised = dt_util.utcnow()
        async with self._lock:
            if self._stopped:
                return
            await self._fold_due(raised, [])

    async def _fold_due(
        self,
        now: datetime,
        effects: list[Effect],
        *,
        refresh_at: datetime | None = None,
        context: Context | None = None,
    ) -> None:
        """Carry out `effects`, which the caller has just made the core produce, and
        whatever falls due at `now` on top of them. Every event that folds what is due
        by a tick goes through here: the alarm, the refresh of the windows (also the
        catch-up of a change made while starting) and the switching off of an
        interval. `refresh_at` is the moment at which a window that the fold finds over
        is replaced (`_async_refresh_windows_locked`). `context` is the cause of
        `effects`, as `_execute_fold` says."""
        before = self.snapshot
        effects = effects + self._core.tick(now)
        await self._execute_fold(
            before, now, effects, refresh_at=refresh_at, context=context
        )

    async def _execute_fold(
        self,
        before: Snapshot,
        now: datetime,
        effects: list[Effect],
        *,
        refresh_at: datetime | None = None,
        context: Context | None = None,
    ) -> None:
        """Carry out the effects of a fold of what fell due at `now`, which `tick` and
        `observe` make, and say what came due while the target is away. Every fold
        goes through here: a tick, the first observation of the target at start-up,
        each later report of it and the pending commands that a command folds before it
        acts (`_command`, with no context). The snapshot before the fold is `before`.

        `context` is the cause of the fold, None where time is: the alarm, a refresh
        of the windows and the catch-up at start-up. A report of the target gives the
        context of the change that made it, unless that is the answer to one of our own
        calls, which is no person's doing and gives none. The switch of an interval
        gives its own. The events of the fold carry it, except those that time caused
        (`_announce`). It goes to this fold only, not to the refresh that follows a
        window that ended: that is time's doing.

        It is imprecise in one known way: a report of a change by hand, or a switch,
        whose fold also starts a window or a pending command that fell due gives that
        start its own context, though the person did not cause it.

        A window the fold found over is replaced by the next one of its interval. That
        goes for whichever event folds it: a report of the target may get the lock
        before the alarm of the end does, and the alarm then finds nothing due. It goes
        for the fold of a refresh too, since asking the Workday sensor may take until a
        window that was just worked out is over. That refresh is made at `refresh_at`,
        or at the time it gets its turn when there is none.
        """
        ended = {w.interval_id for w in before.windows} - {
            w.interval_id for w in self.snapshot.windows
        }
        self._log_due_while_unavailable(before, now, effects)
        await self._execute(effects, context)
        if ended and not self._stopped:
            await self._async_refresh_windows_locked(at=refresh_at)

    def _log_due_while_unavailable(
        self, before: Snapshot, now: datetime, effects: list[Effect]
    ) -> None:
        """Say what came due while the target is away, worded by what it was: nothing
        else shows that a switch waits for the target to come back (R10).

        Only a target that reports "unavailable" is away. One that has not been seen
        (`last_actual is None`, until start-up observes it) is not known to be, so a
        fold before start-up says nothing; start-up says what it folds itself.
        """
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
        # A countdown that ended, or a limit that was reached, is one that wants the
        # target off; a command that was due with it may have moved the end or made the
        # target wanted on instead.
        for before_at, after_at, message in (
            (
                before.end,
                after.end,
                "The timer of %s ended while it is unavailable;"
                " it is turned off when it is back",
            ),
            (
                before.limit_at,
                after.limit_at,
                "The limit of %s was reached while it is unavailable;"
                " it is turned off when it is back",
            ),
        ):
            if (
                before_at is not None
                and before_at <= now
                and after_at is None
                and after.pending == "off"
            ):
                _LOGGER.info(message, self.target_entity_id)
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

    async def _execute(self, effects: list[Effect], context: Context | None) -> None:
        """Save the timer, tell what happened and carry out `effects`. The events carry
        `context`, the cause of the batch (`_announce`); None where time is."""
        self._forget_settled_failure()
        if any(isinstance(effect, Changed) for effect in effects):
            # Saved ahead of the effects: a service call may take up to
            # SERVICE_CALL_TIMEOUT, and a restart meanwhile must find the new timer.
            await self._store.async_save(self.snapshot)
            if not self._stopped:
                # Shown at once too: the entities must not wait for a slow device.
                self._refresh_entities()
        # Told once the timer is saved and shown, and before the target is called: an
        # automation sees the new Ends at, and a slow device does not delay it.
        announcements = self._core.take_announcements()
        if not self._stopped:
            self._announce(announcements, context)
        for effect in effects:
            if self._stopped:
                return  # Unloaded while an earlier effect was under way.
            match effect:
                case TurnOn(settings):
                    # Settings that were all left out count as delivered: the turn-on
                    # is all there is to send, and nothing stays owed.
                    await self._carry_out(
                        "on",
                        self._behaviour.turn_on_calls(
                            self._settings_the_target_takes(settings)
                        ),
                        with_settings=bool(settings),
                    )
                case ApplySettings(settings):
                    await self._carry_out(
                        "settings",
                        self._behaviour.apply_calls(
                            self._settings_the_target_takes(settings)
                        ),
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

    def _announce(
        self, announcements: Sequence[Announcement], context: Context | None
    ) -> None:
        """Fire what the core announced as events, in the order it happened. Each names
        the timer by its Run for as it is called now, so a renamed one is named by its
        new id.

        An event carries `context` itself, not a child of it: the cause of the batch,
        that of a call, a button, a sentence, a switch or a device switched by hand.
        What time caused has a context of its own, with no user and no parent, whatever
        the batch: a countdown that ran out or a limit that came (`expired` and
        `limit`), and a pending command that came due. A call that finds the end
        passed announces the run out and its own start in one batch, and only the start
        is its doing."""
        if not announcements:
            return
        run_for = er.async_get(self._hass).async_get_entity_id(
            Platform.NUMBER, DOMAIN, timer_unique_id(self._entry.entry_id, KEY_RUN_FOR)
        )
        if run_for is None:
            _LOGGER.warning(
                "Not announcing what happened to the timer of %s: its Run for is not in"
                " the entity registry, so the events cannot name the timer",
                self.target_entity_id,
            )
            return
        for announcement in announcements:
            match announcement:
                case CountdownStarted(end, limit):
                    self._hass.bus.async_fire(
                        EVENT_COUNTDOWN_STARTED,
                        {
                            "entity_id": run_for,
                            "ends_at": _ends_at(end),
                            "limit": limit,
                        },
                        context=context,
                    )
                case CountdownEnded(reason):
                    self._hass.bus.async_fire(
                        EVENT_COUNTDOWN_ENDED,
                        {"entity_id": run_for, "reason": reason},
                        context=None if reason in ("expired", "limit") else context,
                    )
                case CommandCameDue(command):
                    self._hass.bus.async_fire(
                        EVENT_COMMAND_DUE,
                        {
                            "entity_id": run_for,
                            "command_id": command.id,
                            "action": command.action,
                        },
                    )
                case _:
                    assert_never(announcement)

    def _settings_the_target_takes(self, settings: Settings) -> Settings:
        """The part of `settings` that the target can be turned on with now.

        They were checked when the command was made or the interval was saved, and
        what the target takes can change after that: an update of its integration
        renames a mode, or the device is replaced. A setting it no longer takes would
        fail its call, and nothing would be turned on. So it is judged when it is sent,
        whoever owes it: a run, a pending command, a window or settings carried over.
        Each setting is judged alone, as the form offers them, by `settings_not_taken`,
        which the warnings of the intervals go by too. One that is left out is said
        once, for as long as it is.
        """
        not_taken = settings_not_taken(self._hass, self.target_entity_id, settings)
        taken: dict[str, SettingValue] = {}
        for name, value in settings.items():
            if name in not_taken:
                if (name, value) not in self._left_out:
                    self._left_out.add((name, value))
                    _LOGGER.warning(
                        "%s cannot take the setting %s=%s now; it is left out",
                        self.target_entity_id,
                        name,
                        value,
                    )
                continue
            taken[name] = value
            self._left_out -= {pair for pair in self._left_out if pair[0] == name}
        return freeze_settings(taken)

    def _refresh_entities(self) -> None:
        self._schedule_refresh()
        # The entities show the end of the countdown and when it began, the limit, the
        # pending commands and which intervals are switched off; the rest of the
        # snapshot is bookkeeping that needs no state write.
        if (
            self.snapshot.end != self._notified_end
            or self.snapshot.started_at != self._notified_started_at
            or self.snapshot.limit_at != self._notified_limit_at
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
            await self._execute(self._core.settings_applied(dt_util.utcnow()), None)

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
        await self._execute(self._core.call_failed(dt_util.utcnow()), None)

    def _arm(self, at: datetime) -> None:
        """Wake up at `at` to carry out what is due, replacing any earlier alarm."""
        if self._stopped:
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
        self._notified_limit_at = self.snapshot.limit_at
        self._notified_commands = self.snapshot.commands
        self._notified_disabled = self.snapshot.disabled_intervals
        for listener in list(self._listeners):
            listener()
