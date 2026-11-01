"""Entries that an earlier release made: set up, they are brought to the current
version of the data, and what the user did to them stays as it was."""

from typing import Any

import pytest
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.timerify.const import (
    CONF_DEFAULT_DURATION,
    CONF_KIND,
    CONF_LANGUAGES,
    CONF_MODE,
    CONF_TARGET,
    CONF_WORKDAY_SENSOR,
    CONF_WRITE_SENTENCES,
    DOMAIN,
    KIND_VOICE_SETTINGS,
    SUBENTRY_INTERVAL,
    VOICE_UNIQUE_ID,
    DaysMode,
)

from .conftest import FakeTarget, FakeWorkday
from .helpers import TARGET_ID, WEEK, edit_interval

INTERVAL = "interval"
"""The id of the interval that most tests set up."""
RUSSIAN_TITLE = (
    "06:30–07:15, "
    "\N{CYRILLIC CAPITAL LETTER PE}\N{CYRILLIC SMALL LETTER EN}–"
    "\N{CYRILLIC CAPITAL LETTER VE}\N{CYRILLIC SMALL LETTER ES}"
)
"""The title that release 1.0.0 gave the interval of `interval_data` in a house set to
Russian, spelled out so that a change of the labels cannot change what the tests
recognise."""


def interval_data(days: DaysMode = "weekdays") -> dict[str, Any]:
    """The data of the interval from 06:30 to 07:15 that release 1.0.0 stored: the
    days of the week, or the kind of days with none."""
    return {
        "days": days,
        "weekdays": list(WEEK) if days == "weekdays" else [],
        "start": "06:30",
        "end": "07:15",
        "settings": {},
    }


def interval(
    title: str, data: dict[str, Any] | None = None, subentry_id: str = INTERVAL
) -> ConfigSubentryData:
    """An interval named `title`, of the weekdays from 06:30 to 07:15 unless `data`
    says otherwise."""
    return ConfigSubentryData(
        data=interval_data() if data is None else data,
        subentry_id=subentry_id,
        subentry_type=SUBENTRY_INTERVAL,
        title=title,
        unique_id=None,
    )


async def set_up_timer(
    hass: HomeAssistant,
    *intervals: ConfigSubentryData,
    minor_version: int = 1,
    workday_sensor: str | None = None,
) -> MockConfigEntry:
    """Set up a timer with `intervals` whose entry is at `minor_version`: the first is
    how release 1.0.0 stored it. Returns the entry once it is set up, so a first one
    has been migrated by then."""
    options: dict[str, Any] = {
        CONF_TARGET: TARGET_ID,
        CONF_MODE: "strict",
        CONF_DEFAULT_DURATION: 45,
    }
    if workday_sensor is not None:
        options[CONF_WORKDAY_SENSOR] = workday_sensor
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=minor_version,
        title="Boiler",
        options=options,
        subentries_data=intervals,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_a_title_generated_in_english_is_marked(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """An interval that the house's language named stays named as it was, and an edit
    can now tell that Timerify named it."""
    hass.config.language = "en"

    entry = await set_up_timer(hass, interval("06:30–07:15, Mon–Sun"))

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    subentry = entry.subentries[INTERVAL]
    assert subentry.title == "06:30–07:15, Mon–Sun"
    assert subentry.data["generated_title"] == "06:30–07:15, Mon–Sun"


async def test_a_title_generated_in_russian_is_marked_in_an_english_house(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """The house was set to Russian when the interval was made and is English now: the
    title is still Timerify's, so the first edit renames it in English."""
    hass.config.language = "en"

    entry = await set_up_timer(hass, interval(RUSSIAN_TITLE))

    assert entry.subentries[INTERVAL].data["generated_title"] == RUSSIAN_TITLE
    await edit_interval(hass, entry, INTERVAL, end="07:30")
    subentry = entry.subentries[INTERVAL]
    assert subentry.title == "06:30–07:30, Mon–Sun"
    assert subentry.data["generated_title"] == "06:30–07:30, Mon–Sun"


async def test_a_title_of_working_days_is_marked(
    hass: HomeAssistant, fake_target: FakeTarget, fake_workday: FakeWorkday
) -> None:
    """The title of an interval that follows the Workday sensor names the kind of days,
    not the weekdays, and is marked as well."""
    hass.config.language = "en"

    entry = await set_up_timer(
        hass,
        interval("06:30–07:15, Working days", interval_data("workdays")),
        workday_sensor=fake_workday.entity_id,
    )

    assert entry.state is ConfigEntryState.LOADED
    subentry = entry.subentries[INTERVAL]
    assert subentry.data["generated_title"] == "06:30–07:15, Working days"


async def test_a_title_the_user_chose_is_not_marked(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """A name the user gave the interval is theirs: nothing is added to the interval,
    and an edit keeps the name."""
    entry = await set_up_timer(hass, interval("Morning"))

    assert entry.minor_version == 2
    assert "generated_title" not in entry.subentries[INTERVAL].data
    await edit_interval(hass, entry, INTERVAL, end="07:30")
    subentry = entry.subentries[INTERVAL]
    assert subentry.title == "Morning"
    assert subentry.data["end"] == "07:30"
    assert "generated_title" not in subentry.data


@pytest.mark.parametrize(
    ("odd", "change"),
    [
        pytest.param({"weekdays": ["mon", "someday"]}, {}, id="a-day-that-is-not-one"),
        pytest.param({"days": "fortnightly"}, {}, id="days-that-are-no-kind"),
        pytest.param({}, {"end"}, id="a-time-that-is-missing"),
    ],
)
async def test_an_interval_no_title_can_be_made_of_is_left_unmarked(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    odd: dict[str, Any],
    change: set[str],
) -> None:
    """Data that was edited by hand to something that is no interval costs that
    interval its mark and no more: the others are marked and the entry moves on."""
    broken = {k: v for k, v in {**interval_data(), **odd}.items() if k not in change}

    entry = await set_up_timer(
        hass,
        interval("06:30–07:15, Mon–Sun", subentry_id="whole"),
        interval("06:30–07:15, Mon–Sun", broken, subentry_id="odd"),
        workday_sensor=fake_workday.entity_id,
    )

    assert entry.minor_version == 2
    assert entry.subentries["whole"].data["generated_title"] == "06:30–07:15, Mon–Sun"
    assert "generated_title" not in entry.subentries["odd"].data


async def test_an_interval_without_the_mark_is_named_again_by_an_edit(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """An entry of the current version can hold an interval with no mark: release 1.0.0
    made or edited it after a downgrade. Its title is the one its data makes, so an
    edit names it again and marks it."""
    hass.config.language = "en"
    entry = await set_up_timer(hass, interval("06:30–07:15, Mon–Sun"), minor_version=2)
    assert "generated_title" not in entry.subentries[INTERVAL].data

    await edit_interval(hass, entry, INTERVAL, end="07:30")

    subentry = entry.subentries[INTERVAL]
    assert subentry.title == "06:30–07:30, Mon–Sun"
    assert subentry.data["generated_title"] == "06:30–07:30, Mon–Sun"


async def test_a_title_the_user_chose_is_kept_in_an_entry_of_the_current_version(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """The fallback for an interval with no mark takes a name that differs from the one
    its data makes for the user's."""
    entry = await set_up_timer(hass, interval("Morning"), minor_version=2)

    await edit_interval(hass, entry, INTERVAL, end="07:30")

    subentry = entry.subentries[INTERVAL]
    assert subentry.title == "Morning"
    assert "generated_title" not in subentry.data


async def test_the_voice_settings_entry_is_migrated_too(hass: HomeAssistant) -> None:
    """The voice settings are an entry of the same integration, with no intervals:
    it loads as it did and moves to the current version."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        unique_id=VOICE_UNIQUE_ID,
        options={
            CONF_KIND: KIND_VOICE_SETTINGS,
            CONF_WRITE_SENTENCES: False,
            CONF_LANGUAGES: ["en"],
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
