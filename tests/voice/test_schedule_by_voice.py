"""Switching the schedule of a timer on and off by voice, in English and Russian, and
through an LLM's tool.

The boiler has a weekly schedule of two intervals, Morning and Evening. A person turns
the whole schedule off, or one interval by its title, and the interval switches on the
device page say so: the voice takes the same path as those switches, so the rules of the
schedule hold. Switching off while the boiler runs on the schedule stops it (S2),
switching on while an interval is open runs the boiler for the rest of it, and nothing
reloads the timer. Every scenario talks to the real built-in agent, or calls the tool of
the real Assist API, on a clock that is moved with `advance_to`.
"""

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.const import LIST_INTERVAL, VOICE_SYNC_COOLDOWN

from ..conftest import SWITCH_SERVICES, FakeTarget, ProvideTarget, SetupTarget
from ..helpers import (
    NUMBER,
    SENSOR,
    SUNDAY,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    add_interval,
    advance,
    advance_to,
    iso,
    local,
    open_sunday,
    reload_held_back,
    retitle_interval,
    set_switch,
    state_of,
)
from .helpers import (
    add_voice_entry,
    assist_api,
    call_tool,
    conversation_reloads,
    converse,
    copy_sentences,
    every_text,
    expose,
    listed,
    reached,
    refusal_of,
    speech,
    translated,
)

SET_SCHEDULE = "TimerifySetSchedule"
MORNING = "switch.boiler_schedule_06_30_07_15_mon_sun"
EVENING = "switch.boiler_schedule_18_00_19_00_mon_sun"
"""The switches of the intervals from 06:30 to 07:15 and from 18:00 to 19:00."""
OFF = "The schedule of Boiler is off."
ON = "The schedule of Boiler is on."
BOILER_INTERVALS = "Morning; Evening"
"""How a refusal lists the titles of the intervals the boiler has."""


@pytest.fixture
async def boiler_schedule(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> MockConfigEntry:
    """A timer on the Boiler with a schedule of two intervals, Morning from 06:30 to
    07:15 and Evening from 18:00 to 19:00, on every day of the week, the way its owner
    titled them. It is Sunday, six in the morning. Assist is not told about them yet."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    morning = await add_interval(hass, entry, start="06:30", end="07:15")
    evening = await add_interval(hass, entry, start="18:00", end="19:00")
    await retitle_interval(hass, entry, morning, "Morning")
    await retitle_interval(hass, entry, evening, "Evening")
    return entry


@pytest.fixture
async def scheduled(
    hass: HomeAssistant, boiler_schedule: MockConfigEntry
) -> MockConfigEntry:
    """The boiler and its two intervals, which Assist knows by the Voice settings in
    English. A test of another language asks for `boiler_schedule` and adds the Voice
    settings of its own."""
    await add_voice_entry(hass, languages=("en",))
    return boiler_schedule


def switches(hass: HomeAssistant) -> tuple[str, str]:
    """What the switches of the Morning and the Evening interval show."""
    return state_of(hass, MORNING), state_of(hass, EVENING)


# --- The whole schedule ------------------------------------------------------------


async def test_turning_off_the_schedule_switches_every_interval_off(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    scheduled: MockConfigEntry,
) -> None:
    """Both intervals go off without the timer reloading, the boiler stays off through
    the windows of the day, and turning the schedule on brings the evening back."""
    controller = scheduled.runtime_data

    response = await converse(hass, "turn off the boiler schedule")

    assert reached(response) == SET_SCHEDULE
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert speech(response) == OFF
    assert switches(hass) == ("off", "off")
    assert scheduled.state is ConfigEntryState.LOADED
    assert scheduled.runtime_data is controller
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    await advance_to(hass, freezer, local(SUNDAY, "18:00"))
    assert fake_target.calls == []

    response = await converse(hass, "turn on the boiler schedule")

    assert reached(response) == SET_SCHEDULE
    assert speech(response) == ON
    assert switches(hass) == ("on", "on")
    assert scheduled.runtime_data is controller
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "19:00")


async def test_turning_off_the_schedule_stops_a_scheduled_run(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    scheduled: MockConfigEntry,
) -> None:
    """S2: the morning window has run the boiler since half past six. Switching the
    schedule off at seven turns it off at once, and the quarter of an hour that was
    left runs nothing."""
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:00"))
    assert fake_target.calls == [TURN_ON]

    response = await converse(hass, "turn off the boiler schedule")

    assert speech(response) == OFF
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"
    assert state_of(hass, SENSOR) == "unknown"
    assert state_of(hass, NUMBER) == "0"
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_turning_the_schedule_on_during_a_window_runs_the_target(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    scheduled: MockConfigEntry,
) -> None:
    """The schedule was off for the morning; switched on at twenty to seven, with the
    window open, the boiler runs for the rest of it."""
    await converse(hass, "turn off the boiler schedule")
    await advance_to(hass, freezer, local(SUNDAY, "06:40"))
    assert fake_target.calls == []

    response = await converse(hass, "turn on the boiler schedule")

    assert speech(response) == ON
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def set_schedule(hass: HomeAssistant, by: str, enabled: bool) -> None:
    """Switch the whole schedule as a person does: say it, or flip the two switches of
    the device page one after the other."""
    if by == "voice":
        await converse(hass, f"turn {'on' if enabled else 'off'} the boiler schedule")
    else:
        for entity_id in (MORNING, EVENING):
            await set_switch(hass, entity_id, enabled)


@pytest.mark.parametrize("by", ["voice", "switches"])
async def test_the_schedule_turned_off_in_the_middle_of_a_window_and_on_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    scheduled: MockConfigEntry,
    by: str,
) -> None:
    """The boiler runs on the morning window from half past six. Turned off at twenty
    to seven the schedule stops it, and turned on at ten to seven it runs the boiler
    for the rest of the window, to a quarter past seven. Said aloud, it comes to what
    the switches of the device page do, and the evening is not forgotten."""
    controller = scheduled.runtime_data
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == [TURN_ON]
    await advance_to(hass, freezer, local(SUNDAY, "06:40"))

    await set_schedule(hass, by, False)

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"
    assert state_of(hass, SENSOR) == "unknown"
    assert switches(hass) == ("off", "off")
    await advance_to(hass, freezer, local(SUNDAY, "06:50"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]

    await set_schedule(hass, by, True)

    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")
    assert switches(hass) == ("on", "on")
    assert scheduled.runtime_data is controller
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON, TURN_OFF]
    await advance_to(hass, freezer, local(SUNDAY, "18:00"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON, TURN_OFF, TURN_ON]


async def test_a_boiler_turned_off_by_hand_is_left_alone_by_the_schedule_asked_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    scheduled: MockConfigEntry,
) -> None:
    """Manual wins: the boiler that runs on the morning window is turned off by hand,
    and that holds until the next window. Asking for the schedule, which is on, to be
    on changes nothing: the window is not opened again."""
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await converse(hass, "turn off the boiler")
    assert fake_target.calls == [TURN_ON, TURN_OFF]

    response = await converse(hass, "turn on the boiler schedule")

    assert speech(response) == ON
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    await advance_to(hass, freezer, local(SUNDAY, "18:00"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]


@pytest.mark.parametrize("by", ["voice", "tool"])
async def test_turning_off_the_schedule_leaves_a_run_the_user_extended(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    scheduled: MockConfigEntry,
    by: str,
) -> None:
    """S3: the morning window runs the boiler to a quarter past seven, and at ten past
    the user adds an hour. The schedule is not running that timer any more, so turning
    it off, by voice or through the tool, does not stop the boiler: it runs to a
    quarter past eight. What the tool's description promises is only this."""
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:10"))
    await converse(hass, "add an hour to the boiler")
    assert state_of(hass, SENSOR) == iso(SUNDAY, "08:15")

    if by == "voice":
        await converse(hass, "turn off the boiler schedule")
    else:
        await call_tool(
            await assist_api(hass),
            "timerify__set_schedule",
            {"name": "Boiler", "enabled": False},
        )

    assert switches(hass) == ("off", "off")
    assert state_of(hass, SENSOR) == iso(SUNDAY, "08:15")
    assert fake_target.calls == [TURN_ON]
    await advance_to(hass, freezer, local(SUNDAY, "08:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_turning_the_schedule_on_leaves_a_run_that_ends_later(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    scheduled: MockConfigEntry,
) -> None:
    """S1: with the schedule off, the user runs the boiler for two hours at twenty to
    seven. Turning the schedule on opens the morning window, which ends sooner than the
    run, so the run is left alone."""
    await converse(hass, "turn off the boiler schedule")
    await advance_to(hass, freezer, local(SUNDAY, "06:40"))
    await converse(hass, "turn on the boiler for 2 hours")
    assert state_of(hass, SENSOR) == iso(SUNDAY, "08:40")

    await converse(hass, "turn on the boiler schedule")

    assert switches(hass) == ("on", "on")
    assert state_of(hass, SENSOR) == iso(SUNDAY, "08:40")
    assert fake_target.calls == [TURN_ON]


async def test_the_schedule_asked_off_twice_is_off(
    hass: HomeAssistant, scheduled: MockConfigEntry
) -> None:
    await converse(hass, "turn off the boiler schedule")

    response = await converse(hass, "disable the boiler schedule")

    assert reached(response) == SET_SCHEDULE
    assert speech(response) == OFF
    assert switches(hass) == ("off", "off")


# --- One interval by its title -----------------------------------------------------


async def test_one_interval_by_its_title(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    scheduled: MockConfigEntry,
) -> None:
    """Only the Morning goes off: the boiler skips the morning and keeps its evening;
    asked on again, in lower case, the morning is back."""
    response = await converse(hass, "turn off the Morning schedule of the Boiler")

    assert reached(response) == SET_SCHEDULE
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert speech(response) == "The Morning schedule of Boiler is off."
    assert switches(hass) == ("off", "on")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == []
    await advance_to(hass, freezer, local(SUNDAY, "18:00"))
    assert fake_target.calls == [TURN_ON]

    response = await converse(hass, "enable the morning schedule of the boiler")

    assert speech(response) == "The Morning schedule of Boiler is on."
    assert switches(hass) == ("on", "on")


async def test_an_interval_is_switched_through_the_switch_it_has(
    hass: HomeAssistant, scheduled: MockConfigEntry
) -> None:
    """What the voice switched, the switch on the device page can switch back, and the
    other way round: it is one flag."""
    await converse(hass, "pause the Evening schedule of the Boiler")
    assert switches(hass) == ("on", "off")

    await set_switch(hass, EVENING, True)
    await set_switch(hass, MORNING, False)
    response = await converse(hass, "resume the Morning schedule of the Boiler")

    assert speech(response) == "The Morning schedule of Boiler is on."
    assert switches(hass) == ("on", "on")


async def test_an_interval_that_is_not_the_timers_is_refused(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    scheduled: MockConfigEntry,
    setup_target: SetupTarget,
) -> None:
    """The titles are the house's: the fan has a Night interval and the boiler has not.
    Asking the boiler for it is answered, nothing is switched, and the fan's schedule
    is untouched."""
    fan = await setup_target(target=fake_fan.entity_id)
    night = await add_interval(hass, fan, start="22:00", end="23:00")
    await retitle_interval(hass, fan, night, "Night")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    response = await converse(hass, "turn off the Night schedule of the Boiler")

    assert reached(response) == SET_SCHEDULE
    assert refusal_of(response) == translated(
        "en", "exceptions", "unknown_interval", "message"
    ).format(target="Boiler", interval="Night", intervals=BOILER_INTERVALS)
    assert switches(hass) == ("on", "on")
    assert state_of(hass, "switch.fan_schedule_22_00_23_00_mon_sun") == "on"


async def test_a_refusal_lists_what_can_be_asked_for_apart_by_semicolons(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    scheduled: MockConfigEntry,
    setup_target: SetupTarget,
) -> None:
    """The title an interval gets when nobody titles it has a comma, so what is listed
    is set apart by semicolons and the one title stays one."""
    await add_interval(hass, scheduled, start="22:00", end="23:00")
    fan = await setup_target(target=fake_fan.entity_id)
    night = await add_interval(hass, fan, start="22:00", end="23:00")
    await retitle_interval(hass, fan, night, "Night")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    response = await converse(hass, "turn off the Night schedule of the Boiler")

    assert reached(response) == SET_SCHEDULE
    assert refusal_of(response) == (
        'Boiler has no schedule interval called "Night". '
        "Its intervals: Morning; Evening; 22:00\u201323:00, Mon\u2013Sun."
    )


async def test_a_long_list_of_titles_is_cut_to_what_can_be_heard(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    scheduled: MockConfigEntry,
    setup_target: SetupTarget,
) -> None:
    """The boiler has seven intervals and is asked for the fan's Night: the answer
    names the first five and counts the other two, instead of reading out the house."""
    for hour in (1, 2, 3, 4, 5):
        interval = await add_interval(
            hass, scheduled, start=f"{hour:02d}:00", end=f"{hour:02d}:30"
        )
        await retitle_interval(hass, scheduled, interval, f"Slot {hour}")
    fan = await setup_target(target=fake_fan.entity_id)
    night = await add_interval(hass, fan, start="22:00", end="23:00")
    await retitle_interval(hass, fan, night, "Night")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    response = await converse(hass, "turn off the Night schedule of the Boiler")

    assert reached(response) == SET_SCHEDULE
    assert refusal_of(response) == (
        'Boiler has no schedule interval called "Night". '
        "Its first intervals: Morning; Evening; Slot 1; Slot 2; Slot 3; and 2 more."
    )
    assert switches(hass) == ("on", "on")


async def test_a_schedule_with_no_title_to_ask_for_says_so_to_the_voice(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    scheduled: MockConfigEntry,
    setup_target: SetupTarget,
) -> None:
    """Every interval of the boiler is titled by punctuation alone, which cannot be
    said. Asked for the fan's Night, the boiler does not list nothing: it says that none
    of its intervals can be asked for by title, and what to do about it."""
    for interval in list(scheduled.subentries):
        await retitle_interval(hass, scheduled, interval, "?!")
    fan = await setup_target(target=fake_fan.entity_id)
    night = await add_interval(hass, fan, start="22:00", end="23:00")
    await retitle_interval(hass, fan, night, "Night")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    response = await converse(hass, "turn off the Night schedule of the Boiler")

    assert reached(response) == SET_SCHEDULE
    assert refusal_of(response) == (
        "Boiler has no schedule interval that can be asked for by title. "
        "Give its intervals titles with letters or digits first."
    )
    assert switches(hass) == ("on", "on")


async def test_a_title_nobody_has_is_not_understood(
    hass: HomeAssistant, scheduled: MockConfigEntry
) -> None:
    """A title that no timer has is not in the sentences: the agent answers as it does
    to anything it cannot place, and nothing is switched."""
    response = await converse(hass, "turn off the Midnight schedule of the Boiler")

    assert reached(response) != SET_SCHEDULE
    assert response.response_type is intent.IntentResponseType.ERROR
    assert switches(hass) == ("on", "on")


# --- Phrasings that are close to the sentences ----------------------------------------

OFF_IN_OTHER_WORDS = [
    ("turn off the schedule for the boiler", ("off", "off")),
    ("turn the schedule of the boiler off", ("off", "off")),
    ("turn the schedule for the boiler off", ("off", "off")),
    ("switch off the schedule for the boiler", ("off", "off")),
    ("disable the schedule for the boiler", ("off", "off")),
    ("pause the schedule for the boiler", ("off", "off")),
    ("turn off the morning schedule for the boiler", ("off", "on")),
    ("turn the morning schedule of the boiler off", ("off", "on")),
    ("turn the morning schedule for the boiler off", ("off", "on")),
    ("disable the morning schedule for the boiler", ("off", "on")),
    ("pause the morning schedule for the boiler", ("off", "on")),
]
ON_IN_OTHER_WORDS = [
    ("turn on the schedule for the boiler", ("on", "on")),
    ("turn the schedule of the boiler on", ("on", "on")),
    ("turn the schedule for the boiler on", ("on", "on")),
    ("switch on the schedule for the boiler", ("on", "on")),
    ("enable the schedule for the boiler", ("on", "on")),
    ("resume the schedule for the boiler", ("on", "on")),
    ("turn on the morning schedule for the boiler", ("on", "off")),
    ("turn the morning schedule of the boiler on", ("on", "off")),
    ("turn the morning schedule for the boiler on", ("on", "off")),
    ("enable the morning schedule for the boiler", ("on", "off")),
    ("resume the morning schedule for the boiler", ("on", "off")),
]


@pytest.mark.parametrize(("text", "expected"), OFF_IN_OTHER_WORDS)
async def test_the_schedule_asked_off_in_other_words_is_not_a_bare_turn_off(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    scheduled: MockConfigEntry,
    text: str,
    expected: tuple[str, str],
) -> None:
    """ "For" as well as "of", and the on or off after the schedule as well as before
    it: Home Assistant would otherwise read the words as a turn off of the boiler,
    which they say nothing about. The schedule is switched, the boiler is not
    touched, and the morning, which is off, runs nothing."""
    response = await converse(hass, text)

    assert reached(response) == SET_SCHEDULE
    assert switches(hass) == expected
    assert fake_target.calls == []
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == []


@pytest.mark.parametrize(("text", "expected"), ON_IN_OTHER_WORDS)
async def test_the_schedule_asked_on_in_other_words_is_not_a_bare_turn_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    scheduled: MockConfigEntry,
    text: str,
    expected: tuple[str, str],
) -> None:
    """The schedule was off and is asked on in other words: it is switched on, and the
    boiler, which is off outside the windows, is not turned on by the words."""
    await set_schedule(hass, "switches", False)

    response = await converse(hass, text)

    assert reached(response) == SET_SCHEDULE
    assert switches(hass) == expected
    assert fake_target.calls == []
    assert state_of(hass, TARGET_ID) == "off"
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == ([TURN_ON] if expected[0] == "on" else [])


# --- Titles --------------------------------------------------------------------------


async def test_interval_titles_follow_edits(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    scheduled: MockConfigEntry,
) -> None:
    """An interval retitled Early is called Early once the cooldown is over: the
    sentences list it, say it, and the old title is not understood any more."""
    reloads = conversation_reloads(hass)
    (morning,) = (
        subentry.subentry_id
        for subentry in scheduled.subentries.values()
        if subentry.title == "Morning"
    )

    await retitle_interval(hass, scheduled, morning, "Early")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert [value["out"] for value in listed(hass, "en", LIST_INTERVAL)] == [
        "Early",
        "Evening",
    ]
    assert len(reloads) == 1
    response = await converse(hass, "turn off the Early schedule of the Boiler")
    assert speech(response) == "The Early schedule of Boiler is off."
    assert switches(hass) == ("off", "on")
    response = await converse(hass, "turn on the Morning schedule of the Boiler")
    assert reached(response) != SET_SCHEDULE
    assert switches(hass) == ("off", "on")


async def test_interval_title_with_template_characters_is_escaped(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    scheduled: MockConfigEntry,
) -> None:
    """A title with parentheses, which Home Assistant would read as part of a sentence
    template, is written so that it is read as the title and said as it is."""
    (morning,) = (
        subentry.subentry_id
        for subentry in scheduled.subentries.values()
        if subentry.title == "Morning"
    )

    await retitle_interval(hass, scheduled, morning, "Morning (weekdays)")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert listed(hass, "en", LIST_INTERVAL)[0] == {
        "in": r"Morning \(weekdays\)",
        "out": "Morning (weekdays)",
    }
    response = await converse(
        hass, "turn off the Morning (weekdays) schedule of the Boiler"
    )
    assert reached(response) == SET_SCHEDULE
    assert speech(response) == "The Morning (weekdays) schedule of Boiler is off."
    assert switches(hass) == ("off", "on")


async def test_an_interval_still_titled_by_its_times_can_be_said(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """The title an interval is given when it is made, its times and days, is listed
    like any other; said as it reads, the interval is switched."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await add_voice_entry(hass)

    response = await converse(
        hass, "turn off the 06:30–07:15, Mon–Sun schedule of the Boiler"
    )

    assert reached(response) == SET_SCHEDULE
    assert speech(response) == "The 06:30–07:15, Mon–Sun schedule of Boiler is off."
    assert state_of(hass, MORNING) == "off"


async def test_two_intervals_with_one_title_are_switched_together(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """The owner calls the weekday and the weekend morning both Morning: the Morning
    schedule is both, and the evening is not touched."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    week = await add_interval(
        hass, entry, start="06:30", end="07:15", weekdays=["mon", "tue", "wed"]
    )
    weekend = await add_interval(
        hass, entry, start="08:00", end="09:00", weekdays=["sat", "sun"]
    )
    evening = await add_interval(hass, entry, start="18:00", end="19:00")
    for interval, title in ((week, "Morning"), (weekend, "Morning"), (evening, "Late")):
        await retitle_interval(hass, entry, interval, title)
    await add_voice_entry(hass)

    response = await converse(hass, "turn off the Morning schedule of the Boiler")

    assert speech(response) == "The Morning schedule of Boiler is off."
    assert [
        state_of(hass, entity_id)
        for entity_id in (
            "switch.boiler_schedule_06_30_07_15_mon_wed",
            "switch.boiler_schedule_08_00_09_00_sat_sun",
            EVENING,
        )
    ] == ["off", "off", "on"]


# --- Where the words do not belong to the schedule ------------------------------------


async def test_the_schedule_of_a_target_that_is_not_exposed_is_not_switched(
    hass: HomeAssistant, scheduled: MockConfigEntry
) -> None:
    expose(hass, TARGET_ID, False)

    response = await converse(hass, "turn off the boiler schedule")

    assert response.response_type is intent.IntentResponseType.ERROR
    assert response.error_code is intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert switches(hass) == ("on", "on")


async def test_the_same_words_about_a_device_without_a_timer_do_nothing(
    hass: HomeAssistant, fake_fan: FakeTarget, scheduled: MockConfigEntry
) -> None:
    response = await converse(hass, "turn off the fan schedule")

    assert response.response_type is intent.IntentResponseType.ERROR
    assert fake_fan.calls == []
    assert switches(hass) == ("on", "on")


async def test_a_timer_without_a_schedule_says_so(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """The boiler has no intervals, so there is nothing to switch: the answer says so,
    in the language of the request, for the whole schedule and for an interval."""
    await setup_target()
    await copy_sentences(hass, ["Boiler"], intervals=["Morning"])

    whole = await converse(hass, "turn off the boiler schedule")
    one = await converse(hass, "turn off the Morning schedule of the boiler")

    assert refusal_of(whole) == translated(
        "en", "exceptions", "no_schedule", "message"
    ).format(target="Boiler")
    assert refusal_of(one) == refusal_of(whole)
    assert fake_target.calls == []


# --- Words that belong to something else too ----------------------------------------


async def test_the_manual_installation_lists_the_titles_by_hand(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """Without the Voice settings the titles are the ones the owner puts in the names
    file: Morning is listed there and Evening is not, so only Morning is understood."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    morning = await add_interval(hass, entry, start="06:30", end="07:15")
    evening = await add_interval(hass, entry, start="18:00", end="19:00")
    await retitle_interval(hass, entry, morning, "Morning")
    await retitle_interval(hass, entry, evening, "Evening")
    await copy_sentences(hass, ["Boiler"], intervals=["Morning"])

    unlisted = await converse(hass, "turn off the Evening schedule of the Boiler")
    listed_one = await converse(hass, "turn off the Morning schedule of the Boiler")

    assert reached(unlisted) != SET_SCHEDULE
    assert reached(listed_one) == SET_SCHEDULE
    assert switches(hass) == ("off", "on")


async def test_a_device_called_like_the_schedule_is_not_what_the_words_mean(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    provide_target: ProvideTarget,
    scheduled: MockConfigEntry,
) -> None:
    """A switch of the house that is called Boiler schedule, which Assist can find by
    that name, is not turned off by the words about the boiler's schedule: they mean the
    schedule (a name that a timer has is the timer's, P-1), and the boiler is not
    turned on or off by them either. The bare words about the boiler are still the
    timer's."""
    lookalike = provide_target(
        "switch.boiler_schedule", SWITCH_SERVICES, name="Boiler schedule"
    )
    expose(hass, lookalike.entity_id, True)
    found = intent.async_match_targets(
        hass,
        intent.MatchTargetsConstraints(
            name="boiler schedule", assistant="conversation"
        ),
    )
    assert [state.entity_id for state in found.states] == [lookalike.entity_id]

    for text in ("turn off the boiler schedule", "turn on the boiler schedule"):
        response = await converse(hass, text)

        assert reached(response) == SET_SCHEDULE, text
    response = await converse(hass, "turn off the boiler schedule")

    assert switches(hass) == ("off", "off")
    assert lookalike.calls == []
    assert fake_target.calls == []
    assert reached(await converse(hass, "turn on the boiler")) == "TimerifyRun"


async def test_an_interval_switch_that_assist_may_use_is_not_what_the_words_mean(
    hass: HomeAssistant, fake_target: FakeTarget, scheduled: MockConfigEntry
) -> None:
    """The switch of the morning interval is exposed to Assist by its owner and called
    Boiler schedule. The words about the boiler's schedule still switch the whole
    schedule, the evening too, and not that one switch."""
    er.async_get(hass).async_update_entity(MORNING, name="Boiler schedule")
    expose(hass, MORNING, True)

    response = await converse(hass, "turn off the boiler schedule")

    assert reached(response) == SET_SCHEDULE
    assert switches(hass) == ("off", "off")
    assert fake_target.calls == []


async def test_the_words_about_another_schedule_are_core_s(
    hass: HomeAssistant,
    provide_target: ProvideTarget,
    fake_target: FakeTarget,
    scheduled: MockConfigEntry,
) -> None:
    """A switch called Pump schedule that no timer is for is turned on and off by Home
    Assistant as before: the words are Timerify's only for the names of its timers."""
    pump = provide_target("switch.pump_schedule", SWITCH_SERVICES, name="Pump schedule")

    on = await converse(hass, "turn on the pump schedule")
    off = await converse(hass, "turn off the pump schedule")

    assert reached(on) == "HassTurnOn"
    assert reached(off) == "HassTurnOff"
    assert pump.calls == [
        ("turn_on", "switch.pump_schedule"),
        ("turn_off", "switch.pump_schedule"),
    ]
    assert fake_target.calls == []
    assert switches(hass) == ("on", "on")


# --- The phrases ---------------------------------------------------------------------


@pytest.mark.parametrize("language", ["en", "ru"])
@pytest.mark.parametrize("enabled", [True, False])
async def test_every_sentence_reaches_set_schedule(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler_schedule: MockConfigEntry,
    language: str,
    enabled: bool,
) -> None:
    """Every way the sentence files have to say it, in both languages, reaches the
    handler with the boiler, the interval when one is said, and what the sentence
    means; the answer differs with what is asked and with the interval, and no
    sentence is taken for a bare turn on or off of the boiler."""
    await add_voice_entry(hass, languages=(language,))
    texts = [
        (text, fixed)
        for text, fixed in every_text(language, SET_SCHEDULE)
        if fixed["enabled"] is enabled
    ]
    assert texts
    answers: dict[bool, set[str]] = {False: set(), True: set()}

    for text, _ in texts:
        response = await converse(hass, text, language)

        assert reached(response) == SET_SCHEDULE, text
        assert response.response_type is intent.IntentResponseType.ACTION_DONE, text
        assert response.intent is not None
        slots = response.intent.slots
        assert slots["name"]["value"] == "Boiler", text
        assert slots["enabled"]["value"] is enabled, text
        if has_interval := "interval" in slots:
            assert slots["interval"]["value"] == "Morning", text
        answers[has_interval].add(speech(response))

    assert fake_target.calls == []
    assert switches(hass) == (("on", "on") if enabled else ("off", "off"))
    assert all(len(spoken) == 1 for spoken in answers.values()), answers
    assert answers[False] != answers[True]
    if language == "en":
        assert answers[False] == {ON if enabled else OFF}
        assert answers[True] == {
            f"The Morning schedule of Boiler is {'on' if enabled else 'off'}."
        }


async def test_russian_answers_differ_with_what_is_asked(
    hass: HomeAssistant, boiler_schedule: MockConfigEntry
) -> None:
    """Off and on are not the same answer, and both name the boiler first."""
    await add_voice_entry(hass, languages=("ru",))
    off = next(
        text
        for text, fixed in every_text("ru", SET_SCHEDULE)
        if fixed["enabled"] is False and "Morning" not in text
    )
    on = next(
        text
        for text, fixed in every_text("ru", SET_SCHEDULE)
        if fixed["enabled"] is True and "Morning" not in text
    )

    said_off = speech(await converse(hass, off, "ru"))
    said_on = speech(await converse(hass, on, "ru"))

    assert said_off != said_on
    assert said_off.startswith("Boiler: ")
    assert said_on.startswith("Boiler: ")
    assert switches(hass) == ("on", "on")


async def test_a_refusal_is_spoken_in_russian(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    await setup_target()
    await add_voice_entry(hass, languages=("ru",))
    text = next(
        text for text, fixed in every_text("ru", SET_SCHEDULE) if "Morning" not in text
    )

    response = await converse(hass, text, "ru")

    assert refusal_of(response) == translated(
        "ru", "exceptions", "no_schedule", "message"
    ).format(target="Boiler")


# --- Through an LLM's tool -----------------------------------------------------------


async def test_llm_set_schedule(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    scheduled: MockConfigEntry,
) -> None:
    """The agent switches the whole schedule and then one interval; it is told which
    intervals were switched, and an interval the boiler has not is explained."""
    api = await assist_api(hass)

    whole = await call_tool(
        api, "timerify__set_schedule", {"name": "Boiler", "enabled": False}
    )

    assert whole["response_type"] == "action_done"
    assert whole["speech_slots"] == {
        "target": "Boiler",
        "enabled": False,
        "interval": None,
        "count": 2,
    }
    assert switches(hass) == ("off", "off")

    one = await call_tool(
        api,
        "timerify__set_schedule",
        {"name": "Boiler", "enabled": True, "interval": "morning"},
    )

    assert one["speech_slots"] == {
        "target": "Boiler",
        "enabled": True,
        "interval": "Morning",
        "count": 1,
    }
    assert switches(hass) == ("on", "off")

    refused = await call_tool(
        api,
        "timerify__set_schedule",
        {"name": "Boiler", "enabled": True, "interval": "Noon"},
    )

    assert refused["response_type"] == "error"
    assert refused["speech"]["plain"]["speech"] == translated(
        "en", "exceptions", "unknown_interval", "message"
    ).format(target="Boiler", interval="Noon", intervals=BOILER_INTERVALS)
    assert switches(hass) == ("on", "off")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == [TURN_ON]


async def test_llm_asking_for_an_interval_just_deleted_is_told_which_are_left(
    hass: HomeAssistant, scheduled: MockConfigEntry
) -> None:
    """The user deletes the Morning interval and an agent, which was told its title a
    moment ago, asks for it before the timer has reloaded: it is told that the boiler
    has no such interval and which it has, and nothing else is switched."""
    api = await assist_api(hass)
    (morning,) = (
        subentry_id
        for subentry_id, subentry in scheduled.subentries.items()
        if subentry.title == "Morning"
    )
    async with reload_held_back(scheduled):
        hass.config_entries.async_remove_subentry(scheduled, morning)

        refused = await call_tool(
            api,
            "timerify__set_schedule",
            {"name": "Boiler", "enabled": False, "interval": "Morning"},
        )

    assert refused["response_type"] == "error"
    assert refused["speech"]["plain"]["speech"] == translated(
        "en", "exceptions", "unknown_interval", "message"
    ).format(target="Boiler", interval="Morning", intervals="Evening")
    await hass.async_block_till_done()
    assert state_of(hass, EVENING) == "on"


async def test_llm_set_schedule_needs_to_be_told_on_or_off(
    hass: HomeAssistant, scheduled: MockConfigEntry
) -> None:
    """There is no default for `enabled`: a tool call that leaves it out is refused as
    one that misses a required argument, and nothing is switched."""
    api = await assist_api(hass)

    with pytest.raises(intent.InvalidSlotInfo):
        await call_tool(api, "timerify__set_schedule", {"name": "Boiler"})

    assert switches(hass) == ("on", "on")


async def test_llm_refuses_a_timer_without_a_schedule_in_its_own_language(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    await setup_target()
    api = await assist_api(hass, "ru")

    refused = await call_tool(
        api, "timerify__set_schedule", {"name": "Boiler", "enabled": False}
    )

    assert refused["response_type"] == "error"
    assert refused["speech"]["plain"]["speech"] == translated(
        "ru", "exceptions", "no_schedule", "message"
    ).format(target="Boiler")


async def test_llm_finds_the_interval_it_titled_by_its_times_whatever_the_dash(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """An interval keeps the title it was made with, its times and days, which has
    en dashes. An agent that types a hyphen, as it would, means that interval, and is
    told the title as the interval has it."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    api = await assist_api(hass)

    result = await call_tool(
        api,
        "timerify__set_schedule",
        {"name": "Boiler", "enabled": False, "interval": "06:30-07:15, Mon-Sun"},
    )

    assert result["response_type"] == "action_done"
    assert result["speech_slots"]["interval"] == "06:30–07:15, Mon–Sun"
    assert state_of(hass, MORNING) == "off"


async def test_llm_asking_for_an_interval_of_punctuation_switches_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    boiler_schedule: MockConfigEntry,
) -> None:
    """A title of nothing but punctuation cannot be said, so the voice does not know it;
    an agent asking for "?" does not get it either, nor does the whole schedule go off
    for want of a title. The answer lists the titles that can be asked for."""
    (morning,) = (
        subentry.subentry_id
        for subentry in boiler_schedule.subentries.values()
        if subentry.title == "Morning"
    )
    await retitle_interval(hass, boiler_schedule, morning, "?!")
    api = await assist_api(hass)

    refused = await call_tool(
        api,
        "timerify__set_schedule",
        {"name": "Boiler", "enabled": False, "interval": "?"},
    )

    assert refused["response_type"] == "error"
    assert refused["speech"]["plain"]["speech"] == translated(
        "en", "exceptions", "unknown_interval", "message"
    ).format(target="Boiler", interval="?", intervals="Evening")
    assert switches(hass) == ("on", "on")


async def test_llm_is_told_the_titles_in_the_quotes_of_its_language(
    hass: HomeAssistant, scheduled: MockConfigEntry
) -> None:
    """The quotes around the asked title are the language's own, English straight and
    Russian guillemets, and the titles listed are bare, so that no sentence mixes two
    kinds."""
    english = await call_tool(
        await assist_api(hass),
        "timerify__set_schedule",
        {"name": "Boiler", "enabled": False, "interval": "Noon"},
    )
    russian = await call_tool(
        await assist_api(hass, "ru"),
        "timerify__set_schedule",
        {"name": "Boiler", "enabled": False, "interval": "Noon"},
    )

    assert english["speech"]["plain"]["speech"] == (
        'Boiler has no schedule interval called "Noon". '
        "Its intervals: Morning; Evening."
    )
    said = russian["speech"]["plain"]["speech"]
    assert said == translated("ru", "exceptions", "unknown_interval", "message").format(
        target="Boiler", interval="Noon", intervals=BOILER_INTERVALS
    )
    assert "\u00abNoon\u00bb" in said
    assert '"' not in said
    assert switches(hass) == ("on", "on")


async def test_llm_is_told_how_many_titles_are_left_out_in_its_language(
    hass: HomeAssistant, scheduled: MockConfigEntry
) -> None:
    """Seven intervals are more than a refusal lists: the first five are named and the
    rest counted, in English and in Russian."""
    for hour in (1, 2, 3, 4, 5):
        interval = await add_interval(
            hass, scheduled, start=f"{hour:02d}:00", end=f"{hour:02d}:30"
        )
        await retitle_interval(hass, scheduled, interval, f"Slot {hour}")
    listed = "Morning; Evening; Slot 1; Slot 2; Slot 3"

    english = await call_tool(
        await assist_api(hass),
        "timerify__set_schedule",
        {"name": "Boiler", "enabled": False, "interval": "Noon"},
    )
    russian = await call_tool(
        await assist_api(hass, "ru"),
        "timerify__set_schedule",
        {"name": "Boiler", "enabled": False, "interval": "Noon"},
    )

    assert english["speech"]["plain"]["speech"] == (
        'Boiler has no schedule interval called "Noon". '
        f"Its first intervals: {listed}; and 2 more."
    )
    assert russian["speech"]["plain"]["speech"] == translated(
        "ru", "exceptions", "unknown_interval_and_more", "message"
    ).format(target="Boiler", interval="Noon", intervals=listed, more="2")
    assert switches(hass) == ("on", "on")


@pytest.mark.parametrize("language", ["en", "ru"])
async def test_llm_is_told_when_no_title_can_be_asked_for(
    hass: HomeAssistant, scheduled: MockConfigEntry, language: str
) -> None:
    """The intervals of the boiler are titled by punctuation alone, which neither the
    voice nor a tool can ask for: the refusal says so in the language of the request
    instead of listing nothing, and the whole schedule is still there to switch."""
    for interval in list(scheduled.subentries):
        await retitle_interval(hass, scheduled, interval, "?!")
    api = await assist_api(hass, language)

    refused = await call_tool(
        api,
        "timerify__set_schedule",
        {"name": "Boiler", "enabled": False, "interval": "Morning"},
    )
    whole = await call_tool(
        api, "timerify__set_schedule", {"name": "Boiler", "enabled": False}
    )

    assert refused["response_type"] == "error"
    assert refused["speech"]["plain"]["speech"] == translated(
        language, "exceptions", "no_interval_titles", "message"
    ).format(target="Boiler")
    assert whole["speech_slots"]["count"] == 2
    assert switches(hass) == ("off", "off")


async def test_llm_leaving_the_interval_blank_means_the_whole_schedule(
    hass: HomeAssistant, scheduled: MockConfigEntry
) -> None:
    """Home Assistant takes an argument that is empty or only spaces for one that was
    not given, for every tool: so a blank interval is no interval, and the whole
    schedule is switched, as the tool says it is when there is none."""
    api = await assist_api(hass)

    result = await call_tool(
        api,
        "timerify__set_schedule",
        {"name": "Boiler", "enabled": False, "interval": "  "},
    )

    assert result["speech_slots"]["interval"] is None
    assert result["speech_slots"]["count"] == 2
    assert switches(hass) == ("off", "off")
