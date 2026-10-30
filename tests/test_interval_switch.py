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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.timerify.const import DOMAIN, MAX_LISTED_INTERVALS

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
    reload_held_back,
    restart,
    retitle_interval,
    saved,
    set_switch,
    state_of,
    storage_key,
)

pytestmark = pytest.mark.usefixtures("hass_storage")

MONDAY = SUNDAY + timedelta(days=1)

SWITCH = "switch.boiler_schedule_06_30_07_15_mon_sun"
"""The switch of the interval from 06:30 to 07:15 on every day of the week."""
EVENING_SWITCH = "switch.boiler_schedule_18_00_19_00_mon_sun"
"""The switch of the interval from 18:00 to 19:00 on every day of the week."""


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


async def test_enabling_during_a_window_the_user_stopped_starts_the_target_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """S4 keeps the window off after the boiler was switched off by hand at 06:40, and
    editing the running interval does not bring it back (RULINGS). Switching the
    interval off and on again is another act of the user, newer than the stop: at 06:50
    the boiler runs for the rest of the window, once."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "06:40"))
    await fake_target.set_state("off")
    await advance_to(hass, freezer, local(SUNDAY, "06:50"))
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == "unknown"

    await set_switch(hass, SWITCH, False)
    await set_switch(hass, SWITCH, True)

    assert fake_target.calls == [TURN_ON, TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_ON, TURN_OFF]


async def test_one_call_for_an_interval_switch_and_the_boiler_reaches_both(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A dashboard button that turns off several switches at once names the interval's
    switch and the boiler in one call: the interval is switched off, the boiler gets its
    turn-off, and the window that would have run does not."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": [SWITCH, TARGET_ID]},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert state_of(hass, SWITCH) == "off"
    assert fake_target.calls == [TURN_OFF]
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == [TURN_OFF]


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


async def test_flipping_an_interval_outside_its_window_does_not_write_the_number(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The number shows the minutes left, and a flip before the window leaves them at
    zero: the history gets no report of a value that did not change."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    writes = record_writes(hass, NUMBER)

    await set_switch(hass, SWITCH, False)
    await set_switch(hass, SWITCH, True)

    assert writes == []


# --- The whole schedule at once ------------------------------------------------------
#
# What the voice and the tools of an LLM switch: every interval of the timer, or the
# intervals that carry a title, each as its own switch would switch it.


async def titled_schedule(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_target: SetupTarget
) -> tuple[MockConfigEntry, str, str]:
    """A timer with the intervals Morning, from 06:30 to 07:15, and Evening, from 18:00
    to 19:00, on a Sunday at six: the entry and the ids of the two intervals."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    morning = await add_interval(hass, entry, start="06:30", end="07:15")
    evening = await add_interval(hass, entry, start="18:00", end="19:00")
    await retitle_interval(hass, entry, morning, "Morning")
    await retitle_interval(hass, entry, evening, "Evening")
    return entry, morning, evening


def schedule_switches(hass: HomeAssistant) -> tuple[str, str]:
    """What the switches of the morning and the evening interval of `titled_schedule`
    show."""
    return state_of(hass, SWITCH), state_of(hass, EVENING_SWITCH)


async def test_the_schedule_is_switched_as_a_whole_without_a_reload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """Both intervals go off and come back on, the titles of the intervals switched
    are given back in the order of the schedule, the flags are kept in the timer's file
    and the timer is not reloaded. Switched on again at half past six, with the morning
    open, the boiler runs for the rest of it."""
    entry, morning, evening = await titled_schedule(hass, freezer, setup_target)
    controller = entry.runtime_data

    assert await controller.async_set_schedule_enabled(False) == ("Morning", "Evening")

    assert saved(hass_storage, entry) == payload(disabled_intervals=[morning, evening])
    assert state_of(hass, SWITCH) == "off"
    assert entry.runtime_data is controller
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == []

    assert await controller.async_set_schedule_enabled(True) == ("Morning", "Evening")

    assert saved(hass_storage, entry)["disabled_intervals"] == []
    assert state_of(hass, SWITCH) == "on"
    assert entry.runtime_data is controller
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")


async def test_an_interval_is_found_by_its_title_without_case_or_punctuation(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The title is compared as the built-in agent hears it, and the title given back
    is the interval's own."""
    entry, _, _ = await titled_schedule(hass, freezer, setup_target)

    assert await entry.runtime_data.async_set_schedule_enabled(
        False, "  mORNING! "
    ) == ("Morning",)

    assert schedule_switches(hass) == ("off", "on")


async def test_the_titles_given_back_are_those_now_as_asked_whether_or_not_they_were(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Asking for a state the schedule is in already is answered as if it were
    changed, and changes nothing more."""
    entry, _, _ = await titled_schedule(hass, freezer, setup_target)
    controller = entry.runtime_data
    await controller.async_set_schedule_enabled(False, "Morning")

    assert await controller.async_set_schedule_enabled(False) == ("Morning", "Evening")
    assert await controller.async_set_schedule_enabled(False) == ("Morning", "Evening")

    assert schedule_switches(hass) == ("off", "off")


async def test_intervals_with_one_title_are_switched_together(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    entry, _, evening = await titled_schedule(hass, freezer, setup_target)
    await retitle_interval(hass, entry, evening, "morning")
    night = await add_interval(hass, entry, start="22:00", end="23:00")
    await retitle_interval(hass, entry, night, "Night")

    assert await entry.runtime_data.async_set_schedule_enabled(False, "Morning") == (
        "Morning",
        "morning",
    )

    assert schedule_switches(hass) == ("off", "off")
    assert state_of(hass, "switch.boiler_schedule_22_00_23_00_mon_sun") == "on"


async def test_an_unknown_title_switches_nothing_and_says_which(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    entry, _, _ = await titled_schedule(hass, freezer, setup_target)
    stored = copy.deepcopy(saved(hass_storage, entry))

    with pytest.raises(ServiceValidationError) as raised:
        await entry.runtime_data.async_set_schedule_enabled(False, "Noon")

    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "unknown_interval"
    assert raised.value.translation_placeholders == {
        "target": "Boiler",
        "interval": "Noon",
        "intervals": "Morning; Evening",
    }
    assert schedule_switches(hass) == ("on", "on")
    assert saved(hass_storage, entry) == stored


@pytest.mark.parametrize(
    "asked",
    [
        "morning early",
        "  Morning   EARLY ",
        "Morning, early!",
        "MORNING\u00a0early",
    ],
)
async def test_titles_are_compared_without_case_punctuation_and_the_space_between_words(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    asked: str,
) -> None:
    entry, morning, _ = await titled_schedule(hass, freezer, setup_target)
    await retitle_interval(hass, entry, morning, "Morning  early")

    titles = await entry.runtime_data.async_set_schedule_enabled(False, asked)

    assert titles == ("Morning  early",)
    assert schedule_switches(hass) == ("off", "on")


@pytest.mark.parametrize(
    ("title", "asked"),
    [
        ("06:30–07:15, Mon–Sun", "06:30-07:15, Mon-Sun"),
        ("06:30-07:15, Mon-Sun", "06:30–07:15, Mon–Sun"),
        ("Mon—Sun", "mon-sun"),
        ("Mon\u2212Sun", "Mon-Sun"),
    ],
    ids=["hyphen-for-en-dash", "en-dash-for-hyphen", "em-dash", "minus-sign"],
)
async def test_a_hyphen_and_a_dash_are_one_in_a_title(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    title: str,
    asked: str,
) -> None:
    """The title an interval is given when it is made has en dashes; whoever asks for
    it types what the keyboard has."""
    entry, morning, _ = await titled_schedule(hass, freezer, setup_target)
    await retitle_interval(hass, entry, morning, title)

    assert await entry.runtime_data.async_set_schedule_enabled(False, asked) == (title,)

    assert schedule_switches(hass) == ("off", "on")


async def test_a_letter_with_and_without_the_diaeresis_is_one_in_a_title(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Russian prints "e" for "yo" (CYRILLIC SMALL LETTER IO) and a title is asked for
    either way."""
    io, ie = "\N{CYRILLIC SMALL LETTER IO}", "\N{CYRILLIC SMALL LETTER IE}"
    entry, morning, _ = await titled_schedule(hass, freezer, setup_target)
    await retitle_interval(hass, entry, morning, f"T{io}st")

    assert await entry.runtime_data.async_set_schedule_enabled(
        False, f"T{ie.upper()}ST"
    ) == (f"T{io}st",)

    assert schedule_switches(hass) == ("off", "on")


@pytest.mark.parametrize("asked", ["?", " ! ", "...", "\u2013"])
async def test_a_title_of_punctuation_asks_for_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    asked: str,
) -> None:
    """What is nothing but punctuation says no title, as it says no name to the
    built-in agent: it is not the interval whose title is nothing but punctuation too,
    and the answer lists the titles that can be asked for, not that one."""
    entry, morning, _ = await titled_schedule(hass, freezer, setup_target)
    await retitle_interval(hass, entry, morning, "?!")

    with pytest.raises(ServiceValidationError) as raised:
        await entry.runtime_data.async_set_schedule_enabled(False, asked)

    assert raised.value.translation_key == "unknown_interval"
    assert raised.value.translation_placeholders == {
        "target": "Boiler",
        "interval": asked,
        "intervals": "Evening",
    }
    assert schedule_switches(hass) == ("on", "on")


async def test_a_schedule_with_no_title_to_ask_for_says_so(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Every interval is titled by punctuation alone, so none can be asked for by
    title: the answer says that, instead of listing nothing."""
    entry, morning, evening = await titled_schedule(hass, freezer, setup_target)
    await retitle_interval(hass, entry, morning, "?!")
    await retitle_interval(hass, entry, evening, "...")

    with pytest.raises(ServiceValidationError) as raised:
        await entry.runtime_data.async_set_schedule_enabled(False, "?!")

    assert raised.value.translation_key == "no_interval_titles"
    assert raised.value.translation_placeholders == {"target": "Boiler"}
    assert schedule_switches(hass) == ("on", "on")


async def test_the_titles_a_refusal_lists_are_bare_and_each_listed_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The refusal gives the titles as they are, apart by semicolons, because the
    translation of each language frames them in its own quotes and a title may have a
    comma of its own (the one an interval is given when it is made does); two intervals
    of a title list it once."""
    entry, _, evening = await titled_schedule(hass, freezer, setup_target)
    await retitle_interval(hass, entry, evening, "Morning")
    await add_interval(hass, entry, start="22:00", end="23:00")

    with pytest.raises(ServiceValidationError) as raised:
        await entry.runtime_data.async_set_schedule_enabled(False, "Noon")

    assert raised.value.translation_key == "unknown_interval"
    assert raised.value.translation_placeholders == {
        "target": "Boiler",
        "interval": "Noon",
        "intervals": "Morning; 22:00–23:00, Mon–Sun",
    }


async def test_titles_that_sound_the_same_take_one_place_in_a_refusal(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Titles that differ only in case or punctuation are one title to whoever asks, so
    they are listed once, as the first of them is written, and take one of the places
    that the list has: the cap counts what can be asked for, not what is stored."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    titles = ["Morning", "morning!", *(f"Title {number}" for number in range(1, 6))]
    for number, title in enumerate(titles, start=1):
        subentry_id = await add_interval(
            hass, entry, start=f"{number:02d}:00", end=f"{number:02d}:30"
        )
        await retitle_interval(hass, entry, subentry_id, title)

    with pytest.raises(ServiceValidationError) as raised:
        await entry.runtime_data.async_set_schedule_enabled(False, "Noon")

    assert raised.value.translation_key == "unknown_interval_and_more"
    assert raised.value.translation_placeholders == {
        "target": "Boiler",
        "interval": "Noon",
        "intervals": "Morning; Title 1; Title 2; Title 3; Title 4",
        "more": "1",
    }


@pytest.mark.parametrize(
    ("intervals", "key", "listed", "more"),
    [
        pytest.param(
            MAX_LISTED_INTERVALS, "unknown_interval", MAX_LISTED_INTERVALS, None
        ),
        pytest.param(
            MAX_LISTED_INTERVALS + 1,
            "unknown_interval_and_more",
            MAX_LISTED_INTERVALS,
            "1",
        ),
        pytest.param(
            MAX_LISTED_INTERVALS + 3,
            "unknown_interval_and_more",
            MAX_LISTED_INTERVALS,
            "3",
        ),
    ],
    ids=["all-fit", "one-more", "three-more"],
)
async def test_a_long_list_of_titles_is_cut_and_says_how_many_are_left_out(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    intervals: int,
    key: str,
    listed: int,
    more: str | None,
) -> None:
    """A refusal is read aloud and read by an agent, so it names the first titles and
    counts the rest instead of reciting a whole house of intervals; the count is a
    placeholder of the message that says it, which only a cut list has."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    for number in range(1, intervals + 1):
        subentry_id = await add_interval(
            hass, entry, start=f"{number:02d}:00", end=f"{number:02d}:30"
        )
        await retitle_interval(hass, entry, subentry_id, f"Title {number}")

    with pytest.raises(ServiceValidationError) as raised:
        await entry.runtime_data.async_set_schedule_enabled(False, "Noon")

    assert raised.value.translation_key == key
    assert raised.value.translation_placeholders == {
        "target": "Boiler",
        "interval": "Noon",
        "intervals": "; ".join(f"Title {number}" for number in range(1, listed + 1)),
        **({} if more is None else {"more": more}),
    }


@pytest.mark.parametrize("interval", [None, "Morning"])
async def test_a_timer_without_intervals_has_no_schedule(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    interval: str | None,
) -> None:
    entry = await setup_target()

    with pytest.raises(ServiceValidationError) as raised:
        await entry.runtime_data.async_set_schedule_enabled(False, interval)

    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "no_schedule"
    assert raised.value.translation_placeholders == {"target": "Boiler"}


async def test_switching_overlapping_windows_together_does_not_flicker_the_boiler(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Two windows are open at ten to seven, from half past six to a quarter past
    seven and from a quarter to seven to a quarter to eight. The whole schedule off
    turns the boiler off once, not off and on again between the two; on again at five
    to seven runs it once, to the later end."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await add_interval(hass, entry, start="06:45", end="07:45")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "06:45"))
    await advance_to(hass, freezer, local(SUNDAY, "06:50"))
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:45")

    await entry.runtime_data.async_set_schedule_enabled(False)

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"
    assert state_of(hass, SENSOR) == "unknown"
    await advance_to(hass, freezer, local(SUNDAY, "06:55"))

    await entry.runtime_data.async_set_schedule_enabled(True)

    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:45")
    await advance_to(hass, freezer, local(SUNDAY, "07:45"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON, TURN_OFF]


async def test_a_schedule_is_not_switched_further_once_the_timer_unloads(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """The morning interval is switched off and the boiler is slow to answer the
    turn-off. The timer is unloaded meanwhile: the call says so and the evening
    interval is left as it was, since a timer that is gone must not go on writing its
    file for the one that replaces it."""
    entry, morning, _ = await titled_schedule(hass, freezer, setup_target)
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == [TURN_ON]
    slow = fake_target.hold_next_call()
    switching = hass.async_create_task(
        entry.runtime_data.async_set_schedule_enabled(False)
    )
    await slow.reached.wait()

    await hass.config_entries.async_unload(entry.entry_id)
    slow.release.set()
    with pytest.raises(HomeAssistantError) as raised:
        await switching

    assert raised.value.translation_key == "timer_unloaded"
    assert saved(hass_storage, entry)["disabled_intervals"] == [morning]


@pytest.mark.parametrize("on", [False, True], ids=["off", "on"])
async def test_a_schedule_waiting_behind_a_slow_boiler_fails_when_the_timer_unloads(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
    on: bool,
) -> None:
    """The call waits its turn while the timer is unloaded: nothing is changed and the
    caller is told, as a flip of a single switch is."""
    entry, _, _ = await titled_schedule(hass, freezer, setup_target)
    controller = entry.runtime_data
    slow = fake_target.hold_next_call()
    starting = hass.async_create_task(
        hass.services.async_call(
            "number", "set_value", {"entity_id": NUMBER, "value": 10}, blocking=True
        )
    )
    await slow.reached.wait()
    switching = hass.async_create_task(controller.async_set_schedule_enabled(on))
    await hass.config_entries.async_unload(entry.entry_id)
    stored = copy.deepcopy(hass_storage[storage_key(entry)])

    slow.release.set()
    await starting
    with pytest.raises(HomeAssistantError) as raised:
        await switching

    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "timer_unloaded"
    assert hass_storage[storage_key(entry)] == stored


async def test_a_schedule_asked_for_after_an_interval_is_deleted_is_refused_as_unknown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Deleting an interval reloads the timer, and the reload waits for its turn when
    another is still going. The call that arrives meanwhile finds the interval gone:
    asked for by its title it is unknown, and the answer names the one that is left."""
    entry, morning, _ = await titled_schedule(hass, freezer, setup_target)
    async with reload_held_back(entry):
        hass.config_entries.async_remove_subentry(entry, morning)

        with pytest.raises(ServiceValidationError) as refused:
            await entry.runtime_data.async_set_schedule_enabled(False, "Morning")

    assert refused.value.translation_key == "unknown_interval"
    assert refused.value.translation_placeholders == {
        "target": "Boiler",
        "interval": "Morning",
        "intervals": "Evening",
    }
    await hass.async_block_till_done()
    assert state_of(hass, EVENING_SWITCH) == "on"


async def test_a_schedule_switched_as_a_whole_after_an_interval_is_deleted_has_one_left(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The whole schedule is the intervals that are still there: the evening one. It is
    still switched off once the timer has reloaded."""
    entry, morning, _ = await titled_schedule(hass, freezer, setup_target)
    async with reload_held_back(entry):
        hass.config_entries.async_remove_subentry(entry, morning)

        titles = await entry.runtime_data.async_set_schedule_enabled(False)

    assert titles == ("Evening",)
    await hass.async_block_till_done()
    assert state_of(hass, EVENING_SWITCH) == "off"


async def test_a_schedule_asked_for_after_its_only_interval_is_deleted_is_no_schedule(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    entry = await setup_target()
    interval = await add_interval(hass, entry, start="06:30", end="07:15")
    async with reload_held_back(entry):
        hass.config_entries.async_remove_subentry(entry, interval)

        with pytest.raises(ServiceValidationError) as refused:
            await entry.runtime_data.async_set_schedule_enabled(True)

    assert refused.value.translation_key == "no_schedule"
