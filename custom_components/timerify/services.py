"""Timerify's services: they act on the "Run for" numbers of timers.

An entity service targets entities, areas or devices; Home Assistant resolves the
target to the `number` entities this integration owns and calls the method named
here on each, so the service reaches the controller of every timer picked.
"""

from collections.abc import Callable
from typing import Any, Final

import probatio
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service
from homeassistant.helpers.typing import VolDictType
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MAX_DELAY_MINUTES, MAX_MINUTES

SERVICE_ADD_TIME = "add_time"
SERVICE_RUN = "run"
SERVICE_STOP = "stop"
SERVICE_ADD_COMMAND = "add_command"
SERVICE_CANCEL_COMMAND = "cancel_command"

ATTR_MINUTES = "minutes"
ATTR_ACTION = "action"
ATTR_DELAY = "delay"
ATTR_AT = "at"
ATTR_COMMAND_ID = "command_id"


def _number(message: str) -> Callable[[Any], float]:
    """A validator of numbers that gives them as a float and refuses the rest with
    `message`.

    Templates hand numbers over as text: "24" is 24.0. A boolean is refused, which
    Python would count as 1: `true` is not a temperature or a brightness.
    """

    def number(value: Any) -> float:
        if isinstance(value, bool):
            raise probatio.Invalid(message)
        try:
            return float(value)
        except (TypeError, ValueError, OverflowError) as err:
            raise probatio.Invalid(message) from err

    return number


def _whole(message: str) -> Callable[[Any], int]:
    """A validator of whole numbers that gives them as an int and refuses the rest
    with `message`.

    A template gives an input_number as 15.0 or "15.0", and 30 / 2 is 15.0: those are
    whole and accepted. 2.5 is rejected rather than rounded.
    """
    number = _number(message)

    def whole(value: Any) -> int:
        if not (whole_value := number(value)).is_integer():
            raise probatio.Invalid(message)
        return int(whole_value)

    return whole


setting_number = _number("expected a number")
whole_minutes = _whole("expected a whole number of minutes")
whole_number = _whole("expected a whole number")

ADD_TIME_SCHEMA: VolDictType = {
    probatio.Required(ATTR_MINUTES): probatio.All(
        whole_minutes, probatio.Range(min=-MAX_MINUTES, max=MAX_MINUTES)
    )
}

SETTINGS_SCHEMA: VolDictType = {
    probatio.Optional("hvac_mode"): cv.string,
    probatio.Optional("temperature"): setting_number,
    probatio.Optional("fan_mode"): cv.string,
    probatio.Optional("preset_mode"): cv.string,
    probatio.Optional("mode"): cv.string,
    probatio.Optional("operation_mode"): cv.string,
    probatio.Optional("brightness_pct"): setting_number,
    probatio.Optional("percentage"): whole_number,
    probatio.Optional("humidity"): whole_number,
}
"""The ways to turn a target on that a service can ask for, as the services of the
target's domain name them. Which of them a target takes, and the values it accepts,
is for the target's own capabilities to decide (see `validate_settings`); this only
gives the values their types."""

RUN_SCHEMA: VolDictType = {
    probatio.Optional(ATTR_MINUTES): probatio.All(
        whole_minutes, probatio.Range(min=1, max=MAX_MINUTES)
    ),
    **SETTINGS_SCHEMA,
}


def _unquoted_yaml_action(value: Any) -> Any:
    """`on` and `off` as hand-written YAML gives them: Home Assistant reads YAML 1.1,
    where an unquoted `on` is the boolean true and `off` is false."""
    if isinstance(value, bool):
        return "on" if value else "off"
    return value


command_time: Final = probatio.All(cv.datetime, dt_util.as_utc)
"""The time a command is due at, as a service takes it and a voice agent's tool does.
A time without a zone, as the UI's date and time picker gives it, is the time on the
wall of the house: Home Assistant's own time zone. The result is in UTC."""

ADD_COMMAND_SCHEMA: VolDictType = {
    probatio.Required(ATTR_ACTION): probatio.All(
        _unquoted_yaml_action, probatio.In(["on", "off"])
    ),
    probatio.Optional(ATTR_DELAY): probatio.All(
        whole_minutes, probatio.Range(min=1, max=MAX_DELAY_MINUTES)
    ),
    probatio.Optional(ATTR_AT): command_time,
    probatio.Optional(ATTR_MINUTES): probatio.All(
        whole_minutes, probatio.Range(min=1, max=MAX_MINUTES)
    ),
    **SETTINGS_SCHEMA,
}
"""Which of `delay` and `at` is given is checked by the service itself, so that the
refusal is translated."""

CANCEL_COMMAND_SCHEMA: VolDictType = {probatio.Required(ATTR_COMMAND_ID): cv.string}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the services; they exist whether or not a timer is set up."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ADD_TIME,
        entity_domain=NUMBER_DOMAIN,
        schema=ADD_TIME_SCHEMA,
        func="async_add_time",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_RUN,
        entity_domain=NUMBER_DOMAIN,
        schema=RUN_SCHEMA,
        func="async_run",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_STOP,
        entity_domain=NUMBER_DOMAIN,
        schema={},
        func="async_stop",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ADD_COMMAND,
        entity_domain=NUMBER_DOMAIN,
        schema=ADD_COMMAND_SCHEMA,
        func="async_add_command",
        supports_response=SupportsResponse.OPTIONAL,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CANCEL_COMMAND,
        entity_domain=NUMBER_DOMAIN,
        schema=CANCEL_COMMAND_SCHEMA,
        func="async_cancel_command",
    )
