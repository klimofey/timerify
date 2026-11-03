"""Timerify: countdowns, auto-off and schedules attached to existing entities."""

from typing import Final

from homeassistant.config_entries import ConfigEntry
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
from .const import (
    CONF_GENERATED_TITLE,
    CONF_TARGET,
    CONF_WORKDAY_SENSOR,
    DOMAIN,
    SIGNAL_TIMERS_CHANGED,
    SUBENTRY_INTERVAL,
    TRANSLATION_LANGUAGES,
)
from .controller import TargetController, TimerifyConfigEntry
from .entity import remove_fallback_device
from .issues import (
    STORED_TIMER_INVALID,
    TARGET_DELETED,
    async_clear,
    async_clear_settings_warnings,
    async_raise_stored_timer_invalid,
)
from .runtime import RuntimeStore
from .schedule import async_title_labels, stored_interval_title
from .services import async_setup_services
from .store import StoredTimerInvalid, TimerStore
from .target import shares_its_device, timers_by_device
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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Bring an entry that an earlier release made to the current minor version.

    Minor version 2 marks the titles Timerify gave the intervals
    (`CONF_GENERATED_TITLE`), so that an edit names them again in the language of the
    house. A title that equals the one made in any shipped language is marked,
    whichever language the house was set to when the interval was made; any other is
    the user's, and so is the title of an interval whose data no title can be made of.
    The voice settings have no intervals and only move to the version.

    Release 1.0.0 has no migration, so it loads an entry of this version and ignores
    the mark, and its own rule for the title applies again.
    """
    if entry.minor_version < 2:
        labels_by_language = [
            await async_title_labels(hass, language)
            for language in TRANSLATION_LANGUAGES
        ]
        for subentry in entry.get_subentries_of_type(SUBENTRY_INTERVAL):
            if subentry.title in {
                stored_interval_title(subentry.data, labels)
                for labels in labels_by_language
            }:
                hass.config_entries.async_update_subentry(
                    entry,
                    subentry,
                    data={**subentry.data, CONF_GENERATED_TITLE: subentry.title},
                )
        hass.config_entries.async_update_entry(entry, minor_version=2)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: TimerifyConfigEntry | VoiceConfigEntry
) -> bool:
    """Set up the timer of one target and its entities, or the voice settings, which
    have no target and no entities."""
    if is_voice_entry(entry):
        return await async_setup_voice_entry(hass, entry)
    try:
        return await _async_setup_timer(hass, entry)
    except Exception:
        # A timer that does not load turns nothing on, so it has nothing to warn about.
        # The warnings outlive an unload (see `TargetController.async_start`); a timer
        # that loads again raises them again.
        async_clear_settings_warnings(hass, entry.entry_id)
        raise
    finally:
        # Also after a failure: a timer that does not load still holds its place on the
        # device, so its siblings are named for it.
        _async_reload_timers_named_otherwise(hass, entry.entry_id)


async def _async_setup_timer(hass: HomeAssistant, entry: TimerifyConfigEntry) -> bool:
    """Set up the timer of one target and its entities."""
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


@callback
def _async_reload_timers_named_otherwise(
    hass: HomeAssistant, entry_id: str, *, removed: bool = False
) -> None:
    """Reload each loaded timer whose entities are named otherwise than the count of
    timers on its device now says.

    A timer on a device that holds more than one timer names its target in its entity
    names, and one that is alone does not. The names are made when the entities are, so
    a timer that joins a device or leaves it changes what its siblings should be called,
    and only a reload makes them again. This runs once the timer `entry_id` is set up,
    whether or not it loaded, and once it is removed (`removed`), when it no longer
    counts.

    It reloads each timer once, and only the ones that differ: a scheduled reload does
    not merge with another, so a reload from each entity would run the timer as many
    times as it has entities, and the third timer on a device, or the second after the
    third is removed, changes no name and reloads nobody. It looks at every loaded
    timer, not only those on the device of `entry_id`, since a target that moves from
    one device to another leaves the timers of both with a new count. The settings of
    the voice have no target and are never reloaded here.
    """
    timers = timers_by_device(hass, removed=entry_id if removed else None)
    for other in hass.config_entries.async_loaded_entries(DOMAIN):
        if other.entry_id == entry_id or is_voice_entry(other):
            continue
        controller = other.runtime_data
        if (controller.target_label is not None) != shares_its_device(
            hass, controller.target_entity_id, timers
        ):
            hass.config_entries.async_schedule_reload(other.entry_id)


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
    repairs and the warnings of its intervals away, or delete the sentence files of the
    voice settings."""
    if is_voice_entry(entry):
        await async_remove_voice_entry(hass, entry)
        return
    async_clear(hass, TARGET_DELETED, entry.entry_id)
    async_clear(hass, STORED_TIMER_INVALID, entry.entry_id)
    async_clear_settings_warnings(hass, entry.entry_id)
    await TimerStore(hass, entry.entry_id).async_remove()
    await RuntimeStore(hass, entry.entry_id).async_remove()
    _async_reload_timers_named_otherwise(hass, entry.entry_id, removed=True)


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
