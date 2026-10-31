"""Pending commands: what a timer does with the commands that wait for their time.

Most commands reach the timer through the storage file, as they do after a restart;
the last tests make them the way the user does, with `timerify.add_command`, and
look at them on the "Next command" sensor.
"""

import logging
import re
from datetime import timedelta
from typing import Any, Literal

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from custom_components.timerify.const import CONF_TARGET, DOMAIN, MAX_COMMANDS
from custom_components.timerify.controller import command_when

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    AC_ENDS_AT,
    AC_ID,
    AC_NEXT,
    AC_NUMBER,
    NEXT,
    NUMBER,
    START,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    add_command,
    advance,
    at,
    call_service,
    command_json,
    payload,
    record_writes,
    saved,
    set_number,
    state_of,
    storage_key,
    timerify_info,
)

RENAMED_ID = "switch.water_heater"
DROPPED = (
    "Dropped the pending command to turn switch.boiler on at 2026-01-04 22:20:00-08:00:"
    " the run it asked for was already over"
)
"""What is logged for a command whose run was over before it could start: its time is
in the local time of the tests, US/Pacific."""
CAME_DUE_WHILE_UNAVAILABLE = (
    "A pending command for switch.boiler came due while it is unavailable;"
    " it is applied when it is back, if it is still relevant then"
)
"""What is logged for a command that falls due while the target is away."""


def listed(hass: HomeAssistant, entity_id: str) -> list[dict[str, Any]]:
    """The commands a "Next command" sensor lists in its attributes."""
    state = hass.states.get(entity_id)
    assert state is not None
    commands: list[dict[str, Any]] = state.attributes["commands"]
    return commands


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
    assert saved(hass_storage, entry) == payload(end=at(40), started_at=at(10))
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
    assert saved(hass_storage, entry) == payload(end=at(20), started_at=at(-10))


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
    assert saved(hass_storage, entry) == payload(end=at(50), started_at=at(-10))
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
    assert timerify_info(caplog) == [CAME_DUE_WHILE_UNAVAILABLE]

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

    assert timerify_info(caplog) == [CAME_DUE_WHILE_UNAVAILABLE]
    assert state_of(hass, NUMBER) == "30"


async def test_open_run_command_at_the_end_while_unavailable_is_not_logged_as_its_end(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A loose-mode command to turn on without minutes, due as the countdown ends,
    leaves the timer at zero but wants the target on: the log must not say that the
    target is turned off when it is back, and it is turned on."""
    caplog.set_level(logging.INFO, logger="custom_components.timerify")
    await fake_target.set_state("on")
    await setup_target(
        mode="loose", stored=payload(end=at(10), commands=[command_json(at(10))])
    )
    await fake_target.set_state("unavailable")

    await advance(hass, freezer, minutes=10)
    await fake_target.set_state("off")

    assert timerify_info(caplog) == [CAME_DUE_WHILE_UNAVAILABLE]
    assert state_of(hass, NUMBER) == "0"
    assert fake_target.calls == [TURN_ON]


async def test_command_whose_run_ends_while_unavailable_never_turns_the_target_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A five minute run that was due when the target dropped off Wi-Fi is over before
    it is back: the target is not switched on late, and the log says what happened."""
    caplog.set_level(logging.INFO, logger="custom_components.timerify")
    await setup_target(stored=payload(commands=[command_json(at(10), minutes=5)]))
    await fake_target.set_state("unavailable")

    await advance(hass, freezer, minutes=10)
    assert state_of(hass, NUMBER) == "5"
    await advance(hass, freezer, minutes=5)
    assert state_of(hass, NUMBER) == "0"
    await fake_target.set_state("off")

    assert fake_target.calls == []
    assert state_of(hass, TARGET_ID) == "off"
    assert timerify_info(caplog) == [
        CAME_DUE_WHILE_UNAVAILABLE,
        "The timer of switch.boiler ended while it is unavailable;"
        " it is turned off when it is back",
    ]


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

    assert saved(hass_storage, entry) == payload(
        end=at(10), started_at=at(0), commands=commands
    )


async def test_ac_in_15_minutes_for_an_hour_cooling_24(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """ "Turn on in 15 minutes for an hour, cooling, 24": the AC is running by remote
    meanwhile, and at the time it is put into cooling at 24 with an hour on the clock
    (P1)."""
    await setup_target(target=AC_ID)
    await fake_climate.set_state("heat")  # on by remote: strict gives it 45 minutes

    response = await add_command(
        hass,
        AC_NUMBER,
        action="on",
        delay=15,
        minutes=60,
        hvac_mode="cool",
        temperature=24,
    )

    command_id = response[AC_NUMBER]["command_id"]
    assert re.fullmatch(r"[0-9a-f]{32}", command_id)
    assert state_of(hass, AC_NEXT) == "2026-01-05T07:15:00+00:00"
    assert listed(hass, AC_NEXT) == [
        command_json(
            "2026-01-05T07:15:00+00:00",
            minutes=60,
            settings={"hvac_mode": "cool", "temperature": 24.0},
            id=command_id,
        )
    ]

    await advance(hass, freezer, minutes=15)

    assert fake_climate.call_data == [
        ("set_hvac_mode", {"hvac_mode": "cool"}),
        ("set_temperature", {"temperature": 24.0}),
    ]
    assert state_of(hass, AC_NUMBER) == "60"
    assert state_of(hass, AC_ENDS_AT) == "2026-01-05T08:15:00+00:00"
    assert state_of(hass, AC_NEXT) == "unknown"


async def test_manual_use_between_now_and_the_command_does_not_cancel_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Someone switches the boiler on and off by hand before the command is due: the
    timer follows them (45 minutes, then none), and the command still turns the boiler
    on for 30 at its time (P2)."""
    await setup_target()
    await add_command(hass, NUMBER, action="on", delay=10, minutes=30)

    await fake_target.set_state("on")
    assert state_of(hass, NUMBER) == "45"
    await advance(hass, freezer, minutes=5)
    await fake_target.set_state("off")
    assert state_of(hass, NUMBER) == "0"
    assert state_of(hass, NEXT) == "2026-01-05T07:10:00+00:00"

    await advance(hass, freezer, minutes=5)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, NUMBER) == "30"
    assert state_of(hass, NEXT) == "unknown"


async def test_cancel_command_removes_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A cancelled command is gone from the sensor and the file, and nothing happens
    at its time."""
    entry = await setup_target()
    response = await add_command(hass, NUMBER, action="on", delay=10, minutes=30)
    command_id = response[NUMBER]["command_id"]
    assert state_of(hass, NEXT) == "2026-01-05T07:10:00+00:00"

    await call_service(
        hass, "cancel_command", {"entity_id": NUMBER}, command_id=command_id
    )

    assert state_of(hass, NEXT) == "unknown"
    assert listed(hass, NEXT) == []
    assert saved(hass_storage, entry) == payload()
    await advance(hass, freezer, minutes=10)
    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "0"


async def test_cancel_unknown_command_is_rejected(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Cancelling a command that is not there says so, and leaves the others."""
    await setup_target()
    await add_command(hass, NUMBER, action="on", delay=10)

    with pytest.raises(ServiceValidationError) as raised:
        await call_service(
            hass, "cancel_command", {"entity_id": NUMBER}, command_id="nope"
        )

    assert raised.value.translation_key == "unknown_command"
    assert raised.value.translation_placeholders == {"command_id": "nope"}
    assert state_of(hass, NEXT) == "2026-01-05T07:10:00+00:00"


async def test_cancel_through_another_timer_is_rejected(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A command belongs to the timer that made it: asking another timer to cancel it
    fails, and the owner's command still runs."""
    await setup_target()
    await setup_target(target=AC_ID)
    response = await add_command(hass, NUMBER, action="on", delay=10, minutes=30)
    command_id = response[NUMBER]["command_id"]

    with pytest.raises(ServiceValidationError) as raised:
        await call_service(
            hass, "cancel_command", {"entity_id": AC_NUMBER}, command_id=command_id
        )

    assert raised.value.translation_key == "unknown_command"
    assert state_of(hass, NEXT) == "2026-01-05T07:10:00+00:00"
    await advance(hass, freezer, minutes=10)
    assert fake_target.calls == [TURN_ON]
    assert fake_climate.calls == []


async def test_cancelling_a_command_gives_it_back(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The controller says which command it cancelled, with everything the command
    held, and leaves the others."""
    entry = await setup_target(
        stored=payload(
            commands=[
                command_json(at(10), minutes=30, settings={}, id="early"),
                command_json(at(20), "off", id="late"),
            ]
        )
    )

    cancelled = await entry.runtime_data.async_cancel_command("late")

    assert (cancelled.id, cancelled.action, cancelled.at) == (
        "late",
        "off",
        START + timedelta(minutes=20),
    )
    assert [c["id"] for c in listed(hass, NEXT)] == ["early"]


@pytest.mark.parametrize(
    ("which", "cancelled", "left"),
    [
        pytest.param("next", ["first"], ["second", "third"], id="the-next"),
        pytest.param("all", ["first", "second", "third"], [], id="all"),
    ],
)
async def test_cancelling_the_next_or_all_commands(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
    which: Literal["next", "all"],
    cancelled: list[str],
    left: list[str],
) -> None:
    """The command that is due first, or every one, goes in one step; what goes is
    given back in the order the commands are due, and the sensor and the file follow."""
    entry = await setup_target(
        stored=payload(
            commands=[
                command_json(at(10), id="first"),
                command_json(at(20), "off", id="second"),
                command_json(at(20), id="third"),
            ]
        )
    )

    gone = await entry.runtime_data.async_cancel_commands(which)

    assert [c.id for c in gone] == cancelled
    assert [c["id"] for c in listed(hass, NEXT)] == left
    assert [c["id"] for c in saved(hass_storage, entry)["commands"]] == left


async def test_cancelling_the_next_of_two_commands_due_together_takes_the_first_added(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Commands due at the same moment run in the order they were added, so the one
    added first is the next one, and the other is next after it."""
    entry = await setup_target()
    controller = entry.runtime_data
    first = (await add_command(hass, NUMBER, action="on", delay=10, minutes=30))[NUMBER]
    second = (await add_command(hass, NUMBER, action="on", delay=10, minutes=60))[
        NUMBER
    ]
    await add_command(hass, NUMBER, action="off", delay=20)

    (gone,) = await controller.async_cancel_commands("next")
    (then,) = await controller.async_cancel_commands("next")

    assert gone.id == first["command_id"]
    assert then.id == second["command_id"]
    assert [c["action"] for c in listed(hass, NEXT)] == ["off"]


@pytest.mark.parametrize("which", ["next", "all"])
async def test_cancelling_commands_when_none_is_pending_changes_nothing(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    which: Literal["next", "all"],
) -> None:
    entry = await setup_target()
    writes = record_writes(hass, NEXT)

    gone = await entry.runtime_data.async_cancel_commands(which)

    assert gone == ()
    assert writes == []
    assert fake_target.calls == []


async def test_cancelled_commands_run_no_more_and_the_countdown_goes_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Cancelling every command leaves the alarm of the countdown as it was: the timer
    that runs still ends at its time, and a command that was cancelled does not turn
    the target on again then."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 30)
    await add_command(hass, NUMBER, action="on", delay=10, minutes=60)
    await add_command(hass, NUMBER, action="on", delay=20, minutes=60)

    await entry.runtime_data.async_cancel_commands("all")
    await advance(hass, freezer, minutes=30)

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, NUMBER) == "0"


async def test_off_command_turns_target_off_on_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A running timer is stopped by a command to turn off at its time."""
    await setup_target()
    await set_number(hass, NUMBER, 45)
    await add_command(hass, NUMBER, action="off", delay=10)

    await advance(hass, freezer, minutes=10)

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"
    assert state_of(hass, NUMBER) == "0"


async def test_command_at_is_local_time(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The date and time picker gives no zone: it means the time on the wall of the
    house, in Home Assistant's time zone, not UTC."""
    await hass.config.async_set_time_zone("Asia/Jerusalem")
    await setup_target()

    await add_command(hass, NUMBER, action="on", at="2026-01-05 09:30:00")

    assert state_of(hass, NEXT) == "2026-01-05T07:30:00+00:00"


async def test_command_at_names_its_own_zone(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A time that carries its zone is taken as it says, and shown in UTC."""
    await setup_target()

    await add_command(hass, NUMBER, action="on", at="2026-01-05T09:30:00+02:00")

    assert state_of(hass, NEXT) == "2026-01-05T07:30:00+00:00"


@pytest.mark.parametrize(
    ("data", "key", "placeholders"),
    [
        (
            {"action": "on", "delay": 5, "at": "2026-01-05T08:00:00+00:00"},
            "delay_or_at",
            None,
        ),
        ({"action": "on"}, "delay_or_at", None),
        (
            {"action": "on", "at": "2026-01-05T06:59:00+00:00"},
            "command_in_past",
            {"at": "2026-01-04 22:59:00-08:00"},
        ),
        (
            {"action": "on", "at": "2026-01-05T07:00:00+00:00"},
            "command_in_past",
            {"at": "2026-01-04 23:00:00-08:00"},
        ),
        (
            {"action": "on", "at": "2026-01-12T07:01:00+00:00"},
            "command_too_far",
            {"days": "7"},
        ),
        (
            {"action": "off", "delay": 5, "minutes": 10},
            "off_takes_no_duration_or_settings",
            None,
        ),
        (
            {"action": "off", "delay": 5, "hvac_mode": "cool"},
            "off_takes_no_duration_or_settings",
            None,
        ),
        (
            {"action": "on", "delay": 5, "hvac_mode": "cool"},
            "setting_not_supported",
            {"target": "Boiler", "setting": "hvac_mode"},
        ),
    ],
    ids=[
        "delay_and_at",
        "neither",
        "past",
        "now",
        "too_far",
        "off_with_minutes",
        "off_with_settings",
        "settings_the_target_cannot_take",
    ],
)
async def test_invalid_commands_are_rejected(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
    data: dict[str, Any],
    key: str,
    placeholders: dict[str, str] | None,
) -> None:
    """A command that cannot be kept is refused with a reason when it is made, and
    nothing is stored; `at` must lie after now and within a week."""
    entry = await setup_target()

    with pytest.raises(ServiceValidationError) as raised:
        await add_command(hass, NUMBER, **data)

    assert raised.value.translation_key == key
    assert raised.value.translation_placeholders == placeholders
    assert state_of(hass, NEXT) == "unknown"
    assert storage_key(entry) not in hass_storage
    await advance(hass, freezer, hours=1)
    assert fake_target.calls == []


def test_a_command_is_due_after_a_delay_or_at_a_time() -> None:
    """Exactly one of the two says when; a delay of nothing is still a delay, and the
    controller refuses it as a time that is not ahead."""
    delay = timedelta(minutes=5)
    moment = START + delay

    assert command_when(delay, None) == delay
    assert command_when(timedelta(0), None) == timedelta(0)
    assert command_when(None, moment) == moment
    for both_or_neither in ((delay, moment), (None, None), (timedelta(0), moment)):
        with pytest.raises(ServiceValidationError) as raised:
            command_when(*both_or_neither)
        assert raised.value.translation_key == "delay_or_at"


@pytest.mark.parametrize(
    "delay",
    [
        timedelta(days=7, seconds=1),
        timedelta(days=4 * 10**6),
        timedelta.max,
    ],
    ids=["a_second_over_the_week", "centuries", "the_longest_delay_there_is"],
)
@pytest.mark.parametrize("action", ["on", "off"])
async def test_a_delay_too_long_to_be_a_date_is_refused_not_added_to_now(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    action: str,
    delay: timedelta,
) -> None:
    """The controller is the one path that every caller, a service, a voice command or
    a tool, takes, so a delay they cannot all bound is refused here with a reason,
    before it is added to the time now: it would not be a date."""
    entry = await setup_target()
    controller = entry.runtime_data

    with pytest.raises(ServiceValidationError) as raised_command:
        await controller.async_add_command(action, delay, None, None)
    with pytest.raises(ServiceValidationError) as raised_turn_off:
        await controller.async_turn_off_in(delay)

    assert raised_command.value.translation_key == "command_too_far"
    assert raised_turn_off.value.translation_key == "duration_out_of_range"
    assert state_of(hass, NEXT) == "unknown"
    assert fake_target.calls == []


async def test_command_the_week_ahead_is_accepted(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The last moment a command may be set for is a week from now, and the longest
    delay is that week in minutes."""
    await setup_target()

    await add_command(hass, NUMBER, action="on", at="2026-01-12T07:00:00+00:00")
    await add_command(hass, NUMBER, action="on", delay=10080)

    assert [c["at"] for c in listed(hass, NEXT)] == [
        "2026-01-12T07:00:00+00:00",
        "2026-01-12T07:00:00+00:00",
    ]


async def test_delay_of_a_command_that_waited_for_a_slow_device_counts_from_its_turn(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A cloud air conditioner takes 25 seconds for each of the three calls that turn
    it on cooling, at 24, with a fan mode. A command for one minute from now that waits
    behind them is not refused as already passed: it is due a minute after its turn."""
    await setup_target(target=AC_ID)
    slow = fake_climate.hold_next_call()
    running = hass.async_create_task(
        hass.services.async_call(
            DOMAIN,
            "run",
            {
                "entity_id": AC_NUMBER,
                "hvac_mode": "cool",
                "temperature": 24,
                "fan_mode": "high",
            },
            blocking=True,
        )
    )
    await slow.reached.wait()
    adding = hass.async_create_task(
        hass.services.async_call(
            DOMAIN,
            "add_command",
            {"entity_id": AC_NUMBER, "action": "off", "delay": 1},
            blocking=True,
            return_response=True,
        )
    )

    for _ in range(2):
        freezer.tick(timedelta(seconds=25))
        finished, slow = slow, fake_climate.hold_next_call()
        finished.release.set()
        await slow.reached.wait()
    freezer.tick(timedelta(seconds=25))
    slow.release.set()
    await running
    response = await adding
    await hass.async_block_till_done()

    assert response is not None
    assert [(c["id"], c["at"]) for c in listed(hass, AC_NEXT)] == [
        (response[AC_NUMBER]["command_id"], "2026-01-05T07:02:15+00:00")
    ]


async def test_command_with_settings_the_target_refuses_is_rejected_when_made(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The AC has no dry mode: the user hears it now, not when the command comes due."""
    await setup_target(target=AC_ID)

    with pytest.raises(ServiceValidationError) as raised:
        await add_command(hass, AC_NUMBER, action="on", delay=5, hvac_mode="dry")

    assert raised.value.translation_key == "setting_not_an_option"
    assert state_of(hass, AC_NEXT) == "unknown"


async def test_twenty_first_command_is_rejected(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A timer keeps twenty commands; the next one is refused and the twenty stay."""
    await setup_target()
    for minute in range(1, MAX_COMMANDS + 1):
        await add_command(hass, NUMBER, action="on", delay=minute)

    with pytest.raises(ServiceValidationError) as raised:
        await add_command(hass, NUMBER, action="on", delay=30)

    assert raised.value.translation_key == "too_many_commands"
    assert raised.value.translation_placeholders == {
        "target": "Boiler",
        "limit": str(MAX_COMMANDS),
    }
    assert len(listed(hass, NEXT)) == MAX_COMMANDS


async def test_command_for_several_timers_returns_one_id_each(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Aimed at two timers at once, the service gives each its own command and answers
    with the id of each, by timer."""
    await setup_target()
    await setup_target(target=AC_ID)

    response = await add_command(
        hass, [NUMBER, AC_NUMBER], action="on", delay=5, minutes=20
    )

    assert response.keys() == {NUMBER, AC_NUMBER}
    assert response[NUMBER]["command_id"] != response[AC_NUMBER]["command_id"]
    await advance(hass, freezer, minutes=5)
    assert fake_target.calls == [TURN_ON]
    assert fake_climate.calls == [("turn_on", AC_ID)]
    assert state_of(hass, NUMBER) == "20"
    assert state_of(hass, AC_NUMBER) == "20"


async def test_next_command_shows_a_command_on_an_idle_timer(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """With no countdown running, a new command still appears on the sensor at once."""
    await setup_target()
    assert state_of(hass, NEXT) == "unknown"

    await add_command(hass, NUMBER, action="on", delay=30)

    assert state_of(hass, NEXT) == "2026-01-05T07:30:00+00:00"
    assert state_of(hass, NUMBER) == "0"


async def test_next_command_shows_the_earliest_command_first(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Commands made out of order are listed by time, and when the first has run the
    sensor moves on to the next."""
    await setup_target()
    await add_command(hass, NUMBER, action="on", delay=30, minutes=5)
    await add_command(hass, NUMBER, action="off", delay=10)

    assert [(c["at"], c["action"]) for c in listed(hass, NEXT)] == [
        ("2026-01-05T07:10:00+00:00", "off"),
        ("2026-01-05T07:30:00+00:00", "on"),
    ]
    assert state_of(hass, NEXT) == "2026-01-05T07:10:00+00:00"

    await advance(hass, freezer, minutes=10)

    assert state_of(hass, NEXT) == "2026-01-05T07:30:00+00:00"
    assert len(listed(hass, NEXT)) == 1


async def test_next_command_shows_the_commands_kept_through_a_restart(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A timer that starts with commands in its file lists them at once."""
    await setup_target(
        stored=payload(commands=[command_json(at(20), minutes=30, id="stored")])
    )

    assert state_of(hass, NEXT) == "2026-01-05T07:20:00+00:00"
    assert [c["id"] for c in listed(hass, NEXT)] == ["stored"]


async def test_next_command_is_written_only_when_commands_change(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The countdown refreshes its entities every minute, but the list of commands has
    not changed, so the sensor stays quiet; adding and cancelling write it once each."""
    await setup_target(target=AC_ID)
    response = await add_command(hass, AC_NUMBER, action="on", delay=60)
    await set_number(hass, AC_NUMBER, 10)
    next_writes = record_writes(hass, AC_NEXT)
    number_writes = record_writes(hass, AC_NUMBER)

    for _ in range(10):
        await advance(hass, freezer, minutes=1)

    assert len(number_writes) >= 10  # the countdown did notify its entities
    assert next_writes == []

    await add_command(hass, AC_NUMBER, action="off", delay=30)
    await call_service(
        hass,
        "cancel_command",
        {"entity_id": AC_NUMBER},
        command_id=response[AC_NUMBER]["command_id"],
    )

    assert next_writes == ["2026-01-05T07:40:00+00:00", "2026-01-05T07:40:00+00:00"]
