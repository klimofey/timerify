"""Facts about a target entity that the config flow and the entities both need."""

from collections import Counter

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_TARGET, DOMAIN


def target_name(hass: HomeAssistant, entity_id: str) -> str:
    """The name the user knows the target by.

    The registry knows it as soon as Home Assistant has loaded; the state may not
    exist yet while the target's own integration is still starting.
    """
    entry = er.async_get(hass).async_get(entity_id)
    if entry is not None and (name := er.async_get_full_entity_name(hass, entry)):
        return name
    if (state := hass.states.get(entity_id)) is not None:
        return state.name
    return entity_id


def target_label(hass: HomeAssistant, entity_id: str) -> str:
    """The name that tells the target from the other entities of its device: its own
    name, without the device's.

    It is the target's full name (`target_name`) when nothing is left of it, as for a
    boiler called Boiler on a device called Boiler, and when the target is not in the
    registry.
    """
    entry = er.async_get(hass).async_get(entity_id)
    if entry is not None and (name := er.async_get_unprefixed_name(hass, entry)):
        return name
    return target_name(hass, entity_id)


def timers_by_device(
    hass: HomeAssistant, *, removed: str | None = None
) -> Counter[str]:
    """How many timers each device holds, by the id of the device.

    Every timer counts, loaded or not: one that is disabled or failed to load still
    has its target on the device, and comes back to it. `removed` is the id of an entry
    to leave out, one that is being deleted. The settings of the voice have no target
    and count nowhere, and neither does a timer whose target is on no device, which gets
    a device of its own, or is not in the registry.
    """
    registry = er.async_get(hass)
    timers = Counter[str]()
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == removed or CONF_TARGET not in entry.options:
            continue
        target = registry.async_get(entry.options[CONF_TARGET])
        if target is not None and target.device_id is not None:
            timers[target.device_id] += 1
    return timers


def shares_its_device(
    hass: HomeAssistant, entity_id: str, timers: Counter[str]
) -> bool:
    """Whether the target is on a device that holds more than one timer, by the count
    `timers_by_device` made."""
    target = er.async_get(hass).async_get(entity_id)
    return (
        target is not None
        and target.device_id is not None
        and timers[target.device_id] > 1
    )
