"""The Repairs issues of a timer: raised and cleared here, fixed in `repairs.py`."""

from typing import Final, Literal

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

TARGET_DELETED: Final = "target_deleted"
"""The kind of the issue of a timer whose target entity was deleted."""

type IssueKind = Literal["target_deleted", "stored_timer_invalid"]
"""What an issue is about. It is the start of its id and the `kind` in its data, which
`repairs.async_create_fix_flow` picks the fix by."""


def issue_id(kind: IssueKind, entry_id: str) -> str:
    """The id of the issue of `kind` for the timer `entry_id`: one timer has at most
    one of each kind."""
    return f"{kind}_{entry_id}"


@callback
def async_raise_target_deleted(
    hass: HomeAssistant, entry: ConfigEntry, target: str
) -> None:
    """Tell the user that the entity `target` of the timer `entry` was deleted. The
    issue is fixed by deleting the timer. It is not persistent: it lives with the loaded
    timer, which raises it again when it is set up."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id(TARGET_DELETED, entry.entry_id),
        data={"entry_id": entry.entry_id, "kind": TARGET_DELETED},
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=TARGET_DELETED,
        translation_placeholders={"timer": entry.title, "target": target},
    )


@callback
def async_clear(hass: HomeAssistant, kind: IssueKind, entry_id: str) -> None:
    """Take the issue of `kind` for the timer `entry_id` away; there may be none."""
    ir.async_delete_issue(hass, DOMAIN, issue_id(kind, entry_id))
