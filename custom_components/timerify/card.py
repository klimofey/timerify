"""The dashboard card: the JavaScript module Timerify serves to every dashboard.

The module is built from the sources in `card/` and committed as
`frontend/timerify-card.js`, so that a plain download of the integration (HACS) has
it. It is served to everyone, because the browser loads it before a user has logged
in, at an address that does not change, with a cache of a month. What changes is the
address the dashboards are told to load it from: it carries a key made of the file's
contents, so that a new bundle is fetched at once.

The bytes served are the ones read when Timerify started, not the file on disk. HACS
writes an update while Home Assistant still runs the Python of the old version, and a
card that came from the new file would ask that Python for answers it does not give
yet. Until the restart that HACS asks for, the browser gets the card that goes with the
server, and the key on its address is the key of those bytes.
"""

import hashlib
from pathlib import Path
from typing import Final

from aiohttp import web
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http.static import CACHE_HEADERS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.http import HomeAssistantView

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


class CardView(HomeAssistantView):
    """Answers the card's address with the bundle it was made with."""

    url = CARD_URL
    name = "timerify:card"
    requires_auth = False

    def __init__(self, bundle: bytes) -> None:
        self._bundle = bundle

    @callback
    def get(self, request: web.Request) -> web.Response:
        """The bundle, for a month, to anyone."""
        return web.Response(
            body=self._bundle,
            content_type="text/javascript",
            charset="utf-8",
            headers=CACHE_HEADERS,
        )


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the card, and tell the frontend to load it on every dashboard.

    This belongs to the integration, not to a timer, and is done once, from
    `async_setup`: a second registration does not fail. Depending on what was
    registered in between, it either replaces the bytes with the file as it is by then,
    or is shadowed by the first view while the frontend is told the key of the new
    bytes. Timerify does not need the frontend, so a Home Assistant without one (no
    dashboards) serves the bundle and loads it nowhere.
    """
    bundle = await hass.async_add_executor_job(CARD_FILE.read_bytes)
    hass.http.register_view(CardView(bundle))
    if "frontend" in hass.config.components:
        add_extra_js_url(hass, card_module_url(bundle))
