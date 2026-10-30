"""The unique ids of a timer's entities are their identity in the registry: an entity
keeps its entity id, its name, its history and its place on the dashboards only while
its unique id stays what it was. Every release must give the entities the ids the
earlier ones gave them, and the modules that look an entity up by its unique id must
build it the way the entity does."""

import pytest
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.const import (
    CONF_DEFAULT_DURATION,
    CONF_MODE,
    CONF_TARGET,
    DEFAULT_DURATION_MINUTES,
    DOMAIN,
    KEY_ENDS_AT,
    KEY_NEXT_COMMAND,
    KEY_RUN_FOR,
    SUBENTRY_INTERVAL,
    default_duration_minutes,
    interval_unique_id,
    timer_unique_id,
)

from .conftest import FakeTarget, SetupTarget
from .helpers import NEXT, NUMBER, SENSOR, TARGET_ID, add_interval

pytestmark = pytest.mark.usefixtures("hass_storage")

EVENING_SWITCH = "switch.boiler_schedule_18_00_19_00_mon_sun"


async def test_entities_of_a_timer_have_the_unique_ids_of_every_release(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The ids are spelled out here, not built by the code under test: they are what
    the registries of the installations already hold."""
    entry = await setup_target()
    interval = await add_interval(hass, entry, start="18:00", end="19:00")

    registered = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)

    assert {e.entity_id: e.unique_id for e in registered} == {
        NUMBER: f"{entry.entry_id}_run_for",
        SENSOR: f"{entry.entry_id}_ends_at",
        NEXT: f"{entry.entry_id}_next_command",
        EVENING_SWITCH: f"{entry.entry_id}_interval_{interval}",
    }


async def test_timer_set_up_again_finds_its_entities_where_an_earlier_release_left_them(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """An entity the registry holds under an earlier release's unique id is the entity
    of the timer, with the entity id the user gave it: nothing new is registered."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        title="Boiler",
        options={
            CONF_TARGET: TARGET_ID,
            CONF_MODE: "strict",
            CONF_DEFAULT_DURATION: 45,
        },
        subentries_data=[
            ConfigSubentryData(
                data={
                    "days": "weekdays",
                    "weekdays": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                    "start": "18:00",
                    "end": "19:00",
                    "settings": {},
                },
                subentry_id="evening",
                subentry_type=SUBENTRY_INTERVAL,
                title="Evening",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    left_by_earlier_release = {
        ("number", f"{entry.entry_id}_run_for"): "number.hot_water_run_for",
        ("sensor", f"{entry.entry_id}_ends_at"): "sensor.hot_water_ends_at",
        ("sensor", f"{entry.entry_id}_next_command"): "sensor.hot_water_next",
        ("switch", f"{entry.entry_id}_interval_evening"): "switch.hot_water_evening",
    }
    for (domain, unique_id), entity_id in left_by_earlier_release.items():
        registry.async_get_or_create(
            domain,
            DOMAIN,
            unique_id,
            config_entry=entry,
            config_subentry_id="evening" if domain == "switch" else None,
            suggested_object_id=entity_id.split(".")[1],
        )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    registered = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert {e.entity_id for e in registered} == set(left_by_earlier_release.values())
    for entity_id in left_by_earlier_release.values():
        assert hass.states.get(entity_id) is not None


def test_unique_ids_are_made_of_the_entry_and_what_the_entity_is() -> None:
    assert timer_unique_id("entry", KEY_RUN_FOR) == "entry_run_for"
    assert timer_unique_id("entry", KEY_ENDS_AT) == "entry_ends_at"
    assert timer_unique_id("entry", KEY_NEXT_COMMAND) == "entry_next_command"
    assert interval_unique_id("entry", "evening") == "entry_interval_evening"


@pytest.mark.parametrize(
    ("options", "minutes"),
    [
        ({CONF_DEFAULT_DURATION: 45}, 45),
        ({}, DEFAULT_DURATION_MINUTES),
        ({CONF_MODE: "loose"}, DEFAULT_DURATION_MINUTES),
    ],
)
def test_default_duration_is_the_option_or_the_default(
    options: dict[str, object], minutes: int
) -> None:
    assert default_duration_minutes(options) == minutes
