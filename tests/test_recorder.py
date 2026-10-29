"""What the recorder keeps of a timer's entities."""

import logging
from collections.abc import Iterator
from datetime import timedelta

import pytest
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.core import HomeAssistant, State
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from .conftest import FakeTarget, SetupTarget
from .helpers import NEXT, NUMBER, START, add_command


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    recorder_db_url: str, enable_custom_integrations: None
) -> None:
    """Let Home Assistant load integrations from custom_components/, after the
    recorder's database is ready: the recorder fixtures need that order, and the
    autouse fixture of the same name in conftest.py would set Home Assistant up
    first."""


@pytest.fixture(autouse=True)
def quiet_sql_engine() -> Iterator[None]:
    """Keep the SQL the recorder runs out of the test output: the plugin sets
    `sqlalchemy.engine` to INFO for the whole session, and the recorder's thread
    prints each statement, some of them after the test is over. Set up before the
    recorder's fixtures, this one is also torn down after them."""
    engine = logging.getLogger("sqlalchemy.engine")
    level = engine.level
    engine.setLevel(logging.WARNING)
    yield
    engine.setLevel(level)


async def test_command_list_is_not_recorded(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The history keeps when the next command is due but not the list of commands,
    which would be stored again with every change; the live state still has it."""
    await setup_target()

    await add_command(hass, NUMBER, action="on", delay=30, minutes=10)
    await async_wait_recording_done(hass)

    states = await recorder_mock.async_add_executor_job(
        get_significant_states,
        hass,
        START - timedelta(days=1),
        None,
        [NEXT],
    )
    recorded = states[NEXT][-1]
    assert isinstance(recorded, State)
    assert recorded.state == "2026-01-05T07:30:00+00:00"
    assert "commands" not in recorded.attributes
    live = hass.states.get(NEXT)
    assert live is not None
    assert len(live.attributes["commands"]) == 1
