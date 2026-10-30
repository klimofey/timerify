"""What every Timerify intent handler shares: finding the timer a name means, speaking a
refusal in the language of the request, and the slots an answer is made of.

A handler translates slots into one call of the controller, which is also what a service
makes, and the result into speech slots. The built-in agent renders them with the
response templates of `sentences/<language>/`, and an LLM receives them as the tool's
result. A rule (a bound, a past time, a setting the target cannot take) lives in the
controller, never in a handler.
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Any, ClassVar, Final, final, override

import probatio
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import intent
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import dt as dt_util
from homeassistant.util import language as language_util

from ..const import DOMAIN, VOICE_LANGUAGES, is_voice_options
from ..controller import TimerifyConfigEntry
from ..core import remaining_minutes
from ..domains import SETTING_KINDS, voice_settings
from ..target import target_name

DEFAULT_LANGUAGE = "en"
"""The language a refusal is spoken in when the request is in none Timerify has."""
SPOKEN_TARGET_SLOT: Final = "timerify_target"
"""The slot in which the sentences that take over Home Assistant's commands to turn a
device on or off (`core_commands.yaml`) say the device. A handler reads it as `name`,
where every other way of saying it puts it.

It is not called `name` because of how the built-in agent treats a sentence that names
no device it knows, such as "turn it off". Among the sentences that came closest it
prefers one that has a `name`, and it gives up on a custom sentence, where it would work
out what "it" means. With a `name`, a sentence of ours would win against the sentence of
Home Assistant for the same words, and every follow-up would fail with an error."""


def named(slots: Mapping[str, Any]) -> dict[str, Any]:
    """`slots` with the device said in `SPOKEN_TARGET_SLOT` in the place of `name`."""
    return {
        "name" if key == SPOKEN_TARGET_SLOT else key: value
        for key, value in slots.items()
    }


def whole_slot(value: float) -> int:
    """A count of minutes, hours or seconds as a slot carries it: a whole number that
    is not negative.

    The built-in agent gives a number it heard as a float, a number it read as a word
    as an integer, and an LLM sends either; a boolean is a number to Python but not to
    anybody else. The type hint is what the tool's parameters are described by: a
    number.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise probatio.Invalid("expected a number")
    if isinstance(value, float) and not value.is_integer():
        raise probatio.Invalid("expected a whole number")
    if value < 0:
        raise probatio.Invalid("expected a number that is not negative")
    return int(value)


def number_slot(value: float) -> float:
    """A number a person or an agent gave for a setting, as it is, whole or not: the
    temperature of a thermostat, the brightness of a light.

    Nothing is converted, and a boolean passes as the number it is to Python: whether
    `true` is a brightness, and whether 2.5 is a speed, is for `validate_settings` to
    say, once, for every way in. The type hint is what the tool's parameter is
    described by: a number.
    """
    if not isinstance(value, int | float):
        raise probatio.Invalid("expected a number")
    return value


SETTING_SLOTS: Final[dict[Any, Any]] = {
    probatio.Optional(name): number_slot if kind == "number" else cv.string
    for name, kind in SETTING_KINDS.items()
}
"""The settings a target can be turned on with, as the slots of a sentence or of a tool,
under the names the services give them. The domain table decides which settings there
are and whether each is a number or a text; the slots only give the values their types,
and `validate_settings` judges them."""

PERCENT_SLOT: Final[dict[Any, Any]] = {probatio.Optional("percent"): number_slot}
"""The slot that only sentences have besides the settings: "at 40 percent", which means
the brightness of a light, the speed of a fan or the humidity of a humidifier,
whichever the target has. Its companion, `mode`, is a setting of the services too."""

_MEANINGS: Final = ("percent", "mode")
"""The slots that mean whichever setting the target's domain has for them."""


def duration_of(slots: Mapping[str, Any], prefix: str = "") -> int | None:
    """The minutes that the slots `<prefix>hours` and `<prefix>minutes` say together;
    None when neither is given."""
    hours = slots.get(f"{prefix}hours")
    minutes = slots.get(f"{prefix}minutes")
    if hours is None and minutes is None:
        return None
    return 60 * (0 if hours is None else hours["value"]) + (
        0 if minutes is None else minutes["value"]
    )


def settings_of(
    hass: HomeAssistant, entry: TimerifyConfigEntry, slots: Mapping[str, Any]
) -> dict[str, Any]:
    """What the slots ask the target to be turned on with: the settings under their own
    names, and what `percent` and `mode` mean for this target.

    A setting asked for by its own name wins over the same setting asked for by
    meaning. Whether the target takes the settings is not judged here.

    Raises ServiceValidationError (`voice_setting_not_supported`) for a meaning that the
    target's domain has no setting for.
    """
    named = {
        key: slots[key]["value"]
        for marker in SETTING_SLOTS
        if (key := str(marker)) in slots and key not in _MEANINGS
    }
    meant = voice_settings(
        hass,
        entry.runtime_data.target_entity_id,
        percent=slots.get("percent", {}).get("value"),
        mode=slots.get("mode", {}).get("value"),
    )
    return {**meant, **named}


def loaded_timers(hass: HomeAssistant) -> list[TimerifyConfigEntry]:
    """The timers that are set up: the loaded entries of Timerify, but for the voice
    settings, which is not a timer."""
    return [
        entry
        for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        if not is_voice_options(entry.options)
    ]


async def async_match_timer(
    hass: HomeAssistant, intent_obj: intent.Intent, name: str
) -> TimerifyConfigEntry:
    """The timer whose target the user called `name`.

    Only the targets of the timers that are set up are candidates, so another entity
    that carries the same name is never taken for one. A name is matched as Home
    Assistant matches any spoken name (case, aliases), and refused as it refuses one:
    when the target is not exposed to the assistant that asked, or when two targets
    have the name.

    Raises `MatchFailedError` when no single target matches; the agents phrase it, in
    the language of the request.
    """
    constraints = intent.MatchTargetsConstraints(
        name=name, assistant=intent_obj.assistant, single_target=True
    )
    timers = {
        entry.runtime_data.target_entity_id: entry for entry in loaded_timers(hass)
    }
    states = [
        state
        for entity_id in timers
        if (state := hass.states.get(entity_id)) is not None
    ]
    if not states:
        # Asked to search no states at all, the matcher searches the whole house.
        raise intent.MatchFailedError(
            result=intent.MatchTargetsResult(False, intent.MatchFailedReason.NAME),
            constraints=constraints,
        )
    result = intent.async_match_targets(hass, constraints, states=states)
    if not result.is_match:
        raise intent.MatchFailedError(result=result, constraints=constraints)
    return timers[result.states[0].entity_id]


def voice_language(language: str) -> str:
    """The language Timerify speaks in answer to a request in `language`.

    A regional language is answered in its language (`en-GB` in `en`); English is
    the answer to a language Timerify has no texts for, and to the wildcard `*`, which
    an MCP client sends and which matches every language, English first.
    """
    matches = language_util.matches(language, list(VOICE_LANGUAGES))
    return matches[0] if matches else DEFAULT_LANGUAGE


def _clock(text: str) -> str:
    """The local time of day of an ISO moment, as `HH:MM`; anything else as it is."""
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return text
    return dt_util.as_local(moment).strftime("%H:%M")


async def async_error_text(
    hass: HomeAssistant, language: str, err: HomeAssistantError
) -> str:
    """What the refusal `err`, one of Timerify's own, says in the language of the
    request.

    The text is that of `translations/<language>.json`, not of the house's language:
    the exception, formatted on its own, would only ever say it in English. A setting
    is named by the translated name of its service field, and a time is read as
    `HH:MM`, as a person says it. A refusal with no text of the integration's says
    what it says on its own.
    """
    spoken = voice_language(language)
    exceptions = await async_get_translations(hass, spoken, "exceptions", [DOMAIN])
    message = exceptions.get(
        f"component.{DOMAIN}.exceptions.{err.translation_key}.message"
    )
    if message is None:
        return str(err)
    placeholders = dict(err.translation_placeholders or {})
    if "setting" in placeholders:
        services = await async_get_translations(hass, spoken, "services", [DOMAIN])
        field = f"component.{DOMAIN}.services.run.fields.{placeholders['setting']}.name"
        placeholders["setting"] = services.get(field, placeholders["setting"])
    if "at" in placeholders:
        placeholders["at"] = _clock(placeholders["at"])
    return message.format(**placeholders)


def clock_slots(moment: datetime, now: datetime) -> dict[str, Any]:
    """When `moment` is, as an answer says it: `at` is the time of day on the clock of
    the house, `in_days` the days from today's date to its date, 0 for today."""
    local_moment = dt_util.as_local(moment)
    return {
        "at": local_moment.strftime("%H:%M"),
        "in_days": (local_moment.date() - dt_util.as_local(now).date()).days,
    }


def timer_slots(
    hass: HomeAssistant, entry: TimerifyConfigEntry, now: datetime
) -> dict[str, Any]:
    """What an answer says about a timer: `target` is its name, `state` is `counting`
    while the countdown runs, `open` while the target is on without one and `off`
    otherwise; the time left as `left_total` minutes, rounded up, and as
    `left_hours` and `left_minutes`; and while it counts, `ends_at` and
    `ends_in_days` (see `clock_slots`). Whether the target is on without a countdown is
    what the controller's `wanted_running` says, as for "turn off in N"."""
    controller = entry.runtime_data
    snapshot = controller.snapshot
    left_total = remaining_minutes(snapshot, now)
    left_hours, left_minutes = divmod(left_total, 60)
    slots: dict[str, Any] = {
        "target": target_name(hass, controller.target_entity_id),
        "left_total": left_total,
        "left_hours": left_hours,
        "left_minutes": left_minutes,
    }
    if snapshot.end is not None and left_total > 0:
        clock = clock_slots(snapshot.end, now)
        return {
            **slots,
            "state": "counting",
            "ends_at": clock["at"],
            "ends_in_days": clock["in_days"],
        }
    # The target is on without a timer when it is wanted on, as the timer judges it: a
    # turn-on that the target has not shown yet counts, and a turn-off that it has not
    # shown yet does not.
    on = controller.wanted_running(now)
    return {**slots, "state": "open" if on else "off"}


class TimerifyIntentHandler(intent.IntentHandler):
    """An intent that acts on, or asks about, the timer of one target.

    A subclass sets `intent_type`; `slot_schema`, which always asks for the `name` of
    the target and has no default for any slot, since an LLM is told none; what an LLM
    is told about the tool the handler makes (`tool_name`, `title`, `description` and,
    where they differ from the defaults, `read_only`, `destructive` and `idempotent`);
    and does its work in `async_handle_timer`, which is handed the slots validated by
    `slot_schema`.
    """

    tool_name: ClassVar[str]
    """The name of the LLM tool: `timerify__` and the intent without its prefix, in
    snake case."""
    title: ClassVar[str]
    """The tool's short title, in English."""
    description: str
    """The tool's description, in English: what it does, and what each slot means,
    `name` being the name of the device as the prompt lists it."""
    slot_schema: ClassVar[dict[Any, Any]]
    read_only: ClassVar[bool] = False
    """The tool does not change anything."""
    destructive: ClassVar[bool] = True
    """The tool may take away what was there. The defaults are those of an LLM tool
    that says nothing: the least safe ones."""
    idempotent: ClassVar[bool] = False
    """Calling the tool again with the same arguments changes nothing more."""

    @final
    @override
    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Find the timer, let the subclass act on it, and answer.

        A refusal of the controller is a quiet error of the answer, in the language of
        the request; anything else is a failure and propagates. The target is the
        result of the answer; a query is also a query answer, with the target's state
        as the state it matched.
        """
        hass = intent_obj.hass
        response = intent_obj.create_response()
        slots = self.async_validate_slots(named(intent_obj.slots))
        entry = await async_match_timer(hass, intent_obj, slots["name"]["value"])
        try:
            await self.async_handle_timer(intent_obj, entry, slots, response)
        except HomeAssistantError as err:
            if err.translation_domain != DOMAIN:
                raise
            response.async_set_error(
                intent.IntentResponseErrorCode.FAILED_TO_HANDLE,
                await async_error_text(hass, intent_obj.language, err),
            )
            return response
        entity_id = entry.runtime_data.target_entity_id
        # The target is the result of a query as much as of an action, as in the
        # answers of Home Assistant's own handlers: it is what "it" means to the
        # built-in agent in the conversation's next sentence.
        response.async_set_results(
            success_results=[
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.ENTITY,
                    name=target_name(hass, entity_id),
                    id=entity_id,
                )
            ]
        )
        if self.read_only:
            response.response_type = intent.IntentResponseType.QUERY_ANSWER
            state = hass.states.get(entity_id)
            response.async_set_states(matched_states=[] if state is None else [state])
        return response

    async def async_handle_timer(
        self,
        intent_obj: intent.Intent,
        entry: TimerifyConfigEntry,
        slots: Mapping[str, Any],
        response: intent.IntentResponse,
    ) -> None:
        """Do the work for the timer of `entry`, as the validated `slots` ask, and set
        the speech slots of `response`. Success never sets speech: the built-in agent
        renders it from the response templates of the sentences."""
        raise NotImplementedError
