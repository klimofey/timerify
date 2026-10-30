"""What every handler is built from: slot validation, the language of a refusal, and
the slots an answer is made of."""

from datetime import timedelta
from typing import Any

import probatio
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from custom_components.timerify.const import DOMAIN
from custom_components.timerify.voice.base import (
    async_error_text,
    clock_slots,
    duration_of,
    named,
    voice_language,
    whole_slot,
)

from ..helpers import JERUSALEM, START
from .helpers import translated


def refusal(key: str, **placeholders: str) -> HomeAssistantError:
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders,
    )


@pytest.mark.parametrize(
    ("slots", "minutes"),
    [
        ({}, None),
        ({"minutes": {"value": 45}}, 45),
        ({"hours": {"value": 2}}, 120),
        ({"hours": {"value": 1}, "minutes": {"value": 30}}, 90),
        ({"hours": {"value": 0}}, 0),
        ({"name": {"value": "Boiler"}}, None),
    ],
)
def test_the_duration_of_slots_is_their_hours_and_minutes_together(
    slots: dict[str, Any], minutes: int | None
) -> None:
    """None when neither is said: the open run, which the timer judges."""
    assert duration_of(slots) == minutes


def test_the_duration_of_slots_can_be_asked_by_prefix() -> None:
    slots = {"hours": {"value": 1}, "delay_minutes": {"value": 15}}

    assert duration_of(slots, "delay_") == 15
    assert duration_of(slots) == 60


def test_the_device_of_a_takeover_sentence_is_its_name() -> None:
    """The sentences that take over Home Assistant's say the device in a slot of their
    own; to a handler it is the `name`, like the device of any other sentence."""
    slots = {"timerify_target": {"value": "Boiler"}, "action": {"value": "on"}}

    assert named(slots) == {"name": {"value": "Boiler"}, "action": {"value": "on"}}
    assert named({"name": {"value": "Boiler"}}) == {"name": {"value": "Boiler"}}


@pytest.mark.parametrize("value", [0, 1, 15, 15.0, 1440, 1440.0])
def test_whole_slot_takes_the_whole_numbers_the_agent_and_an_llm_send(
    value: float,
) -> None:
    taken = whole_slot(value)

    assert taken == value
    assert type(taken) is int


@pytest.mark.parametrize(
    "value",
    [True, False, 2.5, -1, -0.5, float("inf"), float("nan"), "15", None],
)
def test_whole_slot_refuses_everything_else(value: Any) -> None:
    with pytest.raises(probatio.Invalid):
        whole_slot(value)


@pytest.mark.parametrize(
    ("language", "spoken"),
    [
        ("en", "en"),
        ("ru", "ru"),
        ("en-GB", "en"),
        ("ru-RU", "ru"),
        ("*", "en"),
        ("de", "en"),
    ],
)
def test_voice_language_is_the_closest_language_timerify_speaks(
    language: str, spoken: str
) -> None:
    assert voice_language(language) == spoken


async def test_clock_is_the_time_of_day_in_the_house_and_the_days_to_its_date(
    hass: HomeAssistant,
) -> None:
    """The date counts on the wall clock, not in blocks of 24 hours: forty minutes
    after half past eleven in the evening it is tomorrow."""
    await hass.config.async_set_time_zone(JERUSALEM)
    now = START + timedelta(hours=14, minutes=30)  # 23:30 in Jerusalem

    assert clock_slots(now + timedelta(minutes=20), now) == {
        "at": "23:50",
        "in_days": 0,
    }
    assert clock_slots(now + timedelta(minutes=40), now) == {
        "at": "00:10",
        "in_days": 1,
    }
    assert clock_slots(now + timedelta(hours=24), now) == {"at": "23:30", "in_days": 1}


async def test_a_refusal_is_spoken_in_the_language_of_the_request(
    hass: HomeAssistant,
) -> None:
    """A regional language is spoken as its language; the wildcard of an MCP client and
    a language Timerify has no texts for are spoken in English."""
    err = refusal("setting_not_supported", target="Boiler", setting="hvac_mode")
    english = translated("en", "exceptions", "setting_not_supported", "message")
    english_field = translated("en", "services", "run", "fields", "hvac_mode", "name")
    russian = translated("ru", "exceptions", "setting_not_supported", "message")
    russian_field = translated("ru", "services", "run", "fields", "hvac_mode", "name")

    said = {
        language: await async_error_text(hass, language, err)
        for language in ("en", "ru", "ru-RU", "en-GB", "*", "de")
    }

    in_english = english.format(target="Boiler", setting=english_field)
    in_russian = russian.format(target="Boiler", setting=russian_field)
    assert in_english != in_russian
    assert said == {
        "en": in_english,
        "ru": in_russian,
        "ru-RU": in_russian,
        "en-GB": in_english,
        "*": in_english,
        "de": in_english,
    }


async def test_a_setting_without_a_field_name_is_named_as_it_came(
    hass: HomeAssistant,
) -> None:
    err = refusal("setting_not_supported", target="Boiler", setting="not_a_field")

    assert await async_error_text(hass, "en", err) == (
        "Boiler cannot be turned on with the setting not_a_field."
    )


async def test_a_time_is_spoken_as_the_time_of_day(hass: HomeAssistant) -> None:
    await hass.config.async_set_time_zone(JERUSALEM)
    err = refusal(
        "command_in_past",
        at=dt_util.as_local(START).isoformat(sep=" ", timespec="seconds"),
    )

    assert await async_error_text(hass, "en", err) == (
        "09:00 has already passed. Pick a time that is still ahead."
    )


async def test_a_refusal_with_no_text_of_ours_says_what_it_says_itself(
    hass: HomeAssistant,
) -> None:
    err = refusal("a_key_no_translation_has")

    assert await async_error_text(hass, "en", err) == str(err)
