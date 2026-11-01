"""The README's header: the badge of the minimum Home Assistant names the version HACS
enforces."""

import json
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).parent.parent


def test_the_home_assistant_badge_names_the_minimum_version_in_hacs_json() -> None:
    minimum = json.loads((ROOT / "hacs.json").read_text())["homeassistant"]
    readme = unquote((ROOT / "README.md").read_text())

    assert f"badge/Home Assistant-{minimum}+-" in readme
    assert f'alt="Home Assistant {minimum}+"' in readme
