"""Helpers shared by the scenario tests: the entities, the calls and the clock."""

import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Literal

import probatio
import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.climate.const import ClimateEntityFeature
from homeassistant.config_entries import ConfigEntry, SubentryFlowResult
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType, section
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_state_report_event,
)
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.timerify.const import DOMAIN, SUBENTRY_INTERVAL

START = datetime(2026, 1, 5, 7, 0, tzinfo=UTC)
"""The frozen time every entity test starts at."""

TARGET_ID = "switch.boiler"
NUMBER = "number.boiler_run_for"
SENSOR = "sensor.boiler_ends_at"
NEXT = "sensor.boiler_next_command"
TURN_ON = ("turn_on", TARGET_ID)
TURN_OFF = ("turn_off", TARGET_ID)

WEEK: Final = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
"""The names of the weekdays, in week order."""

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
AC_NEXT = "sensor.ac_next_command"


async def call_service(
    hass: HomeAssistant, service: str, target: dict[str, Any], **data: Any
) -> None:
    """Call a Timerify service the way an automation or the UI does."""
    await hass.services.async_call(DOMAIN, service, {**target, **data}, blocking=True)
    await hass.async_block_till_done()


async def add_command(
    hass: HomeAssistant, number: str | list[str], **data: Any
) -> dict[str, Any]:
    """Add a pending command to the timers of the "Run for" number(s) `number` and
    return the response of the service: the new command's id for each number."""
    response = await hass.services.async_call(
        DOMAIN,
        "add_command",
        {"entity_id": number, **data},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()
    assert response is not None
    return response


def _prefilled(schema: probatio.Schema) -> dict[str, Any]:
    """What a form submits when the user touches nothing: for each field the value it
    shows, which is the suggested value or else the default."""
    values: dict[str, Any] = {}
    for marker, validator in schema.schema.items():
        if isinstance(validator, section):
            values[marker.schema] = _prefilled(validator.schema)
        elif (shown := (marker.description or {}).get("suggested_value")) is not None:
            values[marker.schema] = shown
        elif callable(marker.default):
            values[marker.schema] = marker.default()
    return values


async def submit_interval(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    start: str,
    end: str,
    weekdays: Sequence[str] = WEEK,
    settings: dict[str, Any] | None = None,
) -> SubentryFlowResult:
    """Press "Add schedule interval" on the entry's page and fill in the form; return
    what the flow answers, which is the form again when it refuses the input."""
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_INTERVAL), context={"source": "user"}
    )
    user_input: dict[str, Any] = {
        "weekdays": list(weekdays),
        "start": start,
        "end": end,
    }
    if settings is not None:
        user_input["settings"] = settings
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()
    return result


async def add_interval(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    start: str,
    end: str,
    weekdays: Sequence[str] = WEEK,
    settings: dict[str, Any] | None = None,
) -> str:
    """Add a schedule interval to the entry through its form and return the id of the
    new subentry."""
    known = set(entry.subentries)
    result = await submit_interval(
        hass, entry, start=start, end=end, weekdays=weekdays, settings=settings
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (subentry_id,) = set(entry.subentries) - known
    return subentry_id


async def edit_interval(
    hass: HomeAssistant, entry: ConfigEntry, subentry_id: str, **fields: Any
) -> SubentryFlowResult:
    """Press "Edit" on an interval, change `fields` of the form it shows (`weekdays`,
    `start`, `end`, `settings`) and submit it; return what the flow answers."""
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_INTERVAL),
        context={"source": "reconfigure", "subentry_id": subentry_id},
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**_prefilled(result["data_schema"]), **fields}
    )
    await hass.async_block_till_done()
    return result


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


def command_json(
    when: str,
    action: Literal["on", "off"] = "on",
    minutes: int | None = None,
    settings: dict[str, Any] | None = None,
    id: str = "c1",
) -> dict[str, Any]:
    """The stored form of a pending command due at `when` (see `at`)."""
    return {
        "id": id,
        "at": when,
        "action": action,
        "minutes": minutes,
        "settings": settings or {},
    }


def payload(
    end: str | None = None,
    pending: str | None = None,
    owed_settings: dict[str, Any] | None = None,
    commands: Sequence[dict[str, Any]] = (),
    owed_turn_on_only: bool = False,
) -> dict[str, Any]:
    """What the storage file of a timer holds: the stored form of its snapshot."""
    return {
        "end": end,
        "pending": pending,
        "owed_settings": owed_settings or {},
        "commands": list(commands),
        "owed_turn_on_only": owed_turn_on_only,
    }


def saved(hass_storage: dict[str, Any], entry: ConfigEntry) -> dict[str, Any]:
    """What the storage file of `entry` holds."""
    return hass_storage[storage_key(entry)]["data"]


def record_writes(hass: HomeAssistant, entity_id: str) -> list[str]:
    """The state every write to `entity_id` carried, changed or not."""
    writes: list[str] = []

    @callback
    def record(event: Event[Any]) -> None:
        writes.append(event.data["new_state"].state)

    async_track_state_change_event(hass, entity_id, record)
    async_track_state_report_event(hass, entity_id, record)
    return writes


def state_of(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


def storage_key(entry: ConfigEntry) -> str:
    """The key under which the timer of `entry` is stored."""
    return f"timerify.{entry.entry_id}"


def _timerify_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if record.name.startswith("custom_components.timerify")
    ]


def timerify_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """What Timerify said at warning level or above."""
    return [
        record.getMessage()
        for record in _timerify_records(caplog)
        if record.levelno >= logging.WARNING
    ]


def timerify_info(caplog: pytest.LogCaptureFixture) -> list[str]:
    """What Timerify said at info level exactly; the test sets the level that is
    recorded."""
    return [
        record.getMessage()
        for record in _timerify_records(caplog)
        if record.levelno == logging.INFO
    ]
