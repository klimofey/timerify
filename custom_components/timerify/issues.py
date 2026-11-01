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
take. It has no fix: it is not fixable. It is persistent, so that Home Assistant keeps
it, with its Ignore and the names of the settings it was raised with, through a restart
(`async_warned_settings`)."""

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


_NAMES: Final = "names"
_NAME_SEPARATOR: Final = ","
"""The key and the separator of the names of the settings in the data of a warning."""


def _interval_issue_prefix(entry_id: str) -> str:
    return f"{SETTINGS_NOT_TAKEN}_{entry_id}_"


def interval_issue_id(entry_id: str, subentry_id: str) -> str:
    """The id of the warning of the interval `subentry_id` of the timer `entry_id`: one
    interval has at most one."""
    return f"{_interval_issue_prefix(entry_id)}{subentry_id}"


type IssueData = dict[str, str | int | float | None]
"""What Home Assistant keeps with an issue, for the code that handles it."""


def _fix_data(entry: ConfigEntry, kind: TimerIssueKind) -> IssueData:
    """The data of a fixable issue, which `repairs.async_create_fix_flow` picks its fix
    by."""
    return {"entry_id": entry.entry_id, "kind": kind}


@callback
def _async_raise(
    hass: HomeAssistant,
    entry: ConfigEntry,
    kind: IssueKind,
    identifier: str,
    *,
    fixable: bool,
    persistent: bool,
    severity: ir.IssueSeverity,
    data: IssueData | None,
    **placeholders: str,
) -> None:
    """Raise the issue `identifier` of `kind` for the timer `entry`. An issue that
    exists is updated in place and keeps the Ignore of the user. Home Assistant saves
    a persistent issue whole and loads it back active after a restart; it saves any
    other with its Ignore only and loads it back inactive, until the code raises it
    again, which the timer does when it is set up, if the issue still stands."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        identifier,
        data=data,
        is_fixable=fixable,
        is_persistent=persistent,
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
        persistent=False,
        severity=ir.IssueSeverity.ERROR,
        data=_fix_data(entry, TARGET_DELETED),
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
        persistent=False,
        severity=ir.IssueSeverity.ERROR,
        data=_fix_data(entry, STORED_TIMER_INVALID),
        reason=reason,
    )


@callback
def async_raise_settings_not_taken(
    hass: HomeAssistant,
    entry: ConfigEntry,
    subentry: ConfigSubentry,
    names: tuple[str, ...],
    settings: str,
) -> None:
    """Warn the user that the target of the timer `entry` does not take the settings
    `names` of the interval `subentry`, which `settings` calls by their labels. The
    warning has no fix: the target taking them again, or the user choosing others,
    makes it go. The names are kept with it, so that a load of the timer that finds it,
    also after a restart, can tell whether the settings grew. It is persistent for
    that: Home Assistant would save a warning that is not without its data, and the
    Ignore of the user would not survive the growth that follows a restart."""
    _async_raise(
        hass,
        entry,
        SETTINGS_NOT_TAKEN,
        interval_issue_id(entry.entry_id, subentry.subentry_id),
        fixable=False,
        persistent=True,
        severity=ir.IssueSeverity.WARNING,
        data={_NAMES: _NAME_SEPARATOR.join(names)},
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


def _names_of(issue: ir.IssueEntry) -> tuple[str, ...]:
    """The names of the settings a warning was raised with; none for an issue that keeps
    no names, which this code never raises. Then every setting counts as new."""
    names = issue.data.get(_NAMES) if issue.data else None
    return tuple(names.split(_NAME_SEPARATOR)) if isinstance(names, str) else ()


@callback
def async_warned_settings(
    hass: HomeAssistant, entry_id: str
) -> dict[str, tuple[str, ...]]:
    """The warnings in the issue registry for the intervals of the timer `entry_id`,
    also those that an earlier load of the timer raised, or that Home Assistant loaded
    from its file after a restart: the names of the settings of each, by the id of its
    interval."""
    prefix = _interval_issue_prefix(entry_id)
    return {
        issue.issue_id.removeprefix(prefix): _names_of(issue)
        for (domain, found), issue in ir.async_get(hass).issues.items()
        if domain == DOMAIN and found.startswith(prefix)
    }


@callback
def async_clear_settings_warnings(hass: HomeAssistant, entry_id: str) -> None:
    """Take every warning of the intervals of the timer `entry_id` away."""
    for subentry_id in async_warned_settings(hass, entry_id):
        async_clear_settings_not_taken(hass, entry_id, subentry_id)
