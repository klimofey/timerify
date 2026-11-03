"""A real Home Assistant in a container, and what the smoke test and the end-to-end
tests of the dashboard card both do with one: start it from compose.yaml with a fresh
configuration, onboard it, add Timerify timers and intervals the way the pages of Home
Assistant do, and follow its states over the WebSocket API.

An `Instance` says which container: its compose project, the port it answers on and the
directory that holds its throwaway configuration. Two instances with different projects
and ports run side by side.
"""

import asyncio
import contextlib
import json
import os
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any, Literal

import aiohttp

COMPOSE_FILE = Path(__file__).parent / "compose.yaml"
DOMAIN = "timerify"
SWITCH = "input_boolean.smoke_boiler"
"""A switch that configuration.yaml declares, on no device."""
DEMO_SWITCH = "switch.decorative_lights"
"""A switch of the demo integration, which sits on a device of its own."""
LIMIT_SWITCH = "switch.ac"
"""The other switch of the demo integration, on a device of its own. It starts off. Both
the smoke test and the end-to-end tests give it a loose timer with a limit, each in a
container of its own."""
STARTUP_TIMEOUT = 240.0
CALL_TIMEOUT = 30.0
DEFAULT_DURATION_MINUTES = 30
"""The default duration the harness gives every strict timer it adds."""
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
"""The names the interval form gives the days of the week, Monday first."""

type State = dict[str, Any]
type Matcher = Callable[[State | None], bool]
type EntityMatcher = Callable[[str, State], bool]


class HarnessFailure(Exception):
    """Home Assistant, or its container, did not do what the harness asked."""


@dataclass(frozen=True)
class Instance:
    """One container of Home Assistant: the compose project it runs under, the port on
    this machine that it answers on, and the directory that holds its configuration."""

    project: str
    port: int
    config_dir: Path

    @property
    def base_url(self) -> str:
        # `localhost`, not 127.0.0.1: a browser registers the service worker of the
        # frontend only on https or on `localhost`.
        return f"http://localhost:{self.port}"

    @property
    def client_id(self) -> str:
        return f"{self.base_url}/"

    @property
    def redirect_uri(self) -> str:
        return f"{self.base_url}/?auth_callback=1"

    async def compose(self, *arguments: str) -> None:
        """Run `docker compose` on compose.yaml under the project of this instance."""
        command = [
            "docker",
            "compose",
            "--project-name",
            self.project,
            "--file",
            str(COMPOSE_FILE),
            *arguments,
        ]
        environment = {
            **os.environ,
            "TIMERIFY_HA_PORT": str(self.port),
            "TIMERIFY_HA_CONFIG": str(self.config_dir.resolve()),
        }
        process = await asyncio.create_subprocess_exec(*command, env=environment)
        if await process.wait() != 0:
            raise HarnessFailure(f"`{' '.join(command)}` failed")

    async def start_fresh(self) -> None:
        """Start Home Assistant on an empty configuration that has a `www` folder; it is
        not up yet when this returns, see `wait_until_up`.

        Home Assistant serves the files of `www` at `/local`, and only when the folder
        exists as it starts: the configuration of a user who serves files of their own
        has it, so this one has it too. The configuration directory is made here, by
        the user who runs the harness, so that the same user can put files into `www`
        afterwards; the container is not the one to create it."""
        await self.compose("down", "--remove-orphans")
        await asyncio.to_thread(self.config_dir.mkdir, parents=True, exist_ok=True)
        await self.compose("run", "--rm", "wipe")
        try:
            await asyncio.to_thread((self.config_dir / "www").mkdir)
        except PermissionError as error:
            raise HarnessFailure(
                f"Cannot make {self.config_dir / 'www'}: the configuration directory "
                "belongs to another user, most likely made by a container of an earlier"
                " run; remove it"
            ) from error
        await self.compose("up", "--detach", "homeassistant")

    async def restart(self, session: aiohttp.ClientSession) -> None:
        """Restart Home Assistant and wait for it to answer again."""
        await self.compose("restart", "--timeout", "60", "homeassistant")
        await wait_until_up(session, self)

    async def stop(self) -> None:
        await self.compose("down")

    async def print_logs(self, tail: int = 80) -> None:
        """Print the end of the log of Home Assistant."""
        try:
            await self.compose("logs", "--tail", str(tail), "homeassistant")
        except HarnessFailure as failure:
            # The failure that sent us here is the one to fix; this only says the logs
            # are lost.
            say(f"(the logs of Home Assistant could not be read: {failure})")


@dataclass(frozen=True)
class Timer:
    """The entities of the timer under test."""

    entry_id: str
    target: str
    """The entity the timer runs."""
    run_for: str
    ends_at: str
    next_command: str
    device_id: str
    """The device the entities sit on, from the entity registry."""
    runtime: str | None = None
    """The Runtime sensor; None for a timer that was added without the counter."""


def has_state(*values: str) -> Matcher:
    """Match a state whose value is one of `values`."""
    return lambda state: state is not None and state["state"] in values


def has_minutes(minutes: int) -> Matcher:
    """Match a numeric state equal to `minutes`."""

    def matches(state: State | None) -> bool:
        try:
            return state is not None and float(state["state"]) == minutes
        except ValueError:
            return False

    return matches


def is_known(state: State | None) -> bool:
    """Match a state that carries a value."""
    return state is not None and state["state"] not in ("unavailable", "unknown")


def timestamp(value: str) -> datetime:
    """Read a timestamp as Home Assistant writes them."""
    return datetime.fromisoformat(value)


def say(message: str) -> None:
    print(message, flush=True)


async def request_bytes(
    session: aiohttp.ClientSession,
    instance: Instance,
    method: str,
    path: str,
    access_token: str | None = None,
    **options: Any,
) -> bytes:
    """Call Home Assistant's HTTP API and return the body it answers with, as it is."""
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
    async with session.request(
        method, f"{instance.base_url}{path}", headers=headers, **options
    ) as response:
        body = await response.read()
        if response.status >= 400:
            raise HarnessFailure(
                f"{method} {path} answered {response.status}: "
                f"{body.decode(errors='replace')}"
            )
        return body


async def request_json(
    session: aiohttp.ClientSession,
    instance: Instance,
    method: str,
    path: str,
    access_token: str | None = None,
    **options: Any,
) -> Any:
    """Call Home Assistant's HTTP API and return the JSON it answers with."""
    body = await request_bytes(session, instance, method, path, access_token, **options)
    # An answer with no body is no value, as aiohttp reads it.
    return json.loads(body) if body.strip() else None


async def wait_until_up(session: aiohttp.ClientSession, instance: Instance) -> None:
    """Wait for the API of Home Assistant to answer; with no token, it says 401."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + STARTUP_TIMEOUT
    while True:
        try:
            async with session.get(
                f"{instance.base_url}/api/", timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == HTTPStatus.UNAUTHORIZED:
                    return
        except aiohttp.ClientError, TimeoutError:
            pass
        if loop.time() > deadline:
            raise HarnessFailure(
                f"Home Assistant did not answer within {STARTUP_TIMEOUT:.0f}s"
            )
        await asyncio.sleep(2)


async def onboard(
    session: aiohttp.ClientSession,
    instance: Instance,
    username: str,
    password: str,
    language: str = "en",
) -> str:
    """Take Home Assistant through onboarding, with `username` as its first user, an
    administrator; return the user's refresh token."""
    user = await request_json(
        session,
        instance,
        "POST",
        "/api/onboarding/users",
        json={
            "client_id": instance.client_id,
            "name": username,
            "username": username,
            "password": password,
            "language": language,
        },
    )
    tokens = await request_json(
        session,
        instance,
        "POST",
        "/auth/token",
        data={
            "grant_type": "authorization_code",
            "code": user["auth_code"],
            "client_id": instance.client_id,
        },
    )
    access_token = tokens["access_token"]
    for step in ("core_config", "analytics"):
        await request_json(
            session,
            instance,
            "POST",
            f"/api/onboarding/{step}",
            access_token,
            json={},
        )
    await request_json(
        session,
        instance,
        "POST",
        "/api/onboarding/integration",
        access_token,
        json={"client_id": instance.client_id, "redirect_uri": instance.redirect_uri},
    )
    return str(tokens["refresh_token"])


async def login(
    session: aiohttp.ClientSession,
    instance: Instance,
    username: str,
    password: str,
) -> str:
    """Log a user in the way the login page does, through the `homeassistant` login
    flow; return the user's refresh token."""
    flow_path = "/auth/login_flow"
    flow = await request_json(
        session,
        instance,
        "POST",
        flow_path,
        json={
            "client_id": instance.client_id,
            "handler": ["homeassistant", None],
            "redirect_uri": instance.redirect_uri,
        },
    )
    if flow["type"] != "form" or flow["step_id"] != "init":
        raise HarnessFailure(f"The login flow should ask who logs in, but gave {flow}")
    flow = await request_json(
        session,
        instance,
        "POST",
        f"{flow_path}/{flow['flow_id']}",
        json={
            "client_id": instance.client_id,
            "username": username,
            "password": password,
        },
    )
    if flow["type"] != "create_entry":
        raise HarnessFailure(
            f"The login flow should log {username} in, but gave {flow}"
        )
    tokens = await request_json(
        session,
        instance,
        "POST",
        "/auth/token",
        data={
            "grant_type": "authorization_code",
            "code": flow["result"],
            "client_id": instance.client_id,
        },
    )
    return str(tokens["refresh_token"])


async def new_access_token(
    session: aiohttp.ClientSession, instance: Instance, refresh_token: str
) -> str:
    """Exchange the refresh token for an access token."""
    tokens = await request_json(
        session,
        instance,
        "POST",
        "/auth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": instance.client_id,
        },
    )
    return str(tokens["access_token"])


class Socket:
    """The WebSocket API, with the state of every entity kept up to date.

    One task reads the connection: it answers pending calls and applies each
    `state_changed` event, so a wait for a state sees every change from the moment
    `watch_states` returned, and no change can slip by between two calls.
    """

    def __init__(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        self._ws = ws
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._states: dict[str, State] = {}
        self._changed = asyncio.Condition()
        self._closed = False
        self._reader = asyncio.create_task(self._read())

    async def close(self) -> None:
        await self._ws.close()
        await self._reader

    async def call(self, command: str, **fields: Any) -> Any:
        """Send a command and return its result."""
        if self._closed:
            raise HarnessFailure(f"{command}: the WebSocket is closed")
        message_id = self._next_id
        self._next_id += 1
        future = asyncio.get_running_loop().create_future()
        self._pending[message_id] = future
        try:
            await self._ws.send_json({"id": message_id, "type": command, **fields})
            return await asyncio.wait_for(future, CALL_TIMEOUT)
        except TimeoutError:
            raise HarnessFailure(
                f"{command} got no answer in {CALL_TIMEOUT}s"
            ) from None
        except ConnectionError as err:
            raise HarnessFailure(f"{command}: the WebSocket broke: {err}") from err
        finally:
            # A late answer finds no waiter and is dropped, see `_handle`.
            self._pending.pop(message_id, None)

    async def watch_states(self) -> None:
        """Start following the states of all entities."""
        await self.call("subscribe_events", event_type="state_changed")
        for state in await self.call("get_states"):
            # An event that arrived while this snapshot was on its way is newer.
            self._states.setdefault(state["entity_id"], state)

    def state(self, entity_id: str) -> State | None:
        return self._states.get(entity_id)

    async def wait_for_state(
        self, entity_id: str, matches: Matcher, expected: str, seconds: float
    ) -> State:
        """Wait until the entity's state matches; `expected` says what it should be."""

        def found() -> State | None:
            state = self._states.get(entity_id)
            return state if matches(state) else None

        def current() -> str:
            state = self._states.get(entity_id)
            return state["state"] if state else "missing"

        return await self._wait_for(found, entity_id, expected, seconds, current)

    async def wait_for_entity(
        self, matches: EntityMatcher, expected: str, seconds: float
    ) -> State:
        """Wait until the state of some entity matches, for an entity whose id is not
        known yet; returns that state, which names the entity."""

        def found() -> State | None:
            return next(
                (
                    state
                    for entity_id, state in self._states.items()
                    if matches(entity_id, state)
                ),
                None,
            )

        return await self._wait_for(found, "the entities", expected, seconds)

    async def _wait_for(
        self,
        found: Callable[[], State | None],
        what: str,
        expected: str,
        seconds: float,
        current: Callable[[], str] | None = None,
    ) -> State:
        """Wait until `found` gives a state; `what` names the thing waited for."""

        async def satisfied() -> State:
            async with self._changed:
                await self._changed.wait_for(
                    lambda: self._closed or found() is not None
                )
            if (state := found()) is None:
                raise HarnessFailure(
                    f"{what}: the WebSocket closed while waiting for {expected}"
                )
            return state

        try:
            return await asyncio.wait_for(satisfied(), seconds)
        except TimeoutError:
            found_now = f", it is {current()}" if current else ""
            raise HarnessFailure(
                f"{what}: expected {expected} within {seconds:.0f}s{found_now}"
            ) from None

    async def _read(self) -> None:
        try:
            async for message in self._ws:
                if message.type is aiohttp.WSMsgType.TEXT:
                    await self._handle(message.json())
        finally:
            # Wake everything that waits for the socket: calls and state waits alike.
            self._closed = True
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(HarnessFailure("The WebSocket closed"))
            async with self._changed:
                self._changed.notify_all()

    async def _handle(self, message: dict[str, Any]) -> None:
        match message:
            case {"type": "result", "id": int(message_id)}:
                if (future := self._pending.pop(message_id, None)) is None:
                    return  # Its caller gave up waiting.
                if message["success"]:
                    future.set_result(message["result"])
                else:
                    future.set_exception(HarnessFailure(message["error"]["message"]))
            case {
                "type": "event",
                "event": {"event_type": "state_changed", "data": data},
            }:
                async with self._changed:
                    if data["new_state"] is None:
                        self._states.pop(data["entity_id"], None)
                    else:
                        self._states[data["entity_id"]] = data["new_state"]
                    self._changed.notify_all()


@contextlib.asynccontextmanager
async def open_socket(
    session: aiohttp.ClientSession, instance: Instance, refresh_token: str
) -> AsyncIterator[Socket]:
    """Connect as the user the refresh token belongs to and follow the states until the
    block ends."""
    ws = await session.ws_connect(f"{instance.base_url}/api/websocket")
    await ws.receive_json()  # auth_required
    await ws.send_json(
        {
            "type": "auth",
            "access_token": await new_access_token(session, instance, refresh_token),
        }
    )
    reply = await ws.receive_json()
    if reply["type"] != "auth_ok":
        raise HarnessFailure(f"The WebSocket refused the token: {reply}")
    socket = Socket(ws)
    try:
        await socket.watch_states()
        yield socket
    finally:
        await socket.close()


async def wait_until_running(socket: Socket) -> None:
    """Wait for Home Assistant to finish starting. Its API answers well before that, and
    a container restarted in between comes back without the config entries that were
    just added to it."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + STARTUP_TIMEOUT
    while (await socket.call("get_config"))["state"] != "RUNNING":
        if loop.time() > deadline:
            raise HarnessFailure(
                f"Home Assistant was not running within {STARTUP_TIMEOUT:.0f}s"
            )
        await asyncio.sleep(1)


async def add_timer(
    session: aiohttp.ClientSession,
    socket: Socket,
    instance: Instance,
    access_token: str,
    target: str,
    *,
    mode: Literal["strict", "loose"] = "strict",
    on_target_device: bool = False,
    runtime: bool = False,
    limit: int | None = None,
) -> Timer:
    """Add a timer for `target` in Timerify the way the integrations page does.

    A strict timer gets the default duration of `DEFAULT_DURATION_MINUTES`; a loose one
    has none. Its limit box, "Turn off if left on for", holds `limit` minutes, or is
    left empty, so that the timer has no limit; a strict timer has no such box. With
    `on_target_device` the target must sit on a device, and the timer's entities must
    sit on that same device. With `runtime` the box "Count runtime" of the first form is
    ticked; without it the form is submitted as before the counter existed, which
    leaves the box at its default, and the timer must have no Runtime sensor.
    """
    flow_path = "/api/config/config_entries/flow"
    flow = await request_json(
        session,
        instance,
        "POST",
        flow_path,
        access_token,
        json={"handler": DOMAIN},
    )
    if flow["type"] != "menu" or "target" not in flow["menu_options"]:
        raise HarnessFailure(f"The flow should offer to add a timer, but gave {flow}")
    flow = await request_json(
        session,
        instance,
        "POST",
        f"{flow_path}/{flow['flow_id']}",
        access_token,
        json={"next_step_id": "target"},
    )
    first_form: dict[str, Any] = {"target": target, "mode": mode}
    if runtime:
        first_form["runtime"] = True
    steps: list[tuple[str, dict[str, Any]]] = [("target", first_form)]
    if mode == "strict":
        steps.append(("duration", {"default_duration": DEFAULT_DURATION_MINUTES}))
    else:
        steps.append(("limit", {} if limit is None else {"limit": limit}))
    for step_id, user_input in steps:
        if flow["type"] != "form" or flow["step_id"] != step_id:
            raise HarnessFailure(
                f"The flow should ask for {step_id!r}, but gave {flow}"
            )
        flow = await request_json(
            session,
            instance,
            "POST",
            f"{flow_path}/{flow['flow_id']}",
            access_token,
            json=user_input,
        )
    if flow["type"] == "form" and flow["step_id"] == "workday":
        # Asked only in a house that has a Workday sensor, and optional.
        flow = await request_json(
            session,
            instance,
            "POST",
            f"{flow_path}/{flow['flow_id']}",
            access_token,
            json={},
        )
    if flow["type"] != "create_entry":
        raise HarnessFailure(f"The flow should create the timer, but gave {flow}")
    entry_id = flow["result"]["entry_id"]
    registry = await socket.call("config/entity_registry/list")
    rows = {row["unique_id"]: row for row in registry if row["platform"] == DOMAIN}
    try:
        run_for = rows[f"{entry_id}_run_for"]
        ends_at = rows[f"{entry_id}_ends_at"]
        next_command = rows[f"{entry_id}_next_command"]
    except KeyError as missing:
        raise HarnessFailure(
            f"The timer has no entity {missing}: {list(rows)}"
        ) from None
    device_ids = {row["device_id"] for row in (run_for, ends_at, next_command)}
    if len(device_ids) != 1 or None in device_ids:
        raise HarnessFailure(
            "The timer's entities should share one device, "
            f"but are on {sorted(map(str, device_ids))}"
        )
    (device_id,) = device_ids
    if on_target_device:
        await expect_on_device_of(socket, registry, target, device_id)
    runtime_row = rows.get(f"{entry_id}_runtime")
    if (runtime_row is not None) != runtime:
        raise HarnessFailure(
            f"The timer should have {'a' if runtime else 'no'} Runtime sensor, "
            f"but the entities are {list(rows)}"
        )
    return Timer(
        entry_id,
        target,
        run_for["entity_id"],
        ends_at["entity_id"],
        next_command["entity_id"],
        device_id,
        None if runtime_row is None else runtime_row["entity_id"],
    )


async def expect_on_device_of(
    socket: Socket, registry: list[State], target: str, device_id: str
) -> None:
    """Check `target` sits on a device that exists, and that it is `device_id`."""
    rows = [row for row in registry if row["entity_id"] == target]
    if not rows:
        raise HarnessFailure(f"{target} is not in the entity registry")
    if (target_device := rows[0]["device_id"]) is None:
        raise HarnessFailure(f"{target} sits on no device, but this test needs one")
    devices = await socket.call("config/device_registry/list")
    if not any(device["id"] == target_device for device in devices):
        raise HarnessFailure(
            f"{target} sits on device {target_device}, which is missing"
        )
    if target_device != device_id:
        raise HarnessFailure(
            f"The timer sits on device {device_id}, not on that of {target}, "
            f"{target_device}"
        )


async def add_interval(
    session: aiohttp.ClientSession,
    instance: Instance,
    access_token: str,
    timer: Timer,
    *,
    weekday: str,
    start: datetime,
    end: datetime,
) -> str:
    """Add an interval of `weekday` from `start` to `end` to the timer the way its page
    does, through the interval flow; returns the title Timerify gave it.

    The times are the wall clock of Home Assistant, which the form takes as `HH:MM:SS`.
    """
    flow_path = "/api/config/config_entries/subentries/flow"
    flow = await request_json(
        session,
        instance,
        "POST",
        flow_path,
        access_token,
        json={"handler": [timer.entry_id, "interval"]},
    )
    if flow["type"] != "form" or flow["step_id"] != "user":
        raise HarnessFailure(f"The flow should ask for the interval, but gave {flow}")
    flow = await request_json(
        session,
        instance,
        "POST",
        f"{flow_path}/{flow['flow_id']}",
        access_token,
        json={
            "days": "weekdays",
            "weekdays": [weekday],
            "start": f"{start:%H:%M}:00",
            "end": f"{end:%H:%M}:00",
        },
    )
    if flow["type"] != "create_entry":
        raise HarnessFailure(f"The flow should create the interval, but gave {flow}")
    return str(flow["title"])


def _the_only[Row](found: Iterable[Row], what: str) -> Row:
    """The one row of `found`; none or several is a failure that says what was found."""
    rows = list(found)
    if len(rows) != 1:
        raise HarnessFailure(f"Expected one {what}, found {len(rows)}: {rows}")
    return rows[0]


def _is_schedule_switch_of(title: str) -> EntityMatcher:
    """Match the state `on` of the switch of the interval that is called `title`."""
    return lambda entity_id, state: (
        entity_id.startswith("switch.")
        and state["state"] == "on"
        and state["attributes"].get("friendly_name", "").endswith(f"Schedule {title}")
    )


async def find_interval_switch(socket: Socket, timer: Timer, title: str) -> State:
    """Wait for the switch of the interval of `timer` that is called `title` to be on;
    return its row of the entity registry, which names it and the device it sits on."""
    await socket.wait_for_entity(
        _is_schedule_switch_of(title), "the switch of the interval, on", CALL_TIMEOUT
    )
    subentries = await socket.call(
        "config_entries/subentries/list", entry_id=timer.entry_id
    )
    subentry = _the_only(
        (row for row in subentries if row["title"] == title),
        f"subentry titled {title!r}",
    )
    registry = await socket.call("config/entity_registry/list")
    unique_id = f"{timer.entry_id}_interval_{subentry['subentry_id']}"
    return _the_only(
        (row for row in registry if row["unique_id"] == unique_id),
        f"entity with the unique id {unique_id}",
    )
