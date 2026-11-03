"""The names of a timer's entities: a device that holds more than one timer names the
target of each, so that the user tells them apart wherever the names are listed."""

from unittest.mock import patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.timerify.const import EVENT_COUNTDOWN_ENDED
from custom_components.timerify.store import TimerStore

from .conftest import SWITCH_SERVICES, FakeTarget, ProvideTarget, SetupTarget
from .helpers import (
    add_interval,
    add_target,
    advance,
    payload,
    record_events,
    record_writes,
    restart,
    retitle_interval,
    run_for_of,
    set_number,
    set_switch,
    state_of,
)

pytestmark = pytest.mark.usefixtures("hass_storage")


def names_of(hass: HomeAssistant, entry: ConfigEntry) -> list[str]:
    """The friendly names, sorted, of every entity the registry holds for the entry: the
    names the entity lists show."""
    names = []
    for registered in er.async_entries_for_config_entry(
        er.async_get(hass), entry.entry_id
    ):
        state = hass.states.get(registered.entity_id)
        assert state is not None, registered.entity_id
        names.append(state.attributes["friendly_name"])
    return sorted(names)


def friendly_name(hass: HomeAssistant, entity_id: str) -> str:
    """The name the entity lists show for the entity."""
    state = hass.states.get(entity_id)
    assert state is not None, entity_id
    return str(state.attributes["friendly_name"])


def ids_of(hass: HomeAssistant, entry: ConfigEntry) -> set[str]:
    """The entity ids of every entity the registry holds for the entry."""
    return {
        registered.entity_id
        for registered in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }


def relay_names(channel: str | None, interval: str | None = None) -> list[str]:
    """The sorted names of the entities of a timer of a relay, with the Runtime sensor
    and the Turn off button, named after `channel` if it is given, and with the switch
    of an interval if its title is."""
    after = "" if channel is None else f" ({channel})"
    names = [
        f"Relay {name}{after}"
        for name in ("Ends at", "Next command", "Run for", "Runtime", "Turn off")
    ]
    if interval is not None:
        names.append(f"Relay Schedule {interval}{after}")
    return sorted(names)


async def test_one_timer_on_a_relay_keeps_its_plain_names(
    hass: HomeAssistant,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """A device with one timer reads as it always has: the other channel of the relay
    has none, so there is nothing to tell the timer apart from."""
    entry = await setup_target(target="switch.relay_1", runtime=True, off_button=True)

    assert names_of(hass, entry) == relay_names(None)
    assert ids_of(hass, entry) == {
        "number.relay_run_for",
        "sensor.relay_ends_at",
        "sensor.relay_next_command",
        "sensor.relay_runtime",
        "button.relay_turn_off",
    }


async def test_two_timers_on_a_relay_name_their_channels_after_a_restart(
    hass: HomeAssistant,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """Both channels of a relay have a timer with all its entities and an interval. The
    list of entities reads "Relay Run for (Channel 1)" and "Relay Run for (Channel 2)",
    and so on for every entity. The first timer, set up while it was alone, keeps its
    entity ids; the second one's follow its name."""
    one = await setup_target(target="switch.relay_1", runtime=True, off_button=True)
    two = await setup_target(target="switch.relay_2", runtime=True, off_button=True)
    morning = await add_interval(hass, one, start="06:30", end="07:15")
    evening = await add_interval(hass, two, start="18:00", end="19:00")
    await retitle_interval(hass, one, morning, "Morning")
    await retitle_interval(hass, two, evening, "Evening")

    await restart(hass, one)
    await restart(hass, two)

    assert names_of(hass, one) == relay_names("Channel 1", "Morning")
    assert names_of(hass, two) == relay_names("Channel 2", "Evening")
    assert {
        "number.relay_run_for",
        "sensor.relay_ends_at",
        "sensor.relay_next_command",
        "sensor.relay_runtime",
        "button.relay_turn_off",
    } <= ids_of(hass, one)
    assert {
        "number.relay_run_for_channel_2",
        "sensor.relay_ends_at_channel_2",
        "sensor.relay_next_command_channel_2",
        "sensor.relay_runtime_channel_2",
        "button.relay_turn_off_channel_2",
    } <= ids_of(hass, two)


async def test_timers_on_targets_with_no_device_are_never_named_after_them(
    hass: HomeAssistant, provide_target: ProvideTarget, setup_target: SetupTarget
) -> None:
    """A target that is on no device gets a device of its own for its timer, so two
    such timers share nothing to be told apart on: each reads as a timer alone on its
    device."""
    provide_target("switch.boiler", SWITCH_SERVICES, name="Boiler", on_device=False)
    provide_target("switch.pump", SWITCH_SERVICES, name="Pump", on_device=False)
    boiler = await setup_target(target="switch.boiler")
    pump = await setup_target(target="switch.pump")

    await restart(hass, boiler)
    await restart(hass, pump)

    assert "Boiler Run for" in names_of(hass, boiler)
    assert "Pump Run for" in names_of(hass, pump)
    assert run_for_of(hass, boiler) == "number.boiler_run_for"
    assert run_for_of(hass, pump) == "number.pump_run_for"


async def test_a_target_named_like_its_device_is_named_in_full(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    provide_target: ProvideTarget,
    setup_target: SetupTarget,
) -> None:
    """The boiler is called Boiler on a device called Boiler, so nothing is left of its
    name once the device's is taken off. The bracket then says the whole name, rather
    than nothing; the pump's says what it is called besides its device."""
    pump = provide_target("switch.pump", SWITCH_SERVICES, name="Pump")
    er.async_get(hass).async_update_entity(
        pump.entity_id, device_id=fake_target.device_id
    )
    boiler_entry = await setup_target()
    pump_entry = await setup_target(target=pump.entity_id)

    await restart(hass, boiler_entry)
    await restart(hass, pump_entry)

    assert "Boiler Run for (Boiler)" in names_of(hass, boiler_entry)
    assert "Boiler Run for (Pump)" in names_of(hass, pump_entry)


async def test_a_disabled_timer_still_counts_for_its_sibling(
    hass: HomeAssistant,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """The user switches off the timer of the second channel. The relay still holds two
    timers, and the first one keeps naming its channel, so that the second one has the
    name it had when it comes back."""
    one = await setup_target(target="switch.relay_1")
    two = await setup_target(target="switch.relay_2")
    await hass.config_entries.async_set_disabled_by(
        two.entry_id, ConfigEntryDisabler.USER
    )

    await restart(hass, one)

    assert "Relay Run for (Channel 1)" in names_of(hass, one)


async def test_a_second_timer_added_while_the_first_runs_renames_it_at_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """The first channel of a relay is running for half an hour, and the user switched
    its interval off. The user adds a timer for the second channel on the integrations
    page. The first one's entities read "(Channel 1)" at once, with the ids and the
    states they had, the relay is not switched, and the countdown ends on time."""
    relay_1, _ = fake_relay
    one = await setup_target(target="switch.relay_1")
    await add_interval(hass, one, start="18:00", end="19:00")
    await set_switch(hass, "switch.relay_schedule_18_00_19_00_mon_sun", False)
    await set_number(hass, "number.relay_run_for", 30)
    events = record_events(hass)

    await add_target(hass, "switch.relay_2")

    run_for = hass.states.get("number.relay_run_for")
    assert run_for is not None
    assert run_for.attributes["friendly_name"] == "Relay Run for (Channel 1)"
    assert run_for.state == "30"
    assert run_for_of(hass, one) == "number.relay_run_for"
    assert state_of(hass, "switch.relay_schedule_18_00_19_00_mon_sun") == "off"
    assert relay_1.calls == [("turn_on", "switch.relay_1")]
    assert events == []

    await advance(hass, freezer, minutes=30)

    assert relay_1.calls[-1] == ("turn_off", "switch.relay_1")
    assert events == [
        (
            EVENT_COUNTDOWN_ENDED,
            {"entity_id": "number.relay_run_for", "reason": "expired"},
        )
    ]


async def test_deleting_one_of_two_timers_makes_the_other_plain_again(
    hass: HomeAssistant,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """The user deletes the timer of the second channel on the integrations page. The
    first one reads "Relay Run for" again, with the entity ids it has had throughout."""
    one = await setup_target(target="switch.relay_1", runtime=True, off_button=True)
    two = await setup_target(target="switch.relay_2")
    assert names_of(hass, one) == relay_names("Channel 1")
    ids = ids_of(hass, one)

    await hass.config_entries.async_remove(two.entry_id)
    await hass.async_block_till_done()

    assert names_of(hass, one) == relay_names(None)
    assert ids_of(hass, one) == ids


async def test_a_timer_whose_file_cannot_be_removed_still_makes_its_sibling_plain(
    hass: HomeAssistant,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """The user deletes the timer of the second channel, and its stored file cannot be
    removed. The timer is gone all the same, and the first one reads "Relay Run for"
    again."""
    one = await setup_target(target="switch.relay_1")
    two = await setup_target(target="switch.relay_2")

    with patch.object(TimerStore, "async_remove", side_effect=OSError("disk error")):
        await hass.config_entries.async_remove(two.entry_id)
        await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(two.entry_id) is None
    assert "Relay Run for" in names_of(hass, one)


async def test_a_name_the_user_gave_survives_both_renames(
    hass: HomeAssistant,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """The user named the Run for of the first channel "Heater timer". Adding a second
    timer to the relay and deleting it again leave that name alone, while the Ends at
    the user did not name follows the count: "(Channel 1)", then plain."""
    one = await setup_target(target="switch.relay_1")
    er.async_get(hass).async_update_entity(run_for_of(hass, one), name="Heater timer")
    await hass.async_block_till_done()

    two = await add_target(hass, "switch.relay_2")

    assert friendly_name(hass, "number.relay_run_for") == "Heater timer"
    assert friendly_name(hass, "sensor.relay_ends_at") == "Relay Ends at (Channel 1)"

    await hass.config_entries.async_remove(two.entry_id)
    await hass.async_block_till_done()

    assert friendly_name(hass, "number.relay_run_for") == "Heater timer"
    assert friendly_name(hass, "sensor.relay_ends_at") == "Relay Ends at"


async def test_a_target_that_moves_between_devices_renames_both_sides(
    hass: HomeAssistant,
    fake_relay: tuple[FakeTarget, FakeTarget],
    provide_target: ProvideTarget,
    setup_target: SetupTarget,
) -> None:
    """The user moves the pump onto the relay's device, in the settings of the pump.
    Its timer and the relay's name their targets, the pump's with the id it had. The
    user moves the pump back, and both are plain again."""
    pump = provide_target("switch.pump", SWITCH_SERVICES, name="Pump")
    relay_entry = await setup_target(target="switch.relay_1")
    pump_entry = await setup_target(target="switch.pump")
    assert "Pump Run for" in names_of(hass, pump_entry)
    assert "Relay Run for" in names_of(hass, relay_entry)

    er.async_get(hass).async_update_entity(
        pump.entity_id, device_id=fake_relay[0].device_id
    )
    await hass.async_block_till_done()

    assert "Relay Run for (Pump)" in names_of(hass, pump_entry)
    assert "Relay Run for (Channel 1)" in names_of(hass, relay_entry)
    assert run_for_of(hass, pump_entry) == "number.pump_run_for"

    er.async_get(hass).async_update_entity(pump.entity_id, device_id=pump.device_id)
    await hass.async_block_till_done()

    assert "Pump Run for" in names_of(hass, pump_entry)
    assert "Relay Run for" in names_of(hass, relay_entry)
    assert run_for_of(hass, pump_entry) == "number.pump_run_for"


async def test_at_start_up_two_timers_on_a_relay_load_once_each(
    hass: HomeAssistant,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """Home Assistant starts with both timers of a relay. Each sees the other one from
    the start, so the first is named when it loads, and the second one's loading does
    not load it again."""
    one = await setup_target(target="switch.relay_1")
    two = await setup_target(target="switch.relay_2")
    await hass.config_entries.async_unload(one.entry_id)
    await hass.config_entries.async_unload(two.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_setup(one.entry_id)
    await hass.async_block_till_done()
    writes = record_writes(hass, "number.relay_run_for")

    await hass.config_entries.async_setup(two.entry_id)
    await hass.async_block_till_done()

    assert writes == []
    assert friendly_name(hass, "number.relay_run_for") == "Relay Run for (Channel 1)"
    assert friendly_name(hass, "number.relay_run_for_channel_2") == (
        "Relay Run for (Channel 2)"
    )


async def test_a_third_timer_on_the_device_reloads_nobody(
    hass: HomeAssistant,
    fake_relay: tuple[FakeTarget, FakeTarget],
    provide_target: ProvideTarget,
    setup_target: SetupTarget,
) -> None:
    """A relay with a third channel gets its third timer, and loses it. Two timers
    already name their channels, and they still do with three and with two again, so
    neither goes unavailable for a moment."""
    provide_target(
        "switch.relay_3",
        SWITCH_SERVICES,
        name="Relay",
        entity_name="Channel 3",
        device_id=fake_relay[0].device_id,
    )
    one = await setup_target(target="switch.relay_1")
    two = await setup_target(target="switch.relay_2")
    writes = [record_writes(hass, run_for_of(hass, entry)) for entry in (one, two)]

    three = await add_target(hass, "switch.relay_3")

    assert writes == [[], []]
    assert "Relay Run for (Channel 3)" in names_of(hass, three)
    assert "Relay Run for (Channel 1)" in names_of(hass, one)
    assert "Relay Run for (Channel 2)" in names_of(hass, two)

    await hass.config_entries.async_remove(three.entry_id)
    await hass.async_block_till_done()

    assert writes == [[], []]
    assert "Relay Run for (Channel 1)" in names_of(hass, one)
    assert "Relay Run for (Channel 2)" in names_of(hass, two)


async def test_a_timer_that_fails_to_load_still_renames_its_sibling(
    hass: HomeAssistant,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """The file of the second channel's timer contradicts itself, so the timer does not
    load. It still has its place on the relay, and the first timer reads "(Channel 1)"
    at once: it comes back to the name it has now when the file is put right."""
    one = await setup_target(target="switch.relay_1")

    two = await setup_target(target="switch.relay_2", stored=payload(scheduled_by="a"))

    assert two.state is ConfigEntryState.SETUP_ERROR
    assert "Relay Run for (Channel 1)" in names_of(hass, one)


async def test_a_deleted_target_leaves_its_sibling_named_until_it_is_loaded_again(
    hass: HomeAssistant,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """The user deletes the second channel's entity. Nothing is reloaded, so both
    timers go on reading their channels. Once the first one loads again it counts no
    other timer on the relay, and reads plain. The second timer, whose target is gone,
    is loaded again with it and loses its bracket too. When the second channel is
    registered again, its timer reloads, and both are named at once."""
    _, relay_2 = fake_relay
    one = await setup_target(target="switch.relay_1")
    two = await setup_target(target="switch.relay_2")
    writes = record_writes(hass, run_for_of(hass, one))

    await relay_2.delete()

    assert writes == []
    assert "Relay Run for (Channel 1)" in names_of(hass, one)
    assert "Relay Run for (Channel 2)" in names_of(hass, two)

    await restart(hass, one)

    assert "Relay Run for" in names_of(hass, one)
    assert two.state is ConfigEntryState.LOADED
    assert not [name for name in names_of(hass, two) if "(Channel 2)" in name]

    await relay_2.restore()

    assert "Relay Run for (Channel 1)" in names_of(hass, one)
    assert "Relay Run for (Channel 2)" in names_of(hass, two)


async def test_a_renamed_target_is_named_in_the_brackets_at_the_next_load(
    hass: HomeAssistant,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """The user renames the first channel of the relay to "Heater" in its settings.
    Its timer is not reloaded for a label, so it goes on reading "(Channel 1)" and
    never goes unavailable. Once it loads again for any other reason, it reads
    "(Heater)"."""
    one = await setup_target(target="switch.relay_1")
    await setup_target(target="switch.relay_2")
    writes = record_writes(hass, run_for_of(hass, one))

    er.async_get(hass).async_update_entity("switch.relay_1", name="Heater")
    await hass.async_block_till_done()

    assert writes == []
    assert "Relay Run for (Channel 1)" in names_of(hass, one)

    await restart(hass, one)

    assert "Relay Run for (Heater)" in names_of(hass, one)
