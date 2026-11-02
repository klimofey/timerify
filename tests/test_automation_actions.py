"""Timerify's actions in the automation editor.

The editor offers actions by target: pick a device and it lists every service whose
target matches an entity of that device. Home Assistant never asks Timerify for the
"Device" block of a device another integration owns, so the actions are the services,
and these scenarios ask the editor's own question through a real websocket connection.
An automation then runs them aimed at the device, as the editor writes them.
"""

from typing import Any, Final

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_mock_service
from pytest_homeassistant_custom_component.typing import (
    MockHAClientWebSocket,
    WebSocketGenerator,
)

from custom_components.timerify.const import DOMAIN

from .conftest import SWITCH_SERVICES, FakeTarget, ProvideTarget, SetupTarget
from .helpers import (
    NUMBER,
    SENSOR,
    TURN_OFF,
    TURN_ON,
    add_automation,
    record_action,
    run_for_of,
    set_number,
    state_of,
)

TIMERIFY_ACTIONS: Final = {
    "timerify.run",
    "timerify.add_time",
    "timerify.stop",
    "timerify.add_command",
    "timerify.cancel_command",
}
"""What the editor lists for a device that carries a timer, besides the actions of the
device's own integration."""

GO: Final = {"trigger": "event", "event_type": "timerify_test_go"}
"""The trigger of the automations here: the test fires its event when it is ready."""


@pytest.fixture
async def client(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> MockHAClientWebSocket:
    """The editor's connection, of an admin.

    Timerify is set up first. Setting it up adds the card to the web server's routes,
    and the test server closes the routes when the first connection is made.
    """
    assert await async_setup_component(hass, DOMAIN, {})
    return await hass_ws_client(hass)


async def actions_for_device(client: MockHAClientWebSocket, device_id: str) -> set[str]:
    """The services the editor lists under **By target** once the user picks the
    device `device_id`."""
    await client.send_json_auto_id(
        {"type": "get_services_for_target", "target": {"device_id": [device_id]}}
    )
    message: dict[str, Any] = await client.receive_json()
    assert message["success"] is True, message
    return set(message["result"])


async def fire_go(hass: HomeAssistant) -> None:
    """Fire the event the automation waits for, and let the automation finish."""
    hass.bus.async_fire("timerify_test_go")
    await hass.async_block_till_done()


async def test_the_boilers_device_offers_timerifys_actions_by_target(
    client: MockHAClientWebSocket, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Picking the boiler's device, which another integration owns, lists Timerify's
    actions with the boiler's own."""
    await setup_target()
    assert fake_target.device_id is not None

    actions = await actions_for_device(client, fake_target.device_id)

    assert actions >= TIMERIFY_ACTIONS


async def test_a_device_without_a_timer_offers_no_timerify_action(
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    provide_target: ProvideTarget,
    setup_target: SetupTarget,
) -> None:
    """The kettle has no timer, so its device lists none of Timerify's actions, while
    the boiler's, with a timer, does: the list follows the device, not the
    integration."""
    kettle = provide_target("switch.kettle", SWITCH_SERVICES, name="Kettle")
    await setup_target()
    assert fake_target.device_id is not None
    assert kettle.device_id is not None
    assert await actions_for_device(client, fake_target.device_id) >= TIMERIFY_ACTIONS

    actions = await actions_for_device(client, kettle.device_id)

    assert not {action for action in actions if action.startswith(f"{DOMAIN}.")}


@pytest.mark.parametrize("fake_target", [False], indirect=True)
async def test_the_device_made_for_a_switch_offers_them_too(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A switch on no device gets one that Timerify makes, and that device lists the
    actions the same way."""
    await setup_target()
    registered = er.async_get(hass).async_get(NUMBER)
    assert registered is not None
    assert registered.device_id is not None

    actions = await actions_for_device(client, registered.device_id)

    assert actions >= TIMERIFY_ACTIONS


async def test_an_automation_runs_the_boiler_for_20_minutes_by_its_device(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The editor fills the target of the action with the device, and the automation
    reaches the boiler's timer through it."""
    await setup_target()
    await add_automation(
        hass,
        GO,
        [
            {
                "action": "timerify.run",
                "target": {"device_id": fake_target.device_id},
                "data": {"minutes": 20},
            }
        ],
    )

    await fire_go(hass)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == "2026-01-05T07:20:00+00:00"


async def test_add_time_and_stop_by_the_device_reach_the_boiler(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Run, add time and stop, all aimed at the device, act on the one timer on it."""
    await setup_target()
    by_device = {"device_id": fake_target.device_id}
    records = async_mock_service(hass, "test", "record")
    await add_automation(
        hass,
        GO,
        [
            {"action": "timerify.run", "target": by_device, "data": {"minutes": 20}},
            {
                "action": "timerify.add_time",
                "target": by_device,
                "data": {"minutes": 10},
            },
            {
                "action": "test.record",
                "data": {"ends_at": f"{{{{ states('{SENSOR}') }}}}"},
            },
            {"action": "timerify.stop", "target": by_device},
        ],
    )

    await fire_go(hass)

    [record] = records
    assert record.data == {"ends_at": "2026-01-05T07:30:00+00:00"}
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, NUMBER) == "0"


async def test_stop_aimed_at_one_channel_leaves_the_other_running(
    hass: HomeAssistant,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """A relay with two channels has a timer on each. Aimed at one channel's Run for,
    Stop ends that countdown and leaves the other channel's alone."""
    relay_1, relay_2 = fake_relay
    one = await setup_target(target="switch.relay_1")
    two = await setup_target(target="switch.relay_2")
    await set_number(hass, run_for_of(hass, one), 30)
    await set_number(hass, run_for_of(hass, two), 30)
    await add_automation(
        hass,
        GO,
        [{"action": "timerify.stop", "target": {"entity_id": run_for_of(hass, one)}}],
    )

    await fire_go(hass)

    assert relay_1.calls == [
        ("turn_on", "switch.relay_1"),
        ("turn_off", "switch.relay_1"),
    ]
    assert relay_2.calls == [("turn_on", "switch.relay_2")]
    assert state_of(hass, run_for_of(hass, one)) == "0"
    assert state_of(hass, run_for_of(hass, two)) == "30"


async def test_stop_aimed_at_a_deleted_timer_lets_the_automation_go_on(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user deletes the timer an automation stops. Home Assistant skips the
    missing number and says so in the log, and the steps after Stop still run."""
    entry = await setup_target()
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    records = async_mock_service(hass, "test", "record")
    await add_automation(
        hass,
        GO,
        [
            {"action": "timerify.stop", "target": {"entity_id": NUMBER}},
            record_action(["platform"]),
        ],
    )

    await fire_go(hass)

    assert len(records) == 1
    assert fake_target.calls == []
    assert (
        f"Referenced entities {NUMBER} are missing or not currently available"
        in caplog.text
    )
