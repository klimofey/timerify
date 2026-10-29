"""Per-domain rules: what "on" means for an entity and which services switch it."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final, Literal

from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_STANDBY,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import State, split_entity_id

type Actual = Literal["on", "off", "unavailable"]
"""What an entity is doing; "unavailable" covers missing, unavailable and unknown."""


@dataclass(frozen=True)
class DomainBehaviour:
    """How to switch the entities of one domain and how to read their state."""

    on_service: tuple[str, str]
    """(domain, service) that turns an entity on."""
    off_service: tuple[str, str]
    """(domain, service) that turns an entity off."""
    is_on: Callable[[State], bool]
    """Whether a state counts as on; only meaningful for states that are not
    unavailable or unknown, which is why callers go through `actual_state`."""


def _is_state_on(state: State) -> bool:
    return state.state == STATE_ON


def _is_not_off(state: State) -> bool:
    return state.state != STATE_OFF


def _is_not_off_or_standby(state: State) -> bool:
    return state.state not in (STATE_OFF, STATE_STANDBY)


def _domain_behaviour(
    domain: str, is_on: Callable[[State], bool] = _is_state_on
) -> DomainBehaviour:
    """A row whose services are `<domain>.turn_on` and `<domain>.turn_off`."""
    return DomainBehaviour(
        on_service=(domain, SERVICE_TURN_ON),
        off_service=(domain, SERVICE_TURN_OFF),
        is_on=is_on,
    )


_BEHAVIOURS: Final[Mapping[str, DomainBehaviour]] = {
    "switch": _domain_behaviour("switch"),
    "input_boolean": _domain_behaviour("input_boolean"),
    "light": _domain_behaviour("light"),
    "fan": _domain_behaviour("fan"),
    "humidifier": _domain_behaviour("humidifier"),
    "siren": _domain_behaviour("siren"),
    "remote": _domain_behaviour("remote"),
    # Home Assistant has no group.turn_on; homeassistant.turn_on expands a group
    # into its members and switches each through its own domain.
    "group": DomainBehaviour(
        on_service=("homeassistant", SERVICE_TURN_ON),
        off_service=("homeassistant", SERVICE_TURN_OFF),
        is_on=_is_state_on,
    ),
    # The state of these is an HVAC or operation mode, not on/off.
    "climate": _domain_behaviour("climate", _is_not_off),
    "water_heater": _domain_behaviour("water_heater", _is_not_off),
    # Standby is a media player's low-power state, so it counts as off.
    "media_player": _domain_behaviour("media_player", _is_not_off_or_standby),
}

SUPPORTED_DOMAINS: Final[tuple[str, ...]] = tuple(_BEHAVIOURS)


def behaviour_for(entity_id: str) -> DomainBehaviour:
    """Return the behaviour of an entity's domain.

    Raises ValueError for a malformed entity id or an unsupported domain.
    """
    domain, _ = split_entity_id(entity_id)
    try:
        return _BEHAVIOURS[domain]
    except KeyError:
        raise ValueError(f"Domain {domain!r} is not supported") from None


def actual_state(state: State | None) -> Actual:
    """Classify a state as on, off or unavailable according to its domain.

    A missing state, `unavailable` and `unknown` are all "unavailable": none of
    them can be commanded or trusted. Raises ValueError for an unsupported domain.
    """
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return "unavailable"
    return "on" if behaviour_for(state.entity_id).is_on(state) else "off"
