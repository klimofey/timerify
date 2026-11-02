"""The Home Assistant that the end-to-end tests of the dashboard card run against.

    uv run python -m scripts.e2e.hass up --port 18124 --state card/e2e/.state.json
    uv run python -m scripts.e2e.hass restart --port 18124 --state card/e2e/.state.json
    uv run python -m scripts.e2e.hass down --port 18124 --state card/e2e/.state.json

Playwright's global setup runs `up` and its global teardown `down`; a test that needs
Home Assistant to restart runs `restart`.

`up` starts a fresh container and builds the fixture the tests start from, all through
the pages' own APIs: an administrator and a user who is not one, each with a long-lived
access token; a strict timer on a switch that sits on no device and a loose one on a
switch that sits on a device; an interval on the strict timer that is never open while a
test runs; a pending command on the loose timer that never comes due; a third timer
whose "Ends at" sensor is disabled, which stays so, since enabling an entity makes Home
Assistant reload its entry some time later; and a dashboard of the card with a view for
each file of tests that needs one. It writes what the tests
need to find all of it to the state file, which the Playwright side reads: see
`E2EState` in card/e2e/constants.ts. The state file holds the dashboard as it was saved,
for the reset that every test starts with to save it again.
"""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from scripts.harness.hass import (
    CALL_TIMEOUT,
    DEMO_SWITCH,
    DOMAIN,
    STARTUP_TIMEOUT,
    SWITCH,
    WEEKDAYS,
    HarnessFailure,
    Instance,
    Socket,
    Timer,
    add_interval,
    add_timer,
    find_interval_switch,
    has_state,
    is_known,
    login,
    new_access_token,
    onboard,
    open_socket,
    say,
    wait_until_running,
    wait_until_up,
)

PROJECT = "timerify-e2e"
CONFIG_DIR = Path(__file__).parent / "config"
DASHBOARD = "timerify-e2e"
"""The `url_path` of the storage dashboard that holds the views of the tests."""

INTERVAL_DISTANCE = timedelta(hours=12)
"""How far ahead of the time of the server the fixture's interval begins."""
INTERVAL_LENGTH = timedelta(minutes=15)
COMMAND_ACTION = "on"
COMMAND_DELAY_MINUTES = 600
"""The fixture's pending command is due this long after it is added: 10 hours, so a
test run never reaches it, and the interval, 12 hours from the start, is later still."""


@dataclass(frozen=True)
class Account:
    username: str
    password: str


ADMIN = Account("e2e", "e2e-test-password")
VIEWER = Account("viewer", "viewer-test-password")
"""A user who is not an administrator: a member of the group `system-users`."""


STRICT_NAME = "Boiler"
"""What the strict timer's target is called on the dashboard. The configuration of the
harness, which the smoke test shares, names it for itself; the fixture renames it in the
entity registry, as a user does. card/e2e/constants.ts says the same."""

DISABLED_TARGET = "switch.smoke_heater"
"""What the third timer runs: a template switch that configuration.yaml declares, on no
device. The smoke test's thermostat names it as its heater; that thermostat starts
switched off, and no E2E test touches it."""

QUICK_CHIP_MINUTES = 15
"""The minutes of the chip on the pill of the strict timer."""


def timerify_card(timer: Timer, **options: Any) -> dict[str, Any]:
    """A card of the timer, as a user writes it into a dashboard."""
    return {"type": "custom:timerify-card", "entity": timer.run_for, **options}


def dashboard_config(strict: Timer, loose: Timer, disabled: Timer) -> dict[str, Any]:
    """The views of the dashboard, one for each file of tests. Each task that adds a
    file of tests adds its view here."""
    return {
        "views": [
            {
                "title": "Dialog",
                "path": "dialog",
                "cards": [timerify_card(strict, layout="pill")],
            },
            {
                "title": "Pill",
                "path": "pill",
                "cards": [
                    timerify_card(strict, layout="pill", chip=QUICK_CHIP_MINUTES)
                ],
            },
            {
                # Both timers as round cards side by side: what the tests of the long
                # press and the picture of the round layout in the documentation show.
                "title": "Round",
                "path": "round",
                "cards": [
                    {
                        "type": "horizontal-stack",
                        "cards": [
                            timerify_card(strict, layout="round"),
                            timerify_card(loose, layout="round"),
                        ],
                    }
                ],
            },
            {
                # The pop-up of both timers: the strict one has the interval, the loose
                # one the pending command, and both have the default presets.
                "title": "Pop-up",
                "path": "popup",
                "cards": [
                    {
                        "type": "vertical-stack",
                        "cards": [
                            timerify_card(strict, layout="pill"),
                            timerify_card(loose, layout="pill"),
                        ],
                    }
                ],
            },
            {
                # What is pressed besides a tap: the round tile of the strict timer
                # whose long press is a Home Assistant action, and a pill of the same
                # timer whose double tap runs it.
                "title": "Presses",
                "path": "presses",
                "cards": [
                    timerify_card(
                        strict,
                        layout="round",
                        hold="action",
                        hold_action={"action": "more-info"},
                    ),
                    timerify_card(strict, layout="pill", double_tap="run"),
                ],
            },
            {
                # Empty: the editor tests add a card to it from the card picker, and the
                # reset that every test starts with saves the dashboard as it was.
                "title": "Editor",
                "path": "editor",
                "cards": [],
            },
            {
                # The timer whose "Ends at" sensor is disabled: the card says so.
                "title": "Disabled",
                "path": "disabled",
                "cards": [timerify_card(disabled, layout="pill")],
            },
            {
                # What the screenshots of the documentation show: both timers in one
                # stack, so that they are cut from the page as one picture.
                "title": "Screenshots",
                "path": "screenshots",
                "cards": [
                    {
                        "type": "vertical-stack",
                        "cards": [
                            timerify_card(
                                strict, layout="pill", chip=QUICK_CHIP_MINUTES
                            ),
                            timerify_card(loose, layout="pill"),
                        ],
                    }
                ],
            },
        ]
    }


async def long_lived_token(socket: Socket, name: str) -> str:
    """A token that does not expire for a year, which the tests use for the user."""
    return str(
        await socket.call(
            "auth/long_lived_access_token", client_name=name, lifespan=365
        )
    )


async def create_viewer(socket: Socket) -> None:
    """Make the user who is not an administrator, the way the users page does."""
    created = await socket.call(
        "config/auth/create", name=VIEWER.username, group_ids=["system-users"]
    )
    await socket.call(
        "config/auth_provider/homeassistant/create",
        user_id=created["user"]["id"],
        username=VIEWER.username,
        password=VIEWER.password,
    )


async def add_fixture_interval(
    session: aiohttp.ClientSession,
    instance: Instance,
    socket: Socket,
    access_token: str,
    timer: Timer,
) -> dict[str, str]:
    """Add the interval that begins `INTERVAL_DISTANCE` after the time of the server, on
    the weekday of that moment; returns what a test needs to know of it."""
    zone = ZoneInfo((await socket.call("get_config"))["time_zone"])
    start = (datetime.now(UTC) + INTERVAL_DISTANCE).astimezone(zone)
    start = start.replace(second=0, microsecond=0)
    end = start + INTERVAL_LENGTH
    weekday = WEEKDAYS[start.weekday()]
    title = await add_interval(
        session, instance, access_token, timer, weekday=weekday, start=start, end=end
    )
    switch = await find_interval_switch(socket, timer, title)
    return {
        "switch": switch["entity_id"],
        "weekday": weekday,
        "start": f"{start:%H:%M}",
        "end": f"{end:%H:%M}",
    }


async def build_fixture(
    session: aiohttp.ClientSession, instance: Instance
) -> dict[str, Any]:
    """Onboard the fresh Home Assistant and set up everything the tests start from."""
    await wait_until_up(session, instance)
    admin_refresh = await onboard(session, instance, ADMIN.username, ADMIN.password)
    async with open_socket(session, instance, admin_refresh) as socket:
        await wait_until_running(socket)
        say("Making the users")
        await create_viewer(socket)
        admin_token = await long_lived_token(socket, "e2e")
        async with open_socket(
            session,
            instance,
            await login(session, instance, VIEWER.username, VIEWER.password),
        ) as viewer_socket:
            viewer_token = await long_lived_token(viewer_socket, "e2e")

        say("Adding the timers")
        access_token = await new_access_token(session, instance, admin_refresh)
        await socket.wait_for_state(SWITCH, has_state("off"), "off", CALL_TIMEOUT)
        await socket.call(
            "config/entity_registry/update", entity_id=SWITCH, name=STRICT_NAME
        )
        strict = await add_timer(session, socket, instance, access_token, SWITCH)
        # The demo switch starts on; the loose timer starts with it off, as idle.
        await socket.wait_for_state(
            DEMO_SWITCH, is_known, "the demo switch", STARTUP_TIMEOUT
        )
        await socket.call(
            "call_service",
            domain="switch",
            service="turn_off",
            target={"entity_id": DEMO_SWITCH},
        )
        await socket.wait_for_state(DEMO_SWITCH, has_state("off"), "off", CALL_TIMEOUT)
        loose = await add_timer(
            session,
            socket,
            instance,
            access_token,
            DEMO_SWITCH,
            mode="loose",
            on_target_device=True,
        )

        say("Adding the timer whose Ends at sensor is disabled")
        disabled = await add_timer(
            session, socket, instance, access_token, DISABLED_TARGET
        )
        await socket.call(
            "config/entity_registry/update",
            entity_id=disabled.ends_at,
            disabled_by="user",
        )

        say("Adding the interval and the command")
        interval = await add_fixture_interval(
            session, instance, socket, access_token, strict
        )
        await socket.call(
            "call_service",
            domain=DOMAIN,
            service="add_command",
            service_data={"action": COMMAND_ACTION, "delay": COMMAND_DELAY_MINUTES},
            target={"entity_id": loose.run_for},
        )

        say("Making the dashboard")
        dashboard = dashboard_config(strict, loose, disabled)
        await socket.call(
            "lovelace/dashboards/create",
            url_path=DASHBOARD,
            title="Timerify end-to-end tests",
            mode="storage",
            show_in_sidebar=False,
            require_admin=False,
        )
        await socket.call("lovelace/config/save", url_path=DASHBOARD, config=dashboard)

    return {
        "base_url": instance.base_url,
        "users": {
            "admin": {**asdict(ADMIN), "token": admin_token},
            "viewer": {**asdict(VIEWER), "token": viewer_token},
        },
        "timers": {
            "strict": asdict(strict),
            "loose": asdict(loose),
            "disabled": asdict(disabled),
        },
        "interval": interval,
        "command": {"action": COMMAND_ACTION, "delay": COMMAND_DELAY_MINUTES},
        "dashboard": DASHBOARD,
        "dashboard_config": dashboard,
    }


async def up(instance: Instance, state_file: Path) -> None:
    """Start Home Assistant on a fresh configuration and set up the fixture."""
    await instance.start_fresh()
    async with aiohttp.ClientSession() as session:
        fixture = await build_fixture(session, instance)
    await asyncio.to_thread(state_file.write_text, json.dumps(fixture, indent=2) + "\n")
    say(f"Home Assistant is ready at {instance.base_url}; state in {state_file}")


async def restart(instance: Instance, state_file: Path) -> None:
    """Restart Home Assistant, and return when it is running again and the numbers of
    the timers have a value, which is when Timerify has started."""
    fixture = json.loads(await asyncio.to_thread(state_file.read_text))
    admin = fixture["users"]["admin"]
    async with aiohttp.ClientSession() as session:
        await instance.restart(session)
        refresh_token = await login(
            session, instance, admin["username"], admin["password"]
        )
        async with open_socket(session, instance, refresh_token) as socket:
            for timer in fixture["timers"].values():
                await socket.wait_for_state(
                    timer["run_for"], is_known, "a value", STARTUP_TIMEOUT
                )
            # The numbers can have a value before Home Assistant has finished starting,
            # and a second restart before then loses what it had not yet saved.
            await wait_until_running(socket)
    say("Home Assistant is back, and so are the timers")


async def down(instance: Instance, state_file: Path) -> None:
    """Stop Home Assistant; what the state file says belongs to it, so it goes too."""
    await instance.stop()
    await asyncio.to_thread(state_file.unlink, missing_ok=True)


async def main(command: str, port: int, state_file: Path) -> int:
    instance = Instance(PROJECT, port, CONFIG_DIR)
    failed = True
    try:
        match command:
            case "up":
                await up(instance, state_file)
            case "restart":
                await restart(instance, state_file)
            case "down":
                await down(instance, state_file)
        failed = False
    except HarnessFailure as failure:
        say(f"FAILED: {failure}")
        await instance.print_logs()
    finally:
        if failed and command == "up":
            # A global setup that failed has no teardown after it: nobody else stops it.
            await instance.stop()
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Home Assistant for the end-to-end tests of the dashboard card."
    )
    parser.add_argument("command", choices=["up", "restart", "down"])
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--state", type=Path, required=True)
    arguments = parser.parse_args()
    sys.exit(asyncio.run(main(arguments.command, arguments.port, arguments.state)))
