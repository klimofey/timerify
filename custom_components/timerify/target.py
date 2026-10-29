"""Facts about a target entity that the config flow and the entities both need."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


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
