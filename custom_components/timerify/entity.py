"""The base class of a timer's entities, and the device they are on."""

from collections.abc import Mapping

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device import async_entity_id_to_device
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, WITH_TARGET_SUFFIX, timer_unique_id
from .controller import TimerifyConfigEntry


def _fallback_identifier(entry: TimerifyConfigEntry) -> tuple[str, str]:
    """The identifier of the device made for a timer whose target is on no device."""
    return (DOMAIN, entry.entry_id)


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
        identifiers={_fallback_identifier(entry)},
        name=controller.device_name,
    )


@callback
def remove_fallback_device(hass: HomeAssistant, entry: TimerifyConfigEntry) -> None:
    """Remove the device made for the timer once its target is on a device of its own.

    The target's integration can link it to a device while Home Assistant is down, and
    nothing follows that: the entities move to the target's device when they are added,
    but the device made for the timer stays behind, empty. The entities are moved here
    first, because the registry removes the entities of a device it removes, and they
    would vanish for the automations that watch them and then come back. An entity that
    was disabled with the made device (`disabled_by` is the device) is enabled on the
    target's, as the registry does when a device is enabled; one the user disabled
    stays disabled.

    A target that is still on no device keeps the device made for it.
    """
    device = async_entity_id_to_device(hass, entry.runtime_data.target_entity_id)
    devices = dr.async_get(hass)
    fallback = devices.async_get_device_by_identifier(
        _fallback_identifier(entry), entry.entry_id
    )
    if device is None or fallback is None:
        return
    entities = er.async_get(hass)
    for entity in er.async_entries_for_device(
        entities, fallback.id, include_disabled_entities=True
    ):
        disabled_by = entity.disabled_by
        if disabled_by is er.RegistryEntryDisabler.DEVICE and not device.disabled:
            disabled_by = None
        entities.async_update_entity(
            entity.entity_id, device_id=device.id, disabled_by=disabled_by
        )
    devices.async_remove_device(fallback.id)


@callback
def remove_timer_entity(
    hass: HomeAssistant, entry: TimerifyConfigEntry, domain: str, key: str
) -> None:
    """Remove the registry entry of the timer's entity of `domain` with the key `key`,
    if there is one: the entity of an option the timer no longer has.

    Nothing else removes it: left there, it would come back at every start as an
    unavailable entity. Choosing the option again brings it back as it was, with its
    entity id and its history, because the registry keeps a removed entry's identity.
    """
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        domain, DOMAIN, timer_unique_id(entry.entry_id, key)
    )
    if entity_id is not None:
        registry.async_remove(entity_id)


class TimerifyEntity(Entity):
    """An entity of one target: on the target's device, refreshed by its controller.

    A target that is on no device gets one of its own, shared by all its entities.
    Subclasses declare their `entity_description`.

    On a device that holds more than one timer the entity is named after its target:
    it is translated by the key of its description and `_with_target`, whose name has
    the placeholder `target` (`TargetController.target_label`).
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TimerifyConfigEntry,
        *,
        unique_id: str | None = None,
        placeholders: Mapping[str, str] | None = None,
    ) -> None:
        """`unique_id` is the entity's own; without one it is the timer's id and the
        key of the entity's description, for an entity that a timer has one of.
        `placeholders` fill in the blanks of the entity's name.

        The key and the placeholders are set here, once: Home Assistant keeps what it
        reads of them, so an entity is named for as long as it lives.
        """
        self._controller = entry.runtime_data
        self._attr_unique_id = (
            timer_unique_id(entry.entry_id, self.entity_description.key)
            if unique_id is None
            else unique_id
        )
        self.device_entry = timer_device(hass, entry)
        if (label := self._controller.target_label) is not None:
            key = self.entity_description.translation_key
            assert key is not None  # Every entity of a timer is translated.
            self._attr_translation_key = f"{key}{WITH_TARGET_SUFFIX}"
            self._attr_translation_placeholders = {
                **(placeholders or {}),
                "target": label,
            }
        elif placeholders is not None:
            self._attr_translation_placeholders = dict(placeholders)

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
