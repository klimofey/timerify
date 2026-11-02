"""Naming a schedule interval by its start time, by voice and through an LLM's tool.

An interval that still has the title Timerify gave it (a mouthful, such as
`06:30–07:15, Mon–Sun`) can be named by the time it starts at: "turn off the 6:30
schedule of the boiler". The file the Voice settings entry writes lists the time as it
is said, the timer works out which of its intervals it names, and every interval of the
timer that starts then is switched. An interval its owner titled has no start time to
say. Every scenario talks to the real built-in agent, or calls the tool of the real
Assist API.
"""

import copy
from types import MappingProxyType
from typing import Any

import pytest
import yaml
from freezegun.api import FrozenDateTimeFactory
from hassil.intents import Intents, TextSlotList
from hassil.recognize import recognize_all
from hassil.util import merge_dict
from home_assistant_intents import get_intents
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import WEEKDAYS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.const import (
    CONF_GENERATED_TITLE,
    LIST_INTERVAL,
    SUBENTRY_INTERVAL,
    VOICE_SYNC_COOLDOWN,
)
from custom_components.timerify.schedule import (
    has_generated_title,
    spoken_aliases,
    start_aliases,
)
from custom_components.timerify.voice.sentences import (
    VoiceName,
    VoiceTitle,
    build,
    load_sources,
    render,
    validate,
)

from ..conftest import FakeTarget, SetupTarget
from ..helpers import (
    NEXT,
    NUMBER,
    SUNDAY,
    TARGET_ID,
    TURN_ON,
    add_interval,
    advance,
    edit_interval,
    iso,
    open_sunday,
    retitle_interval,
    set_number,
    state_of,
)
from .helpers import (
    BOILER_INTERVALS,
    EVENING,
    EVENING_TITLE,
    MORNING,
    MORNING_TITLE,
    SET_SCHEDULE,
    add_voice_entry,
    assist_api,
    call_tool,
    converse,
    every_text,
    listed,
    pending,
    reached,
    refusal_of,
    russian_schedule_answers,
    speech,
    switches,
    translated,
)

CLOCK_COMMAND = "TimerifyCommandAt"


def test_start_aliases_are_the_ways_a_recogniser_writes_the_time() -> None:
    assert start_aliases("06:30") == ("6:30", "06:30", "6.30", "06.30")
    assert start_aliases("18:00") == ("18:00", "18.00")
    assert start_aliases("00:05") == ("0:05", "00:05", "0.05", "00.05")


LABELS = {
    **{day: day.capitalize() for day in WEEKDAYS},
    "workdays": "Working days",
    "non_workdays": "Days off",
}
"""The words of a title in English: the weekdays and the kinds of days."""


def interval_subentry(title: str, mark: str | None = None) -> ConfigSubentry:
    """The interval from 06:30 to 07:15 on every day, titled `title`, with the mark that
    Timerify gave its title when `mark` is one."""
    data: dict[str, Any] = {
        "days": "weekdays",
        "weekdays": list(WEEKDAYS),
        "start": "06:30",
        "end": "07:15",
        "settings": {},
    }
    if mark is not None:
        data[CONF_GENERATED_TITLE] = mark
    return ConfigSubentry(
        data=MappingProxyType(data),
        subentry_type=SUBENTRY_INTERVAL,
        title=title,
        unique_id=None,
    )


@pytest.mark.parametrize(
    ("title", "mark", "generated"),
    [
        (MORNING_TITLE, MORNING_TITLE, True),
        ("Morning", MORNING_TITLE, False),
        (MORNING_TITLE, None, True),
        ("Morning", None, False),
        ("Morning", "Morning", True),
    ],
    ids=[
        "marked and untouched",
        "marked and renamed",
        "unmarked and titled as its data makes it",
        "unmarked and titled by its owner",
        "the mark is the title it has",
    ],
)
def test_one_rule_tells_a_title_timerify_gave_from_the_owners(
    title: str, mark: str | None, generated: bool
) -> None:
    """The mark decides while the interval has one; an interval with none, which release
    1.0.0 leaves, is Timerify's while its title is the one its data makes. The interval
    form and the times an interval is said by both ask this."""
    subentry = interval_subentry(title, mark)

    assert has_generated_title(subentry, LABELS) is generated
    assert bool(spoken_aliases(subentry, LABELS)) is generated


async def test_a_generated_title_is_said_by_its_start_time(
    hass: HomeAssistant, fake_target: FakeTarget, generated: MockConfigEntry
) -> None:
    """The title Timerify gave the morning interval is a mouthful, so its start time
    names it: only the morning goes off, and the answer gives the title as the interval
    has it. The boiler itself is not touched."""
    response = await converse(hass, "turn off the 6:30 schedule of the boiler")

    assert reached(response) == SET_SCHEDULE
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert speech(response) == f"The {MORNING_TITLE} schedule of Boiler is off."
    assert switches(hass) == ("off", "on")
    assert fake_target.calls == []


@pytest.mark.parametrize(
    ("said", "title", "interval"),
    [
        ("6:30", MORNING_TITLE, MORNING),
        ("06:30", MORNING_TITLE, MORNING),
        ("6.30", MORNING_TITLE, MORNING),
        ("06.30", MORNING_TITLE, MORNING),
        ("18:00", EVENING_TITLE, EVENING),
        ("18.00", EVENING_TITLE, EVENING),
    ],
)
async def test_every_way_a_recogniser_writes_the_start_time_names_the_interval(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    generated: MockConfigEntry,
    said: str,
    title: str,
    interval: str,
) -> None:
    """A speech recogniser writes half past six with or without the zero, after a colon
    or a dot; any of them reaches the interval, off and on again."""
    off = await converse(hass, f"turn off the {said} schedule of the boiler")
    assert reached(off) == SET_SCHEDULE, said
    assert speech(off) == f"The {title} schedule of Boiler is off."
    assert state_of(hass, interval) == "off"

    on = await converse(hass, f"resume the {said} schedule of the boiler")
    assert reached(on) == SET_SCHEDULE, said
    assert speech(on) == f"The {title} schedule of Boiler is on."
    assert switches(hass) == ("on", "on")
    assert fake_target.calls == []


async def test_the_file_lists_each_start_time_with_itself_as_the_value(
    hass: HomeAssistant, generated: MockConfigEntry
) -> None:
    """The title keeps meaning itself, and each start time follows the title it belongs
    to, meaning the text that was said: the controller, not the file, tells which
    intervals that is. A value that reads as a number in YAML is quoted by the writer,
    so that Home Assistant reads it back as the text it is."""
    assert listed(hass, "en", LIST_INTERVAL) == [
        {"in": "06:30–07:15 Mon–Sun", "out": MORNING_TITLE},
        *({"in": said, "out": said} for said in ("6:30", "06:30", "6.30", "06.30")),
        {"in": "18:00–19:00 Mon–Sun", "out": EVENING_TITLE},
        *({"in": said, "out": said} for said in ("18:00", "18.00")),
    ]


def test_the_start_times_are_listed_as_the_built_in_agent_reads_them() -> None:
    """The proof that gates every write holds the start times to what is said: a colon
    or a dot between digits is not punctuation to the agent, so "6:30" and "6.30" are
    read back as they were written, and the file reads back as text, not as the number
    that YAML makes of `6:30` or `6.30` unquoted."""
    aliases = (*start_aliases("06:30"), *start_aliases("18:00"))
    built = build(
        load_sources("en"),
        [VoiceName("Boiler", "switch")],
        intervals=[VoiceTitle(alias) for alias in aliases],
    )

    validate("en", built.data, built.said)

    assert built.said[LIST_INTERVAL] == aliases
    values = yaml.safe_load(render(built.data))["lists"][LIST_INTERVAL]["values"]
    assert values == [{"in": alias, "out": alias} for alias in aliases]


async def test_the_start_time_switches_every_interval_that_starts_then(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """The weekday and the weekend morning both start at half past six, with titles
    that differ in their end and days: the 6:30 schedule is both, as two intervals with
    one title are switched together, and the evening is not touched. The answer names
    both, since it must not say that one went off when two did."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(
        hass, entry, start="06:30", end="07:15", weekdays=["mon", "tue", "wed"]
    )
    await add_interval(hass, entry, start="06:30", end="08:00", weekdays=["sat", "sun"])
    await add_interval(hass, entry, start="18:00", end="19:00")
    await add_voice_entry(hass, languages=("en",))
    both = (
        "switch.boiler_schedule_06_30_07_15_mon_wed",
        "switch.boiler_schedule_06_30_08_00_sat_sun",
    )

    response = await converse(hass, "turn off the 06:30 schedule of the boiler")

    assert reached(response) == SET_SCHEDULE
    assert speech(response) == (
        "The 06:30\u201307:15, Mon\u2013Wed and 06:30\u201308:00, Sat, Sun"
        " schedules of Boiler are off."
    )
    assert [state_of(hass, entity_id) for entity_id in (*both, EVENING)] == [
        "off",
        "off",
        "on",
    ]
    assert fake_target.calls == []


async def test_the_answer_names_each_title_apart_by_semicolons_and_the_last_after_and(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """Three intervals start at half past six. A title has a comma, so the titles are
    set apart by semicolons, the last after "and"; asked on again, the answer is the
    same list of schedules, and a plural verb."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    for end, days in (
        ("07:00", ["mon", "tue"]),
        ("07:15", ["wed", "thu", "fri"]),
        ("08:00", ["sat", "sun"]),
    ):
        await add_interval(hass, entry, start="06:30", end=end, weekdays=days)
    await add_voice_entry(hass, languages=("en",))
    titles = (
        "06:30\u201307:00, Mon, Tue; 06:30\u201307:15, Wed\u2013Fri"
        " and 06:30\u201308:00, Sat, Sun"
    )

    off = await converse(hass, "turn off the 6:30 schedule of the boiler")
    on = await converse(hass, "turn on the 6:30 schedule of the boiler")

    assert speech(off) == f"The {titles} schedules of Boiler are off."
    assert speech(on) == f"The {titles} schedules of Boiler are on."
    assert fake_target.calls == []


async def test_a_start_time_is_listed_once_and_each_timer_switches_its_own(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    generated: MockConfigEntry,
    setup_target: SetupTarget,
) -> None:
    """The fan has an interval from half past six too. The file has "6:30" once for
    the house, and the timer in the words is the one whose interval is switched."""
    fan = await setup_target(target=fake_fan.entity_id)
    await add_interval(hass, fan, start="06:30", end="07:00")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    said = [value["out"] for value in listed(hass, "en", LIST_INTERVAL)]
    assert said.count("6:30") == 1
    response = await converse(hass, "turn off the 6:30 schedule of the fan")

    assert reached(response) == SET_SCHEDULE
    assert state_of(hass, "switch.fan_schedule_06_30_07_00_mon_sun") == "off"
    assert switches(hass) == ("on", "on")
    response = await converse(hass, "turn off the 6:30 schedule of the boiler")

    assert reached(response) == SET_SCHEDULE
    assert switches(hass) == ("off", "on")
    assert fake_target.calls == []
    assert fake_fan.calls == []


async def test_a_start_time_only_another_timer_has_is_refused(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    generated_schedule: MockConfigEntry,
    setup_target: SetupTarget,
) -> None:
    """The start times are the house's, as the titles are: the fan has an interval from
    ten at night and the boiler has none, so the words are understood, the boiler says
    which intervals it has, and nothing is switched or turned off."""
    fan = await setup_target(target=fake_fan.entity_id)
    await add_interval(hass, fan, start="22:00", end="23:00")
    await add_voice_entry(hass, languages=("en",))
    await set_number(hass, NUMBER, 60)

    response = await converse(hass, "turn off the 22:00 schedule of the boiler")

    assert reached(response) == SET_SCHEDULE
    assert refusal_of(response) == translated(
        "en", "exceptions", "unknown_interval", "message"
    ).format(
        target="Boiler",
        interval="22:00",
        intervals=f"{MORNING_TITLE}; {EVENING_TITLE}",
    )
    assert switches(hass) == ("on", "on")
    assert state_of(hass, "switch.fan_schedule_22_00_23_00_mon_sun") == "on"
    assert fake_target.calls == [TURN_ON]
    assert fake_fan.calls == []


@pytest.mark.parametrize(
    "text",
    [
        "turn off the 6:30 schedule of the boiler",
        "turn on the 6:30 schedule of the boiler",
        "turn the 6:30 schedule of the boiler off",
        "turn off the 6:30 schedule for the boiler",
        "disable the 6:30 schedule for the boiler",
        "pause the 6:30 schedule of the boiler",
        "switch off the 6.30 schedule of the boiler",
        "turn off 6:30 schedule for the boiler",
        "turn off the boiler 6:30 schedule",
    ],
)
async def test_a_title_the_user_gave_is_not_said_by_its_start_time(
    hass: HomeAssistant, fake_target: FakeTarget, scheduled: MockConfigEntry, text: str
) -> None:
    """The owner called the morning interval Morning, so half past six is not its name:
    no title in the house is generated for that time and the words are not Timerify's.
    The boiler is running, and neither it nor the schedule is touched by words that
    the built-in agent falls back on its names for."""
    await set_number(hass, NUMBER, 60)
    assert fake_target.calls == [TURN_ON]

    response = await converse(hass, text)

    assert reached(response) != SET_SCHEDULE
    assert response.response_type is intent.IntentResponseType.ERROR
    assert switches(hass) == ("on", "on")
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"


async def test_a_renamed_interval_is_refused_when_its_start_time_is_another_timer_s(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    scheduled: MockConfigEntry,
    setup_target: SetupTarget,
) -> None:
    """The fan has an interval that starts at half past six, still titled by Timerify,
    so the house can say 6:30. The boiler's interval at that time was renamed, so it is
    not the one meant: the boiler says which titles it has, and nothing is switched."""
    fan = await setup_target(target=fake_fan.entity_id)
    await add_interval(hass, fan, start="06:30", end="07:00")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    response = await converse(hass, "turn off the 6:30 schedule of the boiler")

    assert reached(response) == SET_SCHEDULE
    assert refusal_of(response) == translated(
        "en", "exceptions", "unknown_interval", "message"
    ).format(target="Boiler", interval="6:30", intervals=BOILER_INTERVALS)
    assert switches(hass) == ("on", "on")
    assert state_of(hass, "switch.fan_schedule_06_30_07_00_mon_sun") == "on"
    assert fake_target.calls == []
    assert fake_fan.calls == []


async def test_an_interval_edited_to_start_later_is_said_by_the_new_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    generated: MockConfigEntry,
) -> None:
    """Moving the morning interval to seven makes Timerify title it again, since the
    title is still its own, and the half past six goes with the old time: it is not
    understood any more, and the new time is."""
    (morning,) = (
        subentry_id
        for subentry_id, subentry in generated.subentries.items()
        if subentry.title == MORNING_TITLE
    )

    await edit_interval(hass, generated, morning, start="07:00", end="07:45")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    said = [value["out"] for value in listed(hass, "en", LIST_INTERVAL)]
    assert "6:30" not in said
    assert {"7:00", "07:00", "7.00", "07.00"} <= set(said)
    old = await converse(hass, "turn off the 6:30 schedule of the boiler")
    assert reached(old) != SET_SCHEDULE
    assert switches(hass) == ("on", "on")
    new = await converse(hass, "turn off the 7:00 schedule of the boiler")
    assert reached(new) == SET_SCHEDULE
    assert speech(new) == "The 07:00–07:45, Mon–Sun schedule of Boiler is off."
    assert fake_target.calls == []


async def test_renaming_a_generated_interval_takes_its_start_times_out_of_the_file(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    generated: MockConfigEntry,
) -> None:
    """The file was written with the times of the morning interval; its owner then calls
    it Morning. The title is theirs from then on, so the times leave the file, 6:30 is
    not understood any more, and the new title is."""
    (morning,) = (
        subentry_id
        for subentry_id, subentry in generated.subentries.items()
        if subentry.title == MORNING_TITLE
    )
    said = [value["out"] for value in listed(hass, "en", LIST_INTERVAL)]
    assert {"6:30", "06:30", "6.30", "06.30"} <= set(said)

    await retitle_interval(hass, generated, morning, "Morning")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert [value["out"] for value in listed(hass, "en", LIST_INTERVAL)] == [
        "Morning",
        EVENING_TITLE,
        "18:00",
        "18.00",
    ]
    for text in (
        "turn off the 6:30 schedule of the boiler",
        "turn off the 06.30 schedule of the boiler",
    ):
        response = await converse(hass, text)
        assert reached(response) != SET_SCHEDULE, text
        assert switches(hass) == ("on", "on")
    response = await converse(hass, "turn off the Morning schedule of the boiler")
    assert reached(response) == SET_SCHEDULE
    assert switches(hass) == ("off", "on")
    assert fake_target.calls == []


async def test_an_unmarked_interval_with_the_generated_title_is_said_by_its_start_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """Release 1.0.0 keeps no mark of a title Timerify gave: an interval edited there
    after a downgrade has none when the entry comes back. One definition decides, the
    interval form's: a title equal to the one the data makes is Timerify's, with the
    mark or without. So the unmarked morning is said by its start time, and the evening
    that its owner titled, marked or not, is not."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    morning = await add_interval(hass, entry, start="06:30", end="07:15")
    evening = await add_interval(hass, entry, start="18:00", end="19:00")
    await retitle_interval(hass, entry, evening, "Evening")
    for interval_id in (morning, evening):
        subentry = entry.subentries[interval_id]
        hass.config_entries.async_update_subentry(
            entry,
            subentry,
            data={k: v for k, v in subentry.data.items() if k != CONF_GENERATED_TITLE},
        )
    await hass.async_block_till_done()
    assert CONF_GENERATED_TITLE not in entry.subentries[morning].data
    await add_voice_entry(hass, languages=("en",))

    said = [value["out"] for value in listed(hass, "en", LIST_INTERVAL)]
    assert {"6:30", "06:30", "6.30", "06.30"} <= set(said)
    assert "18:00" not in said
    response = await converse(hass, "turn off the 6:30 schedule of the boiler")

    assert reached(response) == SET_SCHEDULE
    assert speech(response) == f"The {MORNING_TITLE} schedule of Boiler is off."
    assert switches(hass) == ("off", "on")
    assert fake_target.calls == []


async def test_a_title_that_reads_as_a_time_is_its_own_name_and_the_time_s_too(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    generated: MockConfigEntry,
) -> None:
    """The owner titles a weekday interval 6:30, which is also what the morning
    interval is said by. The text is listed once and means one thing: the 6:30
    schedule is both, as every interval that is called by a name is."""
    week = await add_interval(
        hass, generated, start="08:00", end="09:00", weekdays=["mon", "tue"]
    )
    await retitle_interval(hass, generated, week, "6:30")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    said = [value["out"] for value in listed(hass, "en", LIST_INTERVAL)]
    assert said.count("6:30") == 1
    response = await converse(hass, "turn off the 6:30 schedule of the boiler")

    assert reached(response) == SET_SCHEDULE
    assert speech(response) == (
        f"The {MORNING_TITLE} and 6:30 schedules of Boiler are off."
    )
    assert [
        state_of(hass, entity_id)
        for entity_id in (
            MORNING,
            "switch.boiler_schedule_08_00_09_00_mon_tue",
            EVENING,
        )
    ] == ["off", "off", "on"]


async def test_russian_start_time_switches_the_interval(
    hass: HomeAssistant, fake_target: FakeTarget, generated_schedule: MockConfigEntry
) -> None:
    """The start time is the same in every language: each way the shipped Russian
    sentences have to switch an interval, said with 6:30 in the place of its title,
    reaches the morning interval, off and on, and the answer names it by its title."""
    await add_voice_entry(hass, languages=("ru",))
    for enabled in (False, True):
        texts = [
            text
            for text, fixed in every_text("ru", SET_SCHEDULE, interval="6:30")
            if fixed["enabled"] is enabled and "6:30" in text
        ]
        assert texts

        for text in texts:
            response = await converse(hass, text, "ru")

            assert reached(response) == SET_SCHEDULE, text
            assert response.response_type is intent.IntentResponseType.ACTION_DONE
            assert response.intent is not None
            assert response.intent.slots["interval"]["value"] == "6:30", text
            assert MORNING_TITLE in speech(response), text

        assert switches(hass) == (("on" if enabled else "off"), "on")
    assert fake_target.calls == []


async def test_the_russian_answer_names_every_interval_a_start_time_switched(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """In a house set to Russian the intervals are titled in Russian, and a start time
    that two of them share switches both: the answer is the one the fixture says."""
    hass.config.language = "ru"
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(
        hass, entry, start="06:30", end="07:15", weekdays=["mon", "tue", "wed"]
    )
    await add_interval(hass, entry, start="06:30", end="08:00", weekdays=["sat", "sun"])
    await add_voice_entry(hass, languages=("ru",))
    expected = russian_schedule_answers()["two intervals with titles of their own, off"]
    text = next(
        text
        for text, fixed in every_text("ru", SET_SCHEDULE, interval="6:30")
        if fixed["enabled"] is False and "6:30" in text
    )

    response = await converse(hass, text, "ru")

    assert reached(response) == SET_SCHEDULE
    assert speech(response) == expected["answer"]
    assert fake_target.calls == []


def intent_types_reading(text: str) -> set[str]:
    """Every intent that Home Assistant's own sentences and Timerify's, built for the
    Boiler with an interval from 06:30, read `text` as: the whole of what the built-in
    agent chooses from. The lists it adds for the names of the house have the Boiler
    and no area or floor."""
    core = get_intents("en")
    assert core is not None
    merged = copy.deepcopy(core)
    built = build(
        load_sources("en"),
        [VoiceName("Boiler", "switch")],
        intervals=[VoiceTitle(alias) for alias in start_aliases("06:30")],
    )
    merge_dict(merged, built.data)
    house = {
        "name": TextSlotList.from_strings(["Boiler"], name="name"),
        "area": TextSlotList(name="area", values=[]),
        "floor": TextSlotList(name="floor", values=[]),
    }
    return {
        result.intent.name
        for result in recognize_all(
            text, Intents.from_dict(merged), slot_lists=house, language="en"
        )
    }


def test_the_time_in_each_phrase_is_read_by_one_intent_only() -> None:
    """The only intent that reads either phrase is the one it is meant for, so there is
    no tie between intents for the order of the sentences to settle."""
    assert intent_types_reading("turn off the 6:30 schedule of the boiler") == {
        SET_SCHEDULE
    }
    assert intent_types_reading("turn off the boiler at 6:30") == {CLOCK_COMMAND}


async def test_a_start_time_is_not_a_clock_time_and_the_other_way_round(
    hass: HomeAssistant, fake_target: FakeTarget, generated: MockConfigEntry
) -> None:
    """Half past six is the interval in one phrase and the time of day in another: the
    command at 6:30 keeps a command and switches no schedule, the schedule of 6:30
    switches the interval and keeps no command, and neither turns the boiler on or off
    now."""
    clock = await converse(hass, "turn on the boiler at 6:30")

    assert reached(clock) == CLOCK_COMMAND, speech(clock)
    assert state_of(hass, NEXT) == iso(SUNDAY, "06:30")
    assert switches(hass) == ("on", "on")

    schedule = await converse(hass, "turn off the 6:30 schedule of the boiler")

    assert reached(schedule) == SET_SCHEDULE
    assert switches(hass) == ("off", "on")
    assert state_of(hass, NEXT) == iso(SUNDAY, "06:30")
    assert len(pending(hass, NEXT)) == 1
    assert fake_target.calls == []


async def test_turning_off_at_a_time_does_not_switch_the_schedule(
    hass: HomeAssistant, fake_target: FakeTarget, generated: MockConfigEntry
) -> None:
    """The boiler is off, so "turn off the boiler at 6:30" has nothing to do: it is
    answered as a command at a time, and the interval that starts then is left on."""
    response = await converse(hass, "turn off the boiler at 6:30")

    assert reached(response) == CLOCK_COMMAND, speech(response)
    assert switches(hass) == ("on", "on")
    assert fake_target.calls == []


# --- Through an LLM's tool ----------------------------------------------------------


async def test_llm_names_an_interval_by_its_start_time(
    hass: HomeAssistant, fake_target: FakeTarget, generated: MockConfigEntry
) -> None:
    """An agent that is told the interval can be named by its start time writes it with
    a dot, as a recogniser may: the morning interval goes off, it is answered with the
    title the interval has, and the tool's description tells it that it may."""
    api = await assist_api(hass)
    (tool,) = (tool for tool in api.tools if tool.name == "timerify__set_schedule")
    assert tool.description is not None
    assert "named by its start time, such as '6:30'" in tool.description

    result = await call_tool(
        api,
        "timerify__set_schedule",
        {"name": "Boiler", "enabled": False, "interval": "6.30"},
    )

    assert result["response_type"] == "action_done"
    assert result["speech_slots"] == {
        "target": "Boiler",
        "enabled": False,
        "intervals": [MORNING_TITLE],
        "count": 1,
    }
    assert switches(hass) == ("off", "on")
    assert fake_target.calls == []


async def test_llm_is_told_every_title_a_start_time_switched(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """The weekday and the weekend morning start together with titles of their own, so
    the agent is told both; once their owner calls both Morning, they are one title
    with two intervals, which it is told as one title and a count of two."""
    entry = await setup_target()
    week = await add_interval(
        hass, entry, start="06:30", end="07:15", weekdays=["mon", "tue", "wed"]
    )
    weekend = await add_interval(
        hass, entry, start="06:30", end="08:00", weekdays=["sat", "sun"]
    )
    api = await assist_api(hass)

    by_time = await call_tool(
        api,
        "timerify__set_schedule",
        {"name": "Boiler", "enabled": False, "interval": "6:30"},
    )

    assert by_time["speech_slots"] == {
        "target": "Boiler",
        "enabled": False,
        "intervals": [
            "06:30\u201307:15, Mon\u2013Wed",
            "06:30\u201308:00, Sat, Sun",
        ],
        "count": 2,
    }
    for interval in (week, weekend):
        await retitle_interval(hass, entry, interval, "Morning")

    by_title = await call_tool(
        api,
        "timerify__set_schedule",
        {"name": "Boiler", "enabled": True, "interval": "morning"},
    )

    assert by_title["speech_slots"] == {
        "target": "Boiler",
        "enabled": True,
        "intervals": ["Morning"],
        "count": 2,
    }


async def test_llm_naming_a_renamed_interval_by_its_start_time_is_told_the_titles(
    hass: HomeAssistant, fake_target: FakeTarget, scheduled: MockConfigEntry
) -> None:
    """The morning interval has a title of the owner's: the time is not a name for it,
    and the agent is told which titles the boiler has instead."""
    refused = await call_tool(
        await assist_api(hass),
        "timerify__set_schedule",
        {"name": "Boiler", "enabled": False, "interval": "6:30"},
    )

    assert refused["response_type"] == "error"
    assert refused["speech"]["plain"]["speech"] == translated(
        "en", "exceptions", "unknown_interval", "message"
    ).format(target="Boiler", interval="6:30", intervals=BOILER_INTERVALS)
    assert switches(hass) == ("on", "on")
    assert fake_target.calls == []
