"""Per-domain rules: what "on" means for an entity, which services switch it and which
settings it can be turned on with.

A domain that is not in the table is switched through the generic `FALLBACK` row.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import IntFlag
from typing import Any, Final, Literal

from homeassistant.components.climate.const import (
    ClimateEntityCapabilityAttribute,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.fan.const import (
    FanEntityCapabilityAttribute,
    FanEntityFeature,
)
from homeassistant.components.humidifier.const import (
    HumidifierEntityCapabilityAttribute,
    HumidifierEntityFeature,
)
from homeassistant.components.light.const import LightEntityCapabilityAttribute
from homeassistant.components.light.helper import brightness_supported
from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from homeassistant.components.siren.const import SirenEntityFeature
from homeassistant.components.water_heater.const import (
    WaterHeaterCapabilityAttribute,
    WaterHeaterEntityFeature,
)
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_STANDBY,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State, split_entity_id
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity import get_capability, get_supported_features

from .const import (
    DOMAIN,
    MAX_AUTOMATIC_RESENDS,
    NO_SETTINGS,
    Settings,
    freeze_settings,
)
from .target import target_name

type Actual = Literal["on", "off", "unavailable"]
"""What an entity is doing; "unavailable" covers missing, unavailable and unknown."""


@dataclass(frozen=True)
class TargetCall:
    """A service call that acts on the target; the target's entity id is added when
    the call is made."""

    domain: str
    service: str
    data: Mapping[str, Any]
    """The service data without `entity_id`."""


class _Capabilities:
    """What one entity says it can do: its supported features and capability attributes.

    Home Assistant keeps both on an `unavailable` state, and the entity registry keeps
    them for an entity that has no state, so they are known while the entity is not
    working.
    """

    def __init__(self, hass: HomeAssistant, entity_id: str) -> None:
        """Raises HomeAssistantError for an entity that is in neither the state machine
        nor the entity registry."""
        self._hass = hass
        self._entity_id = entity_id
        self._features = get_supported_features(hass, entity_id)

    def supports(self, *features: IntFlag) -> bool:
        """Whether the entity advertises every one of the features."""
        return all(self._features & feature == feature for feature in features)

    def attribute(self, name: str) -> Any:
        """The value of a capability attribute; None when the entity has none."""
        return get_capability(self._hass, self._entity_id, name)


def _text(value: Any) -> str:
    """A value as the user reads it: 16 for 16.0."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _bound(capabilities: _Capabilities, bound: float | str) -> Any:
    """The number of a bound: itself, or what the entity says in the attribute."""
    return capabilities.attribute(bound) if isinstance(bound, str) else bound


@dataclass(frozen=True)
class _Between:
    """The numbers from `low` to `high`, both included.

    A bound is a number, or the name of the capability attribute that holds it.
    """

    low: float | str
    high: float | str

    def known(self, capabilities: _Capabilities) -> bool:
        """Whether the entity says where its range begins and ends."""
        return all(
            _bound(capabilities, bound) is not None for bound in (self.low, self.high)
        )

    def check(self, capabilities: _Capabilities, setting: str, value: Any) -> None:
        low = _bound(capabilities, self.low)
        high = _bound(capabilities, self.high)
        # A boolean is a number to Python, not to the user.
        is_number = isinstance(value, int | float) and not isinstance(value, bool)
        if not (is_number and low <= value <= high):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="setting_out_of_range",
                translation_placeholders={
                    "setting": setting,
                    "value": _text(value),
                    "min": _text(low),
                    "max": _text(high),
                },
            )


@dataclass(frozen=True)
class _OneOf:
    """The values in the list that a capability attribute holds, less `excluded`."""

    attribute: str
    excluded: frozenset[str] = frozenset()
    """Values the entity lists but a turn-on must not use: `off` turns it off."""

    def _options(self, capabilities: _Capabilities) -> list[str]:
        """The values the entity lists that a turn-on may use."""
        return [
            option
            for option in capabilities.attribute(self.attribute) or ()
            if option not in self.excluded
        ]

    def known(self, capabilities: _Capabilities) -> bool:
        """Whether the entity lists an option a turn-on may use: one that lists only
        `off` offers no setting."""
        return bool(self._options(capabilities))

    def check(self, capabilities: _Capabilities, setting: str, value: Any) -> None:
        options = self._options(capabilities)
        if value not in options:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="setting_not_an_option",
                translation_placeholders={
                    "setting": setting,
                    "value": _text(value),
                    "options": ", ".join(options),
                },
            )


def _always(_capabilities: _Capabilities) -> bool:
    return True


def _has(feature: IntFlag) -> Callable[[_Capabilities], bool]:
    """A requirement: the entity advertises the feature."""

    def advertised(capabilities: _Capabilities) -> bool:
        return capabilities.supports(feature)

    return advertised


def _has_brightness(capabilities: _Capabilities) -> bool:
    return brightness_supported(
        capabilities.attribute(LightEntityCapabilityAttribute.SUPPORTED_COLOR_MODES)
    )


@dataclass(frozen=True)
class _Setting:
    """One setting an entity can be turned on with, named as the field of the Home
    Assistant service that applies it."""

    name: str
    rule: _Between | _OneOf
    """The values the entity accepts."""
    requires: Callable[[_Capabilities], bool] = _always
    """What the entity must be able to do for the setting to exist at all."""
    service: tuple[str, str] | None = None
    """(domain, service) that applies the setting alone; None when the setting goes
    along with the turn-on call of the domain."""
    turns_on: bool = False
    """Whether `service` also turns the entity on, so that a turn-on needs no call of
    its own when the setting is given."""

    def supported(self, capabilities: _Capabilities) -> bool:
        """Whether the entity can take the setting: it has what the setting needs and
        says which values it accepts."""
        return self.requires(capabilities) and self.rule.known(capabilities)


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
    required_features: tuple[IntFlag, ...] = ()
    """The features an entity must advertise for the on and off services to work."""
    automatic_resends: int = MAX_AUTOMATIC_RESENDS
    """How often reports that repeat the entity's state send an unsent wish again,
    at most; see `MAX_AUTOMATIC_RESENDS`."""
    settings: tuple[_Setting, ...] = ()
    """The settings the entities can be turned on with, in the order that their calls
    are made."""

    @property
    def setting_names(self) -> frozenset[str]:
        """The names of the settings the entities can be turned on with."""
        return frozenset(setting.name for setting in self.settings)

    def turn_on_calls(self, settings: Settings) -> tuple[TargetCall, ...]:
        """The calls that turn the entity on with `settings`, in order.

        The settings must be valid for the entity (see `validate_settings`).
        """
        return self._calls(settings, turning_on=True)

    def apply_calls(self, settings: Settings) -> tuple[TargetCall, ...]:
        """The calls that set `settings` on an entity that is already on, in order;
        none for no settings. Never a call that turns the entity on, except for a
        domain whose settings travel in it."""
        return self._calls(settings, turning_on=False)

    def _calls(self, settings: Settings, *, turning_on: bool) -> tuple[TargetCall, ...]:
        given = [setting for setting in self.settings if setting.name in settings]
        # Settings without a service of their own travel in the turn-on call.
        carried = {s.name: settings[s.name] for s in given if s.service is None}
        alone = tuple(
            TargetCall(*s.service, {s.name: settings[s.name]})
            for s in given
            if s.service is not None
        )
        replaced = any(s.turns_on for s in given)
        if carried or (turning_on and not replaced):
            return (TargetCall(*self.on_service, carried), *alone)
        return alone


def _is_state_on(state: State) -> bool:
    return state.state == STATE_ON


def _is_not_off(state: State) -> bool:
    return state.state != STATE_OFF


def _is_not_off_or_standby(state: State) -> bool:
    return state.state not in (STATE_OFF, STATE_STANDBY)


def _domain_behaviour(
    domain: str,
    is_on: Callable[[State], bool] = _is_state_on,
    *,
    required_features: tuple[IntFlag, ...] = (),
    automatic_resends: int = MAX_AUTOMATIC_RESENDS,
    settings: tuple[_Setting, ...] = (),
) -> DomainBehaviour:
    """A row whose services are `<domain>.turn_on` and `<domain>.turn_off`."""
    return DomainBehaviour(
        on_service=(domain, SERVICE_TURN_ON),
        off_service=(domain, SERVICE_TURN_OFF),
        is_on=is_on,
        required_features=required_features,
        automatic_resends=automatic_resends,
        settings=settings,
    )


FALLBACK: Final = DomainBehaviour(
    on_service=("homeassistant", SERVICE_TURN_ON),
    off_service=("homeassistant", SERVICE_TURN_OFF),
    is_on=_is_state_on,
)
"""The row of every domain that has none of its own."""

_CLIMATE_SETTINGS: Final = (
    _Setting(
        "hvac_mode",
        _OneOf(
            ClimateEntityCapabilityAttribute.HVAC_MODES,
            excluded=frozenset({HVACMode.OFF}),
        ),
        service=("climate", "set_hvac_mode"),
        turns_on=True,
    ),
    _Setting(
        "temperature",
        _Between(
            ClimateEntityCapabilityAttribute.MIN_TEMP,
            ClimateEntityCapabilityAttribute.MAX_TEMP,
        ),
        requires=_has(ClimateEntityFeature.TARGET_TEMPERATURE),
        service=("climate", "set_temperature"),
    ),
    _Setting(
        "fan_mode",
        _OneOf(ClimateEntityCapabilityAttribute.FAN_MODES),
        requires=_has(ClimateEntityFeature.FAN_MODE),
        service=("climate", "set_fan_mode"),
    ),
)

_LIGHT_SETTINGS: Final = (
    _Setting("brightness_pct", _Between(1, 100), requires=_has_brightness),
)

_FAN_SETTINGS: Final = (
    _Setting("percentage", _Between(1, 100), requires=_has(FanEntityFeature.SET_SPEED)),
    _Setting(
        "preset_mode",
        _OneOf(FanEntityCapabilityAttribute.PRESET_MODES),
        requires=_has(FanEntityFeature.PRESET_MODE),
    ),
)

_HUMIDIFIER_SETTINGS: Final = (
    _Setting(
        "humidity",
        _Between(
            HumidifierEntityCapabilityAttribute.MIN_HUMIDITY,
            HumidifierEntityCapabilityAttribute.MAX_HUMIDITY,
        ),
        service=("humidifier", "set_humidity"),
    ),
    _Setting(
        "mode",
        _OneOf(HumidifierEntityCapabilityAttribute.AVAILABLE_MODES),
        requires=_has(HumidifierEntityFeature.MODES),
        service=("humidifier", "set_mode"),
    ),
)

_WATER_HEATER_SETTINGS: Final = (
    _Setting(
        "temperature",
        _Between(
            WaterHeaterCapabilityAttribute.MIN_TEMP,
            WaterHeaterCapabilityAttribute.MAX_TEMP,
        ),
        requires=_has(WaterHeaterEntityFeature.TARGET_TEMPERATURE),
        service=("water_heater", "set_temperature"),
    ),
    _Setting(
        "operation_mode",
        _OneOf(
            WaterHeaterCapabilityAttribute.OPERATION_LIST,
            excluded=frozenset({STATE_OFF}),
        ),
        requires=_has(WaterHeaterEntityFeature.OPERATION_MODE),
        service=("water_heater", "set_operation_mode"),
    ),
)

_BEHAVIOURS: Final[Mapping[str, DomainBehaviour]] = {
    "switch": _domain_behaviour("switch"),
    "input_boolean": _domain_behaviour("input_boolean"),
    "light": _domain_behaviour("light", settings=_LIGHT_SETTINGS),
    "fan": _domain_behaviour(
        "fan",
        required_features=(FanEntityFeature.TURN_ON, FanEntityFeature.TURN_OFF),
        settings=_FAN_SETTINGS,
    ),
    "humidifier": _domain_behaviour("humidifier", settings=_HUMIDIFIER_SETTINGS),
    "siren": _domain_behaviour(
        "siren",
        required_features=(SirenEntityFeature.TURN_ON, SirenEntityFeature.TURN_OFF),
    ),
    # A remote that toggles cannot show whether it obeyed, and a repeated turn_on
    # would switch it off again.
    "remote": _domain_behaviour("remote", automatic_resends=0),
    # Home Assistant has no group.turn_on; homeassistant.turn_on expands a group
    # into its members and switches each through its own domain.
    "group": FALLBACK,
    # The state of these is an HVAC or operation mode, not on/off.
    "climate": _domain_behaviour(
        "climate",
        _is_not_off,
        required_features=(ClimateEntityFeature.TURN_ON, ClimateEntityFeature.TURN_OFF),
        settings=_CLIMATE_SETTINGS,
    ),
    "water_heater": _domain_behaviour(
        "water_heater",
        _is_not_off,
        required_features=(WaterHeaterEntityFeature.ON_OFF,),
        settings=_WATER_HEATER_SETTINGS,
    ),
    # Standby is a media player's low-power state, so it counts as off. A player that
    # is booting reports a state that is not on for a while, and a repeated turn_on
    # can switch a toggling one off again.
    "media_player": _domain_behaviour(
        "media_player",
        _is_not_off_or_standby,
        required_features=(
            MediaPlayerEntityFeature.TURN_ON,
            MediaPlayerEntityFeature.TURN_OFF,
        ),
        automatic_resends=0,
    ),
}

SUPPORTED_DOMAINS: Final[tuple[str, ...]] = tuple(_BEHAVIOURS)


def behaviour_for_domain(domain: str) -> DomainBehaviour:
    """Return the row of a domain: its own, or the generic `FALLBACK`."""
    return _BEHAVIOURS.get(domain, FALLBACK)


def behaviour_for(entity_id: str) -> DomainBehaviour:
    """Return the behaviour of an entity's domain.

    Raises ValueError for a malformed entity id.
    """
    domain, _ = split_entity_id(entity_id)
    return behaviour_for_domain(domain)


def actual_state(state: State | None) -> Actual:
    """Classify a state as on, off or unavailable according to its domain.

    A missing state, `unavailable` and `unknown` are all "unavailable": none of
    them can be commanded or trusted.
    """
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return "unavailable"
    return "on" if behaviour_for(state.entity_id).is_on(state) else "off"


def switchable_by_features(hass: HomeAssistant, entity_id: str) -> bool:
    """Whether the entity advertises every feature its domain's on and off services
    need, from its state or, without one, from the entity registry.

    An entity that is in neither is not switchable, unless its domain needs no
    features. Only the features are judged, not whether the domain may be a target.
    """
    required = behaviour_for(entity_id).required_features
    if not required:
        return True
    try:
        return _Capabilities(hass, entity_id).supports(*required)
    except HomeAssistantError:  # Neither a state nor a registry entry: unknown.
        return False


def validate_settings(
    hass: HomeAssistant, entity_id: str, values: Mapping[str, Any]
) -> Settings:
    """Check that the entity can be turned on with `values` and return them frozen.

    The entity's capabilities decide: its state, or the entity registry when it has
    none. Both survive an outage, so a command can be made for a device that is
    unavailable now. An entity that is in neither says nothing about what it can do,
    so nothing is supported for it. A value of the wrong type is out of range or not
    an option like any other.

    Raises ServiceValidationError for the first setting the entity cannot take or whose
    value it does not accept.
    """
    if not values:
        return NO_SETTINGS
    specs = {spec.name: spec for spec in behaviour_for(entity_id).settings}
    try:
        capabilities = _Capabilities(hass, entity_id)
    except HomeAssistantError:  # Neither a state nor a registry entry: unknown.
        capabilities = None
    for name, value in values.items():
        spec = specs.get(name)
        if spec is None or capabilities is None or not spec.supported(capabilities):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="setting_not_supported",
                translation_placeholders={
                    "target": target_name(hass, entity_id),
                    "setting": name,
                },
            )
        spec.rule.check(capabilities, name, value)
    return freeze_settings(values)
