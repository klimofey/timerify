"""Config and options flows: pick a target, bind it, set the default duration.

Adding a timer takes the entity and the binding mode, and in strict mode a default
duration. The options flow changes the mode and the duration; the target stays.

The picker offers the domains of the table in `domains.py` and, for any entity that
can be turned on and off, every other domain that has both services.
"""

from collections.abc import Mapping
from typing import Any, Final, get_args, override

import probatio
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    UnitOfTime,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)

from .const import (
    CONF_DEFAULT_DURATION,
    CONF_MODE,
    CONF_TARGET,
    DEFAULT_DURATION_MINUTES,
    DOMAIN,
    MAX_MINUTES,
    Mode,
)
from .domains import (
    SUPPORTED_DOMAINS,
    behaviour_for_domain,
    switchable_by_features,
)
from .target import target_name


def offered_domains(hass: HomeAssistant) -> list[str]:
    """The domains the picker offers: those of the table, then, sorted, every other
    domain that has both a turn_on and a turn_off service now.

    `homeassistant` has both and is never offered: its services are how the generic
    row switches the entities of every other domain, and it forwards no call to its
    own domain.
    """
    others = sorted(
        domain
        for domain in hass.services.async_services()
        if domain not in SUPPORTED_DOMAINS
        and domain != HOMEASSISTANT_DOMAIN
        and hass.services.has_service(domain, SERVICE_TURN_ON)
        and hass.services.has_service(domain, SERVICE_TURN_OFF)
    )
    return [*SUPPORTED_DOMAINS, *others]


def _target_selector(hass: HomeAssistant) -> selector.EntitySelector:
    """Offer the domains of `offered_domains`; of those whose services need features,
    the entities that advertise some of them.

    The picker takes an entity that has any one of a filter's features, so it can
    not require several. The exact rule is checked on submit by `_validate_target`;
    that check is needed anyway, since the selector validates only the domain.
    """
    domains = offered_domains(hass)
    required = {
        domain: behaviour_for_domain(domain).required_features for domain in domains
    }
    always_switchable = [
        domain for domain, features in required.items() if not features
    ]
    filters = [selector.EntityWithDeviceFilterSelectorConfig(domain=always_switchable)]
    filters.extend(
        selector.EntityWithDeviceFilterSelectorConfig(
            domain=domain,
            # The `<domain>.<enum>.<member>` form that selector filters take.
            supported_features=[
                f"{domain}.{type(f).__name__}.{f.name}" for f in features
            ],
        )
        for domain, features in required.items()
        if features
    )
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=domains, filter=filters)
    )


def _mode_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(get_args(Mode)),
            mode=selector.SelectSelectorMode.LIST,
            translation_key=CONF_MODE,
        )
    )


def _duration_selector() -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1,
            max=MAX_MINUTES,
            step=1,
            mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement=UnitOfTime.MINUTES,
        )
    )


async def _target_schema(handler: SchemaCommonFlowHandler) -> probatio.Schema:
    """The form that adds a timer, built for the domains on offer when it is shown."""
    flow = handler.parent_handler
    assert isinstance(flow, ConfigFlow)
    return probatio.Schema(
        {
            probatio.Required(CONF_TARGET): _target_selector(flow.hass),
            probatio.Required(CONF_MODE, default="strict"): _mode_selector(),
        }
    )


async def _validate_target(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Accept a target that a timer can switch and that has no timer yet.

    In order: its domain must be on offer, which is a registry id's only check of the
    domain; a domain of the table judges the entity by its features; and an entity
    that is switched through the generic row, a group among them, must read on or
    off, since that row takes any other state for off. The other rows are never
    judged by state: a thermostat heats and a player plays.

    The target is stored as an entity id, whichever of the two the selector took.
    The entry is identified by the registry id, which a rename leaves alone; an
    entity that is not in the registry has only its entity id.
    """
    flow = handler.parent_handler
    assert isinstance(flow, ConfigFlow)
    registry = er.async_get(flow.hass)
    entity_id = er.async_resolve_entity_id(registry, user_input[CONF_TARGET])
    if entity_id is None:
        raise SchemaFlowError("target_not_supported")
    domain = split_entity_id(entity_id)[0]
    # A domain without a row of its own needs no features: only a table domain can fail.
    if domain not in offered_domains(flow.hass) or not switchable_by_features(
        flow.hass, entity_id
    ):
        raise SchemaFlowError("target_not_supported")
    if behaviour_for_domain(domain).judged_by_state and not _reads_on_or_off(
        flow.hass, entity_id
    ):
        raise SchemaFlowError("not_switchable")
    registered = registry.async_get(entity_id)
    await flow.async_set_unique_id(registered.id if registered else entity_id)
    flow._abort_if_unique_id_configured()
    return {**user_input, CONF_TARGET: entity_id}


def _reads_on_or_off(hass: HomeAssistant, entity_id: str) -> bool:
    """Whether the entity's state is on or off now; an entity with no state, or one
    that is unavailable or unknown, is neither."""
    state = hass.states.get(entity_id)
    return state is not None and state.state in (STATE_ON, STATE_OFF)


async def _validate_duration(
    _handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Keep the default duration in whole minutes, the unit the timer counts in."""
    minutes: float = user_input[CONF_DEFAULT_DURATION]
    if not minutes.is_integer():
        raise SchemaFlowError("duration_not_whole")
    return {**user_input, CONF_DEFAULT_DURATION: int(minutes)}


async def _after_mode(options: dict[str, Any]) -> str | None:
    """Strict mode needs a default duration; loose mode has no use for one."""
    return "duration" if options[CONF_MODE] == "strict" else None


_DURATION_STEP = SchemaFlowFormStep(
    probatio.Schema(
        {
            probatio.Required(
                CONF_DEFAULT_DURATION, default=DEFAULT_DURATION_MINUTES
            ): _duration_selector()
        }
    ),
    validate_user_input=_validate_duration,
)

CONFIG_FLOW: Final = {
    "user": SchemaFlowFormStep(
        _target_schema,
        validate_user_input=_validate_target,
        next_step=_after_mode,
    ),
    "duration": _DURATION_STEP,
}

OPTIONS_FLOW: Final = {
    "init": SchemaFlowFormStep(
        probatio.Schema({probatio.Required(CONF_MODE): _mode_selector()}),
        next_step=_after_mode,
    ),
    "duration": _DURATION_STEP,
}


class TimerifyConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle the config and options flows of Timerify."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = True

    VERSION = 1

    @override
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Name the entry after its target."""
        return target_name(self.hass, options[CONF_TARGET])
