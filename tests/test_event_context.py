"""The events of a timer carry the context of what caused them.

A person who switches the boiler on, an automation that adds time, a voice request or
a switch of the device by hand gives the event that follows its own context, so the
logbook and the trace of an automation that the event starts say who did it. An event
that time caused, such as a countdown that ran out, has a new context and names nobody.
The scenarios act as a user with a name (`Context(user_id=...)`), read the context of
the events that follow, and move the clock explicitly.
"""

import asyncio
from collections.abc import Awaitable, Callable, Collection
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.automation import EVENT_AUTOMATION_TRIGGERED
from homeassistant.core import Context, CoreState, Event, HomeAssistant, callback
from pytest_homeassistant_custom_component.common import (
    MockUser,
    async_capture_events,
    async_mock_service,
)

from custom_components.timerify.const import (
    DOMAIN,
    EVENT_COMMAND_DUE,
    EVENT_COUNTDOWN_ENDED,
    EVENT_COUNTDOWN_STARTED,
)

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    AC_ID,
    AC_NUMBER,
    BUTTON,
    NUMBER,
    SUNDAY,
    TARGET_ID,
    add_automation,
    add_command,
    add_interval,
    advance,
    advance_to,
    at,
    call_service,
    local,
    moment,
    open_sunday,
    payload,
    press_button,
    record_action,
    restart_after,
    run_ac_slowly,
    set_number,
    set_switch,
    stamp,
    start_call_service,
)

type Scenario = Callable[
    [HomeAssistant, FrozenDateTimeFactory, SetupTarget, Context],
    Awaitable[list[Event[Any]]],
]
"""What a user does, as the person that the context names: the events that follow the
last thing they do, in the order they are fired."""

SWITCH = "switch.boiler_schedule_06_30_07_15_mon_sun"
"""The switch of the interval from 06:30 to 07:15 on every day of the week."""


def capture(hass: HomeAssistant) -> list[Event[Any]]:
    """Every Timerify event from now on, with its context, in the order it is fired."""
    caught: list[Event[Any]] = []

    @callback
    def keep(event: Event[Any]) -> None:
        caught.append(event)

    for event_type in (
        EVENT_COUNTDOWN_STARTED,
        EVENT_COUNTDOWN_ENDED,
        EVENT_COMMAND_DUE,
    ):
        hass.bus.async_listen(event_type, keep)
    return caught


def types_of(events: list[Event[Any]]) -> list[str]:
    """What happened, in the order it did."""
    return [event.event_type for event in events]


def assert_carries(event: Event[Any], cause: Context) -> None:
    """The event is the doing of `cause`: its context is that context, with its user."""
    assert cause.user_id is not None
    assert event.context.id == cause.id
    assert event.context.user_id == cause.user_id


def assert_fresh(event: Event[Any], calls: Collection[Context]) -> None:
    """Time caused the event: its context is a new one, with no user and no parent,
    and none that a call of the scenario was made under."""
    assert event.context.parent_id is None
    assert event.context.user_id is None
    assert event.context.id not in {call.id for call in calls}


# --- A call gives its context to the event it causes ---------------------------------


async def run_for_ten(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_target: SetupTarget,
    ctx: Context,
) -> list[Event[Any]]:
    """The user runs the boiler for ten minutes."""
    await setup_target()
    caused = capture(hass)
    await call_service(hass, "run", {"entity_id": NUMBER}, minutes=10, context=ctx)
    return caused


async def add_ten_minutes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_target: SetupTarget,
    ctx: Context,
) -> list[Event[Any]]:
    """The user adds ten minutes to a boiler that does not run."""
    await setup_target()
    caused = capture(hass)
    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=10, context=ctx)
    return caused


async def stop_what_another_started(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_target: SetupTarget,
    ctx: Context,
) -> list[Event[Any]]:
    """The user stops a countdown that someone else started."""
    await setup_target()
    await call_service(
        hass, "run", {"entity_id": NUMBER}, minutes=10, context=Context()
    )
    caused = capture(hass)
    await call_service(hass, "stop", {"entity_id": NUMBER}, context=ctx)
    return caused


async def move_the_slider(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_target: SetupTarget,
    ctx: Context,
) -> list[Event[Any]]:
    """The user moves "Run for" to ten minutes."""
    await setup_target()
    caused = capture(hass)
    await set_number(hass, NUMBER, 10, context=ctx)
    return caused


async def press_turn_off(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_target: SetupTarget,
    ctx: Context,
) -> list[Event[Any]]:
    """The user presses the Turn off button on a countdown that runs."""
    await setup_target(off_button=True)
    await call_service(
        hass, "run", {"entity_id": NUMBER}, minutes=10, context=Context()
    )
    caused = capture(hass)
    await press_button(hass, BUTTON, context=ctx)
    return caused


async def switch_off_the_interval_that_runs(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_target: SetupTarget,
    ctx: Context,
) -> list[Event[Any]]:
    """The user switches off the interval whose window runs the boiler."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    caused = capture(hass)
    await set_switch(hass, SWITCH, False, context=ctx)
    return caused


async def switch_on_the_interval_inside_its_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_target: SetupTarget,
    ctx: Context,
) -> list[Event[Any]]:
    """The user switches an interval on in the middle of its window."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await set_switch(hass, SWITCH, False)
    await advance_to(hass, freezer, local(SUNDAY, "06:45"))
    caused = capture(hass)
    await set_switch(hass, SWITCH, True, context=ctx)
    return caused


@pytest.mark.parametrize(
    ("scenario", "caused"),
    [
        pytest.param(run_for_ten, EVENT_COUNTDOWN_STARTED, id="run"),
        pytest.param(add_ten_minutes, EVENT_COUNTDOWN_STARTED, id="add_time"),
        pytest.param(stop_what_another_started, EVENT_COUNTDOWN_ENDED, id="stop"),
        pytest.param(move_the_slider, EVENT_COUNTDOWN_STARTED, id="slider"),
        pytest.param(press_turn_off, EVENT_COUNTDOWN_ENDED, id="turn_off_button"),
        pytest.param(
            switch_off_the_interval_that_runs,
            EVENT_COUNTDOWN_ENDED,
            id="interval_switched_off",
        ),
        pytest.param(
            switch_on_the_interval_inside_its_window,
            EVENT_COUNTDOWN_STARTED,
            id="interval_switched_on_inside_its_window",
        ),
    ],
)
async def test_an_event_carries_the_context_of_the_call_that_caused_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_admin_user: MockUser,
    scenario: Scenario,
    caused: str,
) -> None:
    """The user acts, by whichever way the dashboard and the device page give: an
    action, the slider, the Turn off button or the switch of an interval. The one event
    that follows is theirs: the logbook can say who started or stopped the boiler."""
    ctx = Context(user_id=hass_admin_user.id)

    events = await scenario(hass, freezer, setup_target, ctx)

    assert types_of(events) == [caused]
    assert_carries(events[0], ctx)


async def test_an_automation_run_by_an_event_names_the_call_as_its_parent(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_admin_user: MockUser,
) -> None:
    """An automation that triggers on "Countdown started" is started by the call that
    started the countdown: its trace links to the call, as the logbook needs to say
    "triggered by action timerify.run", with the user."""
    await setup_target()
    async_mock_service(hass, "test", "record")
    await add_automation(
        hass,
        {"trigger": f"{DOMAIN}.countdown_started", "target": {"entity_id": NUMBER}},
        [record_action(["entity_id"])],
    )
    triggered = async_capture_events(hass, EVENT_AUTOMATION_TRIGGERED)
    ctx = Context(user_id=hass_admin_user.id)

    await call_service(hass, "run", {"entity_id": NUMBER}, minutes=10, context=ctx)

    assert len(triggered) == 1
    assert triggered[0].context.parent_id == ctx.id


async def test_a_device_switched_by_hand_gives_its_context_to_the_event(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_admin_user: MockUser,
) -> None:
    """Someone switches the boiler on at the wall, and later off, and Home Assistant
    credits each change to a context of its own. The countdown that starts and the one
    that ends carry the context of the change that caused them."""
    await setup_target()
    events = capture(hass)
    on_ctx = Context(user_id=hass_admin_user.id)
    off_ctx = Context(user_id=hass_admin_user.id)

    fake_target.write("on", context=on_ctx)
    await hass.async_block_till_done()
    fake_target.write("off", context=off_ctx)
    await hass.async_block_till_done()

    assert types_of(events) == [EVENT_COUNTDOWN_STARTED, EVENT_COUNTDOWN_ENDED]
    assert events[1].data["reason"] == "turned_off"
    assert_carries(events[0], on_ctx)
    assert_carries(events[1], off_ctx)


# --- Time gives a new context --------------------------------------------------------


async def expires(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_target: SetupTarget,
    ctx: Context,
) -> list[Event[Any]]:
    """A countdown that the user chose runs out."""
    await setup_target()
    await call_service(hass, "run", {"entity_id": NUMBER}, minutes=5, context=ctx)
    caused = capture(hass)
    await advance(hass, freezer, minutes=5)
    return caused


async def reaches_its_limit(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_target: SetupTarget,
    ctx: Context,
) -> list[Event[Any]]:
    """A boiler that the user left on reaches its limit."""
    await setup_target(mode="loose", limit=1)
    await call_service(hass, "run", {"entity_id": NUMBER}, context=ctx)
    caused = capture(hass)
    await advance(hass, freezer, minutes=1)
    return caused


async def carries_out_a_pending_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_target: SetupTarget,
    ctx: Context,
) -> list[Event[Any]]:
    """A pending "on" that the user added falls due."""
    await setup_target()
    await add_command(hass, NUMBER, action="on", delay=2, minutes=10, context=ctx)
    caused = capture(hass)
    await advance(hass, freezer, minutes=2)
    return caused


async def set_up_a_schedule_that_a_person_switched(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_target: SetupTarget,
    ctx: Context,
) -> None:
    """The interval from 06:30 to 07:15, whose switch a person flipped off and on again
    before its window."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await set_switch(hass, SWITCH, False, context=ctx)
    await set_switch(hass, SWITCH, True, context=ctx)


async def opens_a_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_target: SetupTarget,
    ctx: Context,
) -> list[Event[Any]]:
    """The window of an interval that the user switched opens."""
    await set_up_a_schedule_that_a_person_switched(hass, freezer, setup_target, ctx)
    caused = capture(hass)
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    return caused


async def closes_a_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_target: SetupTarget,
    ctx: Context,
) -> list[Event[Any]]:
    """The window of an interval that the user switched closes."""
    await set_up_a_schedule_that_a_person_switched(hass, freezer, setup_target, ctx)
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    caused = capture(hass)
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    return caused


async def ends_while_home_assistant_is_down(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_target: SetupTarget,
    ctx: Context,
) -> list[Event[Any]]:
    """A countdown ends while Home Assistant is down."""
    entry = await setup_target()
    await call_service(hass, "run", {"entity_id": NUMBER}, minutes=5, context=ctx)
    caused = capture(hass)
    await restart_after(hass, freezer, entry, minutes=10)
    return caused


@pytest.mark.parametrize(
    ("scenario", "caused"),
    [
        pytest.param(expires, [EVENT_COUNTDOWN_ENDED], id="expiry"),
        pytest.param(reaches_its_limit, [EVENT_COUNTDOWN_ENDED], id="limit"),
        pytest.param(
            carries_out_a_pending_on,
            [EVENT_COMMAND_DUE, EVENT_COUNTDOWN_STARTED],
            id="pending_on",
        ),
        pytest.param(opens_a_window, [EVENT_COUNTDOWN_STARTED], id="window_start"),
        pytest.param(closes_a_window, [EVENT_COUNTDOWN_ENDED], id="window_end"),
        pytest.param(
            ends_while_home_assistant_is_down,
            [EVENT_COUNTDOWN_ENDED],
            id="ended_while_down",
        ),
    ],
)
async def test_an_event_caused_by_time_has_a_fresh_context(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_admin_user: MockUser,
    scenario: Scenario,
    caused: list[str],
) -> None:
    """The user made every call of the scenario. Time then does the rest: a countdown
    runs out, a limit comes, a pending command falls due, a window opens or closes, or
    Home Assistant starts again after an end it missed. None of that is the user's
    doing, so the events name no cause and no user, whatever the user did before."""
    ctx = Context(user_id=hass_admin_user.id)

    events = await scenario(hass, freezer, setup_target, ctx)

    assert types_of(events) == caused
    for event in events:
        assert_fresh(event, [ctx])


async def test_a_command_due_100_seconds_after_a_button_press_has_a_fresh_context(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_admin_user: MockUser,
) -> None:
    """The boiler is to be turned on in two minutes, and at twenty seconds the user
    presses the Turn off button on the countdown that runs. The button still has the
    context of that press when the command falls due, but the command is time's doing:
    neither it nor the countdown it starts carries the button or its user."""
    await setup_target(off_button=True)
    await call_service(hass, "run", {"entity_id": NUMBER}, minutes=30)
    await add_command(hass, NUMBER, action="on", delay=2, minutes=10)
    await advance(hass, freezer, seconds=20)
    ctx = Context(user_id=hass_admin_user.id)
    await press_button(hass, BUTTON, context=ctx)
    caused = capture(hass)

    await advance(hass, freezer, seconds=100)

    assert types_of(caused) == [EVENT_COMMAND_DUE, EVENT_COUNTDOWN_STARTED]
    for event in caused:
        assert_fresh(event, [ctx])


async def test_add_time_on_an_end_that_has_passed_gives_the_expiry_a_fresh_context(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    hass_admin_user: MockUser,
) -> None:
    """The air conditioner runs for a minute, and the three slow calls that start it
    hold the timer for 75 seconds. The user adds five minutes at 07:01:05, after the
    end. The countdown ran out on its own, and the added time is a new start: the
    expiry has no cause, and the start is the user's."""
    await setup_target(target=AC_ID)
    ctx = Context(user_id=hass_admin_user.id)
    events = capture(hass)

    await run_ac_slowly(
        hass,
        freezer,
        fake_climate,
        {
            65: lambda: start_call_service(
                hass, "add_time", {"entity_id": AC_NUMBER}, minutes=5, context=ctx
            )
        },
    )

    # The first start is the run of the air conditioner itself.
    assert types_of(events)[1:] == [EVENT_COUNTDOWN_ENDED, EVENT_COUNTDOWN_STARTED]
    assert events[1].data["reason"] == "expired"
    assert_fresh(events[1], [ctx])
    assert_carries(events[2], ctx)


@pytest.mark.parametrize(
    ("action", "slow_call", "own_call", "expected"),
    [
        pytest.param(
            "on",
            ("stop", {}),
            ("stop", {}),
            [
                (EVENT_COMMAND_DUE, False),
                (EVENT_COUNTDOWN_STARTED, False),
                (EVENT_COUNTDOWN_ENDED, True),
            ],
            id="on_then_stop",
        ),
        pytest.param(
            "off",
            ("run", {"minutes": 10}),
            ("run", {"minutes": 5}),
            [
                (EVENT_COMMAND_DUE, False),
                (EVENT_COUNTDOWN_ENDED, False),
                (EVENT_COUNTDOWN_STARTED, True),
            ],
            id="off_then_run",
        ),
    ],
)
async def test_a_pending_command_folded_by_a_call_is_fresh_while_the_call_keeps_its_own(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_admin_user: MockUser,
    action: str,
    slow_call: tuple[str, dict[str, Any]],
    own_call: tuple[str, dict[str, Any]],
    expected: list[tuple[str, bool]],
) -> None:
    """A slow boiler holds the timer for 25 seconds, and the timer is idle behind it
    for "on" and counting for "off". A pending command falls due at 07:00:10 and the
    user acts at 07:00:20, both behind the slow call. The command falls due before the
    user's word, so the call carries it out first, as its alarm would: that is time's
    doing, and has a new context. What the user's word does after it carries the
    user's context."""
    await setup_target()
    if action == "on":
        await call_service(hass, "run", {"entity_id": NUMBER}, minutes=10)
    ctx = Context(user_id=hass_admin_user.id)
    held = fake_target.hold_next_call()
    service, data = slow_call
    slow = start_call_service(hass, service, {"entity_id": NUMBER}, **data)
    await held.reached.wait()
    events = capture(hass)
    freezer.move_to(moment(5))
    keeping = start_call_service(
        hass, "add_command", {"entity_id": NUMBER}, action=action, at=stamp(10)
    )
    freezer.move_to(moment(20))
    service, data = own_call
    acting = start_call_service(
        hass, service, {"entity_id": NUMBER}, context=ctx, **data
    )
    freezer.move_to(moment(25))

    held.release.set()
    await asyncio.gather(slow, keeping, acting)
    await hass.async_block_till_done()

    assert types_of(events) == [event_type for event_type, _ in expected]
    for event, (_, by_the_call) in zip(events, expected, strict=True):
        if by_the_call:
            assert_carries(event, ctx)
        else:
            assert_fresh(event, [ctx])


async def test_a_command_folded_by_a_switch_is_announced_with_a_fresh_context(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_admin_user: MockUser,
) -> None:
    """A slow boiler holds the timer. A pending "off" falls due at 07:00:10, and at
    07:00:20 the user flips the switch of a schedule interval behind the same call. The
    switch is the cause of what its fold does, but the command coming due is time's
    doing: the event that announces it has a new context."""
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    ctx = Context(user_id=hass_admin_user.id)
    held = fake_target.hold_next_call()
    slow = start_call_service(hass, "run", {"entity_id": NUMBER}, minutes=10)
    await held.reached.wait()
    events = capture(hass)
    freezer.move_to(moment(5))
    keeping = start_call_service(
        hass, "add_command", {"entity_id": NUMBER}, action="off", at=stamp(10)
    )
    freezer.move_to(moment(20))
    flipping = hass.async_create_task(
        hass.services.async_call(
            "switch", "turn_off", {"entity_id": SWITCH}, blocking=True, context=ctx
        )
    )
    freezer.move_to(moment(25))

    held.release.set()
    await asyncio.gather(slow, keeping, flipping)
    await hass.async_block_till_done()

    assert EVENT_COMMAND_DUE in types_of(events)
    (due,) = (event for event in events if event.event_type == EVENT_COMMAND_DUE)
    assert_fresh(due, [ctx])


async def test_two_calls_queued_behind_a_slow_call_each_carry_their_own_context(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_admin_user: MockUser,
) -> None:
    """A slow boiler holds the timer. Meanwhile one user stops it at 07:00:05 and
    another runs it for ten minutes at 07:00:10. Each word has its own context when it
    gets its turn, not the context of the call that was under way, nor that of the call
    that came last."""
    await setup_target()
    ctx_a = Context(user_id=hass_admin_user.id)
    ctx_b = Context(user_id=hass_admin_user.id)
    held = fake_target.hold_next_call()
    first = start_call_service(hass, "run", {"entity_id": NUMBER}, minutes=30)
    await held.reached.wait()
    events = capture(hass)
    freezer.move_to(moment(5))
    stopping = start_call_service(hass, "stop", {"entity_id": NUMBER}, context=ctx_a)
    freezer.move_to(moment(10))
    running = start_call_service(
        hass, "run", {"entity_id": NUMBER}, minutes=10, context=ctx_b
    )
    freezer.move_to(moment(20))

    held.release.set()
    await asyncio.gather(first, stopping, running)
    await hass.async_block_till_done()

    assert types_of(events) == [EVENT_COUNTDOWN_ENDED, EVENT_COUNTDOWN_STARTED]
    assert events[0].data["reason"] == "stopped"
    assert_carries(events[0], ctx_a)
    assert_carries(events[1], ctx_b)


async def test_a_call_that_changes_nothing_fires_nothing(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_admin_user: MockUser,
) -> None:
    """Stopping a timer that does not run, and taking time off it, change nothing. No
    event tells of a countdown that neither began nor ended."""
    await setup_target()
    events = capture(hass)
    ctx = Context(user_id=hass_admin_user.id)

    await call_service(hass, "stop", {"entity_id": NUMBER}, context=ctx)
    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=-5, context=ctx)

    assert events == []
    assert fake_target.calls == []


async def test_one_call_to_two_timers_gives_both_starts_its_context(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    hass_admin_user: MockUser,
) -> None:
    """One action runs the boiler and the air conditioner together. Each timer starts
    its countdown, and each start is the doing of that one call."""
    await setup_target()
    await setup_target(target=AC_ID)
    events = capture(hass)
    ctx = Context(user_id=hass_admin_user.id)

    await call_service(
        hass, "run", {"entity_id": [NUMBER, AC_NUMBER]}, minutes=10, context=ctx
    )

    assert types_of(events) == [EVENT_COUNTDOWN_STARTED, EVENT_COUNTDOWN_STARTED]
    assert {event.data["entity_id"] for event in events} == {NUMBER, AC_NUMBER}
    for event in events:
        assert_carries(event, ctx)


async def test_a_call_while_starting_gives_its_context_to_its_own_start_only(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_admin_user: MockUser,
) -> None:
    """Home Assistant is still starting, and the countdown of the boiler ended while it
    was down. The user adds half an hour, and the call first brings the timer up to its
    moment: the end that was missed runs out then, which is time's doing. The start that
    the call makes is the user's."""
    hass.set_state(CoreState.not_running)
    hass.states.async_remove(TARGET_ID)
    await setup_target(stored=payload(end=at(-40), started_at=at(-70)))
    events = capture(hass)
    ctx = Context(user_id=hass_admin_user.id)

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=30, context=ctx)

    assert types_of(events) == [EVENT_COUNTDOWN_ENDED, EVENT_COUNTDOWN_STARTED]
    assert events[0].data["reason"] == "expired"
    assert_fresh(events[0], [ctx])
    assert_carries(events[1], ctx)
