"""The handlers that ask about a timer, run it, extend it and stop it."""

from collections.abc import Mapping
from typing import Any, ClassVar

import probatio
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import intent
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..controller import TimerifyConfigEntry
from .base import (
    PERCENT_SLOT,
    SETTING_SLOTS,
    TimerifyIntentHandler,
    duration_of,
    settings_of,
    timer_slots,
    whole_slot,
)


class TimeLeftHandler(TimerifyIntentHandler):
    """How long is left on the boiler: the time left, and when the target turns off."""

    intent_type = "TimerifyTimeLeft"
    tool_name = "timerify__time_left"
    title = "Time left on a timer"
    description = (
        "Tells how long a device's Timerify timer has left and when the device turns"
        " off, or that the device is off or unavailable, or on without a timer. 'name'"
        " is the name of the device, as the prompt lists it."
    )
    read_only = True
    slot_schema: ClassVar[dict[Any, Any]] = {probatio.Required("name"): cv.string}

    async def async_handle_timer(
        self,
        intent_obj: intent.Intent,
        entry: TimerifyConfigEntry,
        slots: Mapping[str, Any],
        response: intent.IntentResponse,
    ) -> None:
        response.async_set_speech_slots(
            timer_slots(intent_obj.hass, entry, dt_util.utcnow())
        )


class RunHandler(TimerifyIntentHandler):
    """Turn on the boiler for 45 minutes: turn the target on, with the settings it
    takes, and count the time down. With a duration it replaces the countdown that was
    there, so it is destructive. Without one it is the bare turn-on of R9: a target
    that is off runs for the default duration (strict mode) or without a countdown
    (loose mode), and one that is wanted running keeps its countdown; either way the
    answer says how it stands."""

    intent_type = "TimerifyRun"
    tool_name = "timerify__run"
    title = "Run a device for a while"
    description = (
        "Turns a device on and runs its Timerify timer: the device turns off by itself"
        " when the time is up. 'hours' and 'minutes' add up to how long, from 1 minute"
        " to 24 hours; give neither to turn a device that is off on for its usual"
        " time, or without a timer, while a device that is already running keeps its"
        " timer and the result says how long is left. Settings are optional, and a"
        " device takes only its own: 'hvac_mode' and 'temperature' of a thermostat,"
        " 'fan_mode' of a thermostat, 'preset_mode' of a fan, 'operation_mode' and"
        " 'temperature' of a water heater, 'brightness_pct' of a light, 'percentage'"
        " of a fan, 'humidity' and 'mode' of a humidifier. 'percent' stands for the"
        " device's own percentage setting (brightness, speed or humidity), and 'mode'"
        " for its own mode setting (the fan mode of a thermostat, the preset of a fan,"
        " the mode of a humidifier or the operation mode of a water heater). 'name' is"
        " the name of the device, as the prompt lists it."
    )
    slot_schema: ClassVar[dict[Any, Any]] = {
        probatio.Required("name"): cv.string,
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
        await entry.runtime_data.async_run(
            duration_of(slots), settings_of(hass, entry, slots)
        )
        response.async_set_speech_slots(timer_slots(hass, entry, dt_util.utcnow()))


class AddTimeHandler(TimerifyIntentHandler):
    """30 more minutes on the boiler: move the end of the countdown, or start it. It
    only adds, so it is not destructive."""

    intent_type = "TimerifyAddTime"
    tool_name = "timerify__add_time"
    title = "Add time to a timer"
    description = (
        "Adds time to a device's Timerify timer: 'hours' and 'minutes' add up to the"
        " time to add, at least 1 minute. A running timer ends later; a device that is"
        " not running is turned on for that time. A timer never runs for more than 24"
        " hours from now, however much is added. 'name' is the name of the device, as"
        " the prompt lists it."
    )
    destructive = False
    slot_schema: ClassVar[dict[Any, Any]] = {
        probatio.Required("name"): cv.string,
        probatio.Optional("hours"): whole_slot,
        probatio.Optional("minutes"): whole_slot,
    }

    async def async_handle_timer(
        self,
        intent_obj: intent.Intent,
        entry: TimerifyConfigEntry,
        slots: Mapping[str, Any],
        response: intent.IntentResponse,
    ) -> None:
        # Time to add is asked for in the slots; without any there is nothing to add.
        if not (minutes := duration_of(slots)):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_time_to_add"
            )
        await entry.runtime_data.async_add_minutes(minutes)
        response.async_set_speech_slots(
            timer_slots(intent_obj.hass, entry, dt_util.utcnow())
        )


class StopHandler(TimerifyIntentHandler):
    """Stop the boiler timer: the countdown goes to zero and the target is turned off
    (R2). Stopping again changes nothing more."""

    intent_type = "TimerifyStop"
    tool_name = "timerify__stop"
    title = "Stop a timer"
    description = (
        "Stops a device's Timerify timer and turns the device off. 'name' is the name"
        " of the device, as the prompt lists it."
    )
    idempotent = True
    slot_schema: ClassVar[dict[Any, Any]] = {probatio.Required("name"): cv.string}

    async def async_handle_timer(
        self,
        intent_obj: intent.Intent,
        entry: TimerifyConfigEntry,
        slots: Mapping[str, Any],
        response: intent.IntentResponse,
    ) -> None:
        await entry.runtime_data.async_set_minutes(0)
        response.async_set_speech_slots(
            timer_slots(intent_obj.hass, entry, dt_util.utcnow())
        )
