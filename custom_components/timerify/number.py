"""The "Run for" number: remaining minutes of the countdown, writable."""

from datetime import datetime, timedelta
from typing import Any, Literal

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, ServiceResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MAX_MINUTES
from .controller import TimerifyConfigEntry, command_when
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

    _shown: float | None = None
    """The minutes the state was last written with."""

    @property
    def native_value(self) -> float:
        """The remaining minutes."""
        return remaining_minutes(self._controller.snapshot, dt_util.utcnow())

    async def async_added_to_hass(self) -> None:
        """Show the minutes as they are now, then follow them."""
        self._shown = self.native_value
        await super().async_added_to_hass()

    @callback
    def _handle_controller_update(self) -> None:
        """Write the state when the minutes changed; a change of the timer that leaves
        them as they were, such as an interval switched before its window, writes
        nothing."""
        if (minutes := self.native_value) != self._shown:
            self._shown = minutes
            self.async_write_ha_state()

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

    async def async_add_command(
        self,
        action: Literal["on", "off"],
        delay: int | None = None,
        at: datetime | None = None,
        minutes: int | None = None,
        **settings: Any,
    ) -> ServiceResponse:
        """Keep a command to turn the target on or off, `delay` minutes from now or at
        the time `at`; the response is its id.

        An "on" runs for `minutes` and with the `settings` given. Exactly one of
        `delay` and `at` is wanted.
        """
        when = command_when(None if delay is None else timedelta(minutes=delay), at)
        command_id = await self._controller.async_add_command(
            action, when, minutes, settings
        )
        return {"command_id": command_id}

    async def async_cancel_command(self, command_id: str) -> None:
        """Forget the pending command with that id; it must be this timer's own."""
        await self._controller.async_cancel_command(command_id)
