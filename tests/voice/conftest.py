"""Fixtures of the voice tests: the built-in agent as a user talks to it."""

from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from ..conftest import SWITCH_SERVICES, FakeTarget, ProvideTarget
from ..helpers import JERUSALEM


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """A configuration directory of the test's own: the tests that write sentence
    files write them there, not into the plugin's."""
    return hass_tmp_config_dir


@pytest.fixture
async def assist(hass: HomeAssistant, hass_config_dir: str) -> None:
    """Assist as a user has it: the conversation integration with its built-in agent
    and the intent integration, on a clock that reads Jerusalem time.

    The configuration file is empty, since reloading the sentences reads it.
    """
    await hass.async_add_executor_job(
        Path(hass_config_dir, "configuration.yaml").write_text, "", "utf-8"
    )
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    assert await async_setup_component(hass, "intent", {})
    await hass.config.async_set_time_zone(JERUSALEM)


@pytest.fixture
def fake_fan(provide_target: ProvideTarget) -> FakeTarget:
    """`switch.fan` on a device called Fan, switched off, with no timer."""
    return provide_target("switch.fan", SWITCH_SERVICES, name="Fan")
