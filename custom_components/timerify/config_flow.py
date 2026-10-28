"""Config flow of Timerify; Home Assistant needs this module to load config entries."""

from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN


class TimerifyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handler of Timerify config entries, which record their version here."""

    VERSION = 1
