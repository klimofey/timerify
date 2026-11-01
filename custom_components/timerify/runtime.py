"""The runtime counter: how long a target was on, and the file that keeps the total.

`RuntimeCounter` touches nothing: it is told when the target turned on or off and what
time it is, and it records. It decides nothing about the target, and it knows nothing
of the timer. Only `RuntimeStore` is tied to Home Assistant.
"""

import logging
from datetime import datetime
from math import isfinite
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

RUNTIME_STORAGE_VERSION: Final = 1
"""The version of the counter's file, `{"seconds": <float, at least 0>}`."""


def runtime_storage_key(entry_id: str) -> str:
    """The key of the counter's file: that of the timer of `entry_id`, with `.runtime`.
    The counter has a file of its own, so that nothing the timer stores or migrates is
    touched by it."""
    return f"timerify.{entry_id}.runtime"


def _seconds_between(since: datetime, until: datetime) -> float:
    """The seconds from `since` to `until`; none when the clock was set back between
    them, so that a run is never counted as negative."""
    return max(0.0, (until - since).total_seconds())


class RuntimeCounter:
    """The seconds a target was on: those of the runs that ended, and those so far of
    the one that is open.

    The caller says when the target turned on or off (timezone-aware times) and asks
    for the total as of a time; the counter never reads the clock. A report that
    changes nothing (on after on, off after off) is ignored.
    """

    def __init__(self, seconds: float = 0.0) -> None:
        self._closed = seconds
        """The seconds of the runs that ended, including those counted before."""
        self._since: datetime | None = None
        """When the open run began; None while the target is off."""
        self._shown = 0.0
        """The minutes last published."""

    def observe(self, at: datetime, on: bool) -> None:
        """The target is on, or not, from `at`. A run begins at the first report of on
        and ends at the first report of off after it; a run that appears to end before
        it began counts for nothing."""
        if on and self._since is None:
            self._since = at
        elif not on and self._since is not None:
            self._closed += _seconds_between(self._since, at)
            self._since = None

    def total(self, now: datetime) -> float:
        """The seconds counted up to `now`: the runs that ended, and the open one to
        `now`. It changes nothing."""
        if self._since is None:
            return self._closed
        return self._closed + _seconds_between(self._since, now)

    def minutes(self, now: datetime) -> float:
        """The total as of `now` in minutes, to two decimals, and never fewer than were
        published: a total that appears to shrink (the clock was set back) is not
        passed on, because the statistics take a value that goes down for a meter that
        was reset, or take the dip off their sum."""
        return max(self._shown, round(self.total(now) / 60, 2))

    def seconds_to_store(self, now: datetime) -> float:
        """The seconds the file has to hold as of `now`: the total, or the minutes
        published if those are more. A counter built from them shows, to the hundredth,
        at least what was published, even where the total is behind it: the clock was
        set back, or the minute was rounded up. Saving `total` alone would let the
        value drop after a restart."""
        return max(self.total(now), self._shown * 60)

    @property
    def shown(self) -> float:
        """The minutes last published; 0 until some are."""
        return self._shown

    def mark_shown(self, value: float) -> None:
        """Record that `value` minutes were published."""
        self._shown = value


def _seconds_from_json(data: object) -> float:
    """The seconds a stored payload holds; a ValueError saying what is wrong with one
    that no counter wrote, which holds a number no run can add up to.

    A whole number counts as a number of seconds, as it does to anyone who edits the
    file; whatever else the payload carries is left alone, because refusing a file
    throws away everything it counted.
    """
    if not isinstance(data, dict):
        raise ValueError("it is not an object")
    if "seconds" not in data:
        raise ValueError("it holds no seconds")
    seconds = data["seconds"]
    if isinstance(seconds, bool) or not isinstance(seconds, int | float):
        raise ValueError(f"the seconds are {seconds!r}, which is not a number")
    if not isfinite(seconds) or seconds < 0:
        raise ValueError(f"the seconds are {seconds!r}, which no runs add up to")
    return float(seconds)


class RuntimeStore:
    """The seconds the target of one config entry was on, in a versioned file of its
    own."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store[dict[str, Any]](
            hass, RUNTIME_STORAGE_VERSION, runtime_storage_key(entry_id)
        )

    async def async_load(self) -> float:
        """The stored seconds; 0 when nothing was stored yet.

        A file that no counter wrote (see `_seconds_from_json`) is not trusted: the log
        names it and the count starts from zero. The next save replaces it.
        """
        data = await self._store.async_load()
        if data is None:
            return 0.0
        try:
            return _seconds_from_json(data)
        except ValueError as err:
            _LOGGER.warning(
                "The runtime counter file %s cannot be used (%s); counting from zero",
                self._store.path,
                err,
            )
            return 0.0

    async def async_save(self, seconds: float) -> None:
        """Write the total out at once, not after a delay: a value is published only
        after the file holds at least as much, so that a crash cannot lose it. While
        Home Assistant is stopping, the write is queued for its final write, which
        comes before it has stopped."""
        await self._store.async_save({"seconds": seconds})

    async def async_remove(self) -> None:
        """Delete the stored file."""
        await self._store.async_remove()
