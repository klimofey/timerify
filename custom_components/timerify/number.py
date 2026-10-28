"""The "Run for" number: remaining minutes of the countdown, writable."""

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import MAX_MINUTES
from .controller import TimerifyConfigEntry
from .core import remaining_minutes
from .entity import TimerifyEntity

PARALLEL_UPDATES = 0
"""The controller runs commands one at a time itself."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TimerifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the "Run for" number of a target."""
    async_add_entities([RunForNumber(hass, entry)])


class RunForNumber(TimerifyEntity, NumberEntity):
    """Minutes left, rounded up; setting it starts, changes or stops the timer."""

    entity_description = NumberEntityDescription(
        key="run_for",
        translation_key="run_for",
        native_min_value=0,
        native_max_value=MAX_MINUTES,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.SLIDER,
    )

    @property
    def native_value(self) -> float:
        """The remaining minutes."""
        return remaining_minutes(self._controller.snapshot, dt_util.utcnow())

    async def async_set_native_value(self, value: float) -> None:
        """Count down `value` minutes from now."""
        await self._controller.async_set_minutes(int(value))
