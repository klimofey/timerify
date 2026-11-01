"""The fixes of the Repairs issues of a timer (`issues.py`)."""

from abc import ABC, abstractmethod

import probatio
from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .issues import STORED_TIMER_INVALID, TARGET_DELETED
from .store import TimerStore


class _ConfirmedFix(RepairsFlow, ABC):
    """The fix of a problem of one timer: one step that asks the user to confirm, then
    fixes it, in `_async_fix` of the subclass."""

    def __init__(self, entry_id: str) -> None:
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """The first step of the fix, which only shows the second."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Show what the fix does; once the user submits, do it.

        The fix does nothing, and says why, when its timer is gone, deleted on its
        integration page while the repair stood open, or when its issue is no longer
        open: the problem went away by itself, or the timer was unloaded since. A step
        that is shown again then would only show blanks in place of the names in it.
        """
        if self.hass.config_entries.async_get_entry(self._entry_id) is None:
            return self.async_abort(reason="timer_gone")
        if user_input is None:
            issue = ir.async_get(self.hass).async_get_issue(DOMAIN, self.issue_id)
            if issue is None:
                return self.async_abort(reason="issue_gone")
            return self.async_show_form(
                step_id="confirm",
                data_schema=probatio.Schema({}),
                description_placeholders=issue.translation_placeholders,
            )
        await self._async_fix()
        return self.async_create_entry(data={})

    @abstractmethod
    async def _async_fix(self) -> None:
        """Fix the problem, once the user has confirmed."""


class DeleteTimerFlow(_ConfirmedFix):
    """The fix of a timer whose target was deleted: it deletes the timer, with its
    entities, intervals and stored files."""

    async def _async_fix(self) -> None:
        await self.hass.config_entries.async_remove(self._entry_id)


class ResetStoredTimerFlow(_ConfirmedFix):
    """The fix of a timer whose stored state cannot be read: it deletes the file and
    loads the timer again, which starts idle. The timer, its intervals and its runtime
    total stay."""

    async def _async_fix(self) -> None:
        await TimerStore(self.hass, self._entry_id).async_remove()
        await self.hass.config_entries.async_reload(self._entry_id)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """The fix of a Timerify issue, picked by the `kind` in its data."""
    if data is not None:
        if data["kind"] == TARGET_DELETED:
            return DeleteTimerFlow(str(data["entry_id"]))
        if data["kind"] == STORED_TIMER_INVALID:
            return ResetStoredTimerFlow(str(data["entry_id"]))
    raise ValueError(f"The issue {issue_id} has no fix: its data is {data}")
