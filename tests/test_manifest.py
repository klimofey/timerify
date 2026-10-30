"""Home Assistant discovers Timerify as a custom integration."""

import tomllib
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from custom_components.timerify.const import DOMAIN

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


async def test_integration_is_discovered(hass: HomeAssistant) -> None:
    """The loader finds the manifest and reads it as a helper integration."""
    integration = await async_get_integration(hass, DOMAIN)

    assert integration.domain == DOMAIN
    assert integration.name == "Timerify"
    assert integration.integration_type == "helper"
    assert integration.version is not None


async def test_voice_integrations_load_before_timerify(hass: HomeAssistant) -> None:
    """The manifest names conversation and llm as after-dependencies, so Home Assistant
    sets them up before Timerify when they are configured, and installs what they need
    before it loads Timerify's voice code. The frontend is named too: the dashboard card
    is loaded by the frontend, which has to be set up first to be told of it."""
    integration = await async_get_integration(hass, DOMAIN)

    assert integration.after_dependencies == ["conversation", "frontend", "llm"]


async def test_card_needs_http(hass: HomeAssistant) -> None:
    """The card is a file that Timerify serves, which needs the web server, and nothing
    more: the frontend is an after-dependency, so that a Home Assistant without
    dashboards does not load the whole UI for Timerify's sake."""
    integration = await async_get_integration(hass, DOMAIN)

    assert integration.dependencies == ["http"]


async def test_voice_test_dependencies_match_conversation(hass: HomeAssistant) -> None:
    """The tests run the real built-in agent, so the development environment has what
    the conversation integration of the pinned Home Assistant requires, in the very
    versions it pins."""
    conversation = await async_get_integration(hass, "conversation")
    pyproject = tomllib.loads(PYPROJECT.read_text("utf-8"))

    assert conversation.requirements
    assert set(conversation.requirements) <= set(pyproject["dependency-groups"]["dev"])
