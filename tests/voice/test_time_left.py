"""Asking by voice how long is left on a timer, in English and Russian.

Every scenario talks to the real built-in agent, with the sentences installed the
manual way (see `copy_sentences`).
"""

from datetime import date

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent
from pytest_homeassistant_custom_component.common import MockConfigEntry

from ..conftest import SWITCH_SERVICES, FakeTarget, ProvideTarget, SetupTarget
from ..helpers import NUMBER, TARGET_ID, advance, advance_to, local, set_number
from .helpers import (
    HOUR_CLASSES,
    MINUTE_CLASSES,
    PluralClasses,
    converse,
    copy_sentences,
    expose,
    samples,
    speech,
    without_digits,
)

TIME_LEFT = "TimerifyTimeLeft"
LATE_EVENING = local(date(2026, 1, 5), "23:00")
"""From this time every count of hours up to 24 ends the next day, and every count of
minutes below 60 ends the same day, so that answers to different counts differ in
nothing but the count."""


@pytest.fixture
async def boiler(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> MockConfigEntry:
    """A timer on the Boiler, which Assist knows by the sentences of the manual
    installation."""
    entry = await setup_target()
    await copy_sentences(hass, ["Boiler"])
    return entry


def reached(response: intent.IntentResponse) -> str | None:
    """The intent the agent handed the sentence to, if it got as far as a handler."""
    return None if response.intent is None else response.intent.intent_type


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


async def test_time_left_on_an_idle_target(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    response = await converse(hass, "how much time is left on the boiler")

    assert response.response_type is intent.IntentResponseType.QUERY_ANSWER
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


async def spoken_for_each_count(
    hass: HomeAssistant, language: str, counts: tuple[int, ...], minutes_each: int
) -> list[str]:
    """What the answer says, without its numbers, after the timer is set to each of
    `counts` units of `minutes_each` minutes."""
    ask = samples(language, TIME_LEFT, numbers={})[0]
    answers = []
    for count in counts:
        await set_number(hass, NUMBER, count * minutes_each)
        answers.append(without_digits(speech(await converse(hass, ask, language))))
    return answers


async def assert_one_form_per_class(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    language: str,
    classes: PluralClasses,
) -> None:
    """Within a class every count is answered the same way (the numbers aside),
    and between the classes no two answers are alike."""
    await advance_to(hass, freezer, LATE_EVENING)
    forms = []
    for group in classes.russian if language == "ru" else classes.english:
        answers = await spoken_for_each_count(
            hass, language, group, classes.minutes_each
        )
        assert len(set(answers)) == 1, answers
        forms.append(answers[0])
    assert len(set(forms)) == len(forms), forms


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
    await assert_one_form_per_class(hass, freezer, "ru", classes)


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
    await assert_one_form_per_class(hass, freezer, "en", classes)


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
