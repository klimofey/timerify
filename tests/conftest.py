"""Shared fixtures for Timerify tests."""

import asyncio
import copy
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Final

import probatio
import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    WEEKDAYS,
)
from homeassistant.core import (
    Context,
    HomeAssistant,
    Service,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    split_entity_id,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.const import (
    CONF_DEFAULT_DURATION,
    CONF_MODE,
    CONF_RUNTIME,
    CONF_TARGET,
    CONF_WORKDAY_SENSOR,
    DOMAIN,
    Mode,
)
from custom_components.timerify.runtime import RUNTIME_STORAGE_VERSION
from custom_components.timerify.store import TimerStore

from .helpers import (
    AC_ATTRS,
    AC_ID,
    START,
    TARGET_ID,
    runtime_storage_key,
    storage_key,
)

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
    _echoing_unknown: bool = False
    _echoes: int = 0
    _reporting_late: bool = False
    _late: list[tuple[Obey, ServiceCall]] = field(default_factory=list)
    _reverting: int = 0
    _last_context: Context | None = None
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

    def ignore_calls(
        self, *, echo_attribute: bool = False, echo_unknown: bool = False
    ) -> None:
        """Make every service call succeed without the entity doing anything, until
        `obey_calls`. With `echo_attribute` the device also answers each call with a
        report of its unchanged state and a new attribute, as an MQTT switch that
        publishes its full state after every command does. With `echo_unknown` it
        answers each call by writing `unknown` and then the state it had, as a device
        that drops its state while it handles a command."""
        self._ignoring = True
        self._echoing = echo_attribute
        self._echoing_unknown = echo_unknown

    def obey_calls(self) -> None:
        """End `ignore_calls`: the entity does what it is told again."""
        self._ignoring = False
        self._echoing = False
        self._echoing_unknown = False

    def report_next_call_late(self) -> None:
        """Make the next service call succeed with the entity changing only when
        `report_late` is called, as a cloud integration does that confirms a command
        after the call returned. The change then carries the context of the call."""
        self._reporting_late = True

    def revert_next_calls(self, count: int) -> None:
        """Make the device undo each of the next `count` service calls by itself, as a
        relay with an auto-off time of a few seconds or a plug that trips on overload
        does: it obeys, and at once shows the state it was in. Both changes carry the
        context of the call, because Home Assistant credits the writes of an entity to
        the last call it took for five seconds."""
        self._reverting = count

    async def set_state_credited_to_last_call(self, value: str) -> None:
        """Change the state from outside within the five seconds in which Home
        Assistant credits the writes of the entity to the last call it took, as a
        switch pressed on the wall just after a command is: the change carries the
        context of that call."""
        assert self._last_context is not None, "the entity has taken no call yet"
        self.write(value, context=self._last_context)
        await self.hass.async_block_till_done()

    async def report_late(self) -> None:
        """The device reports what the calls it took did, in the order it took them,
        and everything that follows settles."""
        late, self._late = self._late, []
        for obey, call in late:
            obey(self, call)
        await self.hass.async_block_till_done()

    def hold_next_call(self) -> HeldCall:
        """Make the next service call slow: it waits inside the device."""
        self._held = HeldCall()
        return self._held

    def _echo(self, call: ServiceCall) -> None:
        """Answer an ignored call as `ignore_calls` says, with the call's context."""
        self._echoes += 1
        before = self.state
        if self._echoing_unknown:
            self.write(STATE_UNKNOWN, context=call.context)
        attributes = {"echoes": self._echoes} if self._echoing else {}
        self.write(before, context=call.context, **attributes)

    async def take(
        self,
        service: str,
        obey: Obey,
        call: ServiceCall,
        entity_id: str,
        data: dict[str, Any],
    ) -> None:
        """The device receives `call` for its `entity_id` and does what it is set to do:
        hold it, fail it, report late, ignore it or obey."""
        self.calls.append((service, entity_id))
        self.call_data.append((service, data))
        self._last_context = call.context
        if self._held is not None:
            held, self._held = self._held, None
            held.reached.set()
            await held.release.wait()
        if self._failure is not None and self._failure[0] in (None, service):
            _, failure = self._failure
            self._failure = None
            raise failure
        if self._reporting_late:
            self._reporting_late = False
            self._late.append((obey, call))
            return
        if self._ignoring or self._ignore_next:
            self._ignore_next = False
            if (self._echoing or self._echoing_unknown) and self._echoes < ECHO_LIMIT:
                self._echo(call)
            return
        if self._reverting:
            self._reverting -= 1
            before = self.state
            obey(self, call)
            self.write(before, context=call.context)
            return
        obey(self, call)


@dataclass
class FakeServices:
    """The services of the domains the fake targets of a test are in, and who takes
    which call.

    A domain has one set of services for all its entities, so the first fake of a
    domain to provide a service registers one handler for it, and the handler hands
    each entity of a call to the fake that owns the entity. An entity of Timerify's own
    (the switch of an interval) goes on to the service that was there before, which is
    the domain's own. A call for any other entity fails: it is the test that is wrong,
    not the fake that happens to be of the same domain. The entities of that call which
    have an owner still get their call, and the failure names every other one.
    """

    hass: HomeAssistant
    strays: list[str] = field(default_factory=list)
    """Every call for an entity no fake owns, as "<domain>.<service> <entity_id>"."""
    _owners: dict[tuple[str, str], dict[str, tuple[FakeTarget, Obey]]] = field(
        default_factory=dict
    )
    """For each (domain, service), the fake that owns each entity, by its `_key`, with
    what the fake does when the device obeys the call."""

    def provide(self, target: FakeTarget, services: Mapping[str, Obey]) -> None:
        """Provide the services of the domain of `target`, and make it the owner of its
        entity for each of them."""
        domain, _ = split_entity_id(target.entity_id)
        key = self._key(target.entity_id)
        for service, obey in services.items():
            if (domain, service) not in self._owners:
                self._owners[domain, service] = {}
                self._register(domain, service)
            self._owners[domain, service][key] = (target, obey)

    def _key(self, entity_id: str) -> str:
        """What tells the owner of an entity: its registry id, which stays when the user
        renames it and comes back when its integration restores it, else its entity
        id."""
        registered = er.async_get(self.hass).async_get(entity_id)
        return entity_id if registered is None else registered.id

    def _is_timerify_entity(self, entity_id: str) -> bool:
        """Whether `entity_id` is an entity of Timerify's own, not of the target's
        integration: the target may have been renamed, so its id is not a test."""
        registered = er.async_get(self.hass).async_get(entity_id)
        return registered is not None and registered.platform == DOMAIN

    def _register(self, domain: str, service: str) -> None:
        """Register the one handler of `domain.service`."""
        elsewhere = self.hass.services.async_services_for_domain(domain).get(service)

        async def handle(call: ServiceCall) -> None:
            data = dict(call.data)
            entity_ids: list[str] = cv.ensure_list(data.pop("entity_id"))
            ours: list[str] = []
            owned: list[tuple[str, FakeTarget, Obey]] = []
            strays: list[str] = []
            for entity_id in entity_ids:
                if elsewhere is not None and self._is_timerify_entity(entity_id):
                    ours.append(entity_id)
                elif (
                    owner := self._owners[domain, service].get(self._key(entity_id))
                ) is not None:
                    owned.append((entity_id, *owner))
                else:
                    strays.append(entity_id)
            self.strays.extend(f"{domain}.{service} {stray}" for stray in strays)
            if elsewhere is not None and ours:
                await self._forward(elsewhere, call, data, ours)
            for entity_id, target, obey in owned:
                await target.take(service, obey, call, entity_id, data)
            if strays:
                raise AssertionError(
                    f"no fake target owns {', '.join(strays)} ({domain}.{service})"
                )

        self.hass.services.async_register(domain, service, handle)

    async def _forward(
        self,
        elsewhere: Service,
        call: ServiceCall,
        data: dict[str, Any],
        entity_ids: list[str],
    ) -> None:
        """Hand the call for `entity_ids`, entities of Timerify's own, on to the service
        that was there before."""
        forwarded = ServiceCall(
            self.hass,
            call.domain,
            call.service,
            {**data, "entity_id": entity_ids},
            call.context,
        )
        if (
            running := self.hass.async_run_hass_job(elsewhere.job, forwarded)
        ) is not None:
            await running


NO_ENTITY_MATCHED: Final = (
    "Service call requested response data but did not match any entities"
)
"""What Home Assistant raises when an entity service is asked for a response and no
entity answers it, as for a sensor that is unavailable. A test against the real Workday
integration pins that this is what it raises."""


@dataclass
class FakeWorkday:
    """The Workday integration as the other integrations see it: a binary sensor of
    platform `workday` that says whether today is a working day, and the
    `workday.check_date` service that says it of any day.

    The service answers as the real one does: `{entity_id: {"workday": ...}}`, and
    while the sensor is unavailable it raises the error that a call for an entity that
    is not there gets, since Home Assistant cannot tell the two apart.
    """

    hass: HomeAssistant
    entity_id: str = "binary_sensor.workday_sensor"
    workdays: set[str] = field(
        default_factory=lambda: {"sun", "mon", "tue", "wed", "thu"}
    )
    """The weekdays that are working days: Israel's week."""
    holidays: set[date] = field(default_factory=set)
    """The days that are not working days though their weekday is."""
    asked: list[date] = field(default_factory=list)
    """The day of every `check_date` call received, failed ones included."""
    _available: bool = True
    _state: str = STATE_ON
    _failure: Exception | None = None
    _held: HeldCall | None = None

    def is_workday(self, day: date) -> bool:
        """Whether `day` is a working day by the week and the holidays."""
        return WEEKDAYS[day.weekday()] in self.workdays and day not in self.holidays

    def write(self, available: bool | None = None) -> None:
        """Write the state of the sensor, which is that of today when it comes back
        and unchanged otherwise: with `available` left out it is a report of what it
        already says, which Workday makes at every local midnight."""
        if available is not None:
            self._available = available
            if available:
                today = dt_util.now().date()
                self._state = STATE_ON if self.is_workday(today) else STATE_OFF
        self.hass.states.async_set(
            self.entity_id, self._state if self._available else STATE_UNAVAILABLE
        )

    async def set_available(self, on: bool) -> None:
        """Make the sensor unavailable, as a reloading Workday is, or bring it back,
        and let everything that follows settle."""
        self.write(on)
        await self.hass.async_block_till_done()

    async def report(self) -> None:
        """Rewrite the state of the sensor as it is, and let everything that follows
        settle."""
        self.write()
        await self.hass.async_block_till_done()

    async def rename(self, new_entity_id: str) -> None:
        """Give the sensor another entity id, as the user does in its settings: the
        registry entry moves, the entity takes its state to the new id and answers the
        service for it, and everything that follows settles."""
        old_entity_id, self.entity_id = self.entity_id, new_entity_id
        er.async_get(self.hass).async_update_entity(
            old_entity_id, new_entity_id=new_entity_id
        )
        self.hass.states.async_remove(old_entity_id)
        self.write()
        await self.hass.async_block_till_done()

    async def remove(self) -> None:
        """Delete the sensor, as the user does in its settings: the registry entry and
        the state go, and the service, which stays, finds no entity to answer for.
        Everything that follows settles."""
        er.async_get(self.hass).async_remove(self.entity_id)
        self._available = False
        self.hass.states.async_remove(self.entity_id)
        await self.hass.async_block_till_done()

    def fail_next_call(self, error: Exception | None = None) -> None:
        """Make the next `check_date` fail, with `error` (a bug of the integration may
        raise anything) or as a sensor that could not answer."""
        self._failure = error or HomeAssistantError("The sensor could not answer")

    def hold_next_call(self) -> HeldCall:
        """Make the next `check_date` slow: it has its answer, or its error, and waits
        before it gives it."""
        self._held = HeldCall()
        return self._held

    async def check_date(self, call: ServiceCall) -> ServiceResponse:
        """The service `workday.check_date`."""
        day: date = call.data["check_date"]
        self.asked.append(day)
        failure, self._failure = self._failure, None
        if failure is None and (
            call.data["entity_id"] != self.entity_id or not self._available
        ):
            failure = HomeAssistantError(NO_ENTITY_MATCHED)
        if self._held is not None:
            held, self._held = self._held, None
            held.reached.set()
            await held.release.wait()
        if failure is not None:
            raise failure
        return {self.entity_id: {"workday": self.is_workday(day)}}


@pytest.fixture
def fake_workday(hass: HomeAssistant) -> FakeWorkday:
    """A Workday sensor, `binary_sensor.workday_sensor`, for a working week from
    Sunday to Thursday and no holidays: registered under the platform `workday` with
    its `check_date` service."""
    provider = MockConfigEntry(domain="workday")
    provider.add_to_hass(hass)
    workday = FakeWorkday(hass)
    object_id = split_entity_id(workday.entity_id)[1]
    er.async_get(hass).async_get_or_create(
        "binary_sensor",
        provider.domain,
        object_id,
        config_entry=provider,
        original_name="Workday Sensor",
        suggested_object_id=object_id,
    )
    workday.write(True)
    hass.services.async_register(
        provider.domain,
        "check_date",
        workday.check_date,
        schema=probatio.Schema(
            {
                probatio.Required("entity_id"): cv.entity_id,
                probatio.Required("check_date"): cv.date,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    return workday


type ProvideTarget = Callable[..., FakeTarget]


@pytest.fixture
def clock_at_start(freezer: FrozenDateTimeFactory) -> None:
    """Freeze the clock at `START`, where every entity test starts."""
    freezer.move_to(START)


@pytest.fixture
def hass_access_token(
    hass: HomeAssistant, clock_at_start: None, hass_access_token: str
) -> str:
    """The access token of the admin, made with the clock at `START`.

    A token is stamped with the clock, and one made before the clock goes back to
    `START` is not valid yet, so a websocket test would be refused with `auth_invalid`
    or not, depending on the order of its arguments.
    """
    return hass_access_token


@pytest.fixture
def hass_read_only_access_token(
    hass: HomeAssistant, clock_at_start: None, hass_read_only_access_token: str
) -> str:
    """The access token of the user who is not an admin, made with the clock at
    `START`; see `hass_access_token`."""
    return hass_read_only_access_token


def provide_fake(
    hass: HomeAssistant,
    services: FakeServices,
    entity_id: str,
    obeys: Mapping[str, Obey],
    *,
    name: str,
    on_device: bool = True,
    capability_attributes: dict[str, Any] | None = None,
    state_attributes: dict[str, Any] | None = None,
) -> FakeTarget:
    """Make an entity the way another integration provides it, switched off: a registry
    entry (on a device called `name` unless `on_device` is false), a state, and the
    services of `obeys`, which `services` hands the calls for the entity to."""
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
        capability_attributes=copy.deepcopy(dict(capability_attributes or {})),
        state_attributes=state_attributes or {},
    )
    target.write("off")
    services.provide(target, obeys)
    return target


@pytest.fixture
async def provide_target(
    hass: HomeAssistant, clock_at_start: None
) -> AsyncIterator[ProvideTarget]:
    """Make an entity the way another integration provides it, switched off, at
    `START`: `provide(entity_id, services, name=..., ...)`.

    The fakes of a test share the services of their domains, and each takes only the
    calls for its own entity. A call for any other entity fails, but Timerify catches
    the failure of a service call, so the test ends with a check that there was none.
    """
    # Timerify adds switches, so the switch component runs whenever it does. It sets its
    # services up with itself, and would replace those of a fake that came before it.
    assert await async_setup_component(hass, "switch", {})
    fake_services = FakeServices(hass)

    def provide(
        entity_id: str,
        services: Mapping[str, Obey],
        *,
        name: str,
        on_device: bool = True,
        capability_attributes: dict[str, Any] | None = None,
        state_attributes: dict[str, Any] | None = None,
    ) -> FakeTarget:
        return provide_fake(
            hass,
            fake_services,
            entity_id,
            services,
            name=name,
            on_device=on_device,
            capability_attributes=capability_attributes,
            state_attributes=state_attributes,
        )

    yield provide

    assert fake_services.strays == [], (
        f"calls for entities no fake target owns: {fake_services.strays}"
    )


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
    of `stored_version`; the entry then starts the way it does after a restart.
    `workday_sensor` is the Workday sensor the timer asks about the days, and `runtime`
    makes the timer count how long its target is on; `stored_runtime` is what an earlier
    run left in the file of that count, in the form of `stored_runtime_version`. A test
    that sets up a target provides it first, through one of the `fake_*` fixtures.
    """

    async def setup(
        mode: Mode = "strict",
        default_duration: int = 45,
        target: str = TARGET_ID,
        stored: dict[str, Any] | None = None,
        stored_version: int = TimerStore.STORAGE_VERSION,
        workday_sensor: str | None = None,
        runtime: bool = False,
        stored_runtime: dict[str, Any] | None = None,
        stored_runtime_version: int = RUNTIME_STORAGE_VERSION,
    ) -> MockConfigEntry:
        options: dict[str, Any] = {
            CONF_TARGET: target,
            CONF_MODE: mode,
            CONF_DEFAULT_DURATION: default_duration,
        }
        if workday_sensor is not None:
            options[CONF_WORKDAY_SENSOR] = workday_sensor
        if runtime:
            options[CONF_RUNTIME] = True
        entry = MockConfigEntry(
            domain=DOMAIN, version=1, title="Boiler", options=options
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
        if stored_runtime is not None:
            key = runtime_storage_key(entry)
            hass_storage[key] = {
                "version": stored_runtime_version,
                "minor_version": 1,
                "key": key,
                "data": stored_runtime,
            }
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    return setup
