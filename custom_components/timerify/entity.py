"""Base class of the entities Timerify adds to a target's device."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device import async_entity_id_to_device
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .controller import TimerifyConfigEntry


class TimerifyEntity(Entity):
    """An entity of one target: on the target's device, refreshed by its controller.

    A target that is on no device gets one of its own, shared by all its entities.
    Subclasses declare their `entity_description`.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: TimerifyConfigEntry) -> None:
        self._controller = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{self.entity_description.key}"
        target = self._controller.target_entity_id
        self.device_entry = async_entity_id_to_device(hass, target)
        if self.device_entry is None:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, entry.entry_id)},
                name=self._controller.device_name,
            )

    async def async_added_to_hass(self) -> None:
        """Follow the controller."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._controller.async_add_listener(self._handle_controller_update)
        )

    @callback
    def _handle_controller_update(self) -> None:
        """The controller reports that what the entity shows may have changed.

        By default the state is written again; entities that show less than the
        whole timer can skip the write.
        """
        self.async_write_ha_state()
