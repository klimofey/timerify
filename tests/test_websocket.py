"""The dashboard card finds its timer by asking Timerify.

The card is configured with the "Run for" number of a timer and asks `timerify/timer`
which target it belongs to, which entities are its own and what counts as on for the
target. The answer is configuration, read from the registry and the entry, so it does
not depend on whether the timer is running, loaded or even set up. Every scenario asks
through a real websocket connection, as the dashboard does.
"""

from typing import Any

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser
from pytest_homeassistant_custom_component.typing import (
    MockHAClientWebSocket,
    WebSocketGenerator,
)

from custom_components.timerify.const import (
    CONF_KIND,
    CONF_TARGET,
    DOMAIN,
    KIND_VOICE_SETTINGS,
    VOICE_UNIQUE_ID,
)
from custom_components.timerify.store import TimerStore

from .conftest import SWITCH_SERVICES, FakeTarget, ProvideTarget, SetupTarget
from .helpers import (
    AC_ENDS_AT,
    AC_ID,
    AC_NEXT,
    AC_NUMBER,
    NEXT,
    NUMBER,
    SENSOR,
    TARGET_ID,
    add_interval,
    at,
    payload,
    retitle_interval,
    storage_key,
)

pytestmark = pytest.mark.usefixtures("hass_storage")

EVENING_SWITCH = "switch.boiler_schedule_18_00_19_00_mon_sun"
"""The switch of the interval from 18:00 to 19:00 on every day, which is not open at the
time the scenarios start."""
NIGHT_SWITCH = "switch.boiler_schedule_20_00_21_00_mon_sun"
"""The switch of the interval from 20:00 to 21:00 on every day."""

GONE_FROM_REGISTRY = "0123456789abcdef0123456789abcdef"
"""A registry id that belongs to no entity."""

NO_OFFSET = "2026-01-05T07:00:00"
"""A time as a file that no timer wrote might hold it: no offset to tell it by."""


@pytest.fixture
async def client(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> MockHAClientWebSocket:
    """The dashboard's connection, of an admin.

    Timerify is set up first. Setting it up adds the card to the web server's routes,
    and the test server closes the routes when the first connection is made, which the
    web server of Home Assistant does not: it takes the routes of integrations that are
    set up after it has started.
    """
    await async_setup_component(hass, DOMAIN, {})
    return await hass_ws_client(hass)


@pytest.fixture
async def read_only_client(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_user: MockUser,
    hass_read_only_access_token: str,
) -> MockHAClientWebSocket:
    """The dashboard's connection, of a user who is not an admin: the read-only group,
    which may read every entity. Timerify is set up first, as for `client`."""
    assert not hass_read_only_user.is_admin
    await async_setup_component(hass, DOMAIN, {})
    return await hass_ws_client(hass, hass_read_only_access_token)


async def ask(client: MockHAClientWebSocket, entity_id: str) -> dict[str, Any]:
    """Ask Timerify which timer the "Run for" number `entity_id` belongs to; return the
    message that comes back, the result or the error."""
    await client.send_json_auto_id({"type": "timerify/timer", "entity_id": entity_id})
    message: dict[str, Any] = await client.receive_json()
    return message


async def found(client: MockHAClientWebSocket, entity_id: str) -> dict[str, Any]:
    """What Timerify tells about the timer of `entity_id`, which it must be able to."""
    message = await ask(client, entity_id)
    assert message["success"] is True, message
    result: dict[str, Any] = message["result"]
    return result


async def refused(client: MockHAClientWebSocket, entity_id: str) -> dict[str, Any]:
    """The error Timerify answers with when `entity_id` is not a timer's number."""
    message = await ask(client, entity_id)
    assert message["success"] is False, message
    error: dict[str, Any] = message["error"]
    return error


def not_a_timer(entity_id: str) -> dict[str, str]:
    """The error for an entity that is not the "Run for" number of a timer."""
    return {
        "code": "not_found",
        "message": f"{entity_id} is not the Run for number of a Timerify timer",
    }


def told_about(entry: MockConfigEntry, **different: Any) -> dict[str, Any]:
    """What Timerify tells about the boiler's timer, for a timer that is set up with
    the defaults of the scenarios; `different` changes what the scenario changes."""
    return {
        "entry_id": entry.entry_id,
        "target": TARGET_ID,
        "mode": "strict",
        "default_duration": 45,
        "ends_at": SENSOR,
        "next_command": NEXT,
        "intervals": [],
        "target_on": {"match": "is", "states": ["on"]},
        **different,
    }


# --- Finding the timer --------------------------------------------------------------


async def test_card_finds_the_timer_of_its_number(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Given the "Run for" number, Timerify names the entry, the target, how the timer
    is bound, its sensors and what counts as on for the target."""
    entry = await setup_target()

    message = await ask(client, NUMBER)

    assert message["success"] is True
    assert message["result"] == {
        "entry_id": entry.entry_id,
        "target": "switch.boiler",
        "mode": "strict",
        "default_duration": 45,
        "ends_at": "sensor.boiler_ends_at",
        "next_command": "sensor.boiler_next_command",
        "intervals": [],
        "target_on": {"match": "is", "states": ["on"]},
    }


async def test_command_waits_for_a_websocket_api_that_comes_later(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    hass_ws_client: WebSocketGenerator,
    setup_target: SetupTarget,
) -> None:
    """Timerify does not depend on the websocket API, so a timer may be set up before
    it: the command is there when the first connection comes."""
    entry = await setup_target()
    assert "websocket_api" not in hass.config.components
    client = await hass_ws_client(hass)

    assert await found(client, NUMBER) == told_about(entry)


async def test_loose_timer_has_no_default_duration(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A loose timer runs without a duration, so there is none to offer, whatever an
    earlier strict setup left in the options."""
    entry = await setup_target(mode="loose", default_duration=45)

    assert await found(client, NUMBER) == told_about(
        entry, mode="loose", default_duration=None
    )


async def test_intervals_are_listed_with_their_titles(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Each schedule interval is told with the switch that enables it and the title
    the user gave it, in the order they were added."""
    entry = await setup_target()
    evening = await add_interval(hass, entry, start="18:00", end="19:00")
    night = await add_interval(hass, entry, start="20:00", end="21:00")
    await retitle_interval(hass, entry, evening, "Evening")
    await retitle_interval(hass, entry, night, "Night")

    result = await found(client, NUMBER)

    assert result["intervals"] == [
        {"entity_id": EVENING_SWITCH, "title": "Evening"},
        {"entity_id": NIGHT_SWITCH, "title": "Night"},
    ]


async def test_climate_target_says_what_counts_as_on(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A thermostat is on in any mode but off, which the card cannot guess from its
    states: Timerify says it."""
    entry = await setup_target(target=AC_ID)

    assert await found(client, AC_NUMBER) == told_about(
        entry,
        target=AC_ID,
        ends_at=AC_ENDS_AT,
        next_command=AC_NEXT,
        target_on={"match": "is_not", "states": ["off"]},
    )


async def test_media_player_target_says_that_standby_is_off(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_media_player: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A player in standby is off, and the states of the rule come in a fixed order."""
    entry = await setup_target(target="media_player.tv")

    assert await found(client, "number.tv_run_for") == told_about(
        entry,
        target="media_player.tv",
        ends_at="sensor.tv_ends_at",
        next_command="sensor.tv_next_command",
        target_on={"match": "is_not", "states": ["off", "standby"]},
    )


@pytest.mark.parametrize("fake_target", [False], indirect=True)
async def test_target_without_a_device_is_found(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A target on no device has nothing to find its timer through: the entities of the
    timer are on a device Timerify made, and are told by what they are."""
    entry = await setup_target()

    assert await found(client, NUMBER) == told_about(entry)
    registry = er.async_get(hass)
    assert (target := registry.async_get(TARGET_ID)) is not None
    assert target.device_id is None
    assert (number := registry.async_get(NUMBER)) is not None
    assert number.device_id is not None


async def test_two_timers_on_one_device_are_told_apart(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    provide_target: ProvideTarget,
    setup_target: SetupTarget,
) -> None:
    """Two targets of one device have a timer each, and their entities are on that one
    device: each number answers with its own timer, its own target and its own
    sensors and intervals, never those of the other."""
    pump = provide_target("switch.pump", SWITCH_SERVICES, name="Pump")
    er.async_get(hass).async_update_entity(
        pump.entity_id, device_id=fake_target.device_id
    )
    boiler_entry = await setup_target()
    pump_entry = await setup_target(target=pump.entity_id)
    evening = await add_interval(hass, boiler_entry, start="18:00", end="19:00")
    night = await add_interval(hass, pump_entry, start="20:00", end="21:00")
    await retitle_interval(hass, boiler_entry, evening, "Evening")
    await retitle_interval(hass, pump_entry, night, "Night")

    assert await found(client, NUMBER) == told_about(
        boiler_entry, intervals=[{"entity_id": EVENING_SWITCH, "title": "Evening"}]
    )
    assert await found(client, "number.boiler_run_for_2") == told_about(
        pump_entry,
        target="switch.pump",
        ends_at="sensor.boiler_ends_at_2",
        next_command="sensor.boiler_next_command_2",
        intervals=[{"entity_id": NIGHT_SWITCH, "title": "Night"}],
    )


async def test_user_who_is_not_an_admin_can_ask(
    read_only_client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Every dashboard user sees the card, so every user may ask what it needs."""
    entry = await setup_target()

    assert await found(read_only_client, NUMBER) == told_about(entry)


# --- Telling a user only what the user may read -------------------------------------


UNAUTHORIZED = {"code": "unauthorized", "message": "Unauthorized"}
"""The refusal for a user whose policy does not let it read an entity."""


def may_read_only(user: MockUser, *entity_ids: str) -> None:
    """Give `user` a policy that lets it read these entities and no others."""
    user.mock_policy(
        {"entities": {"entity_ids": {entity_id: True for entity_id in entity_ids}}}
    )


async def test_user_who_may_read_every_entity_of_the_answer_is_told(
    hass: HomeAssistant,
    read_only_client: MockHAClientWebSocket,
    hass_read_only_user: MockUser,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A policy that names the entities the card shows is as good as the whole house."""
    entry = await setup_target()
    evening = await add_interval(hass, entry, start="18:00", end="19:00")
    await retitle_interval(hass, entry, evening, "Evening")
    may_read_only(hass_read_only_user, NUMBER, TARGET_ID, SENSOR, NEXT, EVENING_SWITCH)

    assert await found(read_only_client, NUMBER) == told_about(
        entry, intervals=[{"entity_id": EVENING_SWITCH, "title": "Evening"}]
    )


@pytest.mark.parametrize("asked", [NUMBER, SENSOR, "number.nothing_here"])
async def test_user_who_may_not_read_the_entity_asked_about_is_refused(
    read_only_client: MockHAClientWebSocket,
    hass_read_only_user: MockUser,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    asked: str,
) -> None:
    """The answer is refused before anything is looked up, so a user cannot tell
    whether an entity it may not read is a timer's number: it is not told "not found"
    for one that is not."""
    await setup_target()
    may_read_only(hass_read_only_user, *{TARGET_ID, SENSOR, NEXT} - {asked})

    assert await refused(read_only_client, asked) == UNAUTHORIZED


@pytest.mark.parametrize("denied", [TARGET_ID, SENSOR, NEXT])
async def test_user_who_may_not_read_a_part_of_the_answer_is_refused(
    read_only_client: MockHAClientWebSocket,
    hass_read_only_user: MockUser,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    denied: str,
) -> None:
    """The card cannot work without the target and the two sensors, and an answer
    without one would break what it is promised, so the user is refused the whole
    answer, not told the ids of entities it may not read."""
    await setup_target()
    may_read_only(hass_read_only_user, *{NUMBER, TARGET_ID, SENSOR, NEXT} - {denied})

    assert await refused(read_only_client, NUMBER) == UNAUTHORIZED


async def test_interval_the_user_may_not_read_is_left_out(
    hass: HomeAssistant,
    read_only_client: MockHAClientWebSocket,
    hass_read_only_user: MockUser,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The intervals are a list, and a list holds what the user may read: the others
    are still there."""
    entry = await setup_target()
    evening = await add_interval(hass, entry, start="18:00", end="19:00")
    night = await add_interval(hass, entry, start="20:00", end="21:00")
    await retitle_interval(hass, entry, evening, "Evening")
    await retitle_interval(hass, entry, night, "Night")
    may_read_only(hass_read_only_user, NUMBER, TARGET_ID, SENSOR, NEXT, NIGHT_SWITCH)

    result = await found(read_only_client, NUMBER)

    assert result["intervals"] == [{"entity_id": NIGHT_SWITCH, "title": "Night"}]


# --- What is not a timer's number ---------------------------------------------------


@pytest.mark.parametrize("entity_id", [SENSOR, "switch.boiler", "number.nothing_here"])
async def test_anything_but_a_run_for_number_is_not_found(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    entity_id: str,
) -> None:
    """A sensor of the timer, the target itself and an entity that does not exist are
    each refused as what they are not: the "Run for" number of a timer."""
    await setup_target()

    assert await refused(client, entity_id) == not_a_timer(entity_id)


async def test_number_of_another_integration_is_not_found(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Only the numbers Timerify made are its timers', whatever their unique id."""
    entry = await setup_target()
    other = MockConfigEntry(domain="elsewhere")
    other.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "number",
        "elsewhere",
        f"{entry.entry_id}_run_for",
        config_entry=other,
        suggested_object_id="timer_of_another",
    )

    assert await refused(client, "number.timer_of_another") == not_a_timer(
        "number.timer_of_another"
    )


async def test_number_of_the_voice_settings_entry_is_not_a_timer(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The voice settings are an entry of Timerify but not a timer: a number that
    carries its id is not one of the timers' numbers."""
    await setup_target()
    voice = MockConfigEntry(
        domain=DOMAIN,
        unique_id=VOICE_UNIQUE_ID,
        options={CONF_KIND: KIND_VOICE_SETTINGS},
    )
    voice.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "number",
        DOMAIN,
        f"{voice.entry_id}_run_for",
        config_entry=voice,
        suggested_object_id="voice_run_for",
    )

    assert await refused(client, "number.voice_run_for") == not_a_timer(
        "number.voice_run_for"
    )


@pytest.mark.parametrize("asked", ["not an entity id", "", None, 7])
async def test_question_without_an_entity_id_is_refused(
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    asked: Any,
) -> None:
    """The dashboard asks about one entity id; anything else is a malformed question,
    not a timer that was not found."""
    await setup_target()
    await client.send_json_auto_id({"type": "timerify/timer", "entity_id": asked})
    message = await client.receive_json()

    assert message["success"] is False
    assert message["error"]["code"] == "invalid_format"


# --- A timer in whatever state it is in ---------------------------------------------


async def test_timer_that_is_not_loaded_is_still_found(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The card asks when the number comes back, which is while its entry is still
    starting after a restart or a reload, and the answer is the same as when it runs:
    it is configuration, not runtime."""
    entry = await setup_target()
    while_loaded = await found(client, NUMBER)

    await hass.config_entries.async_unload(entry.entry_id)

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert await found(client, NUMBER) == while_loaded == told_about(entry)


async def test_timer_that_failed_to_set_up_is_still_found(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    hass_storage: dict[str, Any],
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A timer whose file is broken does not start, and the card shows its states,
    which are unavailable, instead of a warning that its number is not a timer."""
    entry = await setup_target()
    await hass.config_entries.async_unload(entry.entry_id)
    key = storage_key(entry)
    hass_storage[key] = {
        "version": TimerStore.STORAGE_VERSION,
        "minor_version": 1,
        "key": key,
        "data": {**payload(end=at(30), started_at=at(0)), "end": NO_OFFSET},
    }
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR

    assert await found(client, NUMBER) == told_about(entry)


async def test_timer_whose_target_cannot_be_resolved_is_not_found(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """An entry that names its target by a registry id that is gone has no target to
    tell the card of, so it is not answered as a timer."""
    entry = await setup_target()
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_TARGET: GONE_FROM_REGISTRY}
    )
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR

    assert await refused(client, NUMBER) == {
        "code": "not_found",
        "message": (
            f"The target of the Timerify timer of {NUMBER}"
            " is not in the entity registry"
        ),
    }


@pytest.mark.parametrize(
    ("sibling", "key"), [(SENSOR, "ends_at"), (NEXT, "next_command")]
)
async def test_missing_sibling_is_not_found(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    sibling: str,
    key: str,
) -> None:
    """A timer that was set up has both sensors, so a number without one is not
    answered with a timer the card cannot read, and the refusal says which is
    missing: the number is a timer's."""
    entry = await setup_target()
    await hass.config_entries.async_unload(entry.entry_id)
    er.async_get(hass).async_remove(sibling)

    assert await refused(client, NUMBER) == {
        "code": "not_found",
        "message": (
            f"The Timerify timer of {NUMBER} has no {key} sensor in the entity registry"
        ),
    }


# --- A timer that changes -----------------------------------------------------------


async def test_renamed_number_is_found_under_its_new_id(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The user renames the number: it is the same timer under its new id, and the old
    id is no timer's."""
    entry = await setup_target()
    er.async_get(hass).async_update_entity(NUMBER, new_entity_id="number.hot_water")
    await hass.async_block_till_done()

    assert await found(client, "number.hot_water") == told_about(entry)
    assert await refused(client, NUMBER) == not_a_timer(NUMBER)


async def test_renamed_sibling_is_told_under_its_new_id(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The entities of the timer are found by what they are, so a rename does not lose
    them: the card is told the ids they have now."""
    entry = await setup_target()
    registry = er.async_get(hass)
    registry.async_update_entity(SENSOR, new_entity_id="sensor.hot_water_ends_at")
    registry.async_update_entity(NEXT, new_entity_id="sensor.hot_water_next_command")
    await hass.async_block_till_done()

    assert await found(client, NUMBER) == told_about(
        entry,
        ends_at="sensor.hot_water_ends_at",
        next_command="sensor.hot_water_next_command",
    )


async def test_renamed_target_is_followed(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The timer follows its target when it is renamed, and so does the answer."""
    entry = await setup_target()
    er.async_get(hass).async_update_entity(TARGET_ID, new_entity_id="switch.heater")
    hass.states.async_remove(TARGET_ID)
    hass.states.async_set("switch.heater", "off")
    await hass.async_block_till_done()

    assert await found(client, NUMBER) == told_about(entry, target="switch.heater")


async def test_deleted_interval_leaves_the_list(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """An interval that is deleted from the page of the timer is no longer told."""
    entry = await setup_target()
    evening = await add_interval(hass, entry, start="18:00", end="19:00")
    assert [i["entity_id"] for i in (await found(client, NUMBER))["intervals"]] == [
        EVENING_SWITCH
    ]

    hass.config_entries.async_remove_subentry(entry, evening)
    await hass.async_block_till_done()

    assert (await found(client, NUMBER))["intervals"] == []


async def test_interval_without_a_registry_entry_is_left_out(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """An interval whose switch is not in the registry has nothing to show on the card,
    and the others are told as usual."""
    entry = await setup_target()
    await add_interval(hass, entry, start="18:00", end="19:00")
    await add_interval(hass, entry, start="20:00", end="21:00")
    er.async_get(hass).async_remove(EVENING_SWITCH)
    await hass.async_block_till_done()

    result = await found(client, NUMBER)

    assert [interval["entity_id"] for interval in result["intervals"]] == [NIGHT_SWITCH]
