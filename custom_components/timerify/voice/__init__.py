"""Voice: the intent handlers that let a person, or an LLM, run and ask about timers.

One set of handlers serves both: the built-in agent reaches them through the sentences
of `sentences/<language>/`, an LLM through tools that wrap the same handlers.
"""

from typing import Final

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent

from .base import TimerifyIntentHandler
from .timer import TimeLeftHandler

HANDLER_TYPES: Final[tuple[type[TimerifyIntentHandler], ...]] = (TimeLeftHandler,)
"""Every handler Timerify registers, one per intent type."""


@callback
def async_register_intents(hass: HomeAssistant) -> None:
    """Register the handlers. The registry holds one handler per intent type, for the
    whole of Home Assistant, so this runs once, not once for each timer."""
    for handler_type in HANDLER_TYPES:
        intent.async_register(hass, handler_type())
