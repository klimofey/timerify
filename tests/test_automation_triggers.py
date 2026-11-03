"""Timerify's triggers in the automation editor: a countdown started, a countdown ended
and a pending command came due.

Like the actions, they are offered by target: pick a device and the editor lists every
trigger whose target matches an entity of that device. They are triggers of the
integration, aimed at Timerify's "Run for" numbers, and they listen to the events the
timers fire. The scenarios ask the editor's own question through a real websocket
connection, then run automations that use the triggers as the editor writes them.
"""

import logging
from collections.abc import Sequence
from typing import Any, Final, Literal

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import CoreState, HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)
from pytest_homeassistant_custom_component.typing import MockHAClientWebSocket

from custom_components.timerify.const import DOMAIN, EVENT_COUNTDOWN_ENDED

from .conftest import SWITCH_SERVICES, FakeTarget, ProvideTarget, SetupTarget
from .helpers import (
    NUMBER,
    TARGET_ID,
    TURN_OFF,
    add_automation,
    add_command,
    advance,
    at,
    call_service,
    command_json,
    components_for_device,
    payload,
    record_action,
    restart_after,
    run_for_of,
    set_number,
    state_of,
)

TIMERIFY_TRIGGERS: Final = {
    "timerify.countdown_started",
    "timerify.countdown_ended",
    "timerify.command_due",
}
"""What the editor lists for a device that carries a timer, besides the triggers of the
device's own integration."""


async def watch(
    hass: HomeAssistant, key: str, target: dict[str, Any], fields: Sequence[str]
) -> list[ServiceCall]:
    """Add an automation that records the `fields` of the trigger `timerify.<key>`
    aimed at `target`, as the editor writes it, and return the list its records come
    in."""
    records = async_mock_service(hass, "test", "record")
    await add_automation(
        hass, {"trigger": f"{DOMAIN}.{key}", "target": target}, [record_action(fields)]
    )
    return records


async def test_the_triggers_are_described_for_the_editor(
    client: MockHAClientWebSocket,
) -> None:
    """The editor subscribes to the trigger platforms and gets each trigger with the
    entities it can be aimed at, which are the "Run for" numbers of Timerify, and with
    no fields to fill in. The `client` fixture sets Timerify up before it connects, so
    the platform is there with no timer yet."""
    await client.send_json_auto_id({"type": "trigger_platforms/subscribe"})
    result = await client.receive_json()
    assert result["success"] is True, result
    descriptions: dict[str, Any] = (await client.receive_json())["event"]

    for key in TIMERIFY_TRIGGERS:
        assert descriptions[key] == {
            "target": {"entity": [{"integration": DOMAIN, "domain": ["number"]}]},
            "fields": {},
        }


async def test_the_boilers_device_offers_the_three_triggers_by_target(
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    provide_target: ProvideTarget,
    setup_target: SetupTarget,
) -> None:
    """Picking the boiler's device, which another integration owns, lists Timerify's
    triggers with the boiler's own.

    The kettle has no timer, so its device lists none of them: the list follows the
    device the timer is on, not the integration. The fake switches are no entities of
    a platform, so Home Assistant's lookup knows nothing of them (they are not in
    `entity_sources`) and the kettle's list is empty whatever Timerify does. The
    boiler's list, with a timer, is the control: it shows that the lookup finds the
    triggers where there is a timer.
    """
    kettle = provide_target("switch.kettle", SWITCH_SERVICES, name="Kettle")
    await setup_target()
    assert fake_target.device_id is not None
    assert kettle.device_id is not None

    boiler_triggers = await components_for_device(
        client, "triggers", fake_target.device_id
    )
    kettle_triggers = await components_for_device(client, "triggers", kettle.device_id)

    assert boiler_triggers >= TIMERIFY_TRIGGERS
    assert not {t for t in kettle_triggers if t.startswith(f"{DOMAIN}.")}


@pytest.mark.parametrize("fake_target", [False], indirect=True)
async def test_the_device_made_for_a_switch_offers_the_triggers_too(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A switch on no device gets one that Timerify makes, and that device lists the
    triggers the same way."""
    await setup_target()
    registered = er.async_get(hass).async_get(NUMBER)
    assert registered is not None
    assert registered.device_id is not None

    triggers = await components_for_device(client, "triggers", registered.device_id)

    assert triggers >= TIMERIFY_TRIGGERS


async def test_countdown_started_gives_the_automation_its_end(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    await setup_target()
    records = await watch(
        hass,
        "countdown_started",
        {"device_id": fake_target.device_id},
        ["entity_id", "ends_at", "limit"],
    )

    await set_number(hass, NUMBER, 30)

    assert [record.data for record in records] == [
        {"entity_id": NUMBER, "ends_at": "2026-01-05T07:30:00+00:00", "limit": False}
    ]


async def test_a_limit_gives_the_automation_its_mark(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The trigger fires for a limit too, and `trigger.limit` tells it from a time that
    somebody chose."""
    await setup_target(mode="loose", limit=120)
    records = await watch(
        hass,
        "countdown_started",
        {"device_id": fake_target.device_id},
        ["entity_id", "ends_at", "limit"],
    )

    await fake_target.set_state("on")
    await set_number(hass, NUMBER, 30)

    assert [record.data for record in records] == [
        {"entity_id": NUMBER, "ends_at": "2026-01-05T09:00:00+00:00", "limit": True},
        {"entity_id": NUMBER, "ends_at": "2026-01-05T07:30:00+00:00", "limit": False},
    ]


@pytest.mark.parametrize(
    ("how", "reason"),
    [
        ("expiry", "expired"),
        ("stop", "stopped"),
        ("by_hand", "turned_off"),
        ("limit", "limit"),
    ],
)
async def test_countdown_ended_tells_the_automation_how(
    how: str,
    reason: str,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """However the countdown ends, the automation hears of it once and is told which
    way it ended: it ran out, Timerify stopped it, someone switched the boiler off, or
    the boiler was left on and its limit turned it off. The first three are the
    countdowns of a strict timer; the limit is a loose timer's."""
    if how == "limit":
        await setup_target(mode="loose", limit=120)
    else:
        await setup_target()
    records = await watch(
        hass,
        "countdown_ended",
        {"device_id": fake_target.device_id},
        ["entity_id", "reason"],
    )
    if how == "limit":
        await fake_target.set_state("on")
    else:
        await set_number(hass, NUMBER, 30)
    assert records == []

    match how:
        case "expiry":
            await advance(hass, freezer, minutes=30)
        case "stop":
            await call_service(hass, "stop", {"entity_id": NUMBER})
        case "by_hand":
            await fake_target.set_state("off")
        case "limit":
            await advance(hass, freezer, minutes=120)

    assert [record.data for record in records] == [
        {"entity_id": NUMBER, "reason": reason}
    ]


async def test_command_due_names_the_command_and_its_action(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    await setup_target()
    records = await watch(
        hass,
        "command_due",
        {"device_id": fake_target.device_id},
        ["entity_id", "command_id", "action"],
    )
    await set_number(hass, NUMBER, 30)
    response = await add_command(hass, NUMBER, action="off", delay=10)
    assert records == []

    await advance(hass, freezer, minutes=10)

    assert [record.data for record in records] == [
        {
            "entity_id": NUMBER,
            "command_id": response[NUMBER]["command_id"],
            "action": "off",
        }
    ]


async def test_a_trigger_ignores_the_timers_of_other_devices(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    provide_target: ProvideTarget,
    setup_target: SetupTarget,
) -> None:
    """A trigger aimed at the kettle's device hears the kettle's timer and not the
    boiler's, whose countdown starts first."""
    kettle = provide_target("switch.kettle", SWITCH_SERVICES, name="Kettle")
    await setup_target()
    kettle_entry = await setup_target(target="switch.kettle")
    records = await watch(
        hass, "countdown_started", {"device_id": kettle.device_id}, ["entity_id"]
    )

    await set_number(hass, NUMBER, 30)
    assert records == []

    await set_number(hass, run_for_of(hass, kettle_entry), 10)
    assert [record.data for record in records] == [
        {"entity_id": run_for_of(hass, kettle_entry)}
    ]


async def test_a_relay_trigger_names_the_channel_whose_countdown_ended(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """A trigger aimed at the device of a relay with two timers fires for each channel
    and says which one it fired for."""
    relay_1, _ = fake_relay
    one = await setup_target(target="switch.relay_1")
    two = await setup_target(target="switch.relay_2")
    records = await watch(
        hass, "countdown_ended", {"device_id": relay_1.device_id}, ["entity_id"]
    )
    await set_number(hass, run_for_of(hass, one), 10)
    await set_number(hass, run_for_of(hass, two), 20)

    await advance(hass, freezer, minutes=10)

    assert [record.data for record in records] == [{"entity_id": run_for_of(hass, one)}]

    await advance(hass, freezer, minutes=10)

    assert [record.data for record in records] == [
        {"entity_id": run_for_of(hass, one)},
        {"entity_id": run_for_of(hass, two)},
    ]


async def test_a_trigger_aimed_at_one_run_for_ignores_the_other_channel(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """Aimed at the Run for of the first channel, the trigger hears the end of that
    channel and not of the second, which ends first."""
    one = await setup_target(target="switch.relay_1")
    two = await setup_target(target="switch.relay_2")
    records = await watch(
        hass, "countdown_ended", {"entity_id": run_for_of(hass, one)}, ["entity_id"]
    )
    await set_number(hass, run_for_of(hass, one), 20)
    await set_number(hass, run_for_of(hass, two), 10)

    await advance(hass, freezer, minutes=10)

    assert records == []

    await advance(hass, freezer, minutes=10)

    assert [record.data for record in records] == [{"entity_id": run_for_of(hass, one)}]


async def test_a_trigger_of_a_deleted_timer_never_fires(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    provide_target: ProvideTarget,
    setup_target: SetupTarget,
) -> None:
    """The user deletes the timer an automation waits for. The automation stays on,
    hears nothing of it, and Home Assistant logs no error: the timer of the kettle,
    which runs out meanwhile, is not the one it names."""
    provide_target("switch.kettle", SWITCH_SERVICES, name="Kettle")
    boiler = await setup_target()
    kettle = await setup_target(target="switch.kettle")
    records = await watch(hass, "countdown_ended", {"entity_id": NUMBER}, ["entity_id"])
    await hass.config_entries.async_remove(boiler.entry_id)
    await hass.async_block_till_done()
    await set_number(hass, run_for_of(hass, kettle), 10)

    await advance(hass, freezer, minutes=10)

    assert records == []
    [automation] = hass.states.async_entity_ids("automation")
    assert state_of(hass, automation) == "on"
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []


@pytest.mark.parametrize(
    "data",
    [None, {"reason": "expired"}, {"entity_id": None}, {"entity_id": [NUMBER]}],
    ids=["no_data", "no_timer", "no_entity_id", "entity_id_is_a_list"],
)
async def test_an_event_fired_by_hand_without_a_timer_is_ignored(
    data: dict[str, Any] | None,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A user who tries the event from Developer tools fires it with no timer named, or
    a malformed one. The automation does not run, stays on, and Home Assistant logs no
    error."""
    await setup_target()
    records = await watch(
        hass, "countdown_ended", {"device_id": fake_target.device_id}, ["entity_id"]
    )

    hass.bus.async_fire(EVENT_COUNTDOWN_ENDED, data)
    await hass.async_block_till_done()

    assert records == []
    [automation] = hass.states.async_entity_ids("automation")
    assert state_of(hass, automation) == "on"
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []


async def test_a_timer_added_later_is_covered_by_the_device_trigger(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """The user times the second channel of the relay after the automation was saved.
    The trigger is aimed at the device, so it covers the new timer without an edit."""
    relay_1, _ = fake_relay
    await setup_target(target="switch.relay_1")
    records = await watch(
        hass, "countdown_ended", {"device_id": relay_1.device_id}, ["entity_id"]
    )
    two = await setup_target(target="switch.relay_2")
    await set_number(hass, run_for_of(hass, two), 5)

    await advance(hass, freezer, minutes=5)

    assert [record.data for record in records] == [{"entity_id": run_for_of(hass, two)}]


async def turn_automation(hass: HomeAssistant, service: str, entity_id: str) -> None:
    """Turn the automation off or on, as the user does on its page."""
    await hass.services.async_call(
        "automation", service, {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()


async def test_an_automation_that_is_turned_off_hears_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user turns the automation off. The boiler's countdown ends and the
    automation does not run. Turned on again, it hears the next end."""
    await setup_target()
    records = await watch(
        hass, "countdown_ended", {"device_id": fake_target.device_id}, ["entity_id"]
    )
    [automation] = hass.states.async_entity_ids("automation")
    await turn_automation(hass, "turn_off", automation)
    await set_number(hass, NUMBER, 10)

    await advance(hass, freezer, minutes=10)

    assert records == []

    await turn_automation(hass, "turn_on", automation)
    await set_number(hass, NUMBER, 10)

    await advance(hass, freezer, minutes=10)

    assert [record.data for record in records] == [{"entity_id": NUMBER}]


async def start_home_assistant(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    key: str,
    fields: Sequence[str],
    stored: dict[str, Any],
    boiler: Literal["on", "off"] = "on",
) -> tuple[MockConfigEntry, list[ServiceCall]]:
    """Start Home Assistant the way it starts: the timer is set up from its file and
    the automation is added while it is not running, and the boiler's own integration
    brings the boiler up, in the state `boiler`, before Home Assistant announces that
    it has started. Return the timer's entry and what the automation records."""
    hass.set_state(CoreState.not_running)
    hass.states.async_remove(TARGET_ID)
    entry = await setup_target(stored=stored)
    records = await watch(hass, key, {"device_id": fake_target.device_id}, fields)
    assert records == []
    await fake_target.set_state(boiler)
    await hass.async_start()
    await hass.async_block_till_done()
    assert hass.state is CoreState.running
    return entry, records


async def test_a_countdown_that_ended_while_down_triggers_once_at_start_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The boiler's countdown ran out while Home Assistant was down. Once Home
    Assistant has started the boiler is switched off and the automation runs, once,
    with the reason `expired`; the timer being set up again later does not run it
    again."""
    entry, records = await start_home_assistant(
        hass,
        fake_target,
        setup_target,
        "countdown_ended",
        ["entity_id", "reason"],
        payload(end=at(-5)),
    )

    assert [record.data for record in records] == [
        {"entity_id": NUMBER, "reason": "expired"}
    ]
    assert fake_target.calls == [TURN_OFF]

    await restart_after(hass, freezer, entry, minutes=5)

    assert len(records) == 1


async def test_a_boiler_already_off_at_start_up_still_gets_the_expired_end(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The boiler was switched off while Home Assistant was down, after its countdown
    had run out. The automation still hears, once, that the countdown expired, and
    nothing is sent to a boiler that is already off."""
    _, records = await start_home_assistant(
        hass,
        fake_target,
        setup_target,
        "countdown_ended",
        ["entity_id", "reason"],
        payload(end=at(-5)),
        boiler="off",
    )

    assert [record.data for record in records] == [
        {"entity_id": NUMBER, "reason": "expired"}
    ]
    assert fake_target.calls == []


async def test_a_command_that_came_due_while_down_triggers_at_start_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A pending "off" came due while Home Assistant was down, with the boiler's
    countdown still ahead. The automation hears of the command once Home Assistant
    has started."""
    entry, records = await start_home_assistant(
        hass,
        fake_target,
        setup_target,
        "command_due",
        ["entity_id", "command_id", "action"],
        payload(end=at(25), commands=[command_json(at(-5), "off", id="c1")]),
    )

    assert [record.data for record in records] == [
        {"entity_id": NUMBER, "command_id": "c1", "action": "off"}
    ]
    assert fake_target.calls == [TURN_OFF]

    await restart_after(hass, freezer, entry, minutes=5)

    assert len(records) == 1
