"""The switch that enables a schedule interval, flipped on the boiler's window.

Each interval has a switch on the target's device. Flipping it is not a reload of the
timer: the flag is kept in the timer's file, and switching an interval off is an edit of
the schedule like any other (S2, S3). The scenarios run on the wall clock of Jerusalem,
with the clock frozen on a Sunday morning.
"""

import copy
from datetime import timedelta
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.timerify.const import DOMAIN

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    NEXT,
    NUMBER,
    SENSOR,
    SUNDAY,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    add_interval,
    advance_to,
    call_service,
    edit_interval,
    iso,
    local,
    open_sunday,
    payload,
    record_writes,
    restart,
    saved,
    set_switch,
    state_of,
    storage_key,
)

pytestmark = pytest.mark.usefixtures("hass_storage")

MONDAY = SUNDAY + timedelta(days=1)

SWITCH = "switch.boiler_schedule_06_30_07_15_mon_sun"
"""The switch of the interval from 06:30 to 07:15 on every day of the week."""


# --- The switch on the device ------------------------------------------------------


async def test_each_interval_has_a_switch_on_the_target_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The interval from 06:30 to 07:15 gets a switch that is on, named after it, in
    its own subentry and on the boiler's device; another interval gets another."""
    await open_sunday(hass, freezer)
    entry = await setup_target()

    first = await add_interval(hass, entry, start="06:30", end="07:15")

    assert state_of(hass, SWITCH) == "on"
    state = hass.states.get(SWITCH)
    assert state is not None
    assert state.name == "Boiler Schedule 06:30–07:15, Mon–Sun"
    registered = er.async_get(hass).async_get(SWITCH)
    assert registered is not None
    assert registered.config_subentry_id == first
    assert registered.device_id == fake_target.device_id

    second = await add_interval(
        hass, entry, start="08:00", end="09:00", weekdays=["sat", "sun"]
    )

    switches = [
        e
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if e.domain == "switch"
    ]
    assert {e.config_subentry_id for e in switches} == {first, second}
    assert {e.device_id for e in switches} == {fake_target.device_id}
    assert {state_of(hass, e.entity_id) for e in switches} == {"on"}
    assert len(dr.async_get(hass).devices) == 1


@pytest.mark.parametrize("fake_target", [False], indirect=True)
async def test_switch_of_a_target_without_a_device_keeps_the_timer_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A target on no device has the device Timerify made for it, which every entity of
    the timer is on, the interval's switch too. Deleting the interval takes its switch
    and nothing else: the number and the sensors stay on the same device."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    interval = await add_interval(hass, entry, start="06:30", end="07:15")

    [device] = dr.async_get(hass).devices
    assert device.name == "Boiler"
    assert device.identifiers == {(DOMAIN, entry.entry_id)}
    assert device.config_subentry_id is None
    registry = er.async_get(hass)
    for entity_id in (SWITCH, NUMBER, SENSOR, NEXT):
        registered = registry.async_get(entity_id)
        assert registered is not None
        assert registered.device_id == device.id

    hass.config_entries.async_remove_subentry(entry, interval)
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH) is None
    assert [d.id for d in dr.async_get(hass).devices] == [device.id]
    for entity_id in (NUMBER, SENSOR, NEXT):
        registered = registry.async_get(entity_id)
        assert registered is not None
        assert registered.device_id == device.id
        assert hass.states.get(entity_id) is not None
    assert "different config subentry" not in caplog.text


async def test_switch_follows_its_target_to_another_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The target moves to the device Tank: the interval's switch goes there with the
    rest of the timer's entities."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    registry = er.async_get(hass)
    target = registry.async_get(TARGET_ID)
    assert target is not None
    assert target.config_entry_id is not None
    tank = dr.async_get(hass).async_get_or_create(
        config_entry_id=target.config_entry_id,
        identifiers={("boiler_maker", "tank")},
        name="Tank",
    )

    registry.async_update_entity(TARGET_ID, device_id=tank.id)
    await hass.async_block_till_done()

    registered = registry.async_get(SWITCH)
    assert registered is not None
    assert registered.device_id == tank.id
    assert state_of(hass, SWITCH) == "on"
    assert entry.state is ConfigEntryState.LOADED


# --- Switching off and on ------------------------------------------------------------


async def test_switching_off_skips_the_window_without_a_reload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The switch is turned off before the window: the entry is not reloaded, the
    boiler stays off through the window and through the next morning's."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    controller = entry.runtime_data

    await set_switch(hass, SWITCH, False)

    assert state_of(hass, SWITCH) == "off"
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is controller
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    await advance_to(hass, freezer, local(MONDAY, "06:30"))
    assert fake_target.calls == []
    assert state_of(hass, SENSOR) == "unknown"


async def test_switch_state_survives_a_restart(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """The flag is in the timer's file; after a restart the switch is still off and so
    is the boiler's morning."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    interval = await add_interval(hass, entry, start="06:30", end="07:15")

    await set_switch(hass, SWITCH, False)

    assert saved(hass_storage, entry) == payload(disabled_intervals=[interval])

    await restart(hass, entry)

    assert state_of(hass, SWITCH) == "off"
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == []

    await set_switch(hass, SWITCH, True)

    assert saved(hass_storage, entry)["disabled_intervals"] == []


async def test_editing_a_switched_off_interval_keeps_it_off(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Editing the times of an interval reloads the timer; the interval stays what it
    was, a switched off one among them."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    interval = await add_interval(hass, entry, start="06:30", end="07:15")
    await set_switch(hass, SWITCH, False)

    await edit_interval(hass, entry, interval, end="07:30")

    assert state_of(hass, SWITCH) == "off"
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == []


async def test_deleting_an_interval_removes_its_switch(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The switch goes with its interval: no state and no registry entry."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    interval = await add_interval(hass, entry, start="06:30", end="07:15")

    hass.config_entries.async_remove_subentry(entry, interval)
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH) is None
    assert er.async_get(hass).async_get(SWITCH) is None
    assert entry.state is ConfigEntryState.LOADED


async def test_deleting_a_switched_off_interval_forgets_its_flag(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """The file does not keep the flag of an interval that is gone."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    interval = await add_interval(hass, entry, start="06:30", end="07:15")
    await set_switch(hass, SWITCH, False)
    assert saved(hass_storage, entry)["disabled_intervals"] == [interval]

    hass.config_entries.async_remove_subentry(entry, interval)
    await hass.async_block_till_done()

    assert saved(hass_storage, entry) == payload()


# --- Switching while the window runs (S2, S3) ----------------------------------------


async def test_disabling_during_the_window_stops_the_target(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """S2: the window has had the boiler on since half past six. Switching it off at
    seven takes the boiler off at once, and the quarter of an hour left runs nothing."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:00"))
    assert fake_target.calls == [TURN_ON]

    await set_switch(hass, SWITCH, False)

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"
    assert state_of(hass, SENSOR) == "unknown"
    assert state_of(hass, NUMBER) == "0"
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_disabling_after_a_manual_change_leaves_the_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """S3: ten past seven the user adds half an hour. Switching the interval off then
    leaves the timer alone: the boiler runs to quarter to eight and goes off there."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:10"))
    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=30)

    await set_switch(hass, SWITCH, False)

    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:45")
    assert fake_target.calls == [TURN_ON]
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON]
    await advance_to(hass, freezer, local(SUNDAY, "07:45"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_enabling_during_the_window_starts_the_target(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The interval was switched off before half past six. Switching it on at a quarter
    to seven runs the boiler for the rest of the window, once."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await set_switch(hass, SWITCH, False)
    await advance_to(hass, freezer, local(SUNDAY, "06:45"))
    assert fake_target.calls == []

    await set_switch(hass, SWITCH, True)

    assert state_of(hass, SWITCH) == "on"
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    await advance_to(hass, freezer, local(MONDAY, "06:30"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]


async def test_flipping_the_interval_off_and_on_behind_a_late_boiler_leaves_it_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The boiler has run since half past six, and the cloud shows what it is told a
    moment late. Seven o'clock: the user switches the interval off and, before the
    boiler shows off, on again. The late "off" must not leave the boiler off while "Ends
    at" says quarter past seven: it is turned on again, and goes off at the end."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:00"))
    assert fake_target.calls == [TURN_ON]
    fake_target.report_next_call_late()

    await set_switch(hass, SWITCH, False)
    await set_switch(hass, SWITCH, True)

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")

    await fake_target.report_late()

    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"


async def test_enabling_before_the_window_waits_for_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Switched off at six and on again at ten past, the interval runs at half past six
    as if nothing happened."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await set_switch(hass, SWITCH, False)
    await advance_to(hass, freezer, local(SUNDAY, "06:10"))

    await set_switch(hass, SWITCH, True)

    assert fake_target.calls == []
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")


async def test_disabling_the_interval_that_carries_the_timer_hands_it_to_the_other(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """From six to seven and from half past six to eight, the boiler runs to eight.
    Switching the second off at a quarter to seven leaves the first, which is still
    open: the boiler runs to seven."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:00", end="07:00")
    second = await add_interval(hass, entry, start="06:30", end="08:00")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert state_of(hass, SENSOR) == iso(SUNDAY, "08:00")
    switch = er.async_get(hass).async_get_entity_id(
        "switch", DOMAIN, f"{entry.entry_id}_interval_{second}"
    )
    assert switch is not None

    await advance_to(hass, freezer, local(SUNDAY, "06:45"))
    await set_switch(hass, switch, False)

    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:00")
    assert fake_target.calls == [TURN_ON]
    await advance_to(hass, freezer, local(SUNDAY, "07:00"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_switch_flipped_behind_a_slow_boiler_finds_the_window_over(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The boiler is slow to answer the turn-on at half past six, and the user flips the
    switch of another interval meanwhile. The flip gets its turn when the window is
    already over, and what it finds over is replaced by tomorrow's like any other
    window that ends."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    other = await add_interval(hass, entry, start="10:00", end="11:00")
    switch = er.async_get(hass).async_get_entity_id(
        "switch", DOMAIN, f"{entry.entry_id}_interval_{other}"
    )
    assert switch is not None
    slow = fake_target.hold_next_call()
    freezer.move_to(local(SUNDAY, "06:30"))
    async_fire_time_changed(hass)
    await slow.reached.wait()
    flipping = hass.async_create_task(
        hass.services.async_call(
            "switch", "turn_off", {"entity_id": switch}, blocking=True
        )
    )
    freezer.move_to(local(SUNDAY, "07:15"))

    slow.release.set()
    await flipping
    await hass.async_block_till_done()

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, switch) == "off"
    await advance_to(hass, freezer, local(MONDAY, "06:30"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]
    assert state_of(hass, SENSOR) == iso(MONDAY, "07:15")


@pytest.mark.parametrize("on", [False, True], ids=["off", "on"])
async def test_flip_waiting_behind_a_slow_boiler_fails_when_the_timer_unloads(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
    on: bool,
) -> None:
    """A flip that waits its turn while the timer is unloaded changes nothing and says
    so: the switch would otherwise show a flag that was never kept."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    slow = fake_target.hold_next_call()
    starting = hass.async_create_task(
        hass.services.async_call(
            "number", "set_value", {"entity_id": NUMBER, "value": 10}, blocking=True
        )
    )
    await slow.reached.wait()
    flipping = hass.async_create_task(
        hass.services.async_call(
            "switch",
            "turn_on" if on else "turn_off",
            {"entity_id": SWITCH},
            blocking=True,
        )
    )
    await hass.config_entries.async_unload(entry.entry_id)
    stored = copy.deepcopy(hass_storage[storage_key(entry)])

    slow.release.set()
    await starting
    with pytest.raises(HomeAssistantError) as raised:
        await flipping

    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "timer_unloaded"
    assert hass_storage[storage_key(entry)] == stored


# --- What the switch writes -----------------------------------------------------------


async def test_switch_is_written_only_when_toggled(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The timer's own changes, a window starting and ending, do not write the switch;
    flipping it writes it once, and flipping it to where it is writes nothing."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    writes = record_writes(hass, SWITCH)

    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))

    assert writes == []

    await set_switch(hass, SWITCH, False)

    assert writes == ["off"]

    await set_switch(hass, SWITCH, False)

    assert writes == ["off"]

    await set_switch(hass, SWITCH, True)

    assert writes == ["off", "on"]
