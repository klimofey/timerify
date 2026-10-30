"""Fixtures of the voice tests: the built-in agent as a user talks to it."""

from pathlib import Path

import pytest
from homeassistant.components.fan.const import FanEntityFeature
from homeassistant.components.light.const import ColorMode
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from ..conftest import (
    CLIMATE_SERVICES,
    SWITCH_SERVICES,
    FakeTarget,
    ProvideTarget,
    SetupTarget,
)
from ..helpers import AC_ATTRS, AC_ID, JERUSALEM
from .helpers import copy_sentences


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


@pytest.fixture
async def boiler(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> MockConfigEntry:
    """A timer on the Boiler, which Assist knows by the sentences of the manual
    installation."""
    entry = await setup_target()
    await copy_sentences(hass, ["Boiler"])
    return entry


@pytest.fixture
def fake_lamp(provide_target: ProvideTarget) -> FakeTarget:
    """`light.lamp` on a device called Lamp, switched off: a light with a brightness."""
    return provide_target(
        "light.lamp",
        SWITCH_SERVICES,
        name="Lamp",
        capability_attributes={"supported_color_modes": [ColorMode.BRIGHTNESS]},
    )


@pytest.fixture
def fake_vent(provide_target: ProvideTarget) -> FakeTarget:
    """`fan.vent` on a device called Vent, switched off: a fan with a speed and two
    presets."""
    return provide_target(
        "fan.vent",
        SWITCH_SERVICES,
        name="Vent",
        capability_attributes={
            "preset_modes": ["eco", "sleep"],
            "supported_features": int(
                FanEntityFeature.TURN_ON
                | FanEntityFeature.TURN_OFF
                | FanEntityFeature.SET_SPEED
                | FanEntityFeature.PRESET_MODE
            ),
        },
    )


HVAC_MODES = ["off", "heat", "cool", "heat_cool", "auto", "dry", "fan_only"]
"""Every mode a thermostat can have, the ones people say a word for."""


@pytest.fixture
def fake_full_ac(provide_target: ProvideTarget) -> FakeTarget:
    """`climate.ac` on a device called AC, switched off: the air conditioner of
    `fake_climate`, but for a thermostat that has every mode there is."""
    return provide_target(
        AC_ID,
        CLIMATE_SERVICES,
        name="AC",
        capability_attributes={**AC_ATTRS, "hvac_modes": HVAC_MODES},
        state_attributes={"temperature": 20, "fan_mode": "auto"},
    )
