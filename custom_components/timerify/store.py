"""Persistence of one target's timer, saved whenever it changes."""

from datetime import UTC, datetime
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .core import Snapshot


def _payload(snapshot: Snapshot) -> dict[str, Any]:
    """What is stored of a snapshot: the countdown and the wish not yet confirmed.

    `last_actual` describes the live target, so it is not stored: after a restart
    nothing is known about the target until it reports.
    """
    end = snapshot.end
    return {
        "end": None if end is None else end.astimezone(UTC).isoformat(),
        "pending": snapshot.pending,
    }


class TimerStore:
    """The stored timer of one config entry, in a versioned file of its own."""

    STORAGE_VERSION: Final = 1

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store[dict[str, Any]](
            hass, self.STORAGE_VERSION, f"timerify.{entry_id}"
        )
        self._saved: dict[str, Any] | None = None
        """What the file holds; None while that is not known."""

    async def async_load(self) -> Snapshot:
        """The stored timer; an idle one when nothing was stored yet."""
        data = await self._store.async_load()
        if data is None:
            snapshot = Snapshot()
        else:
            end = data.get("end")
            snapshot = Snapshot(
                end=None if end is None else datetime.fromisoformat(end),
                pending=data.get("pending"),
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
