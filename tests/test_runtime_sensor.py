"""The Runtime sensor of a timer: how long the target was on, counted once a minute."""

import copy
import logging
from datetime import timedelta
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY, ConfigEntryState
from homeassistant.const import (
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.timerify.const import CONF_RUNTIME, DOMAIN, Mode

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    AC_ID,
    AC_RUNTIME,
    NEXT,
    NUMBER,
    RUNTIME,
    SENSOR,
    START,
    TARGET_ID,
    add_command,
    advance,
    advance_to,
    call_service,
    record_writes,
    restart,
    restart_after,
    runtime_saved,
    runtime_storage_key,
    set_number,
    state_of,
    storage_key,
)

RENAMED_ID = "switch.water_heater"
RENAMED_RUNTIME = "sensor.boiler_on_time"


def runtime_of(hass: HomeAssistant, entity_id: str = RUNTIME) -> float:
    """The minutes a Runtime sensor shows. A sensor that is unavailable or unknown has
    no number to show, so reading one fails the test that did it."""
    return float(state_of(hass, entity_id))


async def count_minutes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    minutes: int,
    entity_id: str = RUNTIME,
) -> list[float]:
    """Let `minutes` pass one at a time, as a clock does, and return what the sensor
    showed after each."""
    shown: list[float] = []
    for _ in range(minutes):
        await advance(hass, freezer, minutes=1)
        shown.append(runtime_of(hass, entity_id))
    return shown


async def test_runtime_sensor_is_a_total_in_minutes(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The sensor is a duration in minutes that only goes up, so that Home Assistant
    sums it into daily and weekly figures; it is shown in whole minutes, and a timer
    that has not seen the boiler on has counted nothing."""
    await setup_target(runtime=True)

    state = hass.states.get(RUNTIME)
    assert state is not None
    assert state.attributes["friendly_name"] == "Boiler Runtime"
    assert state.attributes["device_class"] == "duration"
    assert state.attributes["state_class"] == "total_increasing"
    assert state.attributes["unit_of_measurement"] == "min"
    assert "last_reset" not in state.attributes
    assert float(state.state) == 0.0
    registered = er.async_get(hass).async_get(RUNTIME)
    assert registered is not None
    assert registered.options["sensor"]["suggested_display_precision"] == 0


async def test_a_countdown_is_counted_once_a_minute(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """ "Run for 45" counts up one minute at a time, to 45, and stops with the boiler:
    one write for each minute, none after the countdown ended."""
    await setup_target(runtime=True)
    await set_number(hass, NUMBER, 45)
    writes = record_writes(hass, RUNTIME)

    shown = await count_minutes(hass, freezer, 46)

    assert shown == [*(float(minute) for minute in range(1, 46)), 45.0]
    assert [float(write) for write in writes] == [float(m) for m in range(1, 46)]
    assert state_of(hass, TARGET_ID) == "off"


@pytest.mark.parametrize(
    ("mode", "countdown"), [("loose", "0"), ("strict", "25")], ids=["loose", "strict"]
)
async def test_a_manual_run_outside_timerify_is_counted(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    mode: Mode,
    countdown: str,
) -> None:
    """The boiler is switched on at the wall and off again 20 minutes later, and the
    timer was not asked for any of it. A loose timer leaves the run alone, a strict
    one makes it a countdown of its default 45 minutes and clears that when the
    boiler is switched off; the boiler was on for 20 minutes either way."""
    await setup_target(mode=mode, runtime=True)
    await fake_target.set_state("on")

    await advance(hass, freezer, minutes=20)

    assert runtime_of(hass) == 20.0
    assert state_of(hass, NUMBER) == countdown
    await fake_target.set_state("off")
    await advance(hass, freezer, minutes=1)
    assert runtime_of(hass) == 20.0
    assert state_of(hass, NUMBER) == "0"


async def test_a_flapping_target_is_written_once_a_minute(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A relay that chatters, five on and off pairs in 20 seconds, with a command
    added, a countdown started and stopped, and the timer telling its entities about
    each: the sensor writes nothing until the next tick, then once, with the seconds
    the boiler was on, rounded."""
    await setup_target(mode="loose", runtime=True)
    await advance(hass, freezer, minutes=1)  # The first tick: nothing was on.
    writes = record_writes(hass, RUNTIME)

    for _ in range(5):  # On for two seconds, off for two: ten seconds on.
        await fake_target.set_state("on")
        await advance(hass, freezer, seconds=2)
        await fake_target.set_state("off")
        await advance(hass, freezer, seconds=2)
    await add_command(hass, NUMBER, action="on", delay=30, minutes=10)
    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=1)
    await advance(hass, freezer, seconds=10)  # The countdown turned it on: ten more.
    await set_number(hass, NUMBER, 0)
    await advance(hass, freezer, seconds=28)

    assert writes == []
    assert runtime_of(hass) == 0.0

    await advance(hass, freezer, seconds=2)  # 07:02:00, the tick of 07:01:59.
    assert [float(write) for write in writes] == [0.33]  # 20 seconds.
    await advance(hass, freezer, minutes=1)
    assert len(writes) == 1


async def test_a_restart_while_on_continues_and_never_goes_down(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Home Assistant restarts while the boiler has been on for 10 minutes: the sensor
    shows what it showed before at once, and goes on from there."""
    entry = await setup_target(mode="loose", runtime=True)
    await fake_target.set_state("on")
    await advance(hass, freezer, minutes=10)
    assert runtime_of(hass) == 10.0

    await restart(hass, entry)

    assert runtime_of(hass) == 10.0
    await advance(hass, freezer, minutes=1)
    assert runtime_of(hass) == 11.0


async def test_a_reload_between_two_ticks_loses_no_seconds(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A change of the timer's settings reloads it half a minute after a tick: the half
    minute the boiler has been on since is not lost, and shows at the next tick."""
    entry = await setup_target(mode="loose", runtime=True)
    await fake_target.set_state("on")
    await advance(hass, freezer, minutes=10)
    await advance(hass, freezer, seconds=30)

    await restart(hass, entry)

    assert runtime_of(hass) == 10.5
    await advance(hass, freezer, seconds=30)
    assert runtime_of(hass) == 11.0


async def test_a_stop_between_two_ticks_loses_no_seconds(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Home Assistant is stopped half a minute after a tick, as an update or a restart
    from the settings does. A stop unloads no timer, yet the half minute the boiler has
    been on since is in the file when it has stopped, and the timer started again from
    it shows it."""
    entry = await setup_target(mode="loose", runtime=True)
    await fake_target.set_state("on")
    await advance(hass, freezer, minutes=10)
    await advance(hass, freezer, seconds=30)
    assert runtime_saved(hass_storage, entry) == 600.0

    # What Home Assistant does: it is stopping when the integrations are told to stop,
    # and the final write follows.
    hass.set_state(CoreState.stopping)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    hass.set_state(CoreState.final_write)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
    await hass.async_block_till_done()

    assert runtime_saved(hass_storage, entry) == 630.0
    # The next start finds the file as the stop left it.
    key = runtime_storage_key(entry)
    left_by_the_stop = copy.deepcopy(hass_storage[key])
    await hass.config_entries.async_unload(entry.entry_id)
    hass.set_state(CoreState.running)
    hass_storage[key] = left_by_the_stop
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert runtime_of(hass) == 10.5
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []


async def test_downtime_is_not_counted(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Home Assistant is down for 30 minutes with the boiler on, and nobody knows what
    the boiler did meanwhile: the 30 minutes are not counted, and the count goes on
    from the moment it is back, as the timer treats a change it did not see."""
    entry = await setup_target(mode="loose", runtime=True)
    await fake_target.set_state("on")
    await advance(hass, freezer, minutes=10)

    await restart_after(hass, freezer, entry, minutes=30)

    assert runtime_of(hass) == 10.0
    await advance(hass, freezer, minutes=1)
    assert runtime_of(hass) == 11.0


async def test_stored_total_is_never_behind_what_was_shown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """The file holds at least the figure the sensor shows, after every tick and after
    a reload on a clock that was set back; a timer started again from that file shows
    at least the last figure, so the statistics never see the total go down."""
    entry = await setup_target(mode="loose", runtime=True)
    await fake_target.set_state("on")
    for _ in range(10):
        await advance(hass, freezer, minutes=1)
        assert round(runtime_saved(hass_storage, entry) / 60, 2) >= runtime_of(hass)
    assert runtime_of(hass) == 10.0

    # The clock is corrected five minutes back, and the timer is reloaded two later,
    # when the boiler has been on for seven minutes by the corrected clock.
    await advance_to(hass, freezer, START + timedelta(minutes=5))
    await advance(hass, freezer, minutes=2)
    await restart(hass, entry)

    assert round(runtime_saved(hass_storage, entry) / 60, 2) >= 10.0
    assert runtime_of(hass) >= 10.0


async def test_a_crash_between_two_ticks_never_lowers_the_value(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """Home Assistant dies half a minute after a tick, without a word: what an unload
    would have saved is not written. The timer started again from the file shows at
    least the figure it showed."""
    entry = await setup_target(mode="loose", runtime=True)
    await fake_target.set_state("on")
    await advance(hass, freezer, minutes=10)
    await advance(hass, freezer, seconds=30)
    shown = runtime_of(hass)
    key = runtime_storage_key(entry)
    left_by_the_crash = copy.deepcopy(hass_storage[key])

    await hass.config_entries.async_unload(entry.entry_id)
    hass_storage[key] = left_by_the_crash
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert shown == 10.0
    assert runtime_of(hass) >= shown


async def test_an_unavailable_target_pauses_the_count(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A plug that drops off the network does not count while nobody can tell if it is
    on, and counts again when it reports. The sensor keeps its figure meanwhile: it is
    a total, which cards and automations read."""
    await setup_target(mode="loose", runtime=True)
    await fake_target.set_state("on")
    shown = await count_minutes(hass, freezer, 5)

    await fake_target.set_state("unavailable")
    shown += await count_minutes(hass, freezer, 10)
    await fake_target.set_state("unknown")
    shown += await count_minutes(hass, freezer, 5)
    await fake_target.set_state("on")
    shown += await count_minutes(hass, freezer, 5)

    assert shown == [1.0, 2.0, 3.0, 4.0, 5.0, *[5.0] * 15, 6.0, 7.0, 8.0, 9.0, 10.0]


async def test_clock_going_back_never_lowers_the_value(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The clock is corrected five minutes back while the boiler is on. The figure
    stays at 10 while the clock repeats those five minutes, and goes on once it has
    passed them: it never goes down, and the repeated minutes are counted once, on the
    corrected clock, so the count ends at 15 where the boiler was on for 20 minutes by
    the clocks together. The sensor cannot tell a correction from time, so it
    undercounts the five minutes and never counts them twice."""
    await setup_target(mode="loose", runtime=True)
    await fake_target.set_state("on")
    await count_minutes(hass, freezer, 10)
    assert runtime_of(hass) == 10.0

    await advance_to(hass, freezer, START + timedelta(minutes=5))
    shown = await count_minutes(hass, freezer, 10)

    assert shown == [10.0, 10.0, 10.0, 10.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0]


async def test_renaming_the_target_mid_run_keeps_the_counter(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The boiler's entity is renamed after 10 minutes on: the timer follows it, the
    sensor keeps its entity id and its total, and goes on counting the new entity."""
    entry = await setup_target(mode="loose", runtime=True)
    await fake_target.set_state("on")
    await advance(hass, freezer, minutes=10)

    # What the target's own integration does when its entity is renamed.
    er.async_get(hass).async_update_entity(TARGET_ID, new_entity_id=RENAMED_ID)
    hass.states.async_remove(TARGET_ID)
    hass.states.async_set(RENAMED_ID, "on")
    await hass.async_block_till_done()

    assert (
        er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_runtime"
        )
        == RUNTIME
    )
    assert runtime_of(hass) == 10.0
    assert await count_minutes(hass, freezer, 10) == [
        float(minute) for minute in range(11, 21)
    ]
    hass.states.async_set(RENAMED_ID, "off")
    await advance(hass, freezer, minutes=1)
    assert runtime_of(hass) == 20.0


async def test_renaming_the_runtime_sensor_keeps_its_total(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """The user gives the Runtime sensor another entity id after nine and a half
    minutes on: Home Assistant takes the entity out and adds it again, and the figure
    goes on from there, instead of going back to what was stored when the timer was set
    up. The figure the sensor shows when it comes back is in the file before it is
    shown, as with every figure, so a crash right after cannot bring it back down."""
    entry = await setup_target(mode="loose", runtime=True)
    await fake_target.set_state("on")
    await advance(hass, freezer, minutes=9)
    assert runtime_of(hass) == 9.0

    # 570.4 s are 9.5067 minutes, which show as 9.51, the same as 570.6 s do.
    await advance(hass, freezer, seconds=30.4)
    er.async_get(hass).async_update_entity(RUNTIME, new_entity_id=RENAMED_RUNTIME)
    await hass.async_block_till_done()

    assert hass.states.get(RUNTIME) is None
    assert runtime_of(hass, RENAMED_RUNTIME) == 9.51
    assert runtime_saved(hass_storage, entry) >= 9.51 * 60
    await advance(hass, freezer, seconds=29.6)
    assert runtime_of(hass, RENAMED_RUNTIME) == 10.0
    await advance(hass, freezer, minutes=1)
    assert runtime_of(hass, RENAMED_RUNTIME) == 11.0


async def test_two_timers_count_on_their_own(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A boiler and an air conditioner each have their own figure and their own file.
    The air conditioner going from heating to cooling is one run, not two, and taking
    one timer away leaves the other counting."""
    boiler = await setup_target(mode="loose", runtime=True)
    air_conditioner = await setup_target(mode="loose", target=AC_ID, runtime=True)
    await fake_target.set_state("on")
    await advance(hass, freezer, minutes=2)
    await fake_climate.set_state("heat")
    await advance(hass, freezer, minutes=2)
    await fake_climate.set_state("cool")
    await advance(hass, freezer, minutes=2)
    await fake_climate.set_state("off")
    await advance(hass, freezer, minutes=4)

    assert runtime_of(hass, RUNTIME) == 10.0
    assert runtime_of(hass, AC_RUNTIME) == 4.0
    assert runtime_saved(hass_storage, boiler) == 600.0
    assert runtime_saved(hass_storage, air_conditioner) == 240.0

    await hass.config_entries.async_unload(air_conditioner.entry_id)
    await advance(hass, freezer, minutes=5)

    assert runtime_of(hass, RUNTIME) == 15.0
    assert state_of(hass, AC_RUNTIME) == "unavailable"


@pytest.mark.parametrize(
    "counting_off", [{}, {CONF_RUNTIME: False}], ids=["key removed", "set to False"]
)
async def test_disabling_the_counter_removes_its_entity(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    counting_off: dict[str, bool],
) -> None:
    """A timer that stops counting loses the sensor, not only its state: after a
    restart no unavailable entity is left, and no entry in the registry. Counting again
    gives the same entity back with the total it had, without the minutes in between."""
    entry = await setup_target(mode="loose", runtime=True)
    registry = er.async_get(hass)
    await fake_target.set_state("on")
    await advance(hass, freezer, minutes=10)

    hass.config_entries.async_update_entry(
        entry,
        options={
            **{k: v for k, v in entry.options.items() if k != CONF_RUNTIME},
            **counting_off,
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get(RUNTIME) is None
    assert registry.async_get(RUNTIME) is None
    await restart(hass, entry)
    assert hass.states.get(RUNTIME) is None
    assert registry.async_get(RUNTIME) is None

    await advance(hass, freezer, minutes=5)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_RUNTIME: True}
    )
    await hass.async_block_till_done()

    registered = registry.async_get(RUNTIME)
    assert registered is not None
    assert registered.unique_id == f"{entry.entry_id}_runtime"
    assert runtime_of(hass) == 10.0
    await advance(hass, freezer, minutes=1)
    assert runtime_of(hass) == 11.0


async def test_disabling_the_runtime_entity_pauses_the_count(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """The user disables the Runtime entity after 10 minutes on, and the boiler stays on
    for 20 more. Enabling it again (Home Assistant reloads the timer a moment later)
    shows the 10 minutes it had, not the 20 nobody counted, and the count goes on."""
    entry = await setup_target(mode="loose", runtime=True)
    registry = er.async_get(hass)
    await fake_target.set_state("on")
    await advance(hass, freezer, minutes=10)
    assert runtime_of(hass) == 10.0

    registry.async_update_entity(RUNTIME, disabled_by=er.RegistryEntryDisabler.USER)
    await hass.async_block_till_done()

    await advance(hass, freezer, minutes=20)
    assert hass.states.get(RUNTIME) is None
    assert runtime_saved(hass_storage, entry) == 600.0

    registry.async_update_entity(RUNTIME, disabled_by=None)
    await advance(hass, freezer, seconds=RELOAD_AFTER_UPDATE_DELAY)

    assert runtime_of(hass) == 10.0
    await advance(hass, freezer, minutes=1)
    assert runtime_of(hass) == 11.0


async def test_a_runtime_file_of_a_newer_release_fails_only_its_sensor(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """After a downgrade the file of the count was written by a release that Timerify
    does not know. Starting from zero would write over its total, so the Runtime sensor
    is not set up, and Home Assistant says why in the log; the timer's other sensors
    are there, and the file is as it was."""
    written_by_the_next_release = {"seconds": 900.0, "also": "something new"}

    entry = await setup_target(
        runtime=True,
        stored_runtime=written_by_the_next_release,
        stored_runtime_version=2,
    )
    file = copy.deepcopy(hass_storage[runtime_storage_key(entry)])

    assert hass.states.get(RUNTIME) is None
    assert hass.states.get(SENSOR) is not None
    assert hass.states.get(NEXT) is not None
    assert hass.states.get(NUMBER) is not None
    assert entry.state is ConfigEntryState.LOADED
    assert "UnsupportedStorageVersionError" in caplog.text
    assert "Error while setting up timerify platform for sensor" in caplog.text
    await hass.config_entries.async_unload(entry.entry_id)
    assert hass_storage[runtime_storage_key(entry)] == file
    assert file["version"] == 2
    assert file["data"] == written_by_the_next_release


async def test_removing_the_timer_deletes_the_runtime_file(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """Deleting a timer leaves no file of its state behind, and none of its total."""
    entry = await setup_target(runtime=True)
    await set_number(hass, NUMBER, 30)
    await advance(hass, freezer, minutes=3)
    assert storage_key(entry) in hass_storage
    assert runtime_storage_key(entry) in hass_storage

    await hass.config_entries.async_remove(entry.entry_id)

    assert storage_key(entry) not in hass_storage
    assert runtime_storage_key(entry) not in hass_storage


async def test_a_timer_without_the_option_has_no_runtime_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A timer made before the counter existed has no option for it: it has no Runtime
    sensor, and no file of a total, however long the boiler runs."""
    entry = await setup_target()
    assert CONF_RUNTIME not in entry.options

    await fake_target.set_state("on")
    await advance(hass, freezer, minutes=5)
    await restart(hass, entry)

    assert hass.states.get(RUNTIME) is None
    assert er.async_get(hass).async_get(RUNTIME) is None
    assert runtime_storage_key(entry) not in hass_storage
