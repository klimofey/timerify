"""The Russian answers of the voice, pinned by a fixture written by hand.

The plural classes test (`assert_one_form_per_class`) proves that the answers for two
classes of counts differ, not which word goes with which count: a swapped "few" and
"many" passes it. `tests/fixtures/ru/answers.yaml` holds, for every answer that says a
count and for each class of counts, what a speaker of Russian says, written from the
rules of Russian and not produced by the templates. This module renders each shipped
answer with the slots of a case and compares it with the fixture.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

import pytest
import yaml
from homeassistant.core import HomeAssistant

from custom_components.timerify.const import SENTENCES_DIR
from custom_components.timerify.voice.sentences import read_back

from .helpers import (
    render_response,
    russian_limit_answers,
    russian_schedule_answers,
)

FIXTURE: Final = Path(__file__).parents[1] / "fixtures" / "ru" / "answers.yaml"
"""The one file of the tests that holds the Russian answers."""
COUNTED: Final[Mapping[tuple[str, str], frozenset[str]]] = {
    ("TimerifyTimeLeft", "default"): frozenset({"minutes", "hours"}),
    ("TimerifyRun", "default"): frozenset({"minutes", "hours"}),
    ("TimerifyListCommands", "default"): frozenset({"commands", "minutes", "days"}),
    ("TimerifyCancelCommands", "default"): frozenset({"commands"}),
}
"""For each answer that says a count, by intent and response key, the units it counts.
The answer of `TimerifyRun` is the one that Add time and Stop give too, and the
minutes and the days of `TimerifyListCommands` are the run of a planned command and the
days ahead it is due."""
CLASS_COUNTS: Final[Mapping[str, frozenset[int]]] = {
    "minutes": frozenset({1, 2, 5, 11, 21, 22}),
    "hours": frozenset({1, 2, 5, 11, 21}),
    "commands": frozenset({1, 2, 5, 11, 21}),
    "days": frozenset({3, 5}),
}
"""For each unit, the counts the fixture must hold a case of: one that is a "one" in
Russian (1 and 21), a "few" (2 and, for minutes, 22), and a "many" (5, and 11, which is
not a "one" though it ends in 1). The days start at 3, since 1 and 2 are said "tomorrow"
and "the day after tomorrow", and stop at the "few" and "many" a pending command can
reach: it is kept at most 7 days ahead."""
COUNT_SLOT: Final[Mapping[tuple[str, str], tuple[str | int, ...]]] = {
    ("TimerifyTimeLeft", "minutes"): ("left_minutes",),
    ("TimerifyTimeLeft", "hours"): ("left_hours",),
    ("TimerifyRun", "minutes"): ("left_minutes",),
    ("TimerifyRun", "hours"): ("left_hours",),
    ("TimerifyListCommands", "commands"): ("count",),
    ("TimerifyListCommands", "minutes"): ("commands", 0, "minutes"),
    ("TimerifyListCommands", "days"): ("commands", 0, "in_days"),
    ("TimerifyCancelCommands", "commands"): ("cancelled",),
}
"""For each unit of an answer, where in the slots of a handler its count is."""


def load_cases() -> list[Mapping[str, Any]]:
    """The cases of the fixture."""
    cases: list[Mapping[str, Any]] = yaml.safe_load(FIXTURE.read_text("utf-8"))
    return cases


def case_id(case: Mapping[str, Any]) -> str:
    """The name of a case in a test report: the answer, the unit and its count, and for
    hours with minutes after them, the minutes."""
    minutes = f"-and-{case['and_minutes']}" if "and_minutes" in case else ""
    return f"{case['intent']}-{case['unit']}-{case['count']}{minutes}"


def count_in_slots(case: Mapping[str, Any]) -> int:
    """The count of the unit of a case as its slots hold it."""
    found: Any = case["slots"]
    for step in COUNT_SLOT[(case["intent"], case["unit"])]:
        found = found[step]
    return int(found)


def shipped_answers(language: str) -> dict[str, dict[str, str]]:
    """The answer templates of the shipped sentences of `language`, by intent and by
    response key."""
    shipped = read_back((SENTENCES_DIR / language / "timerify.yaml").read_text("utf-8"))
    answers: dict[str, dict[str, str]] = shipped["responses"]["intents"]
    return answers


@pytest.mark.parametrize("case", load_cases(), ids=case_id)
async def test_each_russian_answer_reads_as_the_fixture_says(
    hass: HomeAssistant, case: Mapping[str, Any]
) -> None:
    answers = await hass.async_add_executor_job(shipped_answers, "ru")
    template = answers[case["intent"]][case["response"]]

    assert render_response(hass, template, case["slots"]) == case["answer"]


@pytest.mark.parametrize("name", russian_schedule_answers())
async def test_each_russian_schedule_answer_reads_as_the_fixture_says(
    hass: HomeAssistant, name: str
) -> None:
    """The answer about switching a schedule names the titles asked for, in guillemets,
    and agrees with how many titles that is: one, or several, each once however many
    intervals share it. It has its own fixture, `schedule_answers.yaml`, since it
    counts titles, not a unit that has a plural form per count."""
    case = russian_schedule_answers()[name]
    answers = await hass.async_add_executor_job(shipped_answers, "ru")
    template = answers["TimerifySetSchedule"]["default"]

    assert render_response(hass, template, case["slots"]) == case["answer"]


@pytest.mark.parametrize("name", russian_limit_answers())
async def test_each_russian_limit_answer_reads_as_the_fixture_says(
    hass: HomeAssistant, name: str
) -> None:
    """The answer about a limit says a time of day and no count, so it has its own
    fixture, `limit_answers.yaml`, which pins it for each answer that can give it, today
    and on another date."""
    case = russian_limit_answers()[name]
    answers = await hass.async_add_executor_job(shipped_answers, "ru")
    template = answers[case["intent"]][case["response"]]

    assert render_response(hass, template, case["slots"]) == case["answer"]


def test_the_limit_fixture_pins_every_answer_that_can_give_a_limit() -> None:
    """Only a question about the time left and a run answer with a limit: adding time
    makes a countdown, and a stop makes none."""
    cases = russian_limit_answers().values()

    assert {case["intent"] for case in cases} == {"TimerifyTimeLeft", "TimerifyRun"}
    for intent in ("TimerifyTimeLeft", "TimerifyRun"):
        days = {
            case["slots"]["ends_in_days"] for case in cases if case["intent"] == intent
        }
        assert days == {0, 1, 2}


def test_the_fixture_has_every_count_class_of_every_counted_answer() -> None:
    cases = load_cases()

    for (intent, response), units in COUNTED.items():
        for unit in units:
            counts = {
                case["count"]
                for case in cases
                if (case["intent"], case["response"], case["unit"])
                == (intent, response, unit)
            }
            assert counts == CLASS_COUNTS[unit], (intent, response, unit)


def test_every_case_has_a_name_of_its_own() -> None:
    names = [case_id(case) for case in load_cases()]

    assert len(set(names)) == len(names)


@pytest.mark.parametrize("case", load_cases(), ids=case_id)
def test_each_case_counts_what_it_is_labelled_with(case: Mapping[str, Any]) -> None:
    """A case that says it counts 22 minutes has 22 minutes in its slots: a mistyped
    label would else leave a class of counts without the case the class test thinks it
    has."""
    answer = (case["intent"], case["response"])
    assert case["unit"] in COUNTED.get(answer, frozenset()), answer
    assert count_in_slots(case) == case["count"]
    if "and_minutes" in case:
        assert case["unit"] == "hours"
        assert case["slots"]["left_minutes"] == case["and_minutes"]
