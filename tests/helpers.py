"""Helpers shared by the scenario tests: the entities, the calls and the clock."""

from datetime import timedelta
from typing import Any, Final

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.climate.const import ClimateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed

TARGET_ID = "switch.boiler"
NUMBER = "number.boiler_run_for"
SENSOR = "sensor.boiler_ends_at"
TURN_ON = ("turn_on", TARGET_ID)
TURN_OFF = ("turn_off", TARGET_ID)

AC_ID = "climate.ac"
AC_ATTRS: Final[dict[str, Any]] = {
    "hvac_modes": ["off", "heat", "cool", "fan_only"],
    "min_temp": 16,
    "max_temp": 30,
    "fan_modes": ["auto", "low", "high"],
    "supported_features": int(
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    ),
}
"""The capability attributes and supported features of an air conditioner that Home
Assistant keeps on its state, also while it is unavailable."""


async def set_number(hass: HomeAssistant, entity_id: str, value: float) -> None:
    """Move the slider, as the dashboard does, and let the target's report settle."""
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": value},
        blocking=True,
    )
    await hass.async_block_till_done()


async def advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, **delta: float
) -> None:
    """Let time pass and run everything that falls due."""
    freezer.tick(timedelta(**delta))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def state_of(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


def storage_key(entry: ConfigEntry) -> str:
    """The key under which the timer of `entry` is stored."""
    return f"timerify.{entry.entry_id}"
