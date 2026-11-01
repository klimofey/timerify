"""The fake targets of the harness: a call goes to the fake that owns the entity."""

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant

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
