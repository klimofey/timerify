"""The target changes in the registry: renamed, given a device, moved or removed."""

from collections.abc import Iterable
from unittest.mock import patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.const import CONF_TARGET, DOMAIN

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    NEXT,
    NUMBER,
    SENSOR,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    add_interval,
    advance,
    open_sunday,
    restart_after,
    set_number,
    state_of,
    timerify_warnings,
)

RENAMED_ID = "switch.water_heater"
SWITCH = "switch.boiler_schedule_06_30_07_15_mon_sun"
"""The switch of the interval from 06:30 to 07:15 on every day of the week."""


def timer_entities(hass: HomeAssistant, entry: ConfigEntry) -> list[er.RegistryEntry]:
    """The registry entries of the timer's own entities."""
    return er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)


async def test_target_rename_keeps_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Renaming the entity mid-countdown follows it: the timer ends on the new id."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 30)
    await advance(hass, freezer, minutes=10)

    # What the target's own integration does when its entity is renamed.
    er.async_get(hass).async_update_entity(TARGET_ID, new_entity_id=RENAMED_ID)
    hass.states.async_remove(TARGET_ID)
    hass.states.async_set(RENAMED_ID, "on")
    await hass.async_block_till_done()

    assert entry.options[CONF_TARGET] == RENAMED_ID
    assert entry.state is ConfigEntryState.LOADED
    assert state_of(hass, NUMBER) == "20"
    await advance(hass, freezer, minutes=20)
    assert fake_target.calls == [TURN_ON, ("turn_off", RENAMED_ID)]
    assert state_of(hass, NUMBER) == "0"


async def test_target_rename_reloads_the_entry_once(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Following a renamed target changes the options, which the entry reloads for;
    it does not ask for a second reload on top."""
    entry = await setup_target()

    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as reload:
        er.async_get(hass).async_update_entity(TARGET_ID, new_entity_id=RENAMED_ID)
        hass.states.async_remove(TARGET_ID)
        hass.states.async_set(RENAMED_ID, "off")
        await hass.async_block_till_done()

    reload.assert_called_once_with(entry.entry_id)
    assert entry.options[CONF_TARGET] == RENAMED_ID
    assert entry.state is ConfigEntryState.LOADED


async def test_target_moved_to_another_device_takes_timer_entities_along(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The timer's entities stay on the device of their target."""
    entry = await setup_target()
    registry = er.async_get(hass)
    target = registry.async_get(TARGET_ID)
    assert target is not None
    assert target.config_entry_id is not None
    assert {e.device_id for e in timer_entities(hass, entry)} == {fake_target.device_id}

    tank = dr.async_get(hass).async_get_or_create(
        config_entry_id=target.config_entry_id,
        identifiers={("boiler_maker", "tank")},
        name="Tank",
    )
    registry.async_update_entity(TARGET_ID, device_id=tank.id)
    await hass.async_block_till_done()

    assert {e.device_id for e in timer_entities(hass, entry)} == {tank.id}
    assert entry.state is ConfigEntryState.LOADED


async def test_target_removed_from_its_device_gives_timer_a_device_of_its_own(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A target that leaves its device leaves the timer's entities on a device named
    after it, as for any target that is on no device."""
    entry = await setup_target()

    er.async_get(hass).async_update_entity(TARGET_ID, device_id=None)
    await hass.async_block_till_done()

    (device_id,) = {e.device_id for e in timer_entities(hass, entry)}
    assert device_id is not None
    assert device_id != fake_target.device_id
    device = dr.async_get(hass).async_get(device_id)
    assert device is not None
    assert device.name == "Boiler"
    assert entry.state is ConfigEntryState.LOADED


async def test_target_removed_leaves_timer_entities_without_a_device(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The timer's entities stop belonging to the device of a target that is gone."""
    entry = await setup_target()

    er.async_get(hass).async_remove(TARGET_ID)
    await hass.async_block_till_done()

    assert {e.device_id for e in timer_entities(hass, entry)} == {None}
    assert hass.states.get(SENSOR) is not None


def fallback_device(hass: HomeAssistant, entry: ConfigEntry) -> dr.DeviceEntry | None:
    """The device Timerify makes for a target that is on none, if the timer has it."""
    return dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )


async def set_up_a_scheduled_boiler(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_target: SetupTarget
) -> tuple[ConfigEntry, dict[str, str]]:
    """A boiler on no device, with a schedule and a countdown of 20 minutes that began
    at six, and a name the user gave to the number and to the switch of the schedule.

    It returns the timer's entry and the registry id of each of its entities, which are
    all on the device Timerify made for the boiler.
    """
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await set_number(hass, NUMBER, 20)
    registry = er.async_get(hass)
    registry.async_update_entity(NUMBER, name="Heating minutes")
    registry.async_update_entity(SWITCH, name="Morning heat")
    made = fallback_device(hass, entry)
    assert made is not None
    assert {e.device_id for e in timer_entities(hass, entry)} == {made.id}
    ids = {e.entity_id: e.id for e in timer_entities(hass, entry)}
    assert set(ids) == {NUMBER, SENSOR, NEXT, SWITCH}
    return entry, ids


def make_a_device_for_the_boiler(hass: HomeAssistant) -> dr.DeviceEntry:
    """A device of the boiler's integration, which the boiler is not on yet."""
    target = er.async_get(hass).async_get(TARGET_ID)
    assert target is not None
    assert target.config_entry_id is not None
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=target.config_entry_id,
        identifiers={("boiler_maker", "tank")},
        name="Tank",
    )


def link_the_boiler_to(hass: HomeAssistant, device: dr.DeviceEntry) -> None:
    """What the boiler's integration, or the user in the settings of a helper, does."""
    er.async_get(hass).async_update_entity(TARGET_ID, device_id=device.id)


def watch_for_vanishing(hass: HomeAssistant, entity_ids: Iterable[str]) -> list[str]:
    """The entities whose state is removed from now on, as an automation sees it."""
    vanished: list[str] = []

    @callback
    def watch(event: Event[EventStateChangedData]) -> None:
        if event.data["new_state"] is None:
            vanished.append(event.data["entity_id"])

    async_track_state_change_event(hass, list(entity_ids), watch)
    return vanished


def assert_the_boiler_has_all_of_the_timer(
    hass: HomeAssistant,
    entry: ConfigEntry,
    boiler: dr.DeviceEntry,
    ids: dict[str, str],
) -> None:
    """The made device is gone, and every entity of the timer, the switch of the
    schedule included, is on the boiler's device as it was: the same registry id, the
    names the user gave, and a state."""
    assert entry.state is ConfigEntryState.LOADED
    assert fallback_device(hass, entry) is None
    assert [d.id for d in dr.async_get(hass).devices] == [boiler.id]
    entities = timer_entities(hass, entry)
    assert {e.device_id for e in entities} == {boiler.id}
    assert {e.entity_id: e.id for e in entities} == ids
    assert {e.entity_id: e.name for e in entities} == {
        NUMBER: "Heating minutes",
        SENSOR: None,
        NEXT: None,
        SWITCH: "Morning heat",
    }
    for entity_id in ids:
        assert state_of(hass, entity_id) != "unavailable"


@pytest.mark.parametrize("fake_target", [False], indirect=True)
async def test_a_target_given_a_device_while_down_leaves_no_fallback_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A boiler on no device has the device Timerify made for it, with every entity of
    its timer on it, the switch of its schedule too. The registry says that the boiler
    is on a device of its own when Home Assistant starts again, as when an update of the
    boiler's integration linked it before Timerify set up: the made device is gone, and
    every entity is on the boiler's device as it was. No automation sees an entity
    vanish, and the countdown the boiler was on runs out in time."""
    entry, ids = await set_up_a_scheduled_boiler(hass, freezer, setup_target)
    boiler = make_a_device_for_the_boiler(hass)
    vanished = watch_for_vanishing(hass, ids)

    await restart_after(
        hass,
        freezer,
        entry,
        while_down=lambda: link_the_boiler_to(hass, boiler),
        minutes=5,
    )

    assert_the_boiler_has_all_of_the_timer(hass, entry, boiler, ids)
    assert vanished == []
    assert state_of(hass, NUMBER) == "15"
    await advance(hass, freezer, minutes=15)
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert timerify_warnings(caplog) == []
    assert "Detected that" not in caplog.text


@pytest.mark.parametrize("fake_target", [False], indirect=True)
async def test_a_target_given_a_device_while_running_leaves_no_fallback_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The user picks a device for the boiler in the settings of its helper while its
    countdown runs: the timer reloads once, the made device is gone, every entity is on
    the boiler's device as it was, and the countdown runs out in time."""
    entry, ids = await set_up_a_scheduled_boiler(hass, freezer, setup_target)
    boiler = make_a_device_for_the_boiler(hass)
    await advance(hass, freezer, minutes=5)
    vanished = watch_for_vanishing(hass, ids)

    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as reload:
        link_the_boiler_to(hass, boiler)
        await hass.async_block_till_done()

    reload.assert_called_once_with(entry.entry_id)
    assert_the_boiler_has_all_of_the_timer(hass, entry, boiler, ids)
    assert vanished == []
    assert state_of(hass, NUMBER) == "15"
    await advance(hass, freezer, minutes=15)
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert timerify_warnings(caplog) == []
    assert "Detected that" not in caplog.text


@pytest.mark.parametrize("fake_target", [False], indirect=True)
async def test_a_target_renamed_and_given_a_device_at_once_reloads_the_timer_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """One change of the boiler's registry entry renames it and links it to a device:
    the timer follows the new id and reloads once, not once for each."""
    entry, ids = await set_up_a_scheduled_boiler(hass, freezer, setup_target)
    boiler = make_a_device_for_the_boiler(hass)

    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as reload:
        er.async_get(hass).async_update_entity(
            TARGET_ID, new_entity_id=RENAMED_ID, device_id=boiler.id
        )
        hass.states.async_remove(TARGET_ID)
        hass.states.async_set(RENAMED_ID, "on")
        await hass.async_block_till_done()

    reload.assert_called_once_with(entry.entry_id)
    assert entry.options[CONF_TARGET] == RENAMED_ID
    assert_the_boiler_has_all_of_the_timer(hass, entry, boiler, ids)


@pytest.mark.parametrize("fake_target", [False], indirect=True)
async def test_a_change_of_a_target_with_no_device_that_links_none_reloads_nothing(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Naming the boiler in its registry entry does not reload its timer, nor move its
    entities off the device made for it: only a device does."""
    entry = await setup_target()
    made = fallback_device(hass, entry)
    assert made is not None

    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as reload:
        er.async_get(hass).async_update_entity(TARGET_ID, name="Water boiler")
        await hass.async_block_till_done()

    reload.assert_not_called()
    assert fallback_device(hass, entry) == made
    assert {e.device_id for e in timer_entities(hass, entry)} == {made.id}


async def test_a_target_registered_later_with_a_device_leaves_no_fallback_device(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A lamp that the registry does not know yet gets a device named after its id for
    the timer. Its integration registers it, on a device of its own, once Home
    Assistant is running: the timer reloads once and its entities are on the lamp's
    device, the one made for them gone."""
    entry = await setup_target(target="switch.lamp")
    made = fallback_device(hass, entry)
    assert made is not None
    assert {e.device_id for e in timer_entities(hass, entry)} == {made.id}
    provider = MockConfigEntry(domain="lamp_maker")
    provider.add_to_hass(hass)
    lamp = dr.async_get(hass).async_get_or_create(
        config_entry_id=provider.entry_id,
        identifiers={("lamp_maker", "lamp")},
        name="Lamp",
    )

    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as reload:
        er.async_get(hass).async_get_or_create(
            "switch",
            provider.domain,
            "lamp",
            config_entry=provider,
            device_id=lamp.id,
            suggested_object_id="lamp",
        )
        await hass.async_block_till_done()

    reload.assert_called_once_with(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert fallback_device(hass, entry) is None
    assert {e.device_id for e in timer_entities(hass, entry)} == {lamp.id}


async def test_target_moved_to_another_device_reloads_the_entry_once(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A target that is on a device and moves to another reloads the timer once. What
    follows a target that gets its first device does nothing for it."""
    entry = await setup_target()
    tank = make_a_device_for_the_boiler(hass)

    with patch.object(
        hass.config_entries, "async_reload", wraps=hass.config_entries.async_reload
    ) as reload:
        link_the_boiler_to(hass, tank)
        await hass.async_block_till_done()

    reload.assert_called_once_with(entry.entry_id)
    assert {e.device_id for e in timer_entities(hass, entry)} == {tank.id}


@pytest.mark.parametrize("fake_target", [False], indirect=True)
async def test_a_target_with_no_device_keeps_its_fallback_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A restart in which the boiler is still on no device leaves the device Timerify
    made for it, the same one, with every entity of the timer on it."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    made = fallback_device(hass, entry)
    assert made is not None

    await restart_after(hass, freezer, entry, minutes=5)

    assert [d.id for d in dr.async_get(hass).devices] == [made.id]
    entities = timer_entities(hass, entry)
    assert {e.entity_id for e in entities} == {NUMBER, SENSOR, NEXT, SWITCH}
    assert {e.device_id for e in entities} == {made.id}


@pytest.mark.parametrize("fake_target", [False], indirect=True)
async def test_entities_disabled_with_the_fallback_device_are_enabled_on_the_boilers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user disabled the device made for the boiler, and a sensor on its own before
    that. The boiler is on a device of its own when Home Assistant starts again: what
    went with the made device is enabled on the boiler's, as the registry does when a
    device is enabled, and the sensor the user disabled stays disabled. Home Assistant
    reloads the entry once more, 30 seconds after entities were enabled; a countdown
    started meanwhile runs on, with the entities where they were and no call added to
    the boiler."""
    entry = await setup_target()
    registry = er.async_get(hass)
    registry.async_update_entity(NEXT, disabled_by=er.RegistryEntryDisabler.USER)
    made = fallback_device(hass, entry)
    assert made is not None
    dr.async_get(hass).async_update_device(
        made.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert {e.entity_id: e.disabled_by for e in timer_entities(hass, entry)} == {
        NUMBER: er.RegistryEntryDisabler.DEVICE,
        SENSOR: er.RegistryEntryDisabler.DEVICE,
        NEXT: er.RegistryEntryDisabler.USER,
    }
    boiler = make_a_device_for_the_boiler(hass)

    await restart_after(
        hass,
        freezer,
        entry,
        while_down=lambda: link_the_boiler_to(hass, boiler),
        minutes=5,
    )

    assert fallback_device(hass, entry) is None
    assert {e.entity_id: e.disabled_by for e in timer_entities(hass, entry)} == {
        NUMBER: None,
        SENSOR: None,
        NEXT: er.RegistryEntryDisabler.USER,
    }
    assert {e.device_id for e in timer_entities(hass, entry)} == {boiler.id}
    assert state_of(hass, NUMBER) == "0"
    assert state_of(hass, SENSOR) == "unknown"
    assert hass.states.get(NEXT) is None

    await set_number(hass, NUMBER, 20)
    await advance(hass, freezer, seconds=31)

    assert fallback_device(hass, entry) is None
    assert {e.entity_id: e.disabled_by for e in timer_entities(hass, entry)} == {
        NUMBER: None,
        SENSOR: None,
        NEXT: er.RegistryEntryDisabler.USER,
    }
    assert {e.device_id for e in timer_entities(hass, entry)} == {boiler.id}
    assert entry.state is ConfigEntryState.LOADED
    assert state_of(hass, NUMBER) == "20"
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=20)
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, NUMBER) == "0"
