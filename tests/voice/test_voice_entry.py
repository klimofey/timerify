"""The Voice settings entry: added from the menu, it writes the sentence files for the
built-in agent, keeps them in step with the timers, and takes them away again.

The scenarios are the user's: the integrations page, the options of the entry, the
timers and their targets being added, renamed and removed, and what the built-in agent
then answers. Files are written to the configuration directory of the test.
"""

import logging
import os
from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.fan.const import FanEntityFeature
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.core import CoreState, HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.timerify.const import (
    CONF_KIND,
    CONF_LANGUAGES,
    CONF_WRITE_SENTENCES,
    CONTEXT_HVAC_MODES,
    DOMAIN,
    KIND_VOICE_SETTINGS,
    LIST_INTERVAL,
    LIST_MODE,
    MANAGED_HEADER,
    SUBENTRY_INTERVAL,
    VOICE_LANGUAGES,
    VOICE_SYNC_COOLDOWN,
    VOICE_UNIQUE_ID,
)
from custom_components.timerify.spelling import fold_yo
from custom_components.timerify.voice.files import SentenceFiles
from custom_components.timerify.voice.sentences import (
    InvalidSentences,
    escape_template,
    render,
)

from ..conftest import (
    CLIMATE_SERVICES,
    SWITCH_SERVICES,
    FakeTarget,
    HeldCall,
    ProvideTarget,
    SetupTarget,
)
from ..helpers import (
    AC_ATTRS,
    AC_ID,
    SMALL_AC_ID,
    TARGET_ID,
    add_interval,
    advance,
    restart,
    retitle_interval,
    run_for_of,
    state_of,
)
from .helpers import (
    add_voice_entry,
    conversation_reloads,
    converse,
    copy_sentences,
    hvac_blocks,
    hvac_words,
    listed,
    managed_file,
    outs,
    put_file,
    reached,
    samples,
    speech,
    translated,
)

TIME_LEFT = "TimerifyTimeLeft"
BOILER = {"in": "Boiler", "out": "Boiler", "context": {"domain": "switch"}}
"""What the managed file lists for the boiler."""
FAN = {"in": "Fan", "out": "Fan", "context": {"domain": "switch"}}
AN_OLD_TIME = 1_000_000_000
"""A time, as the seconds since 1970, that no file written during a test has."""
YO_NAME = "\N{CYRILLIC CAPITAL LETTER IO}lka"
"""A name with the Russian letter yo, built from the code point so that this file stays
free of Cyrillic."""


async def open_menu(hass: HomeAssistant) -> FlowResult:
    """Press "Add entry" on the integration page."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def open_voice_form(hass: HomeAssistant) -> FlowResult:
    """Choose "Voice settings" in the menu; the form it shows."""
    menu = await open_menu(hass)
    return await hass.config_entries.flow.async_configure(
        menu["flow_id"], {"next_step_id": "voice_settings"}
    )


def default_of(form: FlowResult, key: str) -> Any:
    """What the form fills in for the field `key` before the user touches it."""
    marker = next(marker for marker in form["data_schema"].schema if marker == key)
    return marker.default() if callable(marker.default) else marker.default


def only_error(caplog: pytest.LogCaptureFixture) -> str:
    """The one error Timerify logged."""
    errors = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.ERROR
        and record.name.startswith("custom_components.timerify")
    ]
    assert len(errors) == 1, errors
    return errors[0]


def timerify_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """What Timerify warned about."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING
        and record.name.startswith("custom_components.timerify")
    ]


def stamp(hass: HomeAssistant, language: str) -> None:
    """Make the file of `language` old, so that a file written afterwards shows."""
    os.utime(managed_file(hass, language), (AN_OLD_TIME, AN_OLD_TIME))


def is_stamped(hass: HomeAssistant, language: str) -> bool:
    """Whether the file of `language` is as `stamp` left it: not written since."""
    return managed_file(hass, language).stat().st_mtime == AN_OLD_TIME


def reached_time_left(response: intent.IntentResponse) -> bool:
    return response.intent is not None and response.intent.intent_type == TIME_LEFT


# The menu and the form


@pytest.mark.usefixtures("assist")
async def test_menu_offers_a_timer_and_voice_settings(hass: HomeAssistant) -> None:
    result = await open_menu(hass)

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["target", "voice_settings"]


@pytest.mark.parametrize(
    ("house", "chosen"),
    [("en", ["en"]), ("ru", ["ru"]), ("ru-RU", ["ru"]), ("de", ["en"])],
)
@pytest.mark.usefixtures("assist")
async def test_languages_default_to_the_house_language(
    hass: HomeAssistant, house: str, chosen: list[str]
) -> None:
    """The form starts with the sentences written in the language of the house, in
    English if the house speaks one Timerify has no sentences in; leaving it as it is
    adds an entry that writes just those."""
    hass.config.language = house

    form = await open_voice_form(hass)
    assert default_of(form, CONF_LANGUAGES) == chosen
    assert default_of(form, CONF_WRITE_SENTENCES) is True
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {
            CONF_WRITE_SENTENCES: default_of(form, CONF_WRITE_SENTENCES),
            CONF_LANGUAGES: default_of(form, CONF_LANGUAGES),
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_LANGUAGES] == chosen
    assert result["options"][CONF_KIND] == KIND_VOICE_SETTINGS


@pytest.mark.usefixtures("assist")
async def test_empty_language_choice_is_refused(hass: HomeAssistant) -> None:
    """With no language the entry would write nothing: when it is added, and when it
    is changed, the form says so and keeps the entry as it was."""
    form = await open_voice_form(hass)
    refused = await hass.config_entries.flow.async_configure(
        form["flow_id"], {CONF_WRITE_SENTENCES: True, CONF_LANGUAGES: []}
    )

    assert refused["type"] is FlowResultType.FORM
    assert refused["step_id"] == "voice_settings"
    assert refused["errors"] == {"base": "languages_required"}
    assert hass.config_entries.async_entries(DOMAIN) == []

    entry = await add_voice_entry(hass, languages=("en",))
    options = await hass.config_entries.options.async_init(entry.entry_id)
    refused = await hass.config_entries.options.async_configure(
        options["flow_id"], {CONF_WRITE_SENTENCES: True, CONF_LANGUAGES: []}
    )

    assert refused["type"] is FlowResultType.FORM
    assert refused["errors"] == {"base": "languages_required"}
    assert entry.options[CONF_LANGUAGES] == ["en"]


@pytest.mark.usefixtures("assist")
async def test_menu_hides_voice_settings_once_it_exists(hass: HomeAssistant) -> None:
    await add_voice_entry(hass)

    result = await open_menu(hass)

    assert result["menu_options"] == ["target"]


@pytest.mark.usefixtures("assist")
async def test_second_voice_entry_is_refused(hass: HomeAssistant) -> None:
    """Two people adding the voice settings at once: the second is turned away, with a
    reason of its own."""
    first = await open_voice_form(hass)
    second = await open_voice_form(hass)
    answer = {CONF_WRITE_SENTENCES: True, CONF_LANGUAGES: ["en"]}

    created = await hass.config_entries.flow.async_configure(first["flow_id"], answer)
    refused = await hass.config_entries.flow.async_configure(second["flow_id"], answer)

    assert created["type"] is FlowResultType.CREATE_ENTRY
    assert refused["type"] is FlowResultType.ABORT
    assert refused["reason"] == "voice_settings_exist"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize("house", ["en", "ru", "de"])
@pytest.mark.usefixtures("assist")
async def test_voice_entry_title_is_in_the_language_of_the_house(
    hass: HomeAssistant, house: str
) -> None:
    """A house in a language Timerify has no translation of gets the English title."""
    hass.config.language = house

    entry = await add_voice_entry(hass, languages=("en",))

    spoken = house if house in ("en", "ru") else "en"
    assert entry.title == translated(
        spoken, "config", "step", "voice_settings", "title"
    )
    assert entry.unique_id == VOICE_UNIQUE_ID


@pytest.mark.usefixtures("assist")
async def test_voice_entry_has_no_intervals_and_no_timer(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The entry is no timer: it has no schedule, no entities, no device, and it is not
    among the timers whose targets the sentences name."""
    await setup_target()

    entry = await add_voice_entry(hass, languages=("en",))

    assert entry.state is ConfigEntryState.LOADED
    assert entry.supported_subentry_types == {}
    assert (SUBENTRY_INTERVAL, DOMAIN) not in entry.supported_subentry_types
    assert er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id) == []
    assert dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id) == []
    assert isinstance(entry.runtime_data, SentenceFiles)
    assert listed(hass, "en") == [BOILER]


# Writing the files


@pytest.mark.usefixtures("assist")
async def test_voice_entry_writes_a_file_per_chosen_language(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """With the entry added, the built-in agent understands the sentences in both
    languages, with no file copied by hand, and was told to read them once."""
    await setup_target()
    reloads = conversation_reloads(hass)

    await add_voice_entry(hass, languages=("en", "ru"))

    for language in ("en", "ru"):
        lines = managed_file(hass, language).read_text("utf-8").splitlines()
        assert lines[0] == MANAGED_HEADER
        assert listed(hass, language) == [BOILER]
    english = await converse(hass, "how long is left on the boiler")
    assert reached_time_left(english)
    assert speech(english) == "Boiler is off and has no timer."
    (russian_text, *_) = samples("ru", TIME_LEFT, numbers={})
    russian = await converse(hass, russian_text, "ru")
    assert reached_time_left(russian)
    assert [call.data for call in reloads] == [{}]


@pytest.mark.usefixtures("assist")
async def test_only_the_chosen_languages_are_written(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A language that is left out has no file, and one that is taken out of the
    entry's languages loses it."""
    await setup_target()
    reloads = conversation_reloads(hass)

    entry = await add_voice_entry(hass, languages=("en",))

    assert managed_file(hass, "en").exists()
    assert not managed_file(hass, "ru").exists()

    options = await hass.config_entries.options.async_init(entry.entry_id)
    assert options["step_id"] == "voice_settings"
    await hass.config_entries.options.async_configure(
        options["flow_id"], {CONF_WRITE_SENTENCES: True, CONF_LANGUAGES: ["ru"]}
    )
    await hass.async_block_till_done()

    assert not managed_file(hass, "en").exists()
    assert listed(hass, "ru") == [BOILER]
    assert len(reloads) == 2


@pytest.mark.usefixtures("assist")
async def test_option_off_at_creation_writes_nothing(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    await setup_target()
    reloads = conversation_reloads(hass)

    entry = await add_voice_entry(hass, write=False)

    assert entry.state is ConfigEntryState.LOADED
    assert not managed_file(hass, "en").exists()
    assert not managed_file(hass, "ru").exists()
    assert reloads == []


@pytest.mark.usefixtures("assist")
async def test_unticking_removes_the_files_and_the_sentences_stop_matching(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    await setup_target()
    entry = await add_voice_entry(hass, languages=("en",))
    assert reached_time_left(await converse(hass, "how long is left on the boiler"))
    reloads = conversation_reloads(hass)

    options = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        options["flow_id"], {CONF_WRITE_SENTENCES: False, CONF_LANGUAGES: ["en"]}
    )
    await hass.async_block_till_done()

    assert not managed_file(hass, "en").exists()
    assert len(reloads) == 1
    assert not reached_time_left(await converse(hass, "how long is left on the boiler"))


@pytest.mark.usefixtures("assist")
async def test_ticking_again_writes_them(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    await setup_target()
    entry = await add_voice_entry(hass, write=False, languages=("en",))
    reloads = conversation_reloads(hass)

    options = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        options["flow_id"], {CONF_WRITE_SENTENCES: True, CONF_LANGUAGES: ["en"]}
    )
    await hass.async_block_till_done()

    assert listed(hass, "en") == [BOILER]
    assert len(reloads) == 1
    assert reached_time_left(await converse(hass, "how long is left on the boiler"))


@pytest.mark.usefixtures("assist")
async def test_removing_the_entry_removes_the_files(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Removing the entry leaves nothing that the built-in agent could stumble on."""
    await setup_target()
    entry = await add_voice_entry(hass)
    reloads = conversation_reloads(hass)

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert not managed_file(hass, "en").exists()
    assert not managed_file(hass, "ru").exists()
    assert [call.data for call in reloads] == [{}]
    assert not reached_time_left(await converse(hass, "how long is left on the boiler"))


@pytest.mark.usefixtures("assist")
async def test_disabling_the_entry_removes_the_files_and_enabling_writes_them(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    await setup_target()
    entry = await add_voice_entry(hass, languages=("en",))
    reloads = conversation_reloads(hass)

    await hass.config_entries.async_set_disabled_by(
        entry.entry_id, ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()

    assert not managed_file(hass, "en").exists()
    assert len(reloads) == 1

    await hass.config_entries.async_set_disabled_by(entry.entry_id, None)
    await hass.async_block_till_done()

    assert listed(hass, "en") == [BOILER]
    assert len(reloads) == 2


@pytest.mark.usefixtures("assist")
async def test_reloading_the_entry_keeps_the_files_without_rewriting(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The files stay while the entry reloads, and since they say what they should,
    nothing is written and the built-in agent is not told to read again."""
    await setup_target()
    entry = await add_voice_entry(hass, languages=("en",))
    stamp(hass, "en")
    reloads = conversation_reloads(hass)

    await restart(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert is_stamped(hass, "en")
    assert reloads == []


@pytest.mark.usefixtures("assist")
async def test_unchanged_file_is_not_rewritten(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A timer that reloads, as every timer does when it is changed, names the same
    devices after: nothing is written and nothing is reloaded."""
    timer = await setup_target()
    await add_voice_entry(hass, languages=("en",))
    stamp(hass, "en")
    reloads = conversation_reloads(hass)

    await restart(hass, timer)
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert is_stamped(hass, "en")
    assert reloads == []


@pytest.mark.usefixtures("assist")
async def test_start_writes_every_target_once(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """While Home Assistant starts the files wait for the timers; when it has started
    each language gets one file, naming every target, and the built-in agent is told to
    read once."""
    hass.set_state(CoreState.not_running)
    reloads = conversation_reloads(hass)

    await add_voice_entry(hass)
    await setup_target()
    await setup_target(target="switch.fan")

    assert not managed_file(hass, "en").exists()
    assert not managed_file(hass, "ru").exists()
    assert reloads == []

    await hass.async_start()
    await hass.async_block_till_done()

    for language in ("en", "ru"):
        assert listed(hass, language) == [BOILER, FAN]
    assert len(reloads) == 1


# Following the timers


@pytest.mark.usefixtures("assist")
async def test_new_target_is_listed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    await setup_target()
    await add_voice_entry(hass, languages=("en",))
    reloads = conversation_reloads(hass)

    await setup_target(target="switch.fan")
    assert listed(hass, "en") == [BOILER]
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert listed(hass, "en") == [BOILER, FAN]
    assert len(reloads) == 1
    assert reached_time_left(await converse(hass, "how long is left on the fan"))


@pytest.mark.usefixtures("assist")
async def test_removed_target_leaves_the_list(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    await setup_target()
    fan_timer = await setup_target(target="switch.fan")
    await add_voice_entry(hass, languages=("en",))
    assert listed(hass, "en") == [BOILER, FAN]

    await hass.config_entries.async_remove(fan_timer.entry_id)
    await hass.async_block_till_done()
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert listed(hass, "en") == [BOILER]
    assert not reached_time_left(await converse(hass, "how long is left on the fan"))


@pytest.mark.usefixtures("assist")
async def test_a_second_timer_on_a_device_leaves_the_voice_settings_alone(
    hass: HomeAssistant,
    fake_relay: tuple[FakeTarget, FakeTarget],
    setup_target: SetupTarget,
) -> None:
    """The Voice settings entry is loaded among the timers and has no target. The user
    adds the timers of both channels of a relay. The first one is renamed at once, and
    the settings are neither reloaded nor failed by it."""
    voice = await add_voice_entry(hass, languages=("en",))

    one = await setup_target(target="switch.relay_1")
    await setup_target(target="switch.relay_2")

    assert voice.state is ConfigEntryState.LOADED
    state = hass.states.get(run_for_of(hass, one))
    assert state is not None
    assert state.attributes["friendly_name"] == "Relay Run for (Channel 1)"


@pytest.mark.usefixtures("assist")
async def test_renamed_target_follows(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    await setup_target()
    await add_voice_entry(hass, languages=("en",))

    er.async_get(hass).async_update_entity(TARGET_ID, name="Water heater")
    await hass.async_block_till_done()
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert listed(hass, "en") == [
        {"in": "Water heater", "out": "Water heater", "context": {"domain": "switch"}}
    ]
    answer = await converse(hass, "how long is left on the water heater")
    assert speech(answer) == "Water heater is off and has no timer."
    assert not reached_time_left(await converse(hass, "how long is left on the boiler"))


@pytest.mark.usefixtures("assist")
async def test_new_name_and_alias_are_matched(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The entity's name and an alias of it are both said, as for any entity; the
    computed name stays among the aliases only if the list says so."""
    await setup_target()
    await add_voice_entry(hass, languages=("en",))

    er.async_get(hass).async_update_entity(
        TARGET_ID, name="Water heater", aliases={er.COMPUTED_NAME, "Geyser"}
    )
    await hass.async_block_till_done()
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert {value["in"] for value in listed(hass, "en")} == {"Water heater", "Geyser"}
    for name in ("water heater", "geyser"):
        assert reached_time_left(
            await converse(hass, f"how long is left on the {name}")
        )


@pytest.mark.usefixtures("assist")
async def test_device_rename_follows_the_full_name(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """An entity that has no name of its own is known by the name of its device."""
    registry = er.async_get(hass)
    registry.async_update_entity(TARGET_ID, has_entity_name=True, original_name=None)
    await setup_target()
    await add_voice_entry(hass, languages=("en",))
    assert [value["in"] for value in listed(hass, "en")] == ["Boiler"]

    dr.async_get(hass).async_update_device(
        fake_target.device_id or "", name_by_user="Geyser"
    )
    await hass.async_block_till_done()
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert [value["in"] for value in listed(hass, "en")] == ["Geyser"]
    assert reached_time_left(await converse(hass, "how long is left on the geyser"))


# The words for the settings the targets take


@pytest.mark.usefixtures("assist")
async def test_words_for_settings_come_with_the_targets_that_take_them(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_climate: FakeTarget,
    fake_vent: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A house with a boiler only has no word for a mode; the air conditioner and the
    fan bring theirs after the cooldown, and the agent reads them once."""
    await setup_target()
    await add_voice_entry(hass, languages=("en",))
    reloads = conversation_reloads(hass)
    assert hvac_words(hass, "en") == {}
    assert listed(hass, "en", LIST_MODE) == []

    await setup_target(target=AC_ID)
    await setup_target(target=fake_vent.entity_id)
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert hvac_words(hass, "en") == {
        "cool fan_only heat": ["cool", "heat", "fan_only"]
    }
    assert outs(listed(hass, "en", LIST_MODE)) == [
        "auto",
        "eco",
        "high",
        "low",
        "sleep",
    ]
    assert len(reloads) == 1
    assert reached(await converse(hass, "turn on the AC for an hour cooling")) == (
        "TimerifyRun"
    )
    assert fake_climate.call_data[0] == ("set_hvac_mode", {"hvac_mode": "cool"})


@pytest.mark.usefixtures("assist")
async def test_words_for_settings_leave_with_the_target(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    await setup_target()
    ac_timer = await setup_target(target=AC_ID)
    await add_voice_entry(hass, languages=("en",))
    assert outs(listed(hass, "en", LIST_MODE)) == ["auto", "high", "low"]

    await hass.config_entries.async_remove(ac_timer.entry_id)
    await hass.async_block_till_done()
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert hvac_words(hass, "en") == {}
    assert listed(hass, "en", LIST_MODE) == []


@pytest.mark.usefixtures("assist")
async def test_a_mode_is_listed_as_a_person_says_it(
    hass: HomeAssistant, provide_target: ProvideTarget, setup_target: SetupTarget
) -> None:
    """A device names its presets with underscores; a person does not say them: the
    list holds the words, and the name the device knows the preset by."""
    vent = provide_target(
        "fan.vent",
        SWITCH_SERVICES,
        name="Vent",
        capability_attributes={
            "preset_modes": ["eco_plus", "Turbo (quiet)"],
            "supported_features": int(
                FanEntityFeature.TURN_ON
                | FanEntityFeature.TURN_OFF
                | FanEntityFeature.PRESET_MODE
            ),
        },
    )
    await setup_target(target=vent.entity_id)
    await add_voice_entry(hass, languages=("en",))

    assert sorted(listed(hass, "en", LIST_MODE), key=lambda value: value["out"]) == [
        {"in": r"Turbo \(quiet\)", "out": "Turbo (quiet)"},
        {"in": "eco plus", "out": "eco_plus"},
    ]
    response = await converse(hass, "turn on the vent for 10 minutes in eco plus mode")
    assert reached(response) == "TimerifyRun"
    assert vent.call_data == [("turn_on", {"preset_mode": "eco_plus"})]


@pytest.mark.usefixtures("assist")
async def test_every_language_gets_the_same_modes(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The words for an HVAC mode differ by language, and so do the words of Home
    Assistant for a mode of a device; the modes they mean do not."""
    await setup_target(target=AC_ID)
    await add_voice_entry(hass)

    hvac = {
        language: {key: set(modes) for key, modes in hvac_words(hass, language).items()}
        for language in VOICE_LANGUAGES
    }
    modes = {
        language: set(outs(listed(hass, language, LIST_MODE)))
        for language in VOICE_LANGUAGES
    }
    assert (
        hvac["en"] == hvac["ru"] == {"cool fan_only heat": {"cool", "heat", "fan_only"}}
    )
    assert modes["en"] == modes["ru"] == {"auto", "high", "low"}


@pytest.mark.usefixtures("assist")
async def test_each_thermostat_is_listed_with_the_modes_it_has(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_full_ac: FakeTarget,
    fake_small_ac: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The name of a thermostat carries the key of its modes, which is what ties it to
    the sentences with the words for those modes; a target that is no thermostat has no
    key. Each set of modes has its own copy of the sentences for thermostats."""
    await setup_target()
    await setup_target(target=fake_full_ac.entity_id)
    await setup_target(target=fake_small_ac.entity_id)
    await add_voice_entry(hass, languages=("en",))

    assert {value["out"]: value["context"] for value in listed(hass, "en")} == {
        "Boiler": {"domain": "switch"},
        "AC": {
            "domain": "climate",
            CONTEXT_HVAC_MODES: "auto cool dry fan_only heat heat_cool",
        },
        "Small AC": {"domain": "climate", CONTEXT_HVAC_MODES: "cool fan_only"},
    }
    assert sorted(hvac_words(hass, "en")) == [
        "auto cool dry fan_only heat heat_cool",
        "cool fan_only",
    ]
    assert len(hvac_blocks(hass, "en")) == 6


@pytest.mark.usefixtures("assist")
async def test_thermostats_with_the_same_modes_share_their_sentences(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    provide_target: ProvideTarget,
    setup_target: SetupTarget,
) -> None:
    """Two air conditioners that can be turned on in the same modes, whatever order
    their integrations list them in, are known by one copy of the sentences."""
    second = provide_target(
        SMALL_AC_ID,
        CLIMATE_SERVICES,
        name="Small AC",
        capability_attributes={
            **AC_ATTRS,
            "hvac_modes": ["fan_only", "cool", "off", "heat"],
        },
        state_attributes={"temperature": 20, "fan_mode": "auto"},
    )
    await setup_target(target=fake_climate.entity_id)
    await setup_target(target=second.entity_id)
    await add_voice_entry(hass, languages=("en",))

    assert hvac_words(hass, "en") == {
        "cool fan_only heat": ["cool", "heat", "fan_only"]
    }
    assert len(hvac_blocks(hass, "en")) == 3
    assert {value["context"][CONTEXT_HVAC_MODES] for value in listed(hass, "en")} == {
        "cool fan_only heat"
    }


@pytest.mark.usefixtures("assist")
async def test_the_sentences_for_thermostats_follow_the_thermostats_of_the_house(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_full_ac: FakeTarget,
    fake_small_ac: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A thermostat added later brings its own copy after the cooldown, and one taken
    away takes its copy with it; the agent reads the sentences once for the change."""
    await setup_target(target=fake_full_ac.entity_id)
    await add_voice_entry(hass, languages=("en",))
    assert len(hvac_blocks(hass, "en")) == 3
    reloads = conversation_reloads(hass)

    small_timer = await setup_target(target=fake_small_ac.entity_id)
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert len(hvac_blocks(hass, "en")) == 6
    assert len(reloads) == 1
    cooled = await converse(hass, "turn on the small AC for an hour cooling")
    assert reached(cooled) == "TimerifyRun"

    await hass.config_entries.async_remove(small_timer.entry_id)
    await hass.async_block_till_done()
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert len(hvac_blocks(hass, "en")) == 3
    assert sorted(hvac_words(hass, "en")) == ["auto cool dry fan_only heat heat_cool"]


# Schedule interval titles


async def add_titled_interval(
    hass: HomeAssistant, entry: ConfigEntry, title: str, start: str = "06:30"
) -> str:
    """Add an interval to the timer of `entry` and give it a title, as its owner does;
    return its id."""
    interval = await add_interval(hass, entry, start=start, end="23:00")
    await retitle_interval(hass, entry, interval, title)
    return interval


def interval_values(title: str) -> dict[str, str]:
    """What the managed file lists for an interval titled `title` that needs no
    escaping."""
    return {"in": title, "out": title}


@pytest.mark.usefixtures("assist")
async def test_interval_titles_are_listed_once_for_every_language(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The boiler has Morning and Evening, the fan Morning and Night: the house has the
    three titles, Morning once, in the order the timers and their intervals come, and
    every language has them."""
    boiler = await setup_target()
    fan = await setup_target(target=fake_fan.entity_id)
    await add_titled_interval(hass, boiler, "Morning")
    await add_titled_interval(hass, boiler, "Evening", "18:00")
    await add_titled_interval(hass, fan, "Morning")
    await add_titled_interval(hass, fan, "Night", "22:00")

    await add_voice_entry(hass)

    for language in VOICE_LANGUAGES:
        assert listed(hass, language, LIST_INTERVAL) == [
            interval_values("Morning"),
            interval_values("Evening"),
            interval_values("Night"),
        ]


@pytest.mark.usefixtures("assist")
async def test_a_house_without_intervals_lists_none(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    await setup_target()

    await add_voice_entry(hass, languages=("en",))

    assert listed(hass, "en", LIST_INTERVAL) == []


@pytest.mark.usefixtures("assist")
async def test_a_new_interval_is_listed_and_a_deleted_one_leaves(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    boiler = await setup_target()
    await add_voice_entry(hass, languages=("en",))
    reloads = conversation_reloads(hass)

    morning = await add_titled_interval(hass, boiler, "Morning")
    assert listed(hass, "en", LIST_INTERVAL) == []
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert listed(hass, "en", LIST_INTERVAL) == [interval_values("Morning")]
    assert len(reloads) == 1

    hass.config_entries.async_remove_subentry(boiler, morning)
    await hass.async_block_till_done()
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert listed(hass, "en", LIST_INTERVAL) == []
    assert len(reloads) == 2


@pytest.mark.usefixtures("assist")
async def test_the_intervals_of_a_removed_timer_leave_with_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    boiler = await setup_target()
    fan = await setup_target(target=fake_fan.entity_id)
    await add_titled_interval(hass, boiler, "Morning")
    await add_titled_interval(hass, fan, "Night", "22:00")
    await add_voice_entry(hass, languages=("en",))
    assert listed(hass, "en", LIST_INTERVAL) == [
        interval_values("Morning"),
        interval_values("Night"),
    ]

    await hass.config_entries.async_remove(fan.entry_id)
    await hass.async_block_till_done()
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert listed(hass, "en", LIST_INTERVAL) == [interval_values("Morning")]


@pytest.mark.usefixtures("assist")
async def test_title_left_empty_by_punctuation_is_skipped(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A title that is nothing but punctuation would match anywhere; it is left out,
    the other titles stay."""
    boiler = await setup_target()
    await add_titled_interval(hass, boiler, "?!")
    await add_titled_interval(hass, boiler, "Evening", "18:00")

    await add_voice_entry(hass, languages=("en",))

    assert listed(hass, "en", LIST_INTERVAL) == [interval_values("Evening")]


AWKWARD_TITLES = [
    "Morning (weekdays)",
    "Lamp [2]",
    "A|B lamp",
    "<Hall>",
    "Tea {pot}",
    "me@home",
    "Back\\slash",
    "A\\(b",
    "Morning!",
    "06:30–07:15, Mon–Sun",
]
"""Titles with a character that Home Assistant reads as part of a sentence template, or
that its agent cleans away when it hears the title."""


@pytest.mark.usefixtures("assist")
async def test_titles_are_listed_so_that_they_match_as_said(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A title with a character that Home Assistant reads as part of a sentence
    template is written so that it is read as the title: the file with all of them
    loads, and each title, said as it is, reaches the timer and switches its own
    interval and no other."""
    boiler = await setup_target()
    for index, title in enumerate(AWKWARD_TITLES):
        await add_titled_interval(hass, boiler, title, start=f"06:{index:02d}")

    await add_voice_entry(hass, languages=("en",))

    assert [value["out"] for value in listed(hass, "en", LIST_INTERVAL)] == (
        AWKWARD_TITLES
    )
    for index, title in enumerate(AWKWARD_TITLES):
        response = await converse(hass, f"turn off the {title} schedule of the boiler")

        assert reached(response) == "TimerifySetSchedule", title
        assert [
            state_of(hass, f"switch.boiler_schedule_06_{other:02d}_23_00_mon_sun")
            for other in range(len(AWKWARD_TITLES))
        ] == ["off"] * (index + 1) + ["on"] * (len(AWKWARD_TITLES) - index - 1), title


@pytest.mark.usefixtures("assist")
async def test_unescaped_title_is_refused_before_writing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A title that the built-in agent could not parse leaves the file as it was, and
    the log says which language it is about."""
    boiler = await setup_target()
    interval = await add_titled_interval(hass, boiler, "Morning")
    await add_voice_entry(hass, languages=("en",))
    before = managed_file(hass, "en").read_text("utf-8")
    reloads = conversation_reloads(hass)

    with patch(
        "custom_components.timerify.voice.sentences.escape_template",
        side_effect=lambda text: text,
    ):
        await retitle_interval(hass, boiler, interval, "Morning (early")
        await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert managed_file(hass, "en").read_text("utf-8") == before
    assert "sentences for en" in only_error(caplog)
    assert reloads == []


@pytest.mark.usefixtures("assist")
async def test_title_that_would_not_match_as_said_is_refused(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A title that parses, but as something other than the text it stands for (here,
    `<Hall>` as a reference to an expansion rule), would never be matched as said: it
    is refused as well."""

    def forgetting_the_angle_brackets(text: str) -> str:
        return escape_template(text).replace("\\<", "<").replace("\\>", ">")

    boiler = await setup_target()
    interval = await add_titled_interval(hass, boiler, "Morning")
    await add_voice_entry(hass, languages=("en",))
    before = managed_file(hass, "en").read_text("utf-8")

    with patch(
        "custom_components.timerify.voice.sentences.escape_template",
        side_effect=forgetting_the_angle_brackets,
    ):
        await retitle_interval(hass, boiler, interval, "<Hall>")
        await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert managed_file(hass, "en").read_text("utf-8") == before
    message = only_error(caplog)
    assert "sentences for en" in message
    assert "matched as said" in message


# Names that are not plain words


@pytest.mark.parametrize(
    "name",
    [
        "Boiler (main)",
        "Lamp [2]",
        "A|B lamp",
        "<Hall>",
        "Tea {pot}",
        "me@home",
        "Back\\slash",
        "A\\(b",
    ],
)
@pytest.mark.usefixtures("assist")
async def test_names_are_listed_so_that_they_match_as_said(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget, name: str
) -> None:
    """A name with a character that Home Assistant reads as part of a sentence template
    is written so that it is read as the name; the file loads and the name, said as it
    is, reaches the timer."""
    er.async_get(hass).async_update_entity(TARGET_ID, name=name)
    await setup_target()

    await add_voice_entry(hass, languages=("en",))

    assert [value["out"] for value in listed(hass, "en")] == [name]
    answer = await converse(hass, f"how long is left on {name}")
    assert reached_time_left(answer)
    assert speech(answer) == f"{name} is off and has no timer."


@pytest.mark.usefixtures("assist")
async def test_name_is_matched_as_the_default_agent_cleans_it(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The built-in agent takes the punctuation out of what it hears and of the names
    it knows; so does the file, and the timer is still asked for by the name it is shown
    with."""
    er.async_get(hass).async_update_entity(TARGET_ID, name="Boiler!")
    await setup_target()

    await add_voice_entry(hass, languages=("en",))

    assert listed(hass, "en") == [
        {"in": "Boiler", "out": "Boiler!", "context": {"domain": "switch"}}
    ]
    answer = await converse(hass, "how long is left on the boiler")
    assert speech(answer) == "Boiler! is off and has no timer."


@pytest.mark.usefixtures("assist")
async def test_name_left_empty_by_punctuation_is_skipped(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A name that is nothing but punctuation would match anywhere; it is left out, the
    other names stay."""
    er.async_get(hass).async_update_entity(
        TARGET_ID, name="?!", aliases={er.COMPUTED_NAME, "Boiler"}
    )
    await setup_target()

    await add_voice_entry(hass, languages=("en",))

    assert [value["in"] for value in listed(hass, "en")] == ["Boiler"]


@pytest.mark.usefixtures("assist")
async def test_a_russian_name_with_yo_is_matched_said_with_ye(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A speech recogniser writes ye where Russian prints yo, and the built-in agent
    compares letter by letter: the name is listed with both, and the answer gives the
    name as the device has it."""
    er.async_get(hass).async_update_entity(TARGET_ID, name=YO_NAME)
    await setup_target()

    await add_voice_entry(hass, languages=("ru",))

    domain = {"domain": "switch"}
    assert listed(hass, "ru") == [
        {"in": YO_NAME, "out": YO_NAME, "context": domain},
        {"in": fold_yo(YO_NAME), "out": YO_NAME, "context": domain},
    ]
    (text, *_) = samples("ru", TIME_LEFT, names=(fold_yo(YO_NAME),), numbers={})
    response = await converse(hass, text, "ru")
    assert reached(response) == TIME_LEFT
    assert speech(response).startswith(YO_NAME)


@pytest.mark.usefixtures("assist")
async def test_a_russian_name_with_yo_is_still_matched_as_written(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    er.async_get(hass).async_update_entity(TARGET_ID, name=YO_NAME)
    await setup_target()
    await add_voice_entry(hass, languages=("ru",))

    (text, *_) = samples("ru", TIME_LEFT, names=(YO_NAME,), numbers={})
    response = await converse(hass, text, "ru")

    assert reached(response) == TIME_LEFT
    assert speech(response).startswith(YO_NAME)


@pytest.mark.usefixtures("assist")
async def test_shared_name_is_not_resolved_to_the_other_entity(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A fan that is called Boiler as well is not the timer's target: the sentence
    means the timer, and the fan is neither asked about nor touched."""
    er.async_get(hass).async_update_entity("switch.fan", name="Boiler")
    await setup_target()
    await add_voice_entry(hass, languages=("en",))

    answer = await converse(hass, "how long is left on boiler")

    assert reached_time_left(answer)
    assert speech(answer) == "Boiler is off and has no timer."
    assert [state.entity_id for state in answer.matched_states] == [TARGET_ID]
    assert fake_fan.calls == []


# Files that would break the built-in agent are not written


@pytest.mark.usefixtures("assist")
async def test_unescaped_name_is_refused_before_writing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A name that the built-in agent could not parse leaves the file as it was, and
    the log says which language it is about: the agent would fail on every request in
    that language."""
    await setup_target()
    await add_voice_entry(hass, languages=("en",))
    before = managed_file(hass, "en").read_text("utf-8")
    reloads = conversation_reloads(hass)

    with patch(
        "custom_components.timerify.voice.sentences.escape_template",
        side_effect=lambda text: text,
    ):
        er.async_get(hass).async_update_entity(TARGET_ID, name="Boiler (main")
        await hass.async_block_till_done()
        await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert managed_file(hass, "en").read_text("utf-8") == before
    assert "sentences for en" in only_error(caplog)
    assert reloads == []


@pytest.mark.usefixtures("assist")
async def test_list_value_that_would_not_match_as_said_is_refused(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A name that parses, but as something other than the text it stands for (here,
    `<Hall>` as a reference to an expansion rule), would never be matched as said: it is
    refused as well."""

    def forgetting_the_angle_brackets(text: str) -> str:
        return escape_template(text).replace("\\<", "<").replace("\\>", ">")

    await setup_target()
    await add_voice_entry(hass, languages=("en",))
    before = managed_file(hass, "en").read_text("utf-8")

    with patch(
        "custom_components.timerify.voice.sentences.escape_template",
        side_effect=forgetting_the_angle_brackets,
    ):
        er.async_get(hass).async_update_entity(TARGET_ID, name="<Hall>")
        await hass.async_block_till_done()
        await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert managed_file(hass, "en").read_text("utf-8") == before
    message = only_error(caplog)
    assert "sentences for en" in message
    assert "matched as said" in message


@pytest.mark.usefixtures("assist")
async def test_a_language_that_fails_does_not_stop_the_other(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Each language is checked on its own: one whose sentences are not fit to be read
    is named in the log, and the other is written."""
    await setup_target()

    def failing_for_russian(language: str, *_: object) -> None:
        if language == "ru":
            raise InvalidSentences("this language is broken")

    with patch(
        "custom_components.timerify.voice.files.validate",
        side_effect=failing_for_russian,
    ):
        await add_voice_entry(hass, languages=("en", "ru"))

    assert listed(hass, "en") == [BOILER]
    assert not managed_file(hass, "ru").exists()
    assert "sentences for ru" in only_error(caplog)


# Files that are not Timerify's

FOREIGN = "# My own sentences, in my own file\nlanguage: en\nintents: {}\n"
"""A file of the user's at the path of the managed file."""
FOREIGN_FIRST_LINES = [
    pytest.param(b"", id="an empty file"),
    pytest.param(b"language: en\nintents: {}\n", id="no comment"),
    pytest.param(b"# Managed by somebody else.\nlanguage: en\n", id="another comment"),
    pytest.param(
        MANAGED_HEADER.encode() + b" \nlanguage: en\n", id="a header and more"
    ),
    pytest.param(
        b"#" + MANAGED_HEADER.encode() + b"\nlanguage: en\n",
        id="the header commented out",
    ),
    pytest.param(b"\n" + MANAGED_HEADER.encode() + b"\n", id="the header second"),
    pytest.param(b"\xff\xfe\x00 not text at all", id="not text"),
]
"""First lines that are not the managed header, which is the only way a file is known
to be Timerify's."""


@pytest.mark.parametrize("content", FOREIGN_FIRST_LINES)
@pytest.mark.usefixtures("assist")
async def test_a_file_that_does_not_start_with_the_managed_header_is_not_timerifys(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    content: bytes,
) -> None:
    """The file is left as it is, the language is not written, and the log says whose
    file is in the way."""
    await setup_target()
    path = await put_file(hass, "en", content)
    reloads = conversation_reloads(hass)

    await add_voice_entry(hass, languages=("en",))

    assert path.read_bytes() == content
    assert reloads == []
    warnings = timerify_warnings(caplog)
    assert len(warnings) == 1
    assert str(path) in warnings[0]
    assert "not written by Timerify" in warnings[0]


@pytest.mark.usefixtures("assist")
async def test_a_foreign_file_costs_only_its_own_language(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The other language is written and follows the timers, and the warning is said
    once for the entry that was loaded, not at every writing."""
    await setup_target()
    path = await put_file(hass, "en", FOREIGN)
    reloads = conversation_reloads(hass)

    await add_voice_entry(hass, languages=("en", "ru"))
    await setup_target(target="switch.fan")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert path.read_text("utf-8") == FOREIGN
    assert listed(hass, "ru") == [BOILER, FAN]
    assert len(reloads) == 2
    warnings = timerify_warnings(caplog)
    assert len(warnings) == 1
    assert str(path) in warnings[0]


@pytest.mark.usefixtures("assist")
async def test_the_language_is_written_once_the_foreign_file_is_moved_away(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    await setup_target()
    path = await put_file(hass, "en", FOREIGN)
    await add_voice_entry(hass, languages=("en",))
    assert path.read_text("utf-8") == FOREIGN

    await hass.async_add_executor_job(path.unlink)
    await setup_target(target="switch.fan")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert listed(hass, "en") == [BOILER, FAN]


@pytest.mark.usefixtures("assist")
async def test_a_foreign_file_in_a_language_that_is_not_chosen_survives(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Nothing is written for the language, so there is nothing to say about the
    file either."""
    await setup_target()
    path = await put_file(hass, "ru", FOREIGN)
    reloads = conversation_reloads(hass)

    await add_voice_entry(hass, languages=("en",))
    await setup_target(target="switch.fan")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert path.read_text("utf-8") == FOREIGN
    assert len(reloads) == 2
    assert timerify_warnings(caplog) == []


@pytest.mark.usefixtures("assist")
async def test_foreign_files_survive_while_the_option_is_off_and_across_a_restart(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """With nothing to write, Timerify removes what it wrote, which is not these."""
    await setup_target()
    paths = [await put_file(hass, language, FOREIGN) for language in ("en", "ru")]
    reloads = conversation_reloads(hass)

    entry = await add_voice_entry(hass, write=False)
    await restart(hass, entry)

    assert [path.read_text("utf-8") for path in paths] == [FOREIGN, FOREIGN]
    assert reloads == []
    assert timerify_warnings(caplog) == []


@pytest.mark.parametrize("action", ["remove", "disable"])
@pytest.mark.usefixtures("assist")
async def test_leaving_takes_what_timerify_wrote_and_not_what_it_did_not(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    action: str,
) -> None:
    await setup_target()
    foreign = await put_file(hass, "ru", FOREIGN)
    entry = await add_voice_entry(hass, languages=("en",))
    assert managed_file(hass, "en").exists()

    await leave(hass, entry, action)

    assert not managed_file(hass, "en").exists()
    assert foreign.read_text("utf-8") == FOREIGN


@pytest.mark.usefixtures("assist")
async def test_a_directory_where_the_file_belongs_is_not_timerifys_either(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A folder called `timerify.yaml` cannot be read as a file, and is no file that
    Timerify wrote: it is left, its language is not written, the other language is, and
    the log says what is in the way."""
    await setup_target()
    folder = managed_file(hass, "en")
    await hass.async_add_executor_job(folder.mkdir, 0o755, True)

    entry = await add_voice_entry(hass, languages=("en", "ru"))

    assert entry.state is ConfigEntryState.LOADED
    assert folder.is_dir()
    assert listed(hass, "ru") == [BOILER]
    warnings = timerify_warnings(caplog)
    assert len(warnings) == 1
    assert str(folder) in warnings[0]
    assert "not written by Timerify" in warnings[0]


@pytest.mark.parametrize("action", ["remove", "disable"])
@pytest.mark.usefixtures("assist")
async def test_leaving_does_not_take_a_directory_where_the_file_belongs(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    action: str,
) -> None:
    await setup_target()
    entry = await add_voice_entry(hass, languages=("ru",))
    folder = managed_file(hass, "en")
    await hass.async_add_executor_job(folder.mkdir, 0o755, True)

    await leave(hass, entry, action)

    assert folder.is_dir()
    assert not managed_file(hass, "ru").exists()


@pytest.mark.usefixtures("assist")
async def test_a_managed_file_that_was_edited_is_written_again(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The header says not to edit it; as long as the header stays, the file is
    Timerify's and what is written over is the user's edit."""
    await setup_target()
    entry = await add_voice_entry(hass, languages=("en",))
    path = managed_file(hass, "en")
    await hass.async_add_executor_job(
        path.write_text, f"{MANAGED_HEADER}\n# and my own line\nlanguage: en\n", "utf-8"
    )
    reloads = conversation_reloads(hass)

    await restart(hass, entry)

    assert path.read_text("utf-8").splitlines()[0] == MANAGED_HEADER
    assert listed(hass, "en") == [BOILER]
    assert len(reloads) == 1


@pytest.mark.usefixtures("assist")
async def test_what_is_written_is_what_is_checked(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The built-in agent reads the text of the file, not the data it was made from:
    text that reads differently from the data is refused like any other."""
    await setup_target()
    reloads = conversation_reloads(hass)

    def read_as_two_names(built: dict[str, Any]) -> str:
        return render(built).replace("in: Boiler\n", "in: Boiler|Heater\n")

    with patch(
        "custom_components.timerify.voice.files.render", side_effect=read_as_two_names
    ):
        await add_voice_entry(hass, languages=("en",))

    assert not managed_file(hass, "en").exists()
    assert reloads == []
    assert "matched as said" in only_error(caplog)


# Changes that wait for the cooldown


async def leave(hass: HomeAssistant, entry: ConfigEntry, how: str) -> None:
    """Remove the entry, or disable it, and let everything that follows run."""
    if how == "remove":
        await hass.config_entries.async_remove(entry.entry_id)
    else:
        await hass.config_entries.async_set_disabled_by(
            entry.entry_id, ConfigEntryDisabler.USER
        )
    await hass.async_block_till_done()


@pytest.mark.parametrize("how", ["remove", "disable"])
@pytest.mark.usefixtures("assist")
async def test_a_change_waiting_for_the_cooldown_is_dropped_with_the_entry(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    setup_target: SetupTarget,
    how: str,
) -> None:
    await setup_target()
    entry = await add_voice_entry(hass, languages=("en",))
    await setup_target(target="switch.fan")
    reloads = conversation_reloads(hass)

    await leave(hass, entry, how)
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert not managed_file(hass, "en").exists()
    assert len(reloads) == 1


@pytest.mark.parametrize("how", ["remove", "disable"])
@pytest.mark.parametrize("first", ["the writing", "the leaving"])
@pytest.mark.usefixtures("assist")
async def test_a_writing_that_falls_due_as_the_entry_goes_does_not_bring_the_files_back(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    setup_target: SetupTarget,
    how: str,
    first: str,
) -> None:
    """The cooldown ends while the entry is being taken away: the files must be gone
    when everything has run, whichever of the two started first."""
    await setup_target()
    entry = await add_voice_entry(hass, languages=("en",))
    await setup_target(target="switch.fan")
    freezer.tick(timedelta(seconds=VOICE_SYNC_COOLDOWN))

    if first == "the writing":
        async_fire_time_changed(hass)
    leaving = hass.async_create_task(leave(hass, entry, how))
    if first == "the leaving":
        async_fire_time_changed(hass)
    await leaving
    await hass.async_block_till_done()

    assert not managed_file(hass, "en").exists()


@pytest.mark.usefixtures("assist")
async def test_a_burst_of_changes_is_written_once_after_the_cooldown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    await setup_target()
    await add_voice_entry(hass, languages=("en",))
    reloads = conversation_reloads(hass)

    await setup_target(target="switch.fan")
    er.async_get(hass).async_update_entity(TARGET_ID, name="Water heater")
    await hass.async_block_till_done()
    assert listed(hass, "en") == [BOILER]
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert [value["in"] for value in listed(hass, "en")] == ["Water heater", "Fan"]
    assert len(reloads) == 1


@pytest.mark.usefixtures("assist")
async def test_changes_while_home_assistant_stops_are_not_written(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    await setup_target()
    await add_voice_entry(hass, languages=("en",))
    stamp(hass, "en")
    reloads = conversation_reloads(hass)

    hass.set_state(CoreState.stopping)
    er.async_get(hass).async_update_entity(TARGET_ID, name="Water heater")
    await hass.async_block_till_done()
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert is_stamped(hass, "en")
    assert reloads == []


def slow_reload(hass: HomeAssistant) -> HeldCall:
    """Make the built-in agent slow to reload its sentences: every `conversation.reload`
    waits inside it until the call is released, and `reached` says one is there."""
    slow = HeldCall()

    async def reload(call: ServiceCall) -> None:
        slow.reached.set()
        await slow.release.wait()

    hass.services.async_register("conversation", "reload", reload)
    return slow


async def rename_the_boiler(hass: HomeAssistant, name: str) -> None:
    """The user renames the boiler on its entity page."""
    er.async_get(hass).async_update_entity(TARGET_ID, name=name)


def let_the_cooldown_pass_without_waiting(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Move the clock past the cooldown and run what falls due, without waiting for the
    tasks that are under way: a writing that is held cannot be waited for."""
    freezer.tick(timedelta(seconds=VOICE_SYNC_COOLDOWN))
    async_fire_time_changed(hass)


async def test_a_target_renamed_while_the_files_are_first_written_is_listed_as_renamed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The built-in agent takes a while to read the first files, and the boiler is
    renamed meanwhile. The files are written again for the new name, not left with the
    old one until something else changes."""
    await setup_target()
    slow = slow_reload(hass)
    adding = hass.async_create_task(add_voice_entry(hass, languages=("en",)))
    await slow.reached.wait()

    await rename_the_boiler(hass, "Water heater")
    slow.release.set()
    await adding
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert [value["in"] for value in listed(hass, "en")] == ["Water heater"]


@pytest.mark.parametrize("first", [True, False], ids=["first writing", "later writing"])
async def test_a_target_renamed_during_a_writing_that_outlasts_the_cooldown_is_listed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    first: bool,
) -> None:
    """The writing is still under way when the cooldown of a rename made during it ends,
    on a slow machine. Home Assistant's debouncer takes the writing for the one that
    covers the change and drops the call, so the writing itself must see that a change
    came in meanwhile and write again."""
    await setup_target()
    if first:
        slow = slow_reload(hass)
        adding = hass.async_create_task(add_voice_entry(hass, languages=("en",)))
    else:
        await add_voice_entry(hass, languages=("en",))
        slow = slow_reload(hass)
        await rename_the_boiler(hass, "Kettle")
        let_the_cooldown_pass_without_waiting(hass, freezer)
    await slow.reached.wait()

    await rename_the_boiler(hass, "Water heater")
    let_the_cooldown_pass_without_waiting(hass, freezer)
    slow.release.set()
    await hass.async_block_till_done()
    if first:
        await adding
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    assert [value["in"] for value in listed(hass, "en")] == ["Water heater"]


# Files by hand, and no conversation


@pytest.mark.usefixtures("assist")
async def test_manual_copy_beside_the_managed_file_is_warned_about(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    fake_target: FakeTarget,
    fake_fan: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The sentences installed by hand and the ones the entry writes would both be
    read; the log says so, once, and the files are written all the same."""
    await setup_target()
    await copy_sentences(hass, ["Boiler"])

    await add_voice_entry(hass, languages=("en",))
    await setup_target(target="switch.fan")
    await advance(hass, freezer, seconds=VOICE_SYNC_COOLDOWN)

    warnings = timerify_warnings(caplog)
    assert len(warnings) == 1
    assert "manual and managed sentences are both installed" in warnings[0]
    assert listed(hass, "en") == [BOILER, FAN]


async def test_files_are_written_without_conversation_and_nothing_is_reloaded(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A house without the conversation integration has no agent to tell: the files are
    written for when it comes."""
    await setup_target()
    reloads = conversation_reloads(hass)

    entry = await add_voice_entry(hass, languages=("en",))

    assert entry.state is ConfigEntryState.LOADED
    assert not hass.services.has_service("conversation", "reload")
    assert listed(hass, "en") == [BOILER]
    assert reloads == []


# The name of a template, as a pure function


@pytest.mark.parametrize(
    ("name", "escaped"),
    [
        ("Boiler", "Boiler"),
        ("Kid's lamp", "Kid's lamp"),
        ("Back\\slash", "Back\\slash"),
        ("Boiler (main)", "Boiler \\(main\\)"),
        ("A|B [1] {x} <y> me@home", "A\\|B \\[1\\] \\{x\\} \\<y\\> me\\@home"),
        ("A\\(b", "A\\\\\\(b"),
    ],
)
def test_names_are_escaped_only_when_home_assistant_would_read_a_template(
    name: str, escaped: str
) -> None:
    """A name with none of `()[]{}<>|@` is its own text, backslashes included; one with
    any has every such character, and every backslash, escaped."""
    assert escape_template(name) == escaped
