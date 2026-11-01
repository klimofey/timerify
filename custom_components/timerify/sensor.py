"""The sensors of a timer: when the countdown ends, the next pending command and, for a
timer that counts it, how long the target was on."""

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, UnitOfTime
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_utc_time_change,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_RUNTIME,
    DOMAIN,
    KEY_ENDS_AT,
    KEY_NEXT_COMMAND,
    KEY_RUNTIME,
    RUNTIME_TICK_SECOND,
    timer_unique_id,
)
from .controller import TimerifyConfigEntry
from .core import Command, Snapshot
from .domains import actual_state
from .entity import TimerifyEntity
from .runtime import RuntimeCounter, RuntimeStore
from .store import command_to_json

PARALLEL_UPDATES = 0
"""The sensor only reads the controller."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TimerifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the "Ends at" and "Next command" sensors of a target, and its "Runtime"
    sensor if the timer counts the runtime; if it does not, take the entry of a sensor
    it counted with before out of the registry.

    The runtime file is read here, after the other sensors are added: a file of a newer
    release raises, which fails this platform's setup where it is logged, and leaves the
    timer's other sensors as they are.
    """
    async_add_entities([EndsAtSensor(hass, entry), NextCommandSensor(hass, entry)])
    if entry.options.get(CONF_RUNTIME):
        store = RuntimeStore(hass, entry.entry_id)
        seconds = await store.async_load()
        async_add_entities([RuntimeSensor(hass, entry, store, seconds)])
    else:
        _remove_runtime_entry(hass, entry)


def _remove_runtime_entry(hass: HomeAssistant, entry: TimerifyConfigEntry) -> None:
    """Remove the registry entry of the Runtime sensor of a timer that stopped counting.

    Nothing else removes it: left there, it would come back at every start as an
    unavailable entity. Counting again brings it back as it was, with its entity id and
    its history, because the registry keeps a removed entry's identity.
    """
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, timer_unique_id(entry.entry_id, KEY_RUNTIME)
    )
    if entity_id is not None:
        registry.async_remove(entity_id)


class EndsAtSensor(TimerifyEntity, SensorEntity):
    """The moment the countdown ends; unknown while no countdown runs.

    The attribute `started_at` is when that countdown began, for the card to show how
    much of it is left; it is None while the state is unknown, and for a countdown
    that was stored before the attribute existed.

    The frontend counts down to it by itself, so the sensor is written only when
    the end or the beginning moves, not as the minutes pass.
    """

    entity_description = SensorEntityDescription(
        key=KEY_ENDS_AT,
        translation_key="ends_at",
        device_class=SensorDeviceClass.TIMESTAMP,
    )

    _shown: tuple[datetime | None, datetime | None] = (None, None)
    """The end and the beginning the state was last written with."""

    async def async_added_to_hass(self) -> None:
        """Show the countdown as it is now, then follow it."""
        self._show(self._controller.snapshot)
        await super().async_added_to_hass()

    def _show(self, snapshot: Snapshot) -> None:
        self._shown = (snapshot.end, snapshot.started_at)
        self._attr_native_value = snapshot.end
        self._attr_extra_state_attributes = {"started_at": snapshot.started_at}

    @callback
    def _handle_controller_update(self) -> None:
        snapshot = self._controller.snapshot
        if (snapshot.end, snapshot.started_at) != self._shown:
            self._show(snapshot)
            self.async_write_ha_state()


class NextCommandSensor(TimerifyEntity, SensorEntity):
    """When the next pending command is due; unknown while there is none.

    The attribute `commands` lists every pending command, for the card and for voice.
    The list is not worth keeping in the history (it is stored again with every
    change), so the recorder leaves it out. The sensor is written only when the
    commands change.
    """

    entity_description = SensorEntityDescription(
        key=KEY_NEXT_COMMAND,
        translation_key="next_command",
        device_class=SensorDeviceClass.TIMESTAMP,
    )
    _unrecorded_attributes = frozenset({"commands"})

    _shown: tuple[Command, ...] = ()
    """The commands the state was last written with."""

    async def async_added_to_hass(self) -> None:
        """Show the commands as they are now, then follow them."""
        self._show(self._controller.snapshot.commands)
        await super().async_added_to_hass()

    def _show(self, commands: tuple[Command, ...]) -> None:
        self._shown = commands
        self._attr_native_value = commands[0].at if commands else None
        self._attr_extra_state_attributes = {
            "commands": [command_to_json(command) for command in commands]
        }

    @callback
    def _handle_controller_update(self) -> None:
        if (commands := self._controller.snapshot.commands) != self._shown:
            self._show(commands)
            self.async_write_ha_state()


class RuntimeSensor(TimerifyEntity, SensorEntity):
    """How long the target was on, in minutes: a total that only goes up.

    It counts every "on" of the target as `actual_state` judges it, whoever caused it,
    and it follows the target's state itself, not the controller: the timer decides
    what the target should do, and the counter records what it did. A change is dated
    by the moment it was made, not by the moment it is looked at. Time that nobody saw
    is not counted: Home Assistant not running, and a target that is unavailable or
    unknown.

    The state is written once a minute at most, at second `RUNTIME_TICK_SECOND`, and
    only when the figure moved; never at a change of the target or a notice of the
    controller. The total is saved to its file before the figure that shows it is
    published, so a restart or a crash can never bring the figure back down, which the
    statistics would take for a counter that was reset. The seconds since the last tick
    are saved when the sensor is removed and when Home Assistant stops, which removes
    no entity. The sensor does not turn unavailable when its target does: it is a
    total, which cards and automations read.
    """

    entity_description = SensorEntityDescription(
        key=KEY_RUNTIME,
        translation_key="runtime",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
    )

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TimerifyConfigEntry,
        store: RuntimeStore,
        seconds: float,
    ) -> None:
        """`seconds` is what the file held: the counter goes on from it."""
        super().__init__(hass, entry)
        self._target = self._controller.target_entity_id
        self._store = store
        self._counter = RuntimeCounter(seconds)

    async def async_added_to_hass(self) -> None:
        """Show the total as it is now, then count until the sensor is removed.

        The file is saved before the state is written, as at every tick. It matters
        when Home Assistant adds the same object again, as it does for a new entity id:
        the figure shown now can be a hundredth above what the removal saved, and a
        crash before the next tick would bring the total back down.
        """
        await super().async_added_to_hass()
        now = dt_util.utcnow()
        self._counter.observe(
            now, actual_state(self.hass.states.get(self._target)) == "on"
        )
        self._attr_native_value = self._counter.minutes(now)
        self._counter.mark_shown(self._attr_native_value)
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._target, self._handle_target_change
            )
        )
        self.async_on_remove(
            async_track_utc_time_change(
                self.hass, self._async_tick, second=RUNTIME_TICK_SECOND
            )
        )
        # Not `async_listen_once`: its listener removes itself when it fires, and
        # removing it again, as the sensor's removal after a stop would, logs an error.
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self._async_flush)
        )
        # Last, so that no change of the target falls between the first look at it and
        # the subscription to it.
        await self._store.async_save(self._counter.seconds_to_store(now))

    async def async_will_remove_from_hass(self) -> None:
        """Save the total as of now: an unload for any change of the timer, or its
        removal, must not lose the seconds counted since the last tick."""
        await self._async_flush()

    async def _async_flush(self, _stop: Event | None = None) -> None:
        """Save the total as of now, which is also what the stop of Home Assistant asks
        for: it unloads no entry, so nothing else would save the seconds since the last
        tick. While it is stopping, the store keeps the data for the final write."""
        await self._store.async_save(self._counter.seconds_to_store(dt_util.utcnow()))

    @callback
    def _handle_target_change(self, event: Event[EventStateChangedData]) -> None:
        self._counter.observe(
            event.time_fired, actual_state(event.data["new_state"]) == "on"
        )

    async def _async_tick(self, _fired: datetime) -> None:
        """Publish the total if its minutes moved since the last time, after the file
        holds it."""
        now = dt_util.utcnow()
        minutes = self._counter.minutes(now)
        if minutes == self._counter.shown:
            return
        await self._store.async_save(self._counter.seconds_to_store(now))
        self._attr_native_value = minutes
        self.async_write_ha_state()
        self._counter.mark_shown(minutes)

    @callback
    def _handle_controller_update(self) -> None:
        """The counter follows the target and its own tick, not the timer."""
