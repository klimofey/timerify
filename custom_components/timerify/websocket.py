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
The command only reads and is open to every user, not only to admins, but it tells a
user only what the user may read, as the commands of Home Assistant that are about
entities do: it refuses a user who may not read the number it is asked about, the target
or one of the two sensors, and leaves out the interval switches the user may not read.

It also says which of the two sensors are disabled. A disabled entity has no state,
which looks like an entity that has not started yet, and only the registry tells them
apart; the card draws the countdown from one and the pending commands from the other,
and tells the user which one it misses instead of staying silent.

A number that is not a timer's is answered `not_found`. A number that is a timer's, but
whose timer cannot be told of, is answered `timer_incomplete`: either its target was
stored by registry id and that id is gone, or one of its two sensors is not in the
entity registry, which happens while the entry is not set up. The card must not tell the
user that a number is no timer's when it is. A target stored as an entity id resolves
whether or not the entity exists, so a timer with such a target is told of as usual.
"""

from typing import Any, Final, Literal, TypedDict

import probatio
from homeassistant.auth.models import User
from homeassistant.auth.permissions import filter_entity_ids_by_permission
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components.websocket_api import async_register_command
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.const import ERR_NOT_FOUND
from homeassistant.components.websocket_api.decorators import websocket_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_MODE,
    CONF_TARGET,
    DOMAIN,
    KEY_ENDS_AT,
    KEY_NEXT_COMMAND,
    KEY_RUN_FOR,
    SUBENTRY_INTERVAL,
    Mode,
    default_duration_minutes,
    interval_unique_id,
    is_voice_options,
    timer_unique_id,
)
from .domains import behaviour_for

COMMAND: Final = "timerify/timer"
ERR_TIMER_INCOMPLETE: Final = "timer_incomplete"
"""The error code for a timer's number whose timer cannot be told of."""


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
    disabled_sensors: list[str]
    """The entity ids of the two sensors that are disabled in the registry; none when
    both are enabled. A disabled sensor has no state, so the card cannot tell it from
    one that has not started yet without this."""


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
    """Answer which timer the "Run for" number `entity_id` belongs to.

    The permission to read the number is checked before anything is looked up, so that
    a user who may not read an entity cannot tell by the answer whether it is a timer's.
    """
    entity_id: str = msg["entity_id"]
    user = connection.user
    _require_read(user, entity_id)
    try:
        info = _timer_of_number(hass, entity_id)
    except _TimerNotFound as err:
        connection.send_error(msg["id"], ERR_NOT_FOUND, str(err))
        return
    except _TimerIncomplete as err:
        connection.send_error(msg["id"], ERR_TIMER_INCOMPLETE, str(err))
        return
    for told in (info["target"], info["ends_at"], info["next_command"]):
        _require_read(user, told)
    readable = set(
        filter_entity_ids_by_permission(
            user, (interval["entity_id"] for interval in info["intervals"]), POLICY_READ
        )
    )
    info["intervals"] = [i for i in info["intervals"] if i["entity_id"] in readable]
    connection.send_result(msg["id"], info)


def _require_read(user: User, entity_id: str) -> None:
    """Refuse the whole answer to a user who may not read `entity_id`."""
    if not user.permissions.check_entity(entity_id, POLICY_READ):
        raise Unauthorized(entity_id=entity_id, permission=POLICY_READ)


class _TimerNotFound(Exception):
    """The entity is not a timer's number; the message says so."""


class _TimerIncomplete(Exception):
    """The entity is a timer's number, but the timer cannot be told of: what the card
    needs of it is not in the entity registry. The message says what."""


def _timer_of_number(hass: HomeAssistant, entity_id: str) -> TimerInfo:
    """What the card needs about the timer whose "Run for" number is `entity_id`, from
    the registry and the entry alone, whatever state the entry is in.

    Raises `_TimerNotFound` when `entity_id` is not such a number (the voice settings
    have none). Raises `_TimerIncomplete` when it is one but the timer cannot be told
    of: it has no target to resolve, or one of its two sensors is not in the registry.
    A timer that was set up has both sensors.
    """
    registry = er.async_get(hass)
    if (entry := _entry_of_number(hass, registry, entity_id)) is None:
        raise _TimerNotFound(
            f"{entity_id} is not the Run for number of a Timerify timer"
        )
    target = er.async_resolve_entity_id(registry, entry.options[CONF_TARGET])
    if target is None:
        raise _TimerIncomplete(
            f"The target of the Timerify timer of {entity_id}"
            " is not in the entity registry"
        )
    ends_at = _sensor(registry, entry, entity_id, KEY_ENDS_AT)
    next_command = _sensor(registry, entry, entity_id, KEY_NEXT_COMMAND)
    mode: Mode = entry.options[CONF_MODE]
    on_rule = behaviour_for(target).on_rule
    return TimerInfo(
        entry_id=entry.entry_id,
        target=target,
        mode=mode,
        default_duration=(
            default_duration_minutes(entry.options) if mode == "strict" else None
        ),
        ends_at=ends_at.entity_id,
        next_command=next_command.entity_id,
        intervals=_intervals(registry, entry),
        target_on=OnRuleInfo(match=on_rule.match, states=sorted(on_rule.states)),
        disabled_sensors=[
            sensor.entity_id for sensor in (ends_at, next_command) if sensor.disabled
        ],
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
    if number.unique_id != timer_unique_id(entry.entry_id, KEY_RUN_FOR):
        return None
    return entry


def _sensor(
    registry: er.EntityRegistry, entry: ConfigEntry, number: str, key: str
) -> er.RegistryEntry:
    """The registry entry of the sensor of the timer that has the key `key`, which every
    timer that was set up has.

    Raises `_TimerIncomplete` when the registry has none; `number` is the timer's, for
    the message.
    """
    entity_id = registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, timer_unique_id(entry.entry_id, key)
    )
    if entity_id is None or (sensor := registry.async_get(entity_id)) is None:
        raise _TimerIncomplete(
            f"The Timerify timer of {number} has no {key} sensor in the entity registry"
        )
    return sensor


def _intervals(registry: er.EntityRegistry, entry: ConfigEntry) -> list[IntervalInfo]:
    """The intervals of the timer that have a switch, with their titles."""
    intervals: list[IntervalInfo] = []
    for subentry in entry.get_subentries_of_type(SUBENTRY_INTERVAL):
        switch = registry.async_get_entity_id(
            Platform.SWITCH,
            DOMAIN,
            interval_unique_id(entry.entry_id, subentry.subentry_id),
        )
        if switch is not None:
            intervals.append(IntervalInfo(entity_id=switch, title=subentry.title))
    return intervals
