"""Home Assistant glue around the timer core: events go in, effects are carried out.

The core decides; this module owns everything that touches Home Assistant. Commands,
target state changes and alarms all run under one lock, so the core sees them strictly
one after another and an effect is finished before the next event is looked at.
"""

import asyncio
import logging
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta
from functools import cached_property
from typing import Any, Literal, assert_never

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DEFAULT_DURATION,
    CONF_MODE,
    CONF_TARGET,
    DEFAULT_DURATION_MINUTES,
    DOMAIN,
    SERVICE_CALL_TIMEOUT,
)
from .core import (
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
from .domains import TargetCall, actual_state, behaviour_for, validate_settings
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


class TargetController:
    """Runs the timer of one target entity."""

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
            timedelta(
                minutes=options.get(CONF_DEFAULT_DURATION, DEFAULT_DURATION_MINUTES)
            ),
            snapshot,
            automatic_resends=self._behaviour.automatic_resends,
        )
        self._lock = asyncio.Lock()
        self._stopped = False
        self._own_contexts = deque[str](maxlen=_REMEMBERED_CONTEXTS)
        self._listeners: list[Callable[[], None]] = []
        self._notified_end = snapshot.end
        self._expiry_alarm: CALLBACK_TYPE | None = None
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
        """Count down `minutes` from now; zero stops the timer."""
        await self._command(
            lambda now: self._core.set_duration(now, timedelta(minutes=minutes))
        )

    async def async_add_minutes(self, minutes: int) -> None:
        """Move the end of the countdown by `minutes`, which may be negative."""
        await self._command(lambda now: self._core.add(now, timedelta(minutes=minutes)))

    async def async_run(
        self, minutes: int | None = None, settings: Mapping[str, Any] | None = None
    ) -> None:
        """Switch the target on for `minutes`, or without a duration (the default one
        in strict mode), with `settings` if there are any.

        Raises ServiceValidationError, before anything runs, for settings that the
        target cannot take.
        """
        owed = validate_settings(self._hass, self.target_entity_id, settings or {})
        if minutes is None:
            await self._command(lambda now: self._core.run_open(now, owed))
        else:
            duration = timedelta(minutes=minutes)
            await self._command(
                lambda now: self._core.set_duration(now, duration, owed)
            )

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Call `listener` whenever what the entities show may have changed."""
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            self._listeners.remove(listener)

        return remove

    async def _command(self, command: Callable[[datetime], list[Effect]]) -> None:
        async with self._lock:
            if self._stopped:
                return
            await self._execute(command(dt_util.utcnow()))

    async def _handle_started(self, _hass: HomeAssistant) -> None:
        """Take stock of the target once, with Home Assistant fully started."""
        async with self._lock:
            if self._stopped:
                return
            # A timer restored unchanged gets no Arm from the core. Arming only now
            # keeps a stored end that has long passed from switching a target that
            # has not been seen yet; the first observation expires it instead.
            if (end := self.snapshot.end) is not None:
                self._arm(end)
            self._schedule_refresh()
            state = self._hass.states.get(self.target_entity_id)
            await self._execute(
                self._core.observe(dt_util.utcnow(), actual_state(state), by_us=False)
            )

    async def _handle_state_change(self, event: Event[EventStateChangedData]) -> None:
        async with self._lock:
            if self._stopped:
                return
            await self._execute(
                self._core.observe(
                    dt_util.utcnow(),
                    actual_state(event.data["new_state"]),
                    by_us=event.context.id in self._own_contexts,
                )
            )

    async def _handle_expiry(self, _scheduled: datetime) -> None:
        async with self._lock:
            if self._stopped:
                return
            effects = self._core.expire(dt_util.utcnow())
            if effects and self.snapshot.last_actual == "unavailable":
                _LOGGER.info(
                    "The timer ended but %s is unavailable;"
                    " it will be turned off when it is back",
                    self.target_entity_id,
                )
            await self._execute(effects)

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
                case _:
                    assert_never(effect)

    def _refresh_entities(self) -> None:
        self._schedule_refresh()
        # The entities show the end of the countdown; the rest of the snapshot is
        # bookkeeping that needs no state write.
        if self.snapshot.end != self._notified_end:
            self._notify()

    def _log_gave_up(self, what: Label) -> None:
        attempts = self._behaviour.automatic_resends + 1
        noun = "attempt" if attempts == 1 else "attempts"
        if what == "settings":
            _LOGGER.warning(
                "%s did not take its settings after %d %s; Timerify will try"
                " again when it reports a change or on the next command",
                self.target_entity_id,
                attempts,
                noun,
            )
        else:
            _LOGGER.warning(
                "%s did not turn %s after %d %s; Timerify will try"
                " again when it reports a change or on the next command",
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
        """Wake up at `at` to expire the timer, replacing any earlier alarm."""
        if self._stopped:
            return
        self._disarm()
        self._expiry_alarm = async_track_point_in_utc_time(
            self._hass, self._handle_expiry, at
        )

    def _disarm(self) -> None:
        """Cancel the expiry alarm; there may be none."""
        if self._expiry_alarm is not None:
            self._expiry_alarm()
            self._expiry_alarm = None

    def _schedule_refresh(self) -> None:
        """Wake up when the rounded-up remaining minutes next change."""
        self._cancel_refresh()
        end = self.snapshot.end
        if self._stopped or end is None:
            return
        remaining = remaining_minutes(self.snapshot, dt_util.utcnow())
        if remaining <= 1:
            return  # The expiry alarm comes at the end, and its change notifies.
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
        for listener in list(self._listeners):
            listener()
