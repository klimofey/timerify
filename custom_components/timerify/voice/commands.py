"""The handler that plans a command to turn a target on or off later."""

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any, ClassVar

import probatio
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import intent
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..controller import TimerifyConfigEntry, command_when
from ..services import command_time
from ..target import target_name
from .base import (
    PERCENT_SLOT,
    SETTING_SLOTS,
    TimerifyIntentHandler,
    clock_slots,
    duration_of,
    settings_of,
    timer_slots,
    whole_slot,
)


class DelayedCommandHandler(TimerifyIntentHandler):
    """Turn on the boiler in 15 minutes, turn it off in ten: a command that waits, or
    the countdown set to end then.

    A command to turn on is kept until it is due (P1), with the duration and settings it
    turns the target on with; it replaces the countdown when it runs, so it is
    destructive. One to turn off sets the countdown of a target that is wanted on to end
    then, and changes nothing for a target that is off (§6.4).
    """

    intent_type = "TimerifyDelayedCommand"
    tool_name = "timerify__delayed_command"
    title = "Plan a command for later"
    description = (
        "Plans to turn a device on or off later. 'action' is 'on' or 'off'. Say when"
        " with either a delay, 'delay_hours', 'delay_minutes' and 'delay_seconds'"
        " adding up to how long from now, or 'at', a date and time on the clock of the"
        " house such as '2026-01-05 10:30:00'; never both. A command to turn on is kept"
        " until it is due, and may say how long the device then runs, 'hours' and"
        " 'minutes' adding up to 1 minute to 24 hours, and the settings it is turned on"
        " with, as running a device does: 'hvac_mode', 'temperature', 'fan_mode',"
        " 'preset_mode', 'operation_mode', 'brightness_pct', 'percentage', 'humidity',"
        " and 'percent' and 'mode' for the device's own percentage and mode settings. A"
        " command to turn off sets the timer of a device that is on to end then, and"
        " changes nothing for a device that is off; it takes no 'hours', 'minutes' or"
        " settings. A command is planned at most 7 days ahead. 'name' is the name of"
        " the device, as the prompt lists it."
    )
    slot_schema: ClassVar[dict[Any, Any]] = {
        probatio.Required("name"): cv.string,
        probatio.Required("action"): probatio.In(["on", "off"]),
        probatio.Optional("delay_hours"): whole_slot,
        probatio.Optional("delay_minutes"): whole_slot,
        probatio.Optional("delay_seconds"): whole_slot,
        probatio.Optional("at"): cv.string,
        probatio.Optional("hours"): whole_slot,
        probatio.Optional("minutes"): whole_slot,
        **PERCENT_SLOT,
        **SETTING_SLOTS,
    }

    async def async_handle_timer(
        self,
        intent_obj: intent.Intent,
        entry: TimerifyConfigEntry,
        slots: Mapping[str, Any],
        response: intent.IntentResponse,
    ) -> None:
        hass = intent_obj.hass
        controller = entry.runtime_data
        when = command_when(_delay_of(slots), _clock_time_of(slots))
        duration = duration_of(slots)
        settings = settings_of(hass, entry, slots)
        if slots["action"]["value"] == "on":
            command_id = await controller.async_add_command(
                "on", when, duration, settings
            )
            # Nothing has been awaited since the command was kept, so it is still there.
            due = next(
                command.at
                for command in controller.snapshot.commands
                if command.id == command_id
            )
            response.async_set_speech_slots(
                {
                    "outcome": "command_added",
                    "target": target_name(hass, controller.target_entity_id),
                    **clock_slots(due, dt_util.utcnow()),
                }
            )
        elif await controller.async_turn_off_in(when, duration, settings):
            response.async_set_speech_slots(
                {"outcome": "timer_set", **timer_slots(hass, entry, dt_util.utcnow())}
            )
        else:
            response.async_set_speech_slots(
                {
                    "outcome": "not_running",
                    "target": target_name(hass, controller.target_entity_id),
                }
            )


def _delay_of(slots: Mapping[str, Any]) -> timedelta | None:
    """How long from now the slots `delay_hours`, `delay_minutes` and `delay_seconds`
    say together; None when none of them is given. A delay of nothing is a delay: the
    controller refuses it as a time that is not ahead."""
    delays = {
        unit: slots[f"delay_{unit}"]["value"]
        for unit in ("hours", "minutes", "seconds")
        if f"delay_{unit}" in slots
    }
    return timedelta(**delays) if delays else None


def _clock_time_of(slots: Mapping[str, Any]) -> datetime | None:
    """The moment the slot `at` says, in UTC; None when it is not given.

    Raises ServiceValidationError (`invalid_command_time`) for text that is not a date
    and a time.
    """
    if "at" not in slots:
        return None
    try:
        moment: datetime = command_time(slots["at"]["value"])
    except probatio.Invalid as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="invalid_command_time"
        ) from err
    return moment
