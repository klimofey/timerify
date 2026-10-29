"""Timerify's services: they act on the "Run for" numbers of timers.

An entity service targets entities, areas or devices; Home Assistant resolves the
target to the `number` entities this integration owns and calls the method named
here on each, so the service reaches the controller of every timer picked.
"""

from typing import Any

import probatio
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN, MAX_MINUTES

SERVICE_ADD_TIME = "add_time"
SERVICE_RUN = "run"

ATTR_MINUTES = "minutes"

_NOT_WHOLE = "expected a whole number of minutes"


def whole_minutes(value: Any) -> int:
    """A count of whole minutes, as an int.

    Templates hand numbers over as they were rendered: an input_number gives 15.0
    or "15.0", and 30 / 2 is 15.0. Those are whole and accepted; 2.5 is rejected
    rather than rounded, and so is a boolean, which Python would count as 1.
    """
    if isinstance(value, bool):
        raise probatio.Invalid(_NOT_WHOLE)
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as err:
        raise probatio.Invalid(_NOT_WHOLE) from err
    if not number.is_integer():
        raise probatio.Invalid(_NOT_WHOLE)
    return int(number)


ADD_TIME_SCHEMA: VolDictType = {
    probatio.Required(ATTR_MINUTES): probatio.All(
        whole_minutes, probatio.Range(min=-MAX_MINUTES, max=MAX_MINUTES)
    )
}


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
        schema=None,
        func="async_run",
    )
