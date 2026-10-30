"""The handlers that ask about a timer, or run it."""

from typing import Any, ClassVar

import probatio
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import intent
from homeassistant.util import dt as dt_util

from ..controller import TimerifyConfigEntry
from .base import TimerifyIntentHandler, timer_slots


class TimeLeftHandler(TimerifyIntentHandler):
    """How long is left on the boiler: the time left, and when the target turns off."""

    intent_type = "TimerifyTimeLeft"
    tool_name = "timerify__time_left"
    title = "Time left on a timer"
    description = (
        "Tells how long a device's Timerify timer has left and when the device turns"
        " off, or that the device is off, or on without a timer. 'name' is the name of"
        " the device, as the prompt lists it."
    )
    read_only = True
    slot_schema: ClassVar[dict[Any, Any]] = {probatio.Required("name"): cv.string}

    async def async_handle_timer(
        self,
        intent_obj: intent.Intent,
        entry: TimerifyConfigEntry,
        response: intent.IntentResponse,
    ) -> None:
        response.async_set_speech_slots(
            timer_slots(intent_obj.hass, entry, dt_util.utcnow())
        )
