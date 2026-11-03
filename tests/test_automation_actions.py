"""Timerify's actions in the automation editor.

The editor offers actions by target: pick a device and it lists every service whose
target matches an entity of that device. Home Assistant never asks Timerify for the
"Device" block of a device another integration owns, so the actions are the services,
and these scenarios ask the editor's own question through a real websocket connection.
An automation then runs them aimed at the device, as the editor writes them.
"""

from typing import Final

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_mock_service
from pytest_homeassistant_custom_component.typing import MockHAClientWebSocket

from custom_components.timerify.const import DOMAIN

from .conftest import SWITCH_SERVICES, FakeTarget, ProvideTarget, SetupTarget
from .helpers import (
    NUMBER,
    SENSOR,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    add_automation,
    components_for_device,
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

    actions = await components_for_device(client, "services", fake_target.device_id)

    assert actions >= TIMERIFY_ACTIONS


async def test_a_device_without_a_timer_offers_no_timerify_action(
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    provide_target: ProvideTarget,
    setup_target: SetupTarget,
) -> None:
    """The kettle has no timer, so its device lists none of Timerify's actions: the
    list follows the device the timer is on, not the integration.

    The fake switches are no entities of a platform, so Home Assistant's lookup knows
    nothing of them (they are not in `entity_sources`) and the kettle's list is empty
    whatever Timerify does. The boiler's list, with a timer, is the control: it shows
    that the lookup finds Timerify's actions where there is a timer.
    """
    kettle = provide_target("switch.kettle", SWITCH_SERVICES, name="Kettle")
    await setup_target()
    assert fake_target.device_id is not None
    assert kettle.device_id is not None
    boiler_actions = await components_for_device(
        client, "services", fake_target.device_id
    )
    assert boiler_actions >= TIMERIFY_ACTIONS

    actions = await components_for_device(client, "services", kettle.device_id)

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

    actions = await components_for_device(client, "services", registered.device_id)

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


async def test_a_device_with_two_timers_offers_timerifys_actions_by_target(
    client: MockHAClientWebSocket,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """The relay's device lists the actions, whatever the number of timers on it."""
    relay_1, _ = fake_relay
    await setup_target(target="switch.relay_1")
    await setup_target(target="switch.relay_2")
    assert relay_1.device_id is not None

    actions = await components_for_device(client, "services", relay_1.device_id)

    assert actions >= TIMERIFY_ACTIONS


async def test_run_aimed_at_the_relay_runs_both_channels(
    hass: HomeAssistant,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """An action aimed at the device of a relay with two timers acts on both."""
    relay_1, relay_2 = fake_relay
    one = await setup_target(target="switch.relay_1")
    two = await setup_target(target="switch.relay_2")
    await add_automation(
        hass,
        GO,
        [
            {
                "action": "timerify.run",
                "target": {"device_id": relay_1.device_id},
                "data": {"minutes": 20},
            }
        ],
    )

    await fire_go(hass)

    assert relay_1.calls == [("turn_on", "switch.relay_1")]
    assert relay_2.calls == [("turn_on", "switch.relay_2")]
    assert state_of(hass, run_for_of(hass, one)) == "20"
    assert state_of(hass, run_for_of(hass, two)) == "20"


async def test_the_run_for_of_two_channels_name_their_channels(
    hass: HomeAssistant,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """What the target picker offers for a relay with two timers: each number names its
    channel, "Relay Run for (Channel 1)" and "Relay Run for (Channel 2)", so the user
    tells the two apart by name, and the entity id of the second says it too."""
    one = await setup_target(target="switch.relay_1")
    two = await setup_target(target="switch.relay_2")

    assert [run_for_of(hass, entry) for entry in (one, two)] == [
        "number.relay_run_for",
        "number.relay_run_for_channel_2",
    ]
    names = []
    for entry in (one, two):
        state = hass.states.get(run_for_of(hass, entry))
        assert state is not None
        names.append(state.attributes["friendly_name"])
    assert names == ["Relay Run for (Channel 1)", "Relay Run for (Channel 2)"]


async def test_stop_aimed_at_a_deleted_timer_lets_the_automation_go_on(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user deletes the timer an automation stops, while the boiler runs. Home
    Assistant skips the missing number and says so in the log, the boiler is left as
    it is, and the steps after Stop still run."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 30)
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

    assert [record.data for record in records] == [{"platform": "event"}]
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"
    assert (
        f"Referenced entities {NUMBER} are missing or not currently available"
        in caplog.text
    )
