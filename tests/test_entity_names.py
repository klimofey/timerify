"""The names of a timer's entities: a device that holds more than one timer names the
target of each, so that the user tells them apart wherever the names are listed."""

import pytest
from homeassistant.config_entries import ConfigEntry, ConfigEntryDisabler
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import SWITCH_SERVICES, FakeTarget, ProvideTarget, SetupTarget
from .helpers import add_interval, restart, retitle_interval, run_for_of

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
