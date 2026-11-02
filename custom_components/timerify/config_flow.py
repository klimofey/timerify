"""Config and options flows: pick a target, bind it, set the default duration; or set up
the voice sentences.

The flow starts with a menu: add a timer, or, while there is none, the voice settings.
Adding a timer takes the entity, the binding mode, whether to count how long the
target is on and where the Run for slider ends, in strict mode a default duration, and,
in a house that has a Workday sensor, that sensor. The options flow changes the mode,
the counting, the end of the slider, the duration and the sensor; the target stays.
Schedule intervals are subentries of the timer's entry, added, edited and deleted one
by one from its page.

The voice settings are an entry of their own, of which there is one: whether Timerify
writes the sentence files for the built-in agent, and in which languages. The options
flow of that entry has the same two fields.

The picker offers the domains of the table in `domains.py` and, for any entity that
can be turned on and off, every other domain that has both services.
"""

from collections.abc import Mapping
from typing import Any, Final, get_args, override

import probatio
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    WEEKDAYS,
    UnitOfTime,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.data_entry_flow import AbortFlow, section
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)
from homeassistant.helpers.translation import (
    async_get_cached_translations,
    async_get_translations,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DAYS,
    CONF_DEFAULT_DURATION,
    CONF_END,
    CONF_GENERATED_TITLE,
    CONF_KIND,
    CONF_LANGUAGES,
    CONF_MODE,
    CONF_OFF_BUTTON,
    CONF_RUN_FOR_MAX,
    CONF_RUNTIME,
    CONF_SETTINGS,
    CONF_START,
    CONF_TARGET,
    CONF_WEEKDAYS,
    CONF_WORKDAY_SENSOR,
    CONF_WRITE_SENTENCES,
    DEFAULT_DURATION_MINUTES,
    DOMAIN,
    KIND_VOICE_SETTINGS,
    MAX_MINUTES,
    SUBENTRY_INTERVAL,
    VOICE_LANGUAGES,
    VOICE_UNIQUE_ID,
    WORKDAY_DOMAIN,
    DaysMode,
    Mode,
    is_voice_options,
    run_for_max_minutes,
)
from .domains import (
    SUPPORTED_DOMAINS,
    SettingChoice,
    behaviour_for_domain,
    supported_settings,
    switchable_by_features,
    validate_settings,
)
from .schedule import (
    DAYS_MODES,
    DAYS_SELECTOR,
    WEEKDAY_SELECTOR,
    async_title_labels,
    has_generated_title,
    interval_title,
)
from .services import SETTINGS_SCHEMA
from .target import target_name
from .voice.base import voice_language


def offered_domains(hass: HomeAssistant) -> list[str]:
    """The domains the picker offers: those of the table, then, sorted, every other
    domain that has both a turn_on and a turn_off service now.

    `homeassistant` has both and is never offered: its services are how the generic
    row switches the entities of every other domain, and it forwards no call to its
    own domain.
    """
    others = sorted(
        domain
        for domain in hass.services.async_services()
        if domain not in SUPPORTED_DOMAINS
        and domain != HOMEASSISTANT_DOMAIN
        and hass.services.has_service(domain, SERVICE_TURN_ON)
        and hass.services.has_service(domain, SERVICE_TURN_OFF)
    )
    return [*SUPPORTED_DOMAINS, *others]


def _target_selector(hass: HomeAssistant) -> selector.EntitySelector:
    """Offer the domains of `offered_domains`; of those whose services need features,
    the entities that advertise some of them.

    The picker takes an entity that has any one of a filter's features, so it can
    not require several. The exact rule is checked on submit by `_validate_target`;
    that check is needed anyway, since the selector validates only the domain.
    """
    domains = offered_domains(hass)
    required = {
        domain: behaviour_for_domain(domain).required_features for domain in domains
    }
    always_switchable = [
        domain for domain, features in required.items() if not features
    ]
    filters = [selector.EntityWithDeviceFilterSelectorConfig(domain=always_switchable)]
    filters.extend(
        selector.EntityWithDeviceFilterSelectorConfig(
            domain=domain,
            # The `<domain>.<enum>.<member>` form that selector filters take.
            supported_features=[
                f"{domain}.{type(f).__name__}.{f.name}" for f in features
            ],
        )
        for domain, features in required.items()
        if features
    )
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=domains, filter=filters)
    )


def _mode_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(get_args(Mode)),
            mode=selector.SelectSelectorMode.LIST,
            translation_key=CONF_MODE,
        )
    )


def _duration_selector() -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1,
            max=MAX_MINUTES,
            step=1,
            mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement=UnitOfTime.MINUTES,
        )
    )


async def _target_schema(handler: SchemaCommonFlowHandler) -> probatio.Schema:
    """The form that adds a timer, built for the domains on offer when it is shown.

    The runtime box, the end of the Run for slider and the Turn off box are on this
    form, not on steps of their own, so that a timer that takes every default is still
    added in three clicks.
    """
    flow = handler.parent_handler
    assert isinstance(flow, ConfigFlow)
    return probatio.Schema(
        {
            probatio.Required(CONF_TARGET): _target_selector(flow.hass),
            probatio.Required(CONF_MODE, default="strict"): _mode_selector(),
            probatio.Required(CONF_RUNTIME, default=False): selector.BooleanSelector(),
            probatio.Required(
                CONF_RUN_FOR_MAX, default=MAX_MINUTES
            ): _duration_selector(),
            probatio.Required(
                CONF_OFF_BUTTON, default=False
            ): selector.BooleanSelector(),
        }
    )


async def _validate_target(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Accept a target that a timer can switch and that has no timer yet.

    In order: its domain must be on offer, which is a registry id's only check of the
    domain; a domain of the table judges the entity by its features; and an entity
    that is switched through the generic row, a group among them, must read on or
    off, since that row takes any other state for off. The other rows are never
    judged by state: a thermostat heats and a player plays.

    The target is stored as an entity id, whichever of the two the selector took.
    The entry is identified by the registry id, which a rename leaves alone; an
    entity that is not in the registry has only its entity id. The end of the Run for
    slider is kept in whole minutes.
    """
    flow = handler.parent_handler
    assert isinstance(flow, ConfigFlow)
    registry = er.async_get(flow.hass)
    entity_id = er.async_resolve_entity_id(registry, user_input[CONF_TARGET])
    if entity_id is None:
        raise SchemaFlowError("target_not_supported")
    domain = split_entity_id(entity_id)[0]
    # A domain without a row of its own needs no features: only a table domain can fail.
    if domain not in offered_domains(flow.hass) or not switchable_by_features(
        flow.hass, entity_id
    ):
        raise SchemaFlowError("target_not_supported")
    if behaviour_for_domain(domain).judged_by_state and not _reads_on_or_off(
        flow.hass, entity_id
    ):
        raise SchemaFlowError("not_switchable")
    registered = registry.async_get(entity_id)
    await flow.async_set_unique_id(registered.id if registered else entity_id)
    flow._abort_if_unique_id_configured()
    return _whole_minutes({**user_input, CONF_TARGET: entity_id}, CONF_RUN_FOR_MAX)


def _reads_on_or_off(hass: HomeAssistant, entity_id: str) -> bool:
    """Whether the entity's state is on or off now; an entity with no state, or one
    that is unavailable or unknown, is neither."""
    state = hass.states.get(entity_id)
    return state is not None and state.state in (STATE_ON, STATE_OFF)


def _whole_minutes(user_input: dict[str, Any], key: str) -> dict[str, Any]:
    """The input with the minutes in `key` as an `int`, the unit the timer counts in; a
    fraction of a minute is refused."""
    minutes: float = user_input[key]
    if not minutes.is_integer():
        raise SchemaFlowError("duration_not_whole")
    return {**user_input, key: int(minutes)}


async def _validate_duration(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Keep the default duration in whole minutes, and not above the end of the Run for
    slider, which the first form has already put in the options.

    The selector keeps a day as its end, so that the form is the same for every timer;
    this is where a duration beyond the slider is refused, in words the user can read.
    """
    accepted = _whole_minutes(user_input, CONF_DEFAULT_DURATION)
    if accepted[CONF_DEFAULT_DURATION] > run_for_max_minutes(handler.options):
        raise SchemaFlowError("duration_above_maximum")
    return accepted


async def _duration_schema(handler: SchemaCommonFlowHandler) -> probatio.Schema:
    """The form of the default duration: usually 30 minutes, but never above the end of
    the Run for slider, so that a timer whose slider ends sooner takes every default
    all the same."""
    return probatio.Schema(
        {
            probatio.Required(
                CONF_DEFAULT_DURATION,
                default=min(
                    DEFAULT_DURATION_MINUTES, run_for_max_minutes(handler.options)
                ),
            ): _duration_selector()
        }
    )


def _workday_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain="binary_sensor", integration=WORKDAY_DOMAIN
        )
    )


async def _workday_schema(handler: SchemaCommonFlowHandler) -> probatio.Schema | None:
    """The form that names the Workday sensor, or None, which skips it, when there is
    nothing to pick and nothing to take away: no Workday sensor in the house and none
    set on the timer.

    A sensor that is set stays on offer after its integration is gone, so that the user
    can still remove it.
    """
    hass = handler.parent_handler.hass
    if CONF_WORKDAY_SENSOR not in handler.options and not any(
        registered.domain == "binary_sensor" and registered.platform == WORKDAY_DOMAIN
        for registered in er.async_get(hass).entities.values()
    ):
        return None
    return probatio.Schema(
        {probatio.Optional(CONF_WORKDAY_SENSOR): _workday_selector()}
    )


async def _validate_workday(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Keep the sensor while an interval follows the working days it tells."""
    flow = handler.parent_handler
    if (
        CONF_WORKDAY_SENSOR not in user_input
        and isinstance(flow, OptionsFlow)
        and any(
            subentry.data[CONF_DAYS] != "weekdays"
            for subentry in flow.config_entry.get_subentries_of_type(SUBENTRY_INTERVAL)
        )
    ):
        raise SchemaFlowError("workday_in_use")
    return user_input


async def _after_mode(options: dict[str, Any]) -> str:
    """Strict mode needs a default duration; loose mode has no use for one."""
    return "duration" if options[CONF_MODE] == "strict" else "workday"


async def _after_duration(_options: dict[str, Any]) -> str:
    """The Workday sensor comes last. A function, not the step's name, so that the
    form does not announce a next step that a house without a Workday sensor never
    gets: it says "Submit" either way."""
    return "workday"


_DURATION_STEP = SchemaFlowFormStep(
    _duration_schema,
    validate_user_input=_validate_duration,
    next_step=_after_duration,
)

_WORKDAY_STEP = SchemaFlowFormStep(
    _workday_schema, validate_user_input=_validate_workday
)


def _voice_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """The entry that holds the voice settings, if there is one, disabled or not."""
    return next(
        (
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if is_voice_options(entry.options)
        ),
        None,
    )


async def _menu_options(handler: SchemaCommonFlowHandler) -> list[str]:
    """What can be added: a timer always, the voice settings while there are none."""
    if _voice_entry(handler.parent_handler.hass) is None:
        return ["target", "voice_settings"]
    return ["target"]


def _voice_language_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(VOICE_LANGUAGES),
            multiple=True,
            mode=selector.SelectSelectorMode.LIST,
            translation_key="voice_language",
        )
    )


async def _voice_schema(handler: SchemaCommonFlowHandler) -> probatio.Schema:
    """The form of the voice settings. A new entry starts with the sentences written in
    the language of the house if Timerify has sentences in it, else in English; a
    change shows what is there."""
    flow = handler.parent_handler
    if isinstance(flow, ConfigFlow):
        return probatio.Schema(
            {
                probatio.Required(CONF_WRITE_SENTENCES, default=True): (
                    selector.BooleanSelector()
                ),
                probatio.Required(
                    CONF_LANGUAGES,
                    default=lambda: [voice_language(flow.hass.config.language)],
                ): _voice_language_selector(),
            }
        )
    return probatio.Schema(
        {
            probatio.Required(CONF_WRITE_SENTENCES): selector.BooleanSelector(),
            probatio.Required(CONF_LANGUAGES): _voice_language_selector(),
        }
    )


async def _validate_voice_settings(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Accept the voice settings if at least one language is chosen; keep the languages
    in the order Timerify lists them.

    A new entry is the only one of its kind: the menu does not offer it a second time,
    and a flow opened before the first was done is turned away here. Its title is
    translated when it is made, since the title of an entry is not looked up later and
    this step is where the translations can be waited for.
    """
    flow = handler.parent_handler
    if isinstance(flow, ConfigFlow) and _voice_entry(flow.hass) is not None:
        raise AbortFlow("voice_settings_exist")
    languages = [
        language
        for language in VOICE_LANGUAGES
        if language in user_input[CONF_LANGUAGES]
    ]
    if not languages:
        raise SchemaFlowError("languages_required")
    accepted = {**user_input, CONF_LANGUAGES: languages}
    if isinstance(flow, ConfigFlow):
        await flow.async_set_unique_id(VOICE_UNIQUE_ID, raise_on_progress=False)
        await async_get_translations(
            flow.hass, flow.hass.config.language, "config", [DOMAIN]
        )
        accepted[CONF_KIND] = KIND_VOICE_SETTINGS
    return accepted


_VOICE_STEP = SchemaFlowFormStep(
    _voice_schema, validate_user_input=_validate_voice_settings
)


async def _options_init_schema(
    handler: SchemaCommonFlowHandler,
) -> probatio.Schema | None:
    """The first form of the options: a timer's mode, whether it counts the runtime,
    where the Run for slider ends and whether it has a Turn off button. The voice
    settings have none of them, and go to their own form.

    The form opens with the options the entry has. A timer made before the counter or
    before the Turn off box has no such option, so the box has no suggested value and
    shows its default, unticked; one made before the maximum of Run for shows a day.
    """
    if is_voice_options(handler.options):
        return None
    return probatio.Schema(
        {
            probatio.Required(CONF_MODE): _mode_selector(),
            probatio.Required(CONF_RUNTIME, default=False): selector.BooleanSelector(),
            probatio.Required(
                CONF_RUN_FOR_MAX, default=MAX_MINUTES
            ): _duration_selector(),
            probatio.Required(
                CONF_OFF_BUTTON, default=False
            ): selector.BooleanSelector(),
        }
    )


async def _validate_timer_settings(
    _handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Keep the end of the Run for slider in whole minutes. The default duration is
    checked against it on the form that follows."""
    return _whole_minutes(user_input, CONF_RUN_FOR_MAX)


async def _after_options_init(options: dict[str, Any]) -> str:
    if is_voice_options(options):
        return "voice_settings"
    return await _after_mode(options)


CONFIG_FLOW: Final = {
    "user": SchemaFlowMenuStep(_menu_options),
    "target": SchemaFlowFormStep(
        _target_schema,
        validate_user_input=_validate_target,
        next_step=_after_mode,
    ),
    "voice_settings": _VOICE_STEP,
    "duration": _DURATION_STEP,
    "workday": _WORKDAY_STEP,
}

OPTIONS_FLOW: Final = {
    "init": SchemaFlowFormStep(
        _options_init_schema,
        validate_user_input=_validate_timer_settings,
        next_step=_after_options_init,
    ),
    "voice_settings": _VOICE_STEP,
    "duration": _DURATION_STEP,
    "workday": _WORKDAY_STEP,
}


_SETTING_TYPES: Final = probatio.Schema(SETTINGS_SCHEMA)
"""Gives the settings of an interval the types they have when a service makes them."""


def _setting_selector(
    choice: SettingChoice, held: Any = None
) -> selector.SelectSelector | selector.NumberSelector:
    """The field for one setting: a list of the values the entity lists, or a number
    in the range it accepts.

    `held` is the value the form is filled in with, if there is one. The entity may no
    longer list it, and the field takes it all the same: the form then shows what the
    interval holds, and the user changes or empties it. A selector that refused it
    would answer in Home Assistant's own words, or the frontend would drop it without
    a word; `validate_settings` refuses it with a translated error instead.
    """
    if choice.low is not None and choice.high is not None:
        low, high = choice.low, choice.high
        if isinstance(held, int | float) and not isinstance(held, bool):
            low, high = min(low, held), max(high, held)
        return selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=low,
                max=high,
                step=0.5 if choice.name == "temperature" else 1,
                mode=selector.NumberSelectorMode.BOX,
            )
        )
    options = list(choice.options)
    if isinstance(held, str) and held not in options:
        options.append(held)
    config = selector.SelectSelectorConfig(
        options=options, mode=selector.SelectSelectorMode.DROPDOWN
    )
    if choice.name == "hvac_mode":
        config["translation_key"] = "hvac_mode"
    return selector.SelectSelector(config)


def _whole_minute(value: str) -> str | None:
    """A time of day as `HH:MM`; None when it has seconds, which the schedule has no
    use for. The time picker sends `HH:MM:SS` whatever the user picks."""
    parsed = dt_util.parse_time(value)
    if parsed is None or parsed.second or parsed.microsecond:
        return None
    return f"{parsed:%H:%M}"


class IntervalSubentryFlow(ConfigSubentryFlow):
    """Add a schedule interval to a timer, or edit one: the kind of days and, for
    weekdays, which, a start and an end, and what the target is turned on with when the
    interval starts.

    Both steps show the same form, built for the target's capabilities.
    """

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add an interval."""
        return await self._async_interval_step("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit an interval."""
        return await self._async_interval_step("reconfigure", user_input)

    async def _async_interval_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        """Show the form, then take what was filled in.

        A refused form is shown again with what was typed, so that the user corrects
        the mistake and nothing more. A new interval is titled by its times and days in
        the language of the house, and keeps that title as `CONF_GENERATED_TITLE`. An
        edit titles an interval whose title is still that one again, in the language of
        the house now, and keeps any other title, the user's own. An interval that has
        no `CONF_GENERATED_TITLE` counts as titled by Timerify when its title equals the
        one its data makes in the language of the house now. An edit keeps the settings
        the form does not offer, as they are (`_interval_from`), and shows one it offers
        with the value it holds, though the target no longer takes that value; the
        input is then refused in words, with the setting still shown.
        """
        entry = self._get_entry()
        subentry = (
            self._get_reconfigure_subentry()
            if self.source == SOURCE_RECONFIGURE
            else None
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = self._interval_from(
                entry, user_input, subentry.data[CONF_SETTINGS] if subentry else {}
            )
            if not errors:
                labels = await async_title_labels(self.hass, self.hass.config.language)
                title = interval_title(data, labels)
                if subentry is None:
                    return self.async_create_entry(
                        title=title, data={**data, CONF_GENERATED_TITLE: title}
                    )
                if has_generated_title(subentry, labels):
                    data[CONF_GENERATED_TITLE] = title
                else:
                    title = subentry.title
                return self.async_update_and_abort(
                    entry, subentry, data=data, title=title
                )
        shown = (
            user_input if user_input is not None else subentry.data if subentry else {}
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                self._interval_schema(entry, shown.get(CONF_SETTINGS) or {}),
                shown,
            ),
            errors=errors,
        )

    def _interval_schema(
        self, entry: ConfigEntry, shown_settings: Mapping[str, Any]
    ) -> probatio.Schema:
        """The form: the kind of days, the weekdays, start, end and, when the target can
        be turned on with any, a section of its settings.

        The kind of days is the working days of the Workday sensor from the start when
        the timer has one: those are what a house with a sensor schedules by.

        The section is open when `shown_settings`, the settings the form is filled in
        with, holds one that the section offers, so that it is not hidden from the user
        nor the fields an error about it is about. It is closed otherwise: a setting
        the target no longer offers is not shown, so it does not open the section. It
        has no default: a default on a section makes the frontend skip the settings
        inside it, and an edit would clear them.

        A field also takes the value that `shown_settings` holds for it when the target
        does not list that value now (see `_setting_selector`).
        """
        has_sensor = CONF_WORKDAY_SENSOR in entry.options
        fields: dict[Any, Any] = {
            probatio.Required(
                CONF_DAYS, default="workdays" if has_sensor else "weekdays"
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(DAYS_MODES),
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key=DAYS_SELECTOR,
                )
            ),
            probatio.Required(
                CONF_WEEKDAYS, default=lambda: list(WEEKDAYS)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(WEEKDAYS),
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key=WEEKDAY_SELECTOR,
                )
            ),
            probatio.Required(CONF_START): selector.TimeSelector(),
            probatio.Required(CONF_END): selector.TimeSelector(),
        }
        if choices := supported_settings(self.hass, entry.options[CONF_TARGET]):
            opened = any(choice.name in shown_settings for choice in choices)
            fields[probatio.Optional(CONF_SETTINGS)] = section(
                probatio.Schema(
                    {
                        probatio.Optional(choice.name): _setting_selector(
                            choice, shown_settings.get(choice.name)
                        )
                        for choice in choices
                    }
                ),
                {"collapsed": not opened},
            )
        return probatio.Schema(fields)

    def _interval_from(
        self,
        entry: ConfigEntry,
        user_input: dict[str, Any],
        stored: Mapping[str, Any],
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """The data of the interval a filled-in form describes, and what is wrong
        with it by field, `base` for the settings as a whole; the data is whole only
        when nothing is wrong.

        `stored` is the settings the interval has, none for a new one. The saved
        settings are the ones of the form, which have the user's values, and then the
        stored ones whose name the form does not offer: the target no longer takes
        them, but may again, and the user cannot change what the form does not show.
        """
        errors: dict[str, str] = {}
        days: DaysMode = user_input[CONF_DAYS]
        weekdays: list[str] = []
        if days == "weekdays":
            weekdays = [day for day in WEEKDAYS if day in user_input[CONF_WEEKDAYS]]
            if not weekdays:
                errors[CONF_WEEKDAYS] = "no_weekdays"
        elif CONF_WORKDAY_SENSOR not in entry.options:
            errors[CONF_DAYS] = "needs_workday_sensor"
        times: dict[str, str] = {}
        for field in (CONF_START, CONF_END):
            if (time := _whole_minute(user_input[field])) is None:
                errors[field] = "whole_minutes_only"
            else:
                times[field] = time
        if len(times) == 2 and times[CONF_START] == times[CONF_END]:
            errors[CONF_END] = "same_start_and_end"
        settings: dict[str, Any] = {}
        try:
            settings = dict(
                validate_settings(
                    self.hass,
                    entry.options[CONF_TARGET],
                    _SETTING_TYPES(user_input.get(CONF_SETTINGS, {})),
                )
            )
        except probatio.Invalid:
            errors["base"] = "settings_not_whole"
        except ServiceValidationError:
            errors["base"] = "settings_not_supported"
        offered = {
            choice.name
            for choice in supported_settings(self.hass, entry.options[CONF_TARGET])
        }
        settings.update(
            {name: value for name, value in stored.items() if name not in offered}
        )
        data = {
            CONF_DAYS: days,
            CONF_WEEKDAYS: weekdays,
            **times,
            CONF_SETTINGS: settings,
        }
        return data, errors


class TimerifyConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle the config, options and interval flows of Timerify."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = False
    """The entry reloads on any change of itself, its options and its intervals
    alike, through the update listener (see `_async_entry_updated` in `__init__`);
    Home Assistant does not combine that with a flow that reloads by itself."""

    VERSION = 1
    MINOR_VERSION = 2
    """Minor version 2 marks the titles Timerify gave the intervals
    (`CONF_GENERATED_TITLE`); see `async_migrate_entry` in `__init__`."""

    @override
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Name a timer after its target, and the voice settings as the translations of
        the house's language call them (see `_validate_voice_settings`)."""
        if is_voice_options(options):
            translations = async_get_cached_translations(
                self.hass, self.hass.config.language, "config", DOMAIN
            )
            return translations[f"component.{DOMAIN}.config.step.voice_settings.title"]
        return target_name(self.hass, options[CONF_TARGET])

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """A timer holds its schedule intervals as subentries; the voice settings hold
        none."""
        if is_voice_options(config_entry.options):
            return {}
        return {SUBENTRY_INTERVAL: IntervalSubentryFlow}
