"""Constants for the Timerify integration."""

from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Literal

DOMAIN: Final = "timerify"

CONF_TARGET: Final = "target"
"""Option holding the entity id of the target. A renamed target is followed by
updating the option (see `_follow_target` in `__init__`), not by a registry id."""
CONF_MODE: Final = "mode"
CONF_DEFAULT_DURATION: Final = "default_duration"
"""Option holding the default duration in whole minutes."""
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
"""How many times a wish that did not reach the target is sent again by reports that
merely repeat the target's state, before the timer stops asking until the state
changes or a command wants the wish again. Without a bound, a device that refuses a
command and answers it with a report of its old state would be commanded for ever."""

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
Timerify writes keep the modes the targets support."""
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
"""How long, in seconds, the sentence files wait for further changes of the timers or
of the names of their targets before they are written again."""
SIGNAL_TIMERS_CHANGED: Final = "timerify_timers_changed"
"""Sent when a timer is set up or unloaded, so that the names of the targets are listed
again."""
MANAGED_HEADER: Final = (
    "# Managed by Timerify. Do not edit:"
    " this file is rewritten whenever a timer changes."
)
"""The first line of every sentence file Timerify writes."""


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
