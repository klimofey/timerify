"""Timerify: countdowns, auto-off and schedules attached to existing entities."""

from typing import Final

from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device import async_entity_id_to_device_id
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.helper_integration import async_handle_source_entity_changes
from homeassistant.helpers.typing import ConfigType

from .const import CONF_TARGET, DOMAIN, SIGNAL_TIMERS_CHANGED
from .controller import TargetController, TimerifyConfigEntry
from .services import async_setup_services
from .store import TimerStore
from .voice import async_register_intents
from .voice.files import (
    VoiceConfigEntry,
    async_remove_voice_entry,
    async_setup_voice_entry,
    async_unload_voice_entry,
    is_voice_entry,
)
from .websocket import async_register_websocket_commands

PLATFORMS: Final = (Platform.NUMBER, Platform.SENSOR, Platform.SWITCH)

CONFIG_SCHEMA: Final = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services, the intent handlers and the websocket commands, which
    belong to the integration, not to a timer."""
    async_setup_services(hass)
    async_register_intents(hass)
    async_register_websocket_commands(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: TimerifyConfigEntry | VoiceConfigEntry
) -> bool:
    """Set up the timer of one target and its entities, or the voice settings, which
    have no target and no entities."""
    if is_voice_entry(entry):
        return await async_setup_voice_entry(hass, entry)
    store = TimerStore(hass, entry.entry_id)
    controller = TargetController(hass, entry, store, await store.async_load())
    entry.runtime_data = controller
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    entry.async_on_unload(_follow_target(hass, entry))
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
    """Delete the stored timer of a removed entry, or the sentence files of the voice
    settings."""
    if is_voice_entry(entry):
        await async_remove_voice_entry(hass, entry)
        return
    await TimerStore(hass, entry.entry_id).async_remove()


def _follow_target(hass: HomeAssistant, entry: TimerifyConfigEntry) -> CALLBACK_TYPE:
    """Keep the entry in step with its target in the entity registry.

    A renamed target is followed by updating the `target` option, which reloads the
    entry through its update listener; a target that moves to another device, or off
    its device, takes the entities along; the entities of a removed target are left
    on no device.
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
    )
