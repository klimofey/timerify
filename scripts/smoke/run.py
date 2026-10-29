"""Smoke test: Timerify in a real Home Assistant container.

Starts Home Assistant from compose.yaml with a fresh configuration, onboards it through
its HTTP API, adds a Timerify timer for the switch that configuration.yaml declares (an
input_boolean) through the config flow, and then checks what a user would see:

1. "Run for" 2 minutes: the switch turns on, and turns off when the countdown ends.
2. "Run for" 3 minutes, then the container restarts: the countdown carries on and the
   switch turns off at the end it had before the restart.

Everything is observed over the WebSocket API by subscribing to state changes.

    uv run python scripts/smoke/run.py [--keep]

`--keep` leaves Home Assistant running, with a countdown on, to look at in a browser.
"""

import argparse
import asyncio
import contextlib
import sys
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any

import aiohttp

COMPOSE_FILE = Path(__file__).parent / "compose.yaml"
BASE_URL = "http://localhost:18123"
CLIENT_ID = f"{BASE_URL}/"
REDIRECT_URI = f"{BASE_URL}/?auth_callback=1"

USERNAME = "smoke"
PASSWORD = "smoke-test-password"
SWITCH = "input_boolean.smoke_boiler"
"""The switch the timer runs; configuration.yaml declares it."""
DOMAIN = "timerify"
KEEP_MINUTES = 60

STARTUP_TIMEOUT = 240.0
CALL_TIMEOUT = 30.0
TURN_ON_TIMEOUT = 15.0
START_SLACK = timedelta(seconds=5)
"""How far the end of a countdown may be from `minutes` after the switch turned on."""
EXPIRY_SLACK = timedelta(seconds=5)
"""How late after the end of a countdown the switch may turn off."""
CLOCK_TOLERANCE = timedelta(seconds=1)

type State = dict[str, Any]
type Matcher = Callable[[State | None], bool]


class SmokeFailure(Exception):
    """The smoke test found something that is not as a user would expect."""


@dataclass(frozen=True)
class Timer:
    """The entities of the timer under test."""

    entry_id: str
    run_for: str
    ends_at: str
    device_id: str
    """The device the entities sit on, from the entity registry."""


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


async def compose(*arguments: str) -> None:
    """Run `docker compose` on the smoke test's compose file."""
    command = ["docker", "compose", "--file", str(COMPOSE_FILE), *arguments]
    process = await asyncio.create_subprocess_exec(*command)
    if await process.wait() != 0:
        raise SmokeFailure(f"`{' '.join(command)}` failed")


async def request_json(
    session: aiohttp.ClientSession,
    method: str,
    path: str,
    access_token: str | None = None,
    **options: Any,
) -> Any:
    """Call Home Assistant's HTTP API and return the JSON it answers with."""
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
    async with session.request(
        method, f"{BASE_URL}{path}", headers=headers, **options
    ) as response:
        body = await response.text()
        if response.status >= 400:
            raise SmokeFailure(f"{method} {path} answered {response.status}: {body}")
        return await response.json(content_type=None)


async def wait_until_up(session: aiohttp.ClientSession) -> None:
    """Wait for the API of Home Assistant to answer; with no token, it says 401."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + STARTUP_TIMEOUT
    while True:
        try:
            async with session.get(
                f"{BASE_URL}/api/", timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == HTTPStatus.UNAUTHORIZED:
                    return
        except aiohttp.ClientError, TimeoutError:
            pass
        if loop.time() > deadline:
            raise SmokeFailure(
                f"Home Assistant did not answer within {STARTUP_TIMEOUT:.0f}s"
            )
        await asyncio.sleep(2)


async def onboard(session: aiohttp.ClientSession) -> str:
    """Take Home Assistant through onboarding; return the user's refresh token."""
    user = await request_json(
        session,
        "POST",
        "/api/onboarding/users",
        json={
            "client_id": CLIENT_ID,
            "name": "Smoke test",
            "username": USERNAME,
            "password": PASSWORD,
            "language": "en",
        },
    )
    tokens = await request_json(
        session,
        "POST",
        "/auth/token",
        data={
            "grant_type": "authorization_code",
            "code": user["auth_code"],
            "client_id": CLIENT_ID,
        },
    )
    access_token = tokens["access_token"]
    for step in ("core_config", "analytics"):
        await request_json(
            session, "POST", f"/api/onboarding/{step}", access_token, json={}
        )
    await request_json(
        session,
        "POST",
        "/api/onboarding/integration",
        access_token,
        json={"client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI},
    )
    return str(tokens["refresh_token"])


async def new_access_token(session: aiohttp.ClientSession, refresh_token: str) -> str:
    """Exchange the refresh token for an access token."""
    tokens = await request_json(
        session,
        "POST",
        "/auth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
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
            raise SmokeFailure(f"{command}: the WebSocket is closed")
        message_id = self._next_id
        self._next_id += 1
        future = asyncio.get_running_loop().create_future()
        self._pending[message_id] = future
        try:
            await self._ws.send_json({"id": message_id, "type": command, **fields})
            return await asyncio.wait_for(future, CALL_TIMEOUT)
        except TimeoutError:
            raise SmokeFailure(f"{command} got no answer in {CALL_TIMEOUT}s") from None
        except ConnectionError as err:
            raise SmokeFailure(f"{command}: the WebSocket broke: {err}") from err
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

        async def satisfied() -> State:
            async with self._changed:
                await self._changed.wait_for(
                    lambda: self._closed or matches(self._states.get(entity_id))
                )
            if not matches(self._states.get(entity_id)):
                raise SmokeFailure(
                    f"{entity_id}: the WebSocket closed while waiting for {expected}"
                )
            return self._states[entity_id]

        try:
            return await asyncio.wait_for(satisfied(), seconds)
        except TimeoutError:
            current = self._states.get(entity_id)
            raise SmokeFailure(
                f"{entity_id}: expected {expected} within {seconds:.0f}s, "
                f"it is {current['state'] if current else 'missing'}"
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
                    future.set_exception(SmokeFailure("The WebSocket closed"))
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
                    future.set_exception(SmokeFailure(message["error"]["message"]))
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
    session: aiohttp.ClientSession, refresh_token: str
) -> AsyncIterator[Socket]:
    """Connect as the test user and follow the states until the block ends."""
    ws = await session.ws_connect(f"{BASE_URL}/api/websocket")
    await ws.receive_json()  # auth_required
    await ws.send_json(
        {
            "type": "auth",
            "access_token": await new_access_token(session, refresh_token),
        }
    )
    reply = await ws.receive_json()
    if reply["type"] != "auth_ok":
        raise SmokeFailure(f"The WebSocket refused the token: {reply}")
    socket = Socket(ws)
    try:
        await socket.watch_states()
        yield socket
    finally:
        await socket.close()


async def add_timer(
    session: aiohttp.ClientSession, socket: Socket, access_token: str
) -> Timer:
    """Add the switch in Timerify the way the integrations page does."""
    flow_path = "/api/config/config_entries/flow"
    flow = await request_json(
        session, "POST", flow_path, access_token, json={"handler": DOMAIN}
    )
    for step_id, user_input in (
        ("user", {"target": SWITCH, "mode": "strict"}),
        ("duration", {"default_duration": 30}),
    ):
        if flow["type"] != "form" or flow["step_id"] != step_id:
            raise SmokeFailure(f"The flow should ask for {step_id!r}, but gave {flow}")
        flow = await request_json(
            session,
            "POST",
            f"{flow_path}/{flow['flow_id']}",
            access_token,
            json=user_input,
        )
    if flow["type"] != "create_entry":
        raise SmokeFailure(f"The flow should create the timer, but gave {flow}")
    entry_id = flow["result"]["entry_id"]
    registry = await socket.call("config/entity_registry/list")
    rows = {row["unique_id"]: row for row in registry if row["platform"] == DOMAIN}
    try:
        run_for, ends_at = rows[f"{entry_id}_run_for"], rows[f"{entry_id}_ends_at"]
    except KeyError as missing:
        raise SmokeFailure(f"The timer has no entity {missing}: {list(rows)}") from None
    if not (device_id := run_for["device_id"]) or ends_at["device_id"] != device_id:
        raise SmokeFailure(
            "The timer's entities should share one device, "
            f"but are on {run_for['device_id']} and {ends_at['device_id']}"
        )
    return Timer(entry_id, run_for["entity_id"], ends_at["entity_id"], device_id)


async def start_countdown(socket: Socket, timer: Timer, minutes: int) -> datetime:
    """Set "Run for" and check the switch turns on and the end is `minutes` away.

    Returns the end of the countdown, as "Ends at" reports it.
    """
    await socket.call(
        "call_service",
        domain="number",
        service="set_value",
        service_data={"value": minutes},
        target={"entity_id": timer.run_for},
    )
    on = await socket.wait_for_state(SWITCH, has_state("on"), "on", TURN_ON_TIMEOUT)
    ends_at = await socket.wait_for_state(
        timer.ends_at, is_known, "a time", TURN_ON_TIMEOUT
    )
    await socket.wait_for_state(
        timer.run_for, has_minutes(minutes), str(minutes), TURN_ON_TIMEOUT
    )
    end = timestamp(ends_at["state"])
    away = end - timestamp(on["last_changed"])
    if abs(away - timedelta(minutes=minutes)) > START_SLACK:
        raise SmokeFailure(f"The end is {away} after the switch turned on")
    say(f"  {SWITCH} on, ends at {end:%H:%M:%S}")
    return end


async def expect_off_at(socket: Socket, timer: Timer, end: datetime) -> None:
    """Check the switch turns off at `end`, and the timer is idle after that."""
    wait = (end - datetime.now(UTC)).total_seconds() + 60
    off = await socket.wait_for_state(SWITCH, has_state("off"), "off", wait)
    stopped = timestamp(off["last_changed"])
    if not end - CLOCK_TOLERANCE <= stopped <= end + EXPIRY_SLACK:
        raise SmokeFailure(f"The switch turned off at {stopped}, not at {end}")
    await socket.wait_for_state(timer.run_for, has_minutes(0), "0", CALL_TIMEOUT)
    await socket.wait_for_state(
        timer.ends_at, has_state("unknown"), "unknown", CALL_TIMEOUT
    )
    say(f"  {SWITCH} off {(stopped - end).total_seconds():+.1f}s from the end")


async def scenario_expiry(
    session: aiohttp.ClientSession, refresh_token: str, timer: Timer
) -> None:
    say("Run for 2 minutes, wait for the switch to turn off")
    async with open_socket(session, refresh_token) as socket:
        end = await start_countdown(socket, timer, 2)
        await expect_off_at(socket, timer, end)


async def scenario_restart(
    session: aiohttp.ClientSession, refresh_token: str, timer: Timer
) -> None:
    say("Run for 3 minutes, restart Home Assistant, wait for the switch to turn off")
    async with open_socket(session, refresh_token) as socket:
        end = await start_countdown(socket, timer, 3)
    say("  restarting Home Assistant")
    await compose("restart", "--timeout", "60", "homeassistant")
    await wait_until_up(session)
    async with open_socket(session, refresh_token) as socket:
        ends_at = await socket.wait_for_state(
            timer.ends_at, is_known, "the countdown, kept", STARTUP_TIMEOUT
        )
        if (kept := timestamp(ends_at["state"])) != end:
            raise SmokeFailure(f"The countdown ended at {end}, now at {kept}")
        if datetime.now(UTC) > end - EXPIRY_SLACK:
            raise SmokeFailure("Home Assistant came back too late to test the restart")
        await socket.wait_for_state(SWITCH, has_state("on"), "on", CALL_TIMEOUT)
        say("  back up, countdown kept")
        await expect_off_at(socket, timer, end)


async def leave_running(
    session: aiohttp.ClientSession, refresh_token: str, timer: Timer
) -> None:
    """Start a long countdown and say where to look at it."""
    async with open_socket(session, refresh_token) as socket:
        await start_countdown(socket, timer, KEEP_MINUTES)
    say(f"Left running: {BASE_URL}/config/devices/device/{timer.device_id}")
    say(f"Log in as {USERNAME!r} with password {PASSWORD!r}.")


async def run(session: aiohttp.ClientSession, keep: bool) -> None:
    await wait_until_up(session)
    refresh_token = await onboard(session)
    async with open_socket(session, refresh_token) as socket:
        await socket.wait_for_state(SWITCH, has_state("off"), "off", CALL_TIMEOUT)
        timer = await add_timer(
            session, socket, await new_access_token(session, refresh_token)
        )
    say(f"Added a timer for {SWITCH}")
    await scenario_expiry(session, refresh_token, timer)
    await scenario_restart(session, refresh_token, timer)
    if keep:
        await leave_running(session, refresh_token, timer)


async def main(keep: bool) -> int:
    await compose("down", "--remove-orphans")
    await compose("run", "--rm", "wipe")
    try:
        await compose("up", "--detach", "homeassistant")
        async with aiohttp.ClientSession() as session:
            await run(session, keep)
    except SmokeFailure as failure:
        say(f"FAILED: {failure}")
        try:
            await compose("logs", "--tail", "80", "homeassistant")
        except SmokeFailure as logs_failure:
            # The failure above is the one to fix; this only says the logs are lost.
            say(f"(the logs of Home Assistant could not be read: {logs_failure})")
        return 1
    finally:
        if not keep:
            await compose("down")
    say("PASSED")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Smoke test of Timerify in a real Home Assistant container."
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="leave Home Assistant running afterwards, with a countdown on",
    )
    sys.exit(asyncio.run(main(parser.parse_args().keep)))
