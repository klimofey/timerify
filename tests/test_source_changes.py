"""The target changes in the registry: renamed, moved to another device or removed."""

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.timerify.const import CONF_TARGET

from .conftest import FakeTarget, SetupTarget
from .helpers import NUMBER, SENSOR, TARGET_ID, TURN_ON, advance, set_number, state_of

RENAMED_ID = "switch.water_heater"


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
