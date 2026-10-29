"""The translations: each language says what English says, with the same blanks."""

import re
from pathlib import Path
from typing import Any

import pytest
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
        for field in service.get("fields", {}):
            wanted |= {f"{name}.fields.{field}.{text}" for text in TEXTS}

    assert texts_in(translations_of(language)["services"]).keys() == wanted
