"""Voice: the intent handlers that let a person, or an LLM, run and ask about timers.

One set of handlers serves both: the built-in agent reaches them through the sentences
of `sentences/<language>/`, an LLM through tools that wrap the same handlers.
"""

from typing import Final

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent

from .base import TimerifyIntentHandler
from .commands import (
    CancelCommandsHandler,
    ClockCommandHandler,
    DelayedCommandHandler,
    ListCommandsHandler,
)
from .intervals import SetScheduleHandler
from .timer import AddTimeHandler, RunHandler, StopHandler, TimeLeftHandler

HANDLER_TYPES: Final[tuple[type[TimerifyIntentHandler], ...]] = (
    TimeLeftHandler,
    RunHandler,
    AddTimeHandler,
    StopHandler,
    DelayedCommandHandler,
    ClockCommandHandler,
    ListCommandsHandler,
    CancelCommandsHandler,
    SetScheduleHandler,
)
"""Every handler Timerify registers, one per intent type."""
TOOL_HANDLER_TYPES: Final[tuple[type[TimerifyIntentHandler], ...]] = tuple(
    handler_type
    for handler_type in HANDLER_TYPES
    if handler_type is not ClockCommandHandler
)
"""The handlers that an LLM agent is offered as tools: every handler but the one that
only sentences reach. A clock time is said to a model with `at`, a moment, in the tool
of the delayed command."""


@callback
def async_register_intents(hass: HomeAssistant) -> None:
    """Register the handlers. The registry holds one handler per intent type, for the
    whole of Home Assistant, so this runs once, not once for each timer."""
    for handler_type in HANDLER_TYPES:
        intent.async_register(hass, handler_type())
