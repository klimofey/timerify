"""The services of a timer: add time to it, or run the target without a duration."""

import logging
from pathlib import Path
from typing import Any

import probatio
import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.setup import async_setup_component
from homeassistant.util.json import json_loads_object
from homeassistant.util.yaml import load_yaml

from custom_components.timerify.const import DOMAIN, MAX_MINUTES

from .conftest import TARGET_ID, FakeTarget, SetupTarget
from .helpers import NUMBER, SENSOR, TURN_OFF, TURN_ON, advance, set_number, state_of

INTEGRATION_DIR = Path(__file__).parent.parent / "custom_components" / DOMAIN
TEXTS = ("name", "description")


async def call_service(
    hass: HomeAssistant, service: str, target: dict[str, Any], **data: Any
) -> None:
    """Call a Timerify service the way an automation or the UI does."""
    await hass.services.async_call(DOMAIN, service, {**target, **data}, blocking=True)
    await hass.async_block_till_done()


async def test_add_time_extends_running_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """At 07:10 with 5 minutes left, adding 30 moves the end to 07:45."""
    await setup_target()
    await set_number(hass, NUMBER, 15)
    await advance(hass, freezer, minutes=10)
    assert state_of(hass, NUMBER) == "5"

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=30)

    assert state_of(hass, SENSOR) == "2026-01-05T07:45:00+00:00"
    assert state_of(hass, NUMBER) == "35"
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=34)
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=1)
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_add_time_on_idle_target_starts_it(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Adding time to a target that is not running turns it on for that long."""
    await setup_target()

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=20)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "20"
    assert state_of(hass, SENSOR) == "2026-01-05T07:20:00+00:00"
    assert state_of(hass, TARGET_ID) == "on"


async def test_negative_add_time_shortens_running_timer(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Taking minutes off leaves the target running for the rest."""
    await setup_target()
    await set_number(hass, NUMBER, 30)

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=-10)

    assert state_of(hass, NUMBER) == "20"
    assert fake_target.calls == [TURN_ON]


@pytest.mark.parametrize("minutes", [-15, -40])
async def test_negative_add_time_to_zero_turns_off(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    minutes: int,
) -> None:
    """Taking off all the time that is left, or more, switches the target off."""
    await setup_target()
    await set_number(hass, NUMBER, 15)

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=minutes)

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, NUMBER) == "0"
    assert state_of(hass, SENSOR) == "unknown"
    assert state_of(hass, TARGET_ID) == "off"


async def test_negative_add_time_on_idle_target_does_nothing(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """There is nothing to take time from, so the target stays off."""
    await setup_target()

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=-5)

    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "0"


async def test_add_time_accepts_up_to_a_day(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The longest timer is one day, and a service call may ask for all of it."""
    await setup_target()

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=MAX_MINUTES)

    assert state_of(hass, NUMBER) == str(MAX_MINUTES)
    assert fake_target.calls == [TURN_ON]


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"minutes": MAX_MINUTES + 1},
        {"minutes": -MAX_MINUTES - 1},
        {"minutes": 2.5},
    ],
    ids=["missing", "above_a_day", "below_minus_a_day", "not_whole"],
)
async def test_add_time_rejects_invalid_minutes(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    data: dict[str, Any],
) -> None:
    """A call without a whole number of minutes within a day changes nothing."""
    await setup_target()

    with pytest.raises(probatio.Invalid):
        await call_service(hass, "add_time", {"entity_id": NUMBER}, **data)

    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "0"


async def test_run_strict_uses_default_duration(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """In strict mode running without a duration counts down the default one."""
    await setup_target(mode="strict", default_duration=45)

    await call_service(hass, "run", {"entity_id": NUMBER})

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "45"
    assert state_of(hass, SENSOR) == "2026-01-05T07:45:00+00:00"


async def test_run_loose_turns_on_without_countdown(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """In loose mode running without a duration leaves the timer at zero."""
    await setup_target(mode="loose")

    await call_service(hass, "run", {"entity_id": NUMBER})

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, NUMBER) == "0"
    assert state_of(hass, SENSOR) == "unknown"


async def test_services_accept_the_device_of_the_target(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Picking the device in the UI reaches the timer on it."""
    await setup_target()

    await call_service(
        hass, "add_time", {"device_id": fake_target.device_id}, minutes=10
    )

    assert state_of(hass, NUMBER) == "10"
    assert fake_target.calls == [TURN_ON]


async def test_services_on_unloaded_timer_do_nothing(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A timer that is not loaded is skipped, as Home Assistant skips any
    unavailable entity, and the target is left alone."""
    entry = await setup_target()
    await hass.config_entries.async_unload(entry.entry_id)
    caplog.set_level(logging.WARNING)

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=10)
    await call_service(hass, "run", {"entity_id": NUMBER})

    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "unavailable"
    assert f"Referenced entities {NUMBER} are missing" in caplog.text


async def test_services_are_described_for_the_ui(hass: HomeAssistant) -> None:
    """The UI offers the services for Timerify's "Run for" numbers only, and the
    range it lets the user pick is the range the service accepts."""
    assert await async_setup_component(hass, DOMAIN, {})

    descriptions = (await async_get_all_descriptions(hass))[DOMAIN]

    target = {"entity": [{"integration": DOMAIN, "domain": ["number"]}]}
    assert descriptions["add_time"]["target"] == target
    assert descriptions["run"]["target"] == target
    minutes = descriptions["add_time"]["fields"]["minutes"]
    assert minutes["required"] is True
    assert minutes["selector"]["number"]["min"] == -MAX_MINUTES
    assert minutes["selector"]["number"]["max"] == MAX_MINUTES
    assert descriptions["run"]["fields"] == {}


def texts_in(tree: Any, path: str = "") -> set[str]:
    """The dotted path of every non-empty text in a tree of translations."""
    if isinstance(tree, str):
        return {path} if tree else set()
    return {
        text
        for key, subtree in tree.items()
        for text in texts_in(subtree, f"{path}.{key}" if path else key)
    }


@pytest.mark.parametrize("language", ["en", "ru"])
def test_services_are_translated(language: str) -> None:
    """Every service and field in services.yaml has a name and a description."""
    services = load_yaml(str(INTEGRATION_DIR / "services.yaml"))
    wanted: set[str] = set()
    for name, service in services.items():
        wanted |= {f"{name}.{text}" for text in TEXTS}
        for field in service.get("fields", {}):
            wanted |= {f"{name}.fields.{field}.{text}" for text in TEXTS}
    translations = json_loads_object(
        (INTEGRATION_DIR / "translations" / f"{language}.json").read_text("utf-8")
    )

    assert texts_in(translations["services"]) == wanted
