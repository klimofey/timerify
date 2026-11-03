"""Adding, changing and removing a timer as the user does on the integration page."""

import uuid
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.climate.const import ClimateEntityFeature
from homeassistant.components.fan.const import FanEntityFeature
from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from homeassistant.components.siren.const import SirenEntityFeature
from homeassistant.components.water_heater.const import WaterHeaterEntityFeature
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResult, FlowResultType, InvalidData
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations
from homeassistant.setup import async_setup_component

from custom_components.timerify.const import (
    CONF_DEFAULT_DURATION,
    CONF_LIMIT,
    CONF_MODE,
    CONF_OFF_BUTTON,
    CONF_RUN_FOR_MAX,
    CONF_RUNTIME,
    CONF_TARGET,
    CONF_WORKDAY_SENSOR,
    DEFAULT_DURATION_MINUTES,
    DOMAIN,
    MAX_MINUTES,
)
from custom_components.timerify.domains import SUPPORTED_DOMAINS

from .conftest import (
    SWITCH_SERVICES,
    FakeTarget,
    FakeWorkday,
    ProvideTarget,
    SetupTarget,
)
from .helpers import (
    BUTTON,
    NUMBER,
    RUNTIME,
    SENSOR,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    add_interval,
    add_target,
    advance,
    change_options,
    prefilled,
    set_number,
    start_flow,
    state_of,
    storage_key,
    submit,
)

pytestmark = pytest.mark.usefixtures("hass_storage")


def suggested_value(result: FlowResult, key: str) -> Any:
    """The value the form shows in the field `key` before the user touches it."""
    marker = next(marker for marker in result["data_schema"].schema if marker == key)
    return marker.description["suggested_value"]


def default_value(result: FlowResult, key: str) -> Any:
    """The value the form submits for the field `key` when the user leaves it alone."""
    marker = next(marker for marker in result["data_schema"].schema if marker == key)
    default = marker.default
    return default() if callable(default) else default


def selector_of(result: FlowResult, key: str) -> dict[str, Any]:
    """The selector of the field `key` of the form `result` shows, as the frontend
    gets it."""
    schema = result["data_schema"].schema
    marker = next(marker for marker in schema if marker == key)
    selector: dict[str, Any] = schema[marker].serialize()["selector"]
    return selector


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


async def test_add_strict_target_in_two_steps(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """Strict mode asks for the default duration after the target and mode."""
    result = await start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "target"

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
        CONF_RUNTIME: False,
        CONF_RUN_FOR_MAX: 1440,
        CONF_OFF_BUTTON: False,
    }
    await hass.async_block_till_done()
    assert result["result"].state is ConfigEntryState.LOADED
    assert state_of(hass, NUMBER) == "0"


async def test_add_loose_target_skips_duration(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """Loose mode has no use for a default duration, so none is asked or stored. The
    form that follows the first asks for the limit instead."""
    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: TARGET_ID, CONF_MODE: "loose"}
    )
    assert result["step_id"] == "limit"

    result = await submit(hass, result, {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        CONF_TARGET: TARGET_ID,
        CONF_MODE: "loose",
        CONF_RUNTIME: False,
        CONF_RUN_FOR_MAX: 1440,
        CONF_OFF_BUTTON: False,
    }


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
        CONF_RUNTIME: False,
        CONF_RUN_FOR_MAX: 1440,
        CONF_OFF_BUTTON: False,
    }


async def test_counting_runtime_is_one_tick_on_the_first_form(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """The checkbox sits with the entity and the mode, unticked, so the common case
    stays three clicks; ticking it adds no step. The timer starts with a Runtime sensor
    at zero."""
    form = await start_flow(hass)
    assert [str(field) for field in form["data_schema"].schema] == [
        CONF_TARGET,
        CONF_MODE,
        CONF_RUNTIME,
        CONF_RUN_FOR_MAX,
        CONF_OFF_BUTTON,
    ]
    assert default_value(form, CONF_RUNTIME) is False

    result = await submit(
        hass, form, {CONF_TARGET: TARGET_ID, CONF_MODE: "loose", CONF_RUNTIME: True}
    )
    assert result["step_id"] == "limit"
    result = await submit(hass, result, {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        CONF_TARGET: TARGET_ID,
        CONF_MODE: "loose",
        CONF_RUNTIME: True,
        CONF_RUN_FOR_MAX: 1440,
        CONF_OFF_BUTTON: False,
    }
    assert float(state_of(hass, RUNTIME)) == 0.0


async def test_the_first_form_asks_for_the_maximum_of_run_for(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """The end of the slider is asked on the first form, a day to begin with, so that
    a timer that takes every default is still added in three clicks. The slider of the
    new timer ends where the user put it."""
    form = await start_flow(hass)
    assert default_value(form, CONF_RUN_FOR_MAX) == MAX_MINUTES
    assert selector_of(form, CONF_RUN_FOR_MAX) == {
        "number": {
            "min": 1,
            "max": MAX_MINUTES,
            "step": 1,
            "mode": "box",
            "unit_of_measurement": "min",
        }
    }

    result = await submit(
        hass,
        form,
        {CONF_TARGET: TARGET_ID, CONF_MODE: "strict", CONF_RUN_FOR_MAX: 120},
    )
    result = await submit(hass, result, {CONF_DEFAULT_DURATION: 45})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_RUN_FOR_MAX] == 120
    number = hass.states.get(NUMBER)
    assert number is not None
    assert number.attributes["max"] == 120


async def test_a_default_duration_above_the_maximum_is_refused(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """A default of 90 minutes on a slider that ends at 60 would be a run the slider
    cannot show. The refusal is on the duration form, whose only field it is; the
    maximum itself is allowed."""
    result = await submit(
        hass,
        await start_flow(hass),
        {CONF_TARGET: TARGET_ID, CONF_MODE: "strict", CONF_RUN_FOR_MAX: 60},
    )

    result = await submit(hass, result, {CONF_DEFAULT_DURATION: 90})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "duration"
    assert result["errors"] == {"base": "duration_above_maximum"}

    result = await submit(hass, result, {CONF_DEFAULT_DURATION: 60})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_DEFAULT_DURATION] == 60


async def test_the_duration_form_starts_at_a_maximum_below_thirty(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """A timer whose slider ends at 20 minutes offers 20 as its default duration, not
    the usual 30, so that taking the form as it is still adds the timer."""
    result = await submit(
        hass,
        await start_flow(hass),
        {CONF_TARGET: TARGET_ID, CONF_MODE: "strict", CONF_RUN_FOR_MAX: 20},
    )
    assert default_value(result, CONF_DEFAULT_DURATION) == 20

    result = await submit(hass, result, {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_DEFAULT_DURATION] == 20


async def test_a_maximum_in_part_minutes_is_refused(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """Minutes are the unit of the timer, so a fraction of one is refused on the first
    form, which stays open for the user to correct it."""
    result = await submit(
        hass,
        await start_flow(hass),
        {CONF_TARGET: TARGET_ID, CONF_MODE: "strict", CONF_RUN_FOR_MAX: 90.5},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "target"
    assert result["errors"] == {"base": "duration_not_whole"}


async def test_a_loose_timer_is_asked_for_a_limit_and_a_strict_one_is_not(
    hass: HomeAssistant, fake_target: FakeTarget, kettle: FakeTarget
) -> None:
    """After the first form, a loose timer is asked for how long its device may be left
    on: one box, empty to begin with, of minutes up to a day. The minutes are in the
    timer when it is added. A strict timer is asked for its default duration and never
    for a limit, since every run of it has a countdown already."""
    loose = await submit(
        hass, await start_flow(hass), {CONF_TARGET: TARGET_ID, CONF_MODE: "loose"}
    )

    assert loose["type"] is FlowResultType.FORM
    assert loose["step_id"] == "limit"
    assert selector_of(loose, CONF_LIMIT) == {
        "number": {
            "min": 1,
            "max": MAX_MINUTES,
            "step": 1,
            "mode": "box",
            "unit_of_measurement": "min",
        }
    }
    assert CONF_LIMIT not in prefilled(loose["data_schema"])

    added = await submit(hass, loose, {CONF_LIMIT: 120})

    assert added["type"] is FlowResultType.CREATE_ENTRY
    assert added["options"][CONF_LIMIT] == 120

    strict = await submit(
        hass, await start_flow(hass), {CONF_TARGET: "kettle.tea", CONF_MODE: "strict"}
    )
    assert strict["step_id"] == "duration"
    added = await submit(hass, strict, {CONF_DEFAULT_DURATION: 45})

    assert added["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_LIMIT not in added["options"]


async def test_an_empty_limit_box_means_no_limit(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, fake_target: FakeTarget
) -> None:
    """A user who has no use for a limit leaves the box empty: the timer is added
    without one, and a boiler switched on by hand runs until someone turns it off."""
    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: TARGET_ID, CONF_MODE: "loose"}
    )

    result = await submit(hass, result, {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_LIMIT not in result["options"]
    await fake_target.set_state("on")
    assert state_of(hass, SENSOR) == "unknown"
    await advance(hass, freezer, hours=24)
    assert fake_target.calls == []
    assert state_of(hass, TARGET_ID) == "on"


async def test_the_settings_set_change_and_remove_the_limit(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The box is the second form of the settings of a loose timer. It opens empty for
    a timer of an earlier release, then with the minutes the timer has, and emptying it
    takes the limit away. Each save loads the timer again."""
    entry = await setup_target(mode="loose")

    form = await change_options(hass, entry, {CONF_MODE: "loose"})
    assert form["step_id"] == "limit"
    assert CONF_LIMIT not in prefilled(form["data_schema"])
    result = await hass.config_entries.options.async_configure(
        form["flow_id"], {CONF_LIMIT: 90}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_LIMIT] == 90
    assert entry.state is ConfigEntryState.LOADED

    form = await change_options(hass, entry, {CONF_MODE: "loose"})
    assert suggested_value(form, CONF_LIMIT) == 90
    result = await hass.config_entries.options.async_configure(
        form["flow_id"], {CONF_LIMIT: 45}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_LIMIT] == 45

    form = await change_options(hass, entry, {CONF_MODE: "loose"})
    result = await hass.config_entries.options.async_configure(form["flow_id"], {})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_LIMIT not in entry.options
    assert entry.state is ConfigEntryState.LOADED


async def test_choosing_strict_removes_the_limit(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A limit means nothing in strict mode, so a timer that turns strict loses it, and
    does not bring it back when it turns loose again: the box then opens empty."""
    entry = await setup_target(mode="loose", limit=120)

    result = await change_options(hass, entry, {CONF_MODE: "strict"})
    assert result["step_id"] == "duration"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEFAULT_DURATION: 45}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_MODE] == "strict"
    assert CONF_LIMIT not in entry.options

    form = await change_options(hass, entry, {CONF_MODE: "loose"})
    assert form["step_id"] == "limit"
    assert CONF_LIMIT not in prefilled(form["data_schema"])


async def test_a_limit_in_part_minutes_is_refused(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """Minutes are the unit of the timer, so a fraction of one is refused on the form of
    the limit, which stays open for the user to correct it."""
    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: TARGET_ID, CONF_MODE: "loose"}
    )

    result = await submit(hass, result, {CONF_LIMIT: 90.5})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "limit"
    assert result["errors"] == {"base": "duration_not_whole"}

    result = await submit(hass, result, {CONF_LIMIT: 90})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_LIMIT] == 90


@pytest.mark.parametrize("minutes", [0, MAX_MINUTES + 1])
async def test_a_limit_outside_the_range_is_rejected(
    hass: HomeAssistant, fake_target: FakeTarget, minutes: int
) -> None:
    """A limit lasts at least a minute and at most a day, like any duration."""
    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: TARGET_ID, CONF_MODE: "loose"}
    )

    with pytest.raises(InvalidData):
        await submit(hass, result, {CONF_LIMIT: minutes})


async def test_the_turn_off_box_is_on_both_first_forms(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """The box sits after the end of the slider on the form that adds a timer and on
    the first form of its settings, unticked to begin with. Ticking it when the timer
    is added gives the timer its button without an extra step, and the settings open
    with the box ticked."""
    form = await start_flow(hass)
    assert default_value(form, CONF_OFF_BUTTON) is False

    result = await submit(
        hass,
        form,
        {CONF_TARGET: TARGET_ID, CONF_MODE: "loose", CONF_OFF_BUTTON: True},
    )
    result = await submit(hass, result, {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_OFF_BUTTON] is True
    assert state_of(hass, BUTTON) == "unknown"
    settings = await change_options(hass, result["result"])
    assert settings["step_id"] == "init"
    assert default_value(settings, CONF_OFF_BUTTON) is False
    assert prefilled(settings["data_schema"])[CONF_OFF_BUTTON] is True


async def test_settings_change_the_maximum_of_run_for(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The settings open at a day for a timer of an earlier release, and a new maximum
    is the end of the slider once the timer has loaded again."""
    entry = await setup_target()
    assert CONF_RUN_FOR_MAX not in entry.options
    form = await hass.config_entries.options.async_init(entry.entry_id)
    assert default_value(form, CONF_RUN_FOR_MAX) == MAX_MINUTES

    result = await hass.config_entries.options.async_configure(
        form["flow_id"],
        {CONF_MODE: "strict", CONF_RUNTIME: False, CONF_RUN_FOR_MAX: 120},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEFAULT_DURATION: 45}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_RUN_FOR_MAX] == 120
    assert entry.state is ConfigEntryState.LOADED
    number = hass.states.get(NUMBER)
    assert number is not None
    assert number.attributes["max"] == 120


async def test_lowering_the_maximum_below_the_default_duration_asks_to_lower_it(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A timer that runs 45 minutes by default cannot get a slider that ends at 30. The
    duration form shows the 45 the timer has, refuses it, and takes 30."""
    entry = await setup_target(default_duration=45)

    result = await change_options(
        hass, entry, {CONF_MODE: "strict", CONF_RUN_FOR_MAX: 30}
    )
    assert result["step_id"] == "duration"
    assert suggested_value(result, CONF_DEFAULT_DURATION) == 45

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEFAULT_DURATION: 45}
    )
    assert result["step_id"] == "duration"
    assert result["errors"] == {"base": "duration_above_maximum"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEFAULT_DURATION: 30}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_RUN_FOR_MAX] == 30
    assert entry.options[CONF_DEFAULT_DURATION] == 30


async def test_the_settings_reopen_at_the_maximum_the_timer_has(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The box shows the maximum set earlier, not a day, so that a user who opens the
    settings for something else and accepts every form as it is keeps it."""
    entry = await setup_target(run_for_max=120)

    form = await change_options(hass, entry)
    assert prefilled(form["data_schema"])[CONF_RUN_FOR_MAX] == 120

    result = await hass.config_entries.options.async_configure(
        form["flow_id"], prefilled(form["data_schema"])
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], prefilled(result["data_schema"])
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_RUN_FOR_MAX] == 120
    number = hass.states.get(NUMBER)
    assert number is not None
    assert number.attributes["max"] == 120


async def test_a_loose_timer_is_not_checked_until_it_turns_strict(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A loose timer has no duration form, so a maximum below the default duration it
    keeps is accepted as it is. The default is checked once the timer turns strict, as
    it is for a timer that was strict all along."""
    entry = await setup_target(mode="loose", default_duration=45)

    result = await change_options(
        hass,
        entry,
        {CONF_MODE: "loose", CONF_RUNTIME: False, CONF_RUN_FOR_MAX: 30},
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_RUN_FOR_MAX] == 30
    assert entry.options[CONF_DEFAULT_DURATION] == 45

    result = await change_options(
        hass,
        entry,
        {CONF_MODE: "strict", CONF_RUNTIME: False, CONF_RUN_FOR_MAX: 30},
    )
    assert result["step_id"] == "duration"
    assert suggested_value(result, CONF_DEFAULT_DURATION) == 45

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEFAULT_DURATION: 45}
    )
    assert result["step_id"] == "duration"
    assert result["errors"] == {"base": "duration_above_maximum"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DEFAULT_DURATION: 30}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_DEFAULT_DURATION] == 30


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
    assert result["step_id"] == "target"
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
    assert result["step_id"] == "target"
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
    assert result["step_id"] == "target"
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
        ("open", "target", {"base": "not_switchable"}),
        ("home", "target", {"base": "not_switchable"}),
        ("unavailable", "target", {"base": "not_switchable"}),
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
    assert kettle.calls == [("turn_on", "kettle.tea")]

    await kettle.set_state("off")

    assert state_of(hass, "number.tea_run_for") == "0"
    assert kettle.calls == [("turn_on", "kettle.tea")]


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


async def test_entity_id_is_taken_when_its_domain_has_both_services(
    hass: HomeAssistant,
) -> None:
    """The form offers the domains that have both services when it opens: the entity
    id of a domain that has only one is refused by the form itself, and the same id is
    accepted in a form that opens once the domain has the other service too."""
    provide_services(hass, "lamp_like", "turn_on")
    hass.states.async_set("lamp_like.hall", "on")

    with pytest.raises(InvalidData):
        await submit(
            hass,
            await start_flow(hass),
            {CONF_TARGET: "lamp_like.hall", CONF_MODE: "strict"},
        )

    provide_services(hass, "lamp_like", "turn_off")
    result = await submit(
        hass,
        await start_flow(hass),
        {CONF_TARGET: "lamp_like.hall", CONF_MODE: "strict"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "duration"


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
    """Saving the settings reloads the entry; the countdown carries on. A timer made
    before the counter existed, saved without touching the box, does not start
    counting: it gains no Runtime sensor, in the states or in the registry."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 30)
    await advance(hass, freezer, minutes=10)

    result = await change_options(hass, entry, {CONF_MODE: "loose"}, {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_MODE] == "loose"
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(RUNTIME) is None
    assert er.async_get(hass).async_get(RUNTIME) is None
    assert state_of(hass, NUMBER) == "20"
    await advance(hass, freezer, minutes=20)
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_options_switching_to_loose_needs_no_duration(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """Leaving strict mode asks for no duration: the form of the limit comes instead,
    and leaving its box empty ends the flow."""
    entry = await add_target(hass, mode="strict")

    result = await change_options(hass, entry, {CONF_MODE: "loose"})
    assert result["step_id"] == "limit"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

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
        CONF_RUNTIME: False,
        CONF_RUN_FOR_MAX: 1440,
        CONF_OFF_BUTTON: False,
    }
    await fake_target.set_state("on")
    assert state_of(hass, NUMBER) == "20"


async def test_options_offer_the_default_duration_kept_through_loose_mode(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A user who tries loose mode and goes back to strict finds the default duration
    they had: loose mode ignores it and does not erase it."""
    entry = await setup_target(mode="strict", default_duration=45)

    await change_options(hass, entry, {CONF_MODE: "loose"}, {})

    assert entry.options[CONF_MODE] == "loose"
    assert entry.options[CONF_DEFAULT_DURATION] == 45

    result = await change_options(hass, entry, {CONF_MODE: "strict"})

    assert result["step_id"] == "duration"
    assert suggested_value(result, CONF_DEFAULT_DURATION) == 45


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


@pytest.mark.parametrize(
    ("stored", "shown"),
    [
        ({CONF_RUNTIME: True}, True),
        ({CONF_RUNTIME: False}, False),
        ({}, False),
    ],
    ids=["ticked", "unticked", "no such option, as in a timer of an earlier release"],
)
async def test_settings_show_whether_the_runtime_is_counted(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    stored: dict[str, bool],
    shown: bool,
) -> None:
    """The box opens as the timer has it: ticked for a timer that counts, unticked for
    one that does not, and unticked for one whose options have no such key."""
    entry = await setup_target()
    hass.config_entries.async_update_entry(entry, options={**entry.options, **stored})
    await hass.async_block_till_done()
    assert entry.options.get(CONF_RUNTIME) is stored.get(CONF_RUNTIME)

    result = await change_options(hass, entry)

    assert result["step_id"] == "init"
    assert prefilled(result["data_schema"])[CONF_RUNTIME] is shown


async def test_enabling_the_counter_mid_countdown_keeps_it_and_counts_from_now(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Ticking the box while the boiler runs for 45 minutes does not touch the
    countdown. The sensor appears at zero, not at the ten minutes the boiler has
    already been on, and counts from the moment the box was ticked."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 45)
    await advance(hass, freezer, minutes=10)
    countdown = hass.states.get(SENSOR)
    assert countdown is not None
    assert state_of(hass, NUMBER) == "35"
    assert hass.states.get(RUNTIME) is None

    result = await change_options(
        hass,
        entry,
        {CONF_MODE: "strict", CONF_RUNTIME: True},
        {CONF_DEFAULT_DURATION: 45},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_RUNTIME] is True
    assert entry.state is ConfigEntryState.LOADED
    assert float(state_of(hass, RUNTIME)) == 0.0
    assert state_of(hass, NUMBER) == "35"
    assert fake_target.calls == [TURN_ON]
    ends_at = hass.states.get(SENSOR)
    assert ends_at is not None
    assert ends_at.state == countdown.state
    assert ends_at.attributes["started_at"] == countdown.attributes["started_at"]

    await advance(hass, freezer, minutes=1)

    assert float(state_of(hass, RUNTIME)) == 1.0
    assert state_of(hass, NUMBER) == "34"


async def test_disabling_the_counter_in_the_settings_removes_the_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Unticking the box takes the sensor away, not only its state, and leaves the
    countdown as it was. Ticking it again brings the sensor back with the total it
    had, without the minutes in between."""
    entry = await setup_target(runtime=True)
    registry = er.async_get(hass)
    await set_number(hass, NUMBER, 45)
    await advance(hass, freezer, minutes=10)
    assert float(state_of(hass, RUNTIME)) == 10.0

    result = await change_options(
        hass,
        entry,
        {CONF_MODE: "strict", CONF_RUNTIME: False},
        {CONF_DEFAULT_DURATION: 45},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_RUNTIME] is False
    assert hass.states.get(RUNTIME) is None
    assert registry.async_get(RUNTIME) is None
    assert state_of(hass, NUMBER) == "35"
    await advance(hass, freezer, minutes=35)
    assert fake_target.calls == [TURN_ON, TURN_OFF]

    result = await change_options(
        hass,
        entry,
        {CONF_MODE: "strict", CONF_RUNTIME: True},
        {CONF_DEFAULT_DURATION: 45},
    )

    assert entry.options[CONF_RUNTIME] is True
    assert float(state_of(hass, RUNTIME)) == 10.0


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


# --- The Workday sensor --------------------------------------------------------------


def sensor_picker_of(result: FlowResult) -> dict[str, Any]:
    """The Workday sensor picker of the form `result` shows, as the frontend gets it."""
    (marker,) = (
        key for key in result["data_schema"].schema if key == CONF_WORKDAY_SENSOR
    )
    return result["data_schema"].schema[marker].serialize()["selector"]["entity"]


async def test_workday_step_is_skipped_without_a_workday_sensor(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """Nobody is asked about a sensor there is none to pick: the flows end where they
    did, and the form that comes last says "Submit"."""
    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: TARGET_ID, CONF_MODE: "strict"}
    )
    assert result["step_id"] == "duration"
    assert result["last_step"] is not False

    result = await submit(hass, result, {CONF_DEFAULT_DURATION: 45})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        CONF_TARGET: TARGET_ID,
        CONF_MODE: "strict",
        CONF_DEFAULT_DURATION: 45,
        CONF_RUNTIME: False,
        CONF_RUN_FOR_MAX: 1440,
        CONF_OFF_BUTTON: False,
    }
    entry = result["result"]
    result = await change_options(
        hass, entry, {CONF_MODE: "strict"}, {CONF_DEFAULT_DURATION: 20}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_WORKDAY_SENSOR not in entry.options
    result = await change_options(hass, entry, {CONF_MODE: "loose"})
    assert result["step_id"] == "limit"
    assert result["last_step"] is not False
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_workday_sensor_is_asked_after_the_duration(
    hass: HomeAssistant, fake_target: FakeTarget, fake_workday: FakeWorkday
) -> None:
    """With a Workday sensor in the house, the last form of a strict timer asks for
    it, among the Workday sensors and nothing else."""
    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: TARGET_ID, CONF_MODE: "strict"}
    )

    result = await submit(hass, result, {CONF_DEFAULT_DURATION: 45})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "workday"
    assert result["last_step"] is True
    picker = sensor_picker_of(result)
    assert picker["domain"] == ["binary_sensor"]
    assert picker["integration"] == "workday"
    assert picker["multiple"] is False

    result = await submit(hass, result, {CONF_WORKDAY_SENSOR: fake_workday.entity_id})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        CONF_TARGET: TARGET_ID,
        CONF_MODE: "strict",
        CONF_DEFAULT_DURATION: 45,
        CONF_RUNTIME: False,
        CONF_RUN_FOR_MAX: 1440,
        CONF_OFF_BUTTON: False,
        CONF_WORKDAY_SENSOR: fake_workday.entity_id,
    }
    await hass.async_block_till_done()
    assert result["result"].state is ConfigEntryState.LOADED


async def test_workday_sensor_can_be_left_out(
    hass: HomeAssistant, fake_target: FakeTarget, fake_workday: FakeWorkday
) -> None:
    """The sensor is for the intervals that follow working days; a timer without any
    of them needs none, and the form is submitted as it is."""
    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: TARGET_ID, CONF_MODE: "strict"}
    )
    result = await submit(hass, result, {CONF_DEFAULT_DURATION: 45})

    result = await submit(hass, result, {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_WORKDAY_SENSOR not in result["options"]


async def test_loose_mode_asks_for_the_workday_sensor_after_the_limit(
    hass: HomeAssistant, fake_target: FakeTarget, fake_workday: FakeWorkday
) -> None:
    """A loose timer has no default duration to ask for, so its second form is the
    limit's and the Workday sensor's comes last."""
    result = await submit(
        hass, await start_flow(hass), {CONF_TARGET: TARGET_ID, CONF_MODE: "loose"}
    )
    assert result["step_id"] == "limit"
    assert result["last_step"] is not False

    result = await submit(hass, result, {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "workday"

    result = await submit(hass, result, {CONF_WORKDAY_SENSOR: fake_workday.entity_id})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        CONF_TARGET: TARGET_ID,
        CONF_MODE: "loose",
        CONF_RUNTIME: False,
        CONF_RUN_FOR_MAX: 1440,
        CONF_OFF_BUTTON: False,
        CONF_WORKDAY_SENSOR: fake_workday.entity_id,
    }


async def test_options_set_and_remove_the_workday_sensor(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """The options end with the sensor: set it, see it there the next time, take it
    away by leaving the field empty."""
    entry = await setup_target()

    result = await change_options(
        hass, entry, {CONF_MODE: "strict"}, {CONF_DEFAULT_DURATION: 45}
    )
    assert result["step_id"] == "workday"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_WORKDAY_SENSOR: fake_workday.entity_id}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_WORKDAY_SENSOR] == fake_workday.entity_id
    assert entry.state is ConfigEntryState.LOADED

    result = await change_options(
        hass, entry, {CONF_MODE: "strict"}, {CONF_DEFAULT_DURATION: 45}
    )
    assert result["step_id"] == "workday"
    assert suggested_value(result, CONF_WORKDAY_SENSOR) == fake_workday.entity_id
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_WORKDAY_SENSOR not in entry.options
    assert entry.state is ConfigEntryState.LOADED


async def test_a_workday_sensor_that_is_gone_can_still_be_removed(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The Workday integration was deleted, and the timer still names its sensor: the
    form keeps showing it, so that the user can take it away."""
    entry = await setup_target(workday_sensor="binary_sensor.workday_sensor")

    result = await change_options(hass, entry, {CONF_MODE: "loose"}, {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "workday"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_WORKDAY_SENSOR not in entry.options


async def test_workday_sensor_in_use_cannot_be_removed(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """An interval of working days cannot be left without the sensor that says which
    they are: the form is shown again with the reason, in words, and the timer keeps
    the sensor."""
    entry = await setup_target(workday_sensor=fake_workday.entity_id)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")

    result = await change_options(hass, entry, {CONF_MODE: "loose"}, {}, {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "workday"
    assert result["errors"] == {"base": "workday_in_use"}
    texts = await async_get_translations(hass, "en", "options", [DOMAIN])
    assert texts[f"component.{DOMAIN}.options.error.workday_in_use"]
    assert entry.options[CONF_WORKDAY_SENSOR] == fake_workday.entity_id

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_WORKDAY_SENSOR: fake_workday.entity_id}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_workday_sensor_can_be_removed_when_only_weekdays_are_used(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """Intervals that name their weekdays do not need the sensor."""
    entry = await setup_target(workday_sensor=fake_workday.entity_id)
    await add_interval(hass, entry, start="06:30", end="07:15", weekdays=["mon"])

    result = await change_options(hass, entry, {CONF_MODE: "loose"}, {}, {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_WORKDAY_SENSOR not in entry.options


async def test_workday_step_is_worded_in_both_flows(hass: HomeAssistant) -> None:
    """Adding a timer and changing one both explain the Workday sensor they ask for."""
    for category in ("config", "options"):
        texts = await async_get_translations(hass, "en", category, [DOMAIN])
        prefix = f"component.{DOMAIN}.{category}.step.workday"

        assert texts[f"{prefix}.title"], category
        assert texts[f"{prefix}.description"], category
        assert texts[f"{prefix}.data.{CONF_WORKDAY_SENSOR}"], category
        assert texts[f"{prefix}.data_description.{CONF_WORKDAY_SENSOR}"], category
