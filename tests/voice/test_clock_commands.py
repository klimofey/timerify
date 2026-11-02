"""Turning a device on or off at a clock time by voice, in English and Russian.

"Turn on the boiler at 7:30", "tomorrow at 7", "at 7 pm": the built-in agent keeps a
command for that time or sets the countdown to end then. Every scenario talks to the
real built-in agent, in Jerusalem, from Sunday at six in the morning unless it moves the
clock. What is said in Russian is read from the shipped sentences, so that no test needs
a Russian letter.

An hour from 1 to 12 said with no "am", "pm" or Russian word for the time of day is the
nearer of its morning and evening times that is still ahead (the owner's decision of
2026-11-02); the hour of 0 or from 13 to 23 is that of the 24-hour clock.
"""

import re
from datetime import date, timedelta
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.voice.commands import DayPart, hour_of_day

from ..conftest import FakeTarget, SetupTarget
from ..helpers import (
    AC_NEXT,
    NEXT,
    NUMBER,
    SENSOR,
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
    SETTING_LISTS,
    converse,
    copy_sentences,
    reached,
    refusal_of,
    samples,
    speech,
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
}
"""The numbers with which a clock time is said: 7:30, or 7 with a part of the day."""


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


def turn_on_at(language: str, clock: str) -> str:
    """The sentence of the shipped files that turns the Boiler on, with `clock` as the
    time it says: the first sentence with a command before the time, taken from the
    samples of the language."""
    forms = spoken_rule(language, "timerify_clock", NUMBERS)
    for sample in samples(
        language,
        CLOCK,
        takeover=True,
        numbers=NUMBERS,
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
        for form in spoken_rule("ru", "timerify_clock", numbers or NUMBERS, texts)
        if re.fullmatch(pattern, form)
    ]
    assert len(forms) == 1, (pattern, forms)
    return forms[0]


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
        absent=SETTING_LISTS,
        admitting="switch",
    )
    sentences += [
        turn_on_at("ru", form) for form in spoken_rule("ru", "timerify_clock", NUMBERS)
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
        absent=SETTING_LISTS,
        admitting="switch",
    )
    sentences += [
        turn_on_at("en", form) for form in spoken_rule("en", "timerify_clock", NUMBERS)
    ]
    assert len(sentences) > 40

    for text in sentences:
        response = await converse(hass, text, "en")

        assert reached(response) == CLOCK, text
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


@pytest.mark.parametrize(("part", "clock"), [("pm", "12:00"), ("am", "00:00")])
async def test_the_russian_words_for_noon_and_midnight_name_their_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    clock_boiler: MockConfigEntry,
    part: str,
    clock: str,
) -> None:
    """The word for noon is 12:00 and the word for midnight 00:00, said in the afternoon
    too, where a bare 12 would be the midnight that is nearer."""
    word = spoken_values("ru", "timerify_clock_words")[part][0]
    form = russian_form(rf"\S+ {re.escape(word)}", texts={"timerify_clock_words": word})

    response = await say_at(
        hass, freezer, SUNDAY, "13:00", turn_on_at("ru", form), "ru"
    )

    assert reached(response) == CLOCK, speech(response)
    assert state_of(hass, NEXT) == at(MONDAY, clock)


# --- What the sentences do not say, and what core's gazetteer took -----------------


@pytest.mark.parametrize(
    "said",
    [
        "turn on the boiler at 7",
        "turn on the boiler tomorrow at 7",
        "turn on the boiler at noon",
        "turn off the boiler at 7",
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


# --- The rules the handler reads ---------------------------------------------------


@pytest.mark.parametrize(
    ("part", "table"),
    [
        ("am", {12: 0, 1: 1, 7: 7, 11: 11}),
        ("pm", {12: 12, 1: 13, 7: 19, 11: 23}),
        ("night", {12: 0, 1: 1, 5: 5, 6: 18, 7: 19, 11: 23}),
        (None, {0: 0, 7: 7, 13: 13, 23: 23}),
    ],
)
def test_the_hour_of_the_day_follows_the_part_it_is_said_with(
    part: DayPart | None, table: dict[int, int]
) -> None:
    """The morning is the hour as it is but for 12, which is 0; the afternoon and the
    evening add 12 but to 12, which stays; the night is the small hours for 1 to 5 and
    the evening for 6 to 11."""
    assert {hour: hour_of_day(hour, part) for hour in table} == table


def spoken(language: str, rule: str, texts: dict[str, str] | None = None) -> set[str]:
    """Every way the shipped rule is said, with the numbers of `NUMBERS` and the words
    of the lists `texts` names (the first value of the others)."""
    return set(spoken_rule(language, rule, NUMBERS, texts))


def time_of(form: str) -> str:
    """The time a form of the English clock says, without its day word or its "at"."""
    days = r"\b(today|tomorrow|the day after tomorrow)\b"
    return re.sub(days, "", form).replace("at ", "", 1).strip()


def is_dotted(time: str) -> bool:
    """Whether a time is said with a dot between its hours and minutes."""
    return re.search(r"\d\.\d", time) is not None


def test_an_exact_clock_is_every_english_form_but_a_bare_hour_and_a_dotted_time() -> (
    None
):
    """After the settings of a thermostat a time must not be said as a temperature is
    ("at 21", "at 7.30"). Every other form is allowed there, and none is added."""
    words = {"timerify_day_parts": "pm", "timerify_clock_days": "tomorrow"}
    clock = spoken("en", "timerify_clock", words)
    exact = spoken("en", "timerify_exact_clock", words)

    left_out = clock - exact

    assert exact < clock
    assert left_out == {
        form for form in clock if time_of(form) == "7" or is_dotted(time_of(form))
    }
    assert {
        "at 7:30",
        "at 7 pm",
        "at noon",
        "at 7 o'clock",
        "tomorrow at 7:30",
    } <= exact
    assert not {"at 7", "at 7.30", "tomorrow at 7"} & exact


def test_russian_needs_no_narrower_clock_after_the_settings() -> None:
    """A time is said with "v" and a temperature with "na", so the time that follows the
    settings is the same as the one that follows the command (`RULINGS.md`)."""
    sources = spoken("ru", "timerify_clock_after_extras")

    assert sources == spoken("ru", "timerify_clock_after_command")
    assert sources == spoken("ru", "timerify_clock_before_command")
