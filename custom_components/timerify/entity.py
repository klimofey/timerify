"""Base class of the entities Timerify adds to a target's device."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device import async_entity_id_to_device
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .controller import TimerifyConfigEntry


def timer_device(hass: HomeAssistant, entry: TimerifyConfigEntry) -> dr.AnyDeviceEntry:
    """The device the entities of a timer are on: the target's own or, for a target that
    is on none, one Timerify makes for the timer, named after the target.

    An entity is put on it by `Entity.device_entry`, never by a `DeviceInfo`: with a
    `DeviceInfo` the platform registers the device under the subentry the entity is
    added to, so the switch of an interval would move the timer's device into the
    interval's subentry, the other entities would leave the registry with it, and
    deleting the interval would delete the device. The device made for the timer
    belongs to the entry alone.
    """
    controller = entry.runtime_data
    device = async_entity_id_to_device(hass, controller.target_entity_id)
    if device is not None:
        return device
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=controller.device_name,
    )


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
        self.device_entry = timer_device(hass, entry)

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
