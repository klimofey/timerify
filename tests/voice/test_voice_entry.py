"""The Voice settings entry: added from the menu, it writes the sentence files for the
built-in agent, keeps them in step with the timers, and takes them away again.

The scenarios are the user's: the integrations page, the options of the entry, the
timers and their targets being added, renamed and removed, and what the built-in agent
then answers. Files are written to the configuration directory of the test.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent

from custom_components.timerify.const import (
    CONF_KIND,
    CONF_LANGUAGES,
    CONF_WRITE_SENTENCES,
    DOMAIN,
    KIND_VOICE_SETTINGS,
    MANAGED_HEADER,
    SUBENTRY_INTERVAL,
    VOICE_SYNC_COOLDOWN,
    VOICE_UNIQUE_ID,
)
from custom_components.timerify.voice.files import SentenceFiles
from custom_components.timerify.voice.sentences import InvalidSentences, escape_template

from ..conftest import FakeTarget, SetupTarget
from ..helpers import TARGET_ID, advance, restart
from .helpers import (
    add_voice_entry,
    conversation_reloads,
    converse,
    copy_sentences,
    listed,
    managed_file,
    samples,
    speech,
)

TIME_LEFT = "TimerifyTimeLeft"
BOILER = {"in": "Boiler", "out": "Boiler", "context": {"domain": "switch"}}
"""What the managed file lists for the boiler."""
FAN = {"in": "Fan", "out": "Fan", "context": {"domain": "switch"}}
AN_OLD_TIME = 1_000_000_000
"""A time, as the seconds since 1970, that no file written during a test has."""
TRANSLATIONS = Path(__file__).parents[2] / "custom_components" / DOMAIN / "translations"


def translated(language: str, *path: str) -> str:
    """A text of `translations/<language>.json`, by its path."""
    node: Any = json.loads((TRANSLATIONS / f"{language}.json").read_text("utf-8"))
    for key in path:
        node = node[key]
    return str(node)


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
    assert len(reloads) == 1


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
    assert len(reloads) == 1
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

    def failing_for_russian(language: str, built: dict[str, Any]) -> None:
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

    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING
        and record.name.startswith("custom_components.timerify")
    ]
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
