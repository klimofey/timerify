"""The events a timer fires when a countdown starts or ends and when a pending command
comes due.

They are what an automation hears. The core decides when and why, and the controller
fires them on the bus once the timer is saved and shown, so these scenarios follow a
boiler through the user's own actions and watch the bus.
"""

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.timerify.const import (
    EVENT_COMMAND_DUE,
    EVENT_COUNTDOWN_ENDED,
    EVENT_COUNTDOWN_STARTED,
)

from .conftest import FakeTarget, FakeWorkday, SetupTarget
from .helpers import (
    BUTTON,
    NUMBER,
    SENSOR,
    SUNDAY,
    TURN_OFF,
    TURN_ON,
    add_command,
    add_interval,
    advance,
    advance_to,
    call_service,
    edit_interval,
    iso,
    local,
    open_sunday,
    press_button,
    record_events,
    restart_after,
    run_for_of,
    set_number,
    start_set_number,
    state_of,
    timerify_warnings,
)


async def test_running_the_boiler_fires_countdown_started_with_its_end(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    await setup_target()
    started = async_capture_events(hass, EVENT_COUNTDOWN_STARTED)

    await set_number(hass, NUMBER, 30)

    assert [e.data for e in started] == [
        {"entity_id": NUMBER, "ends_at": "2026-01-05T07:30:00+00:00"}
    ]


async def test_the_event_states_the_end_as_the_ends_at_sensor_does(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A clock that is not on the second still gives the same moment, in the same
    form, as the Ends at sensor shows."""
    await setup_target()
    started = async_capture_events(hass, EVENT_COUNTDOWN_STARTED)
    freezer.tick(timedelta(microseconds=250_000))

    await set_number(hass, NUMBER, 30)

    [event] = started
    assert event.data["ends_at"] == state_of(hass, SENSOR)
    assert event.data["ends_at"] == "2026-01-05T07:30:00+00:00"


async def test_switching_the_boiler_on_by_hand_fires_countdown_started(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """In strict mode the boiler gets its default countdown, which is a start."""
    await setup_target()
    started = async_capture_events(hass, EVENT_COUNTDOWN_STARTED)

    await fake_target.set_state("on")

    assert [e.data for e in started] == [
        {"entity_id": NUMBER, "ends_at": "2026-01-05T07:45:00+00:00"}
    ]


async def test_switching_the_boiler_on_by_hand_in_loose_mode_fires_nothing(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    await setup_target(mode="loose")
    fired = record_events(hass)

    await fake_target.set_state("on")

    assert fired == []


async def test_the_end_of_the_countdown_fires_countdown_ended_expired(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    await setup_target()
    await set_number(hass, NUMBER, 30)
    ended = async_capture_events(hass, EVENT_COUNTDOWN_ENDED)

    await advance(hass, freezer, minutes=30)

    assert [e.data for e in ended] == [{"entity_id": NUMBER, "reason": "expired"}]
    assert fake_target.calls == [TURN_ON, TURN_OFF]


@pytest.mark.parametrize(
    "how", ["run_for_zero", "stop", "turn_off_button", "pending_off"]
)
async def test_stopping_the_countdown_fires_ended_stopped(
    how: str,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """However the user stops the countdown, it is `stopped`, not `expired`."""
    await setup_target(off_button=how == "turn_off_button")
    await set_number(hass, NUMBER, 30)
    ended = async_capture_events(hass, EVENT_COUNTDOWN_ENDED)

    match how:
        case "run_for_zero":
            await set_number(hass, NUMBER, 0)
        case "stop":
            await call_service(hass, "stop", {"entity_id": NUMBER})
        case "turn_off_button":
            await press_button(hass, BUTTON)
        case "pending_off":
            await add_command(hass, NUMBER, action="off", delay=10)
            await advance(hass, freezer, minutes=10)

    assert [e.data for e in ended] == [{"entity_id": NUMBER, "reason": "stopped"}]
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_turning_the_boiler_off_by_hand_fires_ended_turned_off(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    await setup_target()
    await set_number(hass, NUMBER, 30)
    ended = async_capture_events(hass, EVENT_COUNTDOWN_ENDED)

    await fake_target.set_state("off")

    assert [e.data for e in ended] == [{"entity_id": NUMBER, "reason": "turned_off"}]
    assert fake_target.calls == [TURN_ON]


async def test_a_pending_command_fires_command_due_with_its_id(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    await setup_target()
    started = async_capture_events(hass, EVENT_COUNTDOWN_STARTED)
    due = async_capture_events(hass, EVENT_COMMAND_DUE)
    response = await add_command(hass, NUMBER, action="on", delay=10, minutes=20)
    assert due == []

    await advance(hass, freezer, minutes=10)

    assert [e.data for e in due] == [
        {
            "entity_id": NUMBER,
            "command_id": response[NUMBER]["command_id"],
            "action": "on",
        }
    ]
    assert [e.data for e in started] == [
        {"entity_id": NUMBER, "ends_at": "2026-01-05T07:30:00+00:00"}
    ]


async def test_a_pending_on_fires_the_command_before_the_start_it_causes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    await setup_target()
    fired = record_events(hass)
    response = await add_command(hass, NUMBER, action="on", delay=10, minutes=20)
    command_id = response[NUMBER]["command_id"]

    await advance(hass, freezer, minutes=10)

    assert fired == [
        (
            EVENT_COMMAND_DUE,
            {"entity_id": NUMBER, "command_id": command_id, "action": "on"},
        ),
        (
            EVENT_COUNTDOWN_STARTED,
            {"entity_id": NUMBER, "ends_at": "2026-01-05T07:30:00+00:00"},
        ),
    ]


async def test_a_pending_off_fires_the_command_before_the_stop_it_causes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    await setup_target()
    await set_number(hass, NUMBER, 30)
    fired = record_events(hass)
    response = await add_command(hass, NUMBER, action="off", delay=10)
    command_id = response[NUMBER]["command_id"]

    await advance(hass, freezer, minutes=10)

    assert fired == [
        (
            EVENT_COMMAND_DUE,
            {"entity_id": NUMBER, "command_id": command_id, "action": "off"},
        ),
        (EVENT_COUNTDOWN_ENDED, {"entity_id": NUMBER, "reason": "stopped"}),
    ]


async def test_moving_run_for_while_it_runs_fires_no_event(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """One countdown goes on while its end moves, however the user moves it: a
    notification that it started is not sent again."""
    await setup_target()
    started = async_capture_events(hass, EVENT_COUNTDOWN_STARTED)
    ended = async_capture_events(hass, EVENT_COUNTDOWN_ENDED)
    await set_number(hass, NUMBER, 30)
    assert len(started) == 1

    await set_number(hass, NUMBER, 60)
    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=10)
    await call_service(hass, "run", {"entity_id": NUMBER}, minutes=20)

    assert state_of(hass, NUMBER) == "20"
    assert len(started) == 1
    assert ended == []


async def test_a_countdown_restored_at_start_up_is_not_announced_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A countdown that still runs after a restart is the one that started before it."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 30)
    fired = record_events(hass)

    await restart_after(hass, freezer, entry, minutes=5)

    assert state_of(hass, NUMBER) == "25"
    assert fired == []


async def test_a_countdown_that_ended_while_down_fires_ended_at_start_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    entry = await setup_target()
    await set_number(hass, NUMBER, 30)
    fired = record_events(hass)

    await restart_after(hass, freezer, entry, minutes=60)

    assert fired == [
        (EVENT_COUNTDOWN_ENDED, {"entity_id": NUMBER, "reason": "expired"})
    ]
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_a_countdown_that_ends_while_the_boiler_is_unavailable_fires(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The countdown is over when its end is reached, whether or not the boiler can be
    told; it is switched off when it is back, and that is not another end."""
    await setup_target()
    await set_number(hass, NUMBER, 30)
    await fake_target.set_state("unavailable")
    ended = async_capture_events(hass, EVENT_COUNTDOWN_ENDED)

    await advance(hass, freezer, minutes=30)

    assert [e.data for e in ended] == [{"entity_id": NUMBER, "reason": "expired"}]
    assert fake_target.calls == [TURN_ON]

    await fake_target.set_state("on")

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert len(ended) == 1


async def test_the_event_names_the_run_for_by_its_new_id(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    await setup_target()
    started = async_capture_events(hass, EVENT_COUNTDOWN_STARTED)
    er.async_get(hass).async_update_entity(
        NUMBER, new_entity_id="number.boiler_minutes"
    )
    await hass.async_block_till_done()

    await set_number(hass, "number.boiler_minutes", 30)

    assert [e.data["entity_id"] for e in started] == ["number.boiler_minutes"]


async def test_the_events_of_a_relay_name_the_channel_they_are_about(
    hass: HomeAssistant,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    one = await setup_target(target="switch.relay_1")
    two = await setup_target(target="switch.relay_2")
    started = async_capture_events(hass, EVENT_COUNTDOWN_STARTED)

    await set_number(hass, run_for_of(hass, two), 30)
    await set_number(hass, run_for_of(hass, one), 10)

    assert [e.data["entity_id"] for e in started] == [
        run_for_of(hass, two),
        run_for_of(hass, one),
    ]
    assert run_for_of(hass, one) != run_for_of(hass, two)


async def test_the_start_is_fired_before_a_slow_device_answers(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """An automation hears of the countdown and finds its end shown, while the call
    that switches the boiler on is still under way."""
    await setup_target()
    started = async_capture_events(hass, EVENT_COUNTDOWN_STARTED)
    slow = fake_target.hold_next_call()

    start = start_set_number(hass, NUMBER, 30)
    await slow.reached.wait()

    assert [e.data["ends_at"] for e in started] == [state_of(hass, SENSOR)]
    assert state_of(hass, SENSOR) == "2026-01-05T07:30:00+00:00"
    slow.release.set()
    await start
    await hass.async_block_till_done()


async def test_a_timer_that_lost_its_run_for_fires_nothing_and_says_so(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The events name the timer by its Run for, so without one there is nothing to
    fire; the log says why an automation heard nothing."""
    await setup_target()
    er.async_get(hass).async_remove(NUMBER)
    await hass.async_block_till_done()
    fired = record_events(hass)

    await fake_target.set_state("on")

    assert fired == []
    assert timerify_warnings(caplog) == [
        "Not announcing what happened to the timer of switch.boiler: its Run for is not"
        " in the entity registry, so the events cannot name the timer"
    ]


async def test_the_end_of_a_schedule_window_fires_start_and_expired(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The window carries the boiler: it starts the countdown when it opens and ends it
    by running out when it closes."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    fired = record_events(hass)

    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))

    assert fired == [
        (
            EVENT_COUNTDOWN_STARTED,
            {"entity_id": NUMBER, "ends_at": iso(SUNDAY, "07:15")},
        ),
        (EVENT_COUNTDOWN_ENDED, {"entity_id": NUMBER, "reason": "expired"}),
    ]
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_editing_the_running_interval_to_other_days_fires_ended_stopped(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user changes the days of the interval while its window runs. Today is not
    one of them, so Timerify takes the boiler off: that is a stop, not an expiry, and
    the countdown that follows the edit's reload is not announced as a new one."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    interval = await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "06:40"))
    fired = record_events(hass)

    await edit_interval(hass, entry, interval, weekdays=["mon"])

    assert fired == [
        (EVENT_COUNTDOWN_ENDED, {"entity_id": NUMBER, "reason": "stopped"})
    ]
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_a_holiday_that_takes_the_window_away_fires_ended_stopped(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """The morning of a working day is running when the Workday sensor says that today
    is a day off after all. The window is gone, and Timerify takes the boiler off."""
    await open_sunday(hass, freezer)
    entry = await setup_target(workday_sensor=fake_workday.entity_id)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "06:40"))
    fired = record_events(hass)

    fake_workday.holidays = {SUNDAY}
    await fake_workday.report()

    assert fired == [
        (EVENT_COUNTDOWN_ENDED, {"entity_id": NUMBER, "reason": "stopped"})
    ]
    assert fake_target.calls == [TURN_ON, TURN_OFF]
