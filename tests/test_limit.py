"""The limit of a loose device left on, as the user meets it.

A loose timer with the "Turn off if left on for" setting turns its device off when it
has run that long with no countdown anyone chose. The scenarios follow a boiler with a
limit of two hours through what the user does with it: switches it on at the wall, runs
it for three hours on purpose, adds time, switches it off, changes the settings and
restarts Home Assistant. The engine's rules are pinned in `test_core.py`; here are the
entities, the events and the file a user sees.
"""

from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.timerify.const import (
    CONF_LIMIT,
    CONF_MODE,
    CONF_RUNTIME,
    EVENT_COUNTDOWN_ENDED,
    EVENT_COUNTDOWN_STARTED,
)

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    NUMBER,
    SENSOR,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    advance,
    at,
    call_service,
    change_options,
    payload,
    restart_after,
    saved,
    set_number,
    state_of,
)


def limit_of(hass: HomeAssistant) -> bool:
    """Whether the time the "Ends at" sensor shows is a limit, by its attribute."""
    state = hass.states.get(SENSOR)
    assert state is not None
    shown: bool = state.attributes["limit"]
    return shown


async def test_a_boiler_turned_on_by_hand_turns_off_after_its_limit(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """Switched on at the wall, the boiler has no countdown, so "Ends at" shows when it
    turns off at the latest and says that is a limit. "Run for" stays at 0, because
    nobody chose a time. At the limit the boiler is turned off, as a countdown that
    ran out turns it off."""
    entry = await setup_target(mode="loose", limit=120)
    assert state_of(hass, SENSOR) == "unknown"
    assert limit_of(hass) is False

    await fake_target.set_state("on")

    assert state_of(hass, SENSOR) == at(120)
    assert limit_of(hass) is True
    assert state_of(hass, NUMBER) == "0"
    assert saved(hass_storage, entry) == payload(limit_at=at(120))

    await advance(hass, freezer, minutes=119)

    assert fake_target.calls == []
    assert state_of(hass, SENSOR) == at(120)

    await advance(hass, freezer, minutes=1)

    assert fake_target.calls == [TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"
    assert state_of(hass, SENSOR) == "unknown"
    assert limit_of(hass) is False
    assert saved(hass_storage, entry) == payload()


async def test_a_boiler_run_without_minutes_gets_the_limit_too(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The Run action without minutes starts the boiler as a switch at the wall does,
    so it is bounded the same way."""
    await setup_target(mode="loose", limit=120)

    await call_service(hass, "run", {"entity_id": NUMBER})

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == at(120)
    assert limit_of(hass) is True

    await advance(hass, freezer, minutes=120)

    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_a_boiler_without_a_limit_setting_runs_until_it_is_turned_off(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A loose timer with no limit keeps what it did: no end, and no turning off."""
    await setup_target(mode="loose")

    await fake_target.set_state("on")

    assert state_of(hass, SENSOR) == "unknown"
    assert limit_of(hass) is False
    await advance(hass, freezer, hours=12)
    assert fake_target.calls == []
    assert state_of(hass, TARGET_ID) == "on"


async def test_a_boiler_run_for_three_hours_is_not_limited(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A run asked for on purpose is never cut by the limit, whether the boiler was off
    or had been left on and was already limited when the user chose its time."""
    await setup_target(mode="loose", limit=120)

    await set_number(hass, NUMBER, 180)

    assert state_of(hass, SENSOR) == at(180)
    assert limit_of(hass) is False
    await advance(hass, freezer, minutes=179)
    assert fake_target.calls == [TURN_ON]
    await advance(hass, freezer, minutes=1)
    assert fake_target.calls == [TURN_ON, TURN_OFF]

    await fake_target.set_state("on")
    assert limit_of(hass) is True
    await advance(hass, freezer, minutes=30)
    await set_number(hass, NUMBER, 180)

    assert state_of(hass, SENSOR) == at(180 + 30 + 180)
    assert limit_of(hass) is False
    await advance(hass, freezer, minutes=179)
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    await advance(hass, freezer, minutes=1)
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_OFF]


async def test_adding_time_to_a_limit_on_the_device_page(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A user who presses "+15 min" on a boiler that turns off by 09:00 at the latest
    chooses a time: the boiler then runs until 09:15, which nothing cuts. The limit is
    not announced as over, and the new countdown is announced as started, not as a
    limit. "Run for" shows the minutes then."""
    await setup_target(mode="loose", limit=120)
    await fake_target.set_state("on")
    started = async_capture_events(hass, EVENT_COUNTDOWN_STARTED)
    ended = async_capture_events(hass, EVENT_COUNTDOWN_ENDED)

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=15)

    assert state_of(hass, SENSOR) == at(135)
    assert limit_of(hass) is False
    assert state_of(hass, NUMBER) == "135"
    assert [e.data for e in started] == [
        {"entity_id": NUMBER, "ends_at": at(135), "limit": False}
    ]
    assert ended == []

    await advance(hass, freezer, minutes=134)
    assert fake_target.calls == []
    await advance(hass, freezer, minutes=1)
    assert fake_target.calls == [TURN_OFF]
    assert [e.data for e in ended] == [{"entity_id": NUMBER, "reason": "expired"}]


async def test_a_device_turned_off_before_its_limit_gets_a_new_one_next_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Switching the boiler off ends its limit, whoever does it. The next time it is
    switched on with no time chosen it gets a whole limit from that moment, not what
    was left of the old one."""
    await setup_target(mode="loose", limit=120)
    await fake_target.set_state("on")
    await advance(hass, freezer, minutes=30)
    ended = async_capture_events(hass, EVENT_COUNTDOWN_ENDED)

    await fake_target.set_state("off")

    assert [e.data for e in ended] == [{"entity_id": NUMBER, "reason": "turned_off"}]
    assert state_of(hass, SENSOR) == "unknown"
    assert limit_of(hass) is False

    await advance(hass, freezer, minutes=30)
    await fake_target.set_state("on")

    assert state_of(hass, SENSOR) == at(180)
    assert limit_of(hass) is True
    await advance(hass, freezer, minutes=60)
    assert state_of(hass, TARGET_ID) == "on"
    assert fake_target.calls == []
    await advance(hass, freezer, minutes=60)
    assert fake_target.calls == [TURN_OFF]


async def test_a_reload_keeps_a_running_limit_and_gives_one_to_a_device_left_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Saving the settings reloads the timer, and a reload is a start-up. A boiler
    that is already on with no limit gets one from the reload, counted from the
    moment it loads. A limit that runs keeps its time through a reload, whatever the
    setting is by then."""
    entry = await setup_target(mode="loose")
    await fake_target.set_state("on")
    await advance(hass, freezer, minutes=30)
    assert state_of(hass, SENSOR) == "unknown"

    await change_options(hass, entry, {CONF_MODE: "loose"}, {CONF_LIMIT: 90})

    assert entry.options[CONF_LIMIT] == 90
    assert state_of(hass, SENSOR) == at(30 + 90)
    assert limit_of(hass) is True
    assert fake_target.calls == []

    await advance(hass, freezer, minutes=30)
    await change_options(hass, entry, {CONF_MODE: "loose"}, {CONF_LIMIT: 30})

    assert entry.options[CONF_LIMIT] == 30
    assert state_of(hass, SENSOR) == at(30 + 90)
    assert limit_of(hass) is True

    await advance(hass, freezer, minutes=59)
    assert fake_target.calls == []
    await advance(hass, freezer, minutes=1)
    assert fake_target.calls == [TURN_OFF]


async def test_emptying_the_box_takes_the_limit_away_and_lets_the_boiler_run(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A user who empties the box has no limit any more: the one that ran is dropped
    when the timer loads again, and the boiler goes on running."""
    entry = await setup_target(mode="loose", limit=120)
    await fake_target.set_state("on")
    assert limit_of(hass) is True

    await change_options(hass, entry, {CONF_MODE: "loose"}, {})

    assert CONF_LIMIT not in entry.options
    assert state_of(hass, SENSOR) == "unknown"
    assert limit_of(hass) is False
    await advance(hass, freezer, hours=3)
    assert fake_target.calls == []
    assert state_of(hass, TARGET_ID) == "on"


async def test_a_limit_that_passed_while_down_turns_the_device_off_at_start_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A boiler left on whose limit came while Home Assistant was down is turned off
    when it starts, once, and the automation hears that it was the limit."""
    entry = await setup_target(mode="loose", limit=120)
    await fake_target.set_state("on")
    ended = async_capture_events(hass, EVENT_COUNTDOWN_ENDED)

    await restart_after(hass, freezer, entry, minutes=180)

    assert fake_target.calls == [TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"
    assert state_of(hass, SENSOR) == "unknown"
    assert [e.data for e in ended] == [{"entity_id": NUMBER, "reason": "limit"}]


async def test_a_limit_that_still_runs_after_a_restart_keeps_its_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The limit is counted from when the boiler was switched on, not from the restart:
    it ends at the same moment, and the restart announces nothing."""
    entry = await setup_target(mode="loose", limit=120)
    await fake_target.set_state("on")
    started = async_capture_events(hass, EVENT_COUNTDOWN_STARTED)

    await restart_after(hass, freezer, entry, minutes=45)

    assert state_of(hass, SENSOR) == at(120)
    assert limit_of(hass) is True
    assert started == []
    await advance(hass, freezer, minutes=74)
    assert fake_target.calls == []
    await advance(hass, freezer, minutes=1)
    assert fake_target.calls == [TURN_OFF]


async def test_switching_to_strict_drops_the_limit_and_the_default_duration_applies(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """Strict mode has no limit: every turn-on there gets the default duration. A
    boiler left on under a limit, when its timer turns strict, loses the limit with
    the setting, and is given the default duration from the reload."""
    entry = await setup_target(mode="loose", limit=120, default_duration=45)
    await fake_target.set_state("on")
    await advance(hass, freezer, minutes=30)

    await change_options(
        hass,
        entry,
        {CONF_MODE: "strict", CONF_RUNTIME: False},
        {"default_duration": 45},
    )

    assert CONF_LIMIT not in entry.options
    assert state_of(hass, SENSOR) == at(30 + 45)
    assert limit_of(hass) is False
    assert state_of(hass, NUMBER) == "45"
    assert saved(hass_storage, entry)["limit_at"] is None

    await advance(hass, freezer, minutes=45)

    assert fake_target.calls == [TURN_OFF]


async def test_a_boiler_switched_on_again_after_its_limit_gets_a_new_limit(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The limit turned the boiler off and ended. Switched on again, the boiler is
    limited again, for the whole time and from that moment."""
    await setup_target(mode="loose", limit=60)
    await fake_target.set_state("on")
    await advance(hass, freezer, minutes=60)
    assert fake_target.calls == [TURN_OFF]

    await fake_target.set_state("on")

    assert state_of(hass, SENSOR) == at(120)
    assert limit_of(hass) is True
