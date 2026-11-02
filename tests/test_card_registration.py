"""The dashboard card is part of the integration: Timerify serves it, and every
dashboard that the frontend serves loads it, with nothing for the user to set up.

Whether the committed bundle is what the sources in card/ build to is checked by the
build script of the card (`npm --prefix card run build:check`); these tests run without
Node. That the frontend's index page lists the module is shown in a real Home
Assistant by the smoke test and the end-to-end tests of the card.
"""

import hashlib
import logging
from collections.abc import Mapping
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.timerify import card
from custom_components.timerify.card import CARD_FILE, CARD_URL, card_module_url

from .conftest import FakeTarget, SetupTarget
from .helpers import AC_ID, restart

CACHE_FOR_31_DAYS = "public, max-age=2678400"
JAVASCRIPT = "text/javascript; charset=utf-8"


async def served(
    client_of: ClientSessionGenerator,
) -> tuple[HTTPStatus, bytes, Mapping[str, str]]:
    """What a browser that has not logged in gets for the card's address: the status,
    the body and the headers."""
    client = await client_of()
    response = await client.get(CARD_URL)
    return HTTPStatus(response.status), await response.read(), response.headers


async def test_card_is_served_to_anyone(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """The browser loads the module before anyone has logged in, so the file is open to
    everyone, as JavaScript, and the browser may keep it for a month: its address
    changes with it."""
    await setup_target()
    bundle = await hass.async_add_executor_job(CARD_FILE.read_bytes)

    status, body, headers = await served(hass_client_no_auth)

    assert status is HTTPStatus.OK
    assert body == bundle
    assert headers["Content-Type"] == JAVASCRIPT
    assert headers["Cache-Control"] == CACHE_FOR_31_DAYS


@pytest.fixture
def card_on_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of the bundle that the integration reads as its card file, so that a
    test can write over it the way HACS writes an update."""
    copy = tmp_path / "timerify-card.js"
    copy.write_bytes(CARD_FILE.read_bytes())
    monkeypatch.setattr(card, "CARD_FILE", copy)
    return copy


async def test_the_card_served_is_the_one_registered_until_a_restart(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_client_no_auth: ClientSessionGenerator,
    card_on_disk: Path,
) -> None:
    """HACS writes a new bundle while Home Assistant still runs the Python of the old
    one, which answers the card with what the old card knows. The browser must not get
    the new bundle before the restart: the address the dashboards were told, with its
    version key, serves the bytes that key was made of."""
    hass.config.components.add("frontend")
    with patch("custom_components.timerify.card.add_extra_js_url") as add:
        await setup_target()
    module_url = add.call_args.args[1]
    registered = await hass.async_add_executor_job(card_on_disk.read_bytes)
    updated = b"export const card = 'a bundle that needs a newer server';"
    await hass.async_add_executor_job(card_on_disk.write_bytes, updated)

    client = await hass_client_no_auth()
    response = await client.get(module_url)

    body = await response.read()
    assert response.status == HTTPStatus.OK
    assert body == registered
    assert module_url == card_module_url(body)


async def test_a_timer_set_up_or_reloaded_after_the_update_keeps_the_registered_card(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    hass_client_no_auth: ClientSessionGenerator,
    card_on_disk: Path,
) -> None:
    """Registering the card again, as a second timer or a reload could, would not fail:
    it would swap the bytes for the file as it is by then, and the browser would get
    the new bundle before the restart after all."""
    first = await setup_target()
    registered = await hass.async_add_executor_job(card_on_disk.read_bytes)
    await hass.async_add_executor_job(card_on_disk.write_bytes, b"export {};")

    await setup_target(target=AC_ID)
    await restart(hass, first)

    status, body, _ = await served(hass_client_no_auth)
    assert status is HTTPStatus.OK
    assert body == registered


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
