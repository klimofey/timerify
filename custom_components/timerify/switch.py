"""The switch of a schedule interval: whether the interval runs the timer."""

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SUBENTRY_INTERVAL, interval_unique_id
from .controller import TimerifyConfigEntry
from .entity import TimerifyEntity

PARALLEL_UPDATES = 0
"""The controller runs commands one at a time itself."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TimerifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the switch of each schedule interval to the subentry that holds it, so that
    deleting the interval takes its switch along."""
    for subentry in entry.get_subentries_of_type(SUBENTRY_INTERVAL):
        async_add_entities(
            [IntervalSwitch(hass, entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class IntervalSwitch(TimerifyEntity, SwitchEntity):
    """On while its interval runs the timer; switched off, the interval is skipped.

    The flag lives in the timer's file, not in the entry, so flipping the switch
    reloads nothing. The switch is written only when its own flag changes.

    It configures the timer, so it is a configuration entity: it sits in the device's
    configuration section, and Assist does not know it by default, as it would a switch
    of the house. A timer is driven by voice through its target.
    """

    entity_description = SwitchEntityDescription(
        key="interval",
        translation_key="interval",
        entity_category=EntityCategory.CONFIG,
    )

    def __init__(
        self, hass: HomeAssistant, entry: TimerifyConfigEntry, subentry: ConfigSubentry
    ) -> None:
        super().__init__(
            hass,
            entry,
            unique_id=interval_unique_id(entry.entry_id, subentry.subentry_id),
        )
        self._interval_id = subentry.subentry_id
        self._attr_translation_placeholders = {"interval": subentry.title}

    def _is_enabled(self) -> bool:
        return self._interval_id not in self._controller.snapshot.disabled_intervals

    async def async_added_to_hass(self) -> None:
        """Show the flag as it is now, then follow it."""
        self._attr_is_on = self._is_enabled()
        await super().async_added_to_hass()

    @callback
    def _handle_controller_update(self) -> None:
        if (enabled := self._is_enabled()) != self._attr_is_on:
            self._attr_is_on = enabled
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Let the interval run the timer; if its window is open, for the rest of it."""
        await self._controller.async_set_interval_enabled(
            self._interval_id, True, context=self._context
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Skip the interval; if it runs the timer, the timer stops (S2)."""
        await self._controller.async_set_interval_enabled(
            self._interval_id, False, context=self._context
        )
