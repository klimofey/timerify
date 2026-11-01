"""How long a timer may run, as the controller judges it for every way in.

A service has its schema in front of the controller, but a voice, an agent and a script
that calls the controller do not: a duration that is out of range must be refused here,
with a reason the user can read, before anything runs.

The maximum a timer chooses for its Run for slider bounds the slider and nothing else:
whatever else starts a countdown may run for up to a day.
"""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.const import (
    CONF_DEFAULT_DURATION,
    CONF_MODE,
    CONF_RUN_FOR_MAX,
    CONF_RUNTIME,
    DOMAIN,
    MAX_MINUTES,
)
from custom_components.timerify.controller import TargetController

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    NUMBER,
    START,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    advance,
    call_service,
    change_options,
    set_number,
    state_of,
)
from .helpers import add_command as add_pending_command

type Call = Callable[[TargetController, int], Awaitable[Any]]


async def run(controller: TargetController, minutes: int) -> None:
    await controller.async_run(minutes)


async def set_minutes(controller: TargetController, minutes: int) -> None:
    await controller.async_set_minutes(minutes)


async def add_command(controller: TargetController, minutes: int) -> None:
    await controller.async_add_command("on", timedelta(minutes=15), minutes, {})


@pytest.fixture
async def boiler(
    fake_target: FakeTarget, setup_target: SetupTarget
) -> TargetController:
    """The controller of a timer on the boiler."""
    entry: MockConfigEntry = await setup_target()
    controller: TargetController = entry.runtime_data
    return controller


@pytest.mark.parametrize("call", [run, add_command], ids=["run", "add_command"])
@pytest.mark.parametrize("minutes", [0, -1, MAX_MINUTES + 1, 100_000])
async def test_a_run_for_no_time_or_more_than_a_day_is_refused(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: TargetController,
    call: Call,
    minutes: int,
) -> None:
    """The refusal says the range, and nothing is switched or kept."""
    with pytest.raises(ServiceValidationError) as err:
        await call(boiler, minutes)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "duration_out_of_range"
    assert err.value.translation_placeholders == {"max_hours": "24"}
    assert fake_target.calls == []
    assert boiler.snapshot.end is None
    assert boiler.snapshot.commands == ()


@pytest.mark.parametrize("call", [run, set_minutes])
async def test_a_day_is_the_longest_a_timer_runs(
    hass: HomeAssistant, boiler: TargetController, call: Call
) -> None:
    await call(boiler, MAX_MINUTES)

    assert state_of(hass, NUMBER) == str(MAX_MINUTES)


async def test_a_command_may_run_for_a_day(boiler: TargetController) -> None:
    await add_command(boiler, MAX_MINUTES)

    assert [command.minutes for command in boiler.snapshot.commands] == [MAX_MINUTES]


async def test_a_minute_is_the_shortest_a_timer_runs(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: TargetController
) -> None:
    await boiler.async_run(1)

    assert state_of(hass, NUMBER) == "1"
    assert fake_target.calls == [TURN_ON]


@pytest.mark.parametrize("minutes", [-1, MAX_MINUTES + 1])
async def test_setting_the_countdown_outside_zero_to_a_day_is_refused(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: TargetController,
    minutes: int,
) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await boiler.async_set_minutes(minutes)

    assert err.value.translation_key == "duration_out_of_range"
    assert fake_target.calls == []


async def test_a_countdown_set_to_zero_stops_the_timer(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: TargetController
) -> None:
    """Zero is no duration to run for, but it is the way to stop."""
    await set_number(hass, NUMBER, 30)

    await boiler.async_set_minutes(0)

    assert state_of(hass, NUMBER) == "0"
    assert state_of(hass, TARGET_ID) == "off"


async def test_a_run_with_no_duration_is_not_refused(
    hass: HomeAssistant, boiler: TargetController
) -> None:
    """No duration is the open run (R9): the default duration in strict mode."""
    await boiler.async_run(None)

    assert state_of(hass, NUMBER) == "45"


async def test_a_refused_duration_leaves_a_running_timer_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    boiler: TargetController,
) -> None:
    await set_number(hass, NUMBER, 30)
    await advance(hass, freezer, minutes=10)

    with pytest.raises(ServiceValidationError):
        await boiler.async_run(MAX_MINUTES + 1)

    assert boiler.snapshot.end == START + timedelta(minutes=30)
    assert fake_target.calls == [TURN_ON]


@pytest.mark.parametrize("minutes", [30, MAX_MINUTES, 100_000, 10**9, 10**15, 10**30])
async def test_adding_past_a_day_runs_a_day(
    hass: HomeAssistant, boiler: TargetController, minutes: int
) -> None:
    """Adding keeps its clamp: the end is never more than a day ahead, and nothing is
    refused for asking for more."""
    await set_number(hass, NUMBER, MAX_MINUTES - 10)

    await boiler.async_add_minutes(minutes)

    assert state_of(hass, NUMBER) == str(MAX_MINUTES)


@pytest.mark.parametrize("minutes", [-MAX_MINUTES, -(10**9), -(10**15), -(10**30)])
async def test_taking_off_a_day_or_more_stops_the_timer(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: TargetController, minutes: int
) -> None:
    """The other side of the clamp: the end is never more than a day ahead, so taking
    off a day or more, however much, leaves nothing."""
    await set_number(hass, NUMBER, MAX_MINUTES)

    await boiler.async_add_minutes(minutes)

    assert state_of(hass, NUMBER) == "0"
    assert state_of(hass, TARGET_ID) == "off"


@pytest.mark.parametrize(
    ("run_for_max", "slider_ends"),
    [(120, 120), (None, MAX_MINUTES)],
    ids=["a maximum chosen", "no maximum, as in a timer of an earlier release"],
)
async def test_the_slider_ends_at_the_maximum_of_the_timer(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    run_for_max: int | None,
    slider_ends: int,
) -> None:
    await setup_target(run_for_max=run_for_max)

    number = hass.states.get(NUMBER)
    assert number is not None
    assert number.attributes["min"] == 0
    assert number.attributes["max"] == slider_ends


async def test_setting_run_for_above_the_maximum_is_refused(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Home Assistant refuses the slider, the more-info dialog and a preset of the card
    alike, with its own message; the maximum itself is allowed."""
    await setup_target(run_for_max=120)

    with pytest.raises(ServiceValidationError) as err:
        await set_number(hass, NUMBER, 150)

    assert err.value.translation_domain == "number"
    assert err.value.translation_key == "out_of_range"
    assert fake_target.calls == []

    await set_number(hass, NUMBER, 120)

    assert state_of(hass, NUMBER) == "120"
    assert fake_target.calls == [TURN_ON]


async def test_actions_and_commands_run_past_the_maximum(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The maximum is the end of the slider, not a limit on the timer: an action, and a
    pending command, start a countdown of hours more, and it runs in full."""
    await setup_target(run_for_max=120)

    await call_service(hass, "run", {"entity_id": NUMBER}, minutes=180)
    assert state_of(hass, NUMBER) == "180"
    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=60)
    assert state_of(hass, NUMBER) == "240"
    await advance(hass, freezer, minutes=240)
    assert fake_target.calls == [TURN_ON, TURN_OFF]

    await add_pending_command(hass, NUMBER, action="on", delay=1, minutes=300)
    await advance(hass, freezer, minutes=1)

    assert state_of(hass, NUMBER) == "300"


async def test_lowering_the_maximum_keeps_a_longer_countdown_running(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A countdown of five hours is running when the slider is cut to two. It is not
    cut: the number shows its minutes above the end of the slider, and the device goes
    off at the end it was given."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 300)

    await change_options(
        hass,
        entry,
        {CONF_MODE: "strict", CONF_RUNTIME: False, CONF_RUN_FOR_MAX: 120},
        {CONF_DEFAULT_DURATION: 45},
    )

    number = hass.states.get(NUMBER)
    assert number is not None
    assert number.state == "300"
    assert number.attributes["max"] == 120
    await advance(hass, freezer, minutes=120)
    assert state_of(hass, NUMBER) == "180"
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=180)
    assert state_of(hass, NUMBER) == "0"
    assert fake_target.calls == [TURN_ON, TURN_OFF]
