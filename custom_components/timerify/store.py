"""Persistence of one target's timer: its snapshot, saved on every change."""

from datetime import UTC, datetime
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .core import Snapshot


class TimerStore:
    """The stored snapshot of one config entry, in a versioned file of its own."""

    STORAGE_VERSION: Final = 1

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store[dict[str, Any]](
            hass, self.STORAGE_VERSION, f"timerify.{entry_id}"
        )

    async def async_load(self) -> Snapshot:
        """The stored snapshot; an idle one when nothing was stored yet."""
        data = await self._store.async_load()
        if data is None:
            return Snapshot()
        end = data.get("end")
        return Snapshot(
            end=None if end is None else datetime.fromisoformat(end),
            pending=data.get("pending"),
            last_actual=data.get("last_actual"),
        )

    async def async_save(self, snapshot: Snapshot) -> None:
        """Write the snapshot out at once; datetimes go in as ISO-8601 UTC."""
        end = snapshot.end
        await self._store.async_save(
            {
                "end": None if end is None else end.astimezone(UTC).isoformat(),
                "pending": snapshot.pending,
                "last_actual": snapshot.last_actual,
            }
        )

    async def async_remove(self) -> None:
        """Delete the stored file."""
        await self._store.async_remove()
