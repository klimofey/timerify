"""Timerify's services: they act on the "Run for" numbers of timers.

An entity service targets entities, areas or devices; Home Assistant resolves the
target to the `number` entities this integration owns and calls the method named
here on each, so the service reaches the controller of every timer picked.
"""

from collections.abc import Callable
from typing import Any

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
SERVICE_ADD_COMMAND = "add_command"
SERVICE_CANCEL_COMMAND = "cancel_command"

ATTR_MINUTES = "minutes"
ATTR_ACTION = "action"
ATTR_DELAY = "delay"
ATTR_AT = "at"
ATTR_COMMAND_ID = "command_id"


def _whole(message: str) -> Callable[[Any], int]:
    """A validator of whole numbers that gives them as an int and refuses the rest
    with `message`.

    Templates hand numbers over as they were rendered: an input_number gives 15.0
    or "15.0", and 30 / 2 is 15.0. Those are whole and accepted; 2.5 is rejected
    rather than rounded, and so is a boolean, which Python would count as 1.
    """

    def whole(value: Any) -> int:
        if isinstance(value, bool):
            raise probatio.Invalid(message)
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as err:
            raise probatio.Invalid(message) from err
        if not number.is_integer():
            raise probatio.Invalid(message)
        return int(number)

    return whole


whole_minutes = _whole("expected a whole number of minutes")
whole_number = _whole("expected a whole number")

ADD_TIME_SCHEMA: VolDictType = {
    probatio.Required(ATTR_MINUTES): probatio.All(
        whole_minutes, probatio.Range(min=-MAX_MINUTES, max=MAX_MINUTES)
    )
}

SETTINGS_SCHEMA: VolDictType = {
    probatio.Optional("hvac_mode"): cv.string,
    probatio.Optional("temperature"): probatio.Coerce(float),
    probatio.Optional("fan_mode"): cv.string,
    probatio.Optional("preset_mode"): cv.string,
    probatio.Optional("mode"): cv.string,
    probatio.Optional("operation_mode"): cv.string,
    probatio.Optional("brightness_pct"): probatio.Coerce(float),
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

ADD_COMMAND_SCHEMA: VolDictType = {
    probatio.Required(ATTR_ACTION): probatio.In(["on", "off"]),
    probatio.Optional(ATTR_DELAY): probatio.All(
        whole_minutes, probatio.Range(min=1, max=MAX_DELAY_MINUTES)
    ),
    # A time without a zone, as the UI's date and time picker gives it, is the time
    # on the wall of the house: Home Assistant's own time zone.
    probatio.Optional(ATTR_AT): probatio.All(cv.datetime, dt_util.as_utc),
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
