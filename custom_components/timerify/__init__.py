"""Timerify: countdowns, auto-off and schedules attached to existing entities."""

from typing import Final

from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device import async_entity_id_to_device_id
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_registry import EventEntityRegistryUpdatedData
from homeassistant.helpers.event import async_track_entity_registry_updated_event
from homeassistant.helpers.helper_integration import async_handle_source_entity_changes
from homeassistant.helpers.typing import ConfigType

from .card import async_register_card
from .const import CONF_TARGET, CONF_WORKDAY_SENSOR, DOMAIN, SIGNAL_TIMERS_CHANGED
from .controller import TargetController, TimerifyConfigEntry
from .entity import remove_fallback_device
from .issues import (
    STORED_TIMER_INVALID,
    TARGET_DELETED,
    async_clear,
    async_raise_stored_timer_invalid,
)
from .runtime import RuntimeStore
from .services import async_setup_services
from .store import StoredTimerInvalid, TimerStore
from .voice import async_register_intents
from .voice.files import (
    VoiceConfigEntry,
    async_remove_voice_entry,
    async_setup_voice_entry,
    async_unload_voice_entry,
    is_voice_entry,
)
from .websocket import async_register_websocket_commands

PLATFORMS: Final = (
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
)

CONFIG_SCHEMA: Final = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services, the intent handlers, the websocket commands and the
    dashboard card, which belong to the integration, not to a timer."""
    async_setup_services(hass)
    async_register_intents(hass)
    async_register_websocket_commands(hass)
    await async_register_card(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: TimerifyConfigEntry | VoiceConfigEntry
) -> bool:
    """Set up the timer of one target and its entities, or the voice settings, which
    have no target and no entities."""
    if is_voice_entry(entry):
        return await async_setup_voice_entry(hass, entry)
    store = TimerStore(hass, entry.entry_id)
    try:
        snapshot = await store.async_load()
    except StoredTimerInvalid as err:
        # The set-up fails with the reason; the repair offers to reset the file.
        async_raise_stored_timer_invalid(hass, entry, err.reason)
        raise
    async_clear(hass, STORED_TIMER_INVALID, entry.entry_id)
    controller = TargetController(hass, entry, store, snapshot)
    entry.runtime_data = controller
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    entry.async_on_unload(_follow_target(hass, entry))
    _follow_target_restored(hass, entry)
    _follow_target_gaining_a_device(hass, entry)
    remove_fallback_device(hass, entry)
    if CONF_WORKDAY_SENSOR in entry.options:
        _follow_workday_sensor_rename(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await controller.async_start()
    async_dispatcher_send(hass, SIGNAL_TIMERS_CHANGED)
    return True


async def _async_entry_updated(hass: HomeAssistant, entry: TimerifyConfigEntry) -> None:
    """Reload the timer whenever its entry changes, its options or its intervals (which
    are subentries) alike, so that everything is read again from the entry."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: TimerifyConfigEntry | VoiceConfigEntry
) -> bool:
    """Unload the entities of a target; the controller's alarms go with the entry."""
    if is_voice_entry(entry):
        return await async_unload_voice_entry(hass, entry)
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        async_dispatcher_send(hass, SIGNAL_TIMERS_CHANGED)
    return unloaded


async def async_remove_entry(
    hass: HomeAssistant, entry: TimerifyConfigEntry | VoiceConfigEntry
) -> None:
    """Delete the stored timer and the stored runtime total of a removed entry, take its
    repairs away, or delete the sentence files of the voice settings."""
    if is_voice_entry(entry):
        await async_remove_voice_entry(hass, entry)
        return
    async_clear(hass, TARGET_DELETED, entry.entry_id)
    async_clear(hass, STORED_TIMER_INVALID, entry.entry_id)
    await TimerStore(hass, entry.entry_id).async_remove()
    await RuntimeStore(hass, entry.entry_id).async_remove()


def _follow_target(hass: HomeAssistant, entry: TimerifyConfigEntry) -> CALLBACK_TYPE:
    """Keep the entry in step with its target in the entity registry.

    A renamed target is followed by updating the `target` option, which reloads the
    entry through its update listener; a target that moves to another device, or off
    its device, takes the entities along. A removed target is told to the controller
    (`async_target_removed`), which raises the repair; the entities stay where they are,
    and Home Assistant leaves them on no device only if it is the device that is
    removed. A target that is on no device and gets one is left to
    `_follow_target_gaining_a_device`, since the helper does nothing for it, and one
    that is registered again after it was removed to `_follow_target_restored`.
    """

    def set_target(entity_id: str) -> None:
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_TARGET: entity_id}
        )

    return async_handle_source_entity_changes(
        hass,
        helper_config_entry_id=entry.entry_id,
        set_source_entity_id_or_uuid=set_target,
        source_device_id=async_entity_id_to_device_id(hass, entry.options[CONF_TARGET]),
        source_entity_id_or_uuid=entry.options[CONF_TARGET],
        source_entity_removed=entry.runtime_data.async_target_removed,
    )


def _follow_target_restored(hass: HomeAssistant, entry: TimerifyConfigEntry) -> None:
    """Reload the entry when its target is registered, which is when the user adds the
    device again after the target was deleted.

    The reload sets the timer up again: its entities go back on the target's device,
    which they have left if the device itself was removed, and start-up ends the repair
    of the deleted target. The state that the restored entity writes ends the repair
    too (`TargetController._handle_state_change`), so the timer works as soon as it
    reports; the reload follows. A target that never had a registry entry gets one,
    when its integration gives the entity a unique id, and is reloaded the same way,
    once.
    """

    @callback
    def reload_when_registered(event: Event[EventEntityRegistryUpdatedData]) -> None:
        if event.data["action"] == "create":
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        async_track_entity_registry_updated_event(
            hass, entry.runtime_data.target_entity_id, reload_when_registered
        )
    )


def _follow_target_gaining_a_device(
    hass: HomeAssistant, entry: TimerifyConfigEntry
) -> None:
    """Reload the entry when a target that is on no device gets one.

    `async_handle_source_entity_changes`, which `_follow_target` uses, follows a target
    only from the device it is on, so one that gets its first device while Home
    Assistant runs would leave the timer's entities on the device made for them until
    the next start. That happens when the user picks a device in the settings of a
    helper, and at start-up when the target's integration links its entity after
    Timerify has set up; an entity that is registered with a device after that counts
    as well. The reload sets the timer up again, which moves the entities to the
    target's device and removes the made one (`remove_fallback_device`); they are not
    moved from here, since the loaded ones would keep the device they were added with.

    A rename, which carries the old entity id, is left to the reload that updating the
    `target` option brings: scheduled reloads do not merge, each one runs. A target that
    is on a device needs nothing, as the helper reloads for a move. The registration of
    a target is left to `_follow_target_restored`, which reloads for every one, so only
    a change of the registry entry is followed here.
    """
    target = entry.runtime_data.target_entity_id
    if async_entity_id_to_device_id(hass, target) is not None:
        return

    @callback
    def reload_when_on_a_device(
        event: Event[EventEntityRegistryUpdatedData],
    ) -> None:
        data = event.data
        if data["action"] != "update" or "old_entity_id" in data:
            return
        registered = er.async_get(hass).async_get(data["entity_id"])
        if registered is not None and registered.device_id is not None:
            hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        async_track_entity_registry_updated_event(hass, target, reload_when_on_a_device)
    )


def _follow_workday_sensor_rename(
    hass: HomeAssistant, entry: TimerifyConfigEntry
) -> None:
    """Keep the `workday_sensor` option in step with the sensor's entity id.

    A renamed sensor is followed by updating the option, which reloads the entry
    through its update listener, so that the controller asks about the new id and
    listens to it. A removed sensor changes nothing: the option keeps its id and the
    schedule waits, as it does for a sensor that is away, until the user picks another
    one in the options. `async_handle_source_entity_changes` is not used, since it also
    moves the entities between devices, and those follow the target's device, not the
    sensor's.
    """

    @callback
    def set_sensor(event: Event[EventEntityRegistryUpdatedData]) -> None:
        data = event.data
        if data["action"] != "update" or "entity_id" not in data["changes"]:
            return
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_WORKDAY_SENSOR: data["entity_id"]}
        )

    entry.async_on_unload(
        async_track_entity_registry_updated_event(
            hass, entry.options[CONF_WORKDAY_SENSOR], set_sensor
        )
    )
