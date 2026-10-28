"""Constants for the Timerify integration."""

from typing import Final, Literal

DOMAIN: Final = "timerify"

Mode = Literal["strict", "loose"]
"""How a target is bound: strict runs only while the timer counts down, loose may
also run with the timer at zero."""
