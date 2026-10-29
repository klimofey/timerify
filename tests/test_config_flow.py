"""Adding, changing and removing a timer as the user does on the integration page."""

import uuid
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant import config_entries
from homeassistant.components.climate.const import ClimateEntityFeature
from homeassistant.components.fan.const import FanEntityFeature
from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from homeassistant.components.siren.const import SirenEntityFeature
from homeassistant.components.water_heater.const import WaterHeaterEntityFeature
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResult, FlowResultType, InvalidData
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations
from homeassistant.setup import async_setup_component

from custom_components.timerify.const import (
    CONF_DEFAULT_DURATION,
    CONF_MODE,
    CONF_TARGET,
    DEFAULT_DURATION_MINUTES,
    DOMAIN,
    MAX_MINUTES,
    Mode,
)
from custom_components.timerify.domains import SUPPORTED_DOMAINS

from .conftest import SWITCH_SERVICES, FakeTarget, ProvideTarget, SetupTarget
from .helpers import (
    NUMBER,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    advance,
    set_number,
    state_of,
    storage_key,
)

pytestmark = pytest.mark.usefixtures("hass_storage")


async def start_flow(hass: HomeAssistant) -> FlowResult:
    """Press "Add entry" on the integration page."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def submit(
    hass: HomeAssistant, result: FlowResult, user_input: dict[str, Any]
) -> FlowResult:
    """Fill in the form `result` shows and submit it."""
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


async def add_target(
    hass: HomeAssistant,
    target: str = TARGET_ID,
    mode: Mode = "strict",
    default_duration: int = 45,
) -> ConfigEntry:
    """Add a timer through the whole flow and return its config entry."""
    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: target, CONF_MODE: mode}
    )
    if mode == "strict":
        result = await submit(hass, result, {CONF_DEFAULT_DURATION: default_duration})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["result"]


def suggested_value(result: FlowResult, key: str) -> Any:
    """The value the form shows in the field `key` before the user touches it."""
    marker = next(marker for marker in result["data_schema"].schema if marker == key)
    return marker.description["suggested_value"]


def default_value(result: FlowResult, key: str) -> Any:
    """The value the form submits for the field `key` when the user leaves it alone."""
    marker = next(marker for marker in result["data_schema"].schema if marker == key)
    default = marker.default
    return default() if callable(default) else default


def picker_of(result: FlowResult) -> dict[str, Any]:
    """The entity picker of the form `result` shows, as the frontend gets it."""
    (marker,) = (key for key in result["data_schema"].schema if key == CONF_TARGET)
    return result["data_schema"].schema[marker].serialize()["selector"]["entity"]


async def _ignore(_call: ServiceCall) -> None:
    """A service that does nothing."""


def provide_services(hass: HomeAssistant, domain: str, *services: str) -> None:
    """Register `services` of `domain`, as the integration of that domain does."""
    for service in services:
        hass.services.async_register(domain, service, _ignore)


@pytest.fixture
def kettle(provide_target: ProvideTarget) -> FakeTarget:
    """`kettle.tea` on a device called Tea, switched off: a domain Timerify has no row
    for, whose services are `kettle.turn_on` and `kettle.turn_off`."""
    return provide_target("kettle.tea", SWITCH_SERVICES, name="Tea")


async def change_options(
    hass: HomeAssistant, entry: ConfigEntry, *steps: dict[str, Any]
) -> FlowResult:
    """Open the entry's settings, submit a form per step; return the last result."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    for user_input in steps:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input
        )
    await hass.async_block_till_done()
    return result


async def test_add_strict_target_in_two_steps(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """Strict mode asks for the default duration after the target and mode."""
    result = await start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await submit(hass, result, {CONF_TARGET: TARGET_ID, CONF_MODE: "strict"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "duration"

    result = await submit(hass, result, {CONF_DEFAULT_DURATION: 45})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Boiler"
    assert result["options"] == {
        CONF_TARGET: TARGET_ID,
        CONF_MODE: "strict",
        CONF_DEFAULT_DURATION: 45,
    }
    await hass.async_block_till_done()
    assert result["result"].state is ConfigEntryState.LOADED
    assert state_of(hass, NUMBER) == "0"


async def test_add_loose_target_skips_duration(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """Loose mode has no use for a default duration, so none is asked or stored."""
    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: TARGET_ID, CONF_MODE: "loose"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_TARGET: TARGET_ID, CONF_MODE: "loose"}


async def test_add_target_with_every_default_takes_three_clicks(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """Pick the entity and accept both forms as they are: strict, 30 minutes."""
    result = await submit(hass, await start_flow(hass), {CONF_TARGET: TARGET_ID})
    result = await submit(hass, result, {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        CONF_TARGET: TARGET_ID,
        CONF_MODE: "strict",
        CONF_DEFAULT_DURATION: DEFAULT_DURATION_MINUTES,
    }


async def test_target_is_identified_by_its_registry_id(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """The entry's unique id is the registry id, which survives renames."""
    entry = await add_target(hass, mode="loose")

    registered = er.async_get(hass).async_get(TARGET_ID)
    assert registered is not None
    assert entry.unique_id == registered.id


async def test_same_target_twice_aborts(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """A target has one timer."""
    await add_target(hass, mode="loose")

    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: TARGET_ID, CONF_MODE: "strict"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_second_flow_for_a_target_aborts_while_the_first_is_open(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """Two browser tabs adding the same target: the second is told one is under way,
    in words the user can read."""
    first = await submit(
        hass, await start_flow(hass), {CONF_TARGET: TARGET_ID, CONF_MODE: "strict"}
    )
    assert first["step_id"] == "duration"

    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: TARGET_ID, CONF_MODE: "strict"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"
    texts = await async_get_translations(hass, "en", "config", [DOMAIN])
    assert texts[f"component.{DOMAIN}.config.abort.already_in_progress"]


async def test_renamed_target_is_still_the_same_target(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """Adding a target under its new entity id does not give it a second timer."""
    await add_target(hass, mode="loose")
    er.async_get(hass).async_update_entity(TARGET_ID, new_entity_id="switch.heater")
    await hass.async_block_till_done()

    result = await submit(
        hass,
        await start_flow(hass),
        {CONF_TARGET: "switch.heater", CONF_MODE: "loose"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_target_without_registry_entry_is_identified_by_entity_id(
    hass: HomeAssistant,
) -> None:
    """A YAML-defined entity has no registry id; its entity id stands in."""
    hass.states.async_set("switch.heater", "off")

    entry = await add_target(hass, target="switch.heater", mode="loose")

    assert entry.unique_id == "switch.heater"
    result = await submit(
        hass,
        await start_flow(hass),
        {CONF_TARGET: "switch.heater", CONF_MODE: "loose"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_registry_id_is_stored_as_the_entity_id(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """The entity selector also takes a registry id; the entry keeps the entity id."""
    registered = er.async_get(hass).async_get(TARGET_ID)
    assert registered is not None

    entry = await add_target(hass, target=registered.id, mode="loose")

    assert entry.options[CONF_TARGET] == TARGET_ID
    assert entry.title == "Boiler"


@pytest.mark.parametrize(
    ("entity_id", "features"),
    [
        ("climate.heating", 0),
        ("climate.heating", ClimateEntityFeature.TURN_ON),
        ("climate.heating", ClimateEntityFeature.TURN_OFF),
        ("water_heater.tank", 0),
        ("water_heater.tank", WaterHeaterEntityFeature.TARGET_TEMPERATURE),
        ("fan.ceiling", 0),
        ("fan.ceiling", FanEntityFeature.TURN_ON),
        ("media_player.tv", 0),
        ("media_player.tv", MediaPlayerEntityFeature.TURN_OFF),
        ("siren.yard", 0),
        ("siren.yard", SirenEntityFeature.TURN_ON),
    ],
)
async def test_entity_that_cannot_be_turned_on_and_off_is_rejected(
    hass: HomeAssistant, entity_id: str, features: int
) -> None:
    """A thermostat that only has a mode, or a fan, player or siren that cannot be
    switched, is not a target; the form says so."""
    hass.states.async_set(entity_id, "off", {"supported_features": int(features)})

    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: entity_id, CONF_MODE: "strict"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "target_not_supported"}


@pytest.mark.parametrize(
    ("entity_id", "features"),
    [
        (
            "climate.heating",
            ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF,
        ),
        ("water_heater.tank", WaterHeaterEntityFeature.ON_OFF),
        ("fan.ceiling", FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF),
        (
            "media_player.tv",
            MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF,
        ),
        ("siren.yard", SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF),
        ("light.hall", 0),
    ],
)
async def test_entity_that_can_be_turned_on_and_off_is_accepted(
    hass: HomeAssistant, entity_id: str, features: int
) -> None:
    """Entities qualify when they advertise the features their domain's turn_on and
    turn_off need; a light needs none."""
    hass.states.async_set(entity_id, "off", {"supported_features": int(features)})

    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: entity_id, CONF_MODE: "strict"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "duration"


async def test_entity_without_a_state_is_judged_by_its_registry_entry(
    hass: HomeAssistant,
) -> None:
    """A disabled entity has no state; what the registry knows of it decides."""
    registry = er.async_get(hass)
    both = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
    registry.async_get_or_create(
        "climate", "tester", "ok", suggested_object_id="ok", supported_features=both
    )
    registry.async_get_or_create(
        "climate",
        "tester",
        "half",
        suggested_object_id="half",
        supported_features=ClimateEntityFeature.TURN_ON,
    )
    result = await start_flow(hass)

    for target in ("climate.half", "climate.nothing"):
        result = await submit(hass, result, {CONF_TARGET: target, CONF_MODE: "strict"})
        assert result["errors"] == {"base": "target_not_supported"}

    result = await submit(
        hass, result, {CONF_TARGET: "climate.ok", CONF_MODE: "strict"}
    )
    assert result["step_id"] == "duration"


async def test_registry_id_of_an_unsupported_entity_is_rejected(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """The selector only checks the domain of entity ids, not of registry ids."""
    temperature = er.async_get(hass).async_get_or_create(
        "sensor", "boiler_maker", "temperature"
    )
    result = await start_flow(hass)

    for target in (temperature.id, uuid.uuid4().hex):
        result = await submit(hass, result, {CONF_TARGET: target, CONF_MODE: "strict"})

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "target_not_supported"}


@pytest.mark.parametrize(
    ("domain", "services"),
    [("sensor", ()), ("scene_like", ("turn_on",)), ("scene_like", ("turn_off",))],
)
async def test_domain_without_turn_on_and_off_is_not_supported(
    hass: HomeAssistant, domain: str, services: tuple[str, ...]
) -> None:
    """A sensor, or a domain that can only be turned on or only off, is no target,
    although the entity reads "on": the state is not what decides."""
    provide_services(hass, domain, *services)
    entity = er.async_get(hass).async_get_or_create(domain, "tester", "temp")
    hass.states.async_set(entity.entity_id, "on")

    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: entity.id, CONF_MODE: "strict"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "target_not_supported"}


@pytest.mark.parametrize("state", ["on", "off"])
async def test_fallback_entity_in_on_off_state_is_accepted(
    hass: HomeAssistant, kettle: FakeTarget, state: str
) -> None:
    """An entity of a domain without a row is a target while it reads on or off."""
    await kettle.set_state(state)

    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: "kettle.tea", CONF_MODE: "strict"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "duration"


@pytest.mark.parametrize("state", ["idle", "streaming", "unavailable", "unknown"])
async def test_fallback_entity_in_other_state_is_rejected(
    hass: HomeAssistant, kettle: FakeTarget, state: str
) -> None:
    """A camera is idle or streaming, and an entity that does not answer has no state
    to read: a timer could not tell on from off, so the form says to pick another."""
    await kettle.set_state(state)

    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: "kettle.tea", CONF_MODE: "strict"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "not_switchable"}


async def test_fallback_entity_without_a_state_is_rejected(
    hass: HomeAssistant, kettle: FakeTarget
) -> None:
    """A registered entity that has no state, a disabled one, cannot be read either."""
    hass.states.async_remove("kettle.tea")

    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: "kettle.tea", CONF_MODE: "strict"}
    )

    assert result["errors"] == {"base": "not_switchable"}


@pytest.mark.parametrize(
    ("state", "step_id", "errors"),
    [
        ("on", "duration", None),
        ("off", "duration", None),
        ("open", "user", {"base": "not_switchable"}),
        ("home", "user", {"base": "not_switchable"}),
        ("unavailable", "user", {"base": "not_switchable"}),
    ],
)
async def test_group_is_judged_by_its_state(
    hass: HomeAssistant, state: str, step_id: str, errors: dict[str, str] | None
) -> None:
    """A group of lights reads on or off; one of covers or locks reports open or home,
    which a timer would read as off, so such a group is refused."""
    hass.states.async_set("group.shutters", state)

    result = await submit(
        hass,
        await start_flow(hass),
        {CONF_TARGET: "group.shutters", CONF_MODE: "strict"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id
    assert result["errors"] == errors


@pytest.mark.parametrize(
    ("entity_id", "state", "features"),
    [
        (
            "climate.heating",
            "heat",
            ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF,
        ),
        ("water_heater.tank", "eco", WaterHeaterEntityFeature.ON_OFF),
        (
            "media_player.tv",
            "playing",
            MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF,
        ),
        ("switch.heater", "unavailable", 0),
    ],
)
async def test_table_domain_is_not_judged_by_its_state(
    hass: HomeAssistant, entity_id: str, state: str, features: int
) -> None:
    """A thermostat heats, a player plays, and a switch may be out of reach for now:
    their state says nothing against them."""
    hass.states.async_set(entity_id, state, {"supported_features": int(features)})

    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: entity_id, CONF_MODE: "strict"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "duration"


async def test_not_switchable_is_explained_in_words(hass: HomeAssistant) -> None:
    """The form shows a text for the error, not its key."""
    texts = await async_get_translations(hass, "en", "config", [DOMAIN])

    assert texts[f"component.{DOMAIN}.config.error.not_switchable"]


async def test_fallback_target_runs_through_homeassistant_services(
    hass: HomeAssistant, kettle: FakeTarget
) -> None:
    """A kettle is added from the picker and run for ten minutes; homeassistant.turn_on
    passes the call on to the kettle's own domain. Switching it off by hand clears the
    timer without another call."""
    await async_setup_component(hass, "homeassistant", {})
    await add_target(hass, target="kettle.tea", mode="strict")

    await set_number(hass, "number.tea_run_for", 10)

    assert kettle.state == "on"
    assert kettle.calls == [("turn_on", ["kettle.tea"])]

    await kettle.set_state("off")

    assert state_of(hass, "number.tea_run_for") == "0"
    assert kettle.calls == [("turn_on", ["kettle.tea"])]


async def test_picker_offers_only_entities_that_can_be_switched(
    hass: HomeAssistant,
) -> None:
    """The entity picker lists the supported domains; of the climate, water heater,
    fan, media player and siren entities only those that advertise turning on and
    off."""
    picker = picker_of(await start_flow(hass))

    assert picker["domain"] == list(SUPPORTED_DOMAINS)
    on_off = {
        "climate": [ClimateEntityFeature.TURN_ON, ClimateEntityFeature.TURN_OFF],
        "water_heater": [WaterHeaterEntityFeature.ON_OFF],
        "fan": [FanEntityFeature.TURN_ON, FanEntityFeature.TURN_OFF],
        "media_player": [
            MediaPlayerEntityFeature.TURN_ON,
            MediaPlayerEntityFeature.TURN_OFF,
        ],
        "siren": [SirenEntityFeature.TURN_ON, SirenEntityFeature.TURN_OFF],
    }
    filtered = {
        f["domain"][0]: f["supported_features"]
        for f in picker["filter"]
        if "supported_features" in f
    }
    assert filtered == on_off
    unfiltered = [f for f in picker["filter"] if "supported_features" not in f]
    assert len(unfiltered) == 1
    assert set(unfiltered[0]["domain"]) == set(SUPPORTED_DOMAINS) - set(on_off)


async def test_picker_offers_domains_that_can_be_turned_on_and_off(
    hass: HomeAssistant,
) -> None:
    """A domain Timerify has no row for is offered when it has both a turn_on and a
    turn_off service, whatever it is called: not one that can only be turned on, not
    homeassistant itself, and no domain twice."""
    await async_setup_component(hass, "homeassistant", {})
    provide_services(hass, "kettle", "turn_on", "turn_off")
    provide_services(hass, "aquarium", "turn_off", "turn_on")
    provide_services(hass, "switch", "turn_on", "turn_off")
    provide_services(hass, "scene_like", "turn_on")

    picker = picker_of(await start_flow(hass))

    offered = [*SUPPORTED_DOMAINS, "aquarium", "kettle"]
    assert picker["domain"] == offered
    featured = {f["domain"][0] for f in picker["filter"] if "supported_features" in f}
    assert featured == {"climate", "water_heater", "fan", "media_player", "siren"}
    unfiltered = [f for f in picker["filter"] if "supported_features" not in f]
    assert len(unfiltered) == 1
    assert unfiltered[0]["domain"] == [d for d in offered if d not in featured]


@pytest.mark.parametrize("minutes", [0, MAX_MINUTES + 1])
async def test_duration_outside_the_range_is_rejected(
    hass: HomeAssistant, fake_target: FakeTarget, minutes: int
) -> None:
    """A timer lasts at least a minute and at most a day."""
    result = await submit(hass, await start_flow(hass), {CONF_TARGET: TARGET_ID})

    with pytest.raises(InvalidData):
        await submit(hass, result, {CONF_DEFAULT_DURATION: minutes})


async def test_duration_must_be_whole_minutes(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """Minutes are the unit of the timer, so a fraction of one is refused."""
    result = await submit(hass, await start_flow(hass), {CONF_TARGET: TARGET_ID})

    result = await submit(hass, result, {CONF_DEFAULT_DURATION: 1.5})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "duration"
    assert result["errors"] == {"base": "duration_not_whole"}


async def test_options_change_mode_keeps_running_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Saving the settings reloads the entry; the countdown carries on."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 30)
    await advance(hass, freezer, minutes=10)

    result = await change_options(hass, entry, {CONF_MODE: "loose"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_MODE] == "loose"
    assert entry.state is ConfigEntryState.LOADED
    assert state_of(hass, NUMBER) == "20"
    await advance(hass, freezer, minutes=20)
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_options_switching_to_loose_needs_no_duration(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """Leaving strict mode ends the flow at once."""
    entry = await add_target(hass, mode="strict")

    result = await change_options(hass, entry, {CONF_MODE: "loose"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_MODE] == "loose"
    await fake_target.set_state("on")
    assert state_of(hass, NUMBER) == "0"


async def test_options_switching_to_strict_asks_for_the_duration(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """A loose entry has no default duration yet; strict mode needs one."""
    entry = await add_target(hass, mode="loose")
    assert CONF_DEFAULT_DURATION not in entry.options

    result = await change_options(hass, entry, {CONF_MODE: "strict"})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "duration"
    assert default_value(result, CONF_DEFAULT_DURATION) == DEFAULT_DURATION_MINUTES

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEFAULT_DURATION: 20}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_TARGET: TARGET_ID,
        CONF_MODE: "strict",
        CONF_DEFAULT_DURATION: 20,
    }
    await fake_target.set_state("on")
    assert state_of(hass, NUMBER) == "20"


async def test_options_show_the_current_settings(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The forms open with what the entry has now."""
    entry = await setup_target(mode="strict", default_duration=45)

    result = await change_options(hass, entry)
    assert result["step_id"] == "init"
    assert suggested_value(result, CONF_MODE) == "strict"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_MODE: "strict"}
    )
    assert result["step_id"] == "duration"
    assert suggested_value(result, CONF_DEFAULT_DURATION) == 45


async def test_options_change_default_duration(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A target switched on from outside gets the new default duration."""
    entry = await setup_target(mode="strict", default_duration=45)

    await change_options(
        hass, entry, {CONF_MODE: "strict"}, {CONF_DEFAULT_DURATION: 20}
    )

    assert entry.options[CONF_DEFAULT_DURATION] == 20
    await fake_target.set_state("on")
    assert state_of(hass, NUMBER) == "20"


async def test_removing_entry_deletes_stored_state(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """Deleting a timer leaves no file of its state behind."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 30)
    key = storage_key(entry)
    assert key in hass_storage

    await hass.config_entries.async_remove(entry.entry_id)

    assert key not in hass_storage
