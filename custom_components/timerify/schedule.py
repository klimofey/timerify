"""Schedule intervals: how one is named for the user, and when its windows fall.

An interval is a weekly pattern on the wall clock; a window is one occurrence of it,
worked out in the time zone of Home Assistant, which is why a window follows the clock
through a change to or from summer time and an interval that crosses midnight belongs
to the day it starts on.
"""

from collections.abc import Awaitable, Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from typing import Any, Final

from hassil.util import remove_punctuation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import WEEKDAYS

from .const import (
    CONF_DAYS,
    CONF_END,
    CONF_SETTINGS,
    CONF_START,
    CONF_WEEKDAYS,
    MAX_MINUTES,
    WINDOW_SEARCH_DAYS,
    DaysMode,
    Settings,
    freeze_settings,
)
from .core import Window

_WEEK: Final = len(WEEKDAYS)
_MIN_RANGE: Final = 3
"""The fewest consecutive days written as a range: Mon–Wed, not Mon, Tue, Wed."""


@dataclass(frozen=True)
class Interval:
    """A schedule interval as its subentry holds it: the days it runs on, when it
    begins and ends on the wall clock, and what the target is turned on with."""

    id: str
    """The id of the subentry."""
    days: DaysMode
    weekdays: frozenset[str]
    """The `homeassistant.const.WEEKDAYS` names of the days it runs on."""
    start: time
    end: time
    """When it ends; not after `start` for an interval that crosses midnight."""
    settings: Settings

    @classmethod
    def from_subentry(cls, subentry: ConfigSubentry) -> Interval:
        """Read the interval a subentry of the interval flow holds."""
        data = subentry.data
        return cls(
            id=subentry.subentry_id,
            days=data[CONF_DAYS],
            weekdays=frozenset(data[CONF_WEEKDAYS]),
            start=time.fromisoformat(data[CONF_START]),
            end=time.fromisoformat(data[CONF_END]),
            settings=freeze_settings(data[CONF_SETTINGS]),
        )


def window_on(interval: Interval, day: date, zone: tzinfo) -> Window | None:
    """The occurrence of `interval` that starts on `day` on the wall clock of `zone`;
    None when the change of the clock swallows it.

    It ends the next day when the interval ends at or before its start, and never lasts
    longer than `MAX_MINUTES`. A wall time that does not exist on a day the clock goes
    forward lands later by the length of the gap (02:30 becomes 03:30); one that comes
    twice when it goes back is its first time.
    """
    ends_on = day + timedelta(days=1) if interval.end <= interval.start else day
    start = datetime.combine(day, interval.start, zone).astimezone(UTC)
    end = datetime.combine(ends_on, interval.end, zone).astimezone(UTC)
    end = min(end, start + timedelta(minutes=MAX_MINUTES))
    if end <= start:
        return None
    return Window(interval.id, start, end, interval.settings)


def days_around(now: datetime, zone: tzinfo) -> Iterator[date]:
    """The days on which a window that is open at `now`, or starts within
    `WINDOW_SEARCH_DAYS`, can start: yesterday, which an interval across midnight
    started on, today and every day ahead, in `zone`."""
    today = now.astimezone(zone).date()
    for ahead in range(-1, WINDOW_SEARCH_DAYS + 1):
        yield today + timedelta(days=ahead)


def weekday_window(interval: Interval, now: datetime, zone: tzinfo) -> Window | None:
    """The window of `interval` that is open at `now` or comes next, on the weekdays it
    names; None when there is none within `WINDOW_SEARCH_DAYS`."""
    for day in days_around(now, zone):
        if WEEKDAYS[day.weekday()] not in interval.weekdays:
            continue
        window = window_on(interval, day, zone)
        if window is not None and window.end > now:
            return window
    return None


async def workday_window(
    interval: Interval,
    now: datetime,
    zone: tzinfo,
    is_workday: Callable[[date], Awaitable[bool]],
) -> Window | None:
    """The window of `interval` that is open at `now` or comes next, on the days that
    `is_workday` calls working days if the interval runs on those, on the others if it
    runs on the days off; None when there is none within `WINDOW_SEARCH_DAYS`.

    Only a day whose window has not ended is asked about. Whatever `is_workday` raises
    ends the search: the interval's window is not known then.
    """
    wanted = interval.days == "workdays"
    for day in days_around(now, zone):
        window = window_on(interval, day, zone)
        if window is None or window.end <= now:
            continue
        if await is_workday(day) == wanted:
            return window
    return None


def interval_title(data: Mapping[str, Any], labels: Mapping[str, str]) -> str:
    """The name of an interval: its times and its days, as `06:30–07:15, Sun–Thu`.

    `labels` gives the words of the user's language: the short name of each weekday
    by its `homeassistant.const.WEEKDAYS` name, and of the working and the other days
    by their `DaysMode`.
    """
    days: DaysMode = data[CONF_DAYS]
    label = (
        _weekdays_label(data[CONF_WEEKDAYS], labels)
        if days == "weekdays"
        else labels[days]
    )
    return f"{data[CONF_START]}–{data[CONF_END]}, {label}"


_DASHES: Final = str.maketrans(
    dict.fromkeys(
        "\N{HYPHEN}\N{NON-BREAKING HYPHEN}"
        "\N{FIGURE DASH}\N{EN DASH}\N{EM DASH}\N{HORIZONTAL BAR}\N{MINUS SIGN}",
        "-",
    )
)
"""Every dash that a title may be written with, as the hyphen a keyboard has."""
_YO: Final = "\N{CYRILLIC SMALL LETTER IO}"
_YE: Final = "\N{CYRILLIC SMALL LETTER IE}"
"""Russian prints the one for the other, and a speech recogniser does not tell them
apart."""


def title_key(title: str) -> str:
    """What the titles of intervals are compared by when one is meant by what was said
    or typed: the title as the built-in agent hears it, without punctuation and case,
    with the differences that a keyboard or a speech recogniser does not carry made
    none. Every dash is a hyphen, a Russian "yo" is a "ye", and a run of space is one
    space. So `Morning!` is meant by "morning", the `06:30–07:15, Mon–Sun` that an
    interval is titled by when it is made by `06:30-07:15, Mon-Sun`, and two intervals
    that carry the same title are meant together.

    A title of nothing but punctuation has the key `""`, which is no title at all: the
    built-in agent does not know it either.
    """
    unpunctuated = remove_punctuation(title).translate(_DASHES)
    return " ".join(unpunctuated.casefold().replace(_YO, _YE).split())


def _weekdays_label(weekdays: list[str], labels: Mapping[str, str]) -> str:
    """The days in week order, a run of three or more as `First–Last`.

    The week is a cycle, so a run may cross its end: Sun–Thu is five days. A range
    takes the place of the earliest of its days in the week, so Sun–Wed comes before
    Fri. All seven days are `Mon–Sun`.
    """
    chosen = {WEEKDAYS.index(day) for day in weekdays}
    if len(chosen) == _WEEK:
        return f"{labels[WEEKDAYS[0]]}–{labels[WEEKDAYS[-1]]}"
    parts: list[tuple[int, str]] = []
    for first in sorted(chosen):
        if (first - 1) % _WEEK in chosen:
            continue  # In the middle of a run, which its first day reports.
        run = [first]
        while (run[-1] + 1) % _WEEK in chosen:
            run.append((run[-1] + 1) % _WEEK)
        if len(run) >= _MIN_RANGE:
            text = f"{labels[WEEKDAYS[run[0]]]}–{labels[WEEKDAYS[run[-1]]]}"
            parts.append((min(run), text))
        else:
            parts.extend((day, labels[WEEKDAYS[day]]) for day in run)
    return ", ".join(text for _, text in sorted(parts))
