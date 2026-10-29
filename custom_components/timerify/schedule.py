"""Schedule intervals: how one is named for the user."""

from collections.abc import Mapping
from typing import Any, Final

from homeassistant.const import WEEKDAYS

from .const import CONF_DAYS, CONF_END, CONF_START, CONF_WEEKDAYS, DaysMode

_WEEK: Final = len(WEEKDAYS)
_MIN_RANGE: Final = 3
"""The fewest consecutive days written as a range: Mon–Wed, not Mon, Tue, Wed."""


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
