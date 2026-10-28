"""Timerify: countdowns, auto-off and schedules attached to existing entities."""

from typing import Final

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .controller import TargetController, TimerifyConfigEntry
from .store import TimerStore

PLATFORMS: Final = (Platform.NUMBER, Platform.SENSOR)


async def async_setup_entry(hass: HomeAssistant, entry: TimerifyConfigEntry) -> bool:
    """Set up the timer of one target and its entities."""
    store = TimerStore(hass, entry.entry_id)
    controller = TargetController(hass, entry, store, await store.async_load())
    entry.runtime_data = controller
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await controller.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TimerifyConfigEntry) -> bool:
    """Unload the entities of a target; the controller's alarms go with the entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
