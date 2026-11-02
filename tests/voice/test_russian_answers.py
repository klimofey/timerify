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

from .helpers import render_response

FIXTURE: Final = Path(__file__).parents[1] / "fixtures" / "ru" / "answers.yaml"
"""The one file of the tests that holds the Russian answers."""
COUNTED: Final[Mapping[tuple[str, str], frozenset[str]]] = {
    ("TimerifyTimeLeft", "default"): frozenset({"minutes", "hours"}),
    ("TimerifyRun", "default"): frozenset({"minutes", "hours"}),
    ("TimerifyListCommands", "default"): frozenset({"commands", "minutes"}),
    ("TimerifyCancelCommands", "default"): frozenset({"commands"}),
}
"""For each answer that says a count, by intent and response key, the units it counts.
The answer of `TimerifyRun` is the one that Add time and Stop give too, and the
minutes of `TimerifyListCommands` are the run of a planned command."""
CLASS_COUNTS: Final[Mapping[str, frozenset[int]]] = {
    "minutes": frozenset({1, 2, 5, 11, 21, 22}),
    "hours": frozenset({1, 2, 5, 11, 21}),
    "commands": frozenset({1, 2, 5, 11, 21}),
}
"""For each unit, the counts the fixture must hold a case of: one that is a "one" in
Russian (1 and 21), a "few" (2 and, for minutes, 22), and a "many" (5, and 11, which is
not a "one" though it ends in 1)."""


def load_cases() -> list[Mapping[str, Any]]:
    """The cases of the fixture."""
    cases: list[Mapping[str, Any]] = yaml.safe_load(FIXTURE.read_text("utf-8"))
    return cases


def case_id(case: Mapping[str, Any]) -> str:
    """The name of a case in a test report."""
    return f"{case['intent']}-{case['unit']}-{case['count']}"


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
