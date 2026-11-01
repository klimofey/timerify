"""The repairs of a timer: one whose target was deleted, one whose stored state cannot
be read, and a warning for a schedule interval whose settings the target does not take.

The scenarios are the user's: the boiler's entity is deleted in its settings, or its
whole device is, or Home Assistant starts without it. The timer stays loaded and
switches nothing, the repair says so, and the user either adds the device again, with
the same entity id, or submits the repair to delete the timer. When the file in which
the timer keeps its state is unreadable, the timer does not load, the repair says so,
and the user submits it to reset the file. When the air conditioner stops offering a
setting that an interval turns it on with, a warning names the interval and the setting
for as long as the air conditioner does not take it; it has nothing to submit.
"""

from http import HTTPStatus
from types import MappingProxyType
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.repairs import RepairsFlowManager, repairs_flow_manager
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryDisabler,
    ConfigEntryState,
    ConfigSubentry,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.translation import async_get_translations
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.typing import (
    ClientSessionGenerator,
    MockHAClientWebSocket,
    WebSocketGenerator,
)

from custom_components.timerify.const import DOMAIN
from custom_components.timerify.repairs import async_create_fix_flow
from custom_components.timerify.store import TimerStore

from .conftest import SWITCH_SERVICES, FakeTarget, ProvideTarget, SetupTarget
from .helpers import (
    AC_ATTRS,
    AC_ID,
    AC_WITHOUT_FAN_MODE,
    NUMBER,
    RUNTIME,
    SENSOR,
    SUNDAY,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    add_command,
    add_interval,
    advance,
    advance_to,
    at,
    command_json,
    edit_interval,
    iso,
    local,
    open_sunday,
    payload,
    reload_held_back,
    restart_after,
    retitle_interval,
    runtime_saved,
    saved,
    set_number,
    set_switch,
    start_set_number,
    state_of,
    storage_key,
    timerify_info,
    timerify_warnings,
    window_json,
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


def stored_timer_invalid_issue(
    hass: HomeAssistant, entry: ConfigEntry
) -> ir.IssueEntry | None:
    """The repair of the timer's unreadable stored state, if there is one."""
    return ir.async_get(hass).async_get_issue(
        DOMAIN, f"stored_timer_invalid_{entry.entry_id}"
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


async def open_dialog(
    hass: HomeAssistant, issue: ir.IssueEntry | None
) -> tuple[RepairsFlowManager, str]:
    """Open the repair `issue` as the dialog does; return the manager of the fixes and
    the id of the flow, which shows the form."""
    assert issue is not None
    manager = repairs_flow_manager(hass)
    assert manager is not None
    flow = await manager.async_init(DOMAIN, context={"issue_id": issue.issue_id})
    assert flow["type"] == "form"
    return manager, flow["flow_id"]


async def open_repair_dialog(
    hass: HomeAssistant, entry: ConfigEntry
) -> tuple[RepairsFlowManager, str]:
    """Open the repair of the timer's deleted target as the dialog does."""
    return await open_dialog(hass, target_deleted_issue(hass, entry))


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


# --- The repair resets a stored timer that cannot be read -----------------------------

UNFINISHED = "the timer is scheduled by an interval but has no end"
"""What the timer says of a file that names an interval but holds no end."""


async def test_a_stored_timer_that_cannot_be_read_raises_a_repair(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The file of the timer contradicts itself, as after a fault: the timer does not
    load, and the repair names the timer and says what is wrong."""
    entry = await setup_target(stored=payload(scheduled_by="a"))

    assert entry.state is ConfigEntryState.SETUP_ERROR
    issue = stored_timer_invalid_issue(hass, entry)
    assert issue is not None
    assert issue.translation_key == "stored_timer_invalid"
    assert issue.translation_placeholders == {"timer": "Boiler", "reason": UNFINISHED}
    assert issue.is_fixable
    assert issue.severity == ir.IssueSeverity.ERROR


async def test_a_stored_timer_missing_a_field_raises_the_same_repair(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A file that lacks a field is as unreadable as one that contradicts itself: the
    same repair, saying which field, and no bare KeyError in the log."""
    stored = payload()
    del stored["commands"]

    entry = await setup_target(stored=stored)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "stored_timer_invalid"
    issue = stored_timer_invalid_issue(hass, entry)
    assert issue is not None
    assert issue.translation_placeholders == {
        "timer": "Boiler",
        "reason": "the field commands is missing",
    }
    assert "KeyError" not in caplog.text


async def test_a_stored_field_of_the_wrong_type_raises_the_same_repair(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A field that holds something else than the timer writes is unreadable too: the
    same repair, with a reason, and no bare TypeError in the log."""
    entry = await setup_target(stored={**payload(), "commands": 5})

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "stored_timer_invalid"
    issue = stored_timer_invalid_issue(hass, entry)
    assert issue is not None
    assert issue.translation_placeholders is not None
    reason = issue.translation_placeholders["reason"]
    assert reason
    assert entry.reason is not None
    assert reason in entry.reason
    assert "TypeError" not in caplog.text


def without(item: dict[str, Any], field: str) -> dict[str, Any]:
    """`item` of a stored file with `field` left out."""
    return {key: value for key, value in item.items() if key != field}


@pytest.mark.parametrize(
    ("stored", "reason"),
    [
        pytest.param(
            payload(commands=[without(command_json(at(60), minutes=5), "minutes")]),
            "the field minutes of a pending command is missing",
            id="field-of-a-command",
        ),
        pytest.param(
            payload(
                windows=[
                    without(
                        window_json(
                            "a", local(SUNDAY, "06:30"), local(SUNDAY, "07:15")
                        ),
                        "end",
                    )
                ]
            ),
            "the field end of a schedule window is missing",
            id="field-of-a-window",
        ),
    ],
)
async def test_a_field_missing_inside_a_command_or_window_says_whose_it_is(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    stored: dict[str, Any],
    reason: str,
) -> None:
    """A file whose pending command or schedule window lacks a field is unreadable, and
    the repair says which item the field belongs to, not only its name."""
    entry = await setup_target(stored=stored)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    issue = stored_timer_invalid_issue(hass, entry)
    assert issue is not None
    assert issue.translation_placeholders == {"timer": "Boiler", "reason": reason}


async def test_resetting_the_stored_timer_keeps_the_entry_and_its_intervals(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    repairs: None,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The file of a timer with a switched-off interval and a runtime total is damaged
    while Home Assistant is down. The user submits the repair: the timer loads again
    with its interval, which is on, since the flag was in the file, no countdown, and
    the runtime total as it was."""
    entry = await setup_target(runtime=True, stored_runtime={"seconds": 600.0})
    interval = await add_interval(hass, entry, start="06:30", end="07:15")
    interval_switch = "switch.boiler_schedule_06_30_07_15_mon_sun"
    await set_switch(hass, interval_switch, False)

    def damage_the_file() -> None:
        hass_storage[storage_key(entry)]["data"] = payload(scheduled_by=interval)

    await restart_after(hass, freezer, entry, minutes=5, while_down=damage_the_file)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    client = await hass_client()
    issue = stored_timer_invalid_issue(hass, entry)
    assert issue is not None

    flow = await start_fix(client, issue.issue_id)

    assert flow["type"] == "form"
    assert flow["step_id"] == "confirm"
    assert flow["description_placeholders"] == {"timer": "Boiler", "reason": UNFINISHED}

    done = await submit_fix(client, flow["flow_id"])

    assert done["type"] == "create_entry"
    assert entry.state is ConfigEntryState.LOADED
    assert set(entry.subentries) == {interval}
    assert state_of(hass, interval_switch) == "on"
    assert state_of(hass, NUMBER) == "0"
    assert float(state_of(hass, RUNTIME)) == 10.0
    assert runtime_saved(hass_storage, entry) == 600.0
    assert stored_timer_invalid_issue(hass, entry) is None


async def test_a_stored_timer_that_is_put_right_clears_the_repair(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The file is put right by hand and the timer is reloaded: it loads, and the
    repair of a file that is fine again goes away."""
    entry = await setup_target(stored=payload(scheduled_by="a"))
    assert stored_timer_invalid_issue(hass, entry) is not None
    hass_storage[storage_key(entry)]["data"] = payload()

    await hass.config_entries.async_reload(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED
    assert stored_timer_invalid_issue(hass, entry) is None


async def test_deleting_a_timer_whose_stored_timer_cannot_be_read_clears_the_repair(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The user deletes the timer on its integration page instead of through the
    repair: no repair is left for a timer that is not there."""
    entry = await setup_target(stored=payload(scheduled_by="a"))
    assert stored_timer_invalid_issue(hass, entry) is not None

    await hass.config_entries.async_remove(entry.entry_id)

    assert stored_timer_invalid_issue(hass, entry) is None


async def test_the_reset_of_a_timer_deleted_meanwhile_does_nothing(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    repairs: None,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user opens the repair, deletes the timer on its integration page, and then
    submits the open repair: it says the timer was already deleted."""
    entry = await setup_target(stored=payload(scheduled_by="a"))
    client = await hass_client()
    issue = stored_timer_invalid_issue(hass, entry)
    assert issue is not None
    flow = await start_fix(client, issue.issue_id)
    await hass.config_entries.async_remove(entry.entry_id)

    done = await submit_fix(client, flow["flow_id"])

    assert done["type"] == "abort"
    assert done["reason"] == "timer_gone"


async def test_a_reset_shown_again_after_the_file_was_put_right_does_nothing(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    repairs: None,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user opens the repair, the file is put right and the timer is reloaded, and
    the dialog asks for its step again: it says the problem is no longer open, and the
    timer that loads is left as it is."""
    entry = await setup_target(stored=payload(scheduled_by="a"))
    manager, flow_id = await open_dialog(hass, stored_timer_invalid_issue(hass, entry))
    hass_storage[storage_key(entry)]["data"] = payload()
    await hass.config_entries.async_reload(entry.entry_id)

    shown_again = await manager.async_configure(flow_id, None)

    assert shown_again["type"] == "abort"
    assert shown_again["reason"] == "issue_gone"
    assert entry.state is ConfigEntryState.LOADED


async def test_a_delete_dialog_left_open_after_the_boiler_is_back_deletes_nothing(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    repairs: None,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user opens the repair of the deleted target in a second window. The device
    is added again, and the second window submits: the problem is no longer open, so
    the timer, which works again, is not deleted."""
    entry = await setup_target()
    await fake_target.delete()
    client = await hass_client()
    issue = target_deleted_issue(hass, entry)
    assert issue is not None
    flow = await start_fix(client, issue.issue_id)
    await fake_target.restore()
    assert target_deleted_issue(hass, entry) is None

    done = await submit_fix(client, flow["flow_id"])

    assert done["type"] == "abort"
    assert done["reason"] == "issue_gone"
    assert entry.state is ConfigEntryState.LOADED
    assert timer_entities(hass, entry) != []


async def test_a_reset_dialog_left_open_after_the_file_was_put_right_resets_nothing(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
    repairs: None,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user opens the repair of the unreadable file in a second window. The file is
    put right, the timer loads and runs a countdown, and the second window submits: the
    problem is no longer open, so the countdown is not reset."""
    entry = await setup_target(stored=payload(scheduled_by="a"))
    client = await hass_client()
    issue = stored_timer_invalid_issue(hass, entry)
    assert issue is not None
    flow = await start_fix(client, issue.issue_id)
    hass_storage[storage_key(entry)]["data"] = payload()
    await hass.config_entries.async_reload(entry.entry_id)
    await set_number(hass, NUMBER, 30)
    assert stored_timer_invalid_issue(hass, entry) is None

    done = await submit_fix(client, flow["flow_id"])

    assert done["type"] == "abort"
    assert done["reason"] == "issue_gone"
    assert entry.state is ConfigEntryState.LOADED
    assert state_of(hass, NUMBER) == "30"
    assert saved(hass_storage, entry)["end"] is not None
    assert fake_target.calls == [TURN_ON]


async def test_a_reset_after_which_the_timer_does_not_load_does_not_say_it_worked(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
    repairs: None,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The file is reset, but the timer cannot load for another reason: an interval by
    working days and no Workday sensor. The repair does not end as if it had worked: it
    says that the file is reset and the timer does not load, and the timer's own page
    has the reason."""
    entry = await setup_target(stored=payload(scheduled_by="a"))
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(
                {
                    "days": "workdays",
                    "weekdays": [],
                    "start": "06:30",
                    "end": "07:15",
                    "settings": {},
                }
            ),
            subentry_type="interval",
            title="06:30-07:15, Working days",
            unique_id=None,
        ),
    )
    client = await hass_client()
    issue = stored_timer_invalid_issue(hass, entry)
    assert issue is not None
    flow = await start_fix(client, issue.issue_id)

    done = await submit_fix(client, flow["flow_id"])

    assert done["type"] == "abort"
    assert done["reason"] == "reload_failed"
    assert storage_key(entry) not in hass_storage
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "workday_sensor_missing"


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(None, id="no-data"),
        pytest.param({"entry_id": "abc"}, id="no-kind"),
        pytest.param({"entry_id": "abc", "kind": "other"}, id="unknown-kind"),
    ],
)
async def test_an_issue_with_no_known_kind_has_no_fix(
    hass: HomeAssistant, data: dict[str, str | int | float | None] | None
) -> None:
    """Home Assistant asks for the fix of an issue by its id and data: data that names
    no kind of ours is refused in one way, not with a KeyError for a missing kind."""
    with pytest.raises(ValueError, match="has no fix"):
        await async_create_fix_flow(hass, "issue", data)


# --- The warning for settings the device no longer takes ------------------------------

COOL24 = {"hvac_mode": "cool", "temperature": 24}
COOL24_LOW = {**COOL24, "fan_mode": "low"}
NO_COOLING = ["off", "heat"]
"""The modes of an air conditioner whose integration stopped offering cooling."""


def settings_not_taken_issue(
    hass: HomeAssistant, entry: ConfigEntry, subentry_id: str
) -> ir.IssueEntry | None:
    """The warning of the interval, if there is one."""
    return ir.async_get(hass).async_get_issue(
        DOMAIN, f"settings_not_taken_{entry.entry_id}_{subentry_id}"
    )


def open_issues(hass: HomeAssistant) -> set[str]:
    """The ids of every issue Timerify has open."""
    return {
        issue.issue_id
        for issue in ir.async_get(hass).issues.values()
        if issue.domain == DOMAIN
    }


async def stop_offering_cooling(fake_climate: FakeTarget) -> None:
    """The air conditioner's integration is updated and no longer offers cooling."""
    fake_climate.capability_attributes["hvac_modes"] = NO_COOLING
    await fake_climate.set_state("off")


async def test_an_interval_setting_the_ac_no_longer_takes_raises_a_warning(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The AC stops offering cooling: Repairs shows a warning with nothing to submit,
    which names the interval and the setting."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )

    await stop_offering_cooling(fake_climate)

    issue = settings_not_taken_issue(hass, entry, subentry_id)
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING
    assert not issue.is_fixable
    assert issue.translation_key == "settings_not_taken"
    assert issue.translation_placeholders == {
        "timer": "Boiler",
        "interval": entry.subentries[subentry_id].title,
        "settings": "HVAC mode",
    }


async def test_the_warning_names_every_setting_the_ac_does_not_take(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """Cooling and the fan modes are both gone: the one warning of the interval names
    both settings, in the order the form lists them, and not the temperature."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24_LOW
    )

    fake_climate.capability_attributes["hvac_modes"] = NO_COOLING
    fake_climate.capability_attributes["supported_features"] = AC_WITHOUT_FAN_MODE
    await fake_climate.set_state("off")

    issue = settings_not_taken_issue(hass, entry, subentry_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["settings"] == "HVAC mode, Fan mode"


async def test_the_warning_follows_the_settings_the_ac_does_not_take(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The AC loses one setting, then another, then takes the first back: the warning
    names the ones it does not take at each moment."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24_LOW
    )

    async def named() -> str:
        issue = settings_not_taken_issue(hass, entry, subentry_id)
        assert issue is not None
        assert issue.translation_placeholders is not None
        return issue.translation_placeholders["settings"]

    await stop_offering_cooling(fake_climate)
    assert await named() == "HVAC mode"

    fake_climate.capability_attributes["supported_features"] = AC_WITHOUT_FAN_MODE
    await fake_climate.set_state("off")
    assert await named() == "HVAC mode, Fan mode"

    fake_climate.capability_attributes["hvac_modes"] = AC_ATTRS["hvac_modes"]
    await fake_climate.set_state("off")
    assert await named() == "Fan mode"


async def test_a_value_the_ac_no_longer_accepts_raises_the_warning(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The AC still has a temperature but takes a narrower range: 24 degrees is out of
    it, and the window would leave it out, so the warning names it."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )

    fake_climate.capability_attributes["max_temp"] = 22
    await fake_climate.set_state("off")

    issue = settings_not_taken_issue(hass, entry, subentry_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["settings"] == "Temperature"


async def test_only_the_interval_that_has_the_lost_setting_is_named(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """Each interval has its own warning, and an interval whose settings the AC still
    takes has none."""
    entry = await setup_target(target=AC_ID)
    cooling = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )
    heating = await add_interval(
        hass,
        entry,
        start="18:00",
        end="19:00",
        settings={"hvac_mode": "heat", "temperature": 22},
    )
    plain = await add_interval(hass, entry, start="12:00", end="13:00")

    await stop_offering_cooling(fake_climate)

    assert settings_not_taken_issue(hass, entry, cooling) is not None
    assert settings_not_taken_issue(hass, entry, heating) is None
    assert settings_not_taken_issue(hass, entry, plain) is None


async def test_the_warning_names_the_settings_in_the_language_of_the_house(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The settings are called what the form calls them in the house's language."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24_LOW
    )
    hass.config.language = "ru"
    texts = await async_get_translations(hass, "ru", "config_subentries", [DOMAIN])
    prefix = f"component.{DOMAIN}.config_subentries.interval.step.user"
    names = [
        texts[f"{prefix}.sections.settings.data.{n}"] for n in ("hvac_mode", "fan_mode")
    ]
    assert names != ["HVAC mode", "Fan mode"]

    fake_climate.capability_attributes["hvac_modes"] = NO_COOLING
    fake_climate.capability_attributes["supported_features"] = AC_WITHOUT_FAN_MODE
    await fake_climate.set_state("off")

    issue = settings_not_taken_issue(hass, entry, subentry_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["settings"] == ", ".join(names)


async def test_the_warning_clears_when_the_ac_takes_the_setting_again(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The integration offers cooling again: the interval is used as it was, and the
    warning goes away by itself."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )
    await stop_offering_cooling(fake_climate)
    assert settings_not_taken_issue(hass, entry, subentry_id) is not None

    fake_climate.capability_attributes["hvac_modes"] = AC_ATTRS["hvac_modes"]
    await fake_climate.set_state("off")

    assert settings_not_taken_issue(hass, entry, subentry_id) is None


async def test_the_warning_clears_when_the_interval_no_longer_holds_it(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The user opens the interval and picks a mode the AC takes: the warning goes."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )
    await stop_offering_cooling(fake_climate)
    assert settings_not_taken_issue(hass, entry, subentry_id) is not None

    await edit_interval(
        hass, entry, subentry_id, settings={"hvac_mode": "heat", "temperature": 24}
    )

    assert settings_not_taken_issue(hass, entry, subentry_id) is None


async def test_the_warning_stands_after_editing_an_interval_it_does_not_concern(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The edit reloads the timer, and the start-up judges the interval again: a
    setting the form does not show is kept by the edit, and still warned about."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24_LOW
    )
    fake_climate.capability_attributes["supported_features"] = AC_WITHOUT_FAN_MODE
    await fake_climate.set_state("off")

    await edit_interval(hass, entry, subentry_id, end="07:30")

    issue = settings_not_taken_issue(hass, entry, subentry_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["settings"] == "Fan mode"


async def test_deleting_the_interval_clears_its_warning(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """Deleting the interval drops a setting the form no longer shows, and its
    warning with it."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )
    await stop_offering_cooling(fake_climate)
    assert settings_not_taken_issue(hass, entry, subentry_id) is not None

    hass.config_entries.async_remove_subentry(entry, subentry_id)
    await hass.async_block_till_done()

    assert settings_not_taken_issue(hass, entry, subentry_id) is None


async def test_a_report_before_the_reload_raises_no_warning_for_a_deleted_interval(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The user deletes an interval, and the AC stops offering cooling before the timer
    has reloaded: the interval that is gone gets no warning, the one that is left
    does."""
    entry = await setup_target(target=AC_ID)
    gone = await add_interval(hass, entry, start="06:30", end="07:15", settings=COOL24)
    left = await add_interval(hass, entry, start="18:00", end="19:00", settings=COOL24)

    async with reload_held_back(entry):
        hass.config_entries.async_remove_subentry(entry, gone)
        fake_climate.capability_attributes["hvac_modes"] = NO_COOLING
        fake_climate.write("off")

        assert open_issues(hass) == {f"settings_not_taken_{entry.entry_id}_{left}"}


async def test_a_setting_lost_while_down_raises_the_warning_at_start_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The AC's integration is updated while Home Assistant is down: the timer that is
    set up again warns at once, without waiting for the AC to report."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )

    def update_the_ac() -> None:
        fake_climate.capability_attributes["hvac_modes"] = NO_COOLING
        fake_climate.write("off")

    await restart_after(hass, freezer, entry, minutes=5, while_down=update_the_ac)

    assert settings_not_taken_issue(hass, entry, subentry_id) is not None


async def test_an_unavailable_ac_raises_no_settings_warning(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """An AC that is away still says what it can do, and takes the settings: nothing
    is wrong with the interval."""
    entry = await setup_target(target=AC_ID)
    await add_interval(hass, entry, start="06:30", end="07:15", settings=COOL24)

    await fake_climate.set_state("unavailable")

    assert open_issues(hass) == set()


async def test_a_deleted_ac_raises_no_settings_warning(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """With the AC deleted only the repair of the deleted device speaks for the timer;
    the warning is back when the AC is."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )
    await stop_offering_cooling(fake_climate)
    assert settings_not_taken_issue(hass, entry, subentry_id) is not None

    await fake_climate.delete()

    assert open_issues(hass) == {f"target_deleted_{entry.entry_id}"}

    await fake_climate.restore("off")

    assert settings_not_taken_issue(hass, entry, subentry_id) is not None
    assert target_deleted_issue(hass, entry) is None


async def test_the_warnings_of_a_timer_go_with_it(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """Deleting the timer takes every warning of its intervals away."""
    entry = await setup_target(target=AC_ID)
    await add_interval(hass, entry, start="06:30", end="07:15", settings=COOL24)
    await add_interval(hass, entry, start="18:00", end="19:00", settings=COOL24)
    await stop_offering_cooling(fake_climate)
    assert len(open_issues(hass)) == 2

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert open_issues(hass) == set()


async def listed_warnings(client: MockHAClientWebSocket) -> dict[str, bool]:
    """What the Repairs page lists of the warnings of intervals, by issue id: whether
    the user ignored it."""
    await client.send_json_auto_id({"type": "repairs/list_issues"})
    listed = (await client.receive_json())["result"]["issues"]
    return {
        issue["issue_id"]: issue["ignored"]
        for issue in listed
        if issue["domain"] == DOMAIN
        and issue["translation_key"] == "settings_not_taken"
    }


async def ignore_issue(client: MockHAClientWebSocket, issue_id: str) -> None:
    """Choose "Ignore" on an issue of the Repairs page."""
    await client.send_json_auto_id(
        {
            "type": "repairs/ignore_issue",
            "domain": DOMAIN,
            "issue_id": issue_id,
            "ignore": True,
        }
    )
    assert (await client.receive_json())["success"]


@pytest.mark.parametrize("state", ["unavailable", "unknown"])
async def test_an_ac_that_goes_offline_without_capabilities_raises_no_warning(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget, state: str
) -> None:
    """The AC drops its modes and features with its connection. They are unknown, not
    lost: nothing is sent to it meanwhile, so the interval gets no warning."""
    entry = await setup_target(target=AC_ID)
    await add_interval(hass, entry, start="06:30", end="07:15", settings=COOL24)

    fake_climate.capability_attributes = {}
    await fake_climate.set_state(state)

    assert open_issues(hass) == set()


async def test_the_warning_stands_while_the_ac_is_offline_until_it_reports(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """A warning is neither cleared nor changed by an AC that is away without its
    capabilities. It is judged again when the AC reports, and goes if the AC takes the
    setting."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )
    await stop_offering_cooling(fake_climate)
    warned = settings_not_taken_issue(hass, entry, subentry_id)
    assert warned is not None

    fake_climate.capability_attributes = {}
    await fake_climate.set_state("unavailable")
    assert settings_not_taken_issue(hass, entry, subentry_id) == warned

    fake_climate.capability_attributes = dict(AC_ATTRS)
    await fake_climate.set_state("off")
    assert settings_not_taken_issue(hass, entry, subentry_id) is None


async def test_the_titles_of_two_warnings_of_a_timer_tell_the_intervals_apart(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The Repairs page lists the titles, so each names its interval."""
    entry = await setup_target(target=AC_ID)
    morning = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )
    evening = await add_interval(
        hass, entry, start="18:00", end="19:00", settings=COOL24
    )
    await stop_offering_cooling(fake_climate)
    texts = await async_get_translations(hass, "en", "issues", [DOMAIN])

    titles = []
    for subentry_id in (morning, evening):
        issue = settings_not_taken_issue(hass, entry, subentry_id)
        assert issue is not None
        assert issue.translation_placeholders is not None
        titles.append(
            texts[f"component.{DOMAIN}.issues.settings_not_taken.title"].format(
                **issue.translation_placeholders
            )
        )

    assert titles == [
        'The schedule interval "06:30–07:15, Mon–Sun" of the timer "Boiler"'
        " has settings the device does not take",
        'The schedule interval "18:00–19:00, Mon–Sun" of the timer "Boiler"'
        " has settings the device does not take",
    ]


async def test_renaming_an_interval_renames_its_warning(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The user renames the interval on the integration page: the timer reloads, and
    the warning names the interval as it is called now."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )
    await stop_offering_cooling(fake_climate)

    await retitle_interval(hass, entry, subentry_id, "Morning cooling")

    issue = settings_not_taken_issue(hass, entry, subentry_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["interval"] == "Morning cooling"


async def test_the_warning_names_the_settings_in_the_order_of_the_form(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The AC stops offering the HVAC modes, and an edit stores the setting the form no
    longer shows after the ones it shows. The AC then stops taking the fan mode too.
    The warning lists them as the form does, the HVAC mode first, not as they are
    stored."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24_LOW
    )
    del fake_climate.capability_attributes["hvac_modes"]
    await fake_climate.set_state("off")
    await edit_interval(hass, entry, subentry_id, end="07:30")
    assert list(entry.subentries[subentry_id].data["settings"]) == [
        "temperature",
        "fan_mode",
        "hvac_mode",
    ]

    fake_climate.capability_attributes["fan_modes"] = ["auto", "high"]
    await fake_climate.set_state("off")

    issue = settings_not_taken_issue(hass, entry, subentry_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["settings"] == "HVAC mode, Fan mode"


async def test_an_ignored_warning_stays_ignored_after_a_reload(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    repairs: None,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user keeps the lost setting on purpose and chooses Ignore. Any change of an
    interval, an options change or a reload reloads the timer, and the warning stays
    ignored through it."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )
    await stop_offering_cooling(fake_climate)
    client = await hass_ws_client(hass)
    key = f"settings_not_taken_{entry.entry_id}_{subentry_id}"
    await ignore_issue(client, key)

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert await listed_warnings(client) == {key: True}


async def test_a_warning_that_went_away_comes_back_unignored(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    repairs: None,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """An ignored warning is for the setting being lost. The AC takes it back, and when
    it loses it again the user is told again."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )
    await stop_offering_cooling(fake_climate)
    client = await hass_ws_client(hass)
    key = f"settings_not_taken_{entry.entry_id}_{subentry_id}"
    await ignore_issue(client, key)

    fake_climate.capability_attributes["hvac_modes"] = AC_ATTRS["hvac_modes"]
    await fake_climate.set_state("off")
    assert await listed_warnings(client) == {}
    await stop_offering_cooling(fake_climate)

    assert await listed_warnings(client) == {key: False}


async def test_a_warning_of_an_interval_deleted_while_down_is_gone_at_start_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The warning outlives a restart of Home Assistant. The interval is deleted while
    the timer is not loaded, so no reload follows: the next load takes its warning away
    and keeps the other."""
    entry = await setup_target(target=AC_ID)
    gone = await add_interval(hass, entry, start="06:30", end="07:15", settings=COOL24)
    left = await add_interval(hass, entry, start="18:00", end="19:00", settings=COOL24)
    await stop_offering_cooling(fake_climate)
    assert len(open_issues(hass)) == 2

    def delete_the_interval() -> None:
        hass.config_entries.async_remove_subentry(entry, gone)

    await restart_after(
        hass,
        freezer,
        entry,
        minutes=5,
        issues_reloaded=True,
        while_down=delete_the_interval,
    )

    assert open_issues(hass) == {f"settings_not_taken_{entry.entry_id}_{left}"}


async def test_a_warning_the_ac_takes_back_while_down_is_gone_at_start_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The AC's integration is updated while Home Assistant is down and offers cooling
    again: the warning that outlived the restart is taken away at start-up."""
    entry = await setup_target(target=AC_ID)
    await add_interval(hass, entry, start="06:30", end="07:15", settings=COOL24)
    await stop_offering_cooling(fake_climate)
    assert len(open_issues(hass)) == 1

    def update_the_ac() -> None:
        fake_climate.capability_attributes["hvac_modes"] = AC_ATTRS["hvac_modes"]
        fake_climate.write("off")

    await restart_after(
        hass, freezer, entry, minutes=5, issues_reloaded=True, while_down=update_the_ac
    )

    assert open_issues(hass) == set()


async def test_disabling_the_timer_takes_its_warnings_away(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """A disabled timer is not loaded again, so its warnings do not outlive it."""
    entry = await setup_target(target=AC_ID)
    await add_interval(hass, entry, start="06:30", end="07:15", settings=COOL24)
    await stop_offering_cooling(fake_climate)
    assert len(open_issues(hass)) == 1

    await hass.config_entries.async_set_disabled_by(
        entry.entry_id, ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()

    assert open_issues(hass) == set()


def corrupt_stored_timer(hass_storage: dict[str, Any], entry: ConfigEntry) -> None:
    """Leave the file of the timer in a state that contradicts itself, as after a
    fault."""
    key = storage_key(entry)
    hass_storage[key] = {
        "version": TimerStore.STORAGE_VERSION,
        "minor_version": 1,
        "key": key,
        "data": payload(scheduled_by="a"),
    }


async def test_a_timer_that_cannot_read_its_file_has_no_settings_warning(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The warnings outlive an unload, so a reload that fails must take them away: a
    timer that does not load turns nothing on. When the file is put right and the timer
    loads again, the warning is raised again."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )
    await stop_offering_cooling(fake_climate)
    assert settings_not_taken_issue(hass, entry, subentry_id) is not None
    corrupt_stored_timer(hass_storage, entry)

    await hass.config_entries.async_reload(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert open_issues(hass) == {f"stored_timer_invalid_{entry.entry_id}"}

    hass_storage[storage_key(entry)]["data"] = payload()
    await hass.config_entries.async_reload(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED
    assert settings_not_taken_issue(hass, entry, subentry_id) is not None


async def test_a_timer_that_cannot_set_up_has_no_settings_warning(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The user adds an interval by working days to a timer that has no Workday sensor.
    The timer does not set up, and the warning of its other interval goes."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )
    await stop_offering_cooling(fake_climate)
    assert settings_not_taken_issue(hass, entry, subentry_id) is not None

    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(
                {
                    "days": "workdays",
                    "weekdays": [],
                    "start": "18:00",
                    "end": "19:00",
                    "settings": {},
                }
            ),
            subentry_type="interval",
            title="18:00-19:00, Working days",
            unique_id=None,
        ),
    )
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "workday_sensor_missing"
    assert open_issues(hass) == set()


async def test_an_ignored_warning_returns_when_another_setting_is_lost(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    repairs: None,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user ignored the warning about the HVAC mode. The AC stops taking the fan
    mode too: the warning is shown again, naming both, so the Ignore does not hide the
    new setting."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24_LOW
    )
    await stop_offering_cooling(fake_climate)
    client = await hass_ws_client(hass)
    key = f"settings_not_taken_{entry.entry_id}_{subentry_id}"
    await ignore_issue(client, key)
    assert await listed_warnings(client) == {key: True}

    fake_climate.capability_attributes["supported_features"] = AC_WITHOUT_FAN_MODE
    await fake_climate.set_state("off")

    assert await listed_warnings(client) == {key: False}
    issue = settings_not_taken_issue(hass, entry, subentry_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["settings"] == "HVAC mode, Fan mode"


async def test_an_ignored_warning_stays_ignored_when_a_setting_comes_back(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    repairs: None,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user ignored the warning about two settings. The AC takes one back: the
    warning is updated to name the other and stays ignored."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24_LOW
    )
    fake_climate.capability_attributes["hvac_modes"] = NO_COOLING
    fake_climate.capability_attributes["supported_features"] = AC_WITHOUT_FAN_MODE
    await fake_climate.set_state("off")
    client = await hass_ws_client(hass)
    key = f"settings_not_taken_{entry.entry_id}_{subentry_id}"
    await ignore_issue(client, key)

    fake_climate.capability_attributes["hvac_modes"] = AC_ATTRS["hvac_modes"]
    await fake_climate.set_state("off")

    assert await listed_warnings(client) == {key: True}
    issue = settings_not_taken_issue(hass, entry, subentry_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["settings"] == "Fan mode"


async def test_a_setting_lost_while_down_returns_an_ignored_warning(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_ws_client: WebSocketGenerator,
    repairs: None,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user ignored the warning about the HVAC mode. Home Assistant restarts, and
    the fan mode is lost while it is down: the warning comes back, naming both, and
    the Ignore does not hide it."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24_LOW
    )
    await stop_offering_cooling(fake_climate)
    client = await hass_ws_client(hass)
    key = f"settings_not_taken_{entry.entry_id}_{subentry_id}"
    await ignore_issue(client, key)

    def lose_the_fan_mode() -> None:
        fake_climate.capability_attributes["supported_features"] = AC_WITHOUT_FAN_MODE
        fake_climate.write("off")

    await restart_after(
        hass,
        freezer,
        entry,
        minutes=5,
        issues_reloaded=True,
        while_down=lose_the_fan_mode,
    )

    assert await listed_warnings(client) == {key: False}
    issue = settings_not_taken_issue(hass, entry, subentry_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["settings"] == "HVAC mode, Fan mode"


async def test_renaming_an_interval_keeps_the_ignore_of_its_warning(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    repairs: None,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The settings are the same, so the warning is updated in place: it names the
    interval by its new title and stays ignored."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )
    await stop_offering_cooling(fake_climate)
    client = await hass_ws_client(hass)
    key = f"settings_not_taken_{entry.entry_id}_{subentry_id}"
    await ignore_issue(client, key)

    await retitle_interval(hass, entry, subentry_id, "Morning cooling")

    assert await listed_warnings(client) == {key: True}
    issue = settings_not_taken_issue(hass, entry, subentry_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["interval"] == "Morning cooling"


async def test_an_ignored_warning_survives_a_restart_of_home_assistant(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_ws_client: WebSocketGenerator,
    repairs: None,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user ignored the warning. Home Assistant restarts and the AC still lacks the
    same settings: the warning is still ignored."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24_LOW
    )
    fake_climate.capability_attributes["hvac_modes"] = NO_COOLING
    fake_climate.capability_attributes["supported_features"] = AC_WITHOUT_FAN_MODE
    await fake_climate.set_state("off")
    client = await hass_ws_client(hass)
    key = f"settings_not_taken_{entry.entry_id}_{subentry_id}"
    await ignore_issue(client, key)

    await restart_after(hass, freezer, entry, minutes=5, issues_reloaded=True)

    assert await listed_warnings(client) == {key: True}


async def test_an_ignored_warning_stays_ignored_when_a_setting_returns_while_down(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_ws_client: WebSocketGenerator,
    repairs: None,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user ignored the warning about two settings. Home Assistant restarts, and
    the AC takes one back meanwhile: the warning names the other and stays ignored."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24_LOW
    )
    fake_climate.capability_attributes["hvac_modes"] = NO_COOLING
    fake_climate.capability_attributes["supported_features"] = AC_WITHOUT_FAN_MODE
    await fake_climate.set_state("off")
    client = await hass_ws_client(hass)
    key = f"settings_not_taken_{entry.entry_id}_{subentry_id}"
    await ignore_issue(client, key)

    def take_the_hvac_mode_back() -> None:
        fake_climate.capability_attributes["hvac_modes"] = AC_ATTRS["hvac_modes"]
        fake_climate.write("off")

    await restart_after(
        hass,
        freezer,
        entry,
        minutes=5,
        issues_reloaded=True,
        while_down=take_the_hvac_mode_back,
    )

    assert await listed_warnings(client) == {key: True}
    issue = settings_not_taken_issue(hass, entry, subentry_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["settings"] == "Fan mode"


async def test_a_warning_stays_shown_after_a_restart_with_the_ac_offline(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_ws_client: WebSocketGenerator,
    repairs: None,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Home Assistant restarts while the AC is away. The warning is shown from the first
    moment, with the settings it last named, and goes when the AC takes them again."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )
    await stop_offering_cooling(fake_climate)
    client = await hass_ws_client(hass)
    key = f"settings_not_taken_{entry.entry_id}_{subentry_id}"

    await restart_after(
        hass,
        freezer,
        entry,
        minutes=5,
        issues_reloaded=True,
        while_down=lambda: fake_climate.write("unavailable"),
    )

    assert await listed_warnings(client) == {key: False}
    issue = settings_not_taken_issue(hass, entry, subentry_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["settings"] == "HVAC mode"

    fake_climate.capability_attributes = dict(AC_ATTRS)
    await fake_climate.set_state("off")

    assert await listed_warnings(client) == {}


async def test_an_ignored_warning_survives_a_restart_with_the_ac_offline(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_ws_client: WebSocketGenerator,
    repairs: None,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Home Assistant restarts while the AC is away. The warning is shown, still
    ignored, and the AC that reports the same loss does not bring it back."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )
    await stop_offering_cooling(fake_climate)
    client = await hass_ws_client(hass)
    key = f"settings_not_taken_{entry.entry_id}_{subentry_id}"
    await ignore_issue(client, key)

    await restart_after(
        hass,
        freezer,
        entry,
        minutes=5,
        issues_reloaded=True,
        while_down=lambda: fake_climate.write("unavailable"),
    )

    assert await listed_warnings(client) == {key: True}

    await fake_climate.set_state("off")

    assert await listed_warnings(client) == {key: True}


async def test_a_setting_lost_while_the_ac_is_offline_shows_an_ignored_warning(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_ws_client: WebSocketGenerator,
    repairs: None,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Home Assistant restarts while the AC is away, and the AC reports with one more
    setting lost. The warning names both, and the Ignore does not hide it."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24_LOW
    )
    await stop_offering_cooling(fake_climate)
    client = await hass_ws_client(hass)
    key = f"settings_not_taken_{entry.entry_id}_{subentry_id}"
    await ignore_issue(client, key)
    await restart_after(
        hass,
        freezer,
        entry,
        minutes=5,
        issues_reloaded=True,
        while_down=lambda: fake_climate.write("unavailable"),
    )

    fake_climate.capability_attributes["supported_features"] = AC_WITHOUT_FAN_MODE
    await fake_climate.set_state("off")

    assert await listed_warnings(client) == {key: False}
    issue = settings_not_taken_issue(hass, entry, subentry_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["settings"] == "HVAC mode, Fan mode"


async def test_an_interval_renamed_while_the_ac_is_offline_renames_its_warning(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """What the device does not take waits for the device, but the title of the
    interval does not: the warning names the interval as it is called now."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )
    await stop_offering_cooling(fake_climate)
    await fake_climate.set_state("unavailable")

    await retitle_interval(hass, entry, subentry_id, "Morning cooling")

    issue = settings_not_taken_issue(hass, entry, subentry_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["interval"] == "Morning cooling"
    assert issue.translation_placeholders["settings"] == "HVAC mode"


async def test_a_setting_dropped_from_an_interval_leaves_its_warning_while_offline(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The AC is away and the user edits the interval: the HVAC mode is dropped from
    it, and the warning stops naming it, without waiting for the AC. The fan mode,
    which the form does not show, is kept and still named."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24_LOW
    )
    fake_climate.capability_attributes["hvac_modes"] = NO_COOLING
    fake_climate.capability_attributes["supported_features"] = AC_WITHOUT_FAN_MODE
    await fake_climate.set_state("off")
    await fake_climate.set_state("unavailable")

    await edit_interval(hass, entry, subentry_id, settings={"temperature": 24})

    issue = settings_not_taken_issue(hass, entry, subentry_id)
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["settings"] == "Fan mode"


async def test_an_interval_left_with_no_setting_loses_its_warning_while_offline(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The AC is away and the user empties the settings of the interval: nothing is
    left to warn about."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=COOL24
    )
    await stop_offering_cooling(fake_climate)
    await fake_climate.set_state("unavailable")

    await edit_interval(hass, entry, subentry_id, settings={})

    assert open_issues(hass) == set()
