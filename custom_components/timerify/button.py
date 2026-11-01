"""The Turn off button of a timer: a control on the device that stops it."""

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_OFF_BUTTON, KEY_TURN_OFF
from .controller import TimerifyConfigEntry
from .entity import TimerifyEntity, remove_timer_entity

PARALLEL_UPDATES = 0
"""The controller runs commands one at a time itself."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TimerifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the Turn off button of a timer that has one; if it has not, take the entry
    of a button it had before out of the registry."""
    if entry.options.get(CONF_OFF_BUTTON):
        async_add_entities([TurnOffButton(hass, entry)])
    else:
        remove_timer_entity(hass, entry, "button", KEY_TURN_OFF)


class TurnOffButton(TimerifyEntity, ButtonEntity):
    """Stops the timer, as setting Run for to 0 does: it ends a countdown and turns the
    target off, a target that runs without a countdown included.

    It is a control of the device, so it has no entity category.
    """

    entity_description = ButtonEntityDescription(
        key=KEY_TURN_OFF, translation_key="turn_off"
    )

    async def async_press(self) -> None:
        """Stop the timer."""
        await self._controller.async_set_minutes(0)

    @callback
    def _handle_controller_update(self) -> None:
        """Write nothing: the state of a button is the time it was last pressed."""
