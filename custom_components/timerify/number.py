"""The "Run for" number: remaining minutes of the countdown, writable."""

from typing import Any

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MAX_MINUTES
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
        """Count down `value` minutes from now; a part of a minute is refused, not
        rounded, as `add_time` does."""
        if not value.is_integer():
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_whole_minutes",
                translation_placeholders={"minutes": f"{value:g}"},
            )
        await self._controller.async_set_minutes(int(value))

    async def async_add_time(self, minutes: int) -> None:
        """Move the end of the countdown by `minutes`, which may be negative."""
        await self._controller.async_add_minutes(minutes)

    async def async_run(self, minutes: int | None = None, **settings: Any) -> None:
        """Switch the target on for `minutes`, or without a duration, with the settings
        the service was given."""
        await self._controller.async_run(minutes, settings)
