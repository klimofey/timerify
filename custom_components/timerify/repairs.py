"""The fixes of the Repairs issues of a timer (`issues.py`)."""

import probatio
from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .issues import TARGET_DELETED


class DeleteTimerFlow(RepairsFlow):
    """The fix of a timer whose target was deleted: one step that asks the user to
    confirm, then deletes the timer, with its entities, intervals and stored files."""

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
        """Show what will be deleted; once the user submits, delete it.

        The timer may be gone by then, deleted on its integration page while the
        repair stood open: the fix then does nothing and says so. A step that is shown
        again without its issue says so as well, since it could only show blanks in
        place of the names of the timer and the entity.
        """
        if user_input is None:
            issue = ir.async_get(self.hass).async_get_issue(DOMAIN, self.issue_id)
            if issue is None:
                return self.async_abort(reason="timer_gone")
            return self.async_show_form(
                step_id="confirm",
                data_schema=probatio.Schema({}),
                description_placeholders=issue.translation_placeholders,
            )
        if self.hass.config_entries.async_get_entry(self._entry_id) is None:
            return self.async_abort(reason="timer_gone")
        await self.hass.config_entries.async_remove(self._entry_id)
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """The fix of a Timerify issue, picked by the `kind` in its data."""
    if data is not None and data["kind"] == TARGET_DELETED:
        return DeleteTimerFlow(str(data["entry_id"]))
    raise ValueError(f"The issue {issue_id} has no fix: its data is {data}")
