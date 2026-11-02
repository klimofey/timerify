"""A turn-on by voice that names no duration, inside an open schedule window (#58).

The window runs from half past six to a quarter past seven, and the boiler is switched
off at the wall at twenty to seven. A bare "turn on the boiler", and a clock command
without a length of time that falls due in the window, run it to the window's end; in
Strict mode the default duration is kept where it ends later. Every scenario talks to
the real built-in agent, with the schedule made through the real interval form and the
clock moved explicitly. The Russian answers are pinned by `tests/fixtures/ru`.
"""

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant

from custom_components.timerify.const import Mode

from ..conftest import FakeTarget, SetupTarget
from ..helpers import (
    NEXT,
    SENSOR,
    SUNDAY,
    TURN_OFF,
    TURN_ON,
    add_interval,
    advance_to,
    iso,
    local,
    open_sunday,
    state_of,
)
from .helpers import converse, copy_sentences, speech


async def switched_off_inside_the_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    mode: Mode,
    default_duration: int,
) -> None:
    """The window of 06:30 to 07:15 has turned the boiler on, and someone switches it
    off at the wall at 06:40; it is 06:50 when this returns."""
    await open_sunday(hass, freezer)
    entry = await setup_target(mode=mode, default_duration=default_duration)
    await copy_sentences(hass, ["Boiler"])
    await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "06:40"))
    await fake_target.set_state("off")
    await advance_to(hass, freezer, local(SUNDAY, "06:50"))


@pytest.mark.parametrize(
    ("mode", "default_duration", "ends", "left"),
    [
        pytest.param("strict", 20, "07:15", 25, id="strict-default-ends-sooner"),
        pytest.param("strict", 45, "07:35", 45, id="strict-default-ends-later"),
        pytest.param("loose", 20, "07:15", 25, id="loose"),
    ],
)
async def test_a_bare_turn_on_inside_a_window_runs_to_its_end(
    mode: Mode,
    default_duration: int,
    ends: str,
    left: int,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """At ten to seven, with the boiler switched off in its window, "turn on the boiler"
    runs it to the end of the window, and the answer says when: 25 minutes, until 07:15.
    In Strict mode a default duration of 45 minutes ends later and is kept."""
    await switched_off_inside_the_window(
        hass, freezer, fake_target, setup_target, mode, default_duration
    )

    response = await converse(hass, "turn on the boiler")

    assert speech(response) == f"Boiler runs for {left} minutes, until {ends}."
    assert state_of(hass, SENSOR) == iso(SUNDAY, ends)
    await advance_to(hass, freezer, local(SUNDAY, ends))
    assert fake_target.calls == [TURN_ON, TURN_ON, TURN_OFF]


@pytest.mark.parametrize(
    ("mode", "default_duration", "ends"),
    [
        pytest.param("strict", 10, "07:15", id="strict-default-ends-sooner"),
        pytest.param("strict", 30, "07:30", id="strict-default-ends-later"),
        pytest.param("loose", 20, "07:15", id="loose"),
    ],
)
async def test_a_turn_on_at_a_clock_time_inside_a_window_runs_to_its_end(
    mode: Mode,
    default_duration: int,
    ends: str,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """The boiler is switched off in its window, and at ten to seven somebody says
    "turn on the boiler at 07": a command for 07:00 today that names no length of time.
    When it falls due the window is open, so the boiler runs to the window's end."""
    await switched_off_inside_the_window(
        hass, freezer, fake_target, setup_target, mode, default_duration
    )

    response = await converse(hass, "turn on the boiler at 07")

    assert speech(response) == "Boiler turns on at 07:00."
    assert state_of(hass, NEXT) == iso(SUNDAY, "07:00")
    assert state_of(hass, SENSOR) == "unknown"

    await advance_to(hass, freezer, local(SUNDAY, "07:00"))

    assert state_of(hass, SENSOR) == iso(SUNDAY, ends)
    assert fake_target.calls == [TURN_ON, TURN_ON]
    await advance_to(hass, freezer, local(SUNDAY, ends))
    assert fake_target.calls == [TURN_ON, TURN_ON, TURN_OFF]
