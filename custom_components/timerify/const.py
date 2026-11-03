"""Constants for the Timerify integration."""

from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Literal

DOMAIN: Final = "timerify"
TRANSLATION_LANGUAGES: Final = ("en", "ru")
"""The languages of `translations/`: a file each."""

CONF_TARGET: Final = "target"
"""Option holding the entity id of the target. A renamed target is followed by
updating the option (see `_follow_target` in `__init__`), not by a registry id."""
CONF_MODE: Final = "mode"
CONF_DEFAULT_DURATION: Final = "default_duration"
"""Option holding the default duration in whole minutes."""
CONF_RUNTIME: Final = "runtime"
"""Option holding whether the timer counts how long its target was on, a `bool`. Absent
or False: no counter, and no Runtime sensor; an entry of an earlier release has none."""
CONF_RUN_FOR_MAX: Final = "run_for_max"
"""Option holding the end of the Run for slider in whole minutes. An entry of an earlier
release has none."""
CONF_LIMIT: Final = "limit"
"""Option holding how long, in whole minutes, a loose timer lets its target run with no
countdown before it turns the target off. Absent: no limit; an entry of an earlier
release has none, and a strict timer never has one."""
CONF_OFF_BUTTON: Final = "off_button"
"""Option holding whether the timer has a Turn off button, a `bool`. Absent or False: no
button; an entry of an earlier release has none."""
CONF_WORKDAY_SENSOR: Final = "workday_sensor"
"""Option holding the entity id of the target's Workday sensor, which the intervals of
working days and of days off ask which days are which. Absent when there is none."""
WORKDAY_DOMAIN: Final = "workday"
"""The integration that provides the Workday sensors and the service that answers which
days are working days."""

SUBENTRY_INTERVAL: Final = "interval"
"""Type of the config subentries that each hold one schedule interval of a timer."""
CONF_DAYS: Final = "days"
"""Subentry data: which days an interval runs on, a `DaysMode`."""
CONF_WEEKDAYS: Final = "weekdays"
"""Subentry data: the weekdays (`homeassistant.const.WEEKDAYS` names, in week order) of
an interval whose days are `weekdays`."""
CONF_START: Final = "start"
"""Subentry data: when an interval begins, as `HH:MM` on the wall clock."""
CONF_END: Final = "end"
"""Subentry data: when an interval ends, as `HH:MM`; earlier than the start for an
interval that crosses midnight."""
CONF_SETTINGS: Final = "settings"
"""Subentry data: what the target is turned on with when the interval starts."""
CONF_GENERATED_TITLE: Final = "generated_title"
"""Subentry data: the title Timerify gave an interval, in the language of the house at
the time. The title counts as generated while the subentry's title still equals it. A
rename on the integration page changes only the title, so it ends the mark by itself,
which a bare flag could not tell. Absent from an interval whose title the user chose."""

DEFAULT_DURATION_MINUTES: Final = 30
MAX_MINUTES: Final = 1440
"""The longest timer: one day."""
WINDOW_SEARCH_DAYS: Final = 14
"""How many days ahead the next occurrence of a schedule interval is looked for: an
interval that names a weekday has one within a week, so two weeks leave a margin."""

MAX_COMMANDS: Final = 20
"""How many pending commands one timer keeps."""
MAX_COMMAND_AHEAD: Final = timedelta(days=7)
"""How far ahead of now a pending command may be set."""
MAX_DELAY_MINUTES: Final = 10080
"""The longest delay of a pending command: a week, in minutes."""

MAX_LISTED_INTERVALS: Final = 5
"""How many interval titles a refusal names when it tells which ones can be asked for:
it is spoken and read by an agent, and the rest are counted, not recited."""

SERVICE_CALL_TIMEOUT: Final = timedelta(seconds=30)
"""How long a turn_on or turn_off call may take before it counts as failed."""

MAX_AUTOMATIC_RESENDS: Final = 3
"""How many times a wish that did not reach the target, or a set of settings that did
not, is sent again by reports of the target after the first delivery, before the timer
stops asking until new work wants it again: a new command, or a countdown or a
schedule interval that switches the target. A device that refuses a command and
answers with a report of its old state, or one that drops off the network and comes
back, would be commanded for ever without a bound."""

VOICE_LANGUAGES: Final = ("en", "ru")
"""The languages Timerify ships sentences for: a directory of `sentences/` each."""
SENTENCES_DIR: Final = Path(__file__).parent / "sentences"
"""The sentence sources for the built-in agent, a directory per language."""
LIST_TARGET: Final = "timerify_target"
"""The list of the sentence sources that holds the names of the targets of the timers,
which the sentences use as the slot `name`."""
LIST_HVAC_MODE: Final = "timerify_hvac_mode"
"""The list of the sentence sources that holds the words for an HVAC mode, which the
sentences use as the slot `hvac_mode`. The sources say every mode in words; the files
Timerify writes leave it empty and give each data block that is for thermostats a list
of its own, with the words for the modes of one set of thermostats."""
CONTEXT_HVAC_MODES: Final = "timerify_hvac_modes"
"""The context of the name of a thermostat in the files Timerify writes: the HVAC modes
it can be turned on with, sorted and joined by a space. A data block of the sentences
for thermostats requires the context of one set, so that a thermostat is understood
with the words for its own modes only."""
LIST_MODE: Final = "timerify_mode"
"""The list that holds the modes of the targets as their devices name them, which the
sentences use as the slot `mode`. Empty in the sources: only the files Timerify writes
know the devices."""
LIST_INTERVAL: Final = "timerify_interval"
"""The list that holds the titles of the schedule intervals of the timers, which the
sentences use as the slot `interval`. Empty in the sources: only the files Timerify
writes know the intervals."""
MANUAL_SENTENCES_DIR: Final = "timerify_manual"
"""The directory of `custom_sentences/<language>/` that the sentence files are copied
into by hand. The managed file has a name of its own beside it, and the two are never
meant to be there together."""

CONF_KIND: Final = "kind"
"""Option that tells what an entry is: absent for a timer, `KIND_VOICE_SETTINGS` for the
entry that writes the sentence files."""
KIND_VOICE_SETTINGS: Final = "voice_settings"
CONF_WRITE_SENTENCES: Final = "write_sentence_files"
"""Option of the voice settings: whether Timerify writes the sentence files for the
built-in agent."""
CONF_LANGUAGES: Final = "languages"
"""Option of the voice settings: the languages the sentence files are written in, a
subset of `VOICE_LANGUAGES`."""
VOICE_UNIQUE_ID: Final = "voice_settings"
"""The unique id of the voice settings entry, of which there is at most one."""
VOICE_SYNC_COOLDOWN: Final = 1.0
"""How long, in seconds, a change of the timers or of the names of their targets waits
before the sentence files are written, counted from the first of the changes that come
in a row, and the least time between two writings."""
SIGNAL_TIMERS_CHANGED: Final = "timerify_timers_changed"
"""Sent when a timer is set up or unloaded, so that the names of the targets are listed
again."""
EVENT_COUNTDOWN_STARTED: Final = "timerify_countdown_started"
"""Fired when a timer with no countdown begins one, or sets the limit of a run that has
none. Data: `entity_id`, the timer's Run for, `ends_at`, the end as the Ends at sensor
states it (ISO 8601 in UTC), and `limit`: true when `ends_at` is the time of a limit,
false when it is the end of a countdown that someone chose."""
EVENT_COUNTDOWN_ENDED: Final = "timerify_countdown_ended"
"""Fired when the countdown of a timer, or its limit, is over. Data: `entity_id`, the
timer's Run for, and `reason`: `expired`, `stopped`, `turned_off` or `limit`
(`EndReason`)."""
EVENT_COMMAND_DUE: Final = "timerify_command_due"
"""Fired when a pending command is carried out at its time. Data: `entity_id`, the
timer's Run for, `command_id`, as `add_command` answered it, and `action`: `on` or
`off`. A command dropped for coming too late fires nothing."""
MANAGED_HEADER: Final = (
    "# Managed by Timerify. Do not edit:"
    " this file is rewritten whenever a timer changes."
)
"""The first line of every sentence file Timerify writes."""


KEY_RUN_FOR: Final = "run_for"
KEY_ENDS_AT: Final = "ends_at"
KEY_NEXT_COMMAND: Final = "next_command"
KEY_RUNTIME: Final = "runtime"
KEY_TURN_OFF: Final = "turn_off"
"""The keys of the entities a timer has one of, the last two only if it counts its
runtime and if it has a Turn off button, in that order: with the entry's id they make
an entity's unique id (see `timer_unique_id`)."""
WITH_TARGET_SUFFIX: Final = "_with_target"
"""The suffix that makes the translation key of an entity the key of its name on a
device that holds more than one timer, which names the target in brackets: `run_for`
becomes `run_for_with_target`. The translations and the icons have such a key for every
entity."""

RUNTIME_TICK_SECOND: Final = 59
"""The second of every minute at which the Runtime sensor publishes its total: the last
one. A listener fires up to half a second after its second, so a run that crosses an
hour or midnight is credited to the right side of it to within a second, which a tick
at second 0 would credit to the wrong side. That holds while the file is saved in under
half a second: the tick saves it before it writes the state."""


def timer_unique_id(entry_id: str, key: str) -> str:
    """The unique id of the entity of a timer that has the key `key` (`KEY_RUN_FOR`,
    `KEY_ENDS_AT`, `KEY_NEXT_COMMAND`, `KEY_RUNTIME`, `KEY_TURN_OFF`).

    A unique id is an entity's identity in the registry: changing how it is made would
    leave every installed entity behind, with its entity id, its history and its place
    on the dashboards. It is built here so that the entities and whoever looks them up
    by it, such as the card's websocket command, cannot disagree.
    """
    return f"{entry_id}_{key}"


def interval_unique_id(entry_id: str, subentry_id: str) -> str:
    """The unique id of the switch of the schedule interval that is the subentry
    `subentry_id` of the timer; see `timer_unique_id`."""
    return f"{entry_id}_interval_{subentry_id}"


def default_duration_minutes(options: Mapping[str, Any]) -> int:
    """The minutes a timer of strict mode runs by default: its option, or
    `DEFAULT_DURATION_MINUTES` for an entry that has none."""
    minutes: int = options.get(CONF_DEFAULT_DURATION, DEFAULT_DURATION_MINUTES)
    return minutes


def run_for_max_minutes(options: Mapping[str, Any]) -> int:
    """The end of the Run for slider: its option, or `MAX_MINUTES` for an entry that
    has none. It bounds the slider only; a countdown that something else starts may be
    longer, up to `MAX_MINUTES`."""
    minutes: int = options.get(CONF_RUN_FOR_MAX, MAX_MINUTES)
    return minutes


def limit_minutes(options: Mapping[str, Any]) -> int | None:
    """The minutes a loose timer lets its target run with no countdown: its option, or
    None for an entry that has none."""
    minutes: int | None = options.get(CONF_LIMIT)
    return minutes


def is_voice_options(options: Mapping[str, Any]) -> bool:
    """Whether the options are those of the voice settings, not of a timer."""
    return options.get(CONF_KIND) == KIND_VOICE_SETTINGS


Mode = Literal["strict", "loose"]
"""How a target is bound: strict runs only while the timer counts down, loose may
also run with the timer at zero."""

type DaysMode = Literal["weekdays", "workdays", "non_workdays"]
"""Which days an interval runs on: the weekdays it names, the working days of the
Workday sensor, or the days that are not."""

type SettingValue = str | float | int
"""The value of one setting, as the service of the target's domain takes it."""
type Settings = Mapping[str, SettingValue]
"""What a target is turned on with, by service field name: the HVAC mode and the target
temperature of a thermostat, the brightness of a light."""

NO_SETTINGS: Final[Settings] = MappingProxyType({})


def freeze_settings(values: Mapping[str, SettingValue]) -> Settings:
    """A copy of the settings that nobody can change."""
    return MappingProxyType(dict(values))
