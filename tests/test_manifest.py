"""Home Assistant discovers Timerify as a custom integration."""

import tomllib
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.loader import (
    async_get_integration,
    async_get_integration_descriptions,
)
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.timerify.const import DOMAIN

from .conftest import FakeTarget
from .helpers import add_target

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"

INTEGRATIONS_TAB = ["device", "hub", "service", "hardware"]
"""The types of integration whose entries the Integrations tab of Home Assistant asks
for. A helper is not among them."""


async def test_integration_is_discovered(hass: HomeAssistant) -> None:
    """The loader finds the manifest and reads it as a service integration."""
    integration = await async_get_integration(hass, DOMAIN)

    assert integration.domain == DOMAIN
    assert integration.name == "Timerify"
    assert integration.integration_type == "service"
    assert integration.version is not None


async def test_timerify_is_added_as_an_integration(hass: HomeAssistant) -> None:
    """The user adds a timer with "Add integration" on the Integrations tab. Timerify
    is not offered under "Create helper"."""
    custom = (await async_get_integration_descriptions(hass))["custom"]

    assert DOMAIN in custom["integration"]
    assert DOMAIN not in custom["helper"]


async def test_a_timer_is_on_the_integrations_tab(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    fake_target: FakeTarget,
) -> None:
    """A timer the user added is listed on the Integrations tab, which is the way to
    the page where its schedule intervals are added. The tab asks for the entries of
    devices, hubs, services and hardware. The Helpers tab does not list the timer."""
    assert await async_setup_component(hass, "config", {})
    entry = await add_target(hass)
    client = await hass_ws_client(hass)

    async def listed(type_filter: list[str]) -> list[str]:
        await client.send_json_auto_id(
            {"type": "config_entries/get", "type_filter": type_filter}
        )
        message = await client.receive_json()
        assert message["success"]
        return [
            found["entry_id"]
            for found in message["result"]
            if found["domain"] == DOMAIN
        ]

    assert await listed(INTEGRATIONS_TAB) == [entry.entry_id]
    assert await listed(["helper"]) == []


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
