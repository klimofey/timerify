"""What Assist is offered by default: the target of a timer, and nothing of Timerify's
own.

A timer is driven through its target, by name, so that a person and an LLM have one way
to do it, not two (spec 6.4). The entities Timerify adds to the target's device are for
the dashboard and for automations; if Assist knew them as well, an agent would be told
about "Boiler Run for", "Boiler Ends at" and one switch for each schedule interval next
to the boiler itself.
"""

import pytest
from homeassistant.components.homeassistant.exposed_entities import (
    async_should_expose,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.const import DOMAIN

from ..conftest import FakeTarget, SetupTarget
from ..helpers import BUTTON, NEXT, NUMBER, SENSOR, TARGET_ID, add_interval
from .helpers import ASSISTANT

EVERY_TIMER_HAS = {NUMBER, SENSOR, NEXT}
"""The entities of a timer, apart from the switch of each schedule interval."""


@pytest.fixture
async def scheduled_boiler(
    hass: HomeAssistant,
    assist: None,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> MockConfigEntry:
    """A timer on the Boiler with one schedule interval, so with all its entities."""
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    return entry


def timerify_entities(hass: HomeAssistant, entry: MockConfigEntry) -> set[str]:
    """The ids of the entities Timerify has added for the timer of `entry`."""
    registry = er.async_get(hass)
    return {
        registered.entity_id
        for registered in er.async_entries_for_config_entry(registry, entry.entry_id)
        if registered.platform == DOMAIN
    }


async def test_timerify_entities_are_not_exposed_by_default(
    hass: HomeAssistant, scheduled_boiler: MockConfigEntry
) -> None:
    """The number, both sensors and the switch of the interval stay out of Assist,
    though Home Assistant exposes the switches of a house; the boiler itself is what
    Assist knows."""
    entities = timerify_entities(hass, scheduled_boiler)

    (interval_switch,) = entities - EVERY_TIMER_HAS
    assert interval_switch.startswith("switch.")
    assert entities == EVERY_TIMER_HAS | {interval_switch}
    assert {
        entity_id: async_should_expose(hass, ASSISTANT, entity_id)
        for entity_id in entities
    } == dict.fromkeys(entities, False)
    assert async_should_expose(hass, ASSISTANT, TARGET_ID)


async def test_the_turn_off_button_is_not_exposed_by_default(
    hass: HomeAssistant,
    assist: None,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A timer with a Turn off button still has one way to be driven by voice: the
    boiler, by name. Home Assistant does not expose buttons by default, so Assist is
    not told about "Boiler Turn off" next to it."""
    await setup_target(off_button=True)

    assert hass.states.get(BUTTON) is not None
    assert not async_should_expose(hass, ASSISTANT, BUTTON)
    assert async_should_expose(hass, ASSISTANT, TARGET_ID)


async def test_interval_switch_is_a_config_entity(
    hass: HomeAssistant, scheduled_boiler: MockConfigEntry
) -> None:
    """The switch of an interval configures the timer, so it is in the device's
    configuration section; that is also what keeps Home Assistant from exposing it."""
    (interval_switch,) = timerify_entities(hass, scheduled_boiler) - EVERY_TIMER_HAS

    registered = er.async_get(hass).async_get(interval_switch)
    assert registered is not None
    assert registered.entity_category is EntityCategory.CONFIG
