"""Shared fixtures for Timerify tests."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Context, HomeAssistant, ServiceCall, split_entity_id
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
from custom_components.timerify.store import TimerStore

from .helpers import AC_ATTRS, AC_ID, START, TARGET_ID, storage_key

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


ECHO_LIMIT = 50
"""How often a device that echoes ignored calls does so: a loop in Timerify then ends
the test with the wrong number of calls instead of hanging it."""


@dataclass
class HeldCall:
    """A service call stuck inside a slow device until it is released."""

    reached: asyncio.Event = field(default_factory=asyncio.Event)
    """Set once the call is inside the device."""
    release: asyncio.Event = field(default_factory=asyncio.Event)
    """Set it to let the device finish the call."""


type Obey = Callable[[FakeTarget, ServiceCall], None]
"""What a service does to the target's state when the device obeys the call."""


def switches_to(state: str) -> Obey:
    """A service that puts the target into `state`."""

    def obey(target: FakeTarget, call: ServiceCall) -> None:
        target.write(state, context=call.context)

    return obey


def sets_state_to_the_given(field_name: str) -> Obey:
    """A service whose `field_name` is the state the target ends up in."""

    def obey(target: FakeTarget, call: ServiceCall) -> None:
        target.write(call.data[field_name], context=call.context)

    return obey


def sets_attribute(attribute: str) -> Obey:
    """A service whose field `attribute` becomes the attribute of that name."""

    def obey(target: FakeTarget, call: ServiceCall) -> None:
        target.state_attributes[attribute] = call.data[attribute]
        target.write(target.state, context=call.context)

    return obey


SWITCH_SERVICES: Final[dict[str, Obey]] = {
    "turn_on": switches_to("on"),
    "turn_off": switches_to("off"),
}
"""The services of a plain switch, a light or a media player."""

CLIMATE_SERVICES: Final[dict[str, Obey]] = {
    "turn_on": switches_to("heat"),
    "turn_off": switches_to("off"),
    "set_hvac_mode": sets_state_to_the_given("hvac_mode"),
    "set_temperature": sets_attribute("temperature"),
    "set_fan_mode": sets_attribute("fan_mode"),
}
"""The services of an air conditioner; a plain turn-on starts it heating."""


@dataclass
class FakeTarget:
    """An entity the way another integration provides it: a registry entry on a
    device, a state, and services that record every call and, when the device
    obeys, change the state."""

    hass: HomeAssistant
    device_id: str | None
    """The device the entity is on; None when it belongs to no device."""
    entity_id: str = TARGET_ID
    capability_attributes: dict[str, Any] = field(default_factory=dict)
    """What Home Assistant keeps on every state of the entity, also while it is
    unavailable: the supported features and the lists of modes."""
    state_attributes: dict[str, Any] = field(default_factory=dict)
    """What describes the entity while it works; services may change it."""
    calls: list[tuple[str, str]] = field(default_factory=list)
    """Every service call received as (service, entity_id), failed ones included."""
    call_data: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    """Every service call received as (service, data without `entity_id`)."""
    _failure: tuple[str | None, Exception] | None = None
    _ignore_next: bool = False
    _ignoring: bool = False
    _echoing: bool = False
    _echoes: int = 0
    _held: HeldCall | None = None

    @property
    def state(self) -> str:
        """The state the entity is in now."""
        state = self.hass.states.get(self.entity_id)
        assert state is not None
        return state.state

    def write(
        self, value: str, *, context: Context | None = None, **attributes: str | int
    ) -> None:
        """Write the state as the entity does: its capability attributes always, its
        state attributes unless it is unavailable or unknown."""
        working = value not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        self.hass.states.async_set(
            self.entity_id,
            value,
            {
                **self.capability_attributes,
                **(self.state_attributes if working else {}),
                **attributes,
            },
            context=context,
        )

    async def set_state(self, value: str, **attributes: str | int) -> None:
        """Change the state from outside, as a wall switch or a vendor app would."""
        self.write(value, **attributes)
        await self.hass.async_block_till_done()

    def fail_next_call(
        self, error: Exception | None = None, service: str | None = None
    ) -> None:
        """Make the next service call fail, the next one of `service` if given: with
        `error`, or as a device that rejects the command."""
        self._failure = (
            service,
            error or HomeAssistantError("The device rejected the command"),
        )

    def ignore_next_call(self) -> None:
        """Make the next service call succeed without the entity doing anything, as
        a device out of reach that the integration cannot tell about."""
        self._ignore_next = True

    def ignore_calls(self, *, echo_attribute: bool = False) -> None:
        """Make every service call succeed without the entity doing anything, until
        `obey_calls`. With `echo_attribute` the device also answers each call with a
        report of its unchanged state and a new attribute, as an MQTT switch that
        publishes its full state after every command does."""
        self._ignoring = True
        self._echoing = echo_attribute

    def obey_calls(self) -> None:
        """End `ignore_calls`: the entity does what it is told again."""
        self._ignoring = False
        self._echoing = False

    def hold_next_call(self) -> HeldCall:
        """Make the next service call slow: it waits inside the device."""
        self._held = HeldCall()
        return self._held

    def provide_services(self, services: Mapping[str, Obey]) -> None:
        """Provide the services of the entity's domain."""
        domain, _ = split_entity_id(self.entity_id)
        for service, obey in services.items():
            self.hass.services.async_register(
                domain, service, self._handler(service, obey)
            )

    def _handler(
        self, service: str, obey: Obey
    ) -> Callable[[ServiceCall], Awaitable[None]]:
        async def handle(call: ServiceCall) -> None:
            data = dict(call.data)
            entity_id = data.pop("entity_id")
            self.calls.append((service, entity_id))
            self.call_data.append((service, data))
            if self._held is not None:
                held, self._held = self._held, None
                held.reached.set()
                await held.release.wait()
            if self._failure is not None and self._failure[0] in (None, service):
                _, failure = self._failure
                self._failure = None
                raise failure
            if self._ignoring or self._ignore_next:
                self._ignore_next = False
                if self._echoing and self._echoes < ECHO_LIMIT:
                    self._echoes += 1
                    self.write(self.state, context=call.context, echoes=self._echoes)
                return
            obey(self, call)

        return handle


type ProvideTarget = Callable[..., FakeTarget]


@pytest.fixture
def provide_target(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> ProvideTarget:
    """Make an entity the way another integration provides it, switched off, at
    `START`: `provide(entity_id, services, device_name=..., ...)`."""
    freezer.move_to(START)

    def provide(
        entity_id: str,
        services: Mapping[str, Obey],
        *,
        name: str,
        on_device: bool = True,
        capability_attributes: dict[str, Any] | None = None,
        state_attributes: dict[str, Any] | None = None,
    ) -> FakeTarget:
        domain, object_id = split_entity_id(entity_id)
        provider = MockConfigEntry(domain=f"{object_id}_maker")
        provider.add_to_hass(hass)
        device_id = None
        if on_device:
            device_id = (
                dr.async_get(hass)
                .async_get_or_create(
                    config_entry_id=provider.entry_id,
                    identifiers={(provider.domain, object_id)},
                    name=name,
                )
                .id
            )
        er.async_get(hass).async_get_or_create(
            domain,
            provider.domain,
            object_id,
            config_entry=provider,
            device_id=device_id,
            original_name=name,
            suggested_object_id=object_id,
        )
        target = FakeTarget(
            hass,
            device_id,
            entity_id,
            capability_attributes=capability_attributes or {},
            state_attributes=state_attributes or {},
        )
        target.write("off")
        target.provide_services(services)
        return target

    return provide


@pytest.fixture
def fake_target(
    provide_target: ProvideTarget, request: pytest.FixtureRequest
) -> FakeTarget:
    """`switch.boiler` on a device called Boiler, switched off, at `START`.

    Parametrize it indirectly with `False` for a switch that is on no device.
    """
    return provide_target(
        TARGET_ID,
        SWITCH_SERVICES,
        name="Boiler",
        on_device=getattr(request, "param", True),
    )


@pytest.fixture
def fake_climate(provide_target: ProvideTarget) -> FakeTarget:
    """`climate.ac` on a device called AC, switched off, at `START`: an air
    conditioner with a target temperature and fan modes."""
    return provide_target(
        AC_ID,
        CLIMATE_SERVICES,
        name="AC",
        capability_attributes=AC_ATTRS,
        state_attributes={"temperature": 20, "fan_mode": "auto"},
    )


@pytest.fixture
def fake_media_player(provide_target: ProvideTarget) -> FakeTarget:
    """`media_player.tv` on a device called TV, switched off, at `START`."""
    return provide_target(
        "media_player.tv",
        SWITCH_SERVICES,
        name="TV",
        capability_attributes={
            "supported_features": int(
                MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
            )
        },
    )


type SetupTarget = Callable[..., Awaitable[MockConfigEntry]]


@pytest.fixture
async def setup_target(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> SetupTarget:
    """Set up a Timerify entry for `switch.boiler`; it returns the loaded entry.

    `stored` is what an earlier run left in the entry's storage file, in the form
    of `stored_version`; the entry then starts the way it does after a restart. A
    test that sets up a target provides it first, through one of the `fake_*`
    fixtures.
    """

    async def setup(
        mode: Mode = "strict",
        default_duration: int = 45,
        target: str = TARGET_ID,
        stored: dict[str, Any] | None = None,
        stored_version: int = TimerStore.STORAGE_VERSION,
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
            key = storage_key(entry)
            hass_storage[key] = {
                "version": stored_version,
                "minor_version": 1,
                "key": key,
                "data": stored,
            }
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    return setup
