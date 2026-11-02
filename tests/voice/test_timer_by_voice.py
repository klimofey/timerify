"""Running a timer, adding time to it and stopping it by voice and through an LLM's
tools, with the settings a target takes, in English and Russian.

Every scenario talks to the real built-in agent, or calls a tool of the real Assist API.
The boiler is known to Assist by the sentences of the manual installation (`boiler`);
a target that has settings is known by the Voice settings entry, which also writes the
words for the modes and the presets that the targets have (`with_voice_settings`).
"""

import itertools
from unittest.mock import patch

import probatio
import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.const import (
    CONF_DEFAULT_DURATION,
    CONF_MODE,
    CONF_RUN_FOR_MAX,
    CONF_RUNTIME,
    LIST_HVAC_MODE,
    LIST_MODE,
    MAX_MINUTES,
    VOICE_LANGUAGES,
)
from custom_components.timerify.domains import SETTING_KINDS
from custom_components.timerify.services import SETTINGS_SCHEMA
from custom_components.timerify.voice.base import (
    PERCENT_SLOT,
    SETTING_SLOTS,
)

from ..conftest import CLIMATE_SERVICES, FakeTarget, ProvideTarget, SetupTarget
from ..helpers import (
    AC_ATTRS,
    AC_ID,
    AC_NEXT,
    AC_NUMBER,
    NUMBER,
    SENSOR,
    SMALL_AC_ID,
    SMALL_AC_NEXT,
    SMALL_AC_NUMBER,
    SUNDAY,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    add_interval,
    advance_to,
    change_options,
    edit_interval,
    iso,
    local,
    open_sunday,
    set_number,
    state_of,
)
from .helpers import (
    CLIMATE_FAN_MODE,
    HOUR_CLASSES,
    MINUTE_CLASSES,
    SETTING_LISTS,
    PluralClasses,
    assert_one_form_per_class,
    assist_api,
    call_tool,
    converse,
    copy_sentences,
    expose,
    hvac_words,
    listed,
    pending,
    reached,
    readings,
    refusal_of,
    samples,
    speech,
    spoken_rule,
    spoken_values,
    talk,
    translated,
    with_voice_settings,
    word_of,
)

RUN = "TimerifyRun"
ADD_TIME = "TimerifyAddTime"
STOP = "TimerifyStop"
LAMP_NUMBER = "number.lamp_run_for"
TANK_NUMBER = "number.tank_run_for"
VENT_NUMBER = "number.vent_run_for"
COOL = ("set_hvac_mode", {"hvac_mode": "cool"})
TEMPERATURE_24 = ("set_temperature", {"temperature": 24.0})
COOL_24 = [COOL, TEMPERATURE_24]
"""The calls that turn the air conditioner on cooling, at 24 degrees."""


# --- Running a timer ---------------------------------------------------------------


async def test_turn_on_for_minutes_runs_the_timer(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The boiler is turned on once, the countdown shows the minutes, and the answer
    says when the boiler turns off."""
    response = await converse(hass, "turn on the boiler for 45 minutes")

    assert reached(response) == RUN
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "45"
    assert speech(response) == "Boiler runs for 45 minutes, until 09:45."


@pytest.mark.parametrize(
    ("text", "minutes"),
    [
        ("turn the boiler on for an hour", 60),
        ("run the boiler for 2 hours", 120),
        ("turn on the boiler for 1 hour and 30 minutes", 90),
        ("turn on the boiler for 1 hour 30 minutes", 90),
        ("turn on the boiler for half an hour", 30),
        ("turn on the boiler for an hour and a half", 90),
        ("turn on the boiler for twenty minutes", 20),
        ("set the boiler timer to 20 minutes", 20),
        ("Turn on the Boiler for 15 minutes.", 15),
    ],
)
async def test_run_phrasings(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    text: str,
    minutes: int,
) -> None:
    """Every way to ask reaches the timer with the same minutes."""
    response = await converse(hass, text)

    assert reached(response) == RUN, speech(response)
    assert state_of(hass, NUMBER) == str(minutes)
    assert fake_target.calls == [TURN_ON]


async def test_for_an_hour_and_bare_minutes_runs_a_switch_for_90_minutes(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """A speaker drops the word "minutes" after the hours: "for 1 hour 30" is what
    "for 1 hour 30 minutes" means, for a device that takes no temperature."""
    response = await converse(hass, "turn on the boiler for 1 hour 30")

    assert reached(response) == RUN, speech(response)
    assert state_of(hass, NUMBER) == "90"
    assert fake_target.calls == [TURN_ON]
    assert speech(response).startswith("Boiler runs for 1 hour and 30 minutes, until")


async def test_a_day_is_the_longest_run(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    response = await converse(hass, "turn on the boiler for 24 hours")

    assert state_of(hass, NUMBER) == str(MAX_MINUTES)
    assert speech(response) == "Boiler runs for 24 hours, until 09:00 tomorrow."


async def test_a_run_by_voice_goes_past_the_maximum_of_run_for(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The maximum is the end of the slider, not a limit on the timer: after the user
    cuts the slider to two hours, "for 3 hours" is still heard and runs in full."""
    await change_options(
        hass,
        boiler,
        {CONF_MODE: "strict", CONF_RUNTIME: False, CONF_RUN_FOR_MAX: 120},
        {CONF_DEFAULT_DURATION: 45},
    )

    response = await converse(hass, "turn on the boiler for 3 hours")

    assert reached(response) == RUN, speech(response)
    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert state_of(hass, NUMBER) == "180"
    assert fake_target.calls == [TURN_ON]
    assert speech(response) == "Boiler runs for 3 hours, until 12:00."


async def test_run_longer_than_a_day_is_refused(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The sentence is understood, and the timer says what it takes: nothing is turned
    on, and no countdown is left."""
    response = await converse(hass, "turn on the boiler for 24 hours and 30 minutes")

    assert reached(response) == RUN
    assert refusal_of(response) == "A timer runs for 1 min to 24 h."
    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "0"


async def test_run_for_thirty_hours_is_refused_with_the_limit(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """More than a day is understood, not answered as a sentence that makes no sense:
    the user hears what a timer takes."""
    response = await converse(hass, "turn on the boiler for 30 hours")

    assert reached(response) == RUN
    assert refusal_of(response) == "A timer runs for 1 min to 24 h."
    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "0"


OVER_A_DAY = [
    pytest.param({"timerify_hours": 30}, id="30-hours"),
    pytest.param({"timerify_long_minutes": 1500}, id="1500-minutes"),
    pytest.param({"timerify_hours": 168}, id="a-week-of-hours"),
    pytest.param({"timerify_long_minutes": 10080}, id="a-week-of-minutes"),
]
"""A count that is more than a day and as much as the sentences understand. Minutes
beyond a day are the list of digits that fills the slot of the minutes."""


@pytest.mark.parametrize("numbers", OVER_A_DAY)
@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_a_run_for_more_than_a_day_is_refused_in_the_users_language(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    language: str,
    numbers: dict[str, int],
) -> None:
    """Every way of saying it, as the shipped sentences give them, reaches the timer,
    which refuses with its limit in the language of the request: nothing is turned
    on."""
    texts = samples(language, RUN, numbers=numbers, absent=SETTING_LISTS)
    assert texts

    for text in texts:
        response = await converse(hass, text, language=language)

        assert reached(response) == RUN, text
        assert refusal_of(response) == translated(
            language, "exceptions", "duration_out_of_range", "message"
        ).format(max_hours="24"), text
    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "0"


async def test_a_run_replaces_the_countdown_that_was_there(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
) -> None:
    await set_number(hass, NUMBER, 30)

    response = await converse(hass, "turn on the boiler for 10 minutes")

    assert state_of(hass, NUMBER) == "10"
    assert speech(response) == "Boiler runs for 10 minutes, until 09:10."
    assert fake_target.calls == [TURN_ON]


async def test_a_target_without_a_timer_is_left_alone(
    hass: HomeAssistant, fake_fan: FakeTarget, boiler: MockConfigEntry
) -> None:
    """No timer is attached to the fan, so Timerify's sentences do not know its name,
    and nothing is switched."""
    response = await converse(hass, "turn on the fan for 10 minutes")

    assert reached(response) is None
    assert fake_fan.calls == []


async def test_a_target_that_assist_may_not_control_is_refused(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    expose(hass, TARGET_ID, False)

    response = await converse(hass, "turn on the boiler for 10 minutes")

    assert response.response_type is intent.IntentResponseType.ERROR
    assert response.error_code is intent.IntentResponseErrorCode.NO_VALID_TARGETS
    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "0"


async def test_a_follow_up_can_say_it_after_running_the_timer(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """Running the boiler makes it what "it" means in that conversation."""
    ran = await talk(hass, "turn on the boiler for 10 minutes")

    followed = await talk(hass, "turn it off", conversation_id=ran.conversation_id)

    assert fake_target.calls == [TURN_ON, TURN_OFF], speech(followed.response)
    assert state_of(hass, NUMBER) == "0"


async def test_run_by_voice_on_an_unavailable_target_waits_for_it(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """R10: a boiler out of reach is not off. The timer keeps the wish and the answer
    says it; the boiler is turned on the moment it is back."""
    await fake_target.set_state("unavailable")

    response = await converse(hass, "turn on the boiler for 30 minutes")

    assert reached(response) == RUN
    assert speech(response) == "Boiler runs for 30 minutes, until 09:30."
    assert state_of(hass, NUMBER) == "30"
    assert fake_target.calls == []

    await fake_target.set_state("off")

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, NUMBER) == "30"


async def test_the_slots_of_a_call_are_validated_once(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """The base validates what the agent heard, and hands the handler the result: a
    second pass would be a second place for a rule."""
    validate = intent.IntentHandler.async_validate_slots
    with patch.object(
        intent.IntentHandler,
        "async_validate_slots",
        autospec=True,
        side_effect=validate,
    ) as spy:
        await converse(hass, "turn on the boiler for 45 minutes")
        await converse(hass, "add 5 minutes to the boiler")
        await converse(hass, "stop the boiler timer")

    assert spy.call_count == 3


# --- Turning on with settings ------------------------------------------------------


@pytest.mark.usefixtures("assist")
async def test_run_with_settings_turns_the_ac_on_with_them(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The sentence of the spec, as it is spoken and written: the speech to text
    puts commas in it."""
    await with_voice_settings(hass, setup_target, fake_climate)

    response = await converse(hass, "turn on the AC for an hour, cooling, 24")

    assert reached(response) == RUN
    assert fake_climate.call_data == COOL_24
    assert state_of(hass, AC_NUMBER) == "60"
    assert speech(response) == "AC runs for 1 hour, until 10:00."


PARTS = {
    "hvac": "cooling",
    "temperature": "24 degrees",
    "mode": "fan high",
}
"""What can follow the minutes when turning the air conditioner on, said in words."""


@pytest.mark.usefixtures("assist")
async def test_settings_in_every_order(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """A person says the settings in the order they come to mind; the target gets the
    same calls whichever it is."""
    await with_voice_settings(hass, setup_target, fake_climate)

    for order in itertools.permutations(PARTS):
        text = " ".join(
            ["turn on the AC for 30 minutes", *(PARTS[part] for part in order)]
        )
        fake_climate.call_data.clear()

        response = await converse(hass, text)

        assert reached(response) == RUN, text
        assert fake_climate.call_data == [
            COOL,
            TEMPERATURE_24,
            ("set_fan_mode", {"fan_mode": "high"}),
        ], text
        assert state_of(hass, AC_NUMBER) == "30", text
        await converse(hass, "stop the AC timer")


@pytest.mark.usefixtures("assist")
async def test_all_four_kinds_of_setting_are_understood_in_every_order(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """No device takes all four, so the air conditioner refuses the percentage, but the
    sentence is understood whole: the handler gets each of them."""
    await with_voice_settings(hass, setup_target, fake_climate)
    words = {**PARTS, "percent": "at 40 percent"}

    for order in itertools.permutations(words):
        text = " ".join(
            ["turn on the AC for 30 minutes", *(words[part] for part in order)]
        )

        response = await converse(hass, text)

        assert reached(response) == RUN, text
        assert response.intent is not None
        slots = {key: slot["value"] for key, slot in response.intent.slots.items()}
        assert slots == {
            "name": "AC",
            "minutes": 30,
            "hvac_mode": "cool",
            "temperature": 24,
            "percent": 40,
            "mode": "high",
        }, text


HVAC_WORDS = [
    pytest.param(word, mode, id=f"{mode}-{word}")
    for mode, words in spoken_values("en", LIST_HVAC_MODE).items()
    for word in words
]
"""Every way the shipped sentences say an HVAC mode, with the mode it means."""


@pytest.mark.usefixtures("assist")
@pytest.mark.parametrize(("word", "mode"), HVAC_WORDS)
async def test_every_hvac_word_reaches_its_mode(
    hass: HomeAssistant,
    fake_full_ac: FakeTarget,
    setup_target: SetupTarget,
    word: str,
    mode: str,
) -> None:
    await with_voice_settings(hass, setup_target, fake_full_ac)

    response = await converse(hass, f"turn on the AC for an hour {word}")

    assert reached(response) == RUN, speech(response)
    assert fake_full_ac.call_data == [("set_hvac_mode", {"hvac_mode": mode})]


@pytest.mark.usefixtures("assist")
async def test_hvac_words_are_listed_only_for_supported_modes(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The air conditioner has heat, cool and fan only: a person who says "drying" or
    "auto" gets no guess at what was meant, as they would from a word that is listed
    for a mode that no device has."""
    await with_voice_settings(hass, setup_target, fake_target, fake_climate)

    for language in VOICE_LANGUAGES:
        assert {
            key: set(modes) for key, modes in hvac_words(hass, language).items()
        } == {"cool fan_only heat": {"cool", "heat", "fan_only"}}
    response = await converse(hass, "turn on the AC for an hour drying")
    assert reached(response) != RUN
    assert fake_climate.calls == []


@pytest.mark.usefixtures("assist")
async def test_no_hvac_word_is_a_setting_of_a_target_that_has_no_modes(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """With nothing but a boiler no word for a mode is listed, so "cooling" after the
    minutes is not part of any sentence of Timerify."""
    await with_voice_settings(hass, setup_target, fake_target)

    assert hvac_words(hass, "en") == {}
    response = await converse(hass, "turn on the boiler for an hour cooling")

    assert reached(response) != RUN
    assert fake_target.calls == []


@pytest.mark.usefixtures("assist")
async def test_each_ac_understands_only_its_own_hvac_modes(
    hass: HomeAssistant,
    fake_full_ac: FakeTarget,
    fake_small_ac: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The AC has every mode and the small one only cools and ventilates: each is
    understood with the words for its own modes."""
    await with_voice_settings(hass, setup_target, fake_full_ac, fake_small_ac)

    answers = [
        await converse(hass, "turn on the AC for an hour heating"),
        await converse(hass, "turn on the AC for an hour drying"),
        await converse(hass, "turn on the small AC for an hour cooling"),
        await converse(hass, "turn on the small AC for an hour fan only"),
    ]

    assert [reached(answer) for answer in answers] == [RUN] * 4, [
        speech(answer) for answer in answers
    ]
    assert fake_full_ac.call_data == [
        ("set_hvac_mode", {"hvac_mode": "heat"}),
        ("set_hvac_mode", {"hvac_mode": "dry"}),
    ]
    assert fake_small_ac.call_data == [
        ("set_hvac_mode", {"hvac_mode": "cool"}),
        ("set_hvac_mode", {"hvac_mode": "fan_only"}),
    ]


@pytest.mark.usefixtures("assist")
async def test_a_mode_only_another_ac_has_switches_neither_on(
    hass: HomeAssistant,
    fake_full_ac: FakeTarget,
    fake_small_ac: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The small AC cannot heat, and the AC can. "Heating" after the name of the small
    one is not understood: it is not turned on without the mode, nor is the AC that has
    the mode turned on in its place, and no command is kept."""
    await with_voice_settings(hass, setup_target, fake_full_ac, fake_small_ac)

    response = await converse(hass, "turn on the small AC for an hour heating")

    assert response.response_type is intent.IntentResponseType.ERROR, speech(response)
    assert reached(response) != RUN
    assert fake_small_ac.calls == []
    assert fake_full_ac.calls == []
    assert pending(hass, SMALL_AC_NEXT) == []
    assert pending(hass, AC_NEXT) == []
    assert state_of(hass, SMALL_AC_NUMBER) == state_of(hass, AC_NUMBER) == "0"


@pytest.mark.usefixtures("assist")
async def test_a_thermostat_that_no_mode_is_listed_for_is_still_run_for_a_time(
    hass: HomeAssistant, provide_target: ProvideTarget, setup_target: SetupTarget
) -> None:
    """A thermostat that can only be off has no HVAC mode to be turned on in. It is
    run for a time as any other target is, and no word for a mode is part of its
    sentences."""
    off_only = provide_target(
        SMALL_AC_ID,
        CLIMATE_SERVICES,
        name="Small AC",
        capability_attributes={**AC_ATTRS, "hvac_modes": ["off"]},
        state_attributes={"temperature": 20, "fan_mode": "auto"},
    )
    await with_voice_settings(hass, setup_target, off_only)

    assert hvac_words(hass, "en") == {"": []}
    run = await converse(hass, "turn on the small AC for an hour")
    cooled = await converse(hass, "turn on the small AC for an hour cooling")

    assert reached(run) == RUN, speech(run)
    assert reached(cooled) != RUN
    assert off_only.call_data == [("turn_on", {})]


@pytest.mark.usefixtures("assist")
async def test_russian_hvac_words_are_scoped_per_ac(
    hass: HomeAssistant,
    fake_full_ac: FakeTarget,
    fake_small_ac: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Every Russian word for an HVAC mode, said of the small AC, arrives as the mode it
    means when the small AC has it, and as no HVAC mode otherwise: it is never told to
    take a mode it lacks, and the AC that has the mode is never turned on instead. (The
    word for an automatic fan is also one for the mode `auto`, and is the fan's.)"""
    await with_voice_settings(hass, setup_target, fake_full_ac, fake_small_ac)
    numbers = {"timerify_minutes": 30}
    own_modes = {"cool", "fan_only"}

    for mode, words in spoken_values("ru", LIST_HVAC_MODE).items():
        for word in words:
            texts = samples(
                "ru",
                RUN,
                names=("Small AC",),
                numbers=numbers,
                texts={"timerify_hvac_mode": word},
                absent=("timerify_mode",),
                requiring="climate",
            )
            text = next(text for text in texts if word in text)
            fake_small_ac.call_data.clear()

            response = await converse(hass, text, language="ru")

            slots = {} if response.intent is None else response.intent.slots
            assert ("hvac_mode" in slots) == (mode in own_modes), text
            assert [
                data
                for service, data in fake_small_ac.call_data
                if service == "set_hvac_mode"
            ] == ([{"hvac_mode": mode}] if mode in own_modes else []), text
            assert fake_full_ac.calls == [], text


@pytest.mark.usefixtures("assist")
async def test_auto_is_the_hvac_mode_unless_it_is_asked_for_as_a_fan_mode(
    hass: HomeAssistant, provide_target: ProvideTarget, setup_target: SetupTarget
) -> None:
    """A thermostat with an automatic mode and an automatic fan has one word for both.
    Bare, it is the mode of the thermostat; "fan auto" and "in auto mode" are its
    fan."""
    ac = provide_target(
        AC_ID,
        CLIMATE_SERVICES,
        name="AC",
        capability_attributes={**AC_ATTRS, "hvac_modes": ["off", "heat", "auto"]},
        state_attributes={"temperature": 20, "fan_mode": "auto"},
    )
    await with_voice_settings(hass, setup_target, ac)

    texts = [
        "turn on the AC for an hour auto",
        "turn on the AC for an hour fan auto",
        "turn on the AC for an hour in auto mode",
    ]
    for text in texts:
        await converse(hass, text)

    assert ac.call_data == [
        ("set_hvac_mode", {"hvac_mode": "auto"}),
        ("set_fan_mode", {"fan_mode": "auto"}),
        ("set_fan_mode", {"fan_mode": "auto"}),
    ]


@pytest.mark.usefixtures("assist")
async def test_auto_in_russian_is_the_hvac_mode_unless_it_is_asked_for_as_a_fan_mode(
    hass: HomeAssistant, provide_target: ProvideTarget, setup_target: SetupTarget
) -> None:
    """The word Home Assistant shows in Russian for the automatic fan of a thermostat
    is also a word for its automatic HVAC mode. Bare, with "in mode" or with "mode", it
    is the mode of the thermostat; with "fan" it is the fan."""
    ac = provide_target(
        AC_ID,
        CLIMATE_SERVICES,
        name="AC",
        capability_attributes={**AC_ATTRS, "hvac_modes": ["off", "heat", "auto"]},
        state_attributes={"temperature": 20, "fan_mode": "auto"},
    )
    await with_voice_settings(hass, setup_target, ac)
    word = await word_of(hass, "ru", "entity_component", f"{CLIMATE_FAN_MODE}.auto")
    hvac_words = {w.casefold() for w in spoken_values("ru", LIST_HVAC_MODE)["auto"]}
    assert word.casefold() in hvac_words, "the fan word is no longer an HVAC word"
    hvac_forms = spoken_rule(
        "ru", "timerify_hvac_part", {}, texts={"timerify_hvac_mode": word}
    )
    fan_forms = [
        form
        for form in spoken_rule(
            "ru", "timerify_mode_part", {}, texts={"timerify_mode": word}
        )
        if form not in hvac_forms
    ]
    assert len(fan_forms) == 1
    turn_on = min(
        samples(
            "ru",
            RUN,
            names=("AC",),
            numbers={"timerify_hours": 1},
            absent=SETTING_LISTS,
            admitting="climate",
        ),
        key=len,
    )

    for form in [*hvac_forms, *fan_forms]:
        response = await converse(hass, f"{turn_on} {form}", "ru")
        assert reached(response) == RUN, (form, speech(response))

    assert ac.call_data == [
        ("set_hvac_mode", {"hvac_mode": "auto"}),
        ("set_hvac_mode", {"hvac_mode": "auto"}),
        ("set_hvac_mode", {"hvac_mode": "auto"}),
        ("set_fan_mode", {"fan_mode": "auto"}),
    ]


@pytest.mark.usefixtures("assist")
async def test_auto_is_the_mode_of_the_device_that_has_one(
    hass: HomeAssistant,
    fake_full_ac: FakeTarget,
    fake_humidifier: FakeTarget,
    fake_vent: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A thermostat that has the HVAC mode `auto` is in the house, and a humidifier and
    a fan have a mode and a preset `auto`: the word is the HVAC mode of the thermostat
    and the mode of the other two, which have no HVAC mode to be refused for."""
    await with_voice_settings(
        hass, setup_target, fake_full_ac, fake_humidifier, fake_vent
    )

    answers = [
        await converse(hass, "turn on the AC for an hour auto"),
        await converse(hass, "turn on the humidifier for an hour auto"),
        await converse(hass, "turn on the humidifier for 10 minutes auto mode"),
        await converse(hass, "turn on the vent for an hour auto"),
    ]

    assert [answer.response_type for answer in answers] == [
        intent.IntentResponseType.ACTION_DONE
    ] * 4, [speech(answer) for answer in answers]
    assert fake_full_ac.call_data == [("set_hvac_mode", {"hvac_mode": "auto"})]
    assert fake_humidifier.call_data == [
        ("turn_on", {}),
        ("set_mode", {"mode": "auto"}),
        ("set_mode", {"mode": "auto"}),
    ]
    assert fake_vent.call_data == [("turn_on", {"preset_mode": "auto"})]


@pytest.mark.usefixtures("assist")
async def test_a_temperature_is_said_only_of_a_target_that_has_one(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_full_ac: FakeTarget,
    fake_tank: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A boiler has no temperature to be turned on at, so a temperature after the time
    is not understood, and the words for an HVAC mode are the thermostat's alone. The
    water heater has a temperature but no HVAC mode."""
    await with_voice_settings(hass, setup_target, fake_target, fake_full_ac, fake_tank)

    for text in (
        "turn on the boiler for an hour at 55 degrees",
        "turn on the tank for an hour cooling",
    ):
        assert reached(await converse(hass, text)) != RUN, text
    tank = await converse(hass, "turn on the tank for an hour at 55 degrees")

    assert fake_target.calls == []
    assert reached(tank) == RUN
    assert fake_tank.call_data == [
        ("turn_on", {}),
        ("set_temperature", {"temperature": 55.0}),
    ]


AND_WORDS = {"en": "and", "ru": "\N{CYRILLIC SMALL LETTER I}"}
"""The word that joins the hours to the minutes, in each language."""


@pytest.mark.parametrize("language", VOICE_LANGUAGES)
@pytest.mark.parametrize(
    ("name", "domain"), [("AC", "climate"), ("Tank", "water_heater")]
)
def test_hours_and_a_number_are_read_one_way_where_a_temperature_is_said(
    language: str, name: str, domain: str
) -> None:
    """A thermostat or a water heater has one reading of each phrase, not a tie that
    the order of the alternatives breaks: the number right after the hours is the
    temperature, and the number after the word for "and" is the minutes."""
    hours = samples(
        language,
        RUN,
        names=(name,),
        requiring=domain,
        numbers={"timerify_hours": 1},
        absent=SETTING_LISTS,
    )
    assert hours

    for text in hours:
        bare = readings(language, f"{text} 30", name=name, domain=domain)
        joined = readings(
            language, f"{text} {AND_WORDS[language]} 30", name=name, domain=domain
        )

        assert bare == [{"name": name, "hours": 1, "temperature": 30}], text
        assert joined == [{"name": name, "hours": 1, "minutes": 30}], text


@pytest.mark.usefixtures("assist")
async def test_for_an_hour_and_a_bare_number_stays_a_thermostat_s_temperature(
    hass: HomeAssistant, fake_full_ac: FakeTarget, setup_target: SetupTarget
) -> None:
    """A thermostat reads the bare number after the hours as its temperature, and as
    nothing else, so the air conditioner runs for the hour and is set at 30 degrees."""
    await with_voice_settings(hass, setup_target, fake_full_ac)
    text = "turn on the AC for 1 hour 30"
    assert readings("en", text, name="AC", domain="climate") == [
        {"name": "AC", "hours": 1, "temperature": 30}
    ]

    response = await converse(hass, text)

    assert reached(response) == RUN, speech(response)
    assert state_of(hass, AC_NUMBER) == "60"
    assert fake_full_ac.call_data == [
        ("turn_on", {}),
        ("set_temperature", {"temperature": 30.0}),
    ]


@pytest.mark.usefixtures("assist")
@pytest.mark.parametrize(
    ("text", "calls"),
    [
        ("turn on the AC for 1 hour and 30", [("turn_on", {})]),
        (
            "turn on the AC for 1 hour and 30 at 24",
            [("turn_on", {}), ("set_temperature", {"temperature": 24.0})],
        ),
    ],
)
async def test_for_an_hour_and_30_is_90_minutes_to_a_thermostat(
    hass: HomeAssistant,
    fake_full_ac: FakeTarget,
    setup_target: SetupTarget,
    text: str,
    calls: list[tuple[str, dict[str, object]]],
) -> None:
    """With "and" before it the number is minutes, also for a thermostat: a person who
    wants an hour at 30 degrees leaves "and" out."""
    await with_voice_settings(hass, setup_target, fake_full_ac)

    response = await converse(hass, text)

    assert reached(response) == RUN, speech(response)
    assert state_of(hass, AC_NUMBER) == "90"
    assert fake_full_ac.call_data == calls


@pytest.mark.usefixtures("assist")
async def test_for_an_hour_and_a_bare_number_stays_a_water_heater_s_temperature(
    hass: HomeAssistant, fake_tank: FakeTarget, setup_target: SetupTarget
) -> None:
    """A water heater reads the bare number after the hours as its temperature, as a
    thermostat does, and "and" before the number makes it minutes."""
    await with_voice_settings(hass, setup_target, fake_tank)
    text = "turn on the tank for 1 hour 30"
    assert readings("en", text, name="Tank", domain="water_heater") == [
        {"name": "Tank", "hours": 1, "temperature": 30}
    ]

    response = await converse(hass, text)

    assert reached(response) == RUN, speech(response)
    assert state_of(hass, TANK_NUMBER) == "60"
    assert fake_tank.call_data == [
        ("turn_on", {}),
        ("set_temperature", {"temperature": 30.0}),
    ]

    await set_number(hass, TANK_NUMBER, 0)
    fake_tank.call_data.clear()
    response = await converse(hass, "turn on the tank for 1 hour and 30")

    assert reached(response) == RUN, speech(response)
    assert state_of(hass, TANK_NUMBER) == "90"
    assert fake_tank.call_data == [("turn_on", {})]


@pytest.mark.parametrize("hours", [1, 2, 5])
async def test_russian_hours_and_bare_minutes_run_a_switch_for_90_minutes(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry, hours: int
) -> None:
    """Every form of the word for hours that the Russian sentences take after 1, 2 or 5,
    followed by 30 with no word for the minutes, with or without the word for "and",
    runs the boiler for that many hours and half an hour, in each sampled way to ask.

    The sampler takes the first alternative of a rule, which is the hours alone, so the
    minutes, and the other forms of the hours, are put in the sampled texts."""
    forms = spoken_rule("ru", "timerify_hours_part", {"timerify_hours": hours})
    texts: list[str] = []
    for sampled in samples(
        "ru", RUN, numbers={"timerify_hours": hours}, absent=SETTING_LISTS
    ):
        (ending,) = [form for form in forms if sampled.endswith(form)]
        asked = sampled.removesuffix(ending)
        texts += [
            f"{asked}{form} {more}"
            for form in forms
            for more in ("30", f"{AND_WORDS['ru']} 30")
        ]
    assert len(forms) == 3
    assert texts

    for text in dict.fromkeys(texts):
        response = await converse(hass, text, language="ru")

        assert reached(response) == RUN, text
        assert state_of(hass, NUMBER) == str(hours * 60 + 30), text
        await set_number(hass, NUMBER, 0)


HOT_WATER = [("turn_on", {}), ("set_temperature", {"temperature": 120.0})]
"""The calls that turn the water heater on, at 120 degrees."""


@pytest.mark.usefixtures("assist")
@pytest.mark.parametrize(
    ("text", "temperature"),
    [
        ("turn on the tank for an hour at 120 degrees", 120.0),
        ("turn on the tank for an hour 120", 120.0),
        ("turn on the tank for an hour at 140.5", 140.5),
        ("turn on the tank for an hour at one hundred twenty degrees", 120.0),
        ("turn on the tank for an hour at two hundred fifty degrees", 250.0),
    ],
)
async def test_a_fahrenheit_water_heater_is_given_its_temperature_by_voice(
    hass: HomeAssistant,
    fake_fahrenheit_tank: FakeTarget,
    setup_target: SetupTarget,
    text: str,
    temperature: float,
) -> None:
    """A water heater that counts in Fahrenheit is set at 110 to 140 degrees, which the
    sentences used to refuse as not understood (they ended at 100); the controller still
    judges the number against what this water heater takes."""
    await with_voice_settings(hass, setup_target, fake_fahrenheit_tank)

    response = await converse(hass, text)

    assert reached(response) == RUN, speech(response)
    if temperature <= 150:
        assert fake_fahrenheit_tank.call_data == [
            ("turn_on", {}),
            ("set_temperature", {"temperature": temperature}),
        ]
    else:
        assert refusal_of(response) == (
            "250 is not a valid Temperature: it must be between 100 and 150."
        )
        assert fake_fahrenheit_tank.call_data == []


@pytest.mark.usefixtures("assist")
async def test_a_temperature_beyond_what_can_be_said_is_not_understood(
    hass: HomeAssistant,
    fake_fahrenheit_tank: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The bound is finite: the hottest water a heater makes is below the boiling
    point, and a number past 250 is no temperature."""
    await with_voice_settings(hass, setup_target, fake_fahrenheit_tank)

    response = await converse(hass, "turn on the tank for an hour at 251 degrees")

    assert reached(response) != RUN
    assert fake_fahrenheit_tank.call_data == []


@pytest.mark.usefixtures("assist")
async def test_a_russian_speaker_gives_a_fahrenheit_water_heater_its_temperature(
    hass: HomeAssistant,
    fake_fahrenheit_tank: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The shipped Russian sentences take the same range: every way of asking in them,
    with 120 degrees, turns the water heater on at 120."""
    await with_voice_settings(hass, setup_target, fake_fahrenheit_tank)
    texts = samples(
        "ru",
        RUN,
        names=("Tank",),
        numbers={"timerify_minutes": 60, "timerify_temperature": 120},
        absent=SETTING_LISTS,
    )
    said = [text for text in texts if "120" in text]
    assert said

    for text in said:
        fake_fahrenheit_tank.call_data.clear()

        response = await converse(hass, text, language="ru")

        assert reached(response) == RUN, text
        assert fake_fahrenheit_tank.call_data == HOT_WATER, text
        await converse(hass, "stop the tank timer")


async def test_the_manual_installation_knows_the_hvac_words_but_not_the_modes(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """The files that are copied by hand list every word for an HVAC mode, since only
    the Voice settings entry knows which modes the devices have; the modes of the
    devices themselves are not in them, so a fan mode is not a sentence. The name of
    the thermostat is listed with its domain, which is what the words need."""
    await setup_target(target=AC_ID)
    await copy_sentences(hass, ["AC"], {"AC": "climate"})

    cooled = await converse(hass, "turn on the AC for an hour cooling 24")
    fanned = await converse(hass, "turn on the AC for an hour fan high")

    assert reached(cooled) == RUN
    assert fake_climate.call_data == COOL_24
    assert reached(fanned) != RUN


async def test_a_hand_listed_ac_keeps_every_hvac_word(
    hass: HomeAssistant,
    fake_full_ac: FakeTarget,
    fake_small_ac: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """The files that are copied by hand cannot tell the modes of one thermostat from
    those of another, so every thermostat takes every word: the AC is turned on drying,
    and the small AC, which lacks heating, is understood and refuses it."""
    await setup_target(target=fake_full_ac.entity_id)
    await setup_target(target=fake_small_ac.entity_id)
    await copy_sentences(
        hass, ["AC", "Small AC"], {"AC": "climate", "Small AC": "climate"}
    )

    dried = await converse(hass, "turn on the AC for an hour drying")
    heated = await converse(hass, "turn on the small AC for an hour heating")

    assert reached(dried) == RUN, speech(dried)
    assert fake_full_ac.call_data == [("set_hvac_mode", {"hvac_mode": "dry"})]
    assert reached(heated) == RUN
    assert refusal_of(heated) == (
        "heat is not a valid HVAC mode: it must be one of cool, fan_only."
    )
    assert fake_small_ac.calls == []


async def test_a_name_listed_by_hand_without_its_domain_has_no_hvac_words(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """The words for an HVAC mode and a temperature are for the targets that have
    them, which the sentences know from the domain a name is listed with. A name
    listed without one is run for a time and turned on with a percentage or a mode, and
    that is all."""
    await setup_target(target=AC_ID)
    await copy_sentences(hass, ["AC"])

    cooled = await converse(hass, "turn on the AC for an hour cooling 24")
    run = await converse(hass, "turn on the AC for an hour")

    assert reached(cooled) != RUN
    assert reached(run) == RUN
    assert fake_climate.call_data == [("turn_on", {})]


@pytest.mark.usefixtures("assist")
async def test_percent_means_the_targets_own_setting(
    hass: HomeAssistant,
    fake_lamp: FakeTarget,
    fake_vent: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """ "At 40 percent" is the brightness of a lamp and the speed of a fan: the same
    words, each the target's own setting."""
    await with_voice_settings(hass, setup_target, fake_lamp, fake_vent)

    await converse(hass, "turn on the lamp for 30 minutes at 40 percent")
    await converse(hass, "turn on the vent for 30 minutes at 40 percent")

    assert fake_lamp.call_data == [("turn_on", {"brightness_pct": 40.0})]
    assert fake_vent.call_data == [("turn_on", {"percentage": 40})]
    assert state_of(hass, LAMP_NUMBER) == state_of(hass, VENT_NUMBER) == "30"


@pytest.mark.usefixtures("assist")
async def test_mode_means_the_targets_own_setting(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    fake_vent: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """ "Fan high" is the fan mode of the air conditioner and "in eco mode" the preset
    of the fan; the words for them are the strings the devices themselves list."""
    await with_voice_settings(hass, setup_target, fake_climate, fake_vent)

    await converse(hass, "turn on the AC for 30 minutes fan high")
    await converse(hass, "turn on the vent for 30 minutes in eco mode")

    assert fake_climate.call_data[-1] == ("set_fan_mode", {"fan_mode": "high"})
    assert fake_vent.call_data == [("turn_on", {"preset_mode": "eco"})]
    assert [value["out"] for value in listed(hass, "en", LIST_MODE)] == [
        "auto",
        "eco",
        "high",
        "low",
        "sleep",
    ]


@pytest.mark.usefixtures("assist")
async def test_a_mode_the_devices_do_not_have_is_not_a_sentence(
    hass: HomeAssistant, fake_vent: FakeTarget, setup_target: SetupTarget
) -> None:
    await with_voice_settings(hass, setup_target, fake_vent)

    response = await converse(hass, "turn on the vent for 30 minutes in turbo mode")

    assert reached(response) != RUN
    assert fake_vent.calls == []


async def test_setting_the_target_cannot_take_is_refused(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """A boiler has no brightness and no speed: it says so, and nothing is switched,
    not even for the minutes."""
    response = await converse(hass, "turn on the boiler for an hour at 40 percent")

    assert reached(response) == RUN
    assert refusal_of(response) == "Boiler cannot be turned on with that setting."
    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "0"


async def test_a_mode_of_the_air_conditioner_it_does_not_have_is_refused(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """With the sentences installed the manual way every word for a mode is there,
    "heat and cool" too. The air conditioner has no such mode, and the refusal names the
    setting as the services do, and the modes it has."""
    await setup_target(target=AC_ID)
    await copy_sentences(hass, ["AC"], {"AC": "climate"})

    response = await converse(hass, "turn on the AC for an hour heat and cool")

    assert reached(response) == RUN
    assert refusal_of(response) == (
        "heat_cool is not a valid HVAC mode: it must be one of heat, cool, fan_only."
    )
    assert fake_climate.calls == []
    assert state_of(hass, AC_NUMBER) == "0"


# --- Adding time -------------------------------------------------------------------


async def test_add_time_extends_a_running_timer(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """R7: five minutes left, thirty more."""
    await set_number(hass, NUMBER, 5)

    response = await converse(hass, "30 more minutes on the boiler")

    assert reached(response) == ADD_TIME
    assert state_of(hass, NUMBER) == "35"
    assert fake_target.calls == [TURN_ON]
    assert speech(response) == "Boiler runs for 35 minutes, until 09:35."


@pytest.mark.parametrize(
    ("text", "minutes"),
    [
        ("add 20 minutes to the boiler", 20),
        ("add an hour to the boiler", 60),
        ("add 2 more hours to the boiler", 120),
        ("30 minutes more on the boiler", 30),
        ("an hour more on the boiler", 60),
        ("2 more hours on the boiler", 120),
        ("extend the boiler by half an hour", 30),
        ("extend the boiler by 1 hour and 15 minutes", 75),
    ],
)
async def test_add_time_phrasings(
    hass: HomeAssistant, boiler: MockConfigEntry, text: str, minutes: int
) -> None:
    response = await converse(hass, text)

    assert reached(response) == ADD_TIME, speech(response)
    assert state_of(hass, NUMBER) == str(minutes)


async def test_add_time_on_an_idle_timer_starts_it(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    response = await converse(hass, "add 20 minutes to the boiler")

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "20"
    assert speech(response) == "Boiler runs for 20 minutes, until 09:20."


async def test_add_an_hour_and_bare_minutes_adds_90_minutes(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    response = await converse(hass, "add 1 hour 30 to the boiler")

    assert reached(response) == ADD_TIME, speech(response)
    assert state_of(hass, NUMBER) == "90"


async def test_add_time_past_a_day_runs_a_day(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """A timer never runs for more than a day from now: asking for more is not
    refused, it gets the most there is."""
    await set_number(hass, NUMBER, 1430)

    response = await converse(hass, "add 30 minutes to the boiler")

    assert state_of(hass, NUMBER) == str(MAX_MINUTES)
    assert speech(response) == "Boiler runs for 24 hours, until 09:00 tomorrow."


async def test_add_thirty_hours_runs_a_day(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    """Asking for more than a day is not refused: a timer gets the most there is, and
    the answer says when that ends."""
    await set_number(hass, NUMBER, 600)

    response = await converse(hass, "add 30 hours to the boiler")

    assert reached(response) == ADD_TIME
    assert state_of(hass, NUMBER) == str(MAX_MINUTES)
    assert speech(response) == "Boiler runs for 24 hours, until 09:00 tomorrow."


@pytest.mark.parametrize("numbers", OVER_A_DAY)
@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_adding_more_than_a_day_runs_a_day_in_the_users_language(
    hass: HomeAssistant,
    boiler: MockConfigEntry,
    language: str,
    numbers: dict[str, int],
) -> None:
    """Every way of saying it reaches the timer and gets the answer of a run for a day
    (the clamp of the first phase), said in the language of the request."""
    a_day = samples(language, RUN, numbers={"timerify_hours": 24}, absent=SETTING_LISTS)
    reference = speech(await converse(hass, a_day[0], language=language))
    texts = samples(language, ADD_TIME, numbers=numbers, absent=SETTING_LISTS)
    assert texts

    for text in texts:
        await set_number(hass, NUMBER, 600)

        response = await converse(hass, text, language=language)

        assert reached(response) == ADD_TIME, text
        assert response.response_type is intent.IntentResponseType.ACTION_DONE, text
        assert state_of(hass, NUMBER) == str(MAX_MINUTES), text
        assert speech(response) == reference, text


@pytest.mark.parametrize(
    "numbers",
    [{"timerify_hours": 169}, {"timerify_long_minutes": 10081}],
    ids=["169-hours", "10081-minutes"],
)
@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_a_count_beyond_a_week_is_not_understood(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    language: str,
    numbers: dict[str, int],
) -> None:
    """The sentences are generous but finite: past a week they match nothing of
    Timerify's, and nothing is switched."""
    texts = samples(language, RUN, numbers=numbers, absent=SETTING_LISTS)
    assert texts

    for text in texts:
        response = await converse(hass, text, language=language)

        assert reached(response) not in (RUN, ADD_TIME), text
    assert fake_target.calls == []


# --- Stopping ----------------------------------------------------------------------


async def test_stop_turns_the_target_off(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """R2: an explicit stop is a countdown of zero, and the boiler goes off."""
    await set_number(hass, NUMBER, 30)

    response = await converse(hass, "stop the boiler timer")

    assert reached(response) == STOP
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, NUMBER) == "0"
    assert speech(response) == "Boiler is off."


@pytest.mark.parametrize(
    "text",
    [
        "stop the boiler timer",
        "cancel the boiler timer",
        "stop the timer on the boiler",
        "cancel the timer of the boiler",
        "Stop the timer on the Boiler.",
    ],
)
async def test_stop_phrasings(
    hass: HomeAssistant, boiler: MockConfigEntry, text: str
) -> None:
    await set_number(hass, NUMBER, 30)

    response = await converse(hass, text)

    assert reached(response) == STOP, speech(response)
    assert state_of(hass, NUMBER) == "0"


async def test_stopping_an_idle_timer_changes_nothing_more(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    response = await converse(hass, "stop the boiler timer")

    assert response.response_type is intent.IntentResponseType.ACTION_DONE
    assert fake_target.calls == []
    assert speech(response) == "Boiler is off."


async def test_stopping_an_unavailable_target_is_answered_with_the_wish(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """R10: a boiler out of reach is not known to be off, but the answer to a command
    gives the wish it set, as it does for a run: the boiler is off, nothing is sent to
    it while it is away, and it is turned off the moment it is back."""
    await set_number(hass, NUMBER, 30)
    await fake_target.set_state("unavailable")

    response = await converse(hass, "stop the boiler timer")

    assert reached(response) == STOP
    assert speech(response) == "Boiler is off."
    assert state_of(hass, NUMBER) == "0"
    assert fake_target.calls == [TURN_ON]

    await fake_target.set_state("on")

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"


# --- The rules of the timer hold after a voice command -----------------------------


async def test_voice_change_ends_schedule_alignment(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """S3: ten past seven, five minutes before the window ends, the user asks for half
    an hour more. The boiler runs to quarter to eight whatever the interval is edited
    to, as when the same is done with a button."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await copy_sentences(hass, ["Boiler"])
    interval = await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:10"))

    await converse(hass, "30 more minutes on the boiler")
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:45")
    await edit_interval(hass, entry, interval, end="07:00")

    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:45")
    await advance_to(hass, freezer, local(SUNDAY, "07:45"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_strict_manual_rules_still_apply_after_voice(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """R3 and R4: a boiler that is run by voice and then turned off at the wall has no
    countdown any more, and turned on at the wall again it runs for its default
    duration, as it does after a button."""
    await converse(hass, "turn on the boiler for 10 minutes")
    assert state_of(hass, NUMBER) == "10"

    await fake_target.set_state("off")
    assert state_of(hass, NUMBER) == "0"

    await fake_target.set_state("on")
    assert state_of(hass, NUMBER) == "45"


# --- What the answer says when the device is slow to report ------------------------


async def test_the_answer_says_what_was_asked_before_the_device_reports(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """A device that reports a command a while after it took it still shows its old
    state when the timer has answered: the answer is about what was asked, not about the
    last thing the device said."""
    await converse(hass, "turn on the boiler for 30 minutes")
    fake_target.report_next_call_late()

    stopped = await converse(hass, "stop the boiler timer")

    assert fake_target.state == "on"
    assert speech(stopped) == "Boiler is off."
    await fake_target.report_late()
    assert fake_target.state == "off"
    asked = await converse(hass, "how long is left on the boiler")
    assert speech(asked) == "Boiler is off and has no timer."


# --- Russian -----------------------------------------------------------------------


@pytest.mark.parametrize("intent_type", [RUN, ADD_TIME, STOP])
async def test_russian_sentences_reach_their_intent(
    hass: HomeAssistant, boiler: MockConfigEntry, intent_type: str
) -> None:
    """Every Russian way to ask, as the sentence files give them, reaches the handler
    with the name of the target and the time that was said."""
    texts = samples(
        "ru",
        intent_type,
        numbers={"timerify_hours": 2, "timerify_minutes": 30},
        absent=SETTING_LISTS,
    )
    assert texts

    for text in texts:
        response = await converse(hass, text, language="ru")

        assert reached(response) == intent_type, text
        assert response.response_type is intent.IntentResponseType.ACTION_DONE, text
        assert response.intent is not None
        slots = {key: slot["value"] for key, slot in response.intent.slots.items()}
        assert slots["name"] == "Boiler", text
        if intent_type != STOP:
            assert slots.get("hours", 2) == 2, text
            assert slots.get("minutes", 30) in (30, 60, 90), text
            assert {"hours", "minutes"} & slots.keys(), text


async def run_each_count(
    hass: HomeAssistant, language: str, count: int, minutes_each: int
) -> str:
    """What the answer says after the timer is run for `count` units of `minutes_each`
    minutes, said in `language`."""
    unit = "timerify_hours" if minutes_each == 60 else "timerify_minutes"
    text = samples(language, RUN, numbers={unit: count}, absent=SETTING_LISTS)[0]
    return speech(await converse(hass, text, language))


@pytest.mark.parametrize(
    "classes",
    [
        pytest.param(MINUTE_CLASSES, id="minutes"),
        pytest.param(HOUR_CLASSES, id="hours"),
    ],
)
@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_the_answer_to_a_run_follows_the_plural_rules(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    boiler: MockConfigEntry,
    language: str,
    classes: PluralClasses,
) -> None:
    """Russian says a count three ways (one, few, many), English two; the tests prove
    the split, not which word each class takes."""

    async def say(count: int, minutes_each: int) -> str:
        return await run_each_count(hass, language, count, minutes_each)

    await assert_one_form_per_class(hass, freezer, language, classes, say)


@pytest.mark.usefixtures("assist")
async def test_russian_words_for_a_mode_reach_it(
    hass: HomeAssistant, fake_full_ac: FakeTarget, setup_target: SetupTarget
) -> None:
    """Every Russian word for an HVAC mode, in a sentence that has every kind of
    setting, arrives as the mode it means."""
    await with_voice_settings(hass, setup_target, fake_full_ac)
    numbers = {
        "timerify_minutes": 30,
        "timerify_temperature": 24,
        "timerify_percent": 40,
    }

    for mode, words in spoken_values("ru", LIST_HVAC_MODE).items():
        for word in words:
            texts = samples(
                "ru",
                RUN,
                names=("AC",),
                numbers=numbers,
                texts={"timerify_hvac_mode": word, "timerify_mode": "high"},
            )
            text = next(text for text in texts if word in text)
            response = await converse(hass, text, language="ru")

            assert reached(response) == RUN, text
            assert response.intent is not None
            assert response.intent.slots["hvac_mode"]["value"] == mode, text


@pytest.mark.parametrize(
    ("language", "spoken_in"),
    [("ru-RU", "ru"), ("en-GB", "en"), ("en", "en"), ("ru", "ru")],
)
async def test_regional_language_answers_in_its_language(
    hass: HomeAssistant, boiler: MockConfigEntry, language: str, spoken_in: str
) -> None:
    """A refusal is the text of the translation of the language, whatever the region of
    the request is."""
    text = samples(
        spoken_in,
        RUN,
        numbers={"timerify_hours": 24, "timerify_minutes": 30},
        absent=SETTING_LISTS,
    )[0]

    response = await converse(hass, text, language=language)

    assert reached(response) == RUN
    assert refusal_of(response) == translated(
        spoken_in, "exceptions", "duration_out_of_range", "message"
    ).format(max_hours="24")


# --- Through an LLM's tools --------------------------------------------------------


async def test_llm_run_add_and_stop(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The agent runs the boiler for 45 minutes, adds half an hour and stops it, and
    each time is told how the timer stands."""
    api = await assist_api(hass)

    ran = await call_tool(api, "timerify__run", {"name": "Boiler", "minutes": 45})
    assert ran["speech_slots"]["state"] == "counting"
    assert ran["speech_slots"]["left_total"] == 45
    assert ran["speech_slots"]["ends_at"] == "09:45"

    added = await call_tool(
        api, "timerify__add_time", {"name": "Boiler", "minutes": 30}
    )
    assert added["speech_slots"]["left_total"] == 75

    stopped = await call_tool(api, "timerify__stop", {"name": "Boiler"})
    assert stopped["speech_slots"]["state"] == "off"
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, NUMBER) == "0"


async def test_llm_stop_on_an_unavailable_target_tells_the_agent_it_is_unavailable(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """The agent is told the boiler is out of reach, so that it can say so: the spoken
    answer to the same stop says the boiler is off, which is the wish it set."""
    await set_number(hass, NUMBER, 30)
    await fake_target.set_state("unavailable")
    api = await assist_api(hass)

    stopped = await call_tool(api, "timerify__stop", {"name": "Boiler"})

    assert stopped["speech_slots"]["state"] == "unavailable"
    assert stopped["speech_slots"]["left_total"] == 0
    assert fake_target.calls == [TURN_ON]

    await fake_target.set_state("on")

    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_llm_run_takes_hours_and_minutes_together(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    api = await assist_api(hass)

    ran = await call_tool(
        api, "timerify__run", {"name": "Boiler", "hours": 1, "minutes": 30}
    )

    assert ran["speech_slots"]["left_total"] == 90


async def test_llm_run_without_a_duration_is_the_open_run(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """R9: in loose mode the boiler is turned on with no countdown; in strict mode
    the same command runs it for its default duration."""
    await setup_target(mode="loose")
    api = await assist_api(hass)

    ran = await call_tool(api, "timerify__run", {"name": "Boiler"})

    assert ran["speech_slots"]["state"] == "open"
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "0"


async def test_llm_run_on_an_unavailable_target_waits_for_it(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    """R10, through a tool: the agent is told the boiler runs for the time it asked
    for, and the boiler is turned on when it is back."""
    api = await assist_api(hass)
    await fake_target.set_state("unavailable")

    ran = await call_tool(api, "timerify__run", {"name": "Boiler", "minutes": 30})

    assert ran["speech_slots"]["state"] == "counting"
    assert ran["speech_slots"]["left_total"] == 30
    assert fake_target.calls == []

    await fake_target.set_state("off")

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, NUMBER) == "30"


async def test_llm_run_without_a_duration_runs_the_default_in_strict_mode(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    api = await assist_api(hass)

    ran = await call_tool(api, "timerify__run", {"name": "Boiler"})

    assert ran["speech_slots"]["left_total"] == 45


async def test_llm_run_with_settings(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    fake_lamp: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """A thermostat is asked for a mode and a temperature by name, a lamp for a
    percentage by the meaning it has."""
    await setup_target(target=AC_ID)
    await setup_target(target=fake_lamp.entity_id)
    api = await assist_api(hass)

    await call_tool(
        api,
        "timerify__run",
        {"name": "AC", "hvac_mode": "cool", "temperature": 24, "hours": 1},
    )
    await call_tool(
        api, "timerify__run", {"name": "Lamp", "percent": 40, "minutes": 10}
    )

    assert fake_climate.call_data == COOL_24
    assert state_of(hass, AC_NUMBER) == "60"
    assert fake_lamp.call_data == [("turn_on", {"brightness_pct": 40})]


async def test_llm_a_setting_by_its_name_wins_over_the_same_one_by_its_meaning(
    hass: HomeAssistant,
    fake_vent: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """An agent that says both "percent" and the fan's own "percentage" is taken at its
    word for the specific one."""
    await setup_target(target=fake_vent.entity_id)
    api = await assist_api(hass)

    await call_tool(
        api,
        "timerify__run",
        {"name": "Vent", "percent": 30, "percentage": 60, "minutes": 10},
    )

    assert fake_vent.call_data == [("turn_on", {"percentage": 60})]


async def test_llm_a_meaning_the_target_has_no_setting_for_is_refused(
    hass: HomeAssistant, fake_target: FakeTarget, boiler: MockConfigEntry
) -> None:
    api = await assist_api(hass)

    data = await call_tool(
        api, "timerify__run", {"name": "Boiler", "mode": "eco", "minutes": 10}
    )

    assert data["response_type"] == "error"
    assert data["speech"]["plain"]["speech"] == (
        "Boiler cannot be turned on with that setting."
    )
    assert fake_target.calls == []


@pytest.mark.parametrize(
    "args",
    [{"minutes": 2.5}, {"minutes": True}, {"minutes": -5}, {"hours": 0.5}],
    ids=["fraction", "boolean", "negative", "half an hour"],
)
async def test_llm_duration_must_be_a_whole_number(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    args: dict[str, object],
) -> None:
    api = await assist_api(hass)

    with pytest.raises(intent.InvalidSlotInfo):
        await call_tool(api, "timerify__run", {"name": "Boiler", **args})

    assert fake_target.calls == []
    assert state_of(hass, NUMBER) == "0"


@pytest.mark.parametrize(
    "args",
    [{"minutes": 1441}, {"minutes": 0}, {"hours": 25}, {"hours": 24, "minutes": 1}],
)
async def test_llm_duration_out_of_range_is_refused(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    args: dict[str, int],
) -> None:
    """The tool is handed no range to check: the timer judges the duration, and the
    refusal tells the agent what is allowed."""
    api = await assist_api(hass)

    data = await call_tool(api, "timerify__run", {"name": "Boiler", **args})

    assert data["response_type"] == "error"
    assert data["speech"]["plain"]["speech"] == "A timer runs for 1 min to 24 h."
    assert fake_target.calls == []


@pytest.mark.parametrize(
    "args",
    [
        {"hours": 10**9},
        {"minutes": 10**15},
        {"hours": 10**30},
        {"hours": 10**9, "minutes": 10**15},
    ],
    ids=["billion-hours", "quadrillion-minutes", "nonillion-hours", "both"],
)
async def test_llm_add_time_of_an_absurd_count_runs_a_day(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    args: dict[str, int],
) -> None:
    """An agent that asks for more time than there is gets what a count of 30 hours
    gets: the timer runs for a day, and it is told so. It is no failure."""
    api = await assist_api(hass)

    added = await call_tool(api, "timerify__add_time", {"name": "Boiler", **args})

    assert added["response_type"] == "action_done"
    assert added["speech_slots"]["left_total"] == MAX_MINUTES
    assert state_of(hass, NUMBER) == str(MAX_MINUTES)
    assert fake_target.calls == [TURN_ON]


@pytest.mark.parametrize(
    "args", [{}, {"minutes": 0}, {"hours": 0}], ids=["nothing", "minutes", "hours"]
)
@pytest.mark.parametrize("language", ["en", "ru"])
async def test_llm_add_time_without_a_time_is_refused(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    boiler: MockConfigEntry,
    language: str,
    args: dict[str, int],
) -> None:
    """There is nothing to add: the boiler is not started for no time, and the refusal
    says what is missing, in the language of the request."""
    api = await assist_api(hass, language)

    data = await call_tool(api, "timerify__add_time", {"name": "Boiler", **args})

    assert data["response_type"] == "error"
    assert data["speech"]["plain"]["speech"] == translated(
        language, "exceptions", "no_time_to_add", "message"
    )
    assert fake_target.calls == []


async def test_the_refusal_to_add_no_time_says_how_much_to_add(
    hass: HomeAssistant, boiler: MockConfigEntry
) -> None:
    api = await assist_api(hass)

    data = await call_tool(api, "timerify__add_time", {"name": "Boiler"})

    assert data["speech"]["plain"]["speech"] == "Say how much time to add."


async def test_llm_boolean_setting_is_refused(
    hass: HomeAssistant,
    fake_lamp: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """`true` is a number to Python, a brightness of 1 percent; to an agent it is a
    slip, and the lamp stays off. The refusal shows it as the word the agent wrote."""
    await setup_target(target=fake_lamp.entity_id)
    api = await assist_api(hass)

    data = await call_tool(
        api, "timerify__run", {"name": "Lamp", "brightness_pct": True, "minutes": 10}
    )

    assert data["response_type"] == "error"
    assert data["speech"]["plain"]["speech"] == (
        "true is not a valid Brightness: it must be between 1 and 100."
    )
    assert fake_lamp.calls == []


async def test_llm_fraction_of_a_speed_is_refused(
    hass: HomeAssistant,
    fake_vent: FakeTarget,
    assist: None,
    setup_target: SetupTarget,
) -> None:
    """A fan runs at 50 percent or at 51, never at 50.5."""
    await setup_target(target=fake_vent.entity_id)
    api = await assist_api(hass)

    data = await call_tool(
        api, "timerify__run", {"name": "Vent", "percent": 50.5, "minutes": 10}
    )

    assert data["response_type"] == "error"
    assert fake_vent.calls == []


@pytest.mark.parametrize(
    ("language", "spoken_in"),
    [
        ("en", "en"),
        ("ru", "ru"),
        ("ru-RU", "ru"),
        ("*", "en"),
        ("de", "en"),
        (None, "en"),
    ],
)
async def test_llm_error_text_follows_the_request_language(
    hass: HomeAssistant,
    boiler: MockConfigEntry,
    language: str | None,
    spoken_in: str,
) -> None:
    """A refusal is text the agent may read out: it is in the language of the request,
    and in English for the wildcard of an MCP client and a language Timerify has no
    texts for."""
    api = await assist_api(hass, language)

    data = await call_tool(api, "timerify__run", {"name": "Boiler", "minutes": 1441})

    assert data["speech"]["plain"]["speech"] == translated(
        spoken_in, "exceptions", "duration_out_of_range", "message"
    ).format(max_hours="24")


# --- The slots ---------------------------------------------------------------------


SERVICE_SETTINGS = {str(marker): check for marker, check in SETTINGS_SCHEMA.items()}
SLOTS = {str(marker): check for marker, check in SETTING_SLOTS.items()}


def test_setting_slots_are_the_service_settings() -> None:
    """The settings of a sentence and of a tool are the ones a service has and the
    domain table knows, under the same names."""
    assert SLOTS.keys() == SERVICE_SETTINGS.keys() == SETTING_KINDS.keys()
    assert all(isinstance(marker, probatio.Optional) for marker in SETTING_SLOTS)
    assert {str(marker) for marker in PERCENT_SLOT} == {"percent"}
    assert not {"percent"} & SLOTS.keys()


@pytest.mark.parametrize("name", sorted(SETTING_KINDS))
def test_a_setting_slot_takes_what_its_kind_takes(name: str) -> None:
    """A text setting stays a text and a number setting a number, in the slot and in
    the service, whatever validator either uses: the kind is what the domain table
    says the setting is."""
    slot, service = SLOTS[name], SERVICE_SETTINGS[name]

    if SETTING_KINDS[name] == "text":
        assert slot("eco") == service("eco") == "eco"
    else:
        assert slot(1.5) == 1.5
        for refused in (slot, service):
            with pytest.raises(probatio.Invalid):
                refused("eco")
