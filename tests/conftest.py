"""Shared fixtures for Timerify tests."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.const import (
    CONF_DEFAULT_DURATION,
    CONF_MODE,
    CONF_TARGET,
    DOMAIN,
    Mode,
)

START = datetime(2026, 1, 5, 7, 0, tzinfo=UTC)
"""The frozen time every entity test starts at."""

TARGET_ID = "switch.boiler"


HTTP_APP_KEY_WARNING = (
    "ignore::aiohttp.web_exceptions.NotAppKeyWarning:homeassistant.components.http"
)
"""Home Assistant's own http component still keys its aiohttp application by
strings. Only that warning, from that component, is ignored."""


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Ignore `HTTP_APP_KEY_WARNING` in every test, also under `pytest -W error`.

    A `filterwarnings` setting in pyproject.toml would not do: pytest lets the
    command-line `-W` outrank it, while a mark outranks the command line.
    """
    for item in items:
        item.add_marker(pytest.mark.filterwarnings(HTTP_APP_KEY_WARNING))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load integrations from custom_components/."""


@dataclass
class HeldCall:
    """A service call stuck inside a slow device until it is released."""

    reached: asyncio.Event = field(default_factory=asyncio.Event)
    """Set once the call is inside the device."""
    release: asyncio.Event = field(default_factory=asyncio.Event)
    """Set it to let the device finish the call."""


@dataclass
class FakeTarget:
    """A switch the way another integration provides it: a registry entry on a
    device, a state, and `turn_on`/`turn_off` services that record every call."""

    hass: HomeAssistant
    device_id: str | None
    """The device the switch is on; None when it belongs to no device."""
    calls: list[tuple[str, str]] = field(default_factory=list)
    """Every service call received as (service, entity_id), failed ones included."""
    _fail_next: bool = False
    _held: HeldCall | None = None

    async def set_state(self, value: str, **attributes: str | int) -> None:
        """Change the state from outside, as a wall switch or a vendor app would."""
        self.hass.states.async_set(TARGET_ID, value, attributes)
        await self.hass.async_block_till_done()

    def fail_next_call(self) -> None:
        """Make the next service call fail as a device that rejects it."""
        self._fail_next = True

    def hold_next_call(self) -> HeldCall:
        """Make the next service call slow: it waits inside the device."""
        self._held = HeldCall()
        return self._held

    def register_services(self) -> None:
        """Provide `switch.turn_on` and `switch.turn_off`."""
        for service in ("turn_on", "turn_off"):
            self.hass.services.async_register("switch", service, self._handler(service))

    def _handler(self, service: str) -> Callable[[ServiceCall], Awaitable[None]]:
        async def handle(call: ServiceCall) -> None:
            self.calls.append((service, call.data["entity_id"]))
            if self._held is not None:
                held, self._held = self._held, None
                held.reached.set()
                await held.release.wait()
            if self._fail_next:
                self._fail_next = False
                raise HomeAssistantError("The device rejected the command")
            self.hass.states.async_set(
                call.data["entity_id"],
                "on" if service == "turn_on" else "off",
                context=call.context,
            )

        return handle


@pytest.fixture
def fake_target(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, request: pytest.FixtureRequest
) -> FakeTarget:
    """`switch.boiler` on a device called Boiler, switched off, at `START`.

    Parametrize it indirectly with `False` for a switch that is on no device.
    """
    freezer.move_to(START)
    provider = MockConfigEntry(domain="boiler_maker")
    provider.add_to_hass(hass)
    device_id = None
    if getattr(request, "param", True):
        device_id = (
            dr.async_get(hass)
            .async_get_or_create(
                config_entry_id=provider.entry_id,
                identifiers={("boiler_maker", "boiler")},
                name="Boiler",
            )
            .id
        )
    er.async_get(hass).async_get_or_create(
        "switch",
        "boiler_maker",
        "boiler",
        config_entry=provider,
        device_id=device_id,
        original_name="Boiler",
        suggested_object_id="boiler",
    )
    hass.states.async_set(TARGET_ID, "off")
    target = FakeTarget(hass, device_id)
    target.register_services()
    return target


type SetupTarget = Callable[..., Awaitable[MockConfigEntry]]


@pytest.fixture
async def setup_target(
    hass: HomeAssistant, fake_target: FakeTarget, hass_storage: dict[str, Any]
) -> SetupTarget:
    """Set up a Timerify entry for `switch.boiler`; it returns the loaded entry.

    `stored` is what an earlier run left in the entry's storage file, as the store
    writes it; the entry then starts the way it does after a restart.
    """

    async def setup(
        mode: Mode = "strict",
        default_duration: int = 45,
        target: str = TARGET_ID,
        stored: dict[str, Any] | None = None,
    ) -> MockConfigEntry:
        entry = MockConfigEntry(
            domain=DOMAIN,
            version=1,
            title="Boiler",
            options={
                CONF_TARGET: target,
                CONF_MODE: mode,
                CONF_DEFAULT_DURATION: default_duration,
            },
        )
        entry.add_to_hass(hass)
        if stored is not None:
            key = f"timerify.{entry.entry_id}"
            hass_storage[key] = {
                "version": 1,
                "minor_version": 1,
                "key": key,
                "data": stored,
            }
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    return setup
