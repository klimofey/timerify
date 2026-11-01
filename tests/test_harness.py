"""The fake targets of the harness: a call goes to the fake that owns the entity."""

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    SWITCH_SERVICES,
    FakeServices,
    FakeTarget,
    ProvideTarget,
    SetupTarget,
    provide_fake,
)
from .helpers import NUMBER, TARGET_ID, TURN_OFF, TURN_ON, advance, set_number

PUMP_NUMBER = "number.pump_run_for"


async def test_two_switches_with_a_timer_each_get_only_their_own_calls(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    provide_target: ProvideTarget,
    setup_target: SetupTarget,
) -> None:
    """Two switches of one domain, a timer on each: the boiler's countdown ends with a
    call to the boiler alone, and the pump's with a call to the pump alone."""
    pump = provide_target("switch.pump", SWITCH_SERVICES, name="Pump")
    await setup_target()
    await setup_target(target=pump.entity_id)

    await set_number(hass, NUMBER, 10)
    await set_number(hass, PUMP_NUMBER, 20)
    await advance(hass, freezer, minutes=10)

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert pump.calls == [("turn_on", "switch.pump")]

    await advance(hass, freezer, minutes=10)

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert pump.calls == [("turn_on", "switch.pump"), ("turn_off", "switch.pump")]


async def test_a_call_for_an_entity_no_fake_owns_fails_loudly(
    hass: HomeAssistant, clock_at_start: None
) -> None:
    """A call for an entity that no fake provides is not handed to a fake that happens
    to be of the same domain: it fails, and the harness remembers it."""
    services = FakeServices(hass)
    boiler = provide_fake(hass, services, TARGET_ID, SWITCH_SERVICES, name="Boiler")

    with pytest.raises(AssertionError, match=r"switch\.stray"):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": "switch.stray"}, blocking=True
        )

    assert services.strays == ["switch.turn_on switch.stray"]
    assert boiler.calls == []


async def test_one_call_for_two_fakes_and_two_strays_is_split_between_them(
    hass: HomeAssistant, clock_at_start: None
) -> None:
    """One call names a boiler, a pump and two entities no fake owns: each fake takes
    the call for its own entity and nothing else, and the call fails once, naming both
    strays, which the harness remembers."""
    services = FakeServices(hass)
    boiler = provide_fake(hass, services, TARGET_ID, SWITCH_SERVICES, name="Boiler")
    pump = provide_fake(hass, services, "switch.pump", SWITCH_SERVICES, name="Pump")

    with pytest.raises(AssertionError, match=r"switch\.stray, switch\.ghost"):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": ["switch.stray", TARGET_ID, "switch.pump", "switch.ghost"]},
            blocking=True,
        )

    assert boiler.calls == [TURN_ON]
    assert pump.calls == [("turn_on", "switch.pump")]
    assert services.strays == [
        "switch.turn_on switch.stray",
        "switch.turn_on switch.ghost",
    ]


async def test_a_target_deleted_and_restored_with_the_same_unique_id_is_owned_again(
    hass: HomeAssistant, clock_at_start: None
) -> None:
    """While the user's boiler is deleted nobody owns it, so a call for it fails. When
    its integration restores it under the same unique id, its fake takes calls again."""
    services = FakeServices(hass)
    boiler = provide_fake(hass, services, TARGET_ID, SWITCH_SERVICES, name="Boiler")
    registry = er.async_get(hass)
    entry = registry.async_get(TARGET_ID)
    assert entry is not None
    provider = hass.config_entries.async_get_entry(entry.config_entry_id or "")
    assert provider is not None

    registry.async_remove(TARGET_ID)
    hass.states.async_remove(TARGET_ID)  # so that the restore gets its entity id back

    with pytest.raises(AssertionError, match=r"switch\.boiler"):
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": TARGET_ID}, blocking=True
        )
    assert boiler.calls == []

    restored = registry.async_get_or_create(
        "switch",
        entry.platform,
        entry.unique_id,
        config_entry=provider,
        suggested_object_id="boiler",
    )
    boiler.write("off")
    assert (restored.id, restored.entity_id) == (entry.id, TARGET_ID)

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": TARGET_ID}, blocking=True
    )

    assert boiler.calls == [TURN_ON]
    assert services.strays == ["switch.turn_on switch.boiler"]
