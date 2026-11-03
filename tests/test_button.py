"""The Turn off button of a timer: a control on the device that is the stop command."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.timerify.const import (
    CONF_MODE,
    CONF_OFF_BUTTON,
    CONF_RUN_FOR_MAX,
    CONF_RUNTIME,
    MAX_MINUTES,
)

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    BUTTON,
    NUMBER,
    SENSOR,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    change_options,
    press_button,
    set_number,
    state_of,
)

RENAMED_BUTTON = "button.boiler_stop"


def settings(*, off_button: bool) -> dict[str, str | bool | int]:
    """What the first form of the settings of a loose timer submits. The form of the
    limit follows it, and is submitted empty."""
    return {
        CONF_MODE: "loose",
        CONF_RUNTIME: False,
        CONF_RUN_FOR_MAX: MAX_MINUTES,
        CONF_OFF_BUTTON: off_button,
    }


async def test_a_timer_has_no_turn_off_button_unless_asked(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A timer adds the button only when its settings ask for it."""
    await setup_target()

    assert hass.states.get(BUTTON) is None
    assert er.async_get(hass).async_get(BUTTON) is None


async def test_ticking_the_box_puts_a_turn_off_button_on_the_device(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """The button sits with the other controls of the boiler, on its device, and is
    not tucked away as a configuration entity. It has not been pressed yet."""
    await setup_target(off_button=True)

    state = hass.states.get(BUTTON)
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["friendly_name"] == "Boiler Turn off"
    registry = er.async_get(hass)
    registered = registry.async_get(BUTTON)
    assert registered is not None
    run_for = registry.async_get(NUMBER)
    assert run_for is not None
    assert registered.device_id == run_for.device_id == fake_target.device_id
    assert registered.entity_category is None


async def test_pressing_turn_off_stops_the_countdown_and_the_boiler(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Pressing the button ends a running countdown, as setting Run for to 0 does.
    The button shows when it was last pressed."""
    await setup_target(off_button=True)
    await set_number(hass, NUMBER, 45)

    await press_button(hass, BUTTON)

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, NUMBER) == "0"
    assert state_of(hass, SENSOR) == "unknown"
    assert state_of(hass, BUTTON) == "2026-01-05T07:00:00+00:00"


async def test_pressing_turn_off_stops_a_loose_boiler_without_a_countdown(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A loose boiler that someone switched on by hand has no countdown, and the
    button turns it off all the same."""
    await setup_target(mode="loose", off_button=True)
    await fake_target.set_state("on")

    await press_button(hass, BUTTON)

    assert fake_target.calls == [TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"


async def test_pressing_turn_off_on_a_boiler_that_is_off_sends_nothing(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """With nothing running, a press has nothing to stop."""
    await setup_target(off_button=True)

    await press_button(hass, BUTTON)

    assert fake_target.calls == []
    assert state_of(hass, TARGET_ID) == "off"


async def test_unticking_the_box_removes_the_button(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A timer that loses its button loses the entry in the registry too, so that no
    unavailable entity is left on the device. Ticking the box again brings the button
    back as the user had it: the registry keeps the entity id the user gave it."""
    entry = await setup_target(mode="loose", off_button=True)
    registry = er.async_get(hass)
    assert state_of(hass, BUTTON) == "unknown"
    registered = registry.async_update_entity(BUTTON, new_entity_id=RENAMED_BUTTON)
    await hass.async_block_till_done()
    assert state_of(hass, RENAMED_BUTTON) == "unknown"

    await change_options(hass, entry, settings(off_button=False), {})

    assert hass.states.get(RENAMED_BUTTON) is None
    assert registry.async_get(RENAMED_BUTTON) is None

    await change_options(hass, entry, settings(off_button=True), {})

    assert state_of(hass, RENAMED_BUTTON) == "unknown"
    assert hass.states.get(BUTTON) is None
    restored = registry.async_get(RENAMED_BUTTON)
    assert restored is not None
    assert restored.id == registered.id
