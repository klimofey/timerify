"""The handlers that plan a command to turn a target on or off later, list the commands
that are planned, and cancel them."""

from collections.abc import Mapping
from datetime import datetime, time, timedelta, tzinfo
from typing import Any, ClassVar, Final, Literal, override

import probatio
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import intent
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..controller import TimerifyConfigEntry, command_when
from ..core import Command
from ..schedule import wall_moments
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

    def when(self, slots: Mapping[str, Any]) -> datetime | timedelta:
        """When the command is due, from the slots: how long from now, or a moment.

        Raises ServiceValidationError (`delay_or_at`) for both and for neither.
        """
        return command_when(_delay_of(slots), _clock_time_of(slots))

    async def async_handle_timer(
        self,
        intent_obj: intent.Intent,
        entry: TimerifyConfigEntry,
        slots: Mapping[str, Any],
        response: intent.IntentResponse,
    ) -> None:
        hass = intent_obj.hass
        controller = entry.runtime_data
        when = self.when(slots)
        duration = duration_of(slots)
        settings = settings_of(hass, entry, slots)
        if slots["action"]["value"] == "on":
            command_id = await controller.async_add_command(
                "on", when, duration, settings, context=intent_obj.context
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
        elif (
            end := await controller.async_turn_off_in(
                when, duration, settings, context=intent_obj.context
            )
        ) is not None:
            # The end the call set, not the timer's: a call that waited behind a slow
            # device may find it passed, and the answer must still name it.
            now = dt_util.utcnow()
            clock = clock_slots(end, now)
            response.async_set_speech_slots(
                {
                    "outcome": "timer_set",
                    **timer_slots(hass, entry, now),
                    "ends_at": clock["at"],
                    "ends_in_days": clock["in_days"],
                }
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


type WindowPart = Literal["am", "pm", "afternoon", "evening", "night"]
"""What a speaker says with an hour of the twelve-hour clock to tell its two times
apart: "am" or the word for the morning, "pm" ("pm" is the half of the clock from noon),
and the words for the afternoon, the evening and the night. Each has a window of half a
day (`_WINDOW_START`) and picks the time of the hour that is in it."""

type DayPart = WindowPart | Literal["tonight"]
"""What the slot `clock_part` says: a part of the day with a window, or "tonight". It is
the night of today, so `ClockCommandHandler` reads it as the night with the day word
"today", and it has no window of its own."""

_HALF_DAY: Final = 12
_WINDOW_START: Final[Mapping[WindowPart, int]] = {
    "am": 0,
    "pm": 12,
    "afternoon": 11,
    "evening": 13,
    "night": 18,
}
"""The hour at which the window of a part of the day starts on its date. A window lasts
half a day, so it holds exactly one of the two times that an hour of the dial means. The
evening runs to 01:00 of the next date, and the night to 06:00 of it."""


def _moments_in_windows(
    now: datetime,
    zone: tzinfo,
    hour: int,
    minute: int,
    part: WindowPart,
    day: int | None,
    before: int,
) -> list[datetime]:
    """The moments, earliest first, that a clock time said with `part` can mean: its
    dial time in each window the day word allows.

    The dial, less `before`, tells a time of the twelve-hour clock whatever the hour is.
    A window of twelve hours holds that time once, so there is one moment a window, and
    its wall time is the start of the window plus how far the dial is past it. With a
    day word the window is that of the day named. With "today", and with no day word,
    the window of the day before counts too, while its moment is ahead: a night that
    began yesterday is in progress in the small hours. The window of tomorrow is the
    last that can matter when there is no day word, since it starts after `now`.
    """
    today = now.astimezone(zone).date()
    start = _WINDOW_START[part] * 60
    inside = (hour * 60 + minute - before - start) % (_HALF_DAY * 60)
    named = 0 if day is None else day
    first = named - 1 if named == 0 else named
    last = 1 if day is None else named
    moments: list[datetime] = []
    for offset in range(first, last + 1):
        wall = datetime.combine(today + timedelta(days=offset), time()) + timedelta(
            minutes=start + inside
        )
        moments += [
            moment
            for moment in wall_moments(wall.date(), wall.time(), zone)
            if offset >= named or moment > now
        ]
    return moments


def _moments_on_dates(
    now: datetime,
    zone: tzinfo,
    hour: int,
    minute: int,
    day: int | None,
    zero: bool,
    before: int,
) -> list[datetime]:
    """The moments that a clock time said with no part of the day can mean, in the
    order they are preferred: by time, but for a bare 12 with a day word, whose reading
    as noon comes before the one as midnight.

    An hour from 1 to 12 with no zero is read as its morning and its evening time. Any
    other hour is the one of the 24-hour clock. The minutes before are taken off the
    wall time of each reading on its date, so with no day word three dates are searched,
    today, tomorrow and the day after, and with one the named date and the one after it,
    of which a reading is kept when, with the minutes off, it is on the named day.
    """
    today = now.astimezone(zone).date()
    bare = not zero and 1 <= hour <= _HALF_DAY
    hours = (hour % _HALF_DAY, hour % _HALF_DAY + _HALF_DAY) if bare else (hour,)
    noon_first = bare and hour == _HALF_DAY and day is not None
    dates_ahead = (0, 1, 2) if day is None else (day, day + 1)
    walls = (
        (
            h,
            datetime.combine(today + timedelta(days=ahead), time(h, minute))
            - timedelta(minutes=before),
        )
        for h in hours
        for ahead in dates_ahead
    )
    readings = [
        (h, moment)
        for h, wall in walls
        if day is None or (wall.date() - today).days == day
        for moment in wall_moments(wall.date(), wall.time(), zone)
    ]

    def preference(reading: tuple[int, datetime]) -> tuple[bool, datetime]:
        """The midnight reading after the others when noon is preferred, and then the
        earliest moment."""
        read_as, moment = reading
        return (noon_first and read_as == 0, moment)

    return [moment for _, moment in sorted(readings, key=preference)]


def clock_moment(
    now: datetime,
    zone: tzinfo,
    hour: int,
    minute: int,
    part: WindowPart | None,
    day: int | None,
    *,
    zero: bool = False,
    before: int = 0,
) -> datetime:
    """The moment, in UTC, that a clock time said at `now` means on the wall clock of
    `zone`; `day` is the day word said with it, in days from today, or None; `zero` is
    whether the hour was written with a leading zero ("07"); `before` is the minutes
    said to be before it ("quarter to 8" is the hour 8 and 15 before).

    An hour of the twelve-hour clock means two times, twelve hours apart, and the
    minutes before are taken off both: "quarter to 12" is 11:45 or 23:45. A part of the
    day picks the one inside its window (`_WINDOW_START`), whatever the hour is, so it
    wins over a zero and over the hours 13 to 23: "quarter to 12 in the morning" is
    11:45, "at 11 in the afternoon" is 11:00, and "this evening at 12" is the midnight
    that ends today. A window lasts twelve hours, so exactly one of the two times is in
    it, and the function has no case it refuses. With a day word the window is that of
    the day named: "tomorrow night" runs from 18:00 tomorrow to 06:00 the day after.
    With "today", and with no day word, the night in progress counts too while its
    moment is ahead (`_moments_in_windows`). Without a day word the next moment ahead
    in any window is taken.

    With no part of the day, an hour from 1 to 12 with no zero is the nearer of its
    morning and evening times that is ahead; any other hour is that of the 24-hour
    clock, and a zero says it as the hour 0 and the hours 13 to 23 do, so "07:30" is the
    morning one. Without a day word the time is the next one, today or tomorrow, and a
    time equal to `now` is tomorrow's. With one it is on that date, and the earlier of
    the times an hour can mean is taken unless it has passed today and the other has
    not. A bare 12 is the exception: it is noon, and midnight only once noon has passed,
    so "tomorrow at 12:30" is 12:30 and "today at quarter to 12" is 11:45, or 23:45 once
    11:45 has passed (`_moments_on_dates`).

    A time that has passed is returned as it is, on the date the speaker named: the
    controller refuses it (`command_in_past`). It is not refused here, for a
    `probatio.Invalid` from a sentence's slots is turned by `intent.async_handle` into
    an `InvalidSlotInfo`, which the agent speaks in English whatever the language.

    The wall time, once the minutes are off, follows `schedule.wall_moment`: a time the
    clock skips happens later by the gap, so "quarter to 3" on the night the clock
    goes from 02:00 to 03:00 is 03:45. A time the clock repeats happens twice, and of
    its two moments the earliest that is ahead is taken, so "1:30" said at 01:45 in the
    first pass of the night is the second 01:30.
    """
    if part is None:
        moments = _moments_on_dates(now, zone, hour, minute, day, zero, before)
    else:
        moments = _moments_in_windows(now, zone, hour, minute, part, day, before)
    return next((moment for moment in moments if moment > now), moments[0])


def _written_with_a_zero(hour: Mapping[str, Any]) -> bool:
    """Whether the hour slot was matched from text with a leading zero: "07", "007".

    The built-in agent gives a number it matched from digits as its `value` and the
    characters it matched as its `text`, and the value is the same for "7" and "07".
    An hour said in words, or a slot with no text (a caller that is not a sentence),
    has no zero.
    """
    text = str(hour.get("text", "")).strip()
    return len(text) > 1 and text.startswith("0")


class ClockCommandHandler(DelayedCommandHandler):
    """Turn on the boiler at 7:30, turn it off at 23:00: the command of a delayed
    command, at a time of day.

    It is for the sentences of the built-in agent only, which say the time with
    `clock_hour`, `clock_minute`, `clock_part` and `clock_day` as a person says it. An
    LLM agent has no such tool (`offered_as_tool`): the tool of the delayed command
    takes `at`, a moment, and these slots would only confuse a model. The rest is the
    delayed command's.

    An hour written with a leading zero, "07:30", is on the 24-hour clock, as the hour
    0 and the hours 13 to 23 are: the text of the slot tells it from "7:30", whose hour
    is the nearer of its two times. A part of the day, "07:30 pm", still wins.

    "Noon" is the afternoon and "midnight" the evening, each with no hour, the hour
    being 12: that is not the bare 12 of "at 12", which is the nearer of the two, or
    noon when a day word is said.

    The slot a sentence fills is the direction of the minutes, so that no word of any
    language is known here. `clock_minute` counts minutes after the hour ("half past 7"
    is the hour 7 and 30) and `clock_before` minutes before it ("quarter to 8" is the
    hour 8 and 15 before); they are not said together. The minutes are worked out on the
    dial, and the part of the day picks which of the two times they make
    (`clock_moment`), so "quarter to 8 in the evening" is 19:45, "quarter to 12 in the
    morning" is 11:45 and "quarter to midnight", whose hour is 12, is 23:45.

    `clock_ordinal` is an ordinal hour, as in the Russian "v polovine vos'mogo" (half
    past 7, literally "at the half of the eighth"): the Nth hour is the one that runs
    from N-1 to N, so it is the hour N-1, with 0 read as 12. It stands instead of
    `clock_hour`, and minutes before are not said with it.

    The part "tonight" is the night with today named: "tonight at 7" is 19:00 today,
    and "tonight at 2" is the 02:00 that follows today.

    A part of the day has a window that picks the time (`clock_moment`), and the window
    of the evening and of the night runs past midnight. So with a day word, midnight
    and the small hours said with "night" are in the night that follows that day:
    "tomorrow at midnight" and "tomorrow night at 12" are the 00:00 after tomorrow,
    "tomorrow at 2 at night" is the 02:00 after it, and "today at 2 at night" is the
    coming 02:00: the night in progress when it is said in the small hours and that
    moment is still ahead, else the next night's. "Am" says a half of the clock, not a
    night: "tomorrow at 2 am" is 02:00 tomorrow.
    """

    intent_type = "TimerifyCommandAt"
    tool_name = "timerify__clock_command"
    title = "Plan a command for a time of day"
    description = (
        "Plans to turn a device on or off at a time of day, said as a person says it:"
        " 'clock_hour' (0 to 23, or 1 to 12 with 'clock_part'), 'clock_minute' (0 to"
        " 59, the minutes after the hour), 'clock_before' (1 to 59, the minutes before"
        " the hour, not with 'clock_minute'), 'clock_ordinal' (1 to 12, the hour that"
        " ends the time, instead of 'clock_hour'), 'clock_part' ('am', 'pm',"
        " 'afternoon', 'evening', 'night' or 'tonight', the night of today) and"
        " 'clock_day' (0 for today, 1 for tomorrow, 2 for the day after). Only the"
        " sentences of the built-in agent say a time so;"
        " a model plans a command at a time of day with the tool of the delayed"
        " command, which takes 'at'. 'name', 'action', 'hours', 'minutes' and the"
        " settings are those of that tool."
    )
    offered_as_tool = False
    slot_schema: ClassVar[dict[Any, Any]] = {
        probatio.Required("name"): cv.string,
        probatio.Required("action"): probatio.In(["on", "off"]),
        probatio.Optional("clock_hour"): probatio.All(
            whole_slot, probatio.Range(min=0, max=23)
        ),
        probatio.Optional("clock_minute"): probatio.All(
            whole_slot, probatio.Range(min=0, max=59)
        ),
        probatio.Optional("clock_before"): probatio.All(
            whole_slot, probatio.Range(min=1, max=59)
        ),
        probatio.Optional("clock_ordinal"): probatio.All(
            whole_slot, probatio.Range(min=1, max=12)
        ),
        probatio.Optional("clock_part"): probatio.In(
            ["am", "pm", "afternoon", "evening", "night", "tonight"]
        ),
        probatio.Optional("clock_day"): probatio.In([0, 1, 2]),
        probatio.Optional("hours"): whole_slot,
        probatio.Optional("minutes"): whole_slot,
        **PERCENT_SLOT,
        **SETTING_SLOTS,
    }

    @override
    def when(self, slots: Mapping[str, Any]) -> datetime | timedelta:
        """The moment the clock slots say, on the clock of the house.

        Raises `probatio.Invalid` for slots that no sentence makes, which only a caller
        that is not a sentence can send: a time with no hour that is not noon (the
        afternoon) or midnight (the evening) with no minutes after it, an ordinal hour
        with an hour or with minutes before, and minutes before with minutes after.
        """
        part: DayPart | None = slots.get("clock_part", {}).get("value")
        day = slots.get("clock_day", {}).get("value")
        hour_slot = slots.get("clock_hour", {})
        hour = hour_slot.get("value")
        zero = _written_with_a_zero(hour_slot)
        minute = slots.get("clock_minute", {}).get("value")
        before = slots.get("clock_before", {}).get("value", 0)
        ordinal = slots.get("clock_ordinal", {}).get("value")
        if part == "tonight":
            part = "night"
            day = 0 if day is None else day
        if ordinal is not None and (hour is not None or before):
            raise probatio.Invalid("an ordinal hour is said with no other hour")
        if before and minute is not None:
            raise probatio.Invalid("minutes are before the hour or after it, not both")
        if ordinal is not None:
            # The Nth hour is the one that runs from N-1 to N.
            hour = ordinal - 1 or _HALF_DAY
        if hour is None:
            if part not in ("afternoon", "evening") or minute is not None:
                raise probatio.Invalid("expected an hour, or noon or midnight")
            hour = _HALF_DAY
        now = dt_util.utcnow()
        zone = dt_util.get_default_time_zone()
        minute = 0 if minute is None else minute
        return clock_moment(
            now, zone, hour, minute, part, day, zero=zero, before=before
        )


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
                await controller.async_cancel_command(
                    slots["command_id"]["value"], context=intent_obj.context
                ),
            )
        else:
            which: Literal["next", "all"] = slots.get("which", {}).get("value", "all")
            said = which
            cancelled = await controller.async_cancel_commands(
                which, context=intent_obj.context
            )
        now = dt_util.utcnow()
        response.async_set_speech_slots(
            {
                "target": target_name(intent_obj.hass, controller.target_entity_id),
                "which": said,
                "cancelled": len(cancelled),
                "commands": [command_slots(command, now) for command in cancelled],
            }
        )
