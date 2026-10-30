"""The tools that let an LLM agent run, extend and ask about a timer.

Home Assistant asks every integration that has this platform for tools whenever an agent
that uses the Assist API starts a request. They are the handlers of the built-in agent
(`voice`), wrapped as tools, so that a person speaking and an agent calling a tool take
the same path to the same controller.
"""

from homeassistant.components.homeassistant.exposed_entities import (
    async_should_expose,
)
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.llm import (
    LLM_API_ASSIST,
    IntentTool,
    LLMContext,
    ToolAnnotations,
)

from .const import DOMAIN
from .target import target_name
from .voice import HANDLER_TYPES
from .voice.base import TimerifyIntentHandler, loaded_timers

TOOLS_PROMPT = (
    "These devices have a Timerify timer: {names}. To run one for a while, add time,"
    " stop it, ask how long is left, plan a command for later, list or cancel planned"
    " commands, or switch its schedule on or off, use the timerify__ tools, naming the"
    " device as listed here."
)
"""What an agent is told about the tools, with the names of the devices where `{names}`
is."""


def handler_tool(handler_type: type[TimerifyIntentHandler]) -> IntentTool:
    """The tool that calls the handler of `handler_type`, as the handler describes it.

    The description and the arguments are those of the handler's slots, and the hints
    are its own: none of the tools reaches outside Home Assistant.
    """
    return IntentTool(
        handler_type.tool_name,
        handler_type(),
        title=handler_type.title,
        integration=DOMAIN,
        annotations=ToolAnnotations(
            read_only=handler_type.read_only,
            destructive=handler_type.destructive,
            idempotent=handler_type.idempotent,
            open_world=False,
        ),
    )


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """The tools of Timerify for a request that `llm_context` describes, if the Assist
    API is the one asked about and Assist may control a device that has a timer.

    Home Assistant does not filter a tool by what is exposed to the assistant, so this
    does: the tools are offered while there is a device they can act on, and the prompt
    names those devices only. Exposure is asked again when a tool is called.
    """
    if api_id != LLM_API_ASSIST:
        return None
    targets = (entry.runtime_data.target_entity_id for entry in loaded_timers(hass))
    names = [
        target_name(hass, target)
        for target in targets
        if async_should_expose(hass, llm_context.assistant, target)
    ]
    if not names:
        return None
    return LLMTools(
        tools=[handler_tool(handler_type) for handler_type in HANDLER_TYPES],
        prompt=TOOLS_PROMPT.format(names=", ".join(names)),
    )
