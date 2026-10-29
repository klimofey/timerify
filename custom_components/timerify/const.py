"""Constants for the Timerify integration."""

from collections.abc import Mapping
from datetime import timedelta
from types import MappingProxyType
from typing import Final, Literal

DOMAIN: Final = "timerify"

CONF_TARGET: Final = "target"
"""Option holding the entity id of the target. A renamed target is followed by
updating the option (see `_follow_target` in `__init__`), not by a registry id."""
CONF_MODE: Final = "mode"
CONF_DEFAULT_DURATION: Final = "default_duration"
"""Option holding the default duration in whole minutes."""

DEFAULT_DURATION_MINUTES: Final = 30
MAX_MINUTES: Final = 1440
"""The longest timer: one day."""

MAX_COMMANDS: Final = 20
"""How many pending commands one timer keeps."""
MAX_COMMAND_AHEAD: Final = timedelta(days=7)
"""How far ahead of now a pending command may be set."""
MAX_DELAY_MINUTES: Final = 10080
"""The longest delay of a pending command: a week, in minutes."""

SERVICE_CALL_TIMEOUT: Final = timedelta(seconds=30)
"""How long a turn_on or turn_off call may take before it counts as failed."""

MAX_AUTOMATIC_RESENDS: Final = 3
"""How many times a wish that did not reach the target is sent again by reports that
merely repeat the target's state, before the timer stops asking until the state
changes or a command wants the wish again. Without a bound, a device that refuses a
command and answers it with a report of its old state would be commanded for ever."""

Mode = Literal["strict", "loose"]
"""How a target is bound: strict runs only while the timer counts down, loose may
also run with the timer at zero."""

type SettingValue = str | float | int
"""The value of one setting, as the service of the target's domain takes it."""
type Settings = Mapping[str, SettingValue]
"""What a target is turned on with, by service field name: the HVAC mode and the target
temperature of a thermostat, the brightness of a light."""

NO_SETTINGS: Final[Settings] = MappingProxyType({})


def freeze_settings(values: Mapping[str, SettingValue]) -> Settings:
    """A copy of the settings that nobody can change."""
    return MappingProxyType(dict(values))
