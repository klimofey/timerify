"""The events of a countdown that is run and stopped by voice and by an LLM's tools.

They are Timerify's own events, whoever asks: Assist's built-in agent and the tools of
an LLM agent reach the same timer as the dashboard does, so an automation hears them
alike. Stopping is Timerify's doing, so the reason is `stopped`.
"""

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.const import (
    EVENT_COUNTDOWN_ENDED,
    EVENT_COUNTDOWN_STARTED,
)

from ..conftest import FakeTarget
from ..helpers import NUMBER, TURN_OFF, TURN_ON, record_events
from .helpers import assist_api, call_tool, converse

STARTED_FOR_45 = (
    EVENT_COUNTDOWN_STARTED,
    {"entity_id": NUMBER, "ends_at": "2026-01-05T07:45:00+00:00"},
)
"""The start of a countdown of 45 minutes from the time the scenarios begin at."""
STOPPED = (EVENT_COUNTDOWN_ENDED, {"entity_id": NUMBER, "reason": "stopped"})


async def test_running_and_stopping_the_boiler_by_voice_fires_start_and_stop(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    fired = record_events(hass)

    await converse(hass, "turn on the boiler")
    await converse(hass, "turn off the boiler")

    assert fired == [STARTED_FOR_45, STOPPED]
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_running_and_stopping_the_boiler_by_an_llm_tool_fires_the_same(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    api = await assist_api(hass)
    fired = record_events(hass)

    await call_tool(api, "timerify__run", {"name": "Boiler", "minutes": 45})
    await call_tool(api, "timerify__stop", {"name": "Boiler"})

    assert fired == [STARTED_FOR_45, STOPPED]
    assert fake_target.calls == [TURN_ON, TURN_OFF]
