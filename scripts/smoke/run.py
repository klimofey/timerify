"""Smoke test: Timerify in a real Home Assistant container.

Starts Home Assistant from compose.yaml with a fresh configuration, onboards it through
its HTTP API, adds Timerify timers through the config flow for the entities that
configuration.yaml declares or the demo integration provides, and then checks what a
user would see:

1. "Run for" 2 minutes on a switch that sits on no device (an input_boolean): the switch
   turns on, and turns off when the countdown ends.
2. A pending command on the switch of the demo integration, which sits on a device: the
   timer's entities sit on that device, and a command to turn on in 1 minute for
   1 minute turns the switch on at its time, clears the "Next command" sensor, and
   turns the switch off one minute later.
3. "Run for" 1 minute with a mode and a temperature on a generic thermostat: it is set
   to heat and 23 degrees, and turned off when the countdown ends.
4. A schedule interval for today's weekday, added to the first timer through the
   interval flow to begin in a minute or two and run for two minutes: its switch is on,
   and the first switch turns on at the start and off at the end.
5. "Run for" 3 minutes on the first switch, then the container restarts: the countdown
   carries on and the switch turns off at the end it had before the restart.

Everything is observed over the WebSocket API by subscribing to state changes.

    uv run python scripts/smoke/run.py [--keep]

`--keep` leaves Home Assistant running, with a countdown on, to look at in a browser.
"""

import argparse
import asyncio
import contextlib
import sys
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

COMPOSE_FILE = Path(__file__).parent / "compose.yaml"
BASE_URL = "http://localhost:18123"
CLIENT_ID = f"{BASE_URL}/"
REDIRECT_URI = f"{BASE_URL}/?auth_callback=1"

USERNAME = "smoke"
PASSWORD = "smoke-test-password"
SWITCH = "input_boolean.smoke_boiler"
"""The switch the first timer runs; configuration.yaml declares it, on no device."""
DEMO_SWITCH = "switch.decorative_lights"
"""A switch of the demo integration, which sits on a device of its own."""
THERMOSTAT = "climate.smoke_thermostat"
"""A generic thermostat that configuration.yaml declares, over template entities."""
THERMOSTAT_TEMPERATURE = 23
DOMAIN = "timerify"
KEEP_MINUTES = 60

STARTUP_TIMEOUT = 240.0
CALL_TIMEOUT = 30.0
TURN_ON_TIMEOUT = 15.0
COMMAND_DELAY = timedelta(minutes=1)
"""How far ahead the pending command of the demo switch is set."""
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
"""The names the interval form gives the days of the week, Monday first."""
INTERVAL_LENGTH = timedelta(minutes=2)
"""How long the schedule interval runs the first switch."""
START_SLACK = timedelta(seconds=5)
"""How far the end of a countdown may be from `minutes` after the switch turned on."""
EXPIRY_SLACK = timedelta(seconds=5)
"""How late after the end of a countdown the switch may turn off."""
CLOCK_TOLERANCE = timedelta(seconds=1)

type State = dict[str, Any]
type Matcher = Callable[[State | None], bool]
type EntityMatcher = Callable[[str, State], bool]


class SmokeFailure(Exception):
    """The smoke test found something that is not as a user would expect."""


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


def heating_to(temperature: float) -> Matcher:
    """Match a thermostat that is in heat mode with `temperature` as its target."""
    return lambda state: (
        state is not None
        and state["state"] == "heat"
        and state["attributes"].get("temperature") == temperature
    )


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
                raise SmokeFailure(
                    f"{what}: the WebSocket closed while waiting for {expected}"
                )
            return state

        try:
            return await asyncio.wait_for(satisfied(), seconds)
        except TimeoutError:
            found_now = f", it is {current()}" if current else ""
            raise SmokeFailure(
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
    session: aiohttp.ClientSession,
    socket: Socket,
    access_token: str,
    target: str,
    *,
    on_target_device: bool = False,
) -> Timer:
    """Add a timer for `target` in Timerify the way the integrations page does.

    With `on_target_device` the target must sit on a device, and the timer's entities
    must sit on that same device.
    """
    flow_path = "/api/config/config_entries/flow"
    flow = await request_json(
        session, "POST", flow_path, access_token, json={"handler": DOMAIN}
    )
    if flow["type"] != "menu" or "target" not in flow["menu_options"]:
        raise SmokeFailure(f"The flow should offer to add a timer, but gave {flow}")
    flow = await request_json(
        session,
        "POST",
        f"{flow_path}/{flow['flow_id']}",
        access_token,
        json={"next_step_id": "target"},
    )
    for step_id, user_input in (
        ("target", {"target": target, "mode": "strict"}),
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
    if flow["type"] == "form" and flow["step_id"] == "workday":
        # Asked only in a house that has a Workday sensor, and optional.
        flow = await request_json(
            session, "POST", f"{flow_path}/{flow['flow_id']}", access_token, json={}
        )
    if flow["type"] != "create_entry":
        raise SmokeFailure(f"The flow should create the timer, but gave {flow}")
    entry_id = flow["result"]["entry_id"]
    registry = await socket.call("config/entity_registry/list")
    rows = {row["unique_id"]: row for row in registry if row["platform"] == DOMAIN}
    try:
        run_for = rows[f"{entry_id}_run_for"]
        ends_at = rows[f"{entry_id}_ends_at"]
        next_command = rows[f"{entry_id}_next_command"]
    except KeyError as missing:
        raise SmokeFailure(f"The timer has no entity {missing}: {list(rows)}") from None
    device_ids = {row["device_id"] for row in (run_for, ends_at, next_command)}
    if len(device_ids) != 1 or None in device_ids:
        raise SmokeFailure(
            "The timer's entities should share one device, "
            f"but are on {sorted(map(str, device_ids))}"
        )
    (device_id,) = device_ids
    if on_target_device:
        await expect_on_device_of(socket, registry, target, device_id)
    return Timer(
        entry_id,
        target,
        run_for["entity_id"],
        ends_at["entity_id"],
        next_command["entity_id"],
        device_id,
    )


async def expect_on_device_of(
    socket: Socket, registry: list[State], target: str, device_id: str
) -> None:
    """Check `target` sits on a device that exists, and that it is `device_id`."""
    rows = [row for row in registry if row["entity_id"] == target]
    if not rows:
        raise SmokeFailure(f"{target} is not in the entity registry")
    if (target_device := rows[0]["device_id"]) is None:
        raise SmokeFailure(f"{target} sits on no device, but this test needs one")
    devices = await socket.call("config/device_registry/list")
    if not any(device["id"] == target_device for device in devices):
        raise SmokeFailure(f"{target} sits on device {target_device}, which is missing")
    if target_device != device_id:
        raise SmokeFailure(
            f"The timer sits on device {device_id}, not on that of {target}, "
            f"{target_device}"
        )


async def expect_started(
    socket: Socket,
    timer: Timer,
    minutes: int,
    *,
    is_on: Matcher | None = None,
    expected: str = "on",
    wait: float = TURN_ON_TIMEOUT,
) -> tuple[State, datetime]:
    """Check the target is on within `wait` seconds and the end is `minutes` away.

    `is_on` says what "on" is for this target; the default is the state `on`. Returns
    the state of the target as it turned on and the end of the countdown, as "Ends at"
    reports it.
    """
    on = await socket.wait_for_state(
        timer.target, is_on or has_state("on"), expected, wait
    )
    ends_at = await socket.wait_for_state(
        timer.ends_at, is_known, "a time", TURN_ON_TIMEOUT
    )
    await socket.wait_for_state(
        timer.run_for, has_minutes(minutes), str(minutes), TURN_ON_TIMEOUT
    )
    end = timestamp(ends_at["state"])
    away = end - timestamp(on["last_changed"])
    if abs(away - timedelta(minutes=minutes)) > START_SLACK:
        raise SmokeFailure(f"The end is {away} after {timer.target} turned on")
    say(f"  {timer.target} {expected}, ends at {end:%H:%M:%S}")
    return on, end


async def start_countdown(socket: Socket, timer: Timer, minutes: int) -> datetime:
    """Set "Run for" and check the target turns on and the end is `minutes` away."""
    await socket.call(
        "call_service",
        domain="number",
        service="set_value",
        service_data={"value": minutes},
        target={"entity_id": timer.run_for},
    )
    return (await expect_started(socket, timer, minutes))[1]


async def expect_off_at(socket: Socket, timer: Timer, end: datetime) -> None:
    """Check the target turns off at `end`, and the timer is idle after that."""
    wait = (end - datetime.now(UTC)).total_seconds() + 60
    off = await socket.wait_for_state(timer.target, has_state("off"), "off", wait)
    stopped = timestamp(off["last_changed"])
    if not end - CLOCK_TOLERANCE <= stopped <= end + EXPIRY_SLACK:
        raise SmokeFailure(f"{timer.target} turned off at {stopped}, not at {end}")
    await socket.wait_for_state(timer.run_for, has_minutes(0), "0", CALL_TIMEOUT)
    await socket.wait_for_state(
        timer.ends_at, has_state("unknown"), "unknown", CALL_TIMEOUT
    )
    say(f"  {timer.target} off {(stopped - end).total_seconds():+.1f}s from the end")


async def scenario_expiry(
    session: aiohttp.ClientSession, refresh_token: str, timer: Timer
) -> None:
    say("Run for 2 minutes, wait for the switch to turn off")
    async with open_socket(session, refresh_token) as socket:
        end = await start_countdown(socket, timer, 2)
        await expect_off_at(socket, timer, end)


async def scenario_command(session: aiohttp.ClientSession, refresh_token: str) -> None:
    say(f"Add a command for {DEMO_SWITCH}: on in 1 minute, for 1 minute")
    async with open_socket(session, refresh_token) as socket:
        await socket.wait_for_state(
            DEMO_SWITCH, is_known, "the demo switch", STARTUP_TIMEOUT
        )
        # The demo switch starts on, and a strict timer would count down from the
        # moment it is added. Switch it off first, so the timer starts idle.
        await socket.call(
            "call_service",
            domain="switch",
            service="turn_off",
            target={"entity_id": DEMO_SWITCH},
        )
        await socket.wait_for_state(DEMO_SWITCH, has_state("off"), "off", CALL_TIMEOUT)
        timer = await add_timer(
            session,
            socket,
            await new_access_token(session, refresh_token),
            DEMO_SWITCH,
            on_target_device=True,
        )
        say(f"  timer on the device of {DEMO_SWITCH}")
        await socket.wait_for_state(timer.run_for, has_minutes(0), "0", CALL_TIMEOUT)

        asked = datetime.now(UTC)
        result = await socket.call(
            "call_service",
            domain=DOMAIN,
            service="add_command",
            service_data={
                "action": "on",
                "delay": int(COMMAND_DELAY.total_seconds() // 60),
                "minutes": 1,
            },
            target={"entity_id": timer.run_for},
            return_response=True,
        )
        try:
            command_id = result["response"][timer.run_for]["command_id"]
        except KeyError, TypeError:
            raise SmokeFailure(f"add_command gave no command id: {result}") from None
        pending = await socket.wait_for_state(
            timer.next_command, is_known, "the time of the command", CALL_TIMEOUT
        )
        commands = pending["attributes"].get("commands")
        if not isinstance(commands, list) or [c.get("id") for c in commands] != [
            command_id
        ]:
            raise SmokeFailure(f"The Next command sensor lists {commands}")
        due = timestamp(pending["state"])
        # The state of a timestamp sensor is cut to whole seconds, the attribute is not.
        if abs(timestamp(commands[0]["at"]) - due) > CLOCK_TOLERANCE:
            raise SmokeFailure(
                f"The sensor says {due}, its command {commands[0]['at']}"
            )
        if abs(due - (asked + COMMAND_DELAY)) > START_SLACK:
            raise SmokeFailure(f"The command is due at {due}, asked at {asked}")
        say(f"  command due at {due:%H:%M:%S}")

        wait = (due - datetime.now(UTC)).total_seconds() + TURN_ON_TIMEOUT
        on, end = await expect_started(socket, timer, 1, wait=wait)
        started = timestamp(on["last_changed"])
        if (
            not due - CLOCK_TOLERANCE
            <= started
            <= due + timedelta(seconds=TURN_ON_TIMEOUT)
        ):
            raise SmokeFailure(f"{DEMO_SWITCH} turned on at {started}, not at {due}")
        await socket.wait_for_state(
            timer.next_command, has_state("unknown"), "unknown", CALL_TIMEOUT
        )
        await expect_off_at(socket, timer, end)


async def scenario_settings(session: aiohttp.ClientSession, refresh_token: str) -> None:
    say(f"Run {THERMOSTAT} for 1 minute: heat, {THERMOSTAT_TEMPERATURE} degrees")
    async with open_socket(session, refresh_token) as socket:
        await socket.wait_for_state(
            THERMOSTAT, has_state("off"), "off", STARTUP_TIMEOUT
        )
        timer = await add_timer(
            session,
            socket,
            await new_access_token(session, refresh_token),
            THERMOSTAT,
        )
        await socket.call(
            "call_service",
            domain=DOMAIN,
            service="run",
            service_data={
                "minutes": 1,
                "hvac_mode": "heat",
                "temperature": THERMOSTAT_TEMPERATURE,
            },
            target={"entity_id": timer.run_for},
        )
        _, end = await expect_started(
            socket,
            timer,
            1,
            is_on=heating_to(THERMOSTAT_TEMPERATURE),
            expected=f"heat at {THERMOSTAT_TEMPERATURE}",
        )
        await expect_off_at(socket, timer, end)


def the_only[Row](found: Iterable[Row], what: str) -> Row:
    """The one row of `found`; none or several is a failure that says what was found."""
    rows = list(found)
    if len(rows) != 1:
        raise SmokeFailure(f"Expected one {what}, found {len(rows)}: {rows}")
    return rows[0]


def is_schedule_switch_of(title: str) -> EntityMatcher:
    """Match the state `on` of the switch of the interval that is called `title`."""
    return lambda entity_id, state: (
        entity_id.startswith("switch.")
        and state["state"] == "on"
        and state["attributes"].get("friendly_name", "").endswith(f"Schedule {title}")
    )


async def add_interval(
    session: aiohttp.ClientSession,
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
        "POST",
        flow_path,
        access_token,
        json={"handler": [timer.entry_id, "interval"]},
    )
    if flow["type"] != "form" or flow["step_id"] != "user":
        raise SmokeFailure(f"The flow should ask for the interval, but gave {flow}")
    flow = await request_json(
        session,
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
        raise SmokeFailure(f"The flow should create the interval, but gave {flow}")
    return str(flow["title"])


async def scenario_schedule(
    session: aiohttp.ClientSession, refresh_token: str, timer: Timer
) -> None:
    say(f"Add an interval for {timer.target}: today, two minutes long, in a minute")
    async with open_socket(session, refresh_token) as socket:
        zone = ZoneInfo((await socket.call("get_config"))["time_zone"])
        # The next whole minute, plus one: the form and the reload that follows it take
        # a few seconds, and the interval must not have begun when they are done.
        start = datetime.now(zone).replace(second=0, microsecond=0) + timedelta(
            minutes=2
        )
        end = start + INTERVAL_LENGTH
        title = await add_interval(
            session,
            await new_access_token(session, refresh_token),
            timer,
            weekday=WEEKDAYS[start.weekday()],
            start=start,
            end=end,
        )
        say(f"  interval {title}, in the time zone {zone.key}")

        await socket.wait_for_entity(
            is_schedule_switch_of(title), "the switch of the interval, on", CALL_TIMEOUT
        )
        subentries = await socket.call(
            "config_entries/subentries/list", entry_id=timer.entry_id
        )
        subentry = the_only(
            (row for row in subentries if row["title"] == title),
            f"subentry titled {title!r}",
        )
        registry = await socket.call("config/entity_registry/list")
        unique_id = f"{timer.entry_id}_interval_{subentry['subentry_id']}"
        row = the_only(
            (row for row in registry if row["unique_id"] == unique_id),
            f"entity with the unique id {unique_id}",
        )
        if row["device_id"] != timer.device_id:
            raise SmokeFailure(
                f"The switch of the interval sits on device {row['device_id']}, "
                f"not on that of the timer, {timer.device_id}"
            )
        say(f"  {row['entity_id']} on, on the device of the timer")

        wait = (start - datetime.now(UTC)).total_seconds() + TURN_ON_TIMEOUT
        on, ends_at = await expect_started(
            socket, timer, int(INTERVAL_LENGTH.total_seconds() // 60), wait=wait
        )
        started = timestamp(on["last_changed"])
        if not start - CLOCK_TOLERANCE <= started <= start + START_SLACK:
            raise SmokeFailure(f"{timer.target} turned on at {started}, not at {start}")
        if abs(ends_at - end) > CLOCK_TOLERANCE:
            raise SmokeFailure(f"The interval ends at {end}, the timer at {ends_at}")
        await expect_off_at(socket, timer, end)
        await socket.wait_for_state(
            row["entity_id"], has_state("on"), "on, the interval is still enabled", 1
        )
        say(f"  {row['entity_id']} still on: the interval waits for next week")


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
        await socket.wait_for_state(timer.target, has_state("on"), "on", CALL_TIMEOUT)
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
            session,
            socket,
            await new_access_token(session, refresh_token),
            SWITCH,
        )
    say(f"Added a timer for {SWITCH}")
    await scenario_expiry(session, refresh_token, timer)
    await scenario_command(session, refresh_token)
    await scenario_settings(session, refresh_token)
    await scenario_schedule(session, refresh_token, timer)
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
