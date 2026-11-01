"""The per-domain table tells what "on" means for an entity, how to switch it and
how to switch it on with settings."""

import importlib
import operator
from collections.abc import Mapping
from enum import IntFlag
from functools import reduce
from pathlib import Path
from typing import Any

import pytest
from homeassistant.components.climate.const import ClimateEntityFeature
from homeassistant.components.fan.const import FanEntityFeature
from homeassistant.components.humidifier.const import HumidifierEntityFeature
from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from homeassistant.components.siren.const import SirenEntityFeature
from homeassistant.components.water_heater.const import WaterHeaterEntityFeature
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml

from custom_components.timerify.const import (
    DOMAIN,
    MAX_AUTOMATIC_RESENDS,
    NO_SETTINGS,
    Settings,
)
from custom_components.timerify.domains import (
    FALLBACK,
    SUPPORTED_DOMAINS,
    Actual,
    OnRule,
    TargetCall,
    actual_state,
    behaviour_for,
    behaviour_for_domain,
    settings_not_taken,
    supported_settings,
    switchable_by_features,
    validate_settings,
    voice_settings,
)

from .helpers import AC_ATTRS, AC_ID, AC_WITHOUT_FAN_MODE


@pytest.mark.parametrize(
    ("entity_id", "state", "expected"),
    [
        ("switch.boiler", "on", "on"),
        ("switch.boiler", "off", "off"),
        ("input_boolean.guest_mode", "on", "on"),
        ("input_boolean.guest_mode", "off", "off"),
        ("light.grow_lamp", "on", "on"),
        ("light.grow_lamp", "off", "off"),
        ("fan.bathroom", "on", "on"),
        ("fan.bathroom", "off", "off"),
        ("humidifier.bedroom", "on", "on"),
        ("humidifier.bedroom", "off", "off"),
        ("siren.hallway", "on", "on"),
        ("siren.hallway", "off", "off"),
        ("remote.living_room", "on", "on"),
        ("remote.living_room", "off", "off"),
        ("group.all_lights", "on", "on"),
        ("group.all_lights", "off", "off"),
        ("climate.ac", "cool", "on"),
        ("climate.ac", "heat", "on"),
        ("climate.ac", "heat_cool", "on"),
        ("climate.ac", "off", "off"),
        ("water_heater.tank", "eco", "on"),
        ("water_heater.tank", "performance", "on"),
        ("water_heater.tank", "off", "off"),
        ("media_player.tv", "playing", "on"),
        ("media_player.tv", "paused", "on"),
        ("media_player.tv", "idle", "on"),
        ("media_player.tv", "on", "on"),
        ("media_player.tv", "standby", "off"),
        ("media_player.tv", "off", "off"),
        ("switch.boiler", "unavailable", "unavailable"),
        ("switch.boiler", "unknown", "unavailable"),
        ("climate.ac", "unavailable", "unavailable"),
        ("climate.ac", "unknown", "unavailable"),
        ("media_player.tv", "unavailable", "unavailable"),
    ],
)
def test_actual_state(entity_id: str, state: str, expected: Actual) -> None:
    """The entity's raw state is read the way its domain defines on and off."""
    assert actual_state(State(entity_id, state)) == expected


def test_actual_state_of_missing_entity_is_unavailable() -> None:
    """An entity that is not in the state machine cannot be commanded or trusted."""
    assert actual_state(None) == "unavailable"


@pytest.mark.parametrize(
    ("entity_id", "on_service", "off_service"),
    [
        ("switch.boiler", ("switch", "turn_on"), ("switch", "turn_off")),
        ("light.grow_lamp", ("light", "turn_on"), ("light", "turn_off")),
        ("climate.ac", ("climate", "turn_on"), ("climate", "turn_off")),
        (
            "water_heater.tank",
            ("water_heater", "turn_on"),
            ("water_heater", "turn_off"),
        ),
        (
            "media_player.tv",
            ("media_player", "turn_on"),
            ("media_player", "turn_off"),
        ),
        # Home Assistant has no group.turn_on; a group is switched through
        # homeassistant.turn_on, which expands it into its members.
        (
            "group.all_lights",
            ("homeassistant", "turn_on"),
            ("homeassistant", "turn_off"),
        ),
    ],
)
def test_services_per_domain(
    entity_id: str, on_service: tuple[str, str], off_service: tuple[str, str]
) -> None:
    """Each domain names the services that switch its entities on and off."""
    behaviour = behaviour_for(entity_id)

    assert behaviour.on_service == on_service
    assert behaviour.off_service == off_service


@pytest.mark.parametrize(
    "entity_id", ["kettle.tea", "sensor.temp", "binary_sensor.door", "cover.gate"]
)
def test_unlisted_domain_uses_generic_fallback(entity_id: str) -> None:
    """A domain without a table row is switched through `homeassistant.turn_on` and
    `turn_off`, whatever it is, and asks for nothing special."""
    behaviour = behaviour_for(entity_id)

    assert behaviour is FALLBACK
    assert behaviour is behaviour_for_domain(entity_id.split(".")[0])
    assert behaviour.on_service == ("homeassistant", "turn_on")
    assert behaviour.off_service == ("homeassistant", "turn_off")
    assert behaviour.required_features == ()
    assert behaviour.automatic_resends == MAX_AUTOMATIC_RESENDS
    assert behaviour.setting_names == frozenset()


@pytest.mark.parametrize(("state", "expected"), [("on", "on"), ("idle", "off")])
def test_fallback_reads_only_on_as_on(state: str, expected: Actual) -> None:
    """A camera has states of its own; only `on` counts as on for the fallback."""
    assert actual_state(State("camera.door", state)) == expected


ON_ONLY = OnRule("is", frozenset({"on"}))
NOT_OFF = OnRule("is_not", frozenset({"off"}))
NOT_OFF_OR_STANDBY = OnRule("is_not", frozenset({"off", "standby"}))


@pytest.mark.parametrize(
    ("rule", "state", "expected"),
    [
        (ON_ONLY, "on", True),
        (ON_ONLY, "off", False),
        (ON_ONLY, "idle", False),
        (NOT_OFF, "heat", True),
        (NOT_OFF, "off", False),
        (NOT_OFF_OR_STANDBY, "playing", True),
        (NOT_OFF_OR_STANDBY, "standby", False),
        (NOT_OFF_OR_STANDBY, "off", False),
    ],
)
def test_a_rule_says_which_states_count_as_on(
    rule: OnRule, state: str, expected: bool
) -> None:
    """A rule that names the states of on counts only those; one that names the states
    of off counts every other state."""
    assert rule.matches(state) is expected


@pytest.mark.parametrize(
    ("entity_id", "expected"),
    [
        ("switch.boiler", ON_ONLY),
        ("input_boolean.guest_mode", ON_ONLY),
        ("light.grow_lamp", ON_ONLY),
        ("fan.bathroom", ON_ONLY),
        ("humidifier.bedroom", ON_ONLY),
        ("siren.hallway", ON_ONLY),
        ("remote.living_room", ON_ONLY),
        ("group.all_lights", ON_ONLY),
        ("kettle.tea", ON_ONLY),
        ("climate.ac", NOT_OFF),
        ("water_heater.tank", NOT_OFF),
        ("media_player.tv", NOT_OFF_OR_STANDBY),
    ],
)
def test_each_row_tells_what_counts_as_on_as_data(
    entity_id: str, expected: OnRule
) -> None:
    """The card is told the rule of the target's domain, not a copy of the table, so a
    row states it as data."""
    assert behaviour_for(entity_id).on_rule == expected


def test_only_rows_that_misread_other_states_are_judged_by_state() -> None:
    """The generic row takes every state but `on` for off, and a group goes through
    it: those are the targets whose state must read on or off. A thermostat's mode and
    a player's `playing` are not on or off, and their rows read them right."""
    judged = {
        domain
        for domain in SUPPORTED_DOMAINS
        if behaviour_for_domain(domain).judged_by_state
    }

    assert judged == {"group"}
    assert behaviour_for_domain("kettle").judged_by_state


def test_malformed_entity_id_raises() -> None:
    """An entity id without a domain part is refused."""
    with pytest.raises(ValueError, match="Invalid entity ID"):
        behaviour_for("boiler")


def test_supported_domains() -> None:
    """Exactly these domains are supported; adding one is a deliberate table entry."""
    assert set(SUPPORTED_DOMAINS) == {
        "switch",
        "input_boolean",
        "light",
        "fan",
        "humidifier",
        "siren",
        "remote",
        "group",
        "climate",
        "water_heater",
        "media_player",
    }


@pytest.mark.parametrize("domain", SUPPORTED_DOMAINS)
async def test_table_services_exist_in_home_assistant(
    hass: HomeAssistant, domain: str
) -> None:
    """Every service the table names is registered by the installed Home Assistant."""
    behaviour = behaviour_for(f"{domain}.anything")

    for service_domain, service in (behaviour.on_service, behaviour.off_service):
        assert await async_setup_component(hass, service_domain, {})
        assert hass.services.has_service(service_domain, service), (
            f"{service_domain}.{service} is not a Home Assistant service"
        )


@pytest.mark.parametrize(
    ("domain", "expected"),
    [
        ("switch", ()),
        ("light", ()),
        ("group", ()),
        ("climate", (ClimateEntityFeature.TURN_ON, ClimateEntityFeature.TURN_OFF)),
        ("water_heater", (WaterHeaterEntityFeature.ON_OFF,)),
        ("fan", (FanEntityFeature.TURN_ON, FanEntityFeature.TURN_OFF)),
        (
            "media_player",
            (MediaPlayerEntityFeature.TURN_ON, MediaPlayerEntityFeature.TURN_OFF),
        ),
        ("siren", (SirenEntityFeature.TURN_ON, SirenEntityFeature.TURN_OFF)),
    ],
)
def test_required_features_per_domain(
    domain: str, expected: tuple[IntFlag, ...]
) -> None:
    """The turn_on and turn_off services of these domains work only on entities that
    advertise the features; the others have none to ask for."""
    assert behaviour_for_domain(domain).required_features == expected


@pytest.mark.parametrize(
    ("domain", "expected"),
    [
        ("remote", 0),
        ("media_player", 0),
        ("switch", MAX_AUTOMATIC_RESENDS),
        ("climate", MAX_AUTOMATIC_RESENDS),
        ("group", MAX_AUTOMATIC_RESENDS),
        ("kettle", MAX_AUTOMATIC_RESENDS),  # the fallback
    ],
)
def test_automatic_resends_per_domain(domain: str, expected: int) -> None:
    """A toggle remote or a booting media player must not get a repeated turn_on that
    switches it back off; every other domain may be asked again a few times."""
    assert behaviour_for_domain(domain).automatic_resends == expected


@pytest.mark.parametrize(
    ("domain", "expected"),
    [
        ("climate", {"hvac_mode", "temperature", "fan_mode"}),
        ("light", {"brightness_pct"}),
        ("fan", {"percentage", "preset_mode"}),
        ("humidifier", {"humidity", "mode"}),
        ("water_heater", {"temperature", "operation_mode"}),
        ("switch", set()),
        ("input_boolean", set()),
        ("siren", set()),
        ("remote", set()),
        ("media_player", set()),
        ("group", set()),
    ],
)
def test_setting_names_per_domain(domain: str, expected: set[str]) -> None:
    """The settings a domain's entities can be turned on with."""
    assert behaviour_for_domain(domain).setting_names == frozenset(expected)


@pytest.mark.parametrize(
    ("domain", "percent", "mode"),
    [
        ("climate", None, "fan_mode"),
        ("light", "brightness_pct", None),
        ("fan", "percentage", "preset_mode"),
        ("humidifier", "humidity", "mode"),
        ("water_heater", None, "operation_mode"),
        ("switch", None, None),
        ("media_player", None, None),
    ],
)
def test_voice_means_one_setting_by_percent_and_one_by_mode(
    domain: str, percent: str | None, mode: str | None
) -> None:
    """A person says "40 percent" or "in eco mode", not the name of a service field:
    the row of each domain tells which of its settings that is."""
    row = behaviour_for_domain(domain)

    assert [s.name for s in row.settings if s.voice == "percent"] == (
        [percent] if percent else []
    )
    assert [s.name for s in row.settings if s.voice == "mode"] == (
        [mode] if mode else []
    )


@pytest.mark.parametrize("domain", SUPPORTED_DOMAINS)
def test_each_domain_has_at_most_one_percent_and_one_mode_setting(
    domain: str,
) -> None:
    """Two settings that both mean "percent" would make the word ambiguous."""
    meanings = [s.voice for s in behaviour_for_domain(domain).settings if s.voice]

    assert len(meanings) == len(set(meanings))


async def test_voice_settings_are_named_by_the_row_of_the_target(
    hass: HomeAssistant,
) -> None:
    """The same two words mean the setting each target's domain has for them."""
    assert voice_settings(hass, "light.hall", percent=40, mode=None) == {
        "brightness_pct": 40
    }
    assert voice_settings(hass, "fan.ceiling", percent=40, mode="sleep") == {
        "percentage": 40,
        "preset_mode": "sleep",
    }
    assert voice_settings(hass, "humidifier.room", percent=55, mode="away") == {
        "humidity": 55,
        "mode": "away",
    }
    assert voice_settings(hass, AC_ID, percent=None, mode="high") == {
        "fan_mode": "high"
    }
    assert voice_settings(hass, "water_heater.tank", percent=None, mode="eco") == {
        "operation_mode": "eco"
    }
    assert voice_settings(hass, AC_ID, percent=None, mode=None) == {}


@pytest.mark.parametrize(
    ("entity_id", "percent", "mode"),
    [
        ("switch.boiler", 40, None),
        ("switch.boiler", None, "eco"),
        (AC_ID, 40, None),
        ("light.hall", None, "eco"),
        ("water_heater.tank", 40, None),
    ],
)
async def test_a_voice_setting_the_row_does_not_have_is_refused(
    hass: HomeAssistant, entity_id: str, percent: float | None, mode: str | None
) -> None:
    """The boiler at 40 percent has no meaning: the refusal names the target."""
    hass.states.async_set(entity_id, "off", {"friendly_name": "Boiler"})

    with pytest.raises(ServiceValidationError) as err:
        voice_settings(hass, entity_id, percent=percent, mode=mode)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "voice_setting_not_supported"
    assert err.value.translation_placeholders == {"target": "Boiler"}


async def test_the_choices_of_a_setting_carry_what_it_means_to_say(
    hass: HomeAssistant,
) -> None:
    """The values a person may say are listed from what the target supports, by the
    meaning of the setting that has them."""
    hass.states.async_set(AC_ID, "off", AC_ATTRS)

    choices = {c.name: c for c in supported_settings(hass, AC_ID)}

    assert choices["fan_mode"].voice == "mode"
    assert choices["hvac_mode"].voice is None
    assert choices["temperature"].voice is None


def features(*flags: IntFlag) -> int:
    """The `supported_features` attribute of an entity that advertises `flags`."""
    return int(reduce(operator.or_, flags, 0))


def call(domain: str, service: str, **data: Any) -> TargetCall:
    """A call as the table builds it: the data has no entity id."""
    return TargetCall(domain, service, data)


@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        (
            {"hvac_mode": "cool", "temperature": 24.0},
            (
                call("climate", "set_hvac_mode", hvac_mode="cool"),
                call("climate", "set_temperature", temperature=24.0),
            ),
        ),
        (
            {"temperature": 22.0},
            (
                call("climate", "turn_on"),
                call("climate", "set_temperature", temperature=22.0),
            ),
        ),
        ({}, (call("climate", "turn_on"),)),
        (
            # The order of the calls is the table's, not the order of the settings.
            {"fan_mode": "low", "temperature": 24.0, "hvac_mode": "heat"},
            (
                call("climate", "set_hvac_mode", hvac_mode="heat"),
                call("climate", "set_temperature", temperature=24.0),
                call("climate", "set_fan_mode", fan_mode="low"),
            ),
        ),
    ],
)
def test_climate_turn_on_calls(
    settings: Settings, expected: tuple[TargetCall, ...]
) -> None:
    """Setting the HVAC mode turns a thermostat on, so it replaces the turn_on call."""
    assert behaviour_for(AC_ID).turn_on_calls(settings) == expected


def test_climate_apply_calls_never_turn_on() -> None:
    """Pushing settings onto a running thermostat sets them and nothing else."""
    behaviour = behaviour_for(AC_ID)

    assert behaviour.apply_calls({"temperature": 22.0}) == (
        call("climate", "set_temperature", temperature=22.0),
    )
    assert behaviour.apply_calls({"hvac_mode": "cool", "fan_mode": "low"}) == (
        call("climate", "set_hvac_mode", hvac_mode="cool"),
        call("climate", "set_fan_mode", fan_mode="low"),
    )


@pytest.mark.parametrize(
    ("entity_id", "settings"),
    [
        ("light.hall", {"brightness_pct": 40}),
        ("fan.ceiling", {"percentage": 50, "preset_mode": "auto"}),
    ],
)
def test_light_and_fan_settings_ride_in_turn_on(
    entity_id: str, settings: Settings
) -> None:
    """A light or a fan takes its settings together with turn_on, in one call."""
    domain = entity_id.split(".")[0]
    behaviour = behaviour_for(entity_id)

    assert behaviour.turn_on_calls(settings) == (call(domain, "turn_on", **settings),)
    assert behaviour.apply_calls(settings) == (call(domain, "turn_on", **settings),)


@pytest.mark.parametrize(
    ("entity_id", "settings", "setters"),
    [
        (
            "humidifier.room",
            {"humidity": 55, "mode": "away"},
            (
                call("humidifier", "set_humidity", humidity=55),
                call("humidifier", "set_mode", mode="away"),
            ),
        ),
        (
            "water_heater.tank",
            {"temperature": 55.0, "operation_mode": "eco"},
            (
                call("water_heater", "set_temperature", temperature=55.0),
                call("water_heater", "set_operation_mode", operation_mode="eco"),
            ),
        ),
    ],
)
def test_humidifier_and_water_heater_turn_on_then_set(
    entity_id: str, settings: Settings, setters: tuple[TargetCall, ...]
) -> None:
    """These domains turn on plainly and then set; a running one is only set."""
    domain = entity_id.split(".")[0]
    behaviour = behaviour_for(entity_id)

    assert behaviour.turn_on_calls(settings) == (call(domain, "turn_on"), *setters)
    assert behaviour.apply_calls(settings) == setters


@pytest.mark.parametrize("domain", [*SUPPORTED_DOMAINS, "kettle"])
def test_turning_on_without_settings_is_one_plain_call(domain: str) -> None:
    """No settings, no extra calls: the on service alone, and nothing to apply."""
    behaviour = behaviour_for_domain(domain)

    assert behaviour.turn_on_calls(NO_SETTINGS) == (
        TargetCall(*behaviour.on_service, {}),
    )
    assert behaviour.apply_calls(NO_SETTINGS) == ()


SAMPLE_SETTINGS: dict[str, str | float | int] = {
    "hvac_mode": "cool",
    "temperature": 22.0,
    "fan_mode": "low",
    "brightness_pct": 40.0,
    "percentage": 50,
    "preset_mode": "auto",
    "humidity": 50,
    "mode": "away",
    "operation_mode": "eco",
}
"""A value for every setting name any row has."""


def service_fields(domain: str, service: str) -> set[str]:
    """The fields Home Assistant's own services.yaml gives a service, sections
    flattened."""
    component = importlib.import_module(f"homeassistant.components.{domain}")
    assert component.__file__ is not None
    services = load_yaml(str(Path(component.__file__).parent / "services.yaml"))

    def names(fields: Mapping[str, Any]) -> set[str]:
        found: set[str] = set()
        for name, field in fields.items():
            found |= names(field["fields"]) if "fields" in field else {name}
        return found

    return names(services[service].get("fields", {}))


@pytest.mark.parametrize("domain", SUPPORTED_DOMAINS)
async def test_every_call_names_a_home_assistant_service(
    hass: HomeAssistant, domain: str
) -> None:
    """Whatever the table sends exists in the installed Home Assistant, with the
    fields it fills in."""
    behaviour = behaviour_for_domain(domain)
    settings = {name: SAMPLE_SETTINGS[name] for name in behaviour.setting_names}

    for sent in (*behaviour.turn_on_calls(settings), *behaviour.apply_calls(settings)):
        assert await async_setup_component(hass, sent.domain, {})
        assert hass.services.has_service(sent.domain, sent.service), (
            f"{sent.domain}.{sent.service} is not a Home Assistant service"
        )
        assert set(sent.data) <= service_fields(sent.domain, sent.service), (
            f"{sent.domain}.{sent.service} has no field {set(sent.data)}"
        )


@pytest.mark.parametrize(
    ("entity_id", "features", "expected"),
    [
        ("fan.ceiling", FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF, True),
        ("fan.ceiling", FanEntityFeature.TURN_ON, False),
        ("siren.yard", SirenEntityFeature.TURN_OFF, False),
        ("water_heater.tank", WaterHeaterEntityFeature.ON_OFF, True),
        ("switch.boiler", 0, True),
        # Features only: whether the domain may be a target is not its business.
        ("sensor.temp", 0, True),
    ],
)
async def test_switchability_follows_the_advertised_features(
    hass: HomeAssistant, entity_id: str, features: int, expected: bool
) -> None:
    """An entity can be switched when it advertises every feature its domain needs."""
    hass.states.async_set(entity_id, "off", {"supported_features": int(features)})

    assert switchable_by_features(hass, entity_id) is expected


async def test_switchability_of_an_entity_nobody_knows(hass: HomeAssistant) -> None:
    """A domain that needs features cannot vouch for an entity it cannot look up; one
    that needs none has nothing to look up."""
    assert not switchable_by_features(hass, "climate.nothing")
    assert switchable_by_features(hass, "switch.nothing")


async def test_valid_climate_settings_are_frozen(hass: HomeAssistant) -> None:
    """Settings that suit the thermostat come back as an immutable copy."""
    hass.states.async_set(AC_ID, "off", AC_ATTRS)
    values: dict[str, Any] = {"hvac_mode": "cool", "temperature": 24.0}

    settings = validate_settings(hass, AC_ID, values)

    assert settings == {"hvac_mode": "cool", "temperature": 24.0}
    with pytest.raises(TypeError):
        settings["fan_mode"] = "low"  # type: ignore[index]
    values["hvac_mode"] = "heat"
    assert settings["hvac_mode"] == "cool"


async def test_no_settings_need_no_entity(hass: HomeAssistant) -> None:
    """Nothing to check: an empty set is valid for any entity, even an unknown one."""
    assert validate_settings(hass, "climate.nothing", {}) == NO_SETTINGS


@pytest.mark.parametrize(
    ("entity_id", "attributes", "values"),
    [
        (
            "climate.ac",
            AC_ATTRS,
            {"hvac_mode": "heat", "temperature": 24.5, "fan_mode": "high"},
        ),
        (
            "light.hall",
            {"supported_color_modes": ["color_temp"]},
            {"brightness_pct": 40},
        ),
        (
            "fan.ceiling",
            {
                "supported_features": features(
                    FanEntityFeature.SET_SPEED, FanEntityFeature.PRESET_MODE
                ),
                "preset_modes": ["auto", "sleep"],
            },
            {"percentage": 50, "preset_mode": "sleep"},
        ),
        (
            "humidifier.room",
            {
                "supported_features": features(HumidifierEntityFeature.MODES),
                "min_humidity": 30,
                "max_humidity": 80,
                "available_modes": ["normal", "away"],
            },
            {"humidity": 55, "mode": "away"},
        ),
        (
            "water_heater.tank",
            {
                "supported_features": features(
                    WaterHeaterEntityFeature.TARGET_TEMPERATURE,
                    WaterHeaterEntityFeature.OPERATION_MODE,
                ),
                "min_temp": 30,
                "max_temp": 70,
                "operation_list": ["off", "eco", "performance"],
            },
            {"temperature": 55.0, "operation_mode": "eco"},
        ),
    ],
)
async def test_settings_the_entity_supports_are_accepted(
    hass: HomeAssistant,
    entity_id: str,
    attributes: Mapping[str, Any],
    values: dict[str, Any],
) -> None:
    """Every kind of setting is accepted when the entity says it can do it."""
    hass.states.async_set(entity_id, "off", attributes)

    assert validate_settings(hass, entity_id, values) == values


async def test_settings_not_taken_are_named_one_by_one_in_their_order(
    hass: HomeAssistant,
) -> None:
    """An AC that lost cooling and its fan modes, and tops out at 22 degrees. Each
    setting is judged alone, so the ones it still takes are not named with the others;
    a value out of its range is named too."""
    hass.states.async_set(
        AC_ID,
        "off",
        {
            **AC_ATTRS,
            "hvac_modes": ["off", "heat"],
            "supported_features": AC_WITHOUT_FAN_MODE,
            "max_temp": 22,
        },
    )
    cool_and_low: dict[str, Any] = {"hvac_mode": "cool", "fan_mode": "low"}

    assert settings_not_taken(hass, AC_ID, {**cool_and_low, "temperature": 20}) == (
        "hvac_mode",
        "fan_mode",
    )
    assert settings_not_taken(hass, AC_ID, {"temperature": 24, **cool_and_low}) == (
        "temperature",
        "hvac_mode",
        "fan_mode",
    )
    assert settings_not_taken(hass, AC_ID, {"hvac_mode": "heat"}) == ()
    assert settings_not_taken(hass, AC_ID, NO_SETTINGS) == ()
    assert settings_not_taken(hass, "climate.nothing", {"hvac_mode": "heat"}) == (
        "hvac_mode",
    )


SET_SPEED = features(FanEntityFeature.SET_SPEED)
PRESET_MODE = features(FanEntityFeature.PRESET_MODE)


@pytest.mark.parametrize(
    ("entity_id", "attributes", "values"),
    [
        ("climate.ac", AC_ATTRS, {"temperature": 16}),
        ("climate.ac", AC_ATTRS, {"temperature": 30}),
        (
            "light.hall",
            {"supported_color_modes": ["brightness"]},
            {"brightness_pct": 1},
        ),
        (
            "light.hall",
            {"supported_color_modes": ["brightness"]},
            {"brightness_pct": 100},
        ),
        ("fan.ceiling", {"supported_features": SET_SPEED}, {"percentage": 1}),
        ("fan.ceiling", {"supported_features": SET_SPEED}, {"percentage": 100}),
        ("humidifier.room", {"min_humidity": 30, "max_humidity": 80}, {"humidity": 30}),
        ("humidifier.room", {"min_humidity": 30, "max_humidity": 80}, {"humidity": 80}),
    ],
)
async def test_values_at_the_limits_are_accepted(
    hass: HomeAssistant,
    entity_id: str,
    attributes: Mapping[str, Any],
    values: dict[str, Any],
) -> None:
    """A range includes both of its ends."""
    hass.states.async_set(entity_id, "off", attributes)

    assert validate_settings(hass, entity_id, values) == values


NUMBER_SETTINGS = [
    pytest.param("climate.ac", AC_ATTRS, "temperature", id="climate temperature"),
    pytest.param(
        "light.hall",
        {"supported_color_modes": ["brightness"]},
        "brightness_pct",
        id="light brightness",
    ),
    pytest.param(
        "fan.ceiling", {"supported_features": SET_SPEED}, "percentage", id="fan speed"
    ),
    pytest.param(
        "humidifier.room",
        {"min_humidity": 30, "max_humidity": 80},
        "humidity",
        id="humidity",
    ),
    pytest.param(
        "water_heater.tank",
        {
            "supported_features": features(WaterHeaterEntityFeature.TARGET_TEMPERATURE),
            "min_temp": 30,
            "max_temp": 70,
        },
        "temperature",
        id="water heater temperature",
    ),
]
"""Every setting that is a number, on an entity that takes it."""


@pytest.mark.parametrize(("entity_id", "attributes", "setting"), NUMBER_SETTINGS)
@pytest.mark.parametrize("flag", [True, False])
async def test_number_settings_refuse_booleans(
    hass: HomeAssistant,
    entity_id: str,
    attributes: Mapping[str, Any],
    setting: str,
    flag: bool,
) -> None:
    """Python counts `true` as 1, which no light, fan or thermostat is turned on with:
    whoever asks, a service, a voice or an agent, is refused, since this is where every
    one of them is judged."""
    hass.states.async_set(entity_id, "off", attributes)

    with pytest.raises(ServiceValidationError) as err:
        validate_settings(hass, entity_id, {setting: flag})

    assert err.value.translation_key == "setting_out_of_range"
    # Shown to the person as the word that was said, not as Python spells it.
    assert err.value.translation_placeholders is not None
    assert err.value.translation_placeholders["value"] == str(flag).lower()


@pytest.mark.parametrize(
    ("entity_id", "attributes", "setting", "value"),
    [
        ("fan.ceiling", {"supported_features": SET_SPEED}, "percentage", 50.0),
        ("humidifier.room", {"min_humidity": 30, "max_humidity": 80}, "humidity", 55.0),
        (
            "light.hall",
            {"supported_color_modes": ["brightness"]},
            "brightness_pct",
            12.5,
        ),
        ("climate.ac", AC_ATTRS, "temperature", 24.5),
    ],
)
async def test_a_number_that_is_whole_is_whole_in_any_form(
    hass: HomeAssistant,
    entity_id: str,
    attributes: Mapping[str, Any],
    setting: str,
    value: float,
) -> None:
    """A voice hears 50 as 50.0; a speed of 50.0 is a speed of 50, and a brightness or a
    temperature may have a fraction."""
    hass.states.async_set(entity_id, "off", attributes)

    assert validate_settings(hass, entity_id, {setting: value}) == {setting: value}


NO_TEMPERATURE = {
    **AC_ATTRS,
    "supported_features": features(
        ClimateEntityFeature.TURN_ON, ClimateEntityFeature.TURN_OFF
    ),
}


@pytest.mark.parametrize(
    ("entity_id", "attributes", "values", "key"),
    [
        ("climate.ac", AC_ATTRS, {"hvac_mode": "off"}, "setting_not_an_option"),
        ("climate.ac", AC_ATTRS, {"hvac_mode": "dry"}, "setting_not_an_option"),
        ("climate.ac", AC_ATTRS, {"fan_mode": "turbo"}, "setting_not_an_option"),
        ("climate.ac", AC_ATTRS, {"temperature": 31}, "setting_out_of_range"),
        ("climate.ac", AC_ATTRS, {"temperature": 15.9}, "setting_out_of_range"),
        ("climate.ac", AC_ATTRS, {"brightness_pct": 50}, "setting_not_supported"),
        ("climate.ac", NO_TEMPERATURE, {"temperature": 22}, "setting_not_supported"),
        ("climate.ac", NO_TEMPERATURE, {"fan_mode": "low"}, "setting_not_supported"),
        # An entity that does not say which modes it has cannot be asked for one,
        # and one that can only be off has no mode to turn on in.
        ("climate.ac", {}, {"hvac_mode": "cool"}, "setting_not_supported"),
        (
            "climate.ac",
            {**AC_ATTRS, "hvac_modes": ["off"]},
            {"hvac_mode": "cool"},
            "setting_not_supported",
        ),
        (
            "water_heater.tank",
            {
                "supported_features": features(WaterHeaterEntityFeature.OPERATION_MODE),
                "operation_list": ["off"],
            },
            {"operation_mode": "eco"},
            "setting_not_supported",
        ),
        # Types are the schema's business at the services, but a caller that skips
        # the schema gets an error the user can read, not a TypeError.
        ("climate.ac", AC_ATTRS, {"temperature": "24"}, "setting_out_of_range"),
        ("climate.ac", AC_ATTRS, {"temperature": True}, "setting_out_of_range"),
        ("climate.ac", AC_ATTRS, {"fan_mode": 3}, "setting_not_an_option"),
        # A part of a percent is not a speed or a humidity: the services say whole
        # numbers, and so does every other way in.
        (
            "fan.ceiling",
            {"supported_features": SET_SPEED},
            {"percentage": 50.5},
            "setting_out_of_range",
        ),
        (
            "humidifier.room",
            {"min_humidity": 30, "max_humidity": 80},
            {"humidity": 55.5},
            "setting_out_of_range",
        ),
        (
            "light.hall",
            {"supported_color_modes": ["brightness"]},
            {"brightness_pct": True},
            "setting_out_of_range",
        ),
        (
            "light.hall",
            {"supported_color_modes": ["onoff"]},
            {"brightness_pct": 50},
            "setting_not_supported",
        ),
        (
            "light.hall",
            {"supported_color_modes": ["brightness"]},
            {"brightness_pct": 0},
            "setting_out_of_range",
        ),
        (
            "light.hall",
            {"supported_color_modes": ["brightness"]},
            {"brightness_pct": 101},
            "setting_out_of_range",
        ),
        (
            "fan.ceiling",
            {"supported_features": 0},
            {"percentage": 50},
            "setting_not_supported",
        ),
        (
            "fan.ceiling",
            {"supported_features": SET_SPEED},
            {"percentage": 0},
            "setting_out_of_range",
        ),
        (
            "fan.ceiling",
            {"supported_features": PRESET_MODE, "preset_modes": ["auto"]},
            {"preset_mode": "sleep"},
            "setting_not_an_option",
        ),
        (
            "fan.ceiling",
            {"supported_features": SET_SPEED, "preset_modes": ["auto"]},
            {"preset_mode": "auto"},
            "setting_not_supported",
        ),
        (
            "humidifier.room",
            {"min_humidity": 30, "max_humidity": 80},
            {"humidity": 90},
            "setting_out_of_range",
        ),
        ("humidifier.room", {}, {"humidity": 50}, "setting_not_supported"),
        (
            "humidifier.room",
            {"supported_features": 0, "available_modes": ["away"]},
            {"mode": "away"},
            "setting_not_supported",
        ),
        (
            "water_heater.tank",
            {
                "supported_features": features(
                    WaterHeaterEntityFeature.TARGET_TEMPERATURE,
                    WaterHeaterEntityFeature.OPERATION_MODE,
                ),
                "operation_list": ["off", "eco"],
            },
            {"operation_mode": "off"},
            "setting_not_an_option",
        ),
        (
            "water_heater.tank",
            {
                "supported_features": features(
                    WaterHeaterEntityFeature.TARGET_TEMPERATURE
                ),
                "min_temp": 30,
                "max_temp": 70,
            },
            {"temperature": 75},
            "setting_out_of_range",
        ),
        ("switch.boiler", {}, {"temperature": 20}, "setting_not_supported"),
        ("sensor.temp", {}, {"temperature": 20}, "setting_not_supported"),
    ],
)
async def test_invalid_settings_are_rejected(
    hass: HomeAssistant,
    entity_id: str,
    attributes: Mapping[str, Any],
    values: dict[str, Any],
    key: str,
) -> None:
    """A setting the entity cannot take, or a value it cannot accept, is refused with
    the reason, when the command is made."""
    hass.states.async_set(entity_id, "off", attributes)

    with pytest.raises(ServiceValidationError) as err:
        validate_settings(hass, entity_id, values)

    assert err.value.translation_key == key
    assert err.value.translation_domain == DOMAIN


async def test_one_bad_setting_rejects_all(hass: HomeAssistant) -> None:
    """Settings are all valid or none is kept."""
    hass.states.async_set(AC_ID, "off", AC_ATTRS)

    with pytest.raises(ServiceValidationError) as err:
        validate_settings(hass, AC_ID, {"hvac_mode": "cool", "temperature": 99})

    assert err.value.translation_key == "setting_out_of_range"


@pytest.mark.parametrize(
    ("values", "key", "placeholders"),
    [
        (
            {"brightness_pct": 50},
            "setting_not_supported",
            {"target": "Air conditioner", "setting": "brightness_pct"},
        ),
        (
            {"temperature": 31},
            "setting_out_of_range",
            {"setting": "temperature", "value": "31", "min": "16", "max": "30"},
        ),
        (
            {"temperature": 15.5},
            "setting_out_of_range",
            {"setting": "temperature", "value": "15.5", "min": "16", "max": "30"},
        ),
        (
            {"fan_mode": "turbo"},
            "setting_not_an_option",
            {"setting": "fan_mode", "value": "turbo", "options": "auto, low, high"},
        ),
        (
            {"hvac_mode": "off"},
            "setting_not_an_option",
            {"setting": "hvac_mode", "value": "off", "options": "heat, cool, fan_only"},
        ),
    ],
)
async def test_rejection_tells_the_user_what_is_wrong(
    hass: HomeAssistant,
    values: dict[str, Any],
    key: str,
    placeholders: dict[str, str],
) -> None:
    """The message names the target, the setting and what would have been fine."""
    hass.states.async_set(
        AC_ID, "off", {**AC_ATTRS, "friendly_name": "Air conditioner"}
    )

    with pytest.raises(ServiceValidationError) as err:
        validate_settings(hass, AC_ID, values)

    assert err.value.translation_placeholders == placeholders
    texts = await async_get_translations(hass, "en", "exceptions", [DOMAIN])
    message = texts[f"component.{DOMAIN}.exceptions.{key}.message"]
    assert all(
        value in message.format(**placeholders) for value in placeholders.values()
    )


async def test_settings_validate_while_unavailable(hass: HomeAssistant) -> None:
    """Home Assistant keeps the capabilities on an unavailable state, so a command can
    be made for a thermostat that is offline."""
    hass.states.async_set(AC_ID, "unavailable", AC_ATTRS)

    settings = validate_settings(hass, AC_ID, {"hvac_mode": "cool", "temperature": 24})

    assert settings == {"hvac_mode": "cool", "temperature": 24}
    with pytest.raises(ServiceValidationError) as err:
        validate_settings(hass, AC_ID, {"temperature": 31})
    assert err.value.translation_key == "setting_out_of_range"


async def test_settings_validate_from_registry_without_state(
    hass: HomeAssistant,
) -> None:
    """A disabled entity has no state; what the registry recorded of it decides."""
    capabilities = {k: v for k, v in AC_ATTRS.items() if k != "supported_features"}
    er.async_get(hass).async_get_or_create(
        "climate",
        "tester",
        "ac",
        suggested_object_id="ac",
        capabilities=capabilities,
        supported_features=AC_ATTRS["supported_features"],
    )
    assert hass.states.get(AC_ID) is None

    settings = validate_settings(hass, AC_ID, {"hvac_mode": "cool", "temperature": 24})

    assert settings == {"hvac_mode": "cool", "temperature": 24}
    with pytest.raises(ServiceValidationError) as err:
        validate_settings(hass, AC_ID, {"fan_mode": "turbo"})
    assert err.value.translation_key == "setting_not_an_option"


async def test_settings_of_an_unknown_entity_are_not_supported(
    hass: HomeAssistant,
) -> None:
    """An entity in neither the state machine nor the registry says nothing about what
    it can do, so no setting is taken for it."""
    with pytest.raises(ServiceValidationError) as err:
        validate_settings(hass, "climate.nothing", {"temperature": 22})

    assert err.value.translation_key == "setting_not_supported"
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_placeholders == {
        "target": "climate.nothing",
        "setting": "temperature",
    }
