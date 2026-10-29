"""Restarts: what a timer does when Home Assistant stops and starts again.

A restart is simulated the two ways it shows: the storage file an earlier run left
is there before the entry is set up, or the entry is unloaded and set up again.
"""

import asyncio
from datetime import timedelta
from typing import Any, Final, Literal

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, HomeAssistant

from custom_components.timerify.store import TimerStore

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    AC_ID,
    AC_NUMBER,
    NUMBER,
    SENSOR,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    advance,
    at,
    payload,
    saved,
    set_number,
    state_of,
    storage_key,
)


async def restart(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Stop the entry and start it again, as a Home Assistant restart does."""
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()


async def test_running_timer_survives_reload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A countdown goes on across a restart and still ends at the same moment."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 45)
    freezer.tick(timedelta(minutes=10))

    await restart(hass, entry)

    assert state_of(hass, NUMBER) == "35"
    assert state_of(hass, SENSOR) == at(45)
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=1)
    assert state_of(hass, NUMBER) == "34"
    await advance(hass, freezer, minutes=33)
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=1)
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, NUMBER) == "0"


@pytest.mark.parametrize(
    ("target_state", "calls"), [("on", [TURN_OFF]), ("off", [])], ids=["on", "off"]
)
async def test_timer_expired_during_downtime_turns_off_on_start(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
    target_state: str,
    calls: list[tuple[str, str]],
) -> None:
    """A countdown that ended while Home Assistant was down is over once it starts.

    A target still on is switched off, exactly once; one that is off is left alone.
    """
    await fake_target.set_state(target_state)

    entry = await setup_target(stored=payload(end=at(-5)))

    assert fake_target.calls == calls
    assert state_of(hass, TARGET_ID) == "off"
    assert state_of(hass, NUMBER) == "0"
    assert saved(hass_storage, entry) == payload()
    await advance(hass, freezer, hours=1)
    assert fake_target.calls == calls


async def test_stored_end_in_the_future_expires_at_that_end(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A countdown restored for a target that is on keeps its end: no switch, no cut."""
    await fake_target.set_state("on")

    await setup_target(stored=payload(end=at(20)))

    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "20"
    await advance(hass, freezer, minutes=19)
    assert fake_target.calls == []
    await advance(hass, freezer, minutes=1)
    assert fake_target.calls == [TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"


async def test_target_off_at_start_clears_stored_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A target found off was switched off meanwhile, which ends the countdown."""
    entry = await setup_target(stored=payload(end=at(20)))

    assert state_of(hass, NUMBER) == "0"
    assert state_of(hass, SENSOR) == "unknown"
    assert saved(hass_storage, entry) == payload()
    await advance(hass, freezer, minutes=30)
    assert fake_target.calls == []


@pytest.mark.parametrize("target_state", ["unavailable", None], ids=["down", "absent"])
async def test_target_unavailable_at_start_waits_for_it(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    target_state: str | None,
) -> None:
    """A target that is not there yet is not switched; it is once it shows up."""
    if target_state is None:
        hass.states.async_remove(TARGET_ID)
    else:
        await fake_target.set_state(target_state)

    await setup_target(stored=payload(end=at(-5)))

    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "0"

    await fake_target.set_state("on")

    assert fake_target.calls == [TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"


@pytest.mark.parametrize(
    ("stored", "target_state", "call", "target_ends_up"),
    [
        pytest.param(
            payload(end=at(30), pending="on"), "off", TURN_ON, "on", id="turn_on"
        ),
        pytest.param(payload(pending="off"), "on", TURN_OFF, "off", id="turn_off"),
    ],
)
async def test_stored_wish_the_target_never_got_is_sent_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
    stored: dict[str, Any],
    target_state: str,
    call: tuple[str, str],
    target_ends_up: str,
) -> None:
    """A switch the target did not get before the restart is asked for at start."""
    await fake_target.set_state(target_state)

    entry = await setup_target(stored=stored)

    assert fake_target.calls == [call]
    assert state_of(hass, TARGET_ID) == target_ends_up
    assert saved(hass_storage, entry)["pending"] is None
    await advance(hass, freezer, minutes=1)
    assert fake_target.calls == [call]


async def test_state_is_saved_on_every_change(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """Setting, extending and stopping the timer each leave the new state stored."""
    entry = await setup_target()
    assert storage_key(entry) not in hass_storage

    await set_number(hass, NUMBER, 45)

    assert hass_storage[storage_key(entry)]["version"] == TimerStore.STORAGE_VERSION
    assert saved(hass_storage, entry) == payload(end=at(45))

    await entry.runtime_data.async_add_minutes(15)

    assert saved(hass_storage, entry) == payload(end=at(60))

    await set_number(hass, NUMBER, 0)

    assert saved(hass_storage, entry) == payload()


async def test_version_1_store_is_migrated(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A timer stored before settings existed is read as one that owes none, and the
    next change writes it in the current form."""
    await fake_target.set_state("on")
    entry = await setup_target(
        stored={"end": at(30), "pending": None}, stored_version=1
    )

    assert state_of(hass, NUMBER) == "30"
    assert hass_storage[storage_key(entry)]["version"] == TimerStore.STORAGE_VERSION
    assert saved(hass_storage, entry) == payload(end=at(30))

    await set_number(hass, NUMBER, 45)

    assert hass_storage[storage_key(entry)]["version"] == TimerStore.STORAGE_VERSION
    assert saved(hass_storage, entry) == payload(end=at(45), owed_settings={})


async def test_owed_settings_survive_restart(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """Settings that were asked for and never confirmed are applied once the timer is
    back, and are then not owed any more."""
    entry = await setup_target(
        target=AC_ID,
        stored=payload(
            end=at(60),
            pending="on",
            owed_settings={"hvac_mode": "cool", "temperature": 24.0},
        ),
    )

    assert fake_climate.call_data == [
        ("set_hvac_mode", {"hvac_mode": "cool"}),
        ("set_temperature", {"temperature": 24.0}),
    ]
    assert state_of(hass, AC_ID) == "cool"
    assert state_of(hass, AC_NUMBER) == "60"
    assert saved(hass_storage, entry) == payload(end=at(60), owed_settings={})


async def test_owed_settings_are_stored_until_the_ac_confirms_them(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """The settings are on file while the device is still working on them, so a restart
    meanwhile applies them again."""
    entry = await setup_target(target=AC_ID)
    slow = fake_climate.hold_next_call()
    start = asyncio.ensure_future(
        entry.runtime_data.async_run(60, {"hvac_mode": "cool", "temperature": 24})
    )
    await slow.reached.wait()

    assert saved(hass_storage, entry) == payload(
        end=at(60),
        pending="on",
        owed_settings={"hvac_mode": "cool", "temperature": 24.0},
    )

    slow.release.set()
    await start
    await hass.async_block_till_done()

    assert saved(hass_storage, entry) == payload(end=at(60))


async def test_expiry_is_saved(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A countdown that runs out on its own is stored as finished."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 45)

    await advance(hass, freezer, minutes=45)

    assert saved(hass_storage, entry) == payload()


async def test_expiry_while_unavailable_turns_off_when_back(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A Wi-Fi drop around expiry, even across a restart, ends with the target off."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 45)
    await fake_target.set_state("unavailable")
    await advance(hass, freezer, minutes=45)
    assert fake_target.calls == [TURN_ON]
    assert saved(hass_storage, entry) == payload(pending="off")

    await restart(hass, entry)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "0"

    await fake_target.set_state("on")

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"
    assert saved(hass_storage, entry) == payload()


async def test_timer_is_saved_before_a_slow_service_call_ends(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A timer is stored as soon as it is set, not when the device finally answers."""
    entry = await setup_target()
    slow = fake_target.hold_next_call()
    start = asyncio.ensure_future(entry.runtime_data.async_set_minutes(45))
    await slow.reached.wait()

    assert saved(hass_storage, entry) == payload(end=at(45), pending="on")

    slow.release.set()
    await start
    await hass.async_block_till_done()

    assert saved(hass_storage, entry) == payload(end=at(45))


async def test_timer_set_during_a_slow_call_survives_a_restart(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Home Assistant stopping while the device is still answering loses no timer.

    The duration differs from the default one: a target found on with nothing stored
    would get the default, which must not pass for the timer that was set.
    """
    entry = await setup_target()
    slow = fake_target.hold_next_call()
    start = asyncio.ensure_future(entry.runtime_data.async_set_minutes(30))
    await slow.reached.wait()
    await hass.config_entries.async_unload(entry.entry_id)
    slow.release.set()  # the device switches on although nobody is listening
    await start

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert state_of(hass, NUMBER) == "30"
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=30)
    assert fake_target.calls == [TURN_ON, TURN_OFF]


type TargetAppears = Literal["before_started", "after_started"]

TARGET_APPEARS: Final[tuple[TargetAppears, ...]] = ("before_started", "after_started")


async def set_up_while_starting(
    hass: HomeAssistant, setup_target: SetupTarget, stored: dict[str, Any]
) -> ConfigEntry:
    """Set up the timer while Home Assistant is still starting and the target's own
    integration has not created its entity yet."""
    hass.set_state(CoreState.not_running)
    hass.states.async_remove(TARGET_ID)
    entry = await setup_target(stored=stored)
    assert hass.state is CoreState.not_running
    return entry


async def finish_start_up(
    hass: HomeAssistant, fake_target: FakeTarget, target_appears: TargetAppears
) -> None:
    """Let Home Assistant announce that it is running. The target's integration comes
    up, with the target switched on, before or after that."""
    if target_appears == "before_started":
        await fake_target.set_state("on")
    await hass.async_start()
    await hass.async_block_till_done()
    assert hass.state is CoreState.running
    if target_appears == "after_started":
        await fake_target.set_state("on")


@pytest.mark.parametrize("target_appears", TARGET_APPEARS)
async def test_countdown_restored_in_a_cold_start_ends_on_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    target_appears: TargetAppears,
) -> None:
    """A countdown stored before a restart is shown while Home Assistant is still
    starting, and runs out at its end whenever the target shows up."""
    await set_up_while_starting(hass, setup_target, payload(end=at(20)))
    assert state_of(hass, NUMBER) == "20"

    await finish_start_up(hass, fake_target, target_appears)

    assert state_of(hass, NUMBER) == "20"
    assert fake_target.calls == []
    await advance(hass, freezer, minutes=19)
    assert fake_target.calls == []

    await advance(hass, freezer, minutes=1)

    assert fake_target.calls == [TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"
    assert state_of(hass, NUMBER) == "0"


@pytest.mark.parametrize("target_appears", TARGET_APPEARS)
async def test_countdown_that_ended_before_a_cold_start_switches_off_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
    target_appears: TargetAppears,
) -> None:
    """A target found on after its countdown ended is switched off, exactly once."""
    entry = await set_up_while_starting(hass, setup_target, payload(end=at(-5)))
    assert fake_target.calls == []

    await finish_start_up(hass, fake_target, target_appears)

    assert fake_target.calls == [TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"
    assert state_of(hass, NUMBER) == "0"
    assert saved(hass_storage, entry) == payload()
    await advance(hass, freezer, hours=1)
    assert fake_target.calls == [TURN_OFF]
