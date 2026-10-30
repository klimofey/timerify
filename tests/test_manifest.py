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
    """Timerify imports from the conversation and llm integrations, so Home Assistant
    installs what they need before it imports Timerify."""
    integration = await async_get_integration(hass, DOMAIN)

    assert integration.after_dependencies == ["conversation", "llm"]


async def test_voice_test_dependencies_match_conversation(hass: HomeAssistant) -> None:
    """The tests run the real built-in agent, so the development environment has what
    the conversation integration of the pinned Home Assistant requires, in the very
    versions it pins."""
    conversation = await async_get_integration(hass, "conversation")
    pyproject = tomllib.loads(PYPROJECT.read_text("utf-8"))

    assert conversation.requirements
    assert set(conversation.requirements) <= set(pyproject["dependency-groups"]["dev"])
