"""The events of a countdown that is run and stopped by voice and by an LLM's tools.

They are Timerify's own events, whoever asks: Assist's built-in agent and the tools of
an LLM agent reach the same timer as the dashboard does, so an automation hears them
alike. Stopping is Timerify's doing, so the reason is `stopped`. The events carry the
context of the request, so the logbook says who asked.
"""

from homeassistant.core import Context, HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockUser,
    async_capture_events,
)

from custom_components.timerify.const import (
    EVENT_COUNTDOWN_ENDED,
    EVENT_COUNTDOWN_STARTED,
)

from ..conftest import FakeTarget
from ..helpers import NUMBER, TURN_OFF, TURN_ON, record_events
from .helpers import assist_api, call_tool, converse

STARTED_FOR_45 = (
    EVENT_COUNTDOWN_STARTED,
    {"entity_id": NUMBER, "ends_at": "2026-01-05T07:45:00+00:00", "limit": False},
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


async def test_a_spoken_request_gives_its_context_to_the_event(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    hass_admin_user: MockUser,
) -> None:
    """A user tells Assist to turn the boiler on for ten minutes. The countdown that
    starts is the doing of that request: the logbook can say who asked."""
    started = async_capture_events(hass, EVENT_COUNTDOWN_STARTED)
    ctx = Context(user_id=hass_admin_user.id)

    await converse(hass, "turn on the boiler for 10 minutes", context=ctx)

    assert len(started) == 1
    assert started[0].context.id == ctx.id
    assert started[0].context.user_id == hass_admin_user.id


async def test_a_tool_call_gives_its_context_to_the_event(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    hass_admin_user: MockUser,
) -> None:
    """An LLM agent that a user talks to runs the boiler for ten minutes with a tool.
    The countdown that starts is the doing of the user's request."""
    started = async_capture_events(hass, EVENT_COUNTDOWN_STARTED)
    ctx = Context(user_id=hass_admin_user.id)
    api = await assist_api(hass, context=ctx)

    await call_tool(api, "timerify__run", {"name": "Boiler", "minutes": 10})

    assert len(started) == 1
    assert started[0].context.id == ctx.id
    assert started[0].context.user_id == hass_admin_user.id
