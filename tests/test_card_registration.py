"""The dashboard card is part of the integration: Timerify serves it, and every
dashboard that the frontend serves loads it, with nothing for the user to set up.

Whether the committed bundle is what the sources in card/ build to is checked by the
build script of the card (`npm --prefix card run build:check`); these tests run without
Node. That the frontend's index page lists the module is shown in a real Home
Assistant by the smoke test and the end-to-end tests of the card.
"""

import hashlib
import logging
from http import HTTPStatus
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.timerify.card import CARD_FILE, CARD_URL, card_module_url

from .conftest import FakeTarget, SetupTarget
from .helpers import AC_ID, restart

CACHE_FOR_31_DAYS = "public, max-age=2678400"


async def served(
    client_of: ClientSessionGenerator,
) -> tuple[HTTPStatus, bytes, str | None]:
    """What a browser that has not logged in gets for the card's address: the status,
    the body and the cache header."""
    client = await client_of()
    response = await client.get(CARD_URL)
    return (
        HTTPStatus(response.status),
        await response.read(),
        response.headers.get("Cache-Control"),
    )


async def test_card_is_served_to_anyone(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """The browser loads the module before anyone has logged in, so the file is open to
    everyone, and the browser may keep it for a month: its address changes with it."""
    await setup_target()
    bundle = await hass.async_add_executor_job(CARD_FILE.read_bytes)

    status, body, cache = await served(hass_client_no_auth)

    assert status is HTTPStatus.OK
    assert body == bundle
    assert cache == CACHE_FOR_31_DAYS


def test_module_url_follows_the_bundle() -> None:
    """A new bundle has a new address, so that a browser that kept the old one for a
    month fetches the new one; the same bundle always has the same address."""
    assert card_module_url(b"a") == (
        CARD_URL + "?v=" + hashlib.sha256(b"a").hexdigest()[:16]
    )
    assert card_module_url(b"a") != card_module_url(b"b")
    assert card_module_url(b"a") == card_module_url(b"a")


async def test_timerify_runs_without_the_frontend(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """A Home Assistant with no dashboards (no frontend) still runs the timers, and
    still serves the file, which costs nothing."""
    entry = await setup_target()

    assert entry.state is ConfigEntryState.LOADED
    assert "frontend" not in hass.config.components
    status, _, _ = await served(hass_client_no_auth)
    assert status is HTTPStatus.OK


async def test_dashboards_load_the_card_once(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """With the frontend there, every dashboard is told to load the card, under an
    address that carries the version of the bundle; two timers, and a timer that starts
    again, do not tell it twice."""
    hass.config.components.add("frontend")
    bundle = await hass.async_add_executor_job(CARD_FILE.read_bytes)

    with patch("custom_components.timerify.card.add_extra_js_url") as add:
        first = await setup_target()
        await setup_target(target=AC_ID)
        await restart(hass, first)

    add.assert_called_once_with(hass, card_module_url(bundle))


async def test_reloading_a_timer_keeps_the_card(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    hass_client_no_auth: ClientSessionGenerator,
    caplog: logging.LogCaptureFixture,
) -> None:
    """The card is registered with the integration, not with a timer: reloading one
    timer, which a change of its intervals does, neither fails nor loses the file."""
    first = await setup_target()
    second = await setup_target(target=AC_ID)

    await restart(hass, first)

    assert first.state is ConfigEntryState.LOADED
    assert second.state is ConfigEntryState.LOADED
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []
    status, _, _ = await served(hass_client_no_auth)
    assert status is HTTPStatus.OK
