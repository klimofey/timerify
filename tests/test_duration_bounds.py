"""How long a timer may run, as the controller judges it for every way in.

A service has its schema in front of the controller, but a voice, an agent and a script
that calls the controller do not: a duration that is out of range must be refused here,
with a reason the user can read, before anything runs.
"""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.const import DOMAIN, MAX_MINUTES
from custom_components.timerify.controller import TargetController

from .conftest import FakeTarget, SetupTarget
from .helpers import NUMBER, START, TARGET_ID, TURN_ON, advance, set_number, state_of

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


@pytest.mark.parametrize("minutes", [30, MAX_MINUTES, 100_000])
async def test_adding_past_a_day_runs_a_day(
    hass: HomeAssistant, boiler: TargetController, minutes: int
) -> None:
    """Adding keeps its clamp: the end is never more than a day ahead, and nothing is
    refused for asking for more."""
    await set_number(hass, NUMBER, MAX_MINUTES - 10)

    await boiler.async_add_minutes(minutes)

    assert state_of(hass, NUMBER) == str(MAX_MINUTES)
