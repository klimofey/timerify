"""Schedule intervals as the user manages them on the integration page: added, edited
and deleted one by one, each change reloading the timer without disturbing it."""

from dataclasses import dataclass
from typing import Any

import probatio
import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.fan.const import FanEntityFeature
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import Selector
from homeassistant.helpers.translation import async_get_translations

from custom_components.timerify.const import DOMAIN, SUBENTRY_INTERVAL
from custom_components.timerify.schedule import interval_title
from custom_components.timerify.services import SETTINGS_SCHEMA

from .conftest import (
    SWITCH_SERVICES,
    FakeTarget,
    FakeWorkday,
    ProvideTarget,
    SetupTarget,
)
from .helpers import (
    AC_ID,
    AC_WITHOUT_FAN_MODE,
    NUMBER,
    TURN_OFF,
    TURN_ON,
    WEEK,
    add_interval,
    advance,
    edit_interval,
    prefilled,
    retitle_interval,
    set_number,
    state_of,
    submit_interval,
)

pytestmark = pytest.mark.usefixtures("hass_storage")

FAN_ID = "fan.vent"


@pytest.fixture
def fake_fan(provide_target: ProvideTarget) -> FakeTarget:
    """`fan.vent` on a device called Vent, switched off: a fan with a speed."""
    return provide_target(
        FAN_ID,
        SWITCH_SERVICES,
        name="Vent",
        capability_attributes={
            "supported_features": int(
                FanEntityFeature.TURN_ON
                | FanEntityFeature.TURN_OFF
                | FanEntityFeature.SET_SPEED
            )
        },
    )


async def open_form(
    hass: HomeAssistant,
    entry: ConfigEntry,
    source: str = "user",
    subentry_id: str | None = None,
) -> Any:
    """Press "Add schedule interval" (or "Edit" on one) and return the form shown."""
    context: Any = {"source": source}
    if subentry_id is not None:
        context["subentry_id"] = subentry_id
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_INTERVAL), context=context
    )
    assert result["type"] is FlowResultType.FORM
    return result


def fields_of(schema: probatio.Schema) -> dict[str, Any]:
    """The fields of a form by name, each with what validates it."""
    return {str(marker): validator for marker, validator in schema.schema.items()}


def settings_fields(form: Any) -> dict[str, Selector[Any]]:
    """The fields of the form's settings section by name; none when it has no such
    section."""
    validator = fields_of(form["data_schema"]).get("settings")
    return {} if validator is None else fields_of(validator.schema)


def frontend_fields(form: Any) -> list[dict[str, Any]]:
    """The fields of the form as Home Assistant sends them to the frontend."""
    return probatio.to_field_list(
        form["data_schema"], custom_serializer=cv.custom_serializer
    )


def settings_are_open(form: Any) -> bool:
    """Whether the frontend draws the settings section expanded."""
    (settings,) = (f for f in frontend_fields(form) if f["name"] == "settings")
    return bool(settings["expanded"])


async def test_adding_an_interval_stores_it_with_a_readable_title(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The interval is a subentry of the timer, named by its times and days; the
    days come back in week order."""
    entry = await setup_target()

    subentry_id = await add_interval(
        hass,
        entry,
        start="06:30",
        end="07:15",
        weekdays=["sun", "mon", "tue", "wed", "thu"],
    )

    subentry = entry.subentries[subentry_id]
    assert subentry.subentry_type == "interval"
    assert subentry.title == "06:30–07:15, Sun–Thu"
    assert dict(subentry.data) == {
        "days": "weekdays",
        "weekdays": ["mon", "tue", "wed", "thu", "sun"],
        "start": "06:30",
        "end": "07:15",
        "settings": {},
        "generated_title": "06:30–07:15, Sun–Thu",
    }


@pytest.mark.parametrize(
    ("weekdays", "title"),
    [
        (WEEK, "22:00–06:00, Mon–Sun"),
        (["fri", "sat"], "22:00–06:00, Fri, Sat"),
        (["mon", "wed"], "22:00–06:00, Mon, Wed"),
        (["mon", "tue", "wed", "thu"], "22:00–06:00, Mon–Thu"),
        (["sat", "sun", "mon"], "22:00–06:00, Sat–Mon"),
        (["mon", "tue", "wed", "fri", "sun"], "22:00–06:00, Sun–Wed, Fri"),
        (["tue", "thu", "fri", "sat"], "22:00–06:00, Tue, Thu–Sat"),
        (["sun", "mon"], "22:00–06:00, Mon, Sun"),
        (["wed", "wed", "mon"], "22:00–06:00, Mon, Wed"),
    ],
)
async def test_interval_titles(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    weekdays: list[str],
    title: str,
) -> None:
    """A run of three days or more is written as a range, also across the end of the
    week; an interval that ends before it starts runs through the night."""
    entry = await setup_target()

    subentry_id = await add_interval(
        hass, entry, start="22:00", end="06:00", weekdays=weekdays
    )

    assert entry.subentries[subentry_id].title == title


@pytest.mark.parametrize(
    ("days", "title"),
    [
        ("workdays", "06:30–07:15, Working days"),
        ("non_workdays", "06:30–07:15, Days off"),
    ],
)
def test_a_title_names_intervals_of_working_days_by_their_label(
    days: str, title: str
) -> None:
    """An interval that follows the Workday sensor has no weekdays to list; it is
    named by the words given for its kind of days."""
    labels = {"workdays": "Working days", "non_workdays": "Days off"}
    data = {"days": days, "start": "06:30", "end": "07:15", "settings": {}}

    assert interval_title(data, labels) == title


async def test_title_is_in_the_language_of_the_house(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The weekday names of the title are those of the language of the house."""
    entry = await setup_target()
    hass.config.language = "ru"
    words = await async_get_translations(hass, "ru", "selector", [DOMAIN])
    monday, sunday = (
        words[f"component.{DOMAIN}.selector.weekday.options.{day}"]
        for day in ("mon", "sun")
    )

    subentry_id = await add_interval(hass, entry, start="22:00", end="06:00")

    assert monday != "Mon"
    assert entry.subentries[subentry_id].title == f"22:00–06:00, {monday}–{sunday}"


async def test_new_interval_form_offers_every_day_and_no_times(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The form lists the kind of days, the weekdays, the start and the end, in that
    order; a target without a Workday sensor starts on its weekdays, every day is
    ticked and the times are left to the user: they hold nothing, and the frontend
    shows midnight for a required time that nobody has set."""
    entry = await setup_target()

    form = await open_form(hass, entry)

    schema = form["data_schema"]
    assert list(fields_of(schema)) == ["days", "weekdays", "start", "end"]
    assert prefilled(schema) == {
        "days": "weekdays",
        "weekdays": list(WEEK),
        "start": "00:00:00",
        "end": "00:00:00",
    }
    days = fields_of(schema)["days"]
    assert days.config["options"] == ["weekdays", "workdays", "non_workdays"]
    assert days.config["translation_key"] == "interval_days"
    weekdays = fields_of(schema)["weekdays"]
    assert weekdays.config["options"] == list(WEEK)
    assert weekdays.config["multiple"] is True
    assert weekdays.config["translation_key"] == "weekday"


async def test_submitting_the_form_untouched_is_refused_not_added_at_midnight(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Pressing Submit on the new form sends midnight for both times, as the frontend
    fills them: that is an interval that starts and ends together, and the form says so
    beside the end."""
    entry = await setup_target()
    form = await open_form(hass, entry)

    result = await hass.config_entries.subentries.async_configure(
        form["flow_id"], prefilled(form["data_schema"])
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"end": "same_start_and_end"}
    assert not entry.subentries


@pytest.mark.parametrize(
    ("fields", "field", "error"),
    [
        ({"weekdays": []}, "weekdays", "no_weekdays"),
        ({"end": "06:30"}, "end", "same_start_and_end"),
        ({"start": "06:30:00", "end": "06:30"}, "end", "same_start_and_end"),
        ({"start": "06:30:15"}, "start", "whole_minutes_only"),
        ({"end": "07:15:30"}, "end", "whole_minutes_only"),
    ],
)
async def test_invalid_intervals_are_refused(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    fields: dict[str, Any],
    field: str,
    error: str,
) -> None:
    """The form is shown again with the reason beside the field; nothing is added."""
    entry = await setup_target()
    values: dict[str, Any] = {"start": "06:30", "end": "07:15", **fields}

    result = await submit_interval(hass, entry, **values)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {field: error}
    assert not entry.subentries
    texts = await async_get_translations(hass, "en", "config_subentries", [DOMAIN])
    assert texts[f"component.{DOMAIN}.config_subentries.interval.error.{error}"]


async def test_a_refused_form_keeps_what_was_typed(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The user corrects the one mistake instead of filling in the form again."""
    entry = await setup_target()

    result = await submit_interval(
        hass, entry, start="06:30", end="06:30", weekdays=["mon", "tue"]
    )

    assert prefilled(result["data_schema"]) == {
        "days": "weekdays",
        "weekdays": ["mon", "tue"],
        "start": "06:30",
        "end": "06:30",
    }


async def test_a_refused_form_keeps_the_settings_that_were_typed_and_shows_them(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The settings stay in the form, and the section is open so that the user sees
    the fields an error about them is about."""
    entry = await setup_target(target=AC_ID)

    result = await submit_interval(
        hass,
        entry,
        start="06:30",
        end="06:30",
        settings={"hvac_mode": "cool", "temperature": 24},
    )

    assert prefilled(result["data_schema"])["settings"] == {
        "hvac_mode": "cool",
        "temperature": 24,
    }
    assert settings_are_open(result)


async def test_times_from_the_ui_are_stored_as_hours_and_minutes(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The time picker sends seconds; a whole minute is stored without them."""
    entry = await setup_target()

    subentry_id = await add_interval(hass, entry, start="06:30:00", end="07:15:00")

    subentry = entry.subentries[subentry_id]
    assert subentry.data["start"] == "06:30"
    assert subentry.data["end"] == "07:15"
    assert subentry.title == "06:30–07:15, Mon–Sun"


async def test_form_reaches_the_frontend(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The form converts to the fields the frontend draws, in order, with the
    settings in a section that starts closed and has no value of its own: a default
    on the section would hide the settings that are in it."""
    entry = await setup_target(target=AC_ID)
    form = await open_form(hass, entry)

    fields = frontend_fields(form)

    assert [field["name"] for field in fields] == [
        "days",
        "weekdays",
        "start",
        "end",
        "settings",
    ]
    assert fields[-1]["type"] == "expandable"
    assert fields[-1]["expanded"] is False
    assert "default" not in fields[-1]
    assert [field["name"] for field in fields[-1]["schema"]] == [
        "hvac_mode",
        "temperature",
        "fan_mode",
    ]


async def test_settings_section_offers_what_the_ac_can_do(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The modes and the range are those of the air conditioner; "off" is not a way
    to turn it on."""
    entry = await setup_target(target=AC_ID)

    fields = settings_fields(await open_form(hass, entry))

    assert list(fields) == ["hvac_mode", "temperature", "fan_mode"]
    assert fields["hvac_mode"].config["options"] == ["heat", "cool", "fan_only"]
    assert fields["hvac_mode"].config["translation_key"] == "hvac_mode"
    assert fields["temperature"].config["min"] == 16
    assert fields["temperature"].config["max"] == 30
    assert fields["temperature"].config["step"] == 0.5
    assert fields["fan_mode"].config["options"] == ["auto", "low", "high"]


async def test_settings_are_offered_for_an_ac_that_is_unavailable(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """What the device can do is known while it is away, so the interval can be set
    up then."""
    entry = await setup_target(target=AC_ID)
    await fake_climate.set_state("unavailable")

    fields = settings_fields(await open_form(hass, entry))

    assert list(fields) == ["hvac_mode", "temperature", "fan_mode"]


async def test_a_fan_with_a_speed_offers_it_in_percent(
    hass: HomeAssistant, fake_fan: FakeTarget, setup_target: SetupTarget
) -> None:
    """A fan with a speed offers it as a whole number of percent from 1 to 100, and
    nothing that the fan cannot do."""
    entry = await setup_target(target=FAN_ID)

    fields = settings_fields(await open_form(hass, entry))

    assert list(fields) == ["percentage"]
    assert fields["percentage"].config["min"] == 1
    assert fields["percentage"].config["max"] == 100
    assert fields["percentage"].config["step"] == 1


async def test_a_plain_switch_gets_no_settings_section(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A switch has nothing to be set up with, so the form has no such section."""
    entry = await setup_target()

    form = await open_form(hass, entry)

    assert "settings" not in fields_of(form["data_schema"])


async def test_a_target_that_is_gone_gets_no_settings_section(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """With nothing known about the entity, nothing is offered."""
    entry = await setup_target(target=AC_ID)
    er.async_get(hass).async_remove(AC_ID)
    hass.states.async_remove(AC_ID)
    await hass.async_block_till_done()

    form = await open_form(hass, entry)

    assert "settings" not in fields_of(form["data_schema"])


async def test_interval_settings_are_validated_and_stored(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The interval keeps the settings the user chose and none of the others."""
    entry = await setup_target(target=AC_ID)

    subentry_id = await add_interval(
        hass,
        entry,
        start="06:30",
        end="07:15",
        settings={"hvac_mode": "cool", "temperature": 24},
    )

    assert dict(entry.subentries[subentry_id].data["settings"]) == {
        "hvac_mode": "cool",
        "temperature": 24,
    }


async def test_settings_are_typed_as_the_services_type_them(
    hass: HomeAssistant, fake_fan: FakeTarget, setup_target: SetupTarget
) -> None:
    """The number box gives 60.0; a speed is a whole number of percent wherever it
    comes from, so the same setting is never stored in two types."""
    entry = await setup_target(target=FAN_ID)

    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings={"percentage": 60.0}
    )

    stored = entry.subentries[subentry_id].data["settings"]
    assert stored == {"percentage": 60}
    assert type(stored["percentage"]) is int


async def test_a_fraction_of_a_percent_is_refused(
    hass: HomeAssistant, fake_fan: FakeTarget, setup_target: SetupTarget
) -> None:
    """A speed of 60.5 percent is not one the fan takes."""
    entry = await setup_target(target=FAN_ID)

    result = await submit_interval(
        hass, entry, start="06:30", end="07:15", settings={"percentage": 60.5}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "settings_not_whole"}
    assert not entry.subentries


async def test_settings_the_ac_no_longer_takes_are_refused(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The air conditioner stops offering a mode while the form is open; the mode
    that was picked is refused rather than stored."""
    entry = await setup_target(target=AC_ID)
    form = await open_form(hass, entry)
    fake_climate.capability_attributes["hvac_modes"] = ["off", "heat"]
    await fake_climate.set_state("off")

    result = await hass.config_entries.subentries.async_configure(
        form["flow_id"],
        {
            "weekdays": list(WEEK),
            "start": "06:30",
            "end": "07:15",
            "settings": {"hvac_mode": "cool"},
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "settings_not_supported"}
    assert not entry.subentries


async def test_every_field_of_the_form_is_labelled(hass: HomeAssistant) -> None:
    """Adding and editing show a text for each field, also for every setting that a
    target of some domain can take."""
    texts = await async_get_translations(hass, "en", "config_subentries", [DOMAIN])
    prefix = f"component.{DOMAIN}.config_subentries.interval"
    settings = {str(name) for name in SETTINGS_SCHEMA}

    for step in ("user", "reconfigure"):
        step_prefix = f"{prefix}.step.{step}"
        assert texts[f"{step_prefix}.title"]
        for name in ("days", "weekdays", "start", "end"):
            assert texts[f"{step_prefix}.data.{name}"], (step, name)
            assert texts[f"{step_prefix}.data_description.{name}"], (step, name)
        assert texts[f"{step_prefix}.sections.settings.name"]
        for name in settings:
            section_prefix = f"{step_prefix}.sections.settings"
            assert texts[f"{section_prefix}.data.{name}"], (step, name)
    for flow in ("user", "reconfigure"):
        assert texts[f"{prefix}.initiate_flow.{flow}"]
    assert texts[f"{prefix}.entry_type"]


async def test_editing_an_interval_updates_data_and_title(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The form of an interval is filled in with what it holds; changing the end
    changes the interval and its name."""
    entry = await setup_target()
    subentry_id = await add_interval(hass, entry, start="06:30", end="07:15")

    result = await edit_interval(hass, entry, subentry_id, end="07:30")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    subentry = entry.subentries[subentry_id]
    assert dict(subentry.data) == {
        "days": "weekdays",
        "weekdays": list(WEEK),
        "start": "06:30",
        "end": "07:30",
        "settings": {},
        "generated_title": "06:30–07:30, Mon–Sun",
    }
    assert subentry.title == "06:30–07:30, Mon–Sun"


async def test_edit_form_shows_the_current_values(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """Days, times and settings are there when the user opens an interval."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass,
        entry,
        start="06:30",
        end="07:15",
        weekdays=["sat", "sun"],
        settings={"hvac_mode": "heat", "temperature": 22.5},
    )

    form = await open_form(hass, entry, "reconfigure", subentry_id)

    assert form["step_id"] == "reconfigure"
    assert prefilled(form["data_schema"]) == {
        "days": "weekdays",
        "weekdays": ["sat", "sun"],
        "start": "06:30",
        "end": "07:15",
        "settings": {"hvac_mode": "heat", "temperature": 22.5},
    }


async def test_settings_are_open_when_the_form_shows_some(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The section is closed on a new interval and on one without settings, and open
    on an interval that has some, so that the user sees what it does."""
    entry = await setup_target(target=AC_ID)
    with_settings = await add_interval(
        hass, entry, start="06:30", end="07:15", settings={"hvac_mode": "heat"}
    )
    without_settings = await add_interval(hass, entry, start="08:00", end="09:00")

    assert not settings_are_open(await open_form(hass, entry))
    assert settings_are_open(await open_form(hass, entry, "reconfigure", with_settings))
    assert not settings_are_open(
        await open_form(hass, entry, "reconfigure", without_settings)
    )


async def test_an_interval_with_only_settings_not_offered_shows_them_closed(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The section opens to show settings, and the form shows none of this interval:
    the one it has is a setting the AC no longer offers, so the section stays closed."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings={"fan_mode": "low"}
    )
    assert settings_are_open(await open_form(hass, entry, "reconfigure", subentry_id))
    fake_climate.capability_attributes["supported_features"] = AC_WITHOUT_FAN_MODE
    await fake_climate.set_state("off")

    form = await open_form(hass, entry, "reconfigure", subentry_id)

    assert not settings_are_open(form)


async def test_editing_the_days_renames_the_interval(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The days are part of the name, so a new set of days is a new name."""
    entry = await setup_target()
    subentry_id = await add_interval(hass, entry, start="06:30", end="07:15")

    await edit_interval(hass, entry, subentry_id, weekdays=["sat", "sun"])

    subentry = entry.subentries[subentry_id]
    assert subentry.data["weekdays"] == ["sat", "sun"]
    assert subentry.title == "06:30–07:15, Sat, Sun"


async def test_editing_keeps_a_title_the_user_chose(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A name the user gave the interval outlives edits of what it holds."""
    entry = await setup_target()
    subentry_id = await add_interval(hass, entry, start="06:30", end="07:15")
    hass.config_entries.async_update_subentry(
        entry, entry.subentries[subentry_id], title="Morning"
    )
    await hass.async_block_till_done()

    await edit_interval(hass, entry, subentry_id, end="07:30")

    subentry = entry.subentries[subentry_id]
    assert subentry.data["end"] == "07:30"
    assert subentry.title == "Morning"


async def test_a_new_interval_is_marked_as_titled_by_timerify(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The interval keeps the title it was given, to tell later whether it is still
    the one Timerify made."""
    entry = await setup_target()

    subentry_id = await add_interval(hass, entry, start="06:30", end="07:15")

    subentry = entry.subentries[subentry_id]
    assert subentry.title == "06:30–07:15, Mon–Sun"
    assert subentry.data["generated_title"] == subentry.title


async def test_an_edit_after_the_language_changed_renames_the_interval(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """An interval that Timerify named in Russian is named in English by the first
    edit after the house is set to English, on the integration page and on its
    switch alike; the mark follows the new name."""
    entry = await setup_target()
    hass.config.language = "ru"
    subentry_id = await add_interval(hass, entry, start="06:30", end="07:15")
    assert entry.subentries[subentry_id].title != "06:30–07:15, Mon–Sun"
    hass.config.language = "en"

    await edit_interval(hass, entry, subentry_id, end="07:30")

    subentry = entry.subentries[subentry_id]
    assert subentry.title == "06:30–07:30, Mon–Sun"
    assert subentry.data["generated_title"] == subentry.title
    (switch,) = (
        registered
        for registered in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if registered.config_subentry_id == subentry_id
    )
    state = hass.states.get(switch.entity_id)
    assert state is not None
    assert state.name == "Boiler Schedule 06:30–07:30, Mon–Sun"


async def test_a_house_language_without_translations_names_in_english(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Timerify has no German: Home Assistant falls back to English, so an interval is
    named in English there, and the edit that follows a move from Russian to German
    names it so."""
    entry = await setup_target()
    hass.config.language = "ru"
    subentry_id = await add_interval(hass, entry, start="06:30", end="07:15")
    assert entry.subentries[subentry_id].title != "06:30–07:15, Mon–Sun"
    hass.config.language = "de"

    await edit_interval(hass, entry, subentry_id, end="07:30")

    subentry = entry.subentries[subentry_id]
    assert subentry.title == "06:30–07:30, Mon–Sun"
    assert subentry.data["generated_title"] == "06:30–07:30, Mon–Sun"
    other = await add_interval(hass, entry, start="08:00", end="09:00")
    assert entry.subentries[other].title == "08:00–09:00, Mon–Sun"


async def test_a_renamed_interval_keeps_its_name_after_the_language_changed(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The name is the user's from the rename on: an edit keeps it, though it was the
    name Timerify gave, in a language that the house no longer speaks."""
    entry = await setup_target()
    hass.config.language = "ru"
    subentry_id = await add_interval(hass, entry, start="06:30", end="07:15")
    await retitle_interval(hass, entry, subentry_id, "Morning")
    hass.config.language = "en"

    await edit_interval(hass, entry, subentry_id, end="07:30")

    subentry = entry.subentries[subentry_id]
    assert subentry.title == "Morning"
    assert subentry.data["end"] == "07:30"
    assert "generated_title" not in subentry.data


async def test_editing_keeps_the_settings_it_is_not_asked_to_change(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """The closed settings section still carries the settings of the interval."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass,
        entry,
        start="06:30",
        end="07:15",
        settings={"hvac_mode": "cool", "temperature": 24, "fan_mode": "low"},
    )

    await edit_interval(hass, entry, subentry_id, end="07:30")

    assert dict(entry.subentries[subentry_id].data["settings"]) == {
        "hvac_mode": "cool",
        "temperature": 24,
        "fan_mode": "low",
    }


async def test_editing_keeps_a_setting_the_ac_no_longer_offers(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """An update of the AC's integration drops its fan modes. The form no longer shows
    the fan mode, and editing the interval does not lose the one it has: the AC may
    offer it again."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass,
        entry,
        start="06:30",
        end="07:15",
        settings={"hvac_mode": "cool", "temperature": 24, "fan_mode": "low"},
    )
    fake_climate.capability_attributes["supported_features"] = AC_WITHOUT_FAN_MODE
    await fake_climate.set_state("off")
    form = await open_form(hass, entry, "reconfigure", subentry_id)
    assert "fan_mode" not in settings_fields(form)

    await edit_interval(hass, entry, subentry_id, end="07:30")

    assert dict(entry.subentries[subentry_id].data["settings"]) == {
        "hvac_mode": "cool",
        "temperature": 24,
        "fan_mode": "low",
    }


async def test_editing_changes_the_settings_shown_beside_a_kept_one(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """A setting the form shows has the user's value, also when it is emptied; only the
    one the form does not show is kept as it is."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass,
        entry,
        start="06:30",
        end="07:15",
        settings={"hvac_mode": "cool", "temperature": 24, "fan_mode": "low"},
    )
    fake_climate.capability_attributes["supported_features"] = AC_WITHOUT_FAN_MODE
    await fake_climate.set_state("off")

    await edit_interval(
        hass, entry, subentry_id, settings={"hvac_mode": "heat", "temperature": 21}
    )
    assert dict(entry.subentries[subentry_id].data["settings"]) == {
        "hvac_mode": "heat",
        "temperature": 21,
        "fan_mode": "low",
    }

    await edit_interval(hass, entry, subentry_id, settings={})
    assert dict(entry.subentries[subentry_id].data["settings"]) == {"fan_mode": "low"}


async def test_editing_keeps_every_setting_while_the_ac_is_gone(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """With the AC deleted the form offers no settings at all, and editing the times
    of the interval still keeps all it has: the AC may be added again."""
    entry = await setup_target(target=AC_ID)
    settings = {"hvac_mode": "cool", "temperature": 24, "fan_mode": "low"}
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=settings
    )
    await fake_climate.delete()

    await edit_interval(hass, entry, subentry_id, end="07:30")

    assert dict(entry.subentries[subentry_id].data["settings"]) == settings


async def test_editing_can_remove_the_settings(
    hass: HomeAssistant, fake_climate: FakeTarget, setup_target: SetupTarget
) -> None:
    """Emptying the settings turns the target on as it is."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass,
        entry,
        start="06:30",
        end="07:15",
        settings={"hvac_mode": "cool", "temperature": 24},
    )

    await edit_interval(hass, entry, subentry_id, settings={})

    assert dict(entry.subentries[subentry_id].data["settings"]) == {}


@dataclass(frozen=True)
class LostValue:
    """A value an interval holds and the AC then stops taking: the mode it no longer
    lists, a temperature above its narrower range."""

    held: dict[str, Any]
    """What the interval turns the AC on with."""
    listed: dict[str, Any]
    """What the AC's integration lists after an update."""
    taken: dict[str, Any]
    """A value of the same setting that the AC takes then."""
    field: dict[str, Any]
    """What the field of the setting offers meanwhile: the values the AC lists and the
    one the interval holds, nothing beyond."""


LOST_VALUES = [
    pytest.param(
        LostValue(
            held={"hvac_mode": "cool"},
            listed={"hvac_modes": ["off", "heat"]},
            taken={"hvac_mode": "heat"},
            field={"options": ["heat", "cool"]},
        ),
        id="a-mode-the-ac-dropped",
    ),
    pytest.param(
        LostValue(
            held={"temperature": 24},
            listed={"max_temp": 22},
            taken={"temperature": 22},
            field={"min": 16, "max": 24},
        ),
        id="a-temperature-above-the-new-maximum",
    ),
]


async def hold_a_value_the_ac_no_longer_lists(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    lost: LostValue,
) -> tuple[ConfigEntry, str]:
    """An interval that turns the AC on with the value, then an update of the AC's
    integration that lists less: the entry and the id of the interval."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", settings=lost.held
    )
    fake_climate.capability_attributes.update(lost.listed)
    await fake_climate.set_state("off")
    return entry, subentry_id


@pytest.mark.parametrize("lost", LOST_VALUES)
async def test_the_form_shows_a_value_the_ac_no_longer_lists(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    lost: LostValue,
) -> None:
    """The warning sends the user to the form of the interval. The setting there holds
    what the interval holds, and its field takes that value, so that the user sees it
    and changes it."""
    entry, subentry_id = await hold_a_value_the_ac_no_longer_lists(
        hass, fake_climate, setup_target, lost
    )

    form = await open_form(hass, entry, "reconfigure", subentry_id)

    (name,) = lost.held
    assert prefilled(form["data_schema"])["settings"] == lost.held
    assert settings_are_open(form)
    selector = settings_fields(form)[name]
    assert {key: selector.config[key] for key in lost.field} == lost.field
    selector(lost.held[name])


@pytest.mark.parametrize("lost", LOST_VALUES)
async def test_submitting_a_value_the_ac_no_longer_lists_is_refused_in_words(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    lost: LostValue,
) -> None:
    """The form as it is shown is submitted unchanged: the user is told in words that
    the AC cannot take the setting, the form shows the value still, and nothing is
    saved."""
    entry, subentry_id = await hold_a_value_the_ac_no_longer_lists(
        hass, fake_climate, setup_target, lost
    )
    before = entry.subentries[subentry_id].as_dict()
    form = await open_form(hass, entry, "reconfigure", subentry_id)

    result = await hass.config_entries.subentries.async_configure(
        form["flow_id"], prefilled(form["data_schema"])
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "settings_not_supported"}
    assert prefilled(result["data_schema"])["settings"] == lost.held
    assert settings_are_open(result)
    assert entry.subentries[subentry_id].as_dict() == before


@pytest.mark.parametrize("lost", LOST_VALUES)
async def test_a_value_the_ac_takes_replaces_one_it_no_longer_lists(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    lost: LostValue,
) -> None:
    """After the refusal the user picks a value the AC takes, and the interval is
    saved with it."""
    entry, subentry_id = await hold_a_value_the_ac_no_longer_lists(
        hass, fake_climate, setup_target, lost
    )
    form = await open_form(hass, entry, "reconfigure", subentry_id)
    refused = await hass.config_entries.subentries.async_configure(
        form["flow_id"], prefilled(form["data_schema"])
    )
    assert refused["errors"] == {"base": "settings_not_supported"}

    result = await hass.config_entries.subentries.async_configure(
        form["flow_id"], {**prefilled(refused["data_schema"]), "settings": lost.taken}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert dict(entry.subentries[subentry_id].data["settings"]) == lost.taken


@pytest.mark.parametrize("lost", LOST_VALUES)
async def test_clearing_a_value_the_ac_no_longer_lists_drops_the_setting(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    lost: LostValue,
) -> None:
    """The setting is shown, so emptying its field is the user's choice to drop it,
    and the interval turns the AC on as it is."""
    entry, subentry_id = await hold_a_value_the_ac_no_longer_lists(
        hass, fake_climate, setup_target, lost
    )

    result = await edit_interval(hass, entry, subentry_id, settings={})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert dict(entry.subentries[subentry_id].data["settings"]) == {}


@pytest.mark.parametrize(
    ("held", "field"),
    [
        pytest.param({"hvac_mode": 5}, {"options": ["heat"]}, id="a-number-for-a-mode"),
        pytest.param(
            {"temperature": "warm"}, {"min": 16, "max": 22}, id="text-for-a-number"
        ),
    ],
)
async def test_a_value_of_the_wrong_kind_opens_the_form_without_a_wider_field(
    hass: HomeAssistant,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    held: dict[str, Any],
    field: dict[str, Any],
) -> None:
    """A hand edit of the stored interval leaves a number where a mode belongs, or
    text where a temperature does. The form still opens, with the field as the AC
    lists it: a field that takes what is no value of its kind cannot be made."""
    entry = await setup_target(target=AC_ID)
    subentry_id = await add_interval(hass, entry, start="06:30", end="07:15")
    hass.config_entries.async_update_subentry(
        entry,
        entry.subentries[subentry_id],
        data={**entry.subentries[subentry_id].data, "settings": held},
    )
    fake_climate.capability_attributes.update(
        {"hvac_modes": ["off", "heat"], "max_temp": 22}
    )
    await fake_climate.set_state("off")

    form = await open_form(hass, entry, "reconfigure", subentry_id)

    (name,) = held
    selector = settings_fields(form)[name]
    assert {key: selector.config[key] for key in field} == field


async def test_editing_with_invalid_input_changes_nothing(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A refused edit shows the form again, and the interval stays as it was."""
    entry = await setup_target()
    subentry_id = await add_interval(hass, entry, start="06:30", end="07:15")
    before = entry.subentries[subentry_id].as_dict()

    result = await edit_interval(hass, entry, subentry_id, end="06:30")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"end": "same_start_and_end"}
    assert entry.subentries[subentry_id].as_dict() == before


async def test_adding_an_interval_keeps_a_running_countdown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The entry reloads to take the interval in; the countdown that was running
    carries on and ends on time."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 30)
    await advance(hass, freezer, minutes=10)
    controller = entry.runtime_data

    await add_interval(hass, entry, start="06:30", end="07:15")

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not controller
    assert state_of(hass, NUMBER) == "20"
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=20)
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_editing_an_interval_keeps_a_running_countdown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Saving an edit reloads the entry; the countdown is not disturbed."""
    entry = await setup_target()
    subentry_id = await add_interval(hass, entry, start="06:30", end="07:15")
    await set_number(hass, NUMBER, 30)
    await advance(hass, freezer, minutes=10)
    controller = entry.runtime_data

    await edit_interval(hass, entry, subentry_id, end="07:30")

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not controller
    assert state_of(hass, NUMBER) == "20"
    await advance(hass, freezer, minutes=20)
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_deleting_an_interval_keeps_a_running_countdown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Deleting an interval from the integration page reloads the entry; the
    countdown that was running carries on and ends on time."""
    entry = await setup_target()
    subentry_id = await add_interval(hass, entry, start="06:30", end="07:15")
    await set_number(hass, NUMBER, 30)
    await advance(hass, freezer, minutes=10)
    controller = entry.runtime_data

    hass.config_entries.async_remove_subentry(entry, subentry_id)
    await hass.async_block_till_done()

    assert not entry.subentries
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not controller
    assert state_of(hass, NUMBER) == "20"
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=20)
    assert fake_target.calls == [TURN_ON, TURN_OFF]


# --- Working days and days off --------------------------------------------------------


async def test_days_default_to_working_days_with_a_sensor(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """A house that has a Workday sensor schedules by working days: a new interval
    starts on them, and an interval that is edited shows what it has."""
    entry = await setup_target(workday_sensor=fake_workday.entity_id)
    form = await open_form(hass, entry)

    assert prefilled(form["data_schema"]) == {
        "days": "workdays",
        "weekdays": list(WEEK),
        "start": "00:00:00",
        "end": "00:00:00",
    }

    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", weekdays=["mon"]
    )
    form = await open_form(hass, entry, "reconfigure", subentry_id)

    assert prefilled(form["data_schema"])["days"] == "weekdays"


@pytest.mark.parametrize("days", ["workdays", "non_workdays"])
async def test_workday_modes_need_a_workday_sensor(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    days: str,
) -> None:
    """Nobody can say which days are working days on a timer without a sensor: the form
    comes back with the reason, in words, on the field that is wrong and with what was
    typed; nothing is added, and an interval already there is not edited."""
    entry = await setup_target()

    result = await submit_interval(hass, entry, start="06:30", end="07:15", days=days)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"days": "needs_workday_sensor"}
    assert prefilled(result["data_schema"])["days"] == days
    assert not entry.subentries
    texts = await async_get_translations(hass, "en", "config_subentries", [DOMAIN])
    error = f"component.{DOMAIN}.config_subentries.interval.error.needs_workday_sensor"
    assert texts[error]

    subentry_id = await add_interval(hass, entry, start="06:30", end="07:15")
    result = await edit_interval(hass, entry, subentry_id, days=days)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"days": "needs_workday_sensor"}
    assert entry.subentries[subentry_id].data["days"] == "weekdays"


@pytest.mark.parametrize(
    ("days", "title"),
    [
        ("workdays", "06:30–07:15, Working days"),
        ("non_workdays", "06:30–07:15, Non-working days"),
    ],
)
async def test_workday_interval_titles(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
    days: str,
    title: str,
) -> None:
    """An interval of working days is named by its times and the kind of days, and keeps
    no weekdays, which it has no use for."""
    entry = await setup_target(workday_sensor=fake_workday.entity_id)

    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", days=days, weekdays=[]
    )

    subentry = entry.subentries[subentry_id]
    assert subentry.title == title
    assert dict(subentry.data) == {
        "days": days,
        "weekdays": [],
        "start": "06:30",
        "end": "07:15",
        "settings": {},
        "generated_title": title,
    }


async def test_weekdays_that_working_days_do_not_use_are_not_kept(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """The days of the week that are ticked on the form do not count when the interval
    follows the sensor, and do not stay in it."""
    entry = await setup_target(workday_sensor=fake_workday.entity_id)

    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", days="workdays", weekdays=["mon"]
    )

    assert entry.subentries[subentry_id].data["weekdays"] == []


async def test_weekdays_are_still_needed_when_the_days_are_the_weekdays(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """A timer with a sensor still asks for the days of an interval that names them."""
    entry = await setup_target(workday_sensor=fake_workday.entity_id)

    result = await submit_interval(hass, entry, start="06:30", end="07:15", weekdays=[])

    assert result["errors"] == {"weekdays": "no_weekdays"}
    assert not entry.subentries


async def test_editing_the_kind_of_days_renames_the_interval(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """Working days instead of the weekdays: the data and the name follow, and the
    weekdays go. Back to the weekdays, the user names them again."""
    entry = await setup_target(workday_sensor=fake_workday.entity_id)
    subentry_id = await add_interval(hass, entry, start="06:30", end="07:15")

    result = await edit_interval(hass, entry, subentry_id, days="workdays")

    assert result["type"] is FlowResultType.ABORT
    subentry = entry.subentries[subentry_id]
    assert subentry.data["days"] == "workdays"
    assert subentry.data["weekdays"] == []
    assert subentry.title == "06:30–07:15, Working days"

    result = await edit_interval(hass, entry, subentry_id, days="weekdays")

    assert result["errors"] == {"weekdays": "no_weekdays"}
    result = await edit_interval(
        hass, entry, subentry_id, days="weekdays", weekdays=["sat", "sun"]
    )
    assert result["type"] is FlowResultType.ABORT
    assert entry.subentries[subentry_id].title == "06:30–07:15, Sat, Sun"


async def test_workday_title_is_in_the_language_of_the_house(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """The kind of days in the title is said in the language of the house."""
    entry = await setup_target(workday_sensor=fake_workday.entity_id)
    hass.config.language = "ru"
    words = await async_get_translations(hass, "ru", "selector", [DOMAIN])
    working = words[f"component.{DOMAIN}.selector.interval_days.options.workdays"]

    subentry_id = await add_interval(
        hass, entry, start="06:30", end="07:15", days="workdays"
    )

    assert working != "Working days"
    assert entry.subentries[subentry_id].title == f"06:30–07:15, {working}"


async def test_kind_of_days_reaches_the_frontend(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """The kind of days is a list of three choices, worded by the selector texts, that
    starts on the working days of a house that has a sensor."""
    entry = await setup_target(workday_sensor=fake_workday.entity_id)

    (days, *_) = frontend_fields(await open_form(hass, entry))

    assert days["name"] == "days"
    assert days["default"] == "workdays"
    assert days["selector"]["select"] == {
        "options": ["weekdays", "workdays", "non_workdays"],
        "multiple": False,
        "custom_value": False,
        "sort": False,
        "mode": "list",
        "translation_key": "interval_days",
    }
