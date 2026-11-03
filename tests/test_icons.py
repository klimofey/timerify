"""The icons of the entities, which the frontend finds by their translation keys."""

from typing import Any

from homeassistant.util.json import json_loads_object

from .test_translations import INTEGRATION_DIR, WITH_TARGET, translations_of


def keys_of(entities: dict[str, Any]) -> set[tuple[str, str]]:
    """Every entity key as (platform, key)."""
    return {(platform, key) for platform, keys in entities.items() for key in keys}


def test_every_entity_key_has_its_icon() -> None:
    """An entity with a translation key and no icon of that key shows the default icon
    of its kind. So each key the entities are translated by has its icon, the key an
    entity takes on a device with more than one timer included, and that one shows the
    icon of the plain key."""
    icons = json_loads_object((INTEGRATION_DIR / "icons.json").read_text("utf-8"))[
        "entity"
    ]

    assert keys_of(icons) == keys_of(translations_of("en")["entity"])
    for platform, keys in icons.items():
        for key, icon in keys.items():
            if key.endswith(WITH_TARGET):
                assert icon == keys[key.removesuffix(WITH_TARGET)], f"{platform}.{key}"
