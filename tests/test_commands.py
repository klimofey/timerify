"""Pending commands: what a timer does with the commands that wait in its storage.

Commands reach the timer through the storage file here, as they do after a restart;
the services that create them are a later addition.
"""

import logging
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.timerify.const import CONF_TARGET

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    AC_ID,
    AC_NUMBER,
    NUMBER,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    advance,
    at,
    command_json,
    payload,
    saved,
    set_number,
    state_of,
    timerify_info,
)

RENAMED_ID = "switch.water_heater"
DROPPED = (
    "Dropped the pending command to turn switch.boiler on at 2026-01-04 22:20:00-08:00:"
    " the run it asked for was already over"
)
"""What is logged for a command whose run was over before it could start: its time is
in the local time of the tests, US/Pacific."""


async def test_stored_command_runs_on_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A command waits for its time, turns the target on for its minutes and is gone."""
    entry = await setup_target(
        stored=payload(commands=[command_json(at(10), minutes=30)])
    )

    await advance(hass, freezer, minutes=9)

    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "0"

    await advance(hass, freezer, minutes=1)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "30"
    assert saved(hass_storage, entry) == payload(end=at(40))
    await advance(hass, freezer, minutes=30)
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_command_due_during_downtime_runs_for_the_rest(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A command that came due while Home Assistant was down runs for what is left of
    its minutes, counted from its time."""
    entry = await setup_target(
        stored=payload(commands=[command_json(at(-10), minutes=30)])
    )

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "20"
    assert saved(hass_storage, entry) == payload(end=at(20))


async def test_command_whose_time_ran_out_during_downtime_is_dropped(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A run that was over before Home Assistant came back is not started late; the
    command is dropped and the log says which."""
    caplog.set_level(logging.INFO, logger="custom_components.timerify")

    entry = await setup_target(
        stored=payload(commands=[command_json(at(-40), minutes=30)])
    )

    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "0"
    assert timerify_info(caplog) == [DROPPED]
    assert saved(hass_storage, entry) == payload()


async def test_expired_timer_and_late_command_after_restart_keep_target_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """The timer ran out while Home Assistant was down, but the command that came due
    just before it asks for an hour: the target is not switched off and on again, it
    simply runs for the rest of that hour."""
    await fake_target.set_state("on")

    entry = await setup_target(
        stored=payload(end=at(-5), commands=[command_json(at(-10), minutes=60)])
    )

    assert fake_target.calls == []
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, NUMBER) == "50"
    assert saved(hass_storage, entry) == payload(end=at(50))
    await advance(hass, freezer, minutes=50)
    assert fake_target.calls == [TURN_OFF]


async def test_late_command_with_settings_reaches_a_running_ac_after_restart(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The AC kept running through the restart and its command came due meanwhile: it
    is put into cooling at 24, not switched off and on."""
    await fake_climate.set_state("heat")

    await setup_target(
        target=AC_ID,
        stored=payload(
            end=at(-5),
            commands=[
                command_json(
                    at(-10),
                    minutes=60,
                    settings={"hvac_mode": "cool", "temperature": 24.0},
                )
            ],
        ),
    )

    assert fake_climate.call_data == [
        ("set_hvac_mode", {"hvac_mode": "cool"}),
        ("set_temperature", {"temperature": 24.0}),
    ]
    assert state_of(hass, AC_ID) == "cool"
    assert state_of(hass, AC_NUMBER) == "50"


async def test_command_due_while_unavailable_runs_when_back(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A Wi-Fi drop at the command's time is not a reason to lose it: the timer starts
    at once, and the target is switched on when it is back (R10)."""
    caplog.set_level(logging.INFO, logger="custom_components.timerify")
    await setup_target(stored=payload(commands=[command_json(at(10), minutes=30)]))
    await fake_target.set_state("unavailable")

    await advance(hass, freezer, minutes=10)

    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "30"
    assert timerify_info(caplog) == [
        "A pending command for switch.boiler came due while it is unavailable;"
        " it is carried out when it is back"
    ]

    await fake_target.set_state("off")

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"


async def test_command_survives_target_rename(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The target is renamed while a command waits: the entry reloads and the command
    runs on the new entity id."""
    entry = await setup_target(
        stored=payload(commands=[command_json(at(10), minutes=30)])
    )

    # What the target's own integration does when its entity is renamed.
    er.async_get(hass).async_update_entity(TARGET_ID, new_entity_id=RENAMED_ID)
    hass.states.async_remove(TARGET_ID)
    fake_target.entity_id = RENAMED_ID
    fake_target.write("off")
    await hass.async_block_till_done()

    assert entry.options[CONF_TARGET] == RENAMED_ID
    assert entry.state is ConfigEntryState.LOADED
    await advance(hass, freezer, minutes=10)

    assert fake_target.calls == [("turn_on", RENAMED_ID)]
    assert state_of(hass, RENAMED_ID) == "on"
    assert state_of(hass, NUMBER) == "30"


async def test_off_command_stops_a_running_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A command to turn off ends the countdown that is still running."""
    await fake_target.set_state("on")
    await setup_target(
        stored=payload(end=at(60), commands=[command_json(at(10), action="off")])
    )
    assert state_of(hass, NUMBER) == "60"

    await advance(hass, freezer, minutes=10)

    assert fake_target.calls == [TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"
    assert state_of(hass, NUMBER) == "0"


async def test_commands_run_in_turn_with_the_end_of_each_countdown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The one alarm moves from command to end to command: each waits its turn."""
    await setup_target(
        stored=payload(
            commands=[
                command_json(at(10), minutes=5, id="c1"),
                command_json(at(20), minutes=5, id="c2"),
            ]
        )
    )

    await advance(hass, freezer, minutes=10)
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=5)
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    await advance(hass, freezer, minutes=5)
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]
    await advance(hass, freezer, minutes=5)
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON, TURN_OFF]


async def test_command_that_extends_the_timer_moves_its_end(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A command resets the countdown: the old end passes unnoticed, the new one
    switches the target off."""
    await fake_target.set_state("on")
    await setup_target(
        stored=payload(end=at(30), commands=[command_json(at(10), minutes=60)])
    )

    await advance(hass, freezer, minutes=10)
    assert state_of(hass, NUMBER) == "60"
    await advance(hass, freezer, minutes=30)
    assert fake_target.calls == []
    await advance(hass, freezer, minutes=29)
    assert fake_target.calls == []
    await advance(hass, freezer, minutes=1)
    assert fake_target.calls == [TURN_OFF]


async def test_command_at_the_end_of_the_timer_extends_it_without_a_flap(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The command is due at the very moment the countdown ends: the target stays
    on and runs for the command's minutes."""
    await fake_target.set_state("on")
    await setup_target(
        stored=payload(end=at(10), commands=[command_json(at(10), minutes=30)])
    )

    await advance(hass, freezer, minutes=10)

    assert fake_target.calls == []
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, NUMBER) == "30"
    await advance(hass, freezer, minutes=30)
    assert fake_target.calls == [TURN_OFF]


async def test_command_extending_the_timer_while_unavailable_is_not_logged_as_its_end(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The timer did not end, as a command that was due with it carried it on: the
    log mentions the command only."""
    caplog.set_level(logging.INFO, logger="custom_components.timerify")
    await fake_target.set_state("on")
    await setup_target(
        stored=payload(end=at(10), commands=[command_json(at(10), minutes=30)])
    )
    await fake_target.set_state("unavailable")

    await advance(hass, freezer, minutes=10)

    assert timerify_info(caplog) == [
        "A pending command for switch.boiler came due while it is unavailable;"
        " it is carried out when it is back"
    ]
    assert state_of(hass, NUMBER) == "30"


async def test_command_dropped_while_unavailable_is_only_logged_as_dropped(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The clock jumps past the end of the run a command asked for, with the target
    away: nothing is carried out when it is back, and the log must not say it is."""
    caplog.set_level(logging.INFO, logger="custom_components.timerify")
    await setup_target(stored=payload(commands=[command_json(at(10), minutes=5)]))
    await fake_target.set_state("unavailable")

    await advance(hass, freezer, minutes=40)
    await fake_target.set_state("off")

    assert fake_target.calls == []
    assert timerify_info(caplog) == [
        "Dropped the pending command to turn switch.boiler on at"
        " 2026-01-04 23:10:00-08:00: the run it asked for was already over"
    ]


async def test_manual_use_does_not_cancel_a_command(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Switching the target on and off by hand, and stopping the timer, leaves the
    command: at its time it still starts the run (P2)."""
    await setup_target(stored=payload(commands=[command_json(at(10), minutes=30)]))
    await set_number(hass, NUMBER, 20)
    await fake_target.set_state("off")
    assert state_of(hass, NUMBER) == "0"

    await advance(hass, freezer, minutes=10)

    assert fake_target.calls == [TURN_ON, TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, NUMBER) == "30"


async def test_stored_commands_are_kept_as_they_were_written(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """Everything a command carries is stored and read back: a change of the timer
    writes the waiting commands out unchanged."""
    commands = [
        command_json(
            at(30),
            minutes=60,
            settings={"hvac_mode": "cool", "temperature": 24.0},
            id="cool",
        ),
        command_json(at(90), action="off", id="off"),
        command_json(at(120), id="plain"),
    ]
    entry = await setup_target(target=AC_ID, stored=payload(commands=commands))

    await set_number(hass, AC_NUMBER, 10)

    assert saved(hass_storage, entry) == payload(end=at(10), commands=commands)
