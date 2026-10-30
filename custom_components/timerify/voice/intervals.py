"""The handler that switches the schedule of a timer on and off."""

from collections.abc import Mapping
from typing import Any, ClassVar

import probatio
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import intent

from ..controller import TimerifyConfigEntry
from ..target import target_name
from .base import TimerifyIntentHandler


class SetScheduleHandler(TimerifyIntentHandler):
    """Turn off the boiler schedule, turn on its Morning schedule: every interval of the
    timer's schedule, or the ones with a title, switched as their own switches are. The
    same call again changes nothing more, so it is idempotent."""

    intent_type = "TimerifySetSchedule"
    tool_name = "timerify__set_schedule"
    title = "Switch a schedule on or off"
    description = (
        "Switches the weekly schedule of a device that has a Timerify timer on or off."
        " 'enabled' is true to let the schedule run the device at the times of its"
        " intervals, false to skip them: switching off while an interval is running"
        " stops the timer, and switching on during an interval's time runs the device"
        " for the rest of it. Give 'interval', the title of an interval, to switch only"
        " that one; without it every interval of the schedule is switched. 'name' is"
        " the name of the device, as the prompt lists it."
    )
    idempotent = True
    slot_schema: ClassVar[dict[Any, Any]] = {
        probatio.Required("name"): cv.string,
        probatio.Required("enabled"): cv.boolean,
        probatio.Optional("interval"): cv.string,
    }

    async def async_handle_timer(
        self,
        intent_obj: intent.Intent,
        entry: TimerifyConfigEntry,
        slots: Mapping[str, Any],
        response: intent.IntentResponse,
    ) -> None:
        controller = entry.runtime_data
        enabled: bool = slots["enabled"]["value"]
        asked = slots.get("interval", {}).get("value")
        titles = await controller.async_set_schedule_enabled(enabled, asked)
        response.async_set_speech_slots(
            {
                "target": target_name(intent_obj.hass, controller.target_entity_id),
                "enabled": enabled,
                # The title as the interval has it, not as it was said.
                "interval": None if asked is None else titles[0],
                "count": len(titles),
            }
        )
