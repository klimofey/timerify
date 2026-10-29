"""Helpers shared by the scenario tests: the entities, the calls and the clock."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Final

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.climate.const import ClimateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.timerify.const import DOMAIN

START = datetime(2026, 1, 5, 7, 0, tzinfo=UTC)
"""The frozen time every entity test starts at."""

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
AC_NUMBER = "number.ac_run_for"
AC_ENDS_AT = "sensor.ac_ends_at"


async def call_service(
    hass: HomeAssistant, service: str, target: dict[str, Any], **data: Any
) -> None:
    """Call a Timerify service the way an automation or the UI does."""
    await hass.services.async_call(DOMAIN, service, {**target, **data}, blocking=True)
    await hass.async_block_till_done()


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


def at(minutes: float) -> str:
    """The stored form of the moment `minutes` after `START`: ISO-8601 in UTC."""
    return (START + timedelta(minutes=minutes)).isoformat()


def payload(
    end: str | None = None,
    pending: str | None = None,
    owed_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """What the storage file of a timer holds: the stored form of its snapshot."""
    return {"end": end, "pending": pending, "owed_settings": owed_settings or {}}


def saved(hass_storage: dict[str, Any], entry: ConfigEntry) -> dict[str, Any]:
    """What the storage file of `entry` holds."""
    return hass_storage[storage_key(entry)]["data"]


def state_of(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


def storage_key(entry: ConfigEntry) -> str:
    """The key under which the timer of `entry` is stored."""
    return f"timerify.{entry.entry_id}"


def timerify_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """What Timerify said at warning level or above."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("custom_components.timerify")
        and record.levelno >= logging.WARNING
    ]
