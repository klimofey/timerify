"""Constants for the Timerify integration."""

from datetime import timedelta
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

SERVICE_CALL_TIMEOUT: Final = timedelta(seconds=30)
"""How long a turn_on or turn_off call may take before it counts as failed."""

Mode = Literal["strict", "loose"]
"""How a target is bound: strict runs only while the timer counts down, loose may
also run with the timer at zero."""
