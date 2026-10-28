"""Constants for the Timerify integration."""

from typing import Final, Literal

DOMAIN: Final = "timerify"

CONF_TARGET: Final = "target"
"""Option holding the target entity: an entity id, or a registry UUID once the
entity is registered."""
CONF_MODE: Final = "mode"
CONF_DEFAULT_DURATION: Final = "default_duration"
"""Option holding the default duration in whole minutes."""

DEFAULT_DURATION_MINUTES: Final = 30
MAX_MINUTES: Final = 1440
"""The longest timer: one day."""

Mode = Literal["strict", "loose"]
"""How a target is bound: strict runs only while the timer counts down, loose may
also run with the timer at zero."""
