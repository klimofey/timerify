"""The Voice settings entry follows the state of the targets: a device that reports
another name or another list of modes is listed as it reports itself, and a device that
only switches or reports a temperature costs the file nothing.

The scenarios are the user's: a device updated by its vendor, a thermostat whose
integration offers a mode it did not offer yesterday, the entry unloaded. The file is
read as the built-in agent reads it, and the agent is spoken to.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.timerify.const import (
    CONTEXT_HVAC_MODES,
    LIST_MODE,
    VOICE_SYNC_COOLDOWN,
)
from custom_components.timerify.voice.sentences import build, target_voice

from ..conftest import (
    CLIMATE_SERVICES,
    SWITCH_SERVICES,
    FakeTarget,
    ProvideTarget,
    SetupTarget,
)
from ..helpers import AC_ATTRS, AC_ID, advance
from .helpers import (
    add_voice_entry,
    conversation_reloads,
    converse,
    hvac_blocks,
    hvac_words,
    listed,
    managed_file,
    outs,
    reached,
)

FILES = "custom_components.timerify.voice.files"


@contextmanager
def builds_counted() -> Iterator[MagicMock]:
    """Count the times the sentences of a language are built, which every writing of the
    file does and a change that leaves the file as it is has no reason to."""
    with patch(f"{FILES}.build", wraps=build) as builds:
        yield builds


@pytest.fixture
def pump(provide_target: ProvideTarget) -> FakeTarget:
    """`switch.pump` as a switch of YAML has it: a state that names it, and no registry
    entry, nor a device."""
    return provide_target(
        "switch.pump",
        SWITCH_SERVICES,
        name="Pump",
        registered=False,
        capability_attributes={"friendly_name": "Pump"},
    )


# Names


@pytest.mark.usefixtures("assist")
async def test_a_yaml_switch_renamed_by_its_state_is_listed_by_its_new_name(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    pump: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The name of a switch that has no registry entry is the one its state reports, and
    its integration may report another after an update. Assist hears the new name once
    the cooldown has passed, and the agent reads the sentences once for it."""
    await setup_target(target=pump.entity_id)
    await add_voice_entry(hass, languages=("en",))
    assert outs(listed(hass, "en")) == ["Pump"]
    reloads = conversation_reloads(hass)

    pump.write("off", friendly_name="Well pump")
    await hass.async_block_till_done()
    assert outs(listed(hass, "en")) == ["Pump"]
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert outs(listed(hass, "en")) == ["Well pump"]
    assert len(reloads) == 1
    heard = await converse(hass, "turn on the well pump for 10 minutes")
    assert reached(heard) == "TimerifyRun"
    assert pump.calls == [("turn_on", pump.entity_id)]


# Modes of devices


@pytest.mark.usefixtures("assist")
async def test_a_new_mode_a_device_reports_is_listed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_vent: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A fan that offers a preset it did not offer before is spoken to with it."""
    await setup_target(target=fake_vent.entity_id)
    await add_voice_entry(hass, languages=("en",))
    assert outs(listed(hass, "en", LIST_MODE)) == ["auto", "eco", "sleep"]
    reloads = conversation_reloads(hass)

    fake_vent.capability_attributes["preset_modes"] = ["auto", "eco", "sleep", "turbo"]
    fake_vent.write("off")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert outs(listed(hass, "en", LIST_MODE)) == ["auto", "eco", "sleep", "turbo"]
    assert len(reloads) == 1
    heard = await converse(hass, "turn on the vent for 10 minutes in turbo mode")
    assert reached(heard) == "TimerifyRun"
    assert fake_vent.call_data == [("turn_on", {"preset_mode": "turbo"})]


@pytest.mark.usefixtures("assist")
async def test_a_registered_thermostat_that_gains_a_fan_mode_is_listed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The fan modes of an air conditioner are in its state, not in its registry entry,
    so an update of its integration changes them there."""
    await setup_target(target=fake_climate.entity_id)
    await add_voice_entry(hass, languages=("en",))
    assert outs(listed(hass, "en", LIST_MODE)) == ["auto", "high", "low"]

    fake_climate.capability_attributes["fan_modes"] = ["auto", "low", "medium", "high"]
    fake_climate.write("off")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert outs(listed(hass, "en", LIST_MODE)) == ["auto", "high", "low", "medium"]
    heard = await converse(hass, "turn on the AC for an hour in medium mode")
    assert reached(heard) == "TimerifyRun"
    assert fake_climate.call_data[-1] == ("set_fan_mode", {"fan_mode": "medium"})


@pytest.mark.usefixtures("assist")
async def test_a_mode_a_device_stops_reporting_leaves_the_list(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_vent: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    await setup_target(target=fake_vent.entity_id)
    await add_voice_entry(hass, languages=("en",))

    fake_vent.capability_attributes["preset_modes"] = ["auto", "sleep"]
    fake_vent.write("off")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert outs(listed(hass, "en", LIST_MODE)) == ["auto", "sleep"]


# HVAC modes of thermostats


@pytest.mark.parametrize("registered", [True, False], ids=["registered", "of YAML"])
@pytest.mark.usefixtures("assist")
async def test_a_thermostat_that_gains_an_hvac_mode_is_understood_with_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    provide_target: ProvideTarget,
    setup_target: SetupTarget,
    registered: bool,
) -> None:
    """A thermostat that offers drying after an update of its integration is spoken to
    with the words for drying, and has the sentences for its new set of modes, not the
    old one, which no thermostat has any more."""
    thermostat = provide_target(
        AC_ID,
        CLIMATE_SERVICES,
        name="AC",
        registered=registered,
        capability_attributes={**AC_ATTRS, "friendly_name": "AC"},
        state_attributes={"temperature": 20, "fan_mode": "auto"},
    )
    await setup_target(target=thermostat.entity_id)
    await add_voice_entry(hass, languages=("en",))
    assert sorted(hvac_words(hass, "en")) == ["cool fan_only heat"]
    reloads = conversation_reloads(hass)

    thermostat.capability_attributes["hvac_modes"] = [*AC_ATTRS["hvac_modes"], "dry"]
    thermostat.write("off")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert sorted(hvac_words(hass, "en")) == ["cool dry fan_only heat"]
    assert {value["context"][CONTEXT_HVAC_MODES] for value in listed(hass, "en")} == {
        "cool dry fan_only heat"
    }
    assert len(hvac_blocks(hass, "en")) == 3
    assert len(reloads) == 1
    heard = await converse(hass, "turn on the AC for an hour drying")
    assert reached(heard) == "TimerifyRun"
    assert thermostat.call_data[0] == ("set_hvac_mode", {"hvac_mode": "dry"})


@pytest.mark.usefixtures("assist")
async def test_a_thermostat_with_no_state_follows_the_capabilities_of_its_entry(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """While the integration of a thermostat is not running, as after a restart before
    it starts, the capabilities in its registry entry say what it can do. When it
    starts and offers another mode they change there, and are followed like a change
    of the state."""
    registry = er.async_get(hass)
    capabilities = {
        key: value for key, value in AC_ATTRS.items() if key != "supported_features"
    }
    registry.async_update_entity(
        fake_climate.entity_id,
        capabilities=capabilities,
        supported_features=AC_ATTRS["supported_features"],
    )
    hass.states.async_remove(fake_climate.entity_id)
    await setup_target(target=fake_climate.entity_id)
    await add_voice_entry(hass, languages=("en",))
    assert sorted(hvac_words(hass, "en")) == ["cool fan_only heat"]

    registry.async_update_entity(
        fake_climate.entity_id,
        capabilities={**capabilities, "hvac_modes": [*AC_ATTRS["hvac_modes"], "dry"]},
    )
    await hass.async_block_till_done()
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert sorted(hvac_words(hass, "en")) == ["cool dry fan_only heat"]


@pytest.mark.usefixtures("assist")
async def test_a_thermostat_with_no_name_to_be_said_adds_no_sentences(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A thermostat whose aliases the user took away cannot be spoken to, so the file
    has no sentences for its set of modes: nothing that is said could reach them. They
    come with the first name it is given."""
    er.async_get(hass).async_update_entity(fake_climate.entity_id, aliases=[])
    await setup_target()
    await setup_target(target=fake_climate.entity_id)
    await add_voice_entry(hass, languages=("en",))

    assert outs(listed(hass, "en")) == ["Boiler"]
    assert hvac_blocks(hass, "en") == []
    assert hvac_words(hass, "en") == {}

    er.async_get(hass).async_update_entity(fake_climate.entity_id, aliases=["Cooler"])
    await hass.async_block_till_done()
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert outs(listed(hass, "en")) == ["Boiler", "Cooler"]
    assert hvac_words(hass, "en") == {
        "cool fan_only heat": ["cool", "heat", "fan_only"]
    }
    heard = await converse(hass, "turn on the cooler for an hour cooling")
    assert reached(heard) == "TimerifyRun"


@pytest.mark.usefixtures("assist")
async def test_the_hvac_modes_of_a_thermostat_with_no_name_change_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The file says nothing of the HVAC modes of a thermostat that has no name, so a
    change of them is neither built nor written."""
    er.async_get(hass).async_update_entity(fake_climate.entity_id, aliases=[])
    await setup_target(target=fake_climate.entity_id)
    await add_voice_entry(hass, languages=("en",))
    before = managed_file(hass, "en").read_text("utf-8")
    reloads = conversation_reloads(hass)

    with builds_counted() as builds:
        fake_climate.capability_attributes["hvac_modes"] = ["off", "heat"]
        fake_climate.write("off")
        await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert builds.call_count == 0
    assert managed_file(hass, "en").read_text("utf-8") == before
    assert reloads == []


# Nothing that the file does not say


@pytest.mark.usefixtures("assist")
async def test_a_target_switching_on_and_off_rewrites_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_full_ac: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A switch that goes on and off, and a thermostat that reports the temperature of
    the room, are the states a house produces all day: none changes a word of the file,
    so nothing is built, nothing is written and the agent reads nothing."""
    await setup_target()
    await setup_target(target=fake_full_ac.entity_id)
    await add_voice_entry(hass, languages=("en",))
    before = managed_file(hass, "en").read_text("utf-8")
    reloads = conversation_reloads(hass)

    with builds_counted() as builds:
        for state in ("on", "off", "on"):
            await fake_target.set_state(state)
            await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)
        for temperature in (21, 22, 23):
            fake_full_ac.write("off", current_temperature=temperature)
            await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert builds.call_count == 0
    assert managed_file(hass, "en").read_text("utf-8") == before
    assert reloads == []


@pytest.mark.usefixtures("assist")
async def test_a_device_that_lists_its_modes_in_another_order_rewrites_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_vent: FakeTarget,
    fake_full_ac: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The file lists the modes in an order of its own, so the order a device reports
    them in is not something it says."""
    await setup_target(target=fake_vent.entity_id)
    await setup_target(target=fake_full_ac.entity_id)
    await add_voice_entry(hass, languages=("en",))
    reloads = conversation_reloads(hass)

    with builds_counted() as builds:
        fake_vent.capability_attributes["preset_modes"] = ["sleep", "eco", "auto"]
        fake_vent.write("off")
        fake_full_ac.capability_attributes["hvac_modes"] = list(
            reversed(fake_full_ac.capability_attributes["hvac_modes"])
        )
        fake_full_ac.write("off")
        await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert builds.call_count == 0
    assert reloads == []


# Leaving


@pytest.mark.usefixtures("assist")
async def test_a_state_change_after_the_entry_is_unloaded_writes_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    pump: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Once the entry is unloaded nothing follows the states of the targets: a switch
    renamed by its state is not looked at, and the file keeps the name it had."""
    await setup_target(target=pump.entity_id)
    entry = await add_voice_entry(hass, languages=("en",))
    before = managed_file(hass, "en").read_text("utf-8")
    reloads = conversation_reloads(hass)

    assert await hass.config_entries.async_unload(entry.entry_id)
    with patch(f"{FILES}.target_voice", wraps=target_voice) as looked_at:
        pump.write("off", friendly_name="Well pump")
        await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    looked_at.assert_not_called()
    assert managed_file(hass, "en").read_text("utf-8") == before
    assert reloads == []
