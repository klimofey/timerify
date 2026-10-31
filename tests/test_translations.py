"""The translations: each language says what English says, with the same blanks."""

import re
from pathlib import Path
from typing import Any

import probatio
import pytest
from homeassistant.helpers import config_validation as cv
from homeassistant.util.json import json_loads_object
from homeassistant.util.yaml import load_yaml

from custom_components.timerify.const import DOMAIN

INTEGRATION_DIR = Path(__file__).parent.parent / "custom_components" / DOMAIN
TRANSLATIONS_DIR = INTEGRATION_DIR / "translations"
LANGUAGES = sorted(path.stem for path in TRANSLATIONS_DIR.glob("*.json"))
"""Every language the integration ships, so a new one is checked without an edit."""
TEXTS = ("name", "description")


def translations_of(language: str) -> dict[str, Any]:
    return json_loads_object((TRANSLATIONS_DIR / f"{language}.json").read_text("utf-8"))


def texts_in(tree: Any, path: str = "") -> dict[str, str]:
    """Every non-empty text in a tree of translations, by its dotted path."""
    if isinstance(tree, str):
        return {path: tree} if tree else {}
    return {
        text_path: text
        for key, subtree in tree.items()
        for text_path, text in texts_in(
            subtree, f"{path}.{key}" if path else key
        ).items()
    }


def blanks_of(text: str) -> set[str]:
    """The names of the `{blanks}` Home Assistant fills in."""
    return set(re.findall(r"\{(\w+)\}", text))


def test_english_is_there() -> None:
    """English is the source of the translations, so the checks below have one."""
    assert "en" in LANGUAGES


@pytest.mark.parametrize("language", [lang for lang in LANGUAGES if lang != "en"])
def test_language_translates_everything_english_says(language: str) -> None:
    """No text is missing or left over, and every text has the same blanks."""
    english = texts_in(translations_of("en"))
    translated = texts_in(translations_of(language))

    assert translated.keys() == english.keys()
    for path, text in english.items():
        assert blanks_of(translated[path]) == blanks_of(text), path


@pytest.mark.parametrize("language", LANGUAGES)
def test_services_are_translated(language: str) -> None:
    """Every service and field in services.yaml has a name and a description."""
    services = load_yaml(str(INTEGRATION_DIR / "services.yaml"))
    wanted: set[str] = set()
    for name, service in services.items():
        wanted |= {f"{name}.{text}" for text in TEXTS}
        for field, spec in service.get("fields", {}).items():
            if "fields" in spec:  # A section: its fields are translated flat.
                wanted.add(f"{name}.sections.{field}.name")
                fields = spec["fields"]
            else:
                fields = {field: spec}
            for field_name in fields:
                wanted |= {f"{name}.fields.{field_name}.{text}" for text in TEXTS}

    assert texts_in(translations_of(language)["services"]).keys() == wanted


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_text_contains_markup(language: str) -> None:
    """Home Assistant takes a text for HTML when it has a tag in it, and hassfest
    refuses the integration for one. This runs the check that fails it, Home
    Assistant's own `string_with_no_html`, on every text of every language, so that
    Docker is not the only place that mistake is found. It is the one check of the
    several that hassfest makes on the translations, and the hassfest run stays the
    proof of the rest."""
    refused: dict[str, str] = {}
    for path, text in texts_in(translations_of(language)).items():
        try:
            cv.string_with_no_html(text)
        except probatio.Invalid as err:
            refused[path] = str(err)

    assert refused == {}


def test_a_path_with_a_placeholder_in_angle_brackets_is_markup() -> None:
    """The check sees what once broke hassfest: a path written with `<language>`."""
    with pytest.raises(probatio.Invalid):
        cv.string_with_no_html("custom_sentences/<language>/timerify.yaml")


@pytest.mark.parametrize("language", LANGUAGES)
def test_card_strings_are_common_slugs_prefixed_card(language: str) -> None:
    """The strings of the dashboard card sit in `common`, which the card loads in the
    user's language, as flat texts whose keys cannot be taken for anything else."""
    common = translations_of(language)["common"]

    assert common
    for key, text in common.items():
        assert re.fullmatch(r"card_[a-z0-9_]+", key), key
        assert isinstance(text, str), key
