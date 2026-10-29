"""The "Ends at" sensor: when the countdown reaches zero."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .controller import TimerifyConfigEntry
from .entity import TimerifyEntity

PARALLEL_UPDATES = 0
"""The sensor only reads the controller."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TimerifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the "Ends at" sensor of a target."""
    async_add_entities([EndsAtSensor(hass, entry)])


class EndsAtSensor(TimerifyEntity, SensorEntity):
    """The moment the countdown ends; unknown while no countdown runs.

    The frontend counts down to it by itself, so the sensor is written only when
    the end moves, not as the minutes pass.
    """

    entity_description = SensorEntityDescription(
        key="ends_at",
        translation_key="ends_at",
        device_class=SensorDeviceClass.TIMESTAMP,
    )

    async def async_added_to_hass(self) -> None:
        """Show the end of the countdown as it is now, then follow it."""
        self._attr_native_value = self._controller.snapshot.end
        await super().async_added_to_hass()

    @callback
    def _handle_controller_update(self) -> None:
        if (end := self._controller.snapshot.end) != self._attr_native_value:
            self._attr_native_value = end
            self.async_write_ha_state()
