"""Smoke test: Timerify in a real Home Assistant container.

Starts Home Assistant from scripts/harness/compose.yaml with a fresh configuration (the
harness, scripts/harness/hass.py, does that and the rest of the plumbing), onboards it
through its HTTP API, adds Timerify timers through the config flow for the entities that
configuration.yaml declares or the demo integration provides, and then checks what a
user would see:

1. The dashboard card: the page Home Assistant serves to the browser loads the card's
   module, at the address that carries the version of the bundle in this checkout; that
   address serves the bundle byte for byte; and the card's websocket command tells the
   first timer's entry and entities.
2. "Run for" 2 minutes on a switch that sits on no device (an input_boolean): the switch
   turns on, and turns off when the countdown ends. This timer was added with the
   runtime counter ticked, and its Runtime sensor then shows the 2 minutes, in minutes,
   as a total that only goes up (it publishes at the end of every minute, so this waits
   for the minute to end).
3. A pending command on the switch of the demo integration, which sits on a device: the
   timer's entities sit on that device, and a command to turn on in 1 minute for
   1 minute turns the switch on at its time, clears the "Next command" sensor, and
   turns the switch off one minute later.
4. "Run for" 1 minute with a mode and a temperature on a generic thermostat: it is set
   to heat and 23 degrees, and turned off when the countdown ends.
5. A schedule interval for today's weekday, added to the first timer through the
   interval flow to begin in a minute or two and run for two minutes: its switch is on,
   and the first switch turns on at the start and off at the end.
6. Voice: the Voice settings are added through the menu of the config flow, and the
   built-in agent is talked to over the REST API about the first switch. Asked how long
   is left on it, the agent refuses (an input boolean is not exposed to Assist by
   default); once it is exposed, "turn on ... for 2 minutes" runs it and the agent
   says how long is left, "turn off ... in 1 minute" ends it a minute later, a bare
   "turn on ..." runs it for the default 30 minutes and a bare "turn off ..." stops it.
7. "Run for" 3 minutes on the first switch, then the container restarts: the countdown
   carries on and the switch turns off at the end it had before the restart.

Everything is observed over the WebSocket API by subscribing to state changes.

    uv run python -m scripts.smoke.run [--keep]

`--keep` leaves Home Assistant running, with a countdown on, to look at in a browser.
"""

import argparse
import asyncio
import hashlib
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp

from scripts.harness.hass import (
    CALL_TIMEOUT,
    DEFAULT_DURATION_MINUTES,
    DEMO_SWITCH,
    DOMAIN,
    STARTUP_TIMEOUT,
    SWITCH,
    WEEKDAYS,
    HarnessFailure,
    Instance,
    Matcher,
    Socket,
    State,
    Timer,
    add_interval,
    add_timer,
    find_interval_switch,
    has_minutes,
    has_state,
    is_known,
    new_access_token,
    onboard,
    open_socket,
    request_bytes,
    request_json,
    say,
    timestamp,
    wait_until_up,
)

INSTANCE = Instance("timerify-smoke", 18123, Path(__file__).parent / "config")
"""The container of the smoke test, beside the one of the end-to-end tests."""

USERNAME = "smoke"
PASSWORD = "smoke-test-password"
THERMOSTAT = "climate.smoke_thermostat"
"""A generic thermostat that configuration.yaml declares, over template entities."""
THERMOSTAT_TEMPERATURE = 23
SWITCH_NAME = "Smoke boiler"
"""How Assist calls the first switch: its name as configuration.yaml gives it."""
KEEP_MINUTES = 60
CARD_BUNDLE = (
    Path(__file__).parents[2]
    / "custom_components"
    / "timerify"
    / "frontend"
    / "timerify-card.js"
)
"""The card's module as this checkout builds it, which the container has mounted."""
CARD_URL = "/timerify_frontend/timerify-card.js"
CARD_VERSION_LENGTH = 16
"""The hexadecimal digits of the bundle's SHA-256 that the address carries."""

TURN_ON_TIMEOUT = 15.0
COMMAND_DELAY = timedelta(minutes=1)
"""How far ahead the pending command of the demo switch is set."""
INTERVAL_LENGTH = timedelta(minutes=2)
"""How long the schedule interval runs the first switch."""
START_SLACK = timedelta(seconds=5)
"""How far the end of a countdown may be from `minutes` after the switch turned on."""
EXPIRY_SLACK = timedelta(seconds=5)
"""How late after the end of a countdown the switch may turn off."""
CLOCK_TOLERANCE = timedelta(seconds=1)
RUNTIME_PUBLISH_TIMEOUT = 90.0
"""How long after a run ends its minutes may take to reach the Runtime sensor: it
publishes once a minute, at the end of the minute, so a minute and a half is room
enough."""
RUNTIME_BELOW = 0.05
"""How many minutes short of the run the Runtime sensor may be when it first shows it:
the sensor rounds to hundredths of a minute, and the run starts a moment after "Run
for" is set."""
RUNTIME_ABOVE = 0.1
"""How many minutes beyond the run the Runtime sensor may show: the switch turns off a
moment after the countdown ends."""


class SmokeFailure(HarnessFailure):
    """The smoke test found something that is not as a user would expect."""


def heating_to(temperature: float) -> Matcher:
    """Match a thermostat that is in heat mode with `temperature` as its target."""
    return lambda state: (
        state is not None
        and state["state"] == "heat"
        and state["attributes"].get("temperature") == temperature
    )


def at_least(minimum: float) -> Matcher:
    """Match a numeric state of `minimum` or more."""

    def matches(state: State | None) -> bool:
        try:
            return state is not None and float(state["state"]) >= minimum
        except ValueError:
            return False

    return matches


def ends_near(moment: datetime) -> Matcher:
    """Match the "Ends at" sensor when it names a time within `START_SLACK` of
    `moment`."""
    return lambda state: (
        state is not None
        and is_known(state)
        and abs(timestamp(state["state"]) - moment) <= START_SLACK
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


async def expect_runtime(socket: Socket, timer: Timer, minutes: int) -> None:
    """Check the Runtime sensor of a timer whose only run, of `minutes`, has just ended:
    it reaches that many minutes and no more than a little over, in minutes, as a total
    that only goes up."""
    if timer.runtime is None:
        raise SmokeFailure(f"The timer of {timer.target} counts no runtime")
    shown = await socket.wait_for_state(
        timer.runtime,
        at_least(minutes - RUNTIME_BELOW),
        f"at least {minutes - RUNTIME_BELOW:g} minutes",
        RUNTIME_PUBLISH_TIMEOUT,
    )
    total = float(shown["state"])
    if total > minutes + RUNTIME_ABOVE:
        raise SmokeFailure(
            f"{timer.runtime} shows {total} minutes of a run of {minutes}"
        )
    attributes = shown["attributes"]
    if attributes.get("unit_of_measurement") != "min":
        raise SmokeFailure(
            f"{timer.runtime} is in {attributes.get('unit_of_measurement')}"
        )
    if attributes.get("state_class") != "total_increasing":
        raise SmokeFailure(f"{timer.runtime} is a {attributes.get('state_class')}")
    say(f"  {timer.runtime} shows {total:g} minutes (min, total_increasing)")


async def scenario_card(
    session: aiohttp.ClientSession, refresh_token: str, timer: Timer
) -> None:
    say("The dashboard card: loaded by the page, served as built, told its timer")
    bundle = CARD_BUNDLE.read_bytes()
    version = hashlib.sha256(bundle).hexdigest()[:CARD_VERSION_LENGTH]
    module = f"{CARD_URL}?v={version}"
    page = (await request_bytes(session, INSTANCE, "GET", "/")).decode()
    if f'import("{module}")' not in page:
        raise SmokeFailure(f"The page of Home Assistant should load {module}")
    say(f"  the page loads {module}")
    if await request_bytes(session, INSTANCE, "GET", module) != bundle:
        raise SmokeFailure(f"{module} should serve the bundle of this checkout")
    say(f"  {module} serves the {len(bundle)} bytes of the bundle")
    async with open_socket(session, INSTANCE, refresh_token) as socket:
        told = await socket.call("timerify/timer", entity_id=timer.run_for)
    expected = {
        "entry_id": timer.entry_id,
        "target": timer.target,
        "ends_at": timer.ends_at,
        "next_command": timer.next_command,
    }
    if (given := {key: told.get(key) for key in expected}) != expected:
        raise SmokeFailure(f"The card should be told {expected}, got {given}")
    say(f"  the card is told the timer of {timer.target}")


async def scenario_expiry(
    session: aiohttp.ClientSession, refresh_token: str, timer: Timer
) -> None:
    say("Run for 2 minutes, wait for the switch to turn off")
    async with open_socket(session, INSTANCE, refresh_token) as socket:
        end = await start_countdown(socket, timer, 2)
        await expect_off_at(socket, timer, end)
        await expect_runtime(socket, timer, 2)


async def scenario_command(session: aiohttp.ClientSession, refresh_token: str) -> None:
    say(f"Add a command for {DEMO_SWITCH}: on in 1 minute, for 1 minute")
    async with open_socket(session, INSTANCE, refresh_token) as socket:
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
            INSTANCE,
            await new_access_token(session, INSTANCE, refresh_token),
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
    async with open_socket(session, INSTANCE, refresh_token) as socket:
        await socket.wait_for_state(
            THERMOSTAT, has_state("off"), "off", STARTUP_TIMEOUT
        )
        timer = await add_timer(
            session,
            socket,
            INSTANCE,
            await new_access_token(session, INSTANCE, refresh_token),
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


async def scenario_schedule(
    session: aiohttp.ClientSession, refresh_token: str, timer: Timer
) -> None:
    say(f"Add an interval for {timer.target}: today, two minutes long, in a minute")
    async with open_socket(session, INSTANCE, refresh_token) as socket:
        zone = ZoneInfo((await socket.call("get_config"))["time_zone"])
        # The next whole minute, plus one: the form and the reload that follows it take
        # a few seconds, and the interval must not have begun when they are done.
        start = datetime.now(zone).replace(second=0, microsecond=0) + timedelta(
            minutes=2
        )
        end = start + INTERVAL_LENGTH
        title = await add_interval(
            session,
            INSTANCE,
            await new_access_token(session, INSTANCE, refresh_token),
            timer,
            weekday=WEEKDAYS[start.weekday()],
            start=start,
            end=end,
        )
        say(f"  interval {title}, in the time zone {zone.key}")

        row = await find_interval_switch(socket, timer, title)
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


@dataclass(frozen=True)
class Answer:
    """What the built-in agent answered to a sentence."""

    response_type: str
    """`action_done`, `query_answer` or `error`."""
    code: str | None
    """The error code of an `error`, else None."""
    speech: str


async def add_voice_settings(session: aiohttp.ClientSession, access_token: str) -> None:
    """Add the Voice settings the way the integrations page does: choose them in the
    menu of the flow and submit the form, with the sentences written in English."""
    flow_path = "/api/config/config_entries/flow"
    flow = await request_json(
        session, INSTANCE, "POST", flow_path, access_token, json={"handler": DOMAIN}
    )
    if flow["type"] != "menu" or "voice_settings" not in flow["menu_options"]:
        raise SmokeFailure(f"The flow should offer the voice settings, but gave {flow}")
    flow = await request_json(
        session,
        INSTANCE,
        "POST",
        f"{flow_path}/{flow['flow_id']}",
        access_token,
        json={"next_step_id": "voice_settings"},
    )
    if flow["type"] != "form" or flow["step_id"] != "voice_settings":
        raise SmokeFailure(f"The flow should ask for the voice settings, got {flow}")
    flow = await request_json(
        session,
        INSTANCE,
        "POST",
        f"{flow_path}/{flow['flow_id']}",
        access_token,
        json={"write_sentence_files": True, "languages": ["en"]},
    )
    if flow["type"] != "create_entry":
        raise SmokeFailure(f"The flow should create the voice settings, got {flow}")


async def converse(
    session: aiohttp.ClientSession, access_token: str, text: str
) -> Answer:
    """Say `text` to the built-in agent in English, over the REST API, and log what it
    answered."""
    result = await request_json(
        session,
        INSTANCE,
        "POST",
        "/api/conversation/process",
        access_token,
        json={"text": text, "language": "en"},
    )
    response = result["response"]
    answer = Answer(
        response["response_type"],
        response["data"].get("code"),
        response["speech"]["plain"]["speech"],
    )
    say(f"  {text!r} -> {answer.response_type}: {answer.speech!r}")
    return answer


def expect_answer(
    answer: Answer,
    response_type: str,
    *,
    speech_starts: str | None = None,
    code: str | None = None,
) -> None:
    """Check the type of an answer, its error code, and how its speech begins."""
    if answer.response_type != response_type:
        raise SmokeFailure(
            f"Expected a {response_type} answer, got {answer.response_type}: "
            f"{answer.speech!r}"
        )
    if answer.code != code:
        raise SmokeFailure(f"Expected the error code {code}, got {answer.code}")
    if speech_starts is not None and not answer.speech.startswith(speech_starts):
        raise SmokeFailure(
            f"Expected the answer to begin {speech_starts!r}, got {answer.speech!r}"
        )


async def expect_rest_state(
    session: aiohttp.ClientSession, access_token: str, entity_id: str, expected: str
) -> None:
    """Check what the REST API says the state of `entity_id` is, right now."""
    state = await request_json(
        session, INSTANCE, "GET", f"/api/states/{entity_id}", access_token
    )
    if state["state"] != expected:
        raise SmokeFailure(
            f"{entity_id}: expected {expected} over the REST API, "
            f"it is {state['state']}"
        )


def wall_clock(moment: datetime, zone: ZoneInfo) -> str:
    """The time of day in `zone`, as an answer says it."""
    return f"{moment.astimezone(zone):%H:%M}"


async def scenario_voice(
    session: aiohttp.ClientSession, refresh_token: str, timer: Timer
) -> None:
    say(f"Talk to the built-in agent about {timer.target}")
    access_token = await new_access_token(session, INSTANCE, refresh_token)
    await add_voice_settings(session, access_token)
    say("  voice settings added")
    async with open_socket(session, INSTANCE, refresh_token) as socket:
        zone = ZoneInfo((await socket.call("get_config"))["time_zone"])

        # An input boolean is not exposed to Assist unless the owner says so, and the
        # sentences list the name whatever Assist may see, so the agent refuses.
        answer = await converse(
            session, access_token, f"how much time is left on {SWITCH_NAME.lower()}"
        )
        expect_answer(answer, "error", code="no_valid_targets")
        await socket.call(
            "homeassistant/expose_entity",
            assistants=["conversation"],
            entity_ids=[timer.target],
            should_expose=True,
        )
        say(f"  {timer.target} exposed to Assist")

        answer = await converse(
            session, access_token, f"turn on {SWITCH_NAME.lower()} for 2 minutes"
        )
        _, end = await expect_started(socket, timer, 2)
        expect_answer(
            answer,
            "action_done",
            speech_starts=(
                f"{SWITCH_NAME} runs for 2 minutes, until {wall_clock(end, zone)}"
            ),
        )
        await expect_rest_state(session, access_token, timer.target, "on")

        answer = await converse(
            session, access_token, f"how much time is left on {SWITCH_NAME.lower()}"
        )
        expect_answer(
            answer,
            "query_answer",
            speech_starts=f"2 minutes left on {SWITCH_NAME}",
        )

        asked = datetime.now(UTC)
        answer = await converse(
            session, access_token, f"turn off {SWITCH_NAME.lower()} in 1 minute"
        )
        shortened = await socket.wait_for_state(
            timer.ends_at,
            ends_near(asked + timedelta(minutes=1)),
            "a minute from now",
            CALL_TIMEOUT,
        )
        end = timestamp(shortened["state"])
        expect_answer(
            answer,
            "action_done",
            speech_starts=f"{SWITCH_NAME} turns off at {wall_clock(end, zone)}",
        )
        await expect_rest_state(session, access_token, timer.target, "on")
        await expect_off_at(socket, timer, end)
        await expect_rest_state(session, access_token, timer.target, "off")

        answer = await converse(session, access_token, f"turn on {SWITCH_NAME.lower()}")
        _, end = await expect_started(socket, timer, DEFAULT_DURATION_MINUTES)
        expect_answer(
            answer,
            "action_done",
            speech_starts=(
                f"{SWITCH_NAME} runs for {DEFAULT_DURATION_MINUTES} minutes, "
                f"until {wall_clock(end, zone)}"
            ),
        )
        await expect_rest_state(session, access_token, timer.target, "on")

        answer = await converse(
            session, access_token, f"turn off {SWITCH_NAME.lower()}"
        )
        expect_answer(answer, "action_done", speech_starts=f"{SWITCH_NAME} is off.")
        await expect_rest_state(session, access_token, timer.target, "off")
        await socket.wait_for_state(timer.run_for, has_minutes(0), "0", CALL_TIMEOUT)
        await socket.wait_for_state(
            timer.ends_at, has_state("unknown"), "unknown", CALL_TIMEOUT
        )
        say(f"  {timer.target} stopped by voice")


async def scenario_restart(
    session: aiohttp.ClientSession, refresh_token: str, timer: Timer
) -> None:
    say("Run for 3 minutes, restart Home Assistant, wait for the switch to turn off")
    async with open_socket(session, INSTANCE, refresh_token) as socket:
        end = await start_countdown(socket, timer, 3)
    say("  restarting Home Assistant")
    await INSTANCE.restart(session)
    async with open_socket(session, INSTANCE, refresh_token) as socket:
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
    async with open_socket(session, INSTANCE, refresh_token) as socket:
        await start_countdown(socket, timer, KEEP_MINUTES)
    say(f"Left running: {INSTANCE.base_url}/config/devices/device/{timer.device_id}")
    say(f"Log in as {USERNAME!r} with password {PASSWORD!r}.")


async def run(session: aiohttp.ClientSession, keep: bool) -> None:
    await wait_until_up(session, INSTANCE)
    refresh_token = await onboard(session, INSTANCE, USERNAME, PASSWORD)
    async with open_socket(session, INSTANCE, refresh_token) as socket:
        await socket.wait_for_state(SWITCH, has_state("off"), "off", CALL_TIMEOUT)
        timer = await add_timer(
            session,
            socket,
            INSTANCE,
            await new_access_token(session, INSTANCE, refresh_token),
            SWITCH,
            runtime=True,
        )
    say(f"Added a timer for {SWITCH}, counting its runtime")
    await scenario_card(session, refresh_token, timer)
    await scenario_expiry(session, refresh_token, timer)
    await scenario_command(session, refresh_token)
    await scenario_settings(session, refresh_token)
    await scenario_schedule(session, refresh_token, timer)
    await scenario_voice(session, refresh_token, timer)
    await scenario_restart(session, refresh_token, timer)
    if keep:
        await leave_running(session, refresh_token, timer)


async def main(keep: bool) -> int:
    try:
        await INSTANCE.start_fresh()
        async with aiohttp.ClientSession() as session:
            await run(session, keep)
    except HarnessFailure as failure:
        say(f"FAILED: {failure}")
        await INSTANCE.print_logs()
        return 1
    finally:
        if not keep:
            await INSTANCE.stop()
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
