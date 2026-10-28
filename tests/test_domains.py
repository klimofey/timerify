"""The per-domain table tells what "on" means for an entity and how to switch it."""

import pytest
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component

from custom_components.timerify.domains import (
    SUPPORTED_DOMAINS,
    Actual,
    actual_state,
    behaviour_for,
)


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
    "entity_id", ["sensor.temp", "binary_sensor.door", "cover.gate"]
)
def test_unsupported_domain_raises(entity_id: str) -> None:
    """A domain without a table row is refused instead of guessed."""
    with pytest.raises(ValueError, match="not supported"):
        behaviour_for(entity_id)


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
