"""Config and options flows: pick a target, bind it, set the default duration.

Adding a timer takes the entity and the binding mode, and in strict mode a default
duration. The options flow changes the mode and the duration; the target stays.
Schedule intervals are subentries of the timer's entry, added, edited and deleted one
by one from its page.

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
from homeassistant.data_entry_flow import section
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DAYS,
    CONF_DEFAULT_DURATION,
    CONF_END,
    CONF_MODE,
    CONF_SETTINGS,
    CONF_START,
    CONF_TARGET,
    CONF_WEEKDAYS,
    DEFAULT_DURATION_MINUTES,
    DOMAIN,
    MAX_MINUTES,
    SUBENTRY_INTERVAL,
    DaysMode,
    Mode,
)
from .domains import (
    SUPPORTED_DOMAINS,
    SettingChoice,
    behaviour_for_domain,
    supported_settings,
    switchable_by_features,
    validate_settings,
)
from .schedule import interval_title
from .services import SETTINGS_SCHEMA
from .target import target_name


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
    """The form that adds a timer, built for the domains on offer when it is shown."""
    flow = handler.parent_handler
    assert isinstance(flow, ConfigFlow)
    return probatio.Schema(
        {
            probatio.Required(CONF_TARGET): _target_selector(flow.hass),
            probatio.Required(CONF_MODE, default="strict"): _mode_selector(),
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
    entity that is not in the registry has only its entity id.
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
    return {**user_input, CONF_TARGET: entity_id}


def _reads_on_or_off(hass: HomeAssistant, entity_id: str) -> bool:
    """Whether the entity's state is on or off now; an entity with no state, or one
    that is unavailable or unknown, is neither."""
    state = hass.states.get(entity_id)
    return state is not None and state.state in (STATE_ON, STATE_OFF)


async def _validate_duration(
    _handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Keep the default duration in whole minutes, the unit the timer counts in."""
    minutes: float = user_input[CONF_DEFAULT_DURATION]
    if not minutes.is_integer():
        raise SchemaFlowError("duration_not_whole")
    return {**user_input, CONF_DEFAULT_DURATION: int(minutes)}


async def _after_mode(options: dict[str, Any]) -> str | None:
    """Strict mode needs a default duration; loose mode has no use for one."""
    return "duration" if options[CONF_MODE] == "strict" else None


_DURATION_STEP = SchemaFlowFormStep(
    probatio.Schema(
        {
            probatio.Required(
                CONF_DEFAULT_DURATION, default=DEFAULT_DURATION_MINUTES
            ): _duration_selector()
        }
    ),
    validate_user_input=_validate_duration,
)

CONFIG_FLOW: Final = {
    "user": SchemaFlowFormStep(
        _target_schema,
        validate_user_input=_validate_target,
        next_step=_after_mode,
    ),
    "duration": _DURATION_STEP,
}

OPTIONS_FLOW: Final = {
    "init": SchemaFlowFormStep(
        probatio.Schema({probatio.Required(CONF_MODE): _mode_selector()}),
        next_step=_after_mode,
    ),
    "duration": _DURATION_STEP,
}


_SETTING_TYPES: Final = probatio.Schema(SETTINGS_SCHEMA)
"""Gives the settings of an interval the types they have when a service makes them."""

_WEEKDAY_SELECTOR: Final = "weekday"
"""The key of the weekday names in the `selector` translations: the list the user
picks days from and the words of an interval's title."""


def _setting_selector(
    choice: SettingChoice,
) -> selector.SelectSelector | selector.NumberSelector:
    """The field for one setting: a list of the values the entity lists, or a number
    in the range it accepts."""
    if choice.low is not None and choice.high is not None:
        return selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=choice.low,
                max=choice.high,
                step=0.5 if choice.name == "temperature" else 1,
                mode=selector.NumberSelectorMode.BOX,
            )
        )
    config = selector.SelectSelectorConfig(
        options=list(choice.options), mode=selector.SelectSelectorMode.DROPDOWN
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
    """Add a schedule interval to a timer, or edit one: the days, a start and an end,
    and what the target is turned on with when the interval starts.

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
        the mistake and nothing more. An edit keeps the title the user gave the
        interval; one that is still the generated title follows the new data.
        """
        entry = self._get_entry()
        subentry = (
            self._get_reconfigure_subentry()
            if self.source == SOURCE_RECONFIGURE
            else None
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = self._interval_from(entry, user_input)
            if not errors:
                labels = await self._async_day_labels()
                title = interval_title(data, labels)
                if subentry is None:
                    return self.async_create_entry(title=title, data=data)
                if subentry.title != interval_title(subentry.data, labels):
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
                self._interval_schema(entry, opened=bool(shown.get(CONF_SETTINGS))),
                shown,
            ),
            errors=errors,
        )

    def _interval_schema(self, entry: ConfigEntry, *, opened: bool) -> probatio.Schema:
        """The form: days, start, end and, when the target can be turned on with any,
        a section of its settings.

        The section is open when the form shows settings, which are then not hidden
        from the user nor the fields an error about them is about, and closed when it
        shows none. It has no default: a default on a section makes the frontend skip
        the settings inside it, and an edit would clear them.
        """
        fields: dict[Any, Any] = {
            probatio.Required(
                CONF_WEEKDAYS, default=lambda: list(WEEKDAYS)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(WEEKDAYS),
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key=_WEEKDAY_SELECTOR,
                )
            ),
            probatio.Required(CONF_START): selector.TimeSelector(),
            probatio.Required(CONF_END): selector.TimeSelector(),
        }
        if choices := supported_settings(self.hass, entry.options[CONF_TARGET]):
            fields[probatio.Optional(CONF_SETTINGS)] = section(
                probatio.Schema(
                    {
                        probatio.Optional(choice.name): _setting_selector(choice)
                        for choice in choices
                    }
                ),
                {"collapsed": not opened},
            )
        return probatio.Schema(fields)

    def _interval_from(
        self, entry: ConfigEntry, user_input: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """The data of the interval a filled-in form describes, and what is wrong
        with it by field, `base` for the settings as a whole; the data is whole only
        when nothing is wrong."""
        errors: dict[str, str] = {}
        weekdays = [day for day in WEEKDAYS if day in user_input[CONF_WEEKDAYS]]
        if not weekdays:
            errors[CONF_WEEKDAYS] = "no_weekdays"
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
        days: DaysMode = "weekdays"
        data = {
            CONF_DAYS: days,
            CONF_WEEKDAYS: weekdays,
            **times,
            CONF_SETTINGS: settings,
        }
        return data, errors

    async def _async_day_labels(self) -> dict[str, str]:
        """The short names of the weekdays in the language of the house."""
        words = await async_get_translations(
            self.hass, self.hass.config.language, "selector", [DOMAIN]
        )
        return {
            day: words[f"component.{DOMAIN}.selector.{_WEEKDAY_SELECTOR}.options.{day}"]
            for day in WEEKDAYS
        }


class TimerifyConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle the config, options and interval flows of Timerify."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW
    options_flow_reloads = False
    """The entry reloads on any change of itself, its options and its intervals
    alike, through the update listener (see `_async_entry_updated` in `__init__`);
    Home Assistant does not combine that with a flow that reloads by itself."""

    VERSION = 1

    @override
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Name the entry after its target."""
        return target_name(self.hass, options[CONF_TARGET])

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """A timer holds its schedule intervals as subentries."""
        return {SUBENTRY_INTERVAL: IntervalSubentryFlow}
