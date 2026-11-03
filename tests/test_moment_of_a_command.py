"""A command is carried out at the moment it was given, not when it gets its turn.

A cloud air conditioner takes about 25 seconds for each call, and a timer works one
step at a time: a command, a report of the device or an alarm that comes meanwhile
waits for the call under way. The scenarios give a command, or a report, while three
slow calls hold the timer, and look at what the user sees when they have finished.
What counts is the moment each step was raised, so that a wait of a minute changes
nothing but the time the answer takes.
"""

import asyncio
import copy
import logging
from datetime import datetime
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import (
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.timerify.const import (
    DOMAIN,
    EVENT_COMMAND_DUE,
    EVENT_COUNTDOWN_ENDED,
    EVENT_COUNTDOWN_STARTED,
)

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    AC_ENDS_AT,
    AC_ID,
    AC_NEXT,
    AC_NUMBER,
    NEXT,
    NUMBER,
    START,
    TURN_OFF,
    TURN_ON,
    add_command,
    advance,
    call_service,
    listed,
    moment,
    record_events,
    run_ac_slowly,
    set_number,
    stamp,
    start_call_service,
    start_set_number,
    state_of,
    storage_key,
    timerify_info,
)

CAME_DUE_WHILE_UNAVAILABLE = (
    "A pending command for switch.boiler came due while it is unavailable;"
    " it is applied when it is back, if it is still relevant then"
)
"""What is logged for a command that falls due while the target is away."""


def start_add_command(
    hass: HomeAssistant, **data: Any
) -> asyncio.Task[ServiceResponse]:
    """Start `timerify.add_command` on the air conditioner and leave the call running,
    with the response a call that waits is still given."""
    return hass.async_create_task(
        hass.services.async_call(
            DOMAIN,
            "add_command",
            {"entity_id": AC_NUMBER, **data},
            blocking=True,
            return_response=True,
        )
    )


def countdown_began(hass: HomeAssistant) -> datetime:
    """When the countdown that the "Ends at" sensor of the air conditioner shows began,
    by its attribute."""
    state = hass.states.get(AC_ENDS_AT)
    assert state is not None
    began: datetime = state.attributes["started_at"]
    return began


def shows_a_limit(hass: HomeAssistant) -> bool:
    """Whether the time the "Ends at" sensor of the air conditioner shows is a limit."""
    state = hass.states.get(AC_ENDS_AT)
    assert state is not None
    limit: bool = state.attributes["limit"]
    return limit


@pytest.mark.parametrize("slow", [True, False], ids=["behind_a_slow_call", "at_once"])
async def test_add_time_given_before_the_end_extends_the_countdown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    slow: bool,
) -> None:
    """The user adds five minutes to a countdown of one at 07:00:20, and the device
    answers so slowly that the minute is over when the call gets its turn. They get what
    they would with a quick device: the countdown goes on to 07:06 and began at 07:00,
    it started once, and the air conditioner is not switched off."""
    await setup_target(target=AC_ID)
    started = async_capture_events(hass, EVENT_COUNTDOWN_STARTED)
    ended = async_capture_events(hass, EVENT_COUNTDOWN_ENDED)

    await run_ac_slowly(
        hass,
        freezer,
        fake_climate,
        {
            20: lambda: start_call_service(
                hass, "add_time", {"entity_id": AC_NUMBER}, minutes=5
            )
        },
        slow=slow,
    )

    assert state_of(hass, AC_ENDS_AT) == stamp(360)
    assert countdown_began(hass) == START
    assert len(started) == 1
    assert ended == []
    assert "turn_off" not in [call[0] for call in fake_climate.calls]


async def test_a_report_queued_ahead_of_add_time_does_not_end_the_countdown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The air conditioner reports that it is cooling at 07:00:10, while the timer waits
    for its slow calls, and the user adds five minutes at 07:00:20. The report is ahead
    of the command in the queue, but it came before the end of the countdown, so it
    must not fold that end when its turn comes at 07:01:15. The air conditioner is
    neither switched off nor on again, and the countdown goes on to 07:06."""
    await setup_target(target=AC_ID)
    started = async_capture_events(hass, EVENT_COUNTDOWN_STARTED)
    ended = async_capture_events(hass, EVENT_COUNTDOWN_ENDED)

    await run_ac_slowly(
        hass,
        freezer,
        fake_climate,
        {
            10: lambda: fake_climate.write("cool"),
            20: lambda: start_call_service(
                hass, "add_time", {"entity_id": AC_NUMBER}, minutes=5
            ),
        },
    )

    assert state_of(hass, AC_ENDS_AT) == stamp(360)
    assert countdown_began(hass) == START
    assert len(started) == 1
    assert ended == []
    assert [call[0] for call in fake_climate.calls] == [
        "set_hvac_mode",
        "set_temperature",
        "set_fan_mode",
    ]


async def test_time_taken_off_before_the_end_stops_the_countdown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """At 07:00:20 the user takes a minute off a countdown that ends at 07:01. That
    ends it then, as stopped and not as run out, and the air conditioner is switched
    off once, though the call gets its turn after the minute is over."""
    await setup_target(target=AC_ID)
    ended = async_capture_events(hass, EVENT_COUNTDOWN_ENDED)

    await run_ac_slowly(
        hass,
        freezer,
        fake_climate,
        {
            20: lambda: start_call_service(
                hass, "add_time", {"entity_id": AC_NUMBER}, minutes=-1
            )
        },
    )

    assert [event.data["reason"] for event in ended] == ["stopped"]
    assert [call[0] for call in fake_climate.calls].count("turn_off") == 1
    assert state_of(hass, AC_ENDS_AT) == "unknown"


async def test_run_for_counts_from_the_moment_it_was_given(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user moves "Run for" to ten minutes at 07:00:20, and the call gets its turn
    at 07:01:15. The air conditioner runs until 07:10:20, ten minutes after they asked,
    not until 07:11:15."""
    await setup_target(target=AC_ID)

    await run_ac_slowly(
        hass,
        freezer,
        fake_climate,
        {20: lambda: start_set_number(hass, AC_NUMBER, 10)},
    )

    assert state_of(hass, AC_ENDS_AT) == stamp(620)


async def test_a_moment_ahead_when_asked_is_kept_though_it_passed_while_waiting(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """At 07:00:00 the user asks for the air conditioner to be turned off at 07:00:30,
    and the call gets its turn at 07:01:15. The moment was ahead when they asked: the
    command is accepted, and is carried out at once, as it was due."""
    await setup_target(target=AC_ID)
    due = async_capture_events(hass, EVENT_COMMAND_DUE)

    (adding,) = await run_ac_slowly(
        hass,
        freezer,
        fake_climate,
        {0: lambda: start_add_command(hass, action="off", at=stamp(30))},
    )

    response = await adding
    assert response is not None
    assert response[AC_NUMBER]["command_id"]
    assert len(due) == 1
    assert fake_climate.calls[-1][0] == "turn_off"
    assert listed(hass, AC_NEXT) == []


async def test_a_moment_already_past_when_asked_is_refused(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A moment that was past when the user asked for it is refused, however long the
    call waits to be told so."""
    await setup_target(target=AC_ID)

    (adding,) = await run_ac_slowly(
        hass,
        freezer,
        fake_climate,
        {0: lambda: start_add_command(hass, action="off", at=stamp(-30))},
    )

    with pytest.raises(ServiceValidationError) as raised:
        await adding
    assert raised.value.translation_key == "command_in_past"


async def test_add_time_then_stop_are_carried_out_in_that_order(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user adds five minutes at 07:00:10 and stops the timer at 07:00:20, behind
    the same slow calls. The calls are carried out in the order they were given: the
    countdown is stopped, once, and nothing is left running."""
    await setup_target(target=AC_ID)
    ended = async_capture_events(hass, EVENT_COUNTDOWN_ENDED)

    await run_ac_slowly(
        hass,
        freezer,
        fake_climate,
        {
            10: lambda: start_call_service(
                hass, "add_time", {"entity_id": AC_NUMBER}, minutes=5
            ),
            20: lambda: start_call_service(hass, "stop", {"entity_id": AC_NUMBER}),
        },
    )

    assert [event.data["reason"] for event in ended] == ["stopped"]
    assert [call[0] for call in fake_climate.calls].count("turn_off") == 1
    assert state_of(hass, AC_ENDS_AT) == "unknown"


async def test_a_pending_off_due_while_a_command_waits_comes_after_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The air conditioner is to be turned off at 07:00:30, and at 07:00:20 the user
    moves "Run for" to ten minutes behind a slow call. The command falls due after the
    user's word, so it wins, as it would with a quick device: the air conditioner ends
    off, with no countdown, and the command came due once."""
    await setup_target(target=AC_ID)
    await add_command(hass, AC_NUMBER, action="off", at=stamp(30))
    due = async_capture_events(hass, EVENT_COMMAND_DUE)

    await run_ac_slowly(
        hass,
        freezer,
        fake_climate,
        {20: lambda: start_set_number(hass, AC_NUMBER, 10)},
    )

    assert fake_climate.calls[-1][0] == "turn_off"
    assert state_of(hass, AC_ENDS_AT) == "unknown"
    assert len(due) == 1


async def test_a_pending_off_that_fell_due_while_a_command_waited_comes_before_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """At 07:00:00 the user asks for the air conditioner to be turned off at 07:00:10,
    and at 07:00:20 moves "Run for" to ten minutes, both behind the same slow calls. The
    off fell due ten seconds before the second word, so it comes first and the second
    word wins, as it would with a quick device: the off is announced before the new
    countdown starts, the air conditioner is turned off and on again, and it runs until
    07:10:20."""
    await setup_target(target=AC_ID)
    fired = record_events(hass)

    await run_ac_slowly(
        hass,
        freezer,
        fake_climate,
        {
            0: lambda: start_add_command(hass, action="off", at=stamp(10)),
            20: lambda: start_set_number(hass, AC_NUMBER, 10),
        },
    )

    assert [event for event, _ in fired[1:]] == [
        EVENT_COMMAND_DUE,
        EVENT_COUNTDOWN_ENDED,
        EVENT_COUNTDOWN_STARTED,
    ]
    assert [call[0] for call in fake_climate.calls][3:] == ["turn_off", "turn_on"]
    assert state_of(hass, AC_ENDS_AT) == stamp(620)


async def test_a_pending_off_and_a_later_command_with_no_wait_are_carried_out_alike(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The control of the scenario above, with a device that answers at once: the off
    falls due at 07:00:10 and is carried out, and "Run for" ten minutes at 07:00:20
    starts a new countdown. It is the sequence the slow device must end with too."""
    await setup_target(target=AC_ID)
    await call_service(
        hass,
        "run",
        {"entity_id": AC_NUMBER},
        minutes=1,
        hvac_mode="cool",
        temperature=24,
        fan_mode="high",
    )
    fired = record_events(hass)
    await add_command(hass, AC_NUMBER, action="off", at=stamp(10))

    await advance(hass, freezer, seconds=10)
    await advance(hass, freezer, seconds=10)
    await set_number(hass, AC_NUMBER, 10)

    assert [event for event, _ in fired] == [
        EVENT_COMMAND_DUE,
        EVENT_COUNTDOWN_ENDED,
        EVENT_COUNTDOWN_STARTED,
    ]
    assert [call[0] for call in fake_climate.calls][3:] == ["turn_off", "turn_on"]
    assert state_of(hass, AC_ENDS_AT) == stamp(620)


async def test_timer_unloaded_while_what_fell_due_before_a_command_is_carried_out(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """The boiler runs for half an hour and is to be turned off at 07:00:10. At 07:00:20
    the user moves "Run for" to ten minutes, and the call carries out the off first,
    which is slow. The timer is replaced meanwhile: the call says it was not made, and
    the file is left to the timer that replaces it."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 30)
    await add_command(hass, NUMBER, action="off", at=stamp(10))
    freezer.move_to(moment(20))
    slow = fake_target.hold_next_call()
    setting = start_set_number(hass, NUMBER, 10)
    await slow.reached.wait()
    await hass.config_entries.async_unload(entry.entry_id)
    stored = copy.deepcopy(hass_storage[storage_key(entry)])

    slow.release.set()
    with pytest.raises(HomeAssistantError) as raised:
        await setting

    assert raised.value.translation_key == "timer_unloaded"
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert hass_storage[storage_key(entry)] == stored


async def test_a_refused_command_still_leaves_what_fell_due_before_it_carried_out(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The air conditioner is to be turned off at 07:00:10. At 07:00:20 the user asks
    for another command at 07:00:05, which is past, and is refused when the call gets
    its turn. The off had fallen due before that, and is carried out all the same: the
    air conditioner is turned off, and the countdown is stopped, not run out."""
    await setup_target(target=AC_ID)
    fired = record_events(hass)

    adding, refused = await run_ac_slowly(
        hass,
        freezer,
        fake_climate,
        {
            0: lambda: start_add_command(hass, action="off", at=stamp(10)),
            20: lambda: start_add_command(hass, action="off", at=stamp(5)),
        },
    )

    await adding
    with pytest.raises(ServiceValidationError) as raised:
        await refused
    assert raised.value.translation_key == "command_in_past"
    assert [event for event, _ in fired[1:]] == [
        EVENT_COMMAND_DUE,
        EVENT_COUNTDOWN_ENDED,
    ]
    assert fired[2][1]["reason"] == "stopped"
    assert [call[0] for call in fake_climate.calls][3:] == ["turn_off"]
    assert state_of(hass, AC_ENDS_AT) == "unknown"
    assert listed(hass, AC_NEXT) == []


async def test_add_time_given_before_a_limit_and_run_after_it_adds_to_the_limit(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A loose air conditioner that someone switched on at 07:00 turns off at 07:01 at
    the latest. At 07:00:40 the user sets it to 22 degrees, which is slow, and at
    07:00:50 they add five minutes. The call gets its turn at 07:01:05, after the limit,
    and the five minutes are added to the limit all the same: the countdown goes on
    to 07:06, which is no limit any more, and nothing switches the device off."""
    await setup_target(mode="loose", limit=1, target=AC_ID)
    fake_climate.write("cool")
    await hass.async_block_till_done()
    assert state_of(hass, AC_ENDS_AT) == stamp(60)
    assert shows_a_limit(hass) is True
    ended = async_capture_events(hass, EVENT_COUNTDOWN_ENDED)

    freezer.move_to(moment(40))
    slow = fake_climate.hold_next_call()
    running = start_call_service(hass, "run", {"entity_id": AC_NUMBER}, temperature=22)
    await slow.reached.wait()
    freezer.move_to(moment(50))
    adding = start_call_service(hass, "add_time", {"entity_id": AC_NUMBER}, minutes=5)
    freezer.move_to(moment(65))
    slow.release.set()
    async_fire_time_changed(hass)
    await running
    await adding
    await hass.async_block_till_done()

    assert state_of(hass, AC_ENDS_AT) == stamp(360)
    assert shows_a_limit(hass) is False
    assert ended == []
    assert "turn_off" not in [call[0] for call in fake_climate.calls]


async def test_a_command_that_folds_a_pending_one_says_it_came_due_while_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A cloud boiler hangs on the turn-on of a run from 07:00:00. An "off" is asked for
    at 07:00:15, and at 07:00:10 the boiler reports that it is unavailable. At 07:00:20
    the user adds five minutes, and the call gets its turn at 07:00:25. The "off" fell
    due while the boiler was away, and the call carries it out before it acts. The log
    says so, as it does when the command's own alarm or a command with no wait carries
    it out: it is the only sign that the switch waits for the boiler to come back."""
    caplog.set_level(logging.INFO, logger="custom_components.timerify")
    await setup_target()
    slow = fake_target.hold_next_call()
    fake_target.ignore_next_call()
    running = start_call_service(hass, "run", {"entity_id": NUMBER}, minutes=10)
    await slow.reached.wait()
    freezer.move_to(moment(5))
    keeping = start_call_service(
        hass, "add_command", {"entity_id": NUMBER}, action="off", at=stamp(15)
    )
    freezer.move_to(moment(10))
    fake_target.write("unavailable")
    freezer.move_to(moment(20))
    adding = start_call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=5)
    freezer.move_to(moment(25))

    slow.release.set()
    await asyncio.gather(running, keeping, adding)
    await hass.async_block_till_done()

    assert timerify_info(caplog) == [CAME_DUE_WHILE_UNAVAILABLE]
    assert listed(hass, NEXT) == []


async def test_a_countdown_that_ran_out_before_a_late_command_is_announced_as_run_out(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The air conditioner runs for two minutes from 07:00:00. A slow call holds the
    timer from 07:00:50, and behind it the user asks for a turn-on for ten minutes at
    07:01:05, takes a minute off the countdown, which now ends at 07:01:00, and at
    07:01:10 adds five minutes. The countdown ran out before the turn-on fell due, so
    the call that carries the turn-on out says so, and the turn-on starts a new
    countdown: the events are what they would be with a quick device, and the air
    conditioner is not switched off and on."""
    await setup_target(target=AC_ID)
    await call_service(hass, "run", {"entity_id": AC_NUMBER}, minutes=2)
    freezer.move_to(moment(50))
    slow = fake_climate.hold_next_call()
    running = start_call_service(hass, "run", {"entity_id": AC_NUMBER}, temperature=24)
    await slow.reached.wait()
    fired = record_events(hass)
    freezer.move_to(moment(55))
    keeping = start_call_service(
        hass,
        "add_command",
        {"entity_id": AC_NUMBER},
        action="on",
        at=stamp(65),
        minutes=10,
    )
    freezer.move_to(moment(57))
    shortening = start_call_service(
        hass, "add_time", {"entity_id": AC_NUMBER}, minutes=-1
    )
    freezer.move_to(moment(70))
    adding = start_call_service(hass, "add_time", {"entity_id": AC_NUMBER}, minutes=5)
    freezer.move_to(moment(75))

    slow.release.set()
    await asyncio.gather(running, keeping, shortening, adding)
    await hass.async_block_till_done()

    assert [event for event, _ in fired] == [
        EVENT_COUNTDOWN_ENDED,
        EVENT_COMMAND_DUE,
        EVENT_COUNTDOWN_STARTED,
    ]
    assert fired[0][1]["reason"] == "expired"
    assert fired[2][1]["ends_at"] == stamp(665)
    assert "turn_off" not in [call[0] for call in fake_climate.calls]
    assert state_of(hass, AC_ENDS_AT) == stamp(965)
