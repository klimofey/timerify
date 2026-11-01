"""Asking by voice how long is left on a timer, in English and Russian.

Every scenario talks to the real built-in agent, with the sentences installed the
manual way (see `copy_sentences`).
"""

from collections.abc import Awaitable, Callable
from datetime import date

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent
from homeassistant.helpers.template import Template
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.voice.sentences import load_sources

from ..conftest import SWITCH_SERVICES, FakeTarget, ProvideTarget, SetupTarget
from ..helpers import (
    NUMBER,
    TARGET_ID,
    TURN_OFF,
    advance,
    advance_to,
    local,
    set_number,
    state_of,
)
from .helpers import (
    HOUR_CLASSES,
    LATE_EVENING,
    MINUTE_CLASSES,
    PluralClasses,
    assert_one_form_per_class,
    converse,
    copy_sentences,
    expose,
    reached,
    samples,
    speech,
    talk,
    without_digits,
    words,
)

TIME_LEFT = "TimerifyTimeLeft"
SPRING_FORWARD_EVE = local(date(2026, 3, 26), "23:30")
"""Half an hour before the night the clocks of Jerusalem go forward: a full day later
the wall clock shows 00:30 two dates on, since that day has 23 hours."""
RUSSIAN_DAY_COUNTS = ((21, 31), (3, 4, 22, 23), (5, 6, 7, 11, 12, 14, 20, 25))
"""Counts of days of three or more, grouped by the plural form Russian says them
with (one, few, many)."""


async def test_time_left_while_counting(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """The answer says the minutes left and when the target turns off."""
    await set_number(hass, NUMBER, 45)

    response = await converse(hass, "how much time is left on the boiler")

    assert response.response_type is intent.IntentResponseType.QUERY_ANSWER
    assert reached(response) == TIME_LEFT
    assert speech(response) == "45 minutes left on Boiler, it turns off at 09:45."


async def test_time_left_says_hours_and_minutes(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    await set_number(hass, NUMBER, 90)

    response = await converse(hass, "how much time is left on the boiler")

    assert speech(response) == (
        "1 hour and 30 minutes left on Boiler, it turns off at 10:30."
    )


async def test_time_left_rounds_up_like_the_run_for_number(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, boiler: MockConfigEntry
) -> None:
    """Half a minute into the countdown the number still shows 45, and so does the
    answer."""
    await set_number(hass, NUMBER, 45)
    await advance(hass, freezer, seconds=30)

    response = await converse(hass, "how much time is left on the boiler")

    assert speech(response) == "45 minutes left on Boiler, it turns off at 09:45."


async def test_time_left_past_midnight_says_tomorrow(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    await set_number(hass, NUMBER, 1440)

    response = await converse(hass, "how much time is left on the boiler")

    assert speech(response) == (
        "24 hours left on Boiler, it turns off at 09:00 tomorrow."
    )


async def test_time_left_two_dates_on_says_the_day_after_tomorrow(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, boiler: MockConfigEntry
) -> None:
    """On the night the clocks go forward a full day ends two dates on, and the answer
    still says which day."""
    await advance_to(hass, freezer, SPRING_FORWARD_EVE)
    await set_number(hass, NUMBER, 1440)

    response = await converse(hass, "how much time is left on the boiler")

    assert speech(response) == (
        "24 hours left on Boiler, it turns off at 00:30 the day after tomorrow."
    )


@pytest.mark.parametrize("language", ["en", "ru"])
async def test_the_day_is_said_only_when_the_end_is_not_today(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    boiler: MockConfigEntry,
    language: str,
) -> None:
    """An answer that ends today says no day; one that ends tomorrow adds a word for
    it, and one two dates on adds another. The day words are told by what the answer
    says more than the same answer for today does: a day in 24 hours and a day in 2
    are said with the same words of the count (2 and 24 are of one plural class)."""
    ask = samples(language, TIME_LEFT, numbers={})[0]

    async def said_for(minutes: int) -> frozenset[str]:
        await set_number(hass, NUMBER, minutes)
        return words(speech(await converse(hass, ask, language)))

    today = await said_for(120)
    await advance_to(hass, freezer, LATE_EVENING)
    tomorrow = await said_for(120)
    await advance_to(hass, freezer, SPRING_FORWARD_EVE)
    day_after = await said_for(1440)

    assert tomorrow > today
    assert day_after > today
    assert tomorrow - today != day_after - today


@pytest.mark.parametrize("language", ["en", "ru"])
async def test_three_days_or_more_are_counted_by_the_plural_rules(
    hass: HomeAssistant, language: str
) -> None:
    """No timer runs for days (the number stops at 24 hours), so the wording of three
    days or more is tried on the sentence source itself, with the slots a handler gives
    to a timer that ends that many dates on. English says every count one way, Russian
    one of three ways."""
    sources = await hass.async_add_executor_job(load_sources, language)
    source = sources["responses"]["intents"][TIME_LEFT]["default"]

    def said_for(days: int) -> str:
        slots = {
            "state": "counting",
            "target": "Boiler",
            "left_total": 120,
            "left_hours": 2,
            "left_minutes": 0,
            "ends_at": "11:00",
            "ends_in_days": days,
        }
        return Template(source, hass).async_render({"slots": slots})

    groups = RUSSIAN_DAY_COUNTS if language == "ru" else (sum(RUSSIAN_DAY_COUNTS, ()),)
    forms = []
    for group in groups:
        answers = {without_digits(said_for(days)) for days in group}
        assert len(answers) == 1, answers
        forms.append(answers.pop())
    assert len(set(forms)) == len(forms), forms
    assert all(str(days) in said_for(days) for days in sum(RUSSIAN_DAY_COUNTS, ()))


async def test_time_left_on_an_idle_target(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    response = await converse(hass, "how much time is left on the boiler")

    assert response.response_type is intent.IntentResponseType.QUERY_ANSWER
    assert speech(response) == "Boiler is off and has no timer."


async def test_an_unavailable_target_with_no_timer_is_answered_unavailable(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The boiler dropped off the network and nothing is set to run it: the answer says
    what is known, not that it is off."""
    await fake_target.set_state("unavailable")

    response = await converse(hass, "how much time is left on the boiler")

    assert response.response_type is intent.IntentResponseType.QUERY_ANSWER
    assert speech(response) == "Boiler is unavailable and has no timer."


async def test_an_unavailable_target_with_a_countdown_is_answered_with_the_time_left(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The countdown runs while the boiler is away, since the wish is on: the answer
    keeps saying how long is left, and says nothing of the boiler being away."""
    await set_number(hass, NUMBER, 45)
    await fake_target.set_state("unavailable")

    response = await converse(hass, "how much time is left on the boiler")

    assert speech(response) == "45 minutes left on Boiler, it turns off at 09:45."


async def test_an_off_target_with_no_timer_is_still_answered_off(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """Once the boiler is back, switched off, the answer is the plain one again."""
    await fake_target.set_state("unavailable")
    away = await converse(hass, "how much time is left on the boiler")
    assert speech(away) == "Boiler is unavailable and has no timer."

    await fake_target.set_state("off")

    response = await converse(hass, "how much time is left on the boiler")

    assert speech(response) == "Boiler is off and has no timer."


async def test_time_left_on_a_loose_target_running_without_a_timer(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """A loose timer lets the target run with no countdown; the answer says so."""
    await setup_target(mode="loose")
    await copy_sentences(hass, ["Boiler"])
    await fake_target.set_state("on")

    response = await converse(hass, "how much time is left on the boiler")

    assert speech(response) == "Boiler is on without a timer."


async def test_a_follow_up_can_say_it_after_asking_how_long_is_left(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """Asking about the boiler makes it what "it" means in that conversation: the
    agent remembers the target of an answer, and "turn it off" finds the boiler."""
    await set_number(hass, NUMBER, 45)
    asked = await talk(hass, "how much time is left on the boiler")

    elsewhere = await talk(hass, "turn it off")
    assert TURN_OFF not in fake_target.calls, speech(elsewhere.response)

    followed = await talk(hass, "turn it off", conversation_id=asked.conversation_id)

    assert TURN_OFF in fake_target.calls, speech(followed.response)
    assert state_of(hass, NUMBER) == "0"


@pytest.mark.parametrize(
    "text",
    [
        "how much time is left on the boiler",
        "how long is left on boiler",
        "how long will the boiler run",
        "when does the boiler turn off",
        "How much time is left on the Boiler?",
    ],
)
async def test_english_phrasings_ask_time_left(
    hass: HomeAssistant, boiler: MockConfigEntry, text: str
) -> None:
    response = await converse(hass, text)

    assert reached(response) == TIME_LEFT
    assert response.response_type is intent.IntentResponseType.QUERY_ANSWER
    assert response.intent is not None
    assert response.intent.slots["name"]["value"] == "Boiler"


async def test_unexposed_target_is_refused(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The sentences list the target whatever Assist is allowed to see, so the handler
    asks."""
    expose(hass, TARGET_ID, False)

    response = await converse(hass, "how much time is left on the boiler")

    assert response.response_type is intent.IntentResponseType.ERROR
    assert response.error_code is intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert fake_target.calls == []


async def test_entity_without_a_timer_is_not_captured(
    hass: HomeAssistant, fake_fan: FakeTarget, boiler: MockConfigEntry
) -> None:
    """A fan that no timer is attached to is not a name Timerify's sentences know."""
    response = await converse(hass, "how much time is left on fan")

    assert reached(response) is None
    assert response.response_type is intent.IntentResponseType.ERROR
    assert fake_fan.calls == []


async def test_two_targets_with_one_name_are_not_guessed(
    hass: HomeAssistant,
    provide_target: ProvideTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """Two timers whose targets are both called Lamp: the agent asks nothing and
    switches nothing."""
    first = provide_target("switch.lamp_one", SWITCH_SERVICES, name="Lamp")
    second = provide_target("switch.lamp_two", SWITCH_SERVICES, name="Lamp")
    await setup_target(target=first.entity_id)
    await setup_target(target=second.entity_id)
    await copy_sentences(hass, ["Lamp"])

    response = await converse(hass, "how much time is left on the lamp")

    assert response.response_type is intent.IntentResponseType.ERROR
    assert response.error_code is intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert first.calls == second.calls == []


async def test_only_timer_with_no_state_is_not_matched_among_other_entities(
    hass: HomeAssistant, fake_fan: FakeTarget, boiler: MockConfigEntry
) -> None:
    """With the target's state gone the timer has no entity to match, and the matcher,
    given nothing, would search the whole house: it would find the fan that was
    renamed Boiler."""
    hass.states.async_remove(TARGET_ID)
    er.async_get(hass).async_update_entity("switch.fan", name="Boiler")

    response = await converse(hass, "how much time is left on the boiler")

    assert response.response_type is intent.IntentResponseType.ERROR
    assert response.error_code is intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert fake_fan.calls == []


async def test_russian_sentences_reach_time_left(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """Every Russian way to ask, as the sentence files give them, reaches the handler
    with the target's name."""
    texts = samples("ru", TIME_LEFT, numbers={})
    assert texts

    for text in texts:
        response = await converse(hass, text, language="ru")

        assert reached(response) == TIME_LEFT, text
        assert response.intent is not None
        assert response.intent.slots["name"]["value"] == "Boiler", text


async def test_russian_answers_an_unavailable_target_in_other_words_than_an_off_one(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """In Russian too the answer says that the boiler is away: it differs from the one
    for an off boiler in the state word alone, and still names the boiler."""
    ask = samples("ru", TIME_LEFT, numbers={})[0]
    off = speech(await converse(hass, ask, "ru"))
    await fake_target.set_state("unavailable")

    away = speech(await converse(hass, ask, "ru"))

    assert "Boiler" in away
    assert len(words(away) - words(off)) == 1
    assert len(words(off) - words(away)) == 1


async def said_after_counting(
    hass: HomeAssistant, language: str
) -> Callable[[int, int], Awaitable[str]]:
    """What the answer to "how long is left" says after the timer is set to a count of
    units, as `assert_one_form_per_class` asks for it."""
    ask = samples(language, TIME_LEFT, numbers={})[0]

    async def say(count: int, minutes_each: int) -> str:
        await set_number(hass, NUMBER, count * minutes_each)
        return speech(await converse(hass, ask, language))

    return say


@pytest.mark.parametrize(
    "classes",
    [
        pytest.param(MINUTE_CLASSES, id="minutes"),
        pytest.param(HOUR_CLASSES, id="hours"),
    ],
)
async def test_russian_counts_follow_the_plural_rules(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    boiler: MockConfigEntry,
    classes: PluralClasses,
) -> None:
    """Russian counts three ways (one, few, many), by the last digits of the number;
    the tests prove the three-way split, not which word each class takes."""
    say = await said_after_counting(hass, "ru")

    await assert_one_form_per_class(hass, freezer, "ru", classes, say)


@pytest.mark.parametrize(
    "classes",
    [
        pytest.param(MINUTE_CLASSES, id="minutes"),
        pytest.param(HOUR_CLASSES, id="hours"),
    ],
)
async def test_english_counts_follow_the_plural_rules(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    boiler: MockConfigEntry,
    classes: PluralClasses,
) -> None:
    say = await said_after_counting(hass, "en")

    await assert_one_form_per_class(hass, freezer, "en", classes, say)


async def test_english_says_one_and_many(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """The words themselves: "1 minute", "2 minutes", "1 hour"."""
    said = {}
    for minutes in (1, 2, 60):
        await set_number(hass, NUMBER, minutes)
        said[minutes] = speech(await converse(hass, "how long is left on boiler"))

    assert said[1].startswith("1 minute left on Boiler")
    assert said[2].startswith("2 minutes left on Boiler")
    assert said[60].startswith("1 hour left on Boiler")
