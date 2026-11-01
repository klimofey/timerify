"""Entries that an earlier release made: set up, they are brought to the current
version of the data, and what the user did to them stays as it was."""

from typing import Any

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
from custom_components.timerify.schedule import async_title_labels, interval_title

from .conftest import FakeTarget, FakeWorkday
from .helpers import TARGET_ID, WEEK, edit_interval


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


async def set_up_release_1_0_0(
    hass: HomeAssistant,
    title: str,
    data: dict[str, Any] | None = None,
    *,
    workday_sensor: str | None = None,
) -> tuple[MockConfigEntry, str]:
    """Set up a timer as release 1.0.0 stored it, with one interval named `title`.
    Returns the entry, whose data version is the first, and the id of the interval."""
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
        minor_version=1,
        title="Boiler",
        options=options,
        subentries_data=[
            ConfigSubentryData(
                data=interval_data() if data is None else data,
                subentry_id="interval",
                subentry_type=SUBENTRY_INTERVAL,
                title=title,
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, "interval"


async def test_a_title_generated_in_english_is_marked(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """An interval that the house's language named stays named as it was, and an edit
    can now tell that Timerify named it."""
    hass.config.language = "en"

    entry, interval = await set_up_release_1_0_0(hass, "06:30–07:15, Mon–Sun")

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    subentry = entry.subentries[interval]
    assert subentry.title == "06:30–07:15, Mon–Sun"
    assert subentry.data["generated_title"] == "06:30–07:15, Mon–Sun"


async def test_a_title_generated_in_russian_is_marked_in_an_english_house(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """The house was set to Russian when the interval was made and is English now: the
    title is still Timerify's, so the first edit renames it in English."""
    hass.config.language = "en"
    russian = interval_title(interval_data(), await async_title_labels(hass, "ru"))
    assert russian != "06:30–07:15, Mon–Sun"

    entry, interval = await set_up_release_1_0_0(hass, russian)

    assert entry.subentries[interval].data["generated_title"] == russian
    await edit_interval(hass, entry, interval, end="07:30")
    subentry = entry.subentries[interval]
    assert subentry.title == "06:30–07:30, Mon–Sun"
    assert subentry.data["generated_title"] == "06:30–07:30, Mon–Sun"


async def test_a_title_of_working_days_is_marked(
    hass: HomeAssistant, fake_target: FakeTarget, fake_workday: FakeWorkday
) -> None:
    """The title of an interval that follows the Workday sensor names the kind of days,
    not the weekdays, and is marked as well."""
    hass.config.language = "en"

    entry, interval = await set_up_release_1_0_0(
        hass,
        "06:30–07:15, Working days",
        interval_data("workdays"),
        workday_sensor=fake_workday.entity_id,
    )

    assert entry.state is ConfigEntryState.LOADED
    subentry = entry.subentries[interval]
    assert subentry.data["generated_title"] == "06:30–07:15, Working days"


async def test_a_title_the_user_chose_is_not_marked(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """A name the user gave the interval is theirs: nothing is added to the interval,
    and an edit keeps the name."""
    entry, interval = await set_up_release_1_0_0(hass, "Morning")

    assert entry.minor_version == 2
    assert "generated_title" not in entry.subentries[interval].data
    await edit_interval(hass, entry, interval, end="07:30")
    subentry = entry.subentries[interval]
    assert subentry.title == "Morning"
    assert subentry.data["end"] == "07:30"
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
