"""The target changes in the registry: renamed, moved to another device or removed."""

from unittest.mock import patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

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


@pytest.mark.parametrize("fake_target", [False], indirect=True)
async def test_a_target_given_a_device_while_down_leaves_no_fallback_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A boiler on no device has the device Timerify made for it, with every entity of
    its timer on it, the switch of its schedule too. The boiler's integration links it
    to a device of its own while Home Assistant is down: after the restart the made
    device is gone, and every entity is on the boiler's device as it was: the names the
    user gave to the number and the switch are kept, and no automation sees an entity
    vanish. The countdown the boiler was on runs out in time."""
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
    before = {e.entity_id: e.id for e in timer_entities(hass, entry)}
    assert set(before) == {NUMBER, SENSOR, NEXT, SWITCH}
    target = registry.async_get(TARGET_ID)
    assert target is not None
    assert target.config_entry_id is not None
    boiler = dr.async_get(hass).async_get_or_create(
        config_entry_id=target.config_entry_id,
        identifiers={("boiler_maker", "tank")},
        name="Tank",
    )

    def link_boiler() -> None:
        """What the boiler's integration does on its next start."""
        registry.async_update_entity(TARGET_ID, device_id=boiler.id)

    vanished: list[str] = []

    @callback
    def watch(event: Event[EventStateChangedData]) -> None:
        if event.data["new_state"] is None:
            vanished.append(event.data["entity_id"])

    async_track_state_change_event(hass, list(before), watch)

    await restart_after(hass, freezer, entry, while_down=link_boiler, minutes=5)

    assert entry.state is ConfigEntryState.LOADED
    assert fallback_device(hass, entry) is None
    assert [d.id for d in dr.async_get(hass).devices] == [boiler.id]
    assert {e.device_id for e in timer_entities(hass, entry)} == {boiler.id}
    assert {e.entity_id: e.id for e in timer_entities(hass, entry)} == before
    assert {e.entity_id: e.name for e in timer_entities(hass, entry)} == {
        NUMBER: "Heating minutes",
        SENSOR: None,
        NEXT: None,
        SWITCH: "Morning heat",
    }
    for entity_id in (NUMBER, SENSOR, NEXT, SWITCH):
        assert state_of(hass, entity_id) != "unavailable"
    assert vanished == []
    assert state_of(hass, NUMBER) == "15"
    await advance(hass, freezer, minutes=15)
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert timerify_warnings(caplog) == []
    assert "Detected that" not in caplog.text


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
