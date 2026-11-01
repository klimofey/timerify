"""The Repairs issues of a timer: raised and cleared here, fixed in `repairs.py`."""

from typing import Final, Literal

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

TARGET_DELETED: Final = "target_deleted"
"""The kind of the issue of a timer whose target entity was deleted."""

STORED_TIMER_INVALID: Final = "stored_timer_invalid"
"""The kind of the issue of a timer whose stored state cannot be read."""

SETTINGS_NOT_TAKEN: Final = "settings_not_taken"
"""The kind of the warning of a schedule interval whose settings the target does not
take. It has no fix: it is not fixable, and carries no data."""

type TimerIssueKind = Literal["target_deleted", "stored_timer_invalid"]
"""The kinds of issue that a timer has at most one of, and that the user can fix. The
kind is the start of the id (`issue_id`) and the `kind` in the data, which
`repairs.async_create_fix_flow` picks the fix by."""

type IssueKind = TimerIssueKind | Literal["settings_not_taken"]
"""What an issue is about, which is the key of its texts in the translations."""


def issue_id(kind: TimerIssueKind, entry_id: str) -> str:
    """The id of the issue of `kind` for the timer `entry_id`: one timer has at most
    one of each kind. The warning of an interval has its own (`interval_issue_id`)."""
    return f"{kind}_{entry_id}"


def _interval_issue_prefix(entry_id: str) -> str:
    return f"{SETTINGS_NOT_TAKEN}_{entry_id}_"


def interval_issue_id(entry_id: str, subentry_id: str) -> str:
    """The id of the warning of the interval `subentry_id` of the timer `entry_id`: one
    interval has at most one."""
    return f"{_interval_issue_prefix(entry_id)}{subentry_id}"


@callback
def _async_raise(
    hass: HomeAssistant,
    entry: ConfigEntry,
    kind: IssueKind,
    identifier: str,
    *,
    fixable: bool,
    severity: ir.IssueSeverity,
    **placeholders: str,
) -> None:
    """Raise the issue `identifier` of `kind` for the timer `entry`. A fixable issue
    carries the data that `repairs.async_create_fix_flow` picks its fix by. It is not
    persistent: the timer raises it again when it is set up, if it still stands."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        identifier,
        data={"entry_id": entry.entry_id, "kind": kind} if fixable else None,
        is_fixable=fixable,
        is_persistent=False,
        severity=severity,
        translation_key=kind,
        translation_placeholders={"timer": entry.title, **placeholders},
    )


@callback
def async_raise_target_deleted(
    hass: HomeAssistant, entry: ConfigEntry, target: str
) -> None:
    """Tell the user that the entity `target` of the timer `entry` was deleted. The
    issue is fixed by deleting the timer."""
    _async_raise(
        hass,
        entry,
        TARGET_DELETED,
        issue_id(TARGET_DELETED, entry.entry_id),
        fixable=True,
        severity=ir.IssueSeverity.ERROR,
        target=target,
    )


@callback
def async_raise_stored_timer_invalid(
    hass: HomeAssistant, entry: ConfigEntry, reason: str
) -> None:
    """Tell the user that the stored timer of `entry` cannot be used, and why. The
    issue is fixed by resetting it."""
    _async_raise(
        hass,
        entry,
        STORED_TIMER_INVALID,
        issue_id(STORED_TIMER_INVALID, entry.entry_id),
        fixable=True,
        severity=ir.IssueSeverity.ERROR,
        reason=reason,
    )


@callback
def async_raise_settings_not_taken(
    hass: HomeAssistant, entry: ConfigEntry, subentry: ConfigSubentry, settings: str
) -> None:
    """Warn the user that the target of the timer `entry` does not take `settings`,
    the labels of the settings of the interval `subentry` that it turns the target on
    with. The warning has no fix: the target taking them again, or the user choosing
    others, makes it go."""
    _async_raise(
        hass,
        entry,
        SETTINGS_NOT_TAKEN,
        interval_issue_id(entry.entry_id, subentry.subentry_id),
        fixable=False,
        severity=ir.IssueSeverity.WARNING,
        interval=subentry.title,
        settings=settings,
    )


@callback
def async_clear(hass: HomeAssistant, kind: TimerIssueKind, entry_id: str) -> None:
    """Take the issue of `kind` for the timer `entry_id` away; there may be none."""
    ir.async_delete_issue(hass, DOMAIN, issue_id(kind, entry_id))


@callback
def async_clear_settings_not_taken(
    hass: HomeAssistant, entry_id: str, subentry_id: str
) -> None:
    """Take the warning of the interval `subentry_id` of the timer `entry_id` away;
    there may be none."""
    ir.async_delete_issue(hass, DOMAIN, interval_issue_id(entry_id, subentry_id))


@callback
def async_warned_intervals(hass: HomeAssistant, entry_id: str) -> set[str]:
    """The ids of the intervals of the timer `entry_id` that have a warning in the
    issue registry, also one that an earlier load of the timer raised."""
    prefix = _interval_issue_prefix(entry_id)
    return {
        found.removeprefix(prefix)
        for domain, found in ir.async_get(hass).issues
        if domain == DOMAIN and found.startswith(prefix)
    }


@callback
def async_clear_settings_warnings(hass: HomeAssistant, entry_id: str) -> None:
    """Take every warning of the intervals of the timer `entry_id` away."""
    for subentry_id in async_warned_intervals(hass, entry_id):
        async_clear_settings_not_taken(hass, entry_id, subentry_id)
