"""Fixtures of the voice tests: the built-in agent as a user talks to it."""

from pathlib import Path

import pytest
from homeassistant.components.fan.const import FanEntityFeature
from homeassistant.components.humidifier.const import HumidifierEntityFeature
from homeassistant.components.light.const import ColorMode
from homeassistant.components.water_heater.const import WaterHeaterEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from ..conftest import (
    CLIMATE_SERVICES,
    SWITCH_SERVICES,
    FakeTarget,
    Obey,
    ProvideTarget,
    SetupTarget,
    sets_attribute,
    switches_to,
)
from ..helpers import AC_ATTRS, AC_ID, JERUSALEM, SMALL_AC_ID
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
    """`fan.vent` on a device called Vent, switched off: a fan with a speed and three
    presets, one of them `auto`."""
    return provide_target(
        "fan.vent",
        SWITCH_SERVICES,
        name="Vent",
        capability_attributes={
            "preset_modes": ["auto", "eco", "sleep"],
            "supported_features": int(
                FanEntityFeature.TURN_ON
                | FanEntityFeature.TURN_OFF
                | FanEntityFeature.SET_SPEED
                | FanEntityFeature.PRESET_MODE
            ),
        },
    )


@pytest.fixture
def fake_demo_fan(provide_target: ProvideTarget) -> FakeTarget:
    """`fan.vent` on a device called Vent, switched off: a fan of the Demo integration,
    which has Russian words for its presets, with the presets `sleep`, which it has a
    word for, and `turbo_x`, which no integration has."""
    return provide_target(
        "fan.vent",
        SWITCH_SERVICES,
        name="Vent",
        platform="demo",
        translation_key="demo",
        capability_attributes={
            "preset_modes": ["sleep", "turbo_x"],
            "supported_features": int(
                FanEntityFeature.TURN_ON
                | FanEntityFeature.TURN_OFF
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


@pytest.fixture
def fake_small_ac(provide_target: ProvideTarget) -> FakeTarget:
    """`climate.small_ac` on a device called Small AC, switched off: a second air
    conditioner, for a house where two thermostats have different modes. It has the
    modes `off`, `cool` and `fan_only`, and the fan modes of `fake_climate`."""
    return provide_target(
        SMALL_AC_ID,
        CLIMATE_SERVICES,
        name="Small AC",
        capability_attributes={**AC_ATTRS, "hvac_modes": ["off", "cool", "fan_only"]},
        state_attributes={"temperature": 20, "fan_mode": "auto"},
    )


HUMIDIFIER_SERVICES: dict[str, Obey] = {
    "turn_on": switches_to("on"),
    "turn_off": switches_to("off"),
    "set_mode": sets_attribute("mode"),
    "set_humidity": sets_attribute("humidity"),
}
"""The services of a humidifier."""


@pytest.fixture
def fake_humidifier(provide_target: ProvideTarget) -> FakeTarget:
    """`humidifier.humidifier` on a device called Humidifier, switched off: a
    humidifier with a humidity of 30 to 80 percent and the modes `auto` and `eco`."""
    return provide_target(
        "humidifier.humidifier",
        HUMIDIFIER_SERVICES,
        name="Humidifier",
        capability_attributes={
            "min_humidity": 30,
            "max_humidity": 80,
            "available_modes": ["auto", "eco"],
            "supported_features": int(HumidifierEntityFeature.MODES),
        },
        state_attributes={"humidity": 50, "mode": "eco"},
    )


@pytest.fixture
def fake_dehumidifier(provide_target: ProvideTarget) -> FakeTarget:
    """`humidifier.dehumidifier` on a device called Dehumidifier, switched off: a
    humidifier of the device class `dehumidifier`, with the mode `eco`."""
    return provide_target(
        "humidifier.dehumidifier",
        HUMIDIFIER_SERVICES,
        name="Dehumidifier",
        capability_attributes={
            "min_humidity": 30,
            "max_humidity": 80,
            "available_modes": ["eco"],
            "device_class": "dehumidifier",
            "supported_features": int(HumidifierEntityFeature.MODES),
        },
        state_attributes={"humidity": 50, "mode": "eco"},
    )


WATER_HEATER_SERVICES: dict[str, Obey] = {
    "turn_on": switches_to("on"),
    "turn_off": switches_to("off"),
    "set_temperature": sets_attribute("temperature"),
    "set_operation_mode": sets_attribute("operation_mode"),
}
"""The services of a water heater."""


@pytest.fixture
def fake_tank(provide_target: ProvideTarget) -> FakeTarget:
    """`water_heater.tank` on a device called Tank, switched off: a water heater with
    a temperature of 30 to 70 degrees and the operation modes `eco` and `electric`."""
    return provide_target(
        "water_heater.tank",
        WATER_HEATER_SERVICES,
        name="Tank",
        capability_attributes={
            "min_temp": 30,
            "max_temp": 70,
            "operation_list": ["off", "eco", "electric"],
            "supported_features": int(
                WaterHeaterEntityFeature.TARGET_TEMPERATURE
                | WaterHeaterEntityFeature.OPERATION_MODE
                | WaterHeaterEntityFeature.ON_OFF
            ),
        },
        state_attributes={"temperature": 50, "operation_mode": "eco"},
    )


@pytest.fixture
def fake_fahrenheit_tank(provide_target: ProvideTarget) -> FakeTarget:
    """`water_heater.tank` on a device called Tank, switched off: a water heater of a
    house that counts in Fahrenheit, with a temperature of 100 to 150 degrees and the
    operation modes `eco` and `electric`, as `fake_tank` is in Celsius."""
    return provide_target(
        "water_heater.tank",
        WATER_HEATER_SERVICES,
        name="Tank",
        capability_attributes={
            "min_temp": 100,
            "max_temp": 150,
            "operation_list": ["off", "eco", "electric"],
            "supported_features": int(
                WaterHeaterEntityFeature.TARGET_TEMPERATURE
                | WaterHeaterEntityFeature.OPERATION_MODE
                | WaterHeaterEntityFeature.ON_OFF
            ),
        },
        state_attributes={"temperature": 120, "operation_mode": "eco"},
    )
