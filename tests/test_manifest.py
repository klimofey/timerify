"""Home Assistant discovers Timerify as a custom integration."""

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from custom_components.timerify.const import DOMAIN


async def test_integration_is_discovered(hass: HomeAssistant) -> None:
    """The loader finds the manifest and reads it as a helper integration."""
    integration = await async_get_integration(hass, DOMAIN)

    assert integration.domain == DOMAIN
    assert integration.name == "Timerify"
    assert integration.integration_type == "helper"
    assert integration.version is not None
