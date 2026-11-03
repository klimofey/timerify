"""Turning a device on or off at a clock time by voice, in English and Russian.

"Turn on the boiler at 7:30", "tomorrow at 7", "at 7 pm": the built-in agent keeps a
command for that time or sets the countdown to end then. Every scenario talks to the
real built-in agent, in Jerusalem, from Sunday at six in the morning unless it moves the
clock. What is said in Russian is read from the shipped sentences, so that no test needs
a Russian letter.

An hour from 1 to 12 said with no "am", "pm" or Russian word for the time of day is the
nearer of its morning and evening times that is still ahead (the owner's decision of
2026-11-02); the hour of 0 or from 13 to 23 is that of the 24-hour clock, and so is an
hour written with a leading zero, "07:30" (the owner's decision of 2026-11-03). A part
of the day still chooses the half.
"""

import re
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
import yaml
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from pytest_homeassistant_custom_component.common import MockConfigEntry
from unicode_rbnf import RbnfEngine

from custom_components.timerify.voice.commands import (
    DayPart,
    clock_moment,
    hour_of_day,
)

from ..conftest import FakeTarget, SetupTarget
from ..helpers import (
    AC_NEXT,
    JERUSALEM,
    NEXT,
    NUMBER,
    SENSOR,
    SMALL_AC_NEXT,
    SUNDAY,
    advance_to,
    call_service,
    iso,
    local,
    open_sunday,
    set_number,
    state_of,
)
from .helpers import (
    CLOCK_PHRASES,
    SETTING_LISTS,
    converse,
    copy_sentences,
    reached,
    refusal_of,
    russian_clock_phrases,
    samples,
    speech,
    spoken_number,
    spoken_rule,
    spoken_values,
    translated,
    with_voice_settings,
)

CLOCK = "TimerifyCommandAt"
RUN = "TimerifyRun"
MONDAY = SUNDAY + timedelta(days=1)
NUMBERS = {
    "timerify_clock_hours": 7,
    "timerify_clock_minutes": 30,
    "timerify_half_day_hours": 7,
    "timerify_minutes_of_hour": 20,
}
"""The numbers with which a clock time is said: 7:30, or 7 with a part of the day. The
minutes are said as digits after a separator (`MINUTES`), and as this number only with
their word in Russian: "7 hours 30 minutes". The minutes of an hour are 20, so that the
sampler says the minutes past and to an hour ("20 past 7", "20 to 8"), which a list
without a number is left out of."""
MINUTES = {"timerify_clock_minute_digits": "30"}
"""The minutes said after a separator, which are two digits: the 30 of 7:30."""


@pytest.fixture
async def clock_boiler(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> MockConfigEntry:
    """A timer on the Boiler, which Assist knows by the sentences of the manual
    installation, on Sunday at six in the morning in Jerusalem."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await copy_sentences(hass, ["Boiler"])
    return entry


def at(day: date, clock: str) -> str:
    """What the "Next command" sensor shows for a command due at `clock` on `day`."""
    return iso(day, clock)


def pending(hass: HomeAssistant, entity_id: str = NEXT) -> list[dict[str, Any]]:
    """The commands a "Next command" sensor lists in its attributes."""
    state = hass.states.get(entity_id)
    assert state is not None
    commands: list[dict[str, Any]] = state.attributes["commands"]
    return commands


async def cancel_pending(hass: HomeAssistant, number: str, sensor: str) -> None:
    """Cancel every command the timer of `number` keeps."""
    for command in pending(hass, sensor):
        await call_service(
            hass, "cancel_command", {"entity_id": number}, command_id=command["id"]
        )


async def say_at(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    day: date,
    clock: str,
    text: str,
    language: str = "en",
) -> intent.IntentResponse:
    """Say `text` to the agent when it is `clock` on `day` in Jerusalem."""
    await advance_to(hass, freezer, local(day, clock))
    return await converse(hass, text, language)


async def say_slots(
    hass: HomeAssistant, slots: dict[str, object]
) -> intent.IntentResponse:
    """Ask the clock handler to turn the Boiler on with the clock `slots`, as a sentence
    of the built-in agent would."""
    said = {"name": "Boiler", "action": "on", **slots}
    return await intent.async_handle(
        hass, "test", CLOCK, {key: {"value": value} for key, value in said.items()}
    )


def turn_on_at(language: str, clock: str) -> str:
    """The sentence of the shipped files that turns the Boiler on, with `clock` as the
    time it says: the first sentence with a command before the time, taken from the
    samples of the language."""
    forms = spoken_rule(language, "timerify_clock", NUMBERS, MINUTES)
    for sample in samples(
        language,
        CLOCK,
        takeover=True,
        numbers=NUMBERS,
        texts=MINUTES,
        absent=SETTING_LISTS,
        admitting="switch",
    ):
        if sample.endswith(forms[0]):
            return sample.removesuffix(forms[0]) + clock
    raise AssertionError(f"No sample of {language} ends with {forms[0]!r}")


def russian_form(
    pattern: str,
    numbers: dict[str, int] | None = None,
    texts: dict[str, str] | None = None,
) -> str:
    """The one way of saying a time in Russian that matches `pattern`, from the forms
    the shipped sentences say with the `numbers` and the words of the lists `texts`
    gives (the first value of a list without one)."""
    forms = [
        form
        for form in spoken_rule(
            "ru", "timerify_clock", numbers or NUMBERS, {**MINUTES, **(texts or {})}
        )
        if re.fullmatch(pattern, form)
    ]
    assert len(forms) == 1, (pattern, forms)
    return forms[0]


def clock_sentence(
    language: str, time: str, *, day: str | None = None, part: str | None = None
) -> str:
    """The sentence that turns the Boiler on at `time` in `language`, with the hour
    written as `time` writes it: "7:30", "07:30", "07".

    `day` is a value of the list of days ("0" today, "1" tomorrow) and `part` a word of
    the list of parts of the day, both said as the shipped files say them. Russian is
    read from the shipped sentences, which the sampler can only fill with an hour as a
    plain number, so the hour is written as `time` writes it afterwards.
    """
    if language == "en":
        said = "turn on the boiler"
        if day is not None:
            said += f" {spoken_values('en', 'timerify_clock_days')[day][0]}"
        said += f" at {time}"
        return said if part is None else f"{said} {part}"
    hour, separator, minutes = time.partition(":")
    plain = f"{int(hour)}{separator}{minutes}"
    numbers = {
        **NUMBERS,
        "timerify_clock_hours": int(hour),
        "timerify_half_day_hours": int(hour),
    }
    texts: dict[str, str] = {}
    pattern = rf"\S+ {re.escape(plain)}"
    if day is not None:
        day_word = spoken_values("ru", "timerify_clock_days")[day][0]
        texts["timerify_clock_days"] = day_word
        pattern = rf"{re.escape(day_word)} {pattern}"
    if part is not None:
        texts["timerify_day_parts"] = part
        pattern += rf" {re.escape(part)}"
    form = russian_form(pattern, numbers, texts)
    return turn_on_at("ru", form.replace(plain, time, 1))


# --- The forms of English ----------------------------------------------------------


async def test_turn_on_at_a_clock_time_keeps_a_command_for_then(
    hass: HomeAssistant, fake_target: FakeTarget, clock_boiler: MockConfigEntry
) -> None:
    """The command waits for its time (P1), as a command after a delay does."""
    response = await converse(hass, "turn on the boiler at 7:30")

    assert reached(response) == CLOCK, speech(response)
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert state_of(hass, NEXT) == at(SUNDAY, "07:30")
    assert speech(response) == "Boiler turns on at 07:30."
    assert fake_target.calls == []


@pytest.mark.parametrize(
    ("said", "clock", "days"),
    [
        ("at 7:30", "07:30", 0),
        ("at 07:30", "07:30", 0),
        ("at 7 30", "07:30", 0),
        ("at 7.30", "07:30", 0),
        ("at 7:05", "07:05", 0),
        ("at 7.05", "07:05", 0),
        ("at 7 05", "07:05", 0),
        ("at 7:08", "07:08", 0),
        ("at 7.09", "07:09", 0),
        ("at 7", "07:00", 0),
        ("at 7 o'clock", "07:00", 0),
        ("at 7 pm", "19:00", 0),
        ("at 7:30 p.m.", "19:30", 0),
        ("at 12 am", "00:00", 1),
        ("at 12 pm", "12:00", 0),
        ("at noon", "12:00", 0),
        ("at midnight", "00:00", 1),
        ("at 19:05", "19:05", 0),
        ("tomorrow at 7", "07:00", 1),
        ("at 7 tomorrow", "07:00", 1),
        ("the day after tomorrow at 7", "07:00", 2),
        ("tomorrow at 12:30", "00:30", 1),
        ("at seven thirty", "07:30", 0),
        ("at seven thirty pm", "19:30", 0),
    ],
)
async def test_every_english_clock_form_means_its_time(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    said: str,
    clock: str,
    days: int,
) -> None:
    response = await converse(hass, f"turn on the boiler {said}")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=days), clock)
    assert fake_target.calls == []


@pytest.mark.parametrize(
    "said", ["at 7:30 turn on the boiler", "tomorrow at 7 turn on the boiler"]
)
async def test_the_time_may_come_before_the_command(
    hass: HomeAssistant, clock_boiler: MockConfigEntry, said: str
) -> None:
    response = await converse(hass, said)

    assert reached(response) == CLOCK, speech(response)
    assert len(pending(hass)) == 1


@pytest.mark.parametrize(
    ("said", "day"),
    [
        ("turn on the boiler at 7:30 for an hour", 0),
        ("turn on the boiler for an hour at 7:30", 0),
        ("turn on the boiler for an hour tomorrow at 7:30", 1),
        ("at 7:30 turn on the boiler for an hour", 0),
    ],
)
async def test_a_command_to_turn_on_at_a_time_may_say_how_long_it_runs(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    said: str,
    day: int,
) -> None:
    """How long the boiler then runs comes before the time or after it."""
    response = await converse(hass, said)

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=day), "07:30")
    assert [command["minutes"] for command in pending(hass)] == [60]

    await advance_to(hass, freezer, local(SUNDAY + timedelta(days=day), "07:30"))

    assert fake_target.calls == [("turn_on", fake_target.entity_id)]
    assert state_of(hass, NUMBER) == "60"


async def test_a_clock_time_already_past_today_means_tomorrow(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
) -> None:
    """At eight in the evening neither 6 in the morning nor 6 in the evening is ahead
    today: "at 6:00" is tomorrow's, and the answer says so."""
    response = await say_at(
        hass, freezer, SUNDAY, "20:00", "turn on the boiler at 6:00"
    )

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(MONDAY, "06:00")
    assert speech(response) == "Boiler turns on at 06:00 tomorrow."
    assert fake_target.calls == []


async def test_a_time_of_the_24_hour_clock_that_has_passed_means_tomorrow(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, clock_boiler: MockConfigEntry
) -> None:
    """The hour 19 has one reading only, so at eight in the evening it is tomorrow's."""
    response = await say_at(hass, freezer, SUNDAY, "20:00", "turn on the boiler at 19")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(MONDAY, "19:00")


async def test_the_time_it_is_now_means_tomorrow(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, clock_boiler: MockConfigEntry
) -> None:
    """A time that is not ahead is the next day's, the minute it is said included."""
    response = await say_at(hass, freezer, SUNDAY, "19:00", "turn on the boiler at 19")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(MONDAY, "19:00")


@pytest.mark.parametrize(
    ("now", "said"), [("20:00", "today at 7"), ("08:00", "today at 7 am")]
)
async def test_today_at_a_time_that_has_passed_is_refused(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    now: str,
    said: str,
) -> None:
    """ "Today" is today: the time that has passed is not moved to tomorrow, and nothing
    is kept. At eight in the evening both 7 in the morning and 7 in the evening have
    passed; the morning one is named."""
    response = await say_at(hass, freezer, SUNDAY, now, f"turn on the boiler {said}")

    assert reached(response) == CLOCK, speech(response)
    assert refusal_of(response) == translated(
        "en", "exceptions", "command_in_past", "message"
    ).format(at="07:00")
    assert state_of(hass, NEXT) == "unknown"
    assert fake_target.calls == []


async def test_a_wall_time_the_clock_skips_happens_an_hour_later(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, clock_boiler: MockConfigEntry
) -> None:
    """The clock goes from 02:00 to 03:00 in Jerusalem on 2026-03-27: 02:30 that night
    is 03:30 on the wall, as a schedule window at 02:30 is."""
    response = await say_at(
        hass, freezer, date(2026, 3, 26), "23:00", "turn on the boiler at 2:30"
    )

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == "2026-03-27T00:30:00+00:00"
    assert speech(response) == "Boiler turns on at 03:30 tomorrow."


# --- Turning off -------------------------------------------------------------------


async def test_turn_off_at_a_clock_time_sets_the_countdown_to_end_then(
    hass: HomeAssistant, fake_target: FakeTarget, clock_boiler: MockConfigEntry
) -> None:
    """A running boiler is told when to stop, as "turn off in 90 minutes" does."""
    await set_number(hass, NUMBER, 240)

    response = await converse(hass, "turn off the boiler at 7:30")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, SENSOR) == at(SUNDAY, "07:30")
    assert state_of(hass, NUMBER) == "90"
    assert speech(response) == "Boiler turns off at 07:30."
    assert pending(hass) == []


async def test_turn_off_at_a_clock_time_changes_nothing_for_a_boiler_that_is_off(
    hass: HomeAssistant, fake_target: FakeTarget, clock_boiler: MockConfigEntry
) -> None:
    response = await converse(hass, "turn off the boiler at 7:30")

    assert reached(response) == CLOCK, speech(response)
    assert speech(response) == "Boiler is already off; nothing changed."
    assert state_of(hass, SENSOR) == "unknown"
    assert fake_target.calls == []


async def test_turn_off_at_a_time_more_than_a_day_ahead_is_refused(
    hass: HomeAssistant, fake_target: FakeTarget, clock_boiler: MockConfigEntry
) -> None:
    """A countdown runs for a day at most: the refusal names that limit and the boiler
    keeps its countdown."""
    await set_number(hass, NUMBER, 240)

    response = await converse(hass, "turn off the boiler tomorrow at 23:00")

    assert reached(response) == CLOCK, speech(response)
    assert refusal_of(response) == translated(
        "en", "exceptions", "duration_out_of_range", "message"
    ).format(max_hours="24")
    assert state_of(hass, NUMBER) == "240"


# --- Thermostats -------------------------------------------------------------------


@pytest.mark.usefixtures("assist")
async def test_turn_on_at_a_time_for_a_while_with_settings(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_full_ac: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The settings of the AC are kept with the command, as after a delay, and the AC is
    put into them when the time comes."""
    await open_sunday(hass, freezer)
    await with_voice_settings(hass, setup_target, fake_full_ac)

    response = await converse(
        hass, "turn on the AC at 7:30 for an hour cooling 24 degrees"
    )

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, AC_NEXT) == at(SUNDAY, "07:30")
    assert [(c["minutes"], c["settings"]) for c in pending(hass, AC_NEXT)] == [
        (60, {"hvac_mode": "cool", "temperature": 24.0})
    ]
    assert fake_full_ac.call_data == []


@pytest.mark.usefixtures("assist")
async def test_a_command_at_a_time_takes_only_the_hvac_modes_of_its_ac(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_full_ac: FakeTarget,
    fake_small_ac: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The small AC cannot heat: "heating" after its name keeps no command for 7:30,
    while a mode it has is kept with the command."""
    await open_sunday(hass, freezer)
    await with_voice_settings(hass, setup_target, fake_full_ac, fake_small_ac)

    heated = await converse(hass, "turn on the small AC at 7:30 heating")

    assert reached(heated) != CLOCK, speech(heated)
    assert pending(hass, SMALL_AC_NEXT) == []
    assert pending(hass, AC_NEXT) == []

    cooled = await converse(hass, "turn on the small AC at 7:30 cooling")

    assert reached(cooled) == CLOCK, speech(cooled)
    assert [c["settings"] for c in pending(hass, SMALL_AC_NEXT)] == [
        {"hvac_mode": "cool"}
    ]
    assert pending(hass, AC_NEXT) == []
    assert fake_small_ac.calls == fake_full_ac.calls == []


@pytest.mark.usefixtures("assist")
async def test_for_an_hour_at_21_stays_a_temperature_for_a_thermostat(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_full_ac: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """After how long it runs, a bare number is the temperature of a thermostat, as it
    was before there were clock times: nothing is kept for 21:00."""
    await open_sunday(hass, freezer)
    await with_voice_settings(hass, setup_target, fake_full_ac)

    response = await converse(hass, "turn on the AC for an hour at 21")

    assert reached(response) == RUN, speech(response)
    assert fake_full_ac.call_data == [
        ("turn_on", {}),
        ("set_temperature", {"temperature": 21.0}),
    ]
    assert state_of(hass, AC_NEXT) == "unknown"


@pytest.mark.usefixtures("assist")
async def test_a_thermostat_takes_an_exact_time_after_its_settings(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_full_ac: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A time with minutes cannot be taken for a temperature, so it is a time."""
    await open_sunday(hass, freezer)
    await with_voice_settings(hass, setup_target, fake_full_ac)

    response = await converse(hass, "turn on the AC for an hour at 7:30")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, AC_NEXT) == at(SUNDAY, "07:30")
    assert fake_full_ac.call_data == []


@pytest.mark.usefixtures("assist")
async def test_a_thermostat_reads_a_leading_zero_in_a_time_after_its_settings(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_full_ac: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """After the settings "07:30" is a time as "7:30" is, and it is the morning one."""
    await open_sunday(hass, freezer)
    await with_voice_settings(hass, setup_target, fake_full_ac)
    await advance_to(hass, freezer, local(SUNDAY, "08:00"))

    response = await converse(hass, "turn on the AC for an hour at 07:30")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, AC_NEXT) == at(MONDAY, "07:30")
    assert fake_full_ac.call_data == []


@pytest.mark.usefixtures("assist")
@pytest.mark.parametrize("hour", ["7", "07"])
async def test_a_bare_hour_after_the_settings_is_no_time_with_a_zero_either(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_full_ac: FakeTarget,
    setup_target: SetupTarget,
    hour: str,
) -> None:
    """A zero does not make a bare number after the settings of a thermostat a time: it
    stays what it was before there were clock times, the temperature, and nothing is
    kept. The AC takes 16 to 30 degrees, so 7 is refused as a temperature, which is
    how it shows that it was read as one."""
    await open_sunday(hass, freezer)
    await with_voice_settings(hass, setup_target, fake_full_ac)

    response = await converse(hass, f"turn on the AC for an hour at {hour}")

    assert reached(response) == RUN, speech(response)
    assert refusal_of(response) == (
        "7 is not a valid Temperature: it must be between 16 and 30."
    )
    assert fake_full_ac.call_data == []
    assert state_of(hass, AC_NEXT) == "unknown"


@pytest.mark.usefixtures("assist")
@pytest.mark.parametrize(
    "said",
    [
        "turn on the tank for an hour at 7:30",
        "turn on the tank for an hour at 7 pm",
        "turn on the tank for an hour at 7 o'clock",
        "turn on the tank for an hour tomorrow at 7:30",
    ],
)
async def test_a_water_heater_takes_an_exact_time_after_its_settings(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_tank: FakeTarget,
    setup_target: SetupTarget,
    said: str,
) -> None:
    await open_sunday(hass, freezer)
    await with_voice_settings(hass, setup_target, fake_tank)

    response = await converse(hass, said)

    assert reached(response) == CLOCK, speech(response)
    assert fake_tank.call_data == []


@pytest.mark.usefixtures("assist")
async def test_for_an_hour_at_50_stays_a_temperature_for_a_water_heater(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_tank: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    await open_sunday(hass, freezer)
    await with_voice_settings(hass, setup_target, fake_tank)

    response = await converse(hass, "turn on the tank for an hour at 50")

    assert reached(response) == RUN, speech(response)
    assert ("set_temperature", {"temperature": 50.0}) in fake_tank.call_data


@pytest.mark.usefixtures("assist")
@pytest.mark.parametrize(
    ("said", "day", "clock"),
    [
        ("turn on the AC for an hour at 7 in the evening", SUNDAY, "19:00"),
        ("turn on the AC for an hour at 7:30 in the morning", SUNDAY, "07:30"),
        ("turn on the AC for an hour tomorrow morning at 7", MONDAY, "07:00"),
        ("turn on the AC for an hour in the evening at 7", SUNDAY, "19:00"),
        ("turn on the AC for an hour tonight at 7", SUNDAY, "19:00"),
        ("turn on the AC for an hour at 7:30pm", SUNDAY, "19:30"),
    ],
)
async def test_a_thermostat_takes_a_part_of_the_day_after_its_settings(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_full_ac: FakeTarget,
    setup_target: SetupTarget,
    said: str,
    day: date,
    clock: str,
) -> None:
    """A part of the day tells a time from a temperature, whether it comes after the
    hour or before it, so no bare number is taken for 7 degrees there."""
    await open_sunday(hass, freezer)
    await with_voice_settings(hass, setup_target, fake_full_ac)

    response = await converse(hass, said)

    assert reached(response) == CLOCK, speech(response)
    assert fake_full_ac.call_data == []
    command = pending(hass, AC_NEXT)[0]
    assert command["minutes"] == 60
    assert state_of(hass, AC_NEXT) == at(day, clock)


@pytest.mark.usefixtures("assist")
async def test_a_thermostat_takes_any_time_before_its_settings(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_full_ac: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Said before the settings, or first, a bare hour is a time: only a time that
    follows the settings could be a temperature."""
    await open_sunday(hass, freezer)
    await with_voice_settings(hass, setup_target, fake_full_ac)

    response = await converse(hass, "turn on the AC at 7 for an hour cooling 24")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, AC_NEXT) == at(SUNDAY, "07:00")
    assert [c["settings"] for c in pending(hass, AC_NEXT)] == [
        {"hvac_mode": "cool", "temperature": 24.0}
    ]


# --- The reading of a bare hour (the owner's decision) -----------------------------


@pytest.mark.parametrize("language", ["en", "ru"])
async def test_a_bare_hour_said_in_the_evening_is_that_hour_tonight(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    language: str,
) -> None:
    """At six in the evening "at 7" is 19:00 today, the nearer of 07:00 and 19:00 that
    is ahead, and the answer says 19:00."""
    said = (
        "turn on the boiler at 7"
        if language == "en"
        else turn_on_at("ru", russian_form(r"\S+ 7"))
    )

    response = await say_at(hass, freezer, SUNDAY, "18:00", said, language)

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(SUNDAY, "19:00")
    assert "19:00" in speech(response)


async def test_a_bare_hour_said_early_is_that_hour_this_morning(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, clock_boiler: MockConfigEntry
) -> None:
    """Before seven in the morning "at 7" is 07:00; once 07:00 and 19:00 have passed it
    is tomorrow's 07:00; and the minutes do not change which is nearer."""
    early = await say_at(hass, freezer, SUNDAY, "06:00", "turn on the boiler at 7")
    first = state_of(hass, NEXT)
    await cancel_pending(hass, NUMBER, NEXT)
    late = await say_at(hass, freezer, SUNDAY, "20:00", "turn on the boiler at 7")
    second = state_of(hass, NEXT)
    await cancel_pending(hass, NUMBER, NEXT)
    evening = await say_at(hass, freezer, SUNDAY, "20:30", "turn on the boiler at 7:30")
    third = state_of(hass, NEXT)

    assert {reached(early), reached(late), reached(evening)} == {CLOCK}
    assert first == at(SUNDAY, "07:00")
    assert second == at(MONDAY, "07:00")
    assert third == at(MONDAY, "07:30")


async def test_a_bare_hour_with_minutes_said_in_the_evening_is_that_time_tonight(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, clock_boiler: MockConfigEntry
) -> None:
    response = await say_at(
        hass, freezer, SUNDAY, "18:00", "turn on the boiler at 7:30"
    )

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(SUNDAY, "19:30")


async def test_an_hour_past_twelve_is_a_24_hour_clock(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, clock_boiler: MockConfigEntry
) -> None:
    """The hour 19 is 19:00 whenever it is said, and 0:30 is half past midnight."""
    morning = await say_at(hass, freezer, SUNDAY, "06:00", "turn on the boiler at 19")
    first = state_of(hass, NEXT)
    await cancel_pending(hass, NUMBER, NEXT)
    evening = await say_at(hass, freezer, SUNDAY, "20:00", "turn on the boiler at 0:30")
    second = state_of(hass, NEXT)

    assert {reached(morning), reached(evening)} == {CLOCK}
    assert first == at(SUNDAY, "19:00")
    assert second == at(MONDAY, "00:30")


async def test_tomorrow_with_a_bare_hour_is_the_morning_one(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, clock_boiler: MockConfigEntry
) -> None:
    """ "Tomorrow at 7" is the morning, whatever the hour it is said at; "today at 7" at
    six in the evening is the evening, the only 7 of today that is ahead."""
    tomorrow = await say_at(
        hass, freezer, SUNDAY, "18:00", "turn on the boiler tomorrow at 7"
    )
    first = state_of(hass, NEXT)
    await cancel_pending(hass, NUMBER, NEXT)
    today = await say_at(
        hass, freezer, SUNDAY, "18:00", "turn on the boiler today at 7"
    )
    second = state_of(hass, NEXT)

    assert {reached(tomorrow), reached(today)} == {CLOCK}
    assert first == at(MONDAY, "07:00")
    assert second == at(SUNDAY, "19:00")


# --- The reading of an hour written with a leading zero (the owner's decision) -----


@pytest.mark.parametrize("language", ["en", "ru"])
@pytest.mark.parametrize(
    ("now", "time", "days", "clock"),
    [
        ("08:00", "07:30", 1, "07:30"),
        ("08:00", "7:30", 0, "19:30"),
        ("08:00", "07", 1, "07:00"),
        ("08:00", "7", 0, "19:00"),
        ("06:00", "07", 0, "07:00"),
        ("06:00", "07:30", 0, "07:30"),
        ("20:00", "07", 1, "07:00"),
        ("20:00", "07:30", 1, "07:30"),
    ],
)
async def test_an_hour_with_a_leading_zero_is_the_morning(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    language: str,
    now: str,
    time: str,
    days: int,
    clock: str,
) -> None:
    """Written "07:30" or "07" the hour is on the 24-hour clock, so at eight in the
    morning it is tomorrow's 07:30, not tonight's 19:30. Written "7:30" or "7" it is the
    nearer of its morning and evening times, as before."""
    said = clock_sentence(language, time)

    response = await say_at(hass, freezer, SUNDAY, now, said, language)

    assert reached(response) == CLOCK, said
    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=days), clock)
    assert clock in speech(response)


@pytest.mark.parametrize("language", ["en", "ru"])
@pytest.mark.parametrize(("time", "clock"), [("07:30", "19:30"), ("07", "19:00")])
async def test_a_part_of_the_day_wins_over_a_leading_zero(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    language: str,
    time: str,
    clock: str,
) -> None:
    """The evening is the evening whether the hour is written "07" or "7": said at eight
    in the morning, "07:30 pm" and "07 in the evening" are tonight's, with every word
    that means the afternoon or the evening."""
    words = spoken_values(language, "timerify_day_parts")["pm"]
    assert words

    for word in words:
        said = clock_sentence(language, time, part=word)
        response = await say_at(hass, freezer, SUNDAY, "08:00", said, language)

        assert reached(response) == CLOCK, said
        assert state_of(hass, NEXT) == at(SUNDAY, clock), said
        await cancel_pending(hass, NUMBER, NEXT)


@pytest.mark.parametrize("language", ["en", "ru"])
async def test_tomorrow_at_an_hour_with_a_leading_zero_is_the_morning_one(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    language: str,
) -> None:
    said = clock_sentence(language, "07", day="1")

    response = await say_at(hass, freezer, SUNDAY, "08:00", said, language)

    assert reached(response) == CLOCK, said
    assert state_of(hass, NEXT) == at(MONDAY, "07:00")


@pytest.mark.parametrize("language", ["en", "ru"])
async def test_today_at_an_hour_with_a_leading_zero_that_has_passed_is_refused(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    language: str,
) -> None:
    """At eight in the morning "today at 07:30" is a time that has passed: it is not
    moved to tonight's 19:30 as "today at 7:30" is, and nothing is kept."""
    said = clock_sentence(language, "07:30", day="0")

    response = await say_at(hass, freezer, SUNDAY, "08:00", said, language)

    assert reached(response) == CLOCK, said
    assert refusal_of(response) == translated(
        language, "exceptions", "command_in_past", "message"
    ).format(at="07:30")
    assert state_of(hass, NEXT) == "unknown"
    assert pending(hass) == []
    assert fake_target.calls == []


@pytest.mark.parametrize("language", ["en", "ru"])
async def test_hour_zero_and_an_hour_said_in_words_are_unchanged(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    language: str,
) -> None:
    """The hour 0 was on the 24-hour clock already: "00:30" is the next half past
    midnight. An hour said as a word has no digits to start with a zero, so "seven
    thirty" is still the nearer of 07:30 and 19:30."""
    midnight = await say_at(
        hass, freezer, SUNDAY, "08:00", clock_sentence(language, "00:30"), language
    )

    assert reached(midnight) == CLOCK, speech(midnight)
    assert state_of(hass, NEXT) == at(MONDAY, "00:30")
    await cancel_pending(hass, NUMBER, NEXT)
    if language == "en":
        sentences = ["turn on the boiler at seven thirty"]
    else:
        sentences = [
            clock_sentence("ru", "7:30").replace("7:30", f"{word} 30")
            for word in spoken_number("ru", 7)
        ]
    assert sentences
    for said in sentences:
        response = await say_at(hass, freezer, SUNDAY, "08:00", said, language)

        assert reached(response) == CLOCK, said
        assert state_of(hass, NEXT) == at(SUNDAY, "19:30"), said
        await cancel_pending(hass, NUMBER, NEXT)


@pytest.mark.parametrize(
    ("said", "now", "day", "clock"),
    [
        ("at noon", "13:00", 1, "12:00"),
        ("at noon", "11:00", 0, "12:00"),
        ("at midnight", "13:00", 1, "00:00"),
        ("at midnight", "23:30", 1, "00:00"),
        ("at 12", "13:00", 1, "00:00"),
        ("at 12", "11:00", 0, "12:00"),
        ("at 12:30", "20:00", 1, "00:30"),
        ("at 12:30 am", "13:00", 1, "00:30"),
        ("at 12:30 pm", "13:00", 1, "12:30"),
    ],
)
async def test_noon_and_midnight_are_the_times_they_name_and_twelve_is_the_nearer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    said: str,
    now: str,
    day: int,
    clock: str,
) -> None:
    """The words name their time whenever they are said: "at noon" is never midnight.
    The bare "at 12" is a bare hour like the others, so it is the nearer of the two."""
    response = await say_at(hass, freezer, SUNDAY, now, f"turn on the boiler {said}")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=day), clock)


@pytest.mark.parametrize(
    ("said", "now", "day", "clock"),
    [
        ("at 7 in the morning", "18:00", 1, "07:00"),
        ("at 7 in the morning", "06:00", 0, "07:00"),
        ("at 7 in the afternoon", "06:00", 0, "19:00"),
        ("at 7 in the evening", "06:00", 0, "19:00"),
        ("at 7:30 in the evening", "06:00", 0, "19:30"),
        ("at 7 at night", "06:00", 0, "19:00"),
        ("at 2 at night", "06:00", 1, "02:00"),
        ("at 12 at night", "13:00", 1, "00:00"),
        ("at 7.30 in the evening", "06:00", 0, "19:30"),
        ("at 7 in the evening tomorrow", "06:00", 1, "19:00"),
        ("tomorrow at 7 in the morning", "18:00", 1, "07:00"),
        ("tomorrow morning at 7", "18:00", 1, "07:00"),
        ("tomorrow evening at 7", "06:00", 1, "19:00"),
        ("tomorrow afternoon at 3:15", "06:00", 1, "15:15"),
        ("tomorrow night at 11:30", "06:00", 1, "23:30"),
        ("tomorrow morning at 7 o'clock", "18:00", 1, "07:00"),
        ("at 7 tomorrow morning", "18:00", 1, "07:00"),
        ("at 7.30 tomorrow evening", "06:00", 1, "19:30"),
        ("the day after tomorrow morning at 7", "18:00", 2, "07:00"),
        ("today evening at 7", "06:00", 0, "19:00"),
        ("in the morning at 7", "18:00", 1, "07:00"),
        ("in the evening at 7:30", "06:00", 0, "19:30"),
        ("tomorrow in the morning at 7", "18:00", 1, "07:00"),
    ],
)
async def test_a_part_of_the_day_said_in_words_names_the_half_it_means(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    said: str,
    now: str,
    day: int,
    clock: str,
) -> None:
    """ "In the morning", "in the evening", "tomorrow morning" fix the half of the day
    as "am" and "pm" do: they are what a speaker whose "at 7" was read as the evening
    says to get the morning, and core's gazetteer turned the boiler on at once for
    them."""
    response = await say_at(hass, freezer, SUNDAY, now, f"turn on the boiler {said}")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=day), clock)
    assert fake_target.calls == []


@pytest.mark.parametrize(
    ("said", "now", "day", "clock"),
    [
        ("at midnight", "13:00", 1, "00:00"),
        ("at midnight", "00:10", 1, "00:00"),
        ("today at midnight", "13:00", 1, "00:00"),
        ("today at midnight", "00:10", 1, "00:00"),
        ("today at midnight", "23:30", 1, "00:00"),
        ("at midnight today", "13:00", 1, "00:00"),
        ("tomorrow at midnight", "13:00", 2, "00:00"),
        ("at midnight tomorrow", "13:00", 2, "00:00"),
        ("the day after tomorrow at midnight", "13:00", 3, "00:00"),
        ("tomorrow at 12 am", "13:00", 1, "00:00"),
        ("tomorrow at noon", "13:00", 1, "12:00"),
        ("today at noon", "11:00", 0, "12:00"),
    ],
)
async def test_midnight_with_a_day_is_the_one_that_ends_the_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    said: str,
    now: str,
    day: int,
    clock: str,
) -> None:
    """Said alone, "at midnight" is the next 00:00. With a day word it is the 00:00 that
    ends that day: "today at midnight" is tonight's and is never refused, and "tomorrow
    at midnight" is the one after tomorrow. "12 am" is the start of the day it names,
    and noon is 12:00 of it."""
    response = await say_at(hass, freezer, SUNDAY, now, f"turn on the boiler {said}")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=day), clock)


@pytest.mark.parametrize(
    ("said", "now", "day", "clock"),
    [
        ("tomorrow night at 2", "06:00", 2, "02:00"),
        ("tomorrow at 2 at night", "06:00", 2, "02:00"),
        ("at 2 at night tomorrow", "06:00", 2, "02:00"),
        ("tomorrow night at 5:30", "06:00", 2, "05:30"),
        ("tomorrow night at 12", "06:00", 2, "00:00"),
        ("tomorrow at midnight", "06:00", 2, "00:00"),
        ("today at 2 at night", "20:00", 1, "02:00"),
        ("today at 2 at night", "06:00", 1, "02:00"),
        ("today at 2 at night", "00:30", 0, "02:00"),
        ("today at 2 at night", "03:00", 1, "02:00"),
        ("today at 5 at night", "04:00", 0, "05:00"),
        ("today at 12 at night", "00:30", 1, "00:00"),
        ("tomorrow at 2 at night", "00:30", 2, "02:00"),
        ("the day after tomorrow at 2 at night", "06:00", 3, "02:00"),
        ("tomorrow night at 6", "06:00", 1, "18:00"),
        ("tomorrow night at 11:30", "06:00", 1, "23:30"),
        ("tomorrow at 2 am", "06:00", 1, "02:00"),
        ("tomorrow morning at 2", "06:00", 1, "02:00"),
        ("tomorrow at 0:00", "06:00", 1, "00:00"),
        ("at 2 at night", "20:00", 1, "02:00"),
        ("at 2 at night", "00:30", 0, "02:00"),
    ],
)
async def test_the_night_with_a_day_word_is_the_night_that_follows_that_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    said: str,
    now: str,
    day: int,
    clock: str,
) -> None:
    """The small hours of a night said with a day belong to the night after that day,
    as midnight does: "tomorrow at 2 at night" is 02:00 the day after tomorrow, and
    "today at 2 at night" is the coming 02:00, never refused. Said in the small hours
    it is the night in progress while that moment is ahead (at 00:30, 02:00 of the same
    date), and the next night's once it has passed (at 03:00). The evening hours of the
    night (6 to 11) and "am" are the day itself. Without a day word the next time that
    is ahead is the one."""
    response = await say_at(hass, freezer, SUNDAY, now, f"turn on the boiler {said}")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=day), clock)


@pytest.mark.parametrize(
    ("now", "answer"),
    [
        ("00:30", "Boiler turns on at 02:00."),
        ("03:00", "Boiler turns on at 02:00 tomorrow."),
    ],
)
async def test_the_answer_names_the_night_that_today_at_night_was_taken_for(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    now: str,
    answer: str,
) -> None:
    """Said at 00:30 on Sunday, "today at 2 at night" is Sunday's 02:00 and the answer
    names no day; said at 03:00 it is Monday's, and the answer says "tomorrow"."""
    response = await say_at(
        hass, freezer, SUNDAY, now, "turn on the boiler today at 2 at night"
    )

    assert speech(response) == answer


@pytest.mark.parametrize(
    ("now", "moment"),
    [
        (datetime(2026, 10, 24, 21, 30, tzinfo=UTC), "2026-10-24T22:30:00+00:00"),
        (datetime(2026, 10, 24, 22, 45, tzinfo=UTC), "2026-10-24T23:30:00+00:00"),
        (datetime(2026, 10, 24, 23, 45, tzinfo=UTC), "2026-10-25T11:30:00+00:00"),
    ],
    ids=["before the night", "first pass of 01:45", "second pass of 01:45"],
)
async def test_a_time_the_clock_repeats_is_the_earliest_of_its_moments_ahead(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    now: datetime,
    moment: str,
) -> None:
    """On 2026-10-25 the clock in Jerusalem goes back from 02:00 to 01:00, so 01:30 is
    on the wall twice, at 22:30 and at 23:30 UTC. "At 1:30" is the first from 00:30.
    Said at 01:45 in the first pass, the first 01:30 has passed and the second is
    ahead: it is the nearer of the times "1:30" can mean. Said at 01:45 in the second
    pass, both have passed and the next is 13:30."""
    await advance_to(hass, freezer, now)

    response = await converse(hass, "turn on the boiler at 1:30")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == moment


# --- Minutes around an hour (the owner's rule, issue 49) ---------------------------


@pytest.mark.parametrize(
    ("said", "clock", "days"),
    [
        ("at half past 7", "07:30", 0),
        ("at quarter past 7", "07:15", 0),
        ("at a quarter past 7", "07:15", 0),
        ("at ten past 7", "07:10", 0),
        ("at twenty-five past 7", "07:25", 0),
        ("at quarter to 8", "07:45", 0),
        ("at twenty to 8", "07:40", 0),
        ("at twenty-five to 8", "07:35", 0),
        ("at 5 to 8", "07:55", 0),
        ("at ten minutes to eight", "07:50", 0),
        ("at quarter to 8 in the evening", "19:45", 0),
        ("at quarter to 8 pm", "19:45", 0),
        ("tomorrow morning at quarter to 8", "07:45", 1),
        ("in the evening at half past 7", "19:30", 0),
        ("tomorrow at half past 7", "07:30", 1),
        ("at half past 7 tomorrow", "07:30", 1),
        ("at quarter to noon", "11:45", 0),
        ("at quarter to midnight", "23:45", 0),
    ],
)
async def test_minutes_around_an_hour_mean_their_time(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    said: str,
    clock: str,
    days: int,
) -> None:
    """Any number of minutes from 1 to 59 is counted past an hour or to the next, and
    "quarter" and "half" are only words for 15 and 30."""
    response = await converse(hass, f"turn on the boiler {said}")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=days), clock)
    assert fake_target.calls == []


@pytest.mark.parametrize(
    ("said", "clock", "minutes"),
    [
        ("at quarter to 8", "07:45", "105"),
        ("at half past 7", "07:30", "90"),
        ("at ten to 8", "07:50", "110"),
    ],
)
async def test_minutes_around_an_hour_end_a_countdown_then(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    said: str,
    clock: str,
    minutes: str,
) -> None:
    """A running boiler is told when to stop, as "turn off at 7:30" does."""
    await set_number(hass, NUMBER, 240)

    response = await converse(hass, f"turn off the boiler {said}")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, SENSOR) == at(SUNDAY, clock)
    assert state_of(hass, NUMBER) == minutes
    assert pending(hass) == []


@pytest.mark.parametrize(
    ("now", "said", "days", "clock"),
    [
        ("06:00", "at quarter to 8", 0, "07:45"),
        ("08:00", "at quarter to 8", 0, "19:45"),
        ("19:50", "at quarter to 8", 1, "07:45"),
        ("20:00", "at half past 7", 1, "07:30"),
        ("08:00", "at half past 7", 0, "19:30"),
    ],
)
async def test_minutes_before_an_hour_are_the_nearer_time_ahead(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    now: str,
    said: str,
    days: int,
    clock: str,
) -> None:
    """The rule of "7:30" holds for these forms: with no part of the day, the time is
    the nearer of its morning and evening ones that is still ahead."""
    response = await say_at(hass, freezer, SUNDAY, now, f"turn on the boiler {said}")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=days), clock)


@pytest.mark.parametrize(
    ("now", "said", "days", "clock"),
    [
        ("06:00", "at quarter to 12", 0, "11:45"),
        ("12:00", "at quarter to 12", 0, "23:45"),
        ("12:00", "at quarter to noon", 1, "11:45"),
        ("23:50", "at quarter to midnight", 1, "23:45"),
        ("06:00", "today at quarter to midnight", 0, "23:45"),
        ("06:00", "tomorrow at quarter to midnight", 1, "23:45"),
        ("06:00", "at ten to 1 at night", 1, "00:50"),
        ("20:00", "today at ten to 1 at night", 1, "00:50"),
    ],
)
async def test_minutes_before_twelve_noon_and_midnight(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    now: str,
    said: str,
    days: int,
    clock: str,
) -> None:
    """Noon and midnight, and the 12 and the small hours of the night, count minutes to
    them as any hour does: "quarter to midnight" is 23:45, and the night is the one
    that follows the day word."""
    response = await say_at(hass, freezer, SUNDAY, now, f"turn on the boiler {said}")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=days), clock)


@pytest.mark.usefixtures("assist")
@pytest.mark.parametrize(
    ("said", "day", "clock"),
    [
        ("turn on the AC for an hour at quarter to 8", SUNDAY, "07:45"),
        ("turn on the AC for an hour at half past 7 in the evening", SUNDAY, "19:30"),
    ],
)
async def test_a_thermostat_takes_minutes_around_an_hour_after_its_settings(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_full_ac: FakeTarget,
    setup_target: SetupTarget,
    said: str,
    day: date,
    clock: str,
) -> None:
    """Minutes past or to an hour are no temperature, so a thermostat takes them after
    its settings as it takes "7:30"."""
    await open_sunday(hass, freezer)
    await with_voice_settings(hass, setup_target, fake_full_ac)

    response = await converse(hass, said)

    assert reached(response) == CLOCK, speech(response)
    assert fake_full_ac.call_data == []
    command = pending(hass, AC_NEXT)[0]
    assert command["minutes"] == 60
    assert state_of(hass, AC_NEXT) == at(day, clock)


@pytest.mark.parametrize(
    "said",
    [
        "turn on the boiler at 0 past 7",
        "turn on the boiler at 60 to 8",
        "turn on the boiler at 15 to 13",
        "turn on the boiler at half past noon",
        "turn on the boiler at half to 8",
        "turn on the boiler at twenty to",
    ],
)
async def test_minutes_around_an_hour_out_of_bounds_are_not_understood(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    said: str,
) -> None:
    """The minutes are 1 to 59 and the hour 1 to 12; "half" is past an hour only, and
    noon has no minutes past it. What is not a time reaches no handler, and nothing is
    kept or switched."""
    response = await converse(hass, said)

    assert reached(response) is None, speech(response)
    assert response.response_type is intent.IntentResponseType.ERROR
    assert pending(hass) == []
    assert fake_target.calls == []


# --- A part of the day before the time, and am or pm after the minutes (issue 49) --


@pytest.mark.parametrize(
    ("said", "clock", "days"),
    [
        ("at 7:30am", "07:30", 0),
        ("at 7:30pm", "19:30", 0),
        ("at 7.30pm", "19:30", 0),
        ("tonight at 7", "19:00", 0),
        ("tonight at 11", "23:00", 0),
        ("tonight at 2", "02:00", 1),
        ("tonight at 12", "00:00", 1),
        ("at 7 tonight", "19:00", 0),
        ("tonight at quarter to 8", "19:45", 0),
        ("this morning at 7", "07:00", 0),
        ("this afternoon at 3", "15:00", 0),
        ("this evening at half past 7", "19:30", 0),
        ("tonight at 7 pm", "19:00", 0),
        ("tonight at 7:30pm", "19:30", 0),
        ("tonight at 5 pm", "17:00", 0),
        ("at 7 pm tonight", "19:00", 0),
        ("this evening at 7 pm", "19:00", 0),
        ("this morning at 7am", "07:00", 0),
        ("tomorrow evening at 7:30 pm", "19:30", 1),
        ("in the evening at 7 pm", "19:00", 0),
    ],
)
async def test_a_part_of_the_day_before_the_time_means_its_time(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    said: str,
    clock: str,
    days: int,
) -> None:
    """ "Am" and "pm" may be written right after the minutes, and "tonight", "this
    morning" and the like name today's part of the day: said on Sunday at six in the
    morning they are the times of today, and the small hours of "tonight" are the night
    that follows today. A part of the day said as a word may be repeated by its own
    "am" or "pm" after the time, which then decides the half: "tonight at 5 pm" is
    17:00."""
    response = await converse(hass, f"turn on the boiler {said}")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=days), clock)
    assert fake_target.calls == []


@pytest.mark.parametrize(
    ("said", "clock", "minutes"),
    [
        ("at 7:30am", "07:30", "90"),
        ("this morning at 9", "09:00", "180"),
        ("tonight at 7", "19:00", "780"),
    ],
)
async def test_a_part_of_the_day_before_the_time_ends_a_countdown_then(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    said: str,
    clock: str,
    minutes: str,
) -> None:
    """A running boiler is told when to stop, as "turn off at 7:30" does."""
    await set_number(hass, NUMBER, 240)

    response = await converse(hass, f"turn off the boiler {said}")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, SENSOR) == at(SUNDAY, clock)
    assert state_of(hass, NUMBER) == minutes
    assert pending(hass) == []


@pytest.mark.parametrize(
    ("now", "said", "at_time"),
    [
        ("20:00", "tonight at 7", "19:00"),
        ("08:00", "this morning at 7", "07:00"),
        ("20:00", "this evening at half past 7", "19:30"),
    ],
)
async def test_tonight_or_this_morning_that_has_passed_is_refused(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    now: str,
    said: str,
    at_time: str,
) -> None:
    """ "Tonight", "this morning" and "this evening" name today, as "today" does: the
    time that has passed is not moved to tomorrow, and nothing is kept."""
    response = await say_at(hass, freezer, SUNDAY, now, f"turn on the boiler {said}")

    assert reached(response) == CLOCK, speech(response)
    assert refusal_of(response) == translated(
        "en", "exceptions", "command_in_past", "message"
    ).format(at=at_time)
    assert state_of(hass, NEXT) == "unknown"
    assert pending(hass) == []
    assert fake_target.calls == []


@pytest.mark.parametrize(
    ("now", "days", "clock"), [("01:00", 0, "02:00"), ("23:30", 1, "02:00")]
)
async def test_tonight_at_a_small_hour_is_the_night_in_progress_or_the_next(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    now: str,
    days: int,
    clock: str,
) -> None:
    """ "Tonight at 2" said in the small hours is the night in progress while 02:00 is
    still ahead, as "today at 2 at night" is; said at 23:30 it is the 02:00 that follows
    the day."""
    response = await say_at(
        hass, freezer, SUNDAY, now, "turn on the boiler tonight at 2"
    )

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=days), clock)


async def test_how_long_it_runs_is_read_with_a_part_of_the_day_and_its_mark(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
) -> None:
    """The mark after the time does not swallow the length of the run, said before the
    time or after it: one reading, 2 hours at 19:00."""
    for said in (
        "turn on the boiler for 2 hours tonight at 7 pm",
        "turn on the boiler tonight at 7 pm for 2 hours",
    ):
        response = await converse(hass, said)

        assert reached(response) == CLOCK, said
        assert state_of(hass, NEXT) == at(SUNDAY, "19:00"), said
        assert [command["minutes"] for command in pending(hass)] == [120], said
        await cancel_pending(hass, NUMBER, NEXT)
    assert fake_target.calls == []


@pytest.mark.usefixtures("assist")
@pytest.mark.parametrize(
    "said",
    [
        "turn on the AC for an hour at 22 tonight at 7:30pm",
        "turn on the AC tonight at 7:30pm for an hour at 22",
    ],
)
async def test_a_temperature_is_read_beside_a_part_of_the_day_with_its_mark(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_full_ac: FakeTarget,
    setup_target: SetupTarget,
    said: str,
) -> None:
    """The number after "at" is the temperature and the time is 19:30 tonight: the
    mark after the time leaves one reading, and the AC is not set at once."""
    await open_sunday(hass, freezer)
    await with_voice_settings(hass, setup_target, fake_full_ac)

    response = await converse(hass, said)

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, AC_NEXT) == at(SUNDAY, "19:30")
    assert [(c["minutes"], c["settings"]) for c in pending(hass, AC_NEXT)] == [
        (60, {"temperature": 22.0})
    ]
    assert fake_full_ac.call_data == []


# --- Russian -----------------------------------------------------------------------


async def test_russian_clock_forms_reach_the_clock_handler(
    hass: HomeAssistant, fake_target: FakeTarget, clock_boiler: MockConfigEntry
) -> None:
    """Every sentence the shipped files can say a clock time with, in Russian, reaches
    the handler: the sampled sentences, and each way of saying the time after a
    command."""
    sentences = samples(
        "ru",
        CLOCK,
        takeover=True,
        numbers=NUMBERS,
        texts=MINUTES,
        absent=SETTING_LISTS,
        admitting="switch",
    )
    sentences += [
        turn_on_at("ru", form)
        for form in spoken_rule("ru", "timerify_clock", NUMBERS, MINUTES)
    ]
    assert len(sentences) > 100

    for text in sentences:
        response = await converse(hass, text, "ru")

        assert reached(response) == CLOCK, text
        await cancel_pending(hass, NUMBER, NEXT)
    assert fake_target.calls == []


async def test_english_clock_forms_reach_the_clock_handler(
    hass: HomeAssistant, fake_target: FakeTarget, clock_boiler: MockConfigEntry
) -> None:
    """The same of English: every sentence sampled, and each form of the time."""
    sentences = samples(
        "en",
        CLOCK,
        takeover=True,
        numbers=NUMBERS,
        texts=MINUTES,
        absent=SETTING_LISTS,
        admitting="switch",
    )
    sentences += [
        turn_on_at("en", form)
        for form in spoken_rule("en", "timerify_clock", NUMBERS, MINUTES)
    ]
    assert len(sentences) > 40

    for text in sentences:
        response = await converse(hass, text, "en")

        assert reached(response) == CLOCK, text
        await cancel_pending(hass, NUMBER, NEXT)
    assert fake_target.calls == []


def russian_minute_form(hour: int, separator: str, minute: str) -> str:
    """The Russian way of saying `hour` and `minute` with `separator` between them, read
    from the shipped sentences with the minute written as `minute`: it may be one digit,
    which the sentences do not say."""
    numbers = {**NUMBERS, "timerify_clock_hours": hour}
    return russian_form(
        rf"\S+ {hour}{re.escape(separator)}{minute}",
        numbers,
        {"timerify_clock_minute_digits": minute},
    )


@pytest.mark.parametrize("separator", [":", ".", " "])
async def test_russian_minutes_of_two_digits_make_a_time(
    hass: HomeAssistant,
    clock_boiler: MockConfigEntry,
    separator: str,
) -> None:
    form = russian_minute_form(7, separator, "05")

    response = await converse(hass, turn_on_at("ru", form), "ru")

    assert reached(response) == CLOCK, form
    assert state_of(hass, NEXT) == at(SUNDAY, "07:05")


@pytest.mark.parametrize("hour", [7, 22])
@pytest.mark.parametrize("separator", [":", ".", " "])
async def test_russian_minute_of_one_digit_after_a_separator_is_no_time(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    hour: int,
    separator: str,
) -> None:
    """As in English, "v 7.5" is no 7:05: the sentence is not understood, no command is
    kept, and the boiler is left alone."""
    form = russian_minute_form(hour, separator, "5")

    response = await converse(hass, turn_on_at("ru", form), "ru")

    assert reached(response) is None, speech(response)
    assert response.response_type is intent.IntentResponseType.ERROR
    assert pending(hass) == []
    assert fake_target.calls == []


async def test_russian_minutes_said_with_their_word_may_be_one_digit(
    hass: HomeAssistant, fake_target: FakeTarget, clock_boiler: MockConfigEntry
) -> None:
    """ "7 hours 5 minutes" names the minutes with their word, so a single digit says
    them as plainly as two: it is 07:05."""
    numbers = {**NUMBERS, "timerify_clock_minutes": 5}
    forms = [
        form
        for form in spoken_rule("ru", "timerify_clock", numbers, MINUTES)
        if re.fullmatch(r"\S+ 7 \S+ 5 \S+", form)
    ]
    assert forms

    for form in forms:
        response = await converse(hass, turn_on_at("ru", form), "ru")

        assert reached(response) == CLOCK, form
        assert state_of(hass, NEXT) == at(SUNDAY, "07:05"), form
        await cancel_pending(hass, NUMBER, NEXT)
    assert fake_target.calls == []


@pytest.mark.parametrize(
    ("part", "hour", "days", "clock"),
    [
        ("am", 7, 0, "07:00"),
        ("pm", 7, 0, "19:00"),
        ("night", 7, 0, "19:00"),
        ("night", 2, 1, "02:00"),
    ],
)
async def test_russian_day_parts_mean_the_hours_they_name(
    hass: HomeAssistant,
    clock_boiler: MockConfigEntry,
    part: str,
    hour: int,
    days: int,
    clock: str,
) -> None:
    """Said at six in the morning, 7 "utra" (morning) is 07:00 and 7 "dnya" (afternoon)
    or "vechera" (evening) is 19:00; at night 7 is the evening and 2 is the small
    hours, which at six in the morning are tomorrow's."""
    words = spoken_values("ru", "timerify_day_parts")[part]
    numbers = {**NUMBERS, "timerify_half_day_hours": hour}
    assert words

    for word in words:
        form = russian_form(
            rf"\S+ {hour} {re.escape(word)}", numbers, {"timerify_day_parts": word}
        )
        response = await converse(hass, turn_on_at("ru", form), "ru")

        assert reached(response) == CLOCK, form
        assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=days), clock), form
        await cancel_pending(hass, NUMBER, NEXT)


@pytest.mark.parametrize(
    ("part", "now", "days", "clock"),
    [
        ("pm", "13:00", 1, "12:00"),
        ("pm", "11:00", 0, "12:00"),
        ("am", "13:00", 1, "00:00"),
        ("am", "11:00", 1, "00:00"),
    ],
)
async def test_the_russian_words_for_noon_and_midnight_name_their_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    part: str,
    now: str,
    days: int,
    clock: str,
) -> None:
    """The word for noon is 12:00 and the word for midnight 00:00, said before noon or
    after it, where a bare 12 would be the midnight or the noon that is nearer."""
    word = spoken_values("ru", "timerify_clock_words")[part][0]
    form = russian_form(rf"\S+ {re.escape(word)}", texts={"timerify_clock_words": word})

    response = await say_at(hass, freezer, SUNDAY, now, turn_on_at("ru", form), "ru")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=days), clock)


@pytest.mark.parametrize(
    ("day", "days", "day_first"),
    [
        ("0", 1, True),
        ("0", 1, False),
        ("1", 2, True),
        ("1", 2, False),
        ("2", 3, True),
    ],
)
async def test_the_russian_midnight_with_a_day_is_the_one_that_ends_the_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    day: str,
    days: int,
    day_first: bool,
) -> None:
    """As in English: with the word for today, tomorrow or the day after, the word for
    midnight is the 00:00 that ends that day, whichever comes first in the sentence."""
    midnight = re.escape(spoken_values("ru", "timerify_clock_words")["am"][0])
    word = re.escape(spoken_values("ru", "timerify_clock_days")[day][0])
    texts = {
        "timerify_clock_words": spoken_values("ru", "timerify_clock_words")["am"][0],
        "timerify_clock_days": spoken_values("ru", "timerify_clock_days")[day][0],
    }
    pattern = rf"{word} \S+ {midnight}" if day_first else rf"\S+ {midnight} {word}"
    form = russian_form(pattern, texts=texts)

    response = await say_at(
        hass, freezer, SUNDAY, "13:00", turn_on_at("ru", form), "ru"
    )

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=days), "00:00")


@pytest.mark.parametrize(
    ("day", "part", "hour", "now", "days", "clock"),
    [
        ("1", "night", 2, "06:00", 2, "02:00"),
        ("1", "night", 12, "06:00", 2, "00:00"),
        ("1", "night", 5, "06:00", 2, "05:00"),
        ("0", "night", 2, "20:00", 1, "02:00"),
        ("0", "night", 2, "06:00", 1, "02:00"),
        ("0", "night", 2, "00:30", 0, "02:00"),
        ("0", "night", 2, "03:00", 1, "02:00"),
        ("1", "night", 2, "00:30", 2, "02:00"),
        ("2", "night", 2, "06:00", 3, "02:00"),
        ("1", "night", 6, "06:00", 1, "18:00"),
        ("1", "night", 11, "06:00", 1, "23:00"),
        ("1", "am", 2, "06:00", 1, "02:00"),
    ],
)
@pytest.mark.parametrize("day_first", [True, False])
async def test_the_russian_night_with_a_day_is_the_night_that_follows_that_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    day: str,
    part: str,
    hour: int,
    now: str,
    days: int,
    clock: str,
    day_first: bool,
) -> None:
    """As in English: with the word for today, tomorrow or the day after, the word for
    the night and an hour of the small hours (12 or 1 to 5) is the night after that
    day, whichever comes first in the sentence. Said in the small hours, "today" is the
    night in progress while that moment is ahead. The word for the morning is a half of
    the clock: tomorrow at 2 in the morning is 02:00 tomorrow."""
    day_word = spoken_values("ru", "timerify_clock_days")[day][0]
    part_word = spoken_values("ru", "timerify_day_parts")[part][0]
    texts = {"timerify_clock_days": day_word, "timerify_day_parts": part_word}
    numbers = {**NUMBERS, "timerify_half_day_hours": hour}
    time = rf"\S+ {hour} {re.escape(part_word)}"
    pattern = (
        rf"{re.escape(day_word)} {time}"
        if day_first
        else rf"{time} {re.escape(day_word)}"
    )
    form = russian_form(pattern, numbers, texts)

    response = await say_at(hass, freezer, SUNDAY, now, turn_on_at("ru", form), "ru")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=days), clock)


@pytest.mark.parametrize(("now", "tomorrow"), [("00:30", False), ("03:00", True)])
async def test_the_russian_answer_names_the_night_that_today_was_taken_for(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    now: str,
    tomorrow: bool,
) -> None:
    """As in English: said at 00:30, today at 2 at night is Sunday's 02:00 and the
    answer does not say tomorrow; said at 03:00 it is Monday's, and it does."""
    day_word = spoken_values("ru", "timerify_clock_days")["0"][0]
    part_word = spoken_values("ru", "timerify_day_parts")["night"][0]
    texts = {"timerify_clock_days": day_word, "timerify_day_parts": part_word}
    numbers = {**NUMBERS, "timerify_half_day_hours": 2}
    form = russian_form(
        rf"{re.escape(day_word)} \S+ 2 {re.escape(part_word)}", numbers, texts
    )

    response = await say_at(hass, freezer, SUNDAY, now, turn_on_at("ru", form), "ru")

    tomorrow_word = spoken_values("ru", "timerify_clock_days")["1"][0]
    assert (tomorrow_word in speech(response)) is tomorrow, speech(response)
    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=int(tomorrow)), "02:00")


async def test_the_russian_start_of_a_day_is_said_with_the_hour_0(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, clock_boiler: MockConfigEntry
) -> None:
    """The 00:00 that starts tomorrow is "tomorrow at 0:00": the hour 0 is the 24-hour
    clock's, with a day word as without one."""
    day_text = spoken_values("ru", "timerify_clock_days")["1"][0]
    texts = {"timerify_clock_days": day_text, "timerify_clock_minute_digits": "00"}
    numbers = {**NUMBERS, "timerify_clock_hours": 0}
    form = russian_form(rf"{re.escape(day_text)} \S+ 0:00", numbers, texts)

    response = await say_at(
        hass, freezer, SUNDAY, "06:00", turn_on_at("ru", form), "ru"
    )

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(MONDAY, "00:00")


# --- Russian minutes around an hour (the fixture is written by hand) -----------------


YO = "\N{CYRILLIC SMALL LETTER IO}"
YE = "\N{CYRILLIC SMALL LETTER IE}"
"""The Russian letters "yo" and "ye", which the library of number words does not tell
apart in the fourth hour; a test source has no Russian letter of its own."""


def phrases_of(field: str) -> list[str]:
    """The names of the hand-written Russian clock phrases that have `field`, the field
    that tells their kind: the time they mean (`clock`), a refusal (`refused`) or no
    time (`understood`)."""
    return [name for name, case in russian_clock_phrases().items() if field in case]


def test_every_russian_clock_phrase_is_of_one_kind() -> None:
    """A case with no kind, or two, would be run by no test or by two, and a repeated
    name would drop a case from the file's index: none is skipped in silence."""
    cases = yaml.safe_load(CLOCK_PHRASES.read_text("utf-8"))
    names = [case["name"] for case in cases]
    assert len(set(names)) == len(names)
    for case in cases:
        assert {"name", "said", "now"} <= set(case), case["name"]
        kind = set(case) - {"name", "said", "now"}
        assert kind in ({"days", "clock"}, {"refused"}, {"understood"}), case["name"]
        if "understood" in case:
            assert case["understood"] is False, case["name"]
    # Each kind has a test that runs its cases: a kind with none would run nothing.
    assert phrases_of("clock")
    assert phrases_of("refused")
    assert phrases_of("understood")


@pytest.mark.parametrize("name", phrases_of("clock"))
async def test_russian_clock_phrases_mean_their_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    name: str,
) -> None:
    """What a speaker of Russian means by counting minutes to an hour, or to the next:
    the time in the file, kept as a command and not carried out."""
    case = russian_clock_phrases()[name]

    response = await say_at(
        hass, freezer, SUNDAY, case["now"], turn_on_at("ru", case["said"]), "ru"
    )

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(
        SUNDAY + timedelta(days=case["days"]), case["clock"]
    )
    assert fake_target.calls == []


@pytest.mark.parametrize("name", phrases_of("refused"))
async def test_russian_clock_phrases_that_have_passed_today_are_refused(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    name: str,
) -> None:
    """A time named "today" that has passed is refused with the time the speaker said,
    and is not moved to tomorrow."""
    case = russian_clock_phrases()[name]

    response = await say_at(
        hass, freezer, SUNDAY, case["now"], turn_on_at("ru", case["said"]), "ru"
    )

    assert reached(response) == CLOCK, speech(response)
    assert refusal_of(response) == translated(
        "ru", "exceptions", "command_in_past", "message"
    ).format(at=case["refused"])
    assert state_of(hass, NEXT) == "unknown"
    assert fake_target.calls == []


@pytest.mark.parametrize("name", phrases_of("understood"))
async def test_russian_phrases_that_are_no_clock_time_are_not_understood(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    name: str,
) -> None:
    """A date, or minutes counted to no hour, are no time: no handler is reached,
    nothing is kept and the boiler is left alone."""
    case = russian_clock_phrases()[name]

    response = await say_at(
        hass, freezer, SUNDAY, case["now"], turn_on_at("ru", case["said"]), "ru"
    )

    assert reached(response) is None, speech(response)
    assert response.response_type is intent.IntentResponseType.ERROR
    assert pending(hass) == []
    assert fake_target.calls == []


def test_the_russian_hours_counted_to_are_the_ordinals_of_the_library() -> None:
    """The twelve hours the sentences count minutes to are the genitive ordinals that
    the library of number words gives, so that the list is checked against a source
    other than the file that holds it. The fourth is also said with the letter "ye"."""
    listed = spoken_values("ru", "timerify_clock_hour_ordinals")
    engine = RbnfEngine.for_language("ru")

    assert sorted(listed, key=int) == [str(n) for n in range(1, 13)]
    for hour in range(1, 13):
        ordinal = engine.format_number(
            hour, ruleset_names=["spellout-ordinal-masculine-genitive"]
        ).text
        assert {word.replace(YO, YE) for word in listed[str(hour)]} == {ordinal}, hour


# --- What the sentences do not say, and what core's gazetteer took -----------------


@pytest.mark.parametrize(
    "said",
    [
        "turn on the boiler at 7",
        "turn on the boiler tomorrow at 7",
        "turn on the boiler at noon",
        "turn off the boiler at 7",
        "turn on the boiler at 7 in the morning",
        "turn on the boiler at 7 in the evening",
        "turn on the boiler tomorrow morning at 7",
        "turn on the boiler tomorrow at 7 in the morning",
        "turn on the boiler in the morning at 7",
        "turn off the boiler at 7 in the morning",
        "turn off the boiler tomorrow evening at 7",
    ],
)
async def test_the_clock_phrasings_the_gazetteer_took_are_timerify_s_now(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    said: str,
) -> None:
    """The gazetteer turns a device on or off at once for these, in English. They are
    Timerify's sentences now, so the boiler is not switched: a command waits, or there
    is nothing to turn off."""
    response = await converse(hass, said)

    assert reached(response) == CLOCK, speech(response)
    assert fake_target.calls == []


@pytest.mark.parametrize(
    ("said", "reached_intent", "call"),
    [
        ("turn on the boiler tonight", "HassTurnOn", "turn_on"),
        ("turn on the boiler this evening", "HassTurnOn", "turn_on"),
        ("turn on the boiler tomorrow morning", "HassTurnOn", "turn_on"),
        ("turn off the boiler tonight", "HassTurnOff", "turn_off"),
    ],
)
async def test_a_part_of_the_day_with_no_hour_is_left_to_the_gazetteer(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    said: str,
    reached_intent: str,
    call: str,
) -> None:
    """A part of the day with no hour names no time to plan: these stay core's (issue
    21), which switches the boiler at once in English, and no command is kept."""
    response = await converse(hass, said)

    assert reached(response) == reached_intent, speech(response)
    assert pending(hass) == []
    assert fake_target.calls == [(call, fake_target.entity_id)]


@pytest.mark.parametrize(
    "said",
    [
        "turn on the boiler at 25:00",
        "turn on the boiler at 24:00",
        "turn on the boiler at 7:60",
        "turn off the boiler at 25",
    ],
)
async def test_a_time_that_is_none_is_not_understood(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    said: str,
) -> None:
    """The hour is 0 to 23 and the minutes 0 to 59. What is not a time reaches no
    handler, neither Timerify's nor Home Assistant's, and nothing is kept or
    switched."""
    response = await converse(hass, said)

    assert reached(response) is None, speech(response)
    assert response.response_type is intent.IntentResponseType.ERROR
    assert pending(hass) == []
    assert fake_target.calls == []


@pytest.mark.parametrize(
    "said",
    [
        "turn on the boiler at 7:30a.m.",
        "turn on the boiler at 7:30p.m.",
        "turn on the boiler at 7.30a.m.",
        "turn on the boiler tonight at 7 am",
        "turn on the boiler tonight at 7:30am",
        "turn on the boiler this morning at 7 pm",
        "turn on the boiler this evening at 7am",
        "turn on the boiler tomorrow morning at 7:30 pm",
        "turn on the boiler at 7 am tonight",
        "turn on the boiler tomorrow night at 7 pm",
        "turn on the boiler this evening at half past 7 pm",
    ],
)
async def test_the_forms_left_out_of_a_part_of_the_day_are_not_understood(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    said: str,
) -> None:
    """Only "am" and "pm" are written right after the minutes: with their dots they
    are not. A part of the day said as a word is repeated only by the mark of its own
    half, so "tonight at 7 am" and "this morning at 7 pm" say two halves of the day,
    "night" has no mark to repeat it, and minutes past or to an hour take none after a
    part of the day. What is not a time reaches no handler, and nothing is kept or
    switched."""
    response = await converse(hass, said)

    assert reached(response) is None, speech(response)
    assert response.response_type is intent.IntentResponseType.ERROR
    assert pending(hass) == []
    assert fake_target.calls == []


@pytest.mark.parametrize(
    "said",
    [
        "turn on the boiler at 7.5",
        "turn on the boiler at 7:5",
        "turn on the boiler at 7 5",
        "turn on the boiler at 19:5",
        "turn on the boiler at 7.5 pm",
        "turn on the boiler in the morning at 7.5",
        "turn on the boiler at 7:015",
        "turn off the boiler at 7.5",
    ],
)
async def test_a_minute_of_one_digit_after_a_separator_is_no_time(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    said: str,
) -> None:
    """ "7.5" is seven and a half, if it is anything, and nobody writes 7:05 as "7:5": a
    minute after a colon, a dot or a space is two digits. The sentence is not
    understood, so no command is kept for a time nobody said, and the boiler, which
    Home Assistant's own sentences could turn on at once, is left alone."""
    response = await converse(hass, said)

    assert reached(response) is None, speech(response)
    assert response.response_type is intent.IntentResponseType.ERROR
    assert pending(hass) == []
    assert fake_target.calls == []


@pytest.mark.usefixtures("assist")
@pytest.mark.parametrize(
    "said",
    [
        "turn on the AC at 22.5 for an hour",
        "turn on the AC at 22:5 for an hour",
        "turn on the AC at 7.5 for an hour",
    ],
)
async def test_a_temperature_said_before_how_long_is_no_time_of_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_full_ac: FakeTarget,
    setup_target: SetupTarget,
    said: str,
) -> None:
    """A temperature with a dot, said before how long the AC runs, is not read as the
    time 22:05: the sentence is not understood, nothing is kept for any time, and the
    AC is neither turned on nor given the temperature."""
    await open_sunday(hass, freezer)
    await with_voice_settings(hass, setup_target, fake_full_ac)

    response = await converse(hass, said)

    assert reached(response) is None, speech(response)
    assert response.response_type is intent.IntentResponseType.ERROR
    assert pending(hass, AC_NEXT) == []
    assert fake_full_ac.call_data == []


@pytest.mark.usefixtures("assist")
async def test_a_time_of_two_digit_minutes_is_kept_with_how_long_the_ac_runs(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_full_ac: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """ "At 22.05 for an hour" is a time: the command waits for 22:05, and the AC is not
    turned on now."""
    await open_sunday(hass, freezer)
    await with_voice_settings(hass, setup_target, fake_full_ac)

    response = await converse(hass, "turn on the AC at 22.05 for an hour")

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, AC_NEXT) == at(SUNDAY, "22:05")
    assert [c["minutes"] for c in pending(hass, AC_NEXT)] == [60]
    assert fake_full_ac.call_data == []


@pytest.mark.parametrize(
    "slots",
    [
        {},
        {"clock_day": 1},
        {"clock_part": "night"},
        {"clock_minute": 30},
        {"clock_part": "pm", "clock_minute": 30},
    ],
    ids=["nothing", "a day only", "night", "minutes only", "noon with minutes"],
)
async def test_a_time_with_no_hour_that_is_not_noon_or_midnight_is_not_understood(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    slots: dict[str, object],
) -> None:
    """Noon and midnight are a part of the day with no hour; no sentence makes any
    other time without one. Slots that say it, from a caller that is not a sentence,
    are refused as invalid, not read as the nearer of noon and midnight, and nothing is
    kept or switched."""
    said = {"name": "Boiler", "action": "on", **slots}

    with pytest.raises(intent.InvalidSlotInfo):
        await intent.async_handle(
            hass,
            "test",
            CLOCK,
            {key: {"value": value} for key, value in said.items()},
        )

    assert pending(hass) == []
    assert fake_target.calls == []


@pytest.mark.parametrize(
    ("slots", "day", "clock"),
    [
        ({"clock_part": "pm"}, 1, "12:00"),
        ({"clock_part": "am"}, 1, "00:00"),
        ({"clock_part": "pm", "clock_day": 1}, 1, "12:00"),
        ({"clock_part": "am", "clock_day": 0}, 1, "00:00"),
    ],
    ids=["noon", "midnight", "noon tomorrow", "midnight today"],
)
async def test_noon_and_midnight_are_the_only_times_with_no_hour(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    slots: dict[str, object],
    day: int,
    clock: str,
) -> None:
    """The part of the day with no hour that the sentences of noon and midnight make is
    read as such, from the handler as from a sentence."""
    await advance_to(hass, freezer, local(SUNDAY, "13:00"))
    said = {"name": "Boiler", "action": "on", **slots}

    await intent.async_handle(
        hass,
        "test",
        CLOCK,
        {key: {"value": value} for key, value in said.items()},
    )

    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=day), clock)


@pytest.mark.parametrize(
    ("slots", "days", "clock"),
    [
        ({"clock_ordinal": 8, "clock_minute": 30}, 0, "07:30"),
        ({"clock_ordinal": 1, "clock_minute": 30, "clock_part": "night"}, 1, "00:30"),
        ({"clock_ordinal": 6, "clock_minute": 30, "clock_part": "night"}, 1, "05:30"),
        ({"clock_ordinal": 12, "clock_minute": 30, "clock_part": "am"}, 0, "11:30"),
        (
            {
                "clock_ordinal": 1,
                "clock_minute": 30,
                "clock_part": "night",
                "clock_day": 1,
            },
            2,
            "00:30",
        ),
    ],
    ids=[
        "the eighth",
        "the first at night",
        "the sixth at night",
        "the twelfth am",
        "the first at night tomorrow",
    ],
)
async def test_an_ordinal_hour_is_the_hour_that_ends_it(
    hass: HomeAssistant,
    clock_boiler: MockConfigEntry,
    slots: dict[str, object],
    days: int,
    clock: str,
) -> None:
    """The Nth hour of the dial is the one that runs from N-1 to N, so 30 minutes of the
    eighth is 07:30 and of the first, which is 12 less one, is 00:30; a part of the day
    still names the half."""
    await say_slots(hass, slots)

    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=days), clock)


@pytest.mark.parametrize(
    ("slots", "days", "clock"),
    [
        ({"clock_hour": 8, "clock_before": 15}, 0, "07:45"),
        ({"clock_part": "pm", "clock_before": 15}, 0, "11:45"),
        ({"clock_part": "am", "clock_before": 15}, 0, "23:45"),
        ({"clock_part": "am", "clock_before": 15, "clock_day": 0}, 0, "23:45"),
        ({"clock_part": "am", "clock_before": 15, "clock_day": 1}, 1, "23:45"),
        (
            {"clock_hour": 12, "clock_part": "am", "clock_before": 15, "clock_day": 1},
            1,
            "23:45",
        ),
        ({"clock_hour": 12, "clock_before": 15, "clock_day": 0}, 0, "11:45"),
        ({"clock_hour": 12, "clock_before": 15, "clock_day": 1}, 1, "11:45"),
        ({"clock_hour": 1, "clock_before": 15, "clock_day": 1}, 1, "00:45"),
    ],
    ids=[
        "an hour",
        "noon",
        "midnight",
        "midnight today",
        "midnight tomorrow",
        "12 am tomorrow",
        "12 today",
        "12 tomorrow",
        "1 tomorrow",
    ],
)
async def test_minutes_before_come_with_an_hour_or_noon_or_midnight(
    hass: HomeAssistant,
    clock_boiler: MockConfigEntry,
    slots: dict[str, object],
    days: int,
    clock: str,
) -> None:
    """Minutes before an hour are said of a named hour, and of noon and midnight, which
    have no hour: "quarter to midnight" is 23:45, and "tomorrow at quarter to midnight"
    is the 23:45 that ends tomorrow. A day word names the day of the time, so "tomorrow
    at quarter to 12" is 11:45 tomorrow and not the 23:45 of today."""
    await say_slots(hass, slots)

    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=days), clock)


@pytest.mark.parametrize(
    ("now", "clock"), [("06:00", "11:45"), ("13:00", "23:45")], ids=["early", "late"]
)
async def test_today_at_quarter_to_12_is_the_next_of_its_two_times_today(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    now: str,
    clock: str,
) -> None:
    """The 12 of "today at quarter to 12" is noon or midnight, and the midnight that
    ends today is today's: said at 13:00 the time is that night's 23:45, as "quarter to
    12" with no day word is, and not 11:45, which has passed."""
    await advance_to(hass, freezer, local(SUNDAY, now))

    await say_slots(hass, {"clock_hour": 12, "clock_before": 15, "clock_day": 0})

    assert state_of(hass, NEXT) == at(SUNDAY, clock)


async def test_a_tonight_that_has_passed_is_refused_and_not_moved_to_tomorrow(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
) -> None:
    """ "Tonight" names today, as "today" does: at eight in the evening 7 in the evening
    has passed, and nothing is kept for tomorrow's."""
    await advance_to(hass, freezer, local(SUNDAY, "20:00"))

    response = await say_slots(hass, {"clock_part": "tonight", "clock_hour": 7})

    assert refusal_of(response) == translated(
        "en", "exceptions", "command_in_past", "message"
    ).format(at="19:00")
    assert pending(hass) == []
    assert state_of(hass, NEXT) == "unknown"
    assert fake_target.calls == []


@pytest.mark.parametrize(
    ("slots", "days", "clock"),
    [
        ({"clock_part": "tonight", "clock_hour": 7}, 0, "19:00"),
        ({"clock_part": "tonight", "clock_hour": 2}, 1, "02:00"),
    ],
    ids=["tonight at 7", "tonight at 2"],
)
async def test_tonight_is_the_night_of_today(
    hass: HomeAssistant,
    clock_boiler: MockConfigEntry,
    slots: dict[str, object],
    days: int,
    clock: str,
) -> None:
    """ "Tonight" is the night with today named: 7 is the evening of today, and 2 is the
    small hours of the night after today, by the rule of the night."""
    await say_slots(hass, slots)

    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=days), clock)


@pytest.mark.parametrize(
    "slots",
    [
        {"clock_ordinal": 8, "clock_hour": 7},
        {"clock_ordinal": 8, "clock_before": 15},
        {"clock_hour": 8, "clock_before": 15, "clock_minute": 10},
        {"clock_hour": 8, "clock_before": 0},
        {"clock_hour": 8, "clock_before": 60},
        {"clock_ordinal": 0, "clock_minute": 30},
        {"clock_ordinal": 13, "clock_minute": 30},
    ],
    ids=[
        "an ordinal and an hour",
        "an ordinal and minutes before",
        "minutes before and minutes after",
        "no minutes before",
        "an hour of minutes before",
        "the zeroth hour",
        "the thirteenth hour",
    ],
)
async def test_an_ordinal_or_minutes_before_with_another_hour_are_not_understood(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    clock_boiler: MockConfigEntry,
    slots: dict[str, object],
) -> None:
    """No sentence names two hours, or minutes both before and after one, or minutes
    outside 1 to 59 or an hour outside 1 to 12 in the ordinal. Slots that say it, from a
    caller that is not a sentence, are refused as invalid, and nothing is kept or
    switched."""
    with pytest.raises(intent.InvalidSlotInfo):
        await say_slots(hass, slots)

    assert pending(hass) == []
    assert fake_target.calls == []


@pytest.mark.parametrize(
    ("hour", "text", "now", "days", "clock"),
    [
        (7, "07", "08:00", 1, "07:00"),
        (7, "007", "08:00", 1, "07:00"),
        (7, " 07", "08:00", 1, "07:00"),
        (7, "7", "08:00", 0, "19:00"),
        (7, "seven", "08:00", 0, "19:00"),
        (7, None, "08:00", 0, "19:00"),
        (12, "012", "20:00", 1, "12:00"),
        (12, "12", "20:00", 1, "00:00"),
        (0, "0", "08:00", 1, "00:00"),
        (0, "00", "08:00", 1, "00:00"),
    ],
    ids=[
        "07",
        "007",
        "07 after a space",
        "7",
        "a word",
        "no text",
        "012",
        "12",
        "0",
        "00",
    ],
)
async def test_the_text_of_the_hour_tells_whether_it_was_written_with_a_zero(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    hour: int,
    text: str | None,
    now: str,
    days: int,
    clock: str,
) -> None:
    """A zero is a text of more than one character that begins with one, apart from the
    space the agent may keep before a number; the value of the hour is the same with
    it or without. A caller that gives no text, as an LLM agent would, says no zero."""
    await advance_to(hass, freezer, local(SUNDAY, now))
    slot = {"value": hour} if text is None else {"value": hour, "text": text}

    await intent.async_handle(
        hass,
        "test",
        CLOCK,
        {
            "name": {"value": "Boiler"},
            "action": {"value": "on"},
            "clock_hour": slot,
            "clock_minute": {"value": 0},
        },
    )

    assert state_of(hass, NEXT) == at(SUNDAY + timedelta(days=days), clock)


# --- The rules the handler reads ---------------------------------------------------


@pytest.mark.parametrize(
    ("part", "table"),
    [
        ("am", {12: 0, 1: 1, 7: 7, 11: 11}),
        ("pm", {12: 12, 1: 13, 7: 19, 11: 23}),
        ("night", {12: 0, 1: 1, 5: 5, 6: 18, 7: 19, 11: 23}),
        ("tonight", {12: 0, 1: 1, 5: 5, 6: 18, 7: 19, 11: 23}),
        (None, {0: 0, 7: 7, 13: 13, 23: 23}),
    ],
)
def test_the_hour_of_the_day_follows_the_part_it_is_said_with(
    part: DayPart | None, table: dict[int, int]
) -> None:
    """The morning is the hour as it is but for 12, which is 0; the afternoon and the
    evening add 12 but to 12, which stays; the night is the small hours for 1 to 5 and
    the evening for 6 to 11, and so is "tonight"."""
    assert {hour: hour_of_day(hour, part) for hour in table} == table


@pytest.mark.parametrize(
    ("now", "hour", "part", "zero", "days", "clock"),
    [
        ("08:00", 7, None, True, 1, "07:30"),
        ("20:00", 7, None, True, 1, "07:30"),
        ("08:00", 7, None, False, 0, "19:30"),
        ("20:00", 7, None, False, 1, "07:30"),
        ("08:00", 1, None, True, 1, "01:30"),
        ("20:00", 1, None, True, 1, "01:30"),
        ("08:00", 1, None, False, 0, "13:30"),
        ("08:00", 12, None, True, 0, "12:30"),
        ("20:00", 12, None, True, 1, "12:30"),
        ("08:00", 12, None, False, 0, "12:30"),
        ("20:00", 12, None, False, 1, "00:30"),
        ("08:00", 7, "pm", True, 0, "19:30"),
        ("08:00", 7, "am", True, 1, "07:30"),
        ("08:00", 7, "night", True, 0, "19:30"),
    ],
)
def test_an_hour_written_with_a_zero_is_one_time_of_the_24_hour_clock(
    now: str, hour: int, part: DayPart | None, zero: bool, days: int, clock: str
) -> None:
    """The nearer of two times is for an hour from 1 to 12 with no part and no zero. A
    zero fixes the hour as it is, so 12 is noon and not the nearer of noon and midnight,
    and a part of the day still chooses the half."""
    moment = clock_moment(
        local(SUNDAY, now),
        ZoneInfo(JERUSALEM),
        hour,
        30,
        part,
        None,
        zero=zero,
    )

    assert moment == local(SUNDAY + timedelta(days=days), clock)


@pytest.mark.parametrize(
    ("now", "hour", "part", "day", "before", "days", "clock"),
    [
        ("06:00", 8, None, None, 15, 0, "07:45"),
        ("19:50", 8, None, None, 15, 1, "07:45"),
        ("06:00", 12, None, None, 15, 0, "11:45"),
        ("12:00", 12, None, None, 15, 0, "23:45"),
        ("23:50", 12, "am", None, 15, 1, "23:45"),
        ("08:00", 8, "pm", None, 15, 0, "19:45"),
        ("06:00", 1, "night", None, 10, 1, "00:50"),
        ("06:00", 8, None, 1, 15, 1, "07:45"),
    ],
    ids=[
        "the morning one",
        "the evening one has passed",
        "to 12 is the nearer of 11:45 and 23:45",
        "to 12 at noon is tonight's",
        "to midnight after 23:45 needs the third day",
        "pm names the hour",
        "ten to one at night is in the small hours",
        "a day word",
    ],
)
def test_minutes_before_an_hour_are_taken_off_on_the_wall_clock(
    now: str,
    hour: int,
    part: DayPart | None,
    day: int | None,
    before: int,
    days: int,
    clock: str,
) -> None:
    """The hour is read first, with its part and its day, and the minutes come off it on
    the wall clock, so "quarter to 8" is 07:45 or 19:45, whichever is ahead, "quarter to
    midnight" is 23:45 and "ten to 1 at night" is 00:50."""
    moment = clock_moment(
        local(SUNDAY, now), ZoneInfo(JERUSALEM), hour, 0, part, day, before=before
    )

    assert moment == local(SUNDAY + timedelta(days=days), clock)


@pytest.mark.parametrize("hour", [3, 4])
def test_minutes_before_an_hour_the_clock_skips_happen_later_by_the_gap(
    hour: int,
) -> None:
    """The clock goes from 02:00 to 03:00 in Jerusalem on 2026-03-27. Quarter to 3 is
    02:45, which the clock skips, so it happens later by the gap, at 03:45, as quarter
    to 4 does."""
    moment = clock_moment(
        local(date(2026, 3, 26), "23:00"),
        ZoneInfo(JERUSALEM),
        hour,
        0,
        "am",
        None,
        before=15,
    )

    assert moment == datetime(2026, 3, 27, 0, 45, tzinfo=UTC)


@pytest.mark.parametrize(
    ("now", "hour", "part", "day", "night_after", "before", "days", "clock"),
    [
        ("06:00", 12, None, 1, False, 15, 1, "11:45"),
        ("06:00", 12, None, 0, False, 15, 0, "11:45"),
        ("06:00", 1, None, 1, False, 15, 1, "00:45"),
        ("06:00", 12, "am", 1, True, 15, 1, "23:45"),
        ("06:00", 12, "am", 0, True, 15, 0, "23:45"),
        ("06:00", 12, "night", 1, True, 15, 1, "23:45"),
        ("06:00", 1, "night", 1, True, 10, 2, "00:50"),
        ("00:20", 1, "night", 0, True, 10, 0, "00:50"),
        ("01:00", 1, "night", 0, True, 10, 1, "00:50"),
        ("13:00", 12, None, 0, False, 15, 0, "23:45"),
        ("06:00", 12, "am", 1, False, 15, 1, "23:45"),
        ("06:00", 12, "am", 0, False, 15, 0, "23:45"),
        ("06:00", 0, None, 1, False, 15, 1, "23:45"),
    ],
    ids=[
        "tomorrow at quarter to 12",
        "today at quarter to 12",
        "tomorrow at quarter to 1",
        "tomorrow at quarter to midnight",
        "today at quarter to midnight",
        "tomorrow at quarter to 12 at night",
        "tomorrow at ten to 1 at night",
        "today at ten to 1 at night, said before it",
        "today at ten to 1 at night, said after it",
        "today at quarter to 12, said after 11:45",
        "tomorrow at quarter to 12 am",
        "today at quarter to 12 am",
        "tomorrow at quarter to the hour 0",
    ],
)
def test_minutes_before_an_hour_stay_on_the_day_said(
    now: str,
    hour: int,
    part: DayPart | None,
    day: int,
    night_after: bool,
    before: int,
    days: int,
    clock: str,
) -> None:
    """A day word names the day of the time said, so the minutes before an hour do not
    take it to the day before: "tomorrow at quarter to 12" is 11:45 tomorrow and not the
    23:45 before tomorrow's start. The midnight that ends the day is on the day it
    ends, so the same words are 23:45 tomorrow once 11:45 has passed or with "am", as
    "tomorrow at quarter to midnight" is, and the night after the day is read as it is
    without the minutes."""
    moment = clock_moment(
        local(SUNDAY, now),
        ZoneInfo(JERUSALEM),
        hour,
        0,
        part,
        day,
        before=before,
        night_after=night_after,
    )

    assert moment == local(SUNDAY + timedelta(days=days), clock)


@pytest.mark.parametrize(
    ("hour", "part", "zero", "night_after"),
    [(hour, None, True, False) for hour in range(24)]
    + [(hour, None, False, False) for hour in range(1, 13)]
    + [(12, "am", False, True)]
    + [(hour, "night", False, True) for hour in (12, 1, 2, 3, 4, 5)],
)
def test_a_time_with_a_day_word_and_minutes_before_is_always_on_the_day_named(
    hour: int, part: DayPart | None, zero: bool, night_after: bool
) -> None:
    """Of the dates an hour is read on, the minutes before put one on the named day (the
    night after it may also end on the day after), so a day word never leaves a time
    without a moment: "tomorrow at quarter to 12 am" is not a case that is refused."""
    zone = ZoneInfo(JERUSALEM)
    for day in (0, 1, 2):
        for before in (0, 1, 15, 30, 59):
            moment = clock_moment(
                local(SUNDAY, "06:00"),
                zone,
                hour,
                0,
                part,
                day,
                zero=zero,
                before=before,
                night_after=night_after,
            )

            named = SUNDAY + timedelta(days=day)
            assert moment.astimezone(zone).date() in (
                named,
                named + timedelta(days=int(night_after)),
            ), (day, before)


def spoken(language: str, rule: str, texts: dict[str, str] | None = None) -> set[str]:
    """Every way the shipped rule is said, with the numbers of `NUMBERS`, the minutes
    of `MINUTES` and the words of the lists `texts` names (the first value of the
    others)."""
    return set(spoken_rule(language, rule, NUMBERS, {**MINUTES, **(texts or {})}))


def time_of(form: str) -> str:
    """The time a form of the English clock says, without its day word or its "at"."""
    days = r"\b(today|tomorrow|the day after tomorrow)\b"
    return re.sub(days, "", form).replace("at ", "", 1).strip()


def says_a_part_of_the_day(form: str) -> bool:
    """Whether a form of the English clock says the part of the day as a word before the
    hour or after it: "tomorrow morning at 7", "at 7 in the evening", "tonight at 7"."""
    return re.search(r"\b(morning|afternoon|evening|night|tonight)\b", form) is not None


def is_dotted(time: str) -> bool:
    """Whether a time is said with a dot between its hours and minutes."""
    return re.search(r"\d\.\d", time) is not None


def test_an_exact_clock_is_every_english_form_but_a_bare_hour_and_a_dotted_time() -> (
    None
):
    """After the settings of a thermostat a time must not be said as a temperature is
    ("at 21", "at 7.30"). Every other form is allowed there, and none is added. A part
    of the day as a word before the hour is no temperature, so "tomorrow morning at 7"
    and "in the evening at 7.30" are allowed there."""
    words = {"timerify_day_parts": "pm", "timerify_clock_days": "tomorrow"}
    clock = spoken("en", "timerify_clock", words)
    exact = spoken("en", "timerify_exact_clock", words)

    left_out = clock - exact

    assert exact < clock
    assert left_out == {
        form
        for form in clock
        if not says_a_part_of_the_day(form)
        and (time_of(form) == "7" or is_dotted(time_of(form)))
    }
    assert {
        "at 7:30",
        "at 7 pm",
        "at noon",
        "at 7 o'clock",
        "tomorrow at 7:30",
        "tomorrow morning at 7",
        "in the morning at 7",
        "at 7.30 tomorrow morning",
        "at half past 7",
        "at 20 to 7",
        "at 7:30am",
        "tonight at 7",
        "at 7 tonight",
        "tonight at 7 pm",
        "at 7 pm tonight",
        "this evening at 7:30pm",
    } <= exact
    assert not {"at 7", "at 7.30", "tomorrow at 7"} & exact


def test_russian_needs_no_narrower_clock_after_the_settings() -> None:
    """A Russian time is never a bare number, since it has "v" or "bez" or the ordinal
    of the hour that minutes are counted to, and a temperature is a number with "na":
    the time that follows the settings is the same as the one that follows the command
    (`RULINGS.md`)."""
    sources = spoken("ru", "timerify_clock_after_extras")

    assert sources == spoken("ru", "timerify_clock_after_command")
    assert sources == spoken("ru", "timerify_clock_before_command")
    assert any(is_dotted(form) for form in sources)
