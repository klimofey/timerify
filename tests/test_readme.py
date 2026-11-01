"""The README's header: the badge of the minimum Home Assistant names the version HACS
enforces, in the English README and in the Russian one."""

import json
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).parent.parent


def minimum_home_assistant() -> str:
    return str(json.loads((ROOT / "hacs.json").read_text())["homeassistant"])


@pytest.mark.parametrize("name", ["README.md", "README.ru.md"])
def test_the_home_assistant_badge_names_the_minimum_version_in_hacs_json(
    name: str,
) -> None:
    readme = unquote((ROOT / name).read_text("utf-8"))

    assert f"badge/Home Assistant-{minimum_home_assistant()}+-" in readme


def test_the_english_badge_says_the_minimum_version_in_its_alt_text() -> None:
    readme = (ROOT / "README.md").read_text("utf-8")

    assert f'alt="Home Assistant {minimum_home_assistant()}+"' in readme
