"""Config and options flows: pick a target, bind it, set the default duration.

Adding a timer takes the entity and the binding mode, and in strict mode a default
duration. The options flow changes the mode and the duration; the target stays.
"""

from collections.abc import Mapping
from enum import IntFlag
from typing import Any, Final, get_args, override

import probatio
from homeassistant.components.climate.const import ClimateEntityFeature
from homeassistant.components.water_heater.const import WaterHeaterEntityFeature
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector
from homeassistant.helpers.entity import get_supported_features
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
from .domains import SUPPORTED_DOMAINS
from .entity import target_name

_REQUIRED_FEATURES: Final[Mapping[str, tuple[IntFlag, ...]]] = {
    "climate": (ClimateEntityFeature.TURN_ON, ClimateEntityFeature.TURN_OFF),
    "water_heater": (WaterHeaterEntityFeature.ON_OFF,),
}
"""Domains whose entities may not be switchable: the features an entity of the
domain must advertise to be a target. Other supported domains always can."""


def _target_selector() -> selector.EntitySelector:
    """Offer the supported domains; of the climate and water heater entities, those
    that look switchable.

    The picker takes an entity that has any one of a filter's features, so it can
    not require several. The exact rule is checked on submit by `_validate_target`;
    that check is needed anyway, since the selector validates only the domain.
    """
    always_switchable = [d for d in SUPPORTED_DOMAINS if d not in _REQUIRED_FEATURES]
    filters = [selector.EntityWithDeviceFilterSelectorConfig(domain=always_switchable)]
    filters.extend(
        selector.EntityWithDeviceFilterSelectorConfig(
            domain=domain,
            # The `<domain>.<enum>.<member>` form that selector filters take.
            supported_features=[
                f"{domain}.{type(f).__name__}.{f.name}" for f in features
            ],
        )
        for domain, features in _REQUIRED_FEATURES.items()
    )
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=list(SUPPORTED_DOMAINS), filter=filters)
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


def _supports_switching(hass: HomeAssistant, entity_id: str) -> bool:
    """Whether a timer can turn the entity on and off."""
    domain = split_entity_id(entity_id)[0]
    if domain not in SUPPORTED_DOMAINS:
        return False
    required = _REQUIRED_FEATURES.get(domain, ())
    if not required:
        return True
    try:
        features = get_supported_features(hass, entity_id)
    except HomeAssistantError:  # Neither a state nor a registry entry: unknown.
        return False
    return all(features & feature == feature for feature in required)


async def _validate_target(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Accept a target that a timer can switch and that has no timer yet.

    The target is stored as an entity id, whichever of the two the selector took.
    The entry is identified by the registry id, which a rename leaves alone; an
    entity that is not in the registry has only its entity id.
    """
    flow = handler.parent_handler
    assert isinstance(flow, ConfigFlow)
    registry = er.async_get(flow.hass)
    entity_id = er.async_resolve_entity_id(registry, user_input[CONF_TARGET])
    if entity_id is None or not _supports_switching(flow.hass, entity_id):
        raise SchemaFlowError("target_not_supported")
    registered = registry.async_get(entity_id)
    await flow.async_set_unique_id(registered.id if registered else entity_id)
    flow._abort_if_unique_id_configured()
    return {**user_input, CONF_TARGET: entity_id}


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
        probatio.Schema(
            {
                probatio.Required(CONF_TARGET): _target_selector(),
                probatio.Required(CONF_MODE, default="strict"): _mode_selector(),
            }
        ),
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
