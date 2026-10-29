"""The sensors of a timer: when the countdown ends, and the next pending command."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .controller import TimerifyConfigEntry
from .core import Command
from .entity import TimerifyEntity
from .store import command_to_json

PARALLEL_UPDATES = 0
"""The sensor only reads the controller."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TimerifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the "Ends at" and "Next command" sensors of a target."""
    async_add_entities([EndsAtSensor(hass, entry), NextCommandSensor(hass, entry)])


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


class NextCommandSensor(TimerifyEntity, SensorEntity):
    """When the next pending command is due; unknown while there is none.

    The attribute `commands` lists every pending command, for the card and for voice.
    The list is not worth keeping in the history (it is stored again with every
    change), so the recorder leaves it out. The sensor is written only when the
    commands change.
    """

    entity_description = SensorEntityDescription(
        key="next_command",
        translation_key="next_command",
        device_class=SensorDeviceClass.TIMESTAMP,
    )
    _unrecorded_attributes = frozenset({"commands"})

    _shown: tuple[Command, ...] = ()
    """The commands the state was last written with."""

    async def async_added_to_hass(self) -> None:
        """Show the commands as they are now, then follow them."""
        self._show(self._controller.snapshot.commands)
        await super().async_added_to_hass()

    def _show(self, commands: tuple[Command, ...]) -> None:
        self._shown = commands
        self._attr_native_value = commands[0].at if commands else None
        self._attr_extra_state_attributes = {
            "commands": [command_to_json(command) for command in commands]
        }

    @callback
    def _handle_controller_update(self) -> None:
        if (commands := self._controller.snapshot.commands) != self._shown:
            self._show(commands)
            self.async_write_ha_state()
