"""Persistence of one target's timer, saved whenever it changes."""

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.storage import Store

from .const import DOMAIN, freeze_settings
from .core import Command, Snapshot, Window, checked_window


def _time_to_json(moment: datetime | None) -> str | None:
    """A time as ISO-8601 UTC, or None for none."""
    return None if moment is None else moment.astimezone(UTC).isoformat()


def _time_from_json(text: str, what: str) -> datetime:
    """A stored time, in UTC whatever offset the file gives it, as the core holds every
    time; a ValueError naming `what` for a time with no offset, which no timer wrote
    and which cannot be compared with the clock."""
    moment = datetime.fromisoformat(text)
    if moment.utcoffset() is None:
        raise ValueError(f"{what} must be timezone-aware")
    return moment.astimezone(UTC)


def _optional_time_from_json(text: str | None, what: str) -> datetime | None:
    """`_time_from_json`, or None for a time that is not there."""
    return None if text is None else _time_from_json(text, what)


@contextmanager
def _fields_of(what: str) -> Iterator[None]:
    """A ValueError saying that a field of `what` is missing, in place of the KeyError
    of the field alone, which would not say whose it is."""
    try:
        yield
    except KeyError as err:
        raise ValueError(f"the field {err.args[0]} of {what} is missing") from None


def command_to_json(command: Command) -> dict[str, Any]:
    """A pending command as plain data: its time as ISO-8601 UTC, its settings as a
    dict. The file of the timer and the "Next command" sensor show it alike."""
    return {
        "id": command.id,
        "at": command.at.astimezone(UTC).isoformat(),
        "action": command.action,
        "minutes": command.minutes,
        "settings": dict(command.settings),
    }


def _command_from_json(data: dict[str, Any]) -> Command:
    with _fields_of("a pending command"):
        return Command(
            id=data["id"],
            at=_time_from_json(data["at"], "the command's time"),
            action=data["action"],
            minutes=data["minutes"],
            settings=freeze_settings(data["settings"]),
        )


def window_to_json(window: Window) -> dict[str, Any]:
    """A schedule window as plain data: its times as ISO-8601 UTC, its settings as a
    dict, and whether it has started and whether it was stopped."""
    return {
        "interval": window.interval_id,
        "start": window.start.astimezone(UTC).isoformat(),
        "end": window.end.astimezone(UTC).isoformat(),
        "settings": dict(window.settings),
        "started": window.started,
        "suppressed": window.suppressed,
    }


def _window_from_json(data: dict[str, Any]) -> Window:
    """A stored window, in UTC; a ValueError for one that no schedule could have made,
    by the rule that holds for every window the core is given."""
    with _fields_of("a schedule window"):
        window = Window(
            interval_id=data["interval"],
            start=datetime.fromisoformat(data["start"]),
            end=datetime.fromisoformat(data["end"]),
            settings=freeze_settings(data["settings"]),
            started=data["started"],
            suppressed=data["suppressed"],
        )
    return checked_window(window)


def _validated(snapshot: Snapshot) -> Snapshot:
    """`snapshot`, if it says nothing that no timer could have written; else a
    ValueError.

    The file is read strictly, so that a defect that wrote nonsense shows when the
    timer is set up instead of as a target switched for reasons nobody can follow.
    """
    seen: set[str] = set()
    for window in snapshot.windows:
        if window.interval_id in seen:
            raise ValueError(f"two windows of the interval {window.interval_id}")
        seen.add(window.interval_id)
        if window.suppressed and not window.started:
            raise ValueError(
                f"the window of {window.interval_id} is suppressed but has not started"
            )
    if switched_off := snapshot.disabled_intervals & seen:
        raise ValueError(
            f"the interval {min(switched_off)} is switched off but has a window"
        )
    if snapshot.scheduled_by is not None and snapshot.end is None:
        raise ValueError("the timer is scheduled by an interval but has no end")
    if snapshot.started_at is not None:
        if snapshot.end is None:
            raise ValueError("the countdown has a beginning but no end")
        if snapshot.started_at >= snapshot.end:
            raise ValueError("the countdown begins at or after its end")
    if snapshot.owed_turn_on_only and not snapshot.owed_settings:
        raise ValueError("the turn-on-only marker is set without owed settings")
    return snapshot


def _disabled_from_json(interval_ids: list[str]) -> frozenset[str]:
    """The intervals that are switched off; each is named once."""
    for interval_id, times in Counter(interval_ids).items():
        if times > 1:
            raise ValueError(f"the interval {interval_id} is switched off twice")
    return frozenset(interval_ids)


def _payload(snapshot: Snapshot) -> dict[str, Any]:
    """What is stored of a snapshot: the countdown with when it began, and the interval
    whose window end it carries, the wish not yet confirmed, the settings not yet
    confirmed with whether they may only go with a turn-on, the pending commands, the
    schedule windows and the intervals that are switched off.

    `last_actual` describes the live target, so it is not stored: after a restart
    nothing is known about the target until it reports.
    """
    return {
        "end": _time_to_json(snapshot.end),
        "started_at": _time_to_json(snapshot.started_at),
        "pending": snapshot.pending,
        "owed_settings": dict(snapshot.owed_settings),
        "commands": [command_to_json(command) for command in snapshot.commands],
        "owed_turn_on_only": snapshot.owed_turn_on_only,
        "scheduled_by": snapshot.scheduled_by,
        "windows": [window_to_json(window) for window in snapshot.windows],
        "disabled_intervals": sorted(snapshot.disabled_intervals),
    }


class StoredTimerInvalid(ConfigEntryError):
    """The stored timer cannot be used. `reason` says what is wrong with it, in words
    for the user: the set-up fails with it, and so does the repair that resets the
    file."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="stored_timer_invalid",
            translation_placeholders={"reason": reason},
        )
        self.reason = reason


class _TimerFile(Store[dict[str, Any]]):
    """The file of a timer, which reads what earlier versions wrote."""

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Bring the stored timer of an older version to the current one.

        Version 1 knew no settings and no commands, so nothing was owed and nothing
        waited. Version 2 knew no schedules, so every setting that was owed came from a
        command and may reach a running target (P1), and no window existed for a timer
        to be carried by, nor an interval to be switched off. Version 3 knew no
        beginning of a countdown, and nothing says when one that is stored began, so it
        has none.
        """
        if old_major_version == 1:
            return {
                **old_data,
                "owed_settings": {},
                "commands": [],
                "owed_turn_on_only": False,
                "scheduled_by": None,
                "windows": [],
                "disabled_intervals": [],
                "started_at": None,
            }
        if old_major_version == 2:
            return {
                **old_data,
                "owed_turn_on_only": False,
                "scheduled_by": None,
                "windows": [],
                "disabled_intervals": [],
                "started_at": None,
            }
        if old_major_version == 3:
            return {**old_data, "started_at": None}
        raise NotImplementedError


class TimerStore:
    """The stored timer of one config entry, in a versioned file of its own."""

    STORAGE_VERSION: Final = 4

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = _TimerFile(hass, self.STORAGE_VERSION, f"timerify.{entry_id}")
        self._saved: dict[str, Any] | None = None
        """What the file holds; None while that is not known."""

    async def async_load(self) -> Snapshot:
        """The stored timer, migrated to the current version if need be; an idle one
        when nothing was stored yet.

        Raises StoredTimerInvalid, saying what is wrong, for a file that contradicts
        itself (see `_validated`), holds a time that is not one, lacks a field or holds
        a field of a type that no timer writes.
        """
        data = await self._store.async_load()
        if data is None:
            snapshot = Snapshot()
        else:
            try:
                snapshot = self._read(data)
            except KeyError as err:
                raise StoredTimerInvalid(
                    f"the field {err.args[0]} is missing"
                ) from None
            except (ValueError, TypeError) as err:
                # The reason says all there is to say of it; the cause would only add
                # a traceback of Python's to the log.
                raise StoredTimerInvalid(str(err)) from None
        self._saved = _payload(snapshot)
        return snapshot

    @staticmethod
    def _read(data: dict[str, Any]) -> Snapshot:
        """The timer a file of the current version holds."""
        return _validated(
            Snapshot(
                end=_optional_time_from_json(data["end"], "the end of the countdown"),
                started_at=_optional_time_from_json(
                    data["started_at"], "the beginning of the countdown"
                ),
                pending=data["pending"],
                owed_settings=freeze_settings(data["owed_settings"]),
                owed_turn_on_only=data["owed_turn_on_only"],
                commands=tuple(_command_from_json(c) for c in data["commands"]),
                scheduled_by=data["scheduled_by"],
                windows=tuple(_window_from_json(w) for w in data["windows"]),
                disabled_intervals=_disabled_from_json(data["disabled_intervals"]),
            )
        )

    async def async_save(self, snapshot: Snapshot) -> None:
        """Write the timer out at once, unless the file already holds it.

        Datetimes go in as ISO-8601 UTC.
        """
        payload = _payload(snapshot)
        if payload != self._saved:
            await self._store.async_save(payload)
            self._saved = payload

    async def async_remove(self) -> None:
        """Delete the stored file."""
        await self._store.async_remove()
        self._saved = None
