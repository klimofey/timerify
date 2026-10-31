"""The dashboard card: the JavaScript module Timerify serves to every dashboard.

The module is built from the sources in `card/` and committed as
`frontend/timerify-card.js`, so that a plain download of the integration (HACS) has
it. It is served to everyone, because the browser loads it before a user has logged
in, at an address that does not change, with a cache of a month. What changes is the
address the dashboards are told to load it from: it carries a key made of the file's
contents, so that a new bundle is fetched at once.
"""

import hashlib
from pathlib import Path
from typing import Final

from homeassistant.components.frontend import add_extra_js_url

# The module that defines it: the package only re-exports the name.
from homeassistant.components.http.server import StaticPathConfig
from homeassistant.core import HomeAssistant

CARD_URL: Final = "/timerify_frontend/timerify-card.js"
"""Where the bundle is served, the same for every version of it."""
CARD_FILE: Final = Path(__file__).parent / "frontend" / "timerify-card.js"
VERSION_LENGTH: Final = 16
"""The hexadecimal digits of the bundle's SHA-256 that make its version."""


def card_module_url(bundle: bytes) -> str:
    """The address dashboards load the card from: where it is served, and the version of
    this bundle, which another bundle does not share."""
    version = hashlib.sha256(bundle).hexdigest()[:VERSION_LENGTH]
    return f"{CARD_URL}?v={version}"


def _module_url() -> str:
    return card_module_url(CARD_FILE.read_bytes())


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the card, and tell the frontend to load it on every dashboard.

    This belongs to the integration, not to a timer, and is done once: a static path
    cannot be registered twice. Timerify does not need the frontend, so a Home Assistant
    without one (no dashboards) serves the file and loads it nowhere.
    """
    module_url = await hass.async_add_executor_job(_module_url)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=True)]
    )
    if "frontend" in hass.config.components:
        add_extra_js_url(hass, module_url)
