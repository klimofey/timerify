"""Persistence of one target's timer, saved whenever it changes."""

from datetime import UTC, datetime
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import freeze_settings
from .core import Command, Snapshot


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
    return Command(
        id=data["id"],
        at=datetime.fromisoformat(data["at"]),
        action=data["action"],
        minutes=data["minutes"],
        settings=freeze_settings(data["settings"]),
    )


def _payload(snapshot: Snapshot) -> dict[str, Any]:
    """What is stored of a snapshot: the countdown, the wish not yet confirmed, the
    settings not yet confirmed with whether they may only go with a turn-on, and the
    pending commands.

    `last_actual` describes the live target, so it is not stored: after a restart
    nothing is known about the target until it reports.
    """
    end = snapshot.end
    return {
        "end": None if end is None else end.astimezone(UTC).isoformat(),
        "pending": snapshot.pending,
        "owed_settings": dict(snapshot.owed_settings),
        "commands": [command_to_json(command) for command in snapshot.commands],
        "owed_turn_on_only": snapshot.owed_turn_on_only,
    }


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
        command and may reach a running target (P1).
        """
        if old_major_version == 1:
            return {
                **old_data,
                "owed_settings": {},
                "commands": [],
                "owed_turn_on_only": False,
            }
        if old_major_version == 2:
            return {**old_data, "owed_turn_on_only": False}
        raise NotImplementedError


class TimerStore:
    """The stored timer of one config entry, in a versioned file of its own."""

    STORAGE_VERSION: Final = 3

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = _TimerFile(hass, self.STORAGE_VERSION, f"timerify.{entry_id}")
        self._saved: dict[str, Any] | None = None
        """What the file holds; None while that is not known."""

    async def async_load(self) -> Snapshot:
        """The stored timer, migrated to the current version if need be; an idle one
        when nothing was stored yet."""
        data = await self._store.async_load()
        if data is None:
            snapshot = Snapshot()
        else:
            end = data["end"]
            snapshot = Snapshot(
                end=None if end is None else datetime.fromisoformat(end),
                pending=data["pending"],
                owed_settings=freeze_settings(data["owed_settings"]),
                owed_turn_on_only=data["owed_turn_on_only"],
                commands=tuple(_command_from_json(c) for c in data["commands"]),
            )
        self._saved = _payload(snapshot)
        return snapshot

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
