"""Timerify's triggers: a countdown started, a countdown ended, a pending command came
due.

They are integration triggers, the kind behind Home Assistant's own "Timer started" or
"Button pressed", aimed at the "Run for" numbers of timers. A timer fires an event when
it happens (`const.EVENT_*`) and each trigger listens to one of them. The target is
matched against the event's `entity_id` as the registries are then, so a timer that is
added, deleted or moved to another area needs no tracking.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, ClassVar, cast, override

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA,
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    EVENT_COMMAND_DUE,
    EVENT_COUNTDOWN_ENDED,
    EVENT_COUNTDOWN_STARTED,
)


class TimerEventTrigger(Trigger):
    """Runs the automation for each event of one type that names a timer in the
    target. The variables of the run are the data of the event."""

    _event_type: ClassVar[str]
    """The event this trigger listens to."""
    _what: ClassVar[str]
    """What happened, as the trace of the automation words it."""

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """A target and no options."""
        return cast(ConfigType, ENTITY_STATE_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Keep the target as the automation names it, to be resolved at each event."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.target is not None
        self._selection = TargetSelection(config.target)

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Listen for the event."""

        @callback
        def handle(event: Event[Mapping[str, Any]]) -> None:
            entity_id: str = event.data["entity_id"]
            selected = async_extract_referenced_entity_ids(
                self._hass, self._selection, expand_group=False
            )
            if entity_id in selected.referenced | selected.indirectly_referenced:
                run_action(
                    dict(event.data), f"{self._what} of {entity_id}", event.context
                )

        return self._hass.bus.async_listen(self._event_type, handle)


class CountdownStartedTrigger(TimerEventTrigger):
    """A timer that was not counting down starts a countdown."""

    _event_type = EVENT_COUNTDOWN_STARTED
    _what = "countdown started"


class CountdownEndedTrigger(TimerEventTrigger):
    """The countdown of a timer ends."""

    _event_type = EVENT_COUNTDOWN_ENDED
    _what = "countdown ended"


class CommandDueTrigger(TimerEventTrigger):
    """A pending command of a timer comes due and is carried out."""

    _event_type = EVENT_COMMAND_DUE
    _what = "pending command came due"


TRIGGERS: dict[str, type[Trigger]] = {
    "countdown_started": CountdownStartedTrigger,
    "countdown_ended": CountdownEndedTrigger,
    "command_due": CommandDueTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return Timerify's triggers."""
    return TRIGGERS
