"""A timer whose target was deleted: the repair that says so, and the fix that deletes
it.

The scenarios are the user's: the boiler's entity is deleted in its settings, or its
whole device is, or Home Assistant starts without it. The timer stays loaded and
switches nothing, the repair says so, and the user either adds the device again, with
the same entity id, or submits the repair to delete the timer.
"""

from http import HTTPStatus
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.repairs import RepairsFlowManager, repairs_flow_manager
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.timerify.const import DOMAIN

from .conftest import SWITCH_SERVICES, FakeTarget, ProvideTarget, SetupTarget
from .helpers import (
    NUMBER,
    SENSOR,
    SUNDAY,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    add_command,
    add_interval,
    advance,
    advance_to,
    iso,
    local,
    open_sunday,
    restart_after,
    set_number,
    start_set_number,
    state_of,
    storage_key,
    timerify_info,
    timerify_warnings,
)

pytestmark = pytest.mark.usefixtures("hass_storage")

DELETED = (
    "The entity {target} of the timer Boiler was deleted;"
    " the timer switches nothing until it is back"
)


@pytest.fixture
async def repairs(hass: HomeAssistant) -> None:
    """The Repairs integration, which Home Assistant runs and the user opens."""
    assert await async_setup_component(hass, "repairs", {})


def target_deleted_issue(
    hass: HomeAssistant, entry: ConfigEntry
) -> ir.IssueEntry | None:
    """The repair of the timer's deleted target, if there is one."""
    return ir.async_get(hass).async_get_issue(
        DOMAIN, f"target_deleted_{entry.entry_id}"
    )


def timer_entities(hass: HomeAssistant, entry: ConfigEntry) -> list[er.RegistryEntry]:
    """The registry entries of the timer's own entities."""
    return er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)


async def start_fix(client: Any, issue_id: str) -> dict[str, Any]:
    """Press "Repair" on an issue, as the Repairs page does; return the first step."""
    response = await client.post(
        "/api/repairs/issues/fix", json={"handler": DOMAIN, "issue_id": issue_id}
    )
    assert response.status == HTTPStatus.OK
    result: dict[str, Any] = await response.json()
    return result


async def submit_fix(client: Any, flow_id: str) -> dict[str, Any]:
    """Submit the step of a fix that shows nothing to fill in."""
    response = await client.post(f"/api/repairs/issues/fix/{flow_id}", json={})
    assert response.status == HTTPStatus.OK
    result: dict[str, Any] = await response.json()
    return result


# --- The repair appears ---------------------------------------------------------------


async def test_deleting_the_target_raises_a_repair_that_names_the_timer(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The boiler's entity is deleted: the repair names the timer and the entity, the
    timer stays loaded with its entities, and the log says it switches nothing."""
    entry = await setup_target()

    await fake_target.delete()

    issue = target_deleted_issue(hass, entry)
    assert issue is not None
    assert issue.translation_key == "target_deleted"
    assert issue.translation_placeholders == {"timer": "Boiler", "target": TARGET_ID}
    assert issue.is_fixable
    assert issue.severity == ir.IssueSeverity.ERROR
    assert entry.state is ConfigEntryState.LOADED
    assert state_of(hass, NUMBER) == "0"
    assert timerify_warnings(caplog) == [DELETED.format(target=TARGET_ID)]


async def test_a_target_deleted_while_down_raises_the_repair_at_start_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The boiler is gone when Home Assistant starts again: the timer that is set up
    for it raises the repair."""
    entry = await setup_target()

    def delete_the_boiler() -> None:
        er.async_get(hass).async_remove(TARGET_ID)
        hass.states.async_remove(TARGET_ID)

    await restart_after(hass, freezer, entry, minutes=5, while_down=delete_the_boiler)

    assert target_deleted_issue(hass, entry) is not None
    assert entry.state is ConfigEntryState.LOADED


async def test_a_target_with_no_registry_entry_keeps_the_repair_until_its_state_appears(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    provide_target: ProvideTarget,
    setup_target: SetupTarget,
) -> None:
    """A heater of YAML has a state and no registry entry. Home Assistant starts
    without it, as when its integration has not set up: the repair stands until the
    heater reports."""
    caplog.set_level("INFO")
    heater = provide_target(
        "switch.heater", SWITCH_SERVICES, name="Heater", registered=False
    )
    entry = await setup_target(target=heater.entity_id)
    assert target_deleted_issue(hass, entry) is None

    await restart_after(
        hass,
        freezer,
        entry,
        minutes=5,
        while_down=lambda: hass.states.async_remove(heater.entity_id),
    )

    assert target_deleted_issue(hass, entry) is not None

    await heater.set_state("off")

    assert target_deleted_issue(hass, entry) is None
    assert timerify_info(caplog)[-1] == (
        "The entity switch.heater of the timer Boiler is back"
    )


# --- The timer does nothing until the user acts ---------------------------------------


async def test_a_pending_command_due_while_the_target_is_deleted_calls_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A command to turn the boiler on comes due while it is deleted: nothing is sent
    to the entity that is not there. When it is back, the command is applied."""
    await setup_target()
    await add_command(hass, NUMBER, action="on", delay=10, minutes=30)
    await fake_target.delete()

    await advance(hass, freezer, minutes=10)

    assert fake_target.calls == []

    await fake_target.restore()

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "30"


async def test_a_window_that_opened_while_the_target_was_deleted_runs_when_it_is_back(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The morning window of the boiler opens while it is deleted: nothing is sent. The
    boiler is back inside the window and runs for the rest of it."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await fake_target.delete()

    await advance_to(hass, freezer, local(SUNDAY, "06:30"))

    assert fake_target.calls == []

    await advance_to(hass, freezer, local(SUNDAY, "06:40"))
    await fake_target.restore()

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")


async def test_a_countdown_ended_while_the_target_was_deleted_turns_it_off_when_back(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The boiler is deleted in the middle of a countdown, which ends while it is gone:
    nothing is sent. When the device is added again, with the boiler on, it is turned
    off, once."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 30)
    await fake_target.delete()

    await advance(hass, freezer, minutes=30)

    assert fake_target.calls == [TURN_ON]

    await fake_target.restore("on")

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert target_deleted_issue(hass, entry) is None


# --- The repair goes away when the entity is back -------------------------------------


async def test_restoring_the_target_clears_the_repair_and_the_timer_works_again(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The device is added again with the same entity id: the repair goes away by
    itself and the next countdown switches the boiler."""
    entry = await setup_target()
    await fake_target.delete()
    assert target_deleted_issue(hass, entry) is not None

    await fake_target.restore()

    assert target_deleted_issue(hass, entry) is None
    assert entry.state is ConfigEntryState.LOADED

    await set_number(hass, NUMBER, 10)

    assert fake_target.calls == [TURN_ON]


async def test_restoring_a_deleted_device_puts_the_timer_entities_back_on_it(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The whole device of the boiler is deleted, and Home Assistant leaves the timer's
    entities on no device. When the device is added again they are on it."""
    entry = await setup_target()
    assert {e.device_id for e in timer_entities(hass, entry)} == {fake_target.device_id}

    await fake_target.delete_device()

    assert {e.device_id for e in timer_entities(hass, entry)} == {None}
    assert target_deleted_issue(hass, entry) is not None

    await fake_target.restore()

    assert {e.device_id for e in timer_entities(hass, entry)} == {fake_target.device_id}
    assert target_deleted_issue(hass, entry) is None


async def test_a_target_deleted_over_a_restart_returns_to_its_device_with_the_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Home Assistant restarts while the boiler is deleted: the timer, still repaired,
    puts its entities on a device made for it, as for any target on none. When the
    boiler is added again they are on its device, and the made one is gone."""
    entry = await setup_target()
    await fake_target.delete()
    await restart_after(hass, freezer, entry, minutes=5)
    (made,) = {e.device_id for e in timer_entities(hass, entry)}
    assert made not in (None, fake_target.device_id)
    assert target_deleted_issue(hass, entry) is not None

    await fake_target.restore()

    assert {e.device_id for e in timer_entities(hass, entry)} == {fake_target.device_id}
    assert dr.async_get(hass).async_get(made) is None
    assert target_deleted_issue(hass, entry) is None


@pytest.mark.parametrize("reported", ["on", "off"])
async def test_a_report_queued_before_the_deletion_is_read_as_a_boiler_that_is_gone(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    reported: str,
) -> None:
    """The boiler reports while the timer is busy with a slow call of its own, and is
    deleted before the timer gets to the report. When the timer reads it the boiler is
    gone: the report does not end the repair, and a report of "off" does not make the
    timer send the turn-on that failed to a boiler that is not there."""
    entry = await setup_target()
    held = fake_target.hold_next_call()
    fake_target.fail_next_call()
    running = start_set_number(hass, NUMBER, 30)
    await held.reached.wait()
    # An attribute makes the write a change, which the timer follows. It waits for the
    # timer, which is busy.
    fake_target.write(reported, queued=1)
    er.async_get(hass).async_remove(TARGET_ID)
    hass.states.async_remove(TARGET_ID)

    held.release.set()
    await running
    await hass.async_block_till_done()

    assert target_deleted_issue(hass, entry) is not None
    assert fake_target.calls == [TURN_ON]


# --- The repair deletes the timer -----------------------------------------------------


async def test_the_repair_deletes_the_timer(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
    repairs: None,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user opens the repair and submits it: the timer goes, with its entities, its
    stored countdown and the repair itself."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 30)
    assert storage_key(entry) in hass_storage
    await fake_target.delete()
    client = await hass_client()
    issue = target_deleted_issue(hass, entry)
    assert issue is not None

    flow = await start_fix(client, issue.issue_id)

    assert flow["type"] == "form"
    assert flow["step_id"] == "confirm"
    assert flow["description_placeholders"] == {"timer": "Boiler", "target": TARGET_ID}

    done = await submit_fix(client, flow["flow_id"])

    assert done["type"] == "create_entry"
    assert hass.config_entries.async_get_entry(entry.entry_id) is None
    assert timer_entities(hass, entry) == []
    assert storage_key(entry) not in hass_storage
    assert target_deleted_issue(hass, entry) is None
    assert fake_target.calls == [TURN_ON]


async def test_deleting_the_timer_on_the_integration_page_clears_the_repair(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The user deletes the timer on its integration page instead of through the
    repair: no repair is left for a timer that is not there."""
    entry = await setup_target()
    await fake_target.delete()
    assert target_deleted_issue(hass, entry) is not None

    await hass.config_entries.async_remove(entry.entry_id)

    assert target_deleted_issue(hass, entry) is None


async def test_the_repair_of_a_timer_deleted_meanwhile_does_nothing(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    repairs: None,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user opens the repair, deletes the timer on its integration page, and then
    submits the open repair: it says the timer was already deleted."""
    entry = await setup_target()
    await fake_target.delete()
    client = await hass_client()
    issue = target_deleted_issue(hass, entry)
    assert issue is not None
    flow = await start_fix(client, issue.issue_id)
    await hass.config_entries.async_remove(entry.entry_id)

    done = await submit_fix(client, flow["flow_id"])

    assert done["type"] == "abort"
    assert done["reason"] == "timer_gone"


async def open_repair_dialog(
    hass: HomeAssistant, entry: ConfigEntry
) -> tuple[RepairsFlowManager, str]:
    """Open the repair of the timer's deleted target as the dialog does; return the
    manager of the fixes and the id of the flow, which shows the form."""
    issue = target_deleted_issue(hass, entry)
    assert issue is not None
    manager = repairs_flow_manager(hass)
    assert manager is not None
    flow = await manager.async_init(DOMAIN, context={"issue_id": issue.issue_id})
    assert flow["type"] == "form"
    return manager, flow["flow_id"]


async def test_a_repair_shown_again_after_its_timer_was_deleted_does_nothing(
    hass: HomeAssistant,
    repairs: None,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user opens the repair, the timer is deleted on its integration page, and the
    dialog asks for its step again: it says the timer is gone, rather than show a form
    with the names of the timer and the entity left blank."""
    entry = await setup_target()
    await fake_target.delete()
    manager, flow_id = await open_repair_dialog(hass, entry)
    await hass.config_entries.async_remove(entry.entry_id)

    shown_again = await manager.async_configure(flow_id, None)

    assert shown_again["type"] == "abort"
    assert shown_again["reason"] == "timer_gone"


async def test_a_repair_shown_again_after_the_boiler_is_back_does_nothing(
    hass: HomeAssistant,
    repairs: None,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user opens the repair, the device is added again, and the dialog asks for its
    step again: it says the problem is no longer open, and the timer is still there."""
    entry = await setup_target()
    await fake_target.delete()
    manager, flow_id = await open_repair_dialog(hass, entry)
    await fake_target.restore()

    shown_again = await manager.async_configure(flow_id, None)

    assert shown_again["type"] == "abort"
    assert shown_again["reason"] == "issue_gone"
    assert hass.config_entries.async_get_entry(entry.entry_id) is not None
