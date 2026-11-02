"""The handlers that plan a command to turn a target on or off later, list the commands
that are planned, and cancel them."""

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any, ClassVar, Final, Literal

import probatio
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import intent
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..controller import TimerifyConfigEntry, command_when
from ..core import Command
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
        " with either a delay, 'delay_weeks', 'delay_days', 'delay_hours',"
        " 'delay_minutes' and 'delay_seconds' adding up to how long from now, or 'at',"
        " a date and time on the clock of the house such as '2026-01-05 10:30:00';"
        " never both. A command to turn on is kept"
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
        probatio.Optional("delay_weeks"): whole_slot,
        probatio.Optional("delay_days"): whole_slot,
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


_UNIT_SECONDS: Final = {
    "weeks": 7 * 86400,
    "days": 86400,
    "hours": 3600,
    "minutes": 60,
    "seconds": 1,
}
_LONGEST_DELAY_SECONDS: Final = timedelta.max // timedelta(seconds=1)


def _delay_of(slots: Mapping[str, Any]) -> timedelta | None:
    """How long from now the slots `delay_weeks`, `delay_days`, `delay_hours`,
    `delay_minutes` and `delay_seconds` say together; None when none of them is given.
    A delay of nothing is a delay: the controller refuses it as a time that is not
    ahead.

    A count that no `timedelta` can hold is the longest one that can be: longer than
    any the controller takes, which refuses it as too far.
    """
    seconds = [
        slots[f"delay_{unit}"]["value"] * factor
        for unit, factor in _UNIT_SECONDS.items()
        if f"delay_{unit}" in slots
    ]
    if not seconds:
        return None
    return timedelta(seconds=min(sum(seconds), _LONGEST_DELAY_SECONDS))


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


def command_slots(command: Command, now: datetime) -> dict[str, Any]:
    """What an answer says about a planned command: its `id`, its `action` (`on` or
    `off`), when it is due as `at` and `in_days` (see `clock_slots`), how many `minutes`
    an "on" then runs (None when it has no time of its own), and the `settings` it turns
    the target on with, which an answer does not speak and an LLM is given."""
    return {
        "id": command.id,
        "action": command.action,
        **clock_slots(command.at, now),
        "minutes": command.minutes,
        "settings": dict(command.settings),
    }


class ListCommandsHandler(TimerifyIntentHandler):
    """What is planned for the boiler: the commands that wait for their time, in the
    order they are due. A query, which changes nothing."""

    intent_type = "TimerifyListCommands"
    tool_name = "timerify__list_commands"
    title = "List planned commands"
    description = (
        "Lists the commands planned for a device that has a Timerify timer, in the"
        " order they are due. Each has an 'id' to cancel it by, whether it turns the"
        " device 'on' or 'off', when it is due ('at' is the time of day on the clock of"
        " the house and 'in_days' the number of dates from today, 0 for today), for how"
        " many 'minutes' a command to turn on then runs (none when it has no time of"
        " its own), and the 'settings' it turns the device on with. 'name' is the name"
        " of the device, as the prompt lists it."
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
        controller = entry.runtime_data
        now = dt_util.utcnow()
        commands = controller.snapshot.commands
        response.async_set_speech_slots(
            {
                "target": target_name(intent_obj.hass, controller.target_entity_id),
                "count": len(commands),
                "commands": [command_slots(command, now) for command in commands],
            }
        )


class CancelCommandsHandler(TimerifyIntentHandler):
    """Cancel the planned commands of the boiler: every one, or the next, or one by its
    id (an LLM has the ids; a voice cannot say one). A cancelled command never runs
    (P2). It is destructive and not idempotent: the same call for "the next" cancels
    another command each time, and a command is a promise."""

    intent_type = "TimerifyCancelCommands"
    tool_name = "timerify__cancel_commands"
    title = "Cancel planned commands"
    description = (
        "Cancels commands planned for a device that has a Timerify timer, so that they"
        " never run. 'which' is 'all' to cancel every planned command or 'next' to"
        " cancel only the one that is due first; it defaults to 'all'. 'command_id'"
        " cancels the one command with that id instead, as the list of planned commands"
        " gives it, and then 'which' is not used. Asking for 'next' again cancels the"
        " command after it. 'name' is the name of the device, as the prompt lists it."
    )
    slot_schema: ClassVar[dict[Any, Any]] = {
        probatio.Required("name"): cv.string,
        probatio.Optional("which"): probatio.In(["next", "all"]),
        probatio.Optional("command_id"): cv.string,
    }

    async def async_handle_timer(
        self,
        intent_obj: intent.Intent,
        entry: TimerifyConfigEntry,
        slots: Mapping[str, Any],
        response: intent.IntentResponse,
    ) -> None:
        controller = entry.runtime_data
        said: Literal["next", "all", "id"]
        cancelled: tuple[Command, ...]
        if "command_id" in slots:
            said = "id"
            cancelled = (
                await controller.async_cancel_command(slots["command_id"]["value"]),
            )
        else:
            which: Literal["next", "all"] = slots.get("which", {}).get("value", "all")
            said = which
            cancelled = await controller.async_cancel_commands(which)
        now = dt_util.utcnow()
        response.async_set_speech_slots(
            {
                "target": target_name(intent_obj.hass, controller.target_entity_id),
                "which": said,
                "cancelled": len(cancelled),
                "commands": [command_slots(command, now) for command in cancelled],
            }
        )
