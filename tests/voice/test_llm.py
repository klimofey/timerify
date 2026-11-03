"""Timerify's tools, as an LLM agent that uses the Assist API is given them.

Every scenario asks the real Assist API for the tools of a request, as a conversation
agent or the MCP server does, and calls a tool through it. Which tools there are and
what they say about themselves is checked for every handler Timerify registers
(`TOOL_HANDLER_TYPES`), so a handler that is added later is held to the same rules.
"""

import itertools
import logging
import re

import probatio
import pytest
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent, llm
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.const import DOMAIN
from custom_components.timerify.llm import async_get_tools, handler_tool
from custom_components.timerify.voice import HANDLER_TYPES, TOOL_HANDLER_TYPES
from custom_components.timerify.voice.base import TimerifyIntentHandler
from custom_components.timerify.voice.commands import ClockCommandHandler
from custom_components.timerify.voice.timer import TimeLeftHandler

from ..conftest import SWITCH_SERVICES, FakeTarget, ProvideTarget, SetupTarget
from ..helpers import NUMBER, TARGET_ID, set_number
from .helpers import assist_api, call_tool, expose

TOOL_PREFIX = "timerify__"
PROMPT = (
    "These devices have a Timerify timer: {names}. To run one for a while, add time,"
    " stop it, ask how long is left, plan a command for later, list or cancel planned"
    " commands, or switch its schedule on or off, use the timerify__ tools, naming the"
    " device as listed here."
)
"""What an agent is told about Timerify's tools, with the names of the devices, as a
JSON list, where `{names}` is."""
READ_ONLY = llm.ToolAnnotations(read_only=True, open_world=False)
ADDS = llm.ToolAnnotations(destructive=False, open_world=False)
CONTROL = llm.ToolAnnotations(idempotent=True, open_world=False)
REPEATS = llm.ToolAnnotations(open_world=False)
ANNOTATIONS = {
    "timerify__time_left": READ_ONLY,
    "timerify__run": REPEATS,
    "timerify__add_time": ADDS,
    "timerify__stop": CONTROL,
    "timerify__delayed_command": REPEATS,
    "timerify__list_commands": READ_ONLY,
    "timerify__cancel_commands": REPEATS,
    "timerify__set_schedule": CONTROL,
}
"""How each tool behaves, annotated as core annotates the intent tools of its kind
(`homeassistant/components/intent/llm.py`). A query only reads. Adding time only adds.
Stopping a timer and switching a schedule give the same result when repeated. Running
a timer and planning a command replace the countdown and apply settings, as turning a
device on and starting a timer do in core, so they are destructive and act again when
repeated; so is cancelling commands, since the same call with "next" cancels another
command each time it is made (a firm promise, P1), where core's cancel tools name the
one timer they cancel. None reaches outside Home Assistant."""
EVERY_HANDLER = pytest.mark.parametrize(
    "handler", TOOL_HANDLER_TYPES, ids=lambda handler: handler.tool_name
)


@pytest.fixture
async def boiler(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> MockConfigEntry:
    """A timer on the Boiler, which Assist knows."""
    return await setup_target()


def timerify_tools(api: llm.APIInstance) -> dict[str, llm.Tool]:
    """The tools of the API that are Timerify's, by name."""
    return {tool.name: tool for tool in api.tools if tool.name.startswith(TOOL_PREFIX)}


def tool_of(api: llm.APIInstance, handler: type[TimerifyIntentHandler]) -> llm.Tool:
    """The tool the API has for `handler`."""
    return timerify_tools(api)[handler.tool_name]


def context(
    language: str | None = "en", assistant: str = "conversation"
) -> llm.LLMContext:
    """The context of a request, for the platform to be asked directly."""
    return llm.LLMContext(
        platform="test",
        context=Context(),
        language=language,
        assistant=assistant,
        device_id=None,
    )


# --- Which tools there are ---------------------------------------------------------


async def test_tools_are_offered_while_a_target_is_exposed(
    hass: HomeAssistant, boiler: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """One tool for each handler, named and tagged as Home Assistant asks of an
    integration's tools; Home Assistant has nothing to say about them."""
    caplog.clear()

    api = await assist_api(hass)

    tools = timerify_tools(api)
    assert set(tools) == {handler.tool_name for handler in TOOL_HANDLER_TYPES}
    assert all(re.fullmatch(r"[a-z0-9_]{1,64}", name) for name in tools)
    assert {tool.integration for tool in tools.values()} == {DOMAIN}
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


async def test_the_clock_sentences_add_no_llm_tool(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """A command at a clock time is a sentence of the built-in agent: its handler is
    registered, and the tool of the delayed command, which takes `at`, is what a model
    plans a command at a clock time with. The slots that sentences say a time with would
    only confuse a model, so the tools are exactly those of the handlers that are
    meant to be tools."""
    api = await assist_api(hass)

    tools = timerify_tools(api)

    assert ClockCommandHandler in HANDLER_TYPES
    assert not ClockCommandHandler.offered_as_tool
    assert ClockCommandHandler not in TOOL_HANDLER_TYPES
    assert set(HANDLER_TYPES) - set(TOOL_HANDLER_TYPES) == {ClockCommandHandler}
    assert {handler for handler in HANDLER_TYPES if handler.offered_as_tool} == set(
        TOOL_HANDLER_TYPES
    )
    assert set(tools) == {handler.tool_name for handler in TOOL_HANDLER_TYPES}
    assert len(tools) == len(TOOL_HANDLER_TYPES)
    for tool in tools.values():
        assert "clock_hour" not in tool.parameters.schema


@EVERY_HANDLER
async def test_tools_have_their_own_descriptions_and_titles(
    hass: HomeAssistant,
    boiler: MockConfigEntry,
    handler: type[TimerifyIntentHandler],
) -> None:
    """What an agent reads to decide to call a tool: the description says what the
    tool does and what each of its arguments means, and the title names it; both are in
    English, which is what the tool descriptions of Home Assistant are."""
    tool = tool_of(await assist_api(hass), handler)

    assert tool.description
    assert not tool.description.startswith("Execute Home Assistant")
    assert tool.title
    assert tool.title != tool.name
    assert tool.description.isascii()
    assert tool.title.isascii()
    for argument in tool.parameters.schema:
        assert f"'{argument}'" in tool.description, argument


async def test_no_two_tools_are_described_alike(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    tools = timerify_tools(await assist_api(hass)).values()

    assert len({tool.description for tool in tools}) == len(tools)
    assert len({tool.title for tool in tools}) == len(tools)


def test_a_handler_that_is_no_tool_has_a_tool_identity_of_its_own() -> None:
    """The handler of the clock sentences is a subclass of the delayed command's, and
    what it inherits is not what it is: with no name, title and description of its own
    it would be a second tool with the name of another, the day that a loop over every
    handler offered it. Every handler has its own, whether it is offered or not."""
    for field in ("tool_name", "title", "description"):
        values = [getattr(handler, field) for handler in HANDLER_TYPES]

        assert len(set(values)) == len(HANDLER_TYPES), field


@EVERY_HANDLER
async def test_annotations_follow_each_tool(
    hass: HomeAssistant,
    boiler: MockConfigEntry,
    handler: type[TimerifyIntentHandler],
) -> None:
    """The hints an agent or a client takes from a tool: what the tool is for, in the
    way the core tools of its kind say it."""
    tool = tool_of(await assist_api(hass), handler)

    assert tool.annotations == ANNOTATIONS[tool.name]


@pytest.mark.parametrize(
    ("read_only", "destructive", "idempotent"),
    list(itertools.product([False, True], repeat=3)),
)
def test_a_tool_carries_the_hints_its_handler_declares(
    read_only: bool, destructive: bool, idempotent: bool
) -> None:
    """Each hint of a handler is the same hint of its tool, whichever the handlers are
    that exist now: none of the tools reaches outside Home Assistant."""
    handler = type(
        "DeclaredHandler",
        (TimeLeftHandler,),
        {"read_only": read_only, "destructive": destructive, "idempotent": idempotent},
    )

    assert handler_tool(handler).annotations == llm.ToolAnnotations(
        read_only=read_only,
        destructive=destructive,
        idempotent=idempotent,
        open_world=False,
    )


@EVERY_HANDLER
async def test_tool_parameters_render_as_typed_openapi(
    hass: HomeAssistant,
    boiler: MockConfigEntry,
    handler: type[TimerifyIntentHandler],
) -> None:
    """An agent receives the arguments of a tool as an OpenAPI schema: each of them a
    typed property, and the name of the device required. Nothing is left to be guessed
    as an open `{}` schema."""
    api = await assist_api(hass)
    tool = tool_of(api, handler)

    schema = probatio.to_openapi(
        tool.parameters,
        custom_serializer=api.custom_serializer,
        openapi_version="3.1.0",
        strict=True,
    )

    assert schema["type"] == "object"
    assert "name" in schema["required"]
    assert schema["properties"]["name"] == {"type": "string"}
    for argument, rendered in schema["properties"].items():
        assert "type" in rendered, argument


async def test_no_tools_without_an_exposed_target(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """Assist is not told about a timer whose device it may not control."""
    expose(hass, TARGET_ID, False)

    api = await assist_api(hass)

    assert timerify_tools(api) == {}
    assert "Timerify" not in api.api_prompt


async def test_no_tools_without_a_timer(hass: HomeAssistant, assist: None) -> None:
    api = await assist_api(hass)

    assert timerify_tools(api) == {}
    assert "Timerify" not in api.api_prompt


async def test_no_tools_for_a_timer_that_is_not_set_up(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """A disabled or a failing timer has no controller to call."""
    assert await hass.config_entries.async_unload(boiler.entry_id)

    api = await assist_api(hass)

    assert timerify_tools(api) == {}
    assert "Timerify" not in api.api_prompt


async def test_tools_follow_the_exposure_to_the_asking_assistant(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """The boiler is exposed to Assist, not to Alexa: a request that comes from Alexa
    is offered the tools once the boiler is exposed to it as well."""
    api = await assist_api(hass, assistant="cloud.alexa")
    assert timerify_tools(api) == {}

    expose(hass, TARGET_ID, True, "cloud.alexa")

    api = await assist_api(hass, assistant="cloud.alexa")
    assert set(timerify_tools(api)) == {
        handler.tool_name for handler in TOOL_HANDLER_TYPES
    }


async def test_no_tools_for_another_llm_api(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """Only the Assist API takes tools from the integrations."""
    assert async_get_tools(hass, context(), "other") is None


async def test_no_tools_for_a_request_without_an_assistant(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """An empty name is no assistant. Asked about it, Home Assistant would write a
    decision for it into the registry entry of every target."""
    assert async_get_tools(hass, context(assistant=""), llm.LLM_API_ASSIST) is None

    registered = er.async_get(hass).async_get(TARGET_ID)
    assert registered is not None
    assert "" not in registered.options


# --- What the agent is told --------------------------------------------------------


async def test_prompt_names_the_exposed_targets_only(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """The boiler and the fan have a timer, and Assist may control the boiler only: the
    agent hears of the boiler, in the words the user knows it by."""
    await setup_target()
    await setup_target(target=fake_fan.entity_id)
    expose(hass, fake_fan.entity_id, False)

    api = await assist_api(hass)

    assert PROMPT.format(names='["Boiler"]') in api.api_prompt
    assert "Fan" not in api.api_prompt

    expose(hass, fake_fan.entity_id, True)

    api = await assist_api(hass)

    assert PROMPT.format(names='["Boiler", "Fan"]') in api.api_prompt


async def test_prompt_lists_the_names_so_that_each_is_one(
    hass: HomeAssistant,
    provide_target: ProvideTarget,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """A device is called what its owner called it, a comma, a quote and a line break
    included: the prompt lists the names as a JSON list, in which each stays one name
    and the agent can pass it back as it reads it."""
    name = 'Café, "main"\nlamp'
    odd = provide_target("switch.odd", SWITCH_SERVICES, name=name)
    await setup_target()
    await setup_target(target=odd.entity_id)

    api = await assist_api(hass)

    assert PROMPT.format(names=r'["Boiler", "Café, \"main\"\nlamp"]') in api.api_prompt
    data = await call_tool(api, "timerify__time_left", {"name": name})
    assert data["speech_slots"]["target"] == name


# --- Calling a tool ----------------------------------------------------------------


async def test_time_left_tool_returns_structured_data(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """The agent is handed what the built-in agent would say, as data to say in its
    own words."""
    await set_number(hass, NUMBER, 45)
    api = await assist_api(hass)

    data = await call_tool(api, "timerify__time_left", {"name": "Boiler"})

    assert data["speech_slots"] == {
        "target": "Boiler",
        "state": "counting",
        "left_total": 45,
        "left_hours": 0,
        "left_minutes": 45,
        "ends_at": "09:45",
        "ends_in_days": 0,
    }
    assert data["response_type"] == "query_answer"


async def test_time_left_tool_reports_a_limit(
    hass: HomeAssistant, fake_target: FakeTarget, limited_boiler: MockConfigEntry
) -> None:
    """A boiler that was left on has a limit, a bound and not a countdown: the agent is
    given the state `limit` and the latest time, with no time left, so that it does not
    tell the user how many minutes are left."""
    await fake_target.set_state("on")
    api = await assist_api(hass)

    data = await call_tool(api, "timerify__time_left", {"name": "Boiler"})

    assert data["speech_slots"] == {
        "target": "Boiler",
        "state": "limit",
        "left_total": 0,
        "left_hours": 0,
        "left_minutes": 0,
        "ends_at": "11:00",
        "ends_in_days": 0,
    }
    assert data["response_type"] == "query_answer"


async def test_run_tool_reports_the_limit_of_a_bare_turn_on(
    hass: HomeAssistant, fake_target: FakeTarget, limited_boiler: MockConfigEntry
) -> None:
    """Turning the loose boiler on with no time gives the limit it got, as the question
    does."""
    api = await assist_api(hass)

    data = await call_tool(api, "timerify__run", {"name": "Boiler"})

    assert data["speech_slots"]["state"] == "limit"
    assert data["speech_slots"]["ends_at"] == "11:00"
    assert data["speech_slots"]["left_total"] == 0


async def test_time_left_tool_tells_an_unavailable_target_from_an_off_one(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The agent is told that the boiler is away, so that it does not say it is off."""
    api = await assist_api(hass)
    await fake_target.set_state("unavailable")

    away = await call_tool(api, "timerify__time_left", {"name": "Boiler"})

    assert away["speech_slots"]["state"] == "unavailable"

    await fake_target.set_state("off")

    back = await call_tool(api, "timerify__time_left", {"name": "Boiler"})

    assert back["speech_slots"]["state"] == "off"


async def test_tool_refuses_an_unexposed_target(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """Exposure is asked again when a tool is called, since the tools are offered for
    the whole of a conversation: the boiler stops being exposed in the middle of it."""
    api = await assist_api(hass)
    expose(hass, TARGET_ID, False)

    with pytest.raises(intent.MatchFailedError) as raised:
        await call_tool(api, "timerify__time_left", {"name": "Boiler"})

    assert raised.value.result.no_match_reason is intent.MatchFailedReason.ASSISTANT
    assert fake_target.calls == []


@pytest.mark.parametrize("language", ["*", "de", "en-GB", None])
async def test_tool_with_language_star_and_unknown_language_works(
    hass: HomeAssistant, boiler: MockConfigEntry, language: str | None
) -> None:
    """An MCP client asks in every language (`*`), another request in one Timerify has
    no texts for, or in none: the tool answers as it does in English."""
    await set_number(hass, NUMBER, 45)
    english = await call_tool(
        await assist_api(hass), "timerify__time_left", {"name": "Boiler"}
    )

    api = await assist_api(hass, language)
    data = await call_tool(api, "timerify__time_left", {"name": "Boiler"})

    assert data["speech_slots"] == english["speech_slots"]
    assert data["speech_slots"]["state"] == "counting"
