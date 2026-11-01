"""Restarts: what a timer does when Home Assistant stops and starts again.

A restart is simulated the two ways it shows: the storage file an earlier run left
is there before the entry is set up, or the entry is unloaded and set up again.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Final, Literal
from zoneinfo import ZoneInfo

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.timerify.const import freeze_settings
from custom_components.timerify.core import Command
from custom_components.timerify.store import TimerStore, command_to_json

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    AC_ATTRS,
    AC_ID,
    AC_NUMBER,
    NUMBER,
    SENSOR,
    SUNDAY,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    add_command,
    add_interval,
    advance,
    advance_to,
    at,
    call_service,
    command_json,
    iso,
    local,
    open_sunday,
    payload,
    restart,
    restart_after,
    saved,
    set_number,
    set_switch,
    start_call_service,
    start_set_number,
    state_of,
    storage_key,
    timerify_info,
    window_json,
)

MONDAY = SUNDAY + timedelta(days=1)
OFF_AT_MINUS_10: Final = command_json(at(-10), "off")
TIMER_ENDED_WHILE_UNAVAILABLE: Final = (
    "The timer of switch.boiler ended while it is unavailable;"
    " it is turned off when it is back"
)
CAME_DUE_WHILE_UNAVAILABLE: Final = (
    "A pending command for switch.boiler came due while it is unavailable;"
    " it is applied when it is back, if it is still relevant then"
)


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
    assert saved(hass_storage, entry) == payload(end=at(45), started_at=at(0))

    await entry.runtime_data.async_add_minutes(15)

    assert saved(hass_storage, entry) == payload(end=at(60), started_at=at(0))

    await set_number(hass, NUMBER, 0)

    assert saved(hass_storage, entry) == payload()


async def test_version_1_store_is_migrated(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A timer stored before settings and commands existed is read as one that owes
    no settings and waits for no commands, and the next change writes it in the
    current form."""
    await fake_target.set_state("on")
    entry = await setup_target(
        stored={"end": at(30), "pending": None}, stored_version=1
    )

    assert state_of(hass, NUMBER) == "30"
    assert hass_storage[storage_key(entry)]["version"] == TimerStore.STORAGE_VERSION
    assert saved(hass_storage, entry) == payload(end=at(30))

    await set_number(hass, NUMBER, 45)

    assert hass_storage[storage_key(entry)]["version"] == TimerStore.STORAGE_VERSION
    assert saved(hass_storage, entry) == payload(end=at(45), started_at=at(0))


async def test_version_2_store_is_migrated(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A timer stored before schedules existed owes settings that a command asked for,
    so they still reach an AC that is running; the file is written in the current form
    and no longer says anything else of them."""
    await fake_climate.set_state("heat")
    entry = await setup_target(
        target=AC_ID,
        stored={
            "end": at(30),
            "pending": None,
            "owed_settings": {"hvac_mode": "cool"},
            "commands": [],
        },
        stored_version=2,
    )

    assert fake_climate.call_data == [("set_hvac_mode", {"hvac_mode": "cool"})]
    assert state_of(hass, AC_ID) == "cool"
    assert hass_storage[storage_key(entry)]["version"] == TimerStore.STORAGE_VERSION
    assert saved(hass_storage, entry) == payload(end=at(30))
    assert saved(hass_storage, entry)["scheduled_by"] is None
    assert saved(hass_storage, entry)["windows"] == []


async def test_schedule_state_is_stored(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """The file holds the window that is waiting, then the window that runs with the
    timer that carries its end, then the window of the next day."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    interval = await add_interval(hass, entry, start="06:30", end="07:15")

    assert saved(hass_storage, entry) == payload(
        windows=[window_json(interval, local(SUNDAY, "06:30"), local(SUNDAY, "07:15"))]
    )

    await advance_to(hass, freezer, local(SUNDAY, "06:30"))

    assert saved(hass_storage, entry) == payload(
        end=iso(SUNDAY, "07:15"),
        started_at=iso(SUNDAY, "06:30"),
        scheduled_by=interval,
        windows=[
            window_json(
                interval,
                local(SUNDAY, "06:30"),
                local(SUNDAY, "07:15"),
                started=True,
            )
        ],
    )

    await advance_to(hass, freezer, local(SUNDAY, "07:15"))

    monday = SUNDAY + timedelta(days=1)
    assert saved(hass_storage, entry) == payload(
        windows=[window_json(interval, local(monday, "06:30"), local(monday, "07:15"))]
    )


async def test_interval_settings_are_stored_with_their_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """The window keeps what its interval turns the AC on with, so a restart before the
    window starts still turns the AC on that way."""
    await open_sunday(hass, freezer)
    entry = await setup_target(target=AC_ID)
    settings = {"hvac_mode": "cool", "temperature": 24.0}
    interval = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=settings
    )

    assert saved(hass_storage, entry) == payload(
        windows=[
            window_json(
                interval, local(SUNDAY, "06:30"), local(SUNDAY, "07:15"), settings
            )
        ]
    )

    await restart(hass, entry)
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))

    assert fake_climate.call_data == [
        ("set_hvac_mode", {"hvac_mode": "cool"}),
        ("set_temperature", {"temperature": 24.0}),
    ]


async def test_window_stopped_by_hand_is_stored_as_suppressed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """Switching the target off during its window is on file with the window, which is
    what keeps a restart from turning the target on again (S4)."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    interval = await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))

    await fake_target.set_state("off")

    assert saved(hass_storage, entry) == payload(
        windows=[
            window_json(
                interval,
                local(SUNDAY, "06:30"),
                local(SUNDAY, "07:15"),
                started=True,
                suppressed=True,
            )
        ]
    )


@pytest.mark.parametrize(
    ("stored", "complaint"),
    [
        pytest.param(
            payload(
                windows=[
                    window_json("a", local(SUNDAY, "06:30"), local(SUNDAY, "07:15")),
                    window_json("a", local(SUNDAY, "08:30"), local(SUNDAY, "09:15")),
                ]
            ),
            "two windows of the interval a",
            id="two-windows-of-one-interval",
        ),
        pytest.param(
            payload(scheduled_by="a"),
            "scheduled by an interval but has no end",
            id="schedule-without-an-end",
        ),
        pytest.param(
            payload(
                windows=[
                    window_json(
                        "a",
                        local(SUNDAY, "06:30"),
                        local(SUNDAY, "07:15"),
                        suppressed=True,
                    )
                ]
            ),
            "window of a is suppressed but has not started",
            id="suppressed-before-it-started",
        ),
        pytest.param(
            payload(end=at(30), owed_turn_on_only=True),
            "turn-on-only marker is set without owed settings",
            id="marker-without-settings",
        ),
        pytest.param(
            payload(
                windows=[
                    window_json("a", local(SUNDAY, "06:30"), local(SUNDAY, "07:15"))
                ],
                disabled_intervals=["a"],
            ),
            "the interval a is switched off but has a window",
            id="window-of-a-switched-off-interval",
        ),
        pytest.param(
            {**payload(), "disabled_intervals": ["a", "a"]},
            "the interval a is switched off twice",
            id="interval-switched-off-twice",
        ),
        pytest.param(
            payload(
                windows=[
                    {
                        **window_json(
                            "a", local(SUNDAY, "06:30"), local(SUNDAY, "07:15")
                        ),
                        "start": "2026-01-04T04:30:00",
                    }
                ]
            ),
            "the window's start must be timezone-aware",
            id="window-start-without-an-offset",
        ),
        pytest.param(
            payload(
                windows=[
                    {
                        **window_json(
                            "a", local(SUNDAY, "06:30"), local(SUNDAY, "07:15")
                        ),
                        "end": "2026-01-04T05:15:00",
                    }
                ]
            ),
            "the window's end must be timezone-aware",
            id="window-end-without-an-offset",
        ),
        pytest.param(
            payload(
                windows=[
                    window_json("a", local(SUNDAY, "07:15"), local(SUNDAY, "06:30"))
                ]
            ),
            "the window of a must start before it ends and last at most a day",
            id="window-that-ends-before-it-starts",
        ),
        pytest.param(
            payload(
                windows=[
                    window_json("a", local(SUNDAY, "06:30"), local(MONDAY, "06:31"))
                ]
            ),
            "the window of a must start before it ends and last at most a day",
            id="window-longer-than-a-day",
        ),
    ],
)
async def test_file_that_contradicts_itself_is_refused(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
    stored: dict[str, Any],
    complaint: str,
) -> None:
    """The file is read strictly: one that no timer could have written fails the
    set-up with a reason in words, saying what is wrong, instead of running on a state
    nothing makes sense of; the log has the reason, not a bare ValueError."""
    entry = await setup_target(stored=stored)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_domain == "timerify"
    assert entry.error_reason_translation_key == "stored_timer_invalid"
    assert entry.reason is not None
    assert "Remove this timer and add it again" in entry.reason
    assert complaint in entry.reason
    assert complaint in caplog.text
    assert "ValueError" not in caplog.text
    assert fake_target.calls == []


def test_command_is_stored_as_plain_data_in_utc() -> None:
    """The file, and anything else that shows a command, gets its time in UTC whatever
    zone it was made in, and its settings as a plain dict."""
    command = Command(
        "c1",
        datetime(2026, 1, 5, 9, 15, tzinfo=ZoneInfo("Asia/Jerusalem")),
        "on",
        60,
        freeze_settings({"hvac_mode": "cool", "temperature": 24.0}),
    )

    assert command_to_json(command) == command_json(
        at(15),
        minutes=60,
        settings={"hvac_mode": "cool", "temperature": 24.0},
    )


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
    start = start_call_service(
        hass,
        "run",
        {"entity_id": AC_NUMBER},
        minutes=60,
        hvac_mode="cool",
        temperature=24,
    )
    await slow.reached.wait()

    assert saved(hass_storage, entry) == payload(
        end=at(60),
        started_at=at(0),
        pending="on",
        owed_settings={"hvac_mode": "cool", "temperature": 24.0},
    )

    slow.release.set()
    await start
    await hass.async_block_till_done()

    assert saved(hass_storage, entry) == payload(end=at(60), started_at=at(0))


async def test_turn_on_only_settings_survive_a_restart_and_skip_a_running_ac(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """§5.4: a schedule window owed its settings to a turn-on that had not happened when
    Home Assistant stopped; the AC is found running, so nobody pushes them onto it."""
    await fake_climate.set_state("heat")
    entry = await setup_target(
        target=AC_ID,
        stored=payload(
            end=at(30),
            pending="on",
            owed_settings={"hvac_mode": "cool"},
            owed_turn_on_only=True,
        ),
    )

    assert fake_climate.call_data == []
    assert state_of(hass, AC_ID) == "heat"
    assert state_of(hass, AC_NUMBER) == "30"
    assert saved(hass_storage, entry) == payload(end=at(30))


async def test_turn_on_only_settings_survive_a_restart_and_turn_an_off_ac_on(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """The same file with the AC off: the turn-on that was owed goes out with them."""
    entry = await setup_target(
        target=AC_ID,
        stored=payload(
            end=at(30),
            pending="on",
            owed_settings={"hvac_mode": "cool"},
            owed_turn_on_only=True,
        ),
    )

    assert fake_climate.call_data == [("set_hvac_mode", {"hvac_mode": "cool"})]
    assert state_of(hass, AC_ID) == "cool"
    assert saved(hass_storage, entry) == payload(end=at(30))


async def test_partly_applied_window_settings_are_retried_on_the_ac_it_turned_on(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """The window's turn-on switches the AC to heat, and setting the temperature fails:
    the AC runs because of that turn-on, so the temperature is tried again instead of
    being dropped as settings pushed onto a running AC."""
    fake_climate.fail_next_call(service="set_temperature")
    entry = await setup_target(
        target=AC_ID,
        stored=payload(
            end=at(30),
            pending="on",
            owed_settings={"hvac_mode": "heat", "temperature": 22.0},
            owed_turn_on_only=True,
        ),
    )

    assert fake_climate.call_data == [
        ("set_hvac_mode", {"hvac_mode": "heat"}),
        ("set_temperature", {"temperature": 22.0}),
        ("set_hvac_mode", {"hvac_mode": "heat"}),
        ("set_temperature", {"temperature": 22.0}),
    ]
    assert fake_climate.state_attributes["temperature"] == 22.0
    assert saved(hass_storage, entry) == payload(end=at(30))


async def test_turn_on_only_settings_are_stored_while_the_ac_is_away(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """The file keeps the marker with the settings across changes of the timer, so the
    AC that comes back running is still not given them."""
    await fake_climate.set_state("unavailable")
    entry = await setup_target(
        target=AC_ID,
        stored=payload(
            end=at(30),
            pending="on",
            owed_settings={"hvac_mode": "cool"},
            owed_turn_on_only=True,
        ),
    )

    await entry.runtime_data.async_add_minutes(15)

    assert saved(hass_storage, entry) == payload(
        end=at(45),
        pending="on",
        owed_settings={"hvac_mode": "cool"},
        owed_turn_on_only=True,
    )

    await fake_climate.set_state("heat")

    assert fake_climate.call_data == []
    assert saved(hass_storage, entry) == payload(end=at(45))


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


async def test_a_countdown_ended_while_down_is_logged_at_start_up_if_the_target_is_away(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The countdown ended while Home Assistant was down, and the target is away when
    it starts again. The log says, as for a countdown that ends while the target is
    away, that it is turned off when it is back."""
    caplog.set_level(logging.INFO, logger="custom_components.timerify")
    entry = await setup_target()
    await set_number(hass, NUMBER, 10)

    await restart_after(
        hass,
        freezer,
        entry,
        minutes=20,
        while_down=lambda: fake_target.write("unavailable"),
    )

    assert timerify_info(caplog) == [TIMER_ENDED_WHILE_UNAVAILABLE]
    assert fake_target.calls == [TURN_ON]

    await fake_target.set_state("on")

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert timerify_info(caplog) == [TIMER_ENDED_WHILE_UNAVAILABLE]


async def test_a_command_due_while_down_is_logged_at_start_up_if_the_target_is_away(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A pending command came due while Home Assistant was down, and the target is away
    when it starts again. The log says it is applied when the target is back."""
    caplog.set_level(logging.INFO, logger="custom_components.timerify")
    entry = await setup_target()
    await add_command(hass, NUMBER, action="on", delay=10, minutes=30)

    await restart_after(
        hass,
        freezer,
        entry,
        minutes=20,
        while_down=lambda: fake_target.write("unavailable"),
    )

    assert timerify_info(caplog) == [CAME_DUE_WHILE_UNAVAILABLE]
    assert fake_target.calls == []

    await fake_target.set_state("off")

    assert fake_target.calls == [TURN_ON]
    assert timerify_info(caplog) == [CAME_DUE_WHILE_UNAVAILABLE]


async def test_a_change_while_starting_says_nothing_of_a_target_that_has_not_been_seen(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A countdown ended and a command came due while Home Assistant was down. "Run
    for 30" is given while it is still starting, and folds both first. The target has
    not been seen, so it is not known to be unavailable: the log does not say that
    anything came due while it is. The target is not unavailable when it appears."""
    caplog.set_level(logging.INFO, logger="custom_components.timerify")
    await set_up_while_starting(
        hass,
        setup_target,
        payload(end=at(-10), started_at=at(-40), commands=[OFF_AT_MINUS_10]),
    )

    await set_number(hass, NUMBER, 30)

    assert state_of(hass, NUMBER) == "30"
    assert timerify_info(caplog) == []

    await finish_start_up(hass, fake_target, "after_started")

    assert timerify_info(caplog) == []
    assert fake_target.calls == []


async def test_start_up_logs_what_came_due_since_the_last_change_while_starting_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A countdown ended while Home Assistant was down, and a command is due ten
    minutes into the start. A command given while it is starting folds the countdown
    first, which says nothing, as the target has not been seen. Start-up finds the
    target unavailable and folds the due command: the log mentions that command once,
    and the countdown, which start-up did not fold, not at all."""
    caplog.set_level(logging.INFO, logger="custom_components.timerify")
    await set_up_while_starting(
        hass,
        setup_target,
        payload(
            end=at(-10), started_at=at(-40), commands=[command_json(at(10), minutes=30)]
        ),
    )
    await add_command(hass, NUMBER, action="on", delay=60, minutes=5)
    assert timerify_info(caplog) == []
    freezer.tick(timedelta(minutes=10))  # the alarm of the due command has not fired

    await finish_start_up(hass, fake_target, "before_started", "unavailable")

    assert timerify_info(caplog) == [CAME_DUE_WHILE_UNAVAILABLE]
    assert fake_target.calls == []
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert timerify_info(caplog) == [CAME_DUE_WHILE_UNAVAILABLE]

    await fake_target.set_state("off")

    assert timerify_info(caplog) == [CAME_DUE_WHILE_UNAVAILABLE]
    assert fake_target.calls == [TURN_ON]


async def test_timer_is_saved_before_a_slow_service_call_ends(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A timer is stored as soon as it is set, not when the device finally answers."""
    entry = await setup_target()
    slow = fake_target.hold_next_call()
    start = start_set_number(hass, NUMBER, 45)
    await slow.reached.wait()

    assert saved(hass_storage, entry) == payload(
        end=at(45), started_at=at(0), pending="on"
    )

    slow.release.set()
    await start
    await hass.async_block_till_done()

    assert saved(hass_storage, entry) == payload(end=at(45), started_at=at(0))


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
    start = start_set_number(hass, NUMBER, 30)
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
    hass: HomeAssistant,
    setup_target: SetupTarget,
    stored: dict[str, Any],
    target: str = TARGET_ID,
) -> ConfigEntry:
    """Set up the timer while Home Assistant is still starting and the target's own
    integration has not created its entity yet."""
    hass.set_state(CoreState.not_running)
    hass.states.async_remove(target)
    entry = await setup_target(target=target, stored=stored)
    assert hass.state is CoreState.not_running
    return entry


async def finish_start_up(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    target_appears: TargetAppears,
    target_state: str = "on",
) -> None:
    """Let Home Assistant announce that it is running. The target's integration comes
    up, with the target in `target_state`, before or after that."""
    if target_appears == "before_started":
        await fake_target.set_state(target_state)
    await hass.async_start()
    await hass.async_block_till_done()
    assert hass.state is CoreState.running
    if target_appears == "after_started":
        await fake_target.set_state(target_state)


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


type CommandWhileStarting = Literal["run_for", "add_time", "run"]


async def give_command(hass: HomeAssistant, command: CommandWhileStarting) -> None:
    """Give the timer a command that runs the target for 30 minutes: by the slider, or
    by one of the services."""
    match command:
        case "run_for":
            await set_number(hass, NUMBER, 30)
        case "add_time":
            await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=30)
        case "run":
            await call_service(hass, "run", {"entity_id": NUMBER}, minutes=30)


@pytest.mark.parametrize("command", ["run_for", "add_time", "run"])
async def test_a_command_given_while_starting_is_saved_and_sends_nothing_until_started(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
    command: CommandWhileStarting,
) -> None:
    """A change made while Home Assistant is still starting is kept and saved, and
    nothing is sent to a target that has not been seen. Once Home Assistant has
    started, the target is found where the change wants it, and the change is carried
    out when it falls due."""
    entry = await set_up_while_starting(hass, setup_target, payload())

    await give_command(hass, command)

    assert fake_target.calls == []
    assert saved(hass_storage, entry) == payload(
        end=at(30), started_at=at(0), pending="on"
    )

    await finish_start_up(hass, fake_target, "after_started")

    assert fake_target.calls == []
    await advance(hass, freezer, minutes=30)
    assert fake_target.calls == [TURN_OFF]


@pytest.mark.parametrize("target_appears", TARGET_APPEARS)
async def test_adding_time_while_starting_to_a_countdown_that_ended_while_down(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
    target_appears: TargetAppears,
) -> None:
    """The countdown ended while Home Assistant was down, and nothing has folded it
    yet. "Add time" runs the target for the added minutes from now, as it does with
    Home Assistant running; the target is not turned off at start-up."""
    entry = await set_up_while_starting(
        hass, setup_target, payload(end=at(-40), started_at=at(-70))
    )

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=30)

    assert fake_target.calls == []
    assert saved(hass_storage, entry) == payload(
        end=at(30), started_at=at(0), pending="on"
    )

    await finish_start_up(hass, fake_target, target_appears)

    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "30"
    await advance(hass, freezer, minutes=30)
    assert fake_target.calls == [TURN_OFF]


async def test_a_command_added_while_starting_comes_after_what_came_due_while_down(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A countdown ended while Home Assistant was down. A pending command added while
    it is still starting comes after that end, which is folded first but sent to a
    target that has not been seen only at start-up, once. The command itself runs at
    its own time."""
    entry = await set_up_while_starting(
        hass, setup_target, payload(end=at(-10), started_at=at(-40))
    )

    await add_command(hass, NUMBER, action="on", delay=60, minutes=5)

    assert fake_target.calls == []
    stored = saved(hass_storage, entry)
    assert (stored["end"], stored["pending"]) == (None, "off")
    assert len(stored["commands"]) == 1

    await finish_start_up(hass, fake_target, "before_started")

    assert fake_target.calls == [TURN_OFF]
    assert len(saved(hass_storage, entry)["commands"]) == 1
    await advance(hass, freezer, minutes=60)
    assert fake_target.calls == [TURN_OFF, TURN_ON]
    await advance(hass, freezer, minutes=5)
    assert fake_target.calls == [TURN_OFF, TURN_ON, TURN_OFF]


async def test_switching_an_interval_while_starting_changes_the_timer_only(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """An interval switched off and on while Home Assistant is starting changes the
    timer as it would with Home Assistant running: the flag goes and comes back, and
    so does the window. Nothing is sent to the target."""
    await open_sunday(hass, freezer)
    entry = await set_up_while_starting(hass, setup_target, payload())
    interval = await add_interval(hass, entry, start="08:00", end="09:00")
    interval_switch = "switch.boiler_schedule_08_00_09_00_mon_sun"

    await set_switch(hass, interval_switch, False)

    assert saved(hass_storage, entry) == payload(disabled_intervals=[interval])
    assert fake_target.calls == []

    await set_switch(hass, interval_switch, True)

    assert saved(hass_storage, entry) == payload(
        windows=[window_json(interval, local(SUNDAY, "08:00"), local(SUNDAY, "09:00"))]
    )
    assert fake_target.calls == []

    await finish_start_up(hass, fake_target, "before_started")

    assert saved(hass_storage, entry)["windows"] == [
        window_json(interval, local(SUNDAY, "08:00"), local(SUNDAY, "09:00"))
    ]
    assert fake_target.calls == []


async def test_switching_off_the_interval_that_carries_the_countdown_while_starting(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """The window of an interval carries the countdown when Home Assistant stops. The
    interval is switched off while Home Assistant is still starting: the countdown
    follows the window that is gone at once, as with Home Assistant running. The
    target, which has not been seen, is turned off at start-up, once."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    interval = await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == [TURN_ON]
    await hass.config_entries.async_unload(entry.entry_id)
    hass.set_state(CoreState.not_running)
    hass.states.async_remove(TARGET_ID)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await set_switch(hass, "switch.boiler_schedule_06_30_07_15_mon_sun", False)

    assert saved(hass_storage, entry) == payload(
        pending="off", disabled_intervals=[interval]
    )
    assert fake_target.calls == [TURN_ON]

    await finish_start_up(hass, fake_target, "before_started")

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert saved(hass_storage, entry) == payload(disabled_intervals=[interval])
    await advance(hass, freezer, hours=1)
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_a_report_of_the_target_while_starting_folds_nothing_until_started(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """The target's integration comes up and reports before Home Assistant has
    started. The report is not answered then. The countdown that ended while Home
    Assistant was down and the window that opened after it are folded together, once,
    at start-up: the target stays on, and is switched off once when the window ends."""
    await open_sunday(hass, freezer)
    entry = await set_up_while_starting(
        hass,
        setup_target,
        payload(end=iso(SUNDAY, "05:50"), started_at=iso(SUNDAY, "05:20")),
    )
    interval = await add_interval(hass, entry, start="05:55", end="06:30")

    await fake_target.set_state("on")

    assert fake_target.calls == []
    assert saved(hass_storage, entry)["end"] == iso(SUNDAY, "05:50")
    assert saved(hass_storage, entry)["windows"] == []

    await hass.async_start()
    await hass.async_block_till_done()

    assert fake_target.calls == []
    assert saved(hass_storage, entry) == payload(
        end=iso(SUNDAY, "06:30"),
        started_at=iso(SUNDAY, "05:55"),
        scheduled_by=interval,
        windows=[
            window_json(
                interval, local(SUNDAY, "05:55"), local(SUNDAY, "06:30"), started=True
            )
        ],
    )
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == [TURN_OFF]
    await advance(hass, freezer, hours=1)
    assert fake_target.calls == [TURN_OFF]


async def test_settings_given_while_starting_wait_for_the_ac_and_go_out_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A turn-on that never reached the air conditioner is stored. A command given
    while Home Assistant is still starting adds settings to it. Nothing is sent to an
    air conditioner that has not been seen. At start-up the settings go out once."""
    # The registry remembers what the air conditioner can do from the run before.
    er.async_get(hass).async_update_entity(
        AC_ID,
        capabilities={k: v for k, v in AC_ATTRS.items() if k != "supported_features"},
        supported_features=AC_ATTRS["supported_features"],
    )
    entry = await set_up_while_starting(
        hass,
        setup_target,
        payload(end=at(60), started_at=at(0), pending="on"),
        target=AC_ID,
    )

    await call_service(
        hass,
        "run",
        {"entity_id": AC_NUMBER},
        minutes=30,
        hvac_mode="cool",
        temperature=24,
    )

    assert fake_climate.calls == []
    assert saved(hass_storage, entry) == payload(
        end=at(30),
        started_at=at(0),
        pending="on",
        owed_settings={"hvac_mode": "cool", "temperature": 24.0},
    )

    await fake_climate.set_state("heat")  # it reports before Home Assistant has started

    assert fake_climate.calls == []

    await hass.async_start()
    await hass.async_block_till_done()

    assert fake_climate.call_data == [
        ("set_hvac_mode", {"hvac_mode": "cool"}),
        ("set_temperature", {"temperature": 24.0}),
    ]
    assert saved(hass_storage, entry) == payload(end=at(30), started_at=at(0))
    await advance(hass, freezer, minutes=1)
    assert len(fake_climate.call_data) == 2


@pytest.mark.parametrize("target_appears", TARGET_APPEARS)
@pytest.mark.parametrize(
    ("command", "stored"),
    [
        (
            "run_for",
            payload(end=at(20), started_at=at(-10), commands=[OFF_AT_MINUS_10]),
        ),
        (
            "add_time",
            payload(end=at(-40), started_at=at(-70), commands=[OFF_AT_MINUS_10]),
        ),
    ],
    ids=["run_for_on_a_running_countdown", "add_time_on_an_ended_countdown"],
)
async def test_a_command_while_starting_wins_over_what_came_due_while_down(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
    command: CommandWhileStarting,
    stored: dict[str, Any],
    target_appears: TargetAppears,
) -> None:
    """A pending "off" came due while Home Assistant was down. A command given while it
    is still starting comes after it, as it would with Home Assistant running: the
    "off" is spent, and the target runs for the 30 minutes of the command."""
    entry = await set_up_while_starting(hass, setup_target, stored)

    await give_command(hass, command)

    assert fake_target.calls == []
    assert saved(hass_storage, entry) == payload(
        end=at(30), started_at=at(0), pending="on"
    )

    await finish_start_up(hass, fake_target, target_appears)

    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "30"
    assert saved(hass_storage, entry) == payload(end=at(30), started_at=at(0))
    await advance(hass, freezer, minutes=29)
    assert fake_target.calls == []
    await advance(hass, freezer, minutes=1)
    assert fake_target.calls == [TURN_OFF]


@pytest.mark.parametrize("target_appears", TARGET_APPEARS)
async def test_stopping_while_starting_overrides_a_window_that_opened_while_down(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
    target_appears: TargetAppears,
) -> None:
    """A schedule window opened while Home Assistant was down. "Run for 0" while it is
    still starting stops the timer as it would with Home Assistant running: the window
    counts as stopped by hand, so start-up turns the target off and the window does not
    turn it on again."""
    await open_sunday(hass, freezer)
    entry = await set_up_while_starting(hass, setup_target, payload())
    interval = await add_interval(hass, entry, start="05:30", end="06:30")
    stopped_window = window_json(
        interval,
        local(SUNDAY, "05:30"),
        local(SUNDAY, "06:30"),
        started=True,
        suppressed=True,
    )

    await set_number(hass, NUMBER, 0)

    assert fake_target.calls == []
    assert saved(hass_storage, entry) == payload(
        pending="off", windows=[stopped_window]
    )

    await finish_start_up(hass, fake_target, target_appears)

    assert fake_target.calls == [TURN_OFF]
    assert saved(hass_storage, entry) == payload(windows=[stopped_window])
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == [TURN_OFF]
    assert saved(hass_storage, entry)["windows"] == [
        window_json(interval, local(MONDAY, "05:30"), local(MONDAY, "06:30"))
    ]


async def test_commands_while_starting_apply_in_order_with_what_came_due_between(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """Home Assistant takes a while to start. "Run for 30" is given, a pending "off"
    comes due, and then "Run for 10" is given. Each applies at its own moment, as with
    Home Assistant running: the last word is the second command's."""
    entry = await set_up_while_starting(
        hass, setup_target, payload(commands=[command_json(at(5), "off")])
    )

    await set_number(hass, NUMBER, 30)
    await advance(hass, freezer, minutes=10)
    await set_number(hass, NUMBER, 10)

    assert fake_target.calls == []
    assert saved(hass_storage, entry) == payload(
        end=at(20), started_at=at(10), pending="on"
    )

    await finish_start_up(hass, fake_target, "before_started")

    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "10"
    await advance(hass, freezer, minutes=9)
    assert fake_target.calls == []
    await advance(hass, freezer, minutes=1)
    assert fake_target.calls == [TURN_OFF]


@pytest.mark.parametrize("target_appears", TARGET_APPEARS)
async def test_a_command_while_starting_survives_a_restart_before_start_up_ends(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
    target_appears: TargetAppears,
) -> None:
    """A pending "off" came due while Home Assistant was down, and "Run for 30" is
    given while it is starting. Home Assistant restarts again before it has started.
    The saved timer holds the command's outcome, so it is still in force after the
    second start-up."""
    entry = await set_up_while_starting(
        hass,
        setup_target,
        payload(end=at(20), started_at=at(-10), commands=[OFF_AT_MINUS_10]),
    )
    await set_number(hass, NUMBER, 30)

    await hass.config_entries.async_unload(entry.entry_id)
    await advance(hass, freezer, minutes=1)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert fake_target.calls == []
    assert saved(hass_storage, entry) == payload(
        end=at(30), started_at=at(0), pending="on"
    )

    await finish_start_up(hass, fake_target, target_appears)

    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "29"
    await advance(hass, freezer, minutes=29)
    assert fake_target.calls == [TURN_OFF]


async def test_adding_time_while_starting_after_a_countdown_by_hand_ended_while_down(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A countdown set by hand inside a schedule window ended while Home Assistant was
    down, which stopped that window. "Add time 30" while starting comes after that end:
    the window stays stopped, and a later window carries the timer to its own end, as
    with Home Assistant running."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    first = await add_interval(hass, entry, start="06:05", end="08:00")
    second = await add_interval(hass, entry, start="06:50", end="07:20")
    await advance_to(hass, freezer, local(SUNDAY, "06:05"))
    await set_number(hass, NUMBER, 15)
    assert fake_target.calls == [TURN_ON]
    await hass.config_entries.async_unload(entry.entry_id)
    hass.set_state(CoreState.not_running)
    hass.states.async_remove(TARGET_ID)
    freezer.move_to(local(SUNDAY, "06:40"))
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=30)

    assert saved(hass_storage, entry) == payload(
        end=iso(SUNDAY, "07:10"),
        started_at=iso(SUNDAY, "06:40"),
        pending="on",
        windows=[
            window_json(
                first,
                local(SUNDAY, "06:05"),
                local(SUNDAY, "08:00"),
                started=True,
                suppressed=True,
            ),
            window_json(second, local(SUNDAY, "06:50"), local(SUNDAY, "07:20")),
        ],
    )

    await finish_start_up(hass, fake_target, "before_started")
    await advance_to(hass, freezer, local(SUNDAY, "06:50"))

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:20")

    await advance_to(hass, freezer, local(SUNDAY, "07:20"))

    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_a_countdown_given_while_starting_runs_out_while_still_starting(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """Home Assistant takes long to start. "Run for 30" is given while it is starting,
    and the 30 minutes run out before it has started. The countdown ends at its time,
    as with Home Assistant running, though the target, not seen yet, is sent nothing.
    Start-up turns it off, once."""
    entry = await set_up_while_starting(hass, setup_target, payload())
    await set_number(hass, NUMBER, 30)

    await advance(hass, freezer, minutes=30)

    assert fake_target.calls == []
    assert state_of(hass, SENSOR) == "unknown"
    assert saved(hass_storage, entry) == payload(pending="off")

    await finish_start_up(hass, fake_target, "before_started")

    assert fake_target.calls == [TURN_OFF]
    await advance(hass, freezer, hours=1)
    assert fake_target.calls == [TURN_OFF]
