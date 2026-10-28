"""Timerify: countdowns, auto-off and schedules attached to existing entities."""

from typing import Final

from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.device import async_entity_id_to_device_id
from homeassistant.helpers.helper_integration import async_handle_source_entity_changes

from .const import CONF_TARGET
from .controller import TargetController, TimerifyConfigEntry
from .store import TimerStore

PLATFORMS: Final = (Platform.NUMBER, Platform.SENSOR)


async def async_setup_entry(hass: HomeAssistant, entry: TimerifyConfigEntry) -> bool:
    """Set up the timer of one target and its entities."""
    store = TimerStore(hass, entry.entry_id)
    controller = TargetController(hass, entry, store, await store.async_load())
    entry.runtime_data = controller
    entry.async_on_unload(_follow_target(hass, entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await controller.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TimerifyConfigEntry) -> bool:
    """Unload the entities of a target; the controller's alarms go with the entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: TimerifyConfigEntry) -> None:
    """Delete the stored timer of a removed entry."""
    await TimerStore(hass, entry.entry_id).async_remove()


def _follow_target(hass: HomeAssistant, entry: TimerifyConfigEntry) -> CALLBACK_TYPE:
    """Keep the entry in step with its target in the entity registry.

    A renamed target is followed by updating the `target` option and reloading;
    a target that moves to another device, or off its device, takes the entities
    along; the entities of a removed target are left on no device.
    """

    def set_target(entity_id: str) -> None:
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_TARGET: entity_id}
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)

    return async_handle_source_entity_changes(
        hass,
        helper_config_entry_id=entry.entry_id,
        set_source_entity_id_or_uuid=set_target,
        source_device_id=async_entity_id_to_device_id(hass, entry.options[CONF_TARGET]),
        source_entity_id_or_uuid=entry.options[CONF_TARGET],
    )
