"""The proof that the built-in agent can read the sentence files before they are
written: what it refuses, and that it lets the shipped sentences through. A file the
agent cannot load breaks it for the whole language, so each way a file can be unfit is
tried here on the shipped sentences with the names of a timer's target in them.
"""

import copy
from collections.abc import Callable
from typing import Any

import pytest
import yaml

from custom_components.timerify.const import (
    LIST_TARGET,
    MANAGED_HEADER,
    VOICE_LANGUAGES,
)
from custom_components.timerify.voice.sentences import (
    InvalidSentences,
    VoiceName,
    build,
    load_sources,
    render,
    spoken_form,
    validate,
)

NAMES = tuple(
    VoiceName(spoken_form(name), name, "switch") for name in ("Boiler", "Boiler (main)")
)
"""A target known by a plain name and by one with characters in it that a sentence
template would read as its own."""

Mutation = Callable[[dict[str, Any]], object]


def built_sentences(language: str = "en") -> dict[str, Any]:
    """The shipped sentences of `language` with the names of `NAMES` in them."""
    return build(load_sources(language), NAMES)


def timerify_sentences(built: dict[str, Any]) -> list[str]:
    """The sentences of the first data block of the first intent in `built`."""
    return built["intents"][next(iter(built["intents"]))]["data"][0]["sentences"]


def first_name(built: dict[str, Any]) -> dict[str, Any]:
    return built["lists"][LIST_TARGET]["values"][0]  # type: ignore[no-any-return]


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_the_shipped_sentences_with_names_are_fit_to_be_read(language: str) -> None:
    validate(language, built_sentences(language))


def test_a_language_home_assistant_has_no_sentences_in_is_refused() -> None:
    with pytest.raises(InvalidSentences, match="no sentences in zz"):
        validate("zz", built_sentences())


@pytest.mark.parametrize(
    ("mutation", "complaint"),
    [
        pytest.param(
            lambda built: built["lists"].update({"timerify_bad": {"wrong": 1}}),
            "Unknown slot list type",
            id="a list that is neither values nor a range",
        ),
        pytest.param(
            lambda built: timerify_sentences(built).append("how long [is left"),
            "ParseError",
            id="a sentence that is not a template, found only when it is parsed",
        ),
        pytest.param(
            lambda built: timerify_sentences(built).append("how long on {nothing}"),
            "No list nothing",
            id="a list that is not there",
        ),
        pytest.param(
            lambda built: timerify_sentences(built).append("how long <nothing>"),
            "No expansion rule nothing",
            id="an expansion rule that is not there",
        ),
        pytest.param(
            lambda built: built.setdefault("expansion_rules", {}).update(
                {"timerify_rule": "{nothing} <nothing_either>"}
            ),
            "No ",
            id="a rule of Timerify's own, that no sentence uses, that is broken",
        ),
        pytest.param(
            lambda built: first_name(built).update({"in": "Boiler|Heater"}),
            "would not be matched as said",
            id="a name that is read as a choice of two",
        ),
        pytest.param(
            lambda built: first_name(built).update({"in": "[Boiler]"}),
            "would not be matched as said",
            id="a name that is read as an optional word",
        ),
        pytest.param(
            lambda built: first_name(built).update({"in": "Heater"}),
            "would not be matched as said",
            id="a name that is another text",
        ),
        pytest.param(
            lambda built: first_name(built).update({"in": "Boiler (main"}),
            "ParseError",
            id="a name that is not a template at all",
        ),
    ],
)
def test_sentences_the_built_in_agent_would_not_read_as_wanted_are_refused(
    mutation: Mutation, complaint: str
) -> None:
    built = built_sentences()
    mutation(built)

    with pytest.raises(InvalidSentences, match=complaint):
        validate("en", built)


def test_a_rule_that_is_not_timerifys_is_not_the_sentences_to_judge() -> None:
    """Rules of the core sentences refer to lists of their own, which `validate` does
    not claim to check: only what Timerify defines or uses is its to answer for."""
    built = built_sentences()
    built.setdefault("expansion_rules", {})["somebody_elses"] = "{nothing}"

    validate("en", built)


def test_building_the_sentences_leaves_the_sources_as_they_were() -> None:
    sources = load_sources("en")
    before = copy.deepcopy(sources)

    build(sources, NAMES)

    assert sources == before


def test_building_without_names_gives_an_empty_list_of_targets() -> None:
    built = build(load_sources("en"), [])

    assert built["lists"][LIST_TARGET] == {"values": []}


def test_a_name_is_listed_as_said_and_as_meant_with_the_domain_of_its_target() -> None:
    built = built_sentences()

    assert built["lists"][LIST_TARGET]["values"][1] == {
        "in": r"Boiler \(main\)",
        "out": "Boiler (main)",
        "context": {"domain": "switch"},
    }


def test_a_file_says_that_it_is_managed_and_holds_the_sentences() -> None:
    built = built_sentences()

    text = render(built)

    assert text.startswith(f"{MANAGED_HEADER}\n")
    assert yaml.safe_load(text) == built
