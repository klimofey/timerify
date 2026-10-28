"""Base class of the entities Timerify adds to a target's device."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device import async_entity_id_to_device
from homeassistant.helpers.entity import Entity

from .controller import TimerifyConfigEntry


class TimerifyEntity(Entity):
    """An entity of one target: on the target's device, refreshed by its controller.

    Subclasses declare their `entity_description`.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: TimerifyConfigEntry) -> None:
        self._controller = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{self.entity_description.key}"
        self.device_entry = async_entity_id_to_device(
            hass, self._controller.target_entity_id
        )

    async def async_added_to_hass(self) -> None:
        """Write the state again whenever the controller reports a change."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._controller.async_add_listener(self.async_write_ha_state)
        )
