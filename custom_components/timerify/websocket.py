"""The websocket command that tells the dashboard card about one timer.

The card is configured with the "Run for" number of a timer, the one handle that names
exactly one timer: the entity registry the frontend keeps carries neither the config
entry nor the unique id of an entity, and two timers can share a device. The command
`timerify/timer` turns that number into everything else the card needs: the target, how
the timer is bound, the entities of the timer that the card reads and switches, and what
counts as on for the target.

The answer is configuration, read from the entity registry and the entry, never from
the running timer. The card asks again whenever the number comes back, which is while
its entry is still starting after a restart or a reload, so the answer is the same
whatever state the entry is in; the card shows a timer that did not start by its states.
The command only reads, and tells nothing a user's states do not, so it is open to
every user, not only to admins.
"""

from typing import Any, Final, Literal, TypedDict

import probatio
from homeassistant.components.websocket_api import async_register_command
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.const import ERR_NOT_FOUND
from homeassistant.components.websocket_api.decorators import websocket_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_DEFAULT_DURATION,
    CONF_MODE,
    CONF_TARGET,
    DEFAULT_DURATION_MINUTES,
    DOMAIN,
    SUBENTRY_INTERVAL,
    Mode,
    is_voice_options,
)
from .domains import behaviour_for

COMMAND: Final = "timerify/timer"

# The keys of the entity descriptions of a timer, which its unique ids are made of: the
# entry's id and the key, `<entry id>_<key>` (see `TimerifyEntity`).
_RUN_FOR: Final = "run_for"
_ENDS_AT: Final = "ends_at"
_NEXT_COMMAND: Final = "next_command"


class IntervalInfo(TypedDict):
    """A schedule interval: the switch that enables it and the title it was given."""

    entity_id: str
    title: str


class OnRuleInfo(TypedDict):
    """Which states of the target count as on; see `OnRule`."""

    match: Literal["is", "is_not"]
    states: list[str]


class TimerInfo(TypedDict):
    """What the card is told about a timer; the card mirrors these keys exactly."""

    entry_id: str
    target: str
    mode: Mode
    default_duration: int | None
    """The minutes a bare run lasts in strict mode; none in loose mode, where a bare
    run has no end."""
    ends_at: str
    """The entity id of the "Ends at" sensor, which every timer that was set up has."""
    next_command: str
    """The entity id of the "Next command" sensor, which every timer that was set up
    has."""
    intervals: list[IntervalInfo]
    """The intervals in the order they were added; one with no switch in the registry
    is left out."""
    target_on: OnRuleInfo


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register the commands; they exist whether or not a timer is set up."""
    async_register_command(hass, _handle_timer)


@websocket_command(
    {
        probatio.Required("type"): COMMAND,
        probatio.Required("entity_id"): cv.entity_id,
    }
)
@callback
def _handle_timer(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Answer which timer the "Run for" number `entity_id` belongs to."""
    entity_id: str = msg["entity_id"]
    if (info := _timer_of_number(hass, entity_id)) is None:
        connection.send_error(
            msg["id"],
            ERR_NOT_FOUND,
            f"{entity_id} is not the Run for number of a Timerify timer",
        )
        return
    connection.send_result(msg["id"], info)


def _timer_of_number(hass: HomeAssistant, entity_id: str) -> TimerInfo | None:
    """What the card needs about the timer whose "Run for" number is `entity_id`, from
    the registry and the entry alone, whatever state the entry is in.

    None when `entity_id` is not such a number, when it belongs to the voice settings
    (which are not a timer), or when the timer cannot be told of: it has no target to
    resolve, or one of its two sensors is not in the registry. A timer that was set up
    has both sensors.
    """
    registry = er.async_get(hass)
    entry = _entry_of_number(hass, registry, entity_id)
    if entry is None:
        return None
    target = er.async_resolve_entity_id(registry, entry.options[CONF_TARGET])
    ends_at = registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, _unique_id(entry, _ENDS_AT)
    )
    next_command = registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, _unique_id(entry, _NEXT_COMMAND)
    )
    if target is None or ends_at is None or next_command is None:
        return None
    mode: Mode = entry.options[CONF_MODE]
    on_rule = behaviour_for(target).on_rule
    return TimerInfo(
        entry_id=entry.entry_id,
        target=target,
        mode=mode,
        default_duration=(
            entry.options.get(CONF_DEFAULT_DURATION, DEFAULT_DURATION_MINUTES)
            if mode == "strict"
            else None
        ),
        ends_at=ends_at,
        next_command=next_command,
        intervals=_intervals(registry, entry),
        target_on=OnRuleInfo(match=on_rule.match, states=sorted(on_rule.states)),
    )


def _entry_of_number(
    hass: HomeAssistant, registry: er.EntityRegistry, entity_id: str
) -> ConfigEntry | None:
    """The entry of the timer whose "Run for" number is `entity_id`, if it is one."""
    number = registry.async_get(entity_id)
    if number is None or number.platform != DOMAIN or number.config_entry_id is None:
        return None
    entry = hass.config_entries.async_get_entry(number.config_entry_id)
    if entry is None or entry.domain != DOMAIN or is_voice_options(entry.options):
        return None
    if number.unique_id != _unique_id(entry, _RUN_FOR):
        return None
    return entry


def _intervals(registry: er.EntityRegistry, entry: ConfigEntry) -> list[IntervalInfo]:
    """The intervals of the timer that have a switch, with their titles."""
    intervals: list[IntervalInfo] = []
    for subentry in entry.get_subentries_of_type(SUBENTRY_INTERVAL):
        # The unique id of an `IntervalSwitch`.
        switch = registry.async_get_entity_id(
            Platform.SWITCH,
            DOMAIN,
            f"{entry.entry_id}_interval_{subentry.subentry_id}",
        )
        if switch is not None:
            intervals.append(IntervalInfo(entity_id=switch, title=subentry.title))
    return intervals


def _unique_id(entry: ConfigEntry, key: str) -> str:
    """The unique id of the entity of the timer that has the description key `key`."""
    return f"{entry.entry_id}_{key}"
