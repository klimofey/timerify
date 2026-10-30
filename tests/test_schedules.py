"""Schedule intervals running the timer by day of the week.

The scenarios are the owner's boiler: a window every morning, edited while it runs,
stopped by hand, cut short by a restart or by the change of the clock. They run on the
wall clock of Jerusalem, with the clock frozen on a Sunday morning, and step to each
event with its own jump: one jump is one catch-up.
"""

import logging
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.timerify.const import (
    MAX_MINUTES,
    WINDOW_SEARCH_DAYS,
    freeze_settings,
)
from custom_components.timerify.core import Window
from custom_components.timerify.schedule import (
    Interval,
    days_around,
    weekday_window,
    window_on,
)

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    AC_ENDS_AT,
    AC_ID,
    JERUSALEM,
    NUMBER,
    SENSOR,
    SUNDAY,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    WEEK,
    add_interval,
    advance_to,
    call_service,
    edit_interval,
    iso,
    local,
    open_sunday,
    restart,
    restart_after,
    state_of,
    timerify_info,
    timerify_warnings,
)

pytestmark = pytest.mark.usefixtures("hass_storage")

MONDAY = SUNDAY + timedelta(days=1)
FRIDAY = SUNDAY + timedelta(days=5)
SATURDAY = SUNDAY + timedelta(days=6)

COOL24 = {"hvac_mode": "cool", "temperature": 24}
SET_COOL = ("set_hvac_mode", {"hvac_mode": "cool"})
SET_24 = ("set_temperature", {"temperature": 24.0})

WINDOW_STARTED_WHILE_UNAVAILABLE = (
    "A schedule window of switch.boiler started while it is unavailable;"
    " it is turned on when it is back, if the window is still open then"
)


# --- The boiler's window ------------------------------------------------------------


async def test_interval_runs_the_boiler_through_its_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The boiler goes on at the start of the window, counts down to its end and goes
    off there."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    assert fake_target.calls == []

    await advance_to(hass, freezer, local(SUNDAY, "06:30"))

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")
    assert state_of(hass, NUMBER) == "45"

    await advance_to(hass, freezer, local(SUNDAY, "07:15"))

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"
    assert state_of(hass, SENSOR) == "unknown"


async def test_interval_runs_again_on_the_next_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """When a window is over the next one is waiting: tomorrow's morning."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))

    await advance_to(hass, freezer, local(MONDAY, "06:30"))

    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]
    assert state_of(hass, SENSOR) == iso(MONDAY, "07:15")
    await advance_to(hass, freezer, local(MONDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON, TURN_OFF]


async def test_window_that_ends_while_the_boiler_is_slow_is_replaced_by_tomorrows(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The boiler is slow to answer the turn-on at the start of the window, reports
    that it is on meanwhile, and the window is over when the timer is free again. The
    report finds the window over before the alarm of its end can: tomorrow's window
    must still be there."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    slow = fake_target.hold_next_call()
    freezer.move_to(local(SUNDAY, "06:30"))
    async_fire_time_changed(hass)
    await slow.reached.wait()
    fake_target.write("on")
    freezer.move_to(local(SUNDAY, "07:15"))
    async_fire_time_changed(hass)

    slow.release.set()
    await hass.async_block_till_done()

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    await advance_to(hass, freezer, local(MONDAY, "06:30"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]
    assert state_of(hass, SENSOR) == iso(MONDAY, "07:15")


async def test_interval_skips_days_it_does_not_name(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """An interval for Mondays leaves Sunday morning alone and runs on Monday."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15", weekdays=["mon"])

    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))

    assert fake_target.calls == []

    await advance_to(hass, freezer, local(MONDAY, "06:30"))

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(MONDAY, "07:15")
    await advance_to(hass, freezer, local(MONDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_window_across_midnight_belongs_to_its_start_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A Friday interval from 22:00 to 06:00 runs Friday night into Saturday morning,
    and not again on Saturday night."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="22:00", end="06:00", weekdays=["fri"])

    await advance_to(hass, freezer, local(FRIDAY, "22:00"))

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SATURDAY, "06:00")

    await advance_to(hass, freezer, local(SATURDAY, "06:00"))

    assert fake_target.calls == [TURN_ON, TURN_OFF]

    await advance_to(hass, freezer, local(SATURDAY, "22:00"))

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"


async def test_restart_after_midnight_keeps_the_window_that_began_yesterday(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Home Assistant restarting at two in the morning finds the Friday window still
    open and leaves the boiler running to its end."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="22:00", end="06:00", weekdays=["fri"])
    await advance_to(hass, freezer, local(FRIDAY, "22:00"))
    await advance_to(hass, freezer, local(SATURDAY, "02:00"))

    await restart(hass, entry)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SATURDAY, "06:00")
    await advance_to(hass, freezer, local(SATURDAY, "06:00"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


# --- The clock changes --------------------------------------------------------------


@pytest.mark.parametrize(
    ("day_before", "start", "end", "starts_at", "ends_at"),
    [
        pytest.param(
            date(2026, 3, 26),
            "06:30",
            "07:15",
            datetime(2026, 3, 27, 3, 30, tzinfo=UTC),
            datetime(2026, 3, 27, 4, 15, tzinfo=UTC),
            id="morning-after-the-clock-goes-forward",
        ),
        pytest.param(
            date(2026, 3, 26),
            "23:00",
            "07:00",
            datetime(2026, 3, 26, 21, 0, tzinfo=UTC),
            datetime(2026, 3, 27, 4, 0, tzinfo=UTC),
            id="night-the-clock-goes-forward-seven-hours",
        ),
        pytest.param(
            date(2026, 10, 24),
            "23:00",
            "07:00",
            datetime(2026, 10, 24, 20, 0, tzinfo=UTC),
            datetime(2026, 10, 25, 5, 0, tzinfo=UTC),
            id="night-the-clock-goes-back-nine-hours",
        ),
    ],
)
async def test_window_follows_the_clock_on_dst_days(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    day_before: date,
    start: str,
    end: str,
    starts_at: datetime,
    ends_at: datetime,
) -> None:
    """In Jerusalem the clock goes from 02:00 to 03:00 on 2026-03-27 and from 03:00 to
    02:00 on 2026-10-25. A window starts and ends at the wall time it was given on both
    sides of the change: at 06:30 the morning after the first, an hour earlier by UTC
    than the day before; from 23:00 to 07:00 across either it lasts what the clock
    says, seven hours or nine."""
    await hass.config.async_set_time_zone(JERUSALEM)
    freezer.move_to(local(day_before, "12:00"))
    entry = await setup_target()
    await add_interval(hass, entry, start=start, end=end)

    await advance_to(hass, freezer, starts_at - timedelta(minutes=1))
    assert fake_target.calls == []

    await advance_to(hass, freezer, starts_at)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == ends_at.isoformat()

    await advance_to(hass, freezer, ends_at)

    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_window_inside_the_skipped_hour_runs_an_hour_later(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The clock goes from 02:00 to 03:00 on 2026-03-27, so 02:10 and 02:50 do not exist
    that day. Each happens an hour later, and the boiler runs from 03:10 to 03:50 by the
    clock on the wall, which is 00:10 to 00:50 in UTC."""
    await hass.config.async_set_time_zone(JERUSALEM)
    freezer.move_to(local(date(2026, 3, 26), "12:00"))
    entry = await setup_target()
    await add_interval(hass, entry, start="02:10", end="02:50")
    starts_at = datetime(2026, 3, 27, 0, 10, tzinfo=UTC)
    ends_at = datetime(2026, 3, 27, 0, 50, tzinfo=UTC)

    await advance_to(hass, freezer, starts_at - timedelta(minutes=1))
    assert fake_target.calls == []

    await advance_to(hass, freezer, starts_at)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == ends_at.isoformat()

    await advance_to(hass, freezer, ends_at)

    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_window_whose_shifted_start_passes_its_end_is_skipped(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """On the day the clock goes from 02:00 to 03:00, 02:50 happens at 03:50, after the
    03:10 that the interval ends at: there is no window that day, and the boiler waits
    for the next day's."""
    await hass.config.async_set_time_zone(JERUSALEM)
    freezer.move_to(local(date(2026, 3, 26), "12:00"))
    entry = await setup_target()
    await add_interval(hass, entry, start="02:50", end="03:10")
    friday = date(2026, 3, 27)

    await advance_to(hass, freezer, local(friday, "03:30"))

    assert fake_target.calls == []

    await advance_to(hass, freezer, local(friday + timedelta(days=1), "02:50"))

    assert fake_target.calls == [TURN_ON]


async def test_time_zone_change_moves_the_next_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Moving the house to Berlin on Sunday morning moves Monday's window with it: it
    starts at 06:30 in Berlin, an hour after it would have in Jerusalem."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15", weekdays=["mon"])

    await hass.config.async_update(time_zone="Europe/Berlin")
    await hass.async_block_till_done()

    await advance_to(hass, freezer, local(MONDAY, "06:30"))
    assert fake_target.calls == []

    berlin = ZoneInfo("Europe/Berlin")
    await advance_to(
        hass, freezer, datetime.combine(MONDAY, time(6, 30), berlin).astimezone(UTC)
    )

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == (
        datetime.combine(MONDAY, time(7, 15), berlin).astimezone(UTC).isoformat()
    )


async def test_timer_follows_the_time_zone_only_while_it_is_loaded(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A timer listens for the house moving to another time zone once, however often
    it is reloaded, and no longer once it is unloaded."""
    await open_sunday(hass, freezer)
    others = hass.bus.async_listeners().get(EVENT_CORE_CONFIG_UPDATE, 0)

    entry = await setup_target()
    await restart(hass, entry)

    assert hass.bus.async_listeners()[EVENT_CORE_CONFIG_UPDATE] == others + 1

    await hass.config_entries.async_unload(entry.entry_id)

    assert hass.bus.async_listeners().get(EVENT_CORE_CONFIG_UPDATE, 0) == others


async def test_time_zone_change_during_start_up_is_not_lost(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Home Assistant comes back at ten to seven, in the window, and the boiler is slow
    to answer the turn-on it is owed. The house is moved to Berlin meanwhile, where the
    window does not start until half past five by UTC: when the boiler has answered,
    the window is the Berlin one, so the boiler is stopped and runs again then."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await hass.config_entries.async_unload(entry.entry_id)
    freezer.move_to(local(SUNDAY, "06:50"))
    slow = fake_target.hold_next_call()
    await hass.config_entries.async_setup(entry.entry_id)
    await slow.reached.wait()

    await hass.config.async_update(time_zone="Europe/Berlin")
    slow.release.set()
    await hass.async_block_till_done()

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, SENSOR) == "unknown"
    berlin = ZoneInfo("Europe/Berlin")
    await advance_to(
        hass, freezer, datetime.combine(SUNDAY, time(6, 30), berlin).astimezone(UTC)
    )
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]


async def test_time_zone_change_that_opens_the_window_starts_the_boiler_at_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """In Moscow, an hour ahead of Jerusalem, it is already inside the window of 06:30
    to 07:15: moving the house there starts the boiler for the rest of the window."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")

    await hass.config.async_update(time_zone="Europe/Moscow")
    await hass.async_block_till_done()

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == datetime(2026, 1, 4, 4, 15, tzinfo=UTC).isoformat()


# --- Edits while the window runs (S2, S3) ---------------------------------------------


@pytest.mark.parametrize("end", ["07:00", "08:30"])
async def test_plus_thirty_wins_and_edits_no_longer_touch_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    end: str,
) -> None:
    """S3: ten past seven, five minutes before the window ends, the user adds half an
    hour. The boiler now runs to quarter to eight whatever the interval is edited to,
    shorter or longer, and goes off then."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    interval = await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:10"))
    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=30)
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:45")

    await edit_interval(hass, entry, interval, end=end)

    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:45")
    await advance_to(hass, freezer, local(SUNDAY, "07:30"))
    assert fake_target.calls == [TURN_ON]

    await advance_to(hass, freezer, local(SUNDAY, "07:45"))

    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_shortening_the_running_interval_moves_the_end(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """S2: an interval from six to eight, shortened at seven to end at half past, takes
    the boiler off at half past seven."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    interval = await add_interval(hass, entry, start="06:00", end="08:00")
    assert fake_target.calls == [TURN_ON]
    await advance_to(hass, freezer, local(SUNDAY, "07:00"))

    await edit_interval(hass, entry, interval, end="07:30")

    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:30")
    assert fake_target.calls == [TURN_ON]
    await advance_to(hass, freezer, local(SUNDAY, "07:30"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_extending_the_running_interval_moves_the_end(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """S2: the same interval extended at seven to end at half past eight keeps the
    boiler on until then."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    interval = await add_interval(hass, entry, start="06:00", end="08:00")
    await advance_to(hass, freezer, local(SUNDAY, "07:00"))

    await edit_interval(hass, entry, interval, end="08:30")

    assert state_of(hass, SENSOR) == iso(SUNDAY, "08:30")
    await advance_to(hass, freezer, local(SUNDAY, "08:00"))
    assert fake_target.calls == [TURN_ON]
    await advance_to(hass, freezer, local(SUNDAY, "08:30"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_moving_the_running_interval_ahead_stops_and_starts_later(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """S2: an interval from six to eight, moved at seven to half past seven to half past
    eight, takes the boiler off at once, with no countdown of the default length
    started for it, and turns it on at half past seven."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    interval = await add_interval(hass, entry, start="06:00", end="08:00")
    await advance_to(hass, freezer, local(SUNDAY, "07:00"))

    await edit_interval(hass, entry, interval, start="07:30", end="08:30")

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, TARGET_ID) == "off"
    assert state_of(hass, SENSOR) == "unknown"

    await advance_to(hass, freezer, local(SUNDAY, "07:30"))

    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "08:30")


async def test_deleting_the_running_interval_stops_the_boiler(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """S2: the interval that is running the boiler is deleted from the integration
    page; the boiler goes off and nothing is left to turn it on again."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    interval = await add_interval(hass, entry, start="06:00", end="08:00")
    await advance_to(hass, freezer, local(SUNDAY, "07:00"))

    hass.config_entries.async_remove_subentry(entry, interval)
    await hass.async_block_till_done()

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, SENSOR) == "unknown"
    await advance_to(hass, freezer, local(MONDAY, "06:00"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_overlapping_intervals_follow_the_later_end(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """From six to seven and from half past six to eight: the boiler runs to eight.
    Editing the first changes nothing; editing the second to end at half past seven
    ends the run then."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    first = await add_interval(hass, entry, start="06:00", end="07:00")
    second = await add_interval(hass, entry, start="06:30", end="08:00")
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:00")

    await advance_to(hass, freezer, local(SUNDAY, "06:30"))

    assert state_of(hass, SENSOR) == iso(SUNDAY, "08:00")

    await edit_interval(hass, entry, first, end="06:45")

    assert state_of(hass, SENSOR) == iso(SUNDAY, "08:00")

    await edit_interval(hass, entry, second, end="07:30")

    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:30")
    await advance_to(hass, freezer, local(SUNDAY, "06:45"))
    assert fake_target.calls == [TURN_ON]
    await advance_to(hass, freezer, local(SUNDAY, "07:30"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_interval_added_during_its_window_starts_now(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The window of 06:30 to 07:15 added at a quarter to seven: the boiler runs for the
    rest of it."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await advance_to(hass, freezer, local(SUNDAY, "06:45"))

    await add_interval(hass, entry, start="06:30", end="07:15")

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


# --- By hand, and across restarts (S4, S5, §5.7) -----------------------------------


async def test_manual_off_keeps_the_boiler_off_until_the_next_window_across_a_restart(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """S4: the boiler is switched off at the wall during the window. It stays off
    through the rest of the window, also when Home Assistant restarts meanwhile, and
    runs again the next morning."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "06:40"))
    await fake_target.set_state("off")
    assert state_of(hass, SENSOR) == "unknown"

    await restart(hass, entry)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == "unknown"
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, TARGET_ID) == "off"

    await advance_to(hass, freezer, local(MONDAY, "06:30"))

    assert fake_target.calls == [TURN_ON, TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, SENSOR) == iso(MONDAY, "07:15")


async def test_manual_on_during_a_window_runs_the_default_duration(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """S5: after switching the boiler off, switching it on again at ten to seven is an
    ordinary manual start, which runs for the default 45 minutes, not to the end of the
    window."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "06:40"))
    await fake_target.set_state("off")
    await advance_to(hass, freezer, local(SUNDAY, "06:50"))

    await fake_target.set_state("on")

    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:35")
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON]
    await advance_to(hass, freezer, local(SUNDAY, "07:35"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_restart_in_the_middle_of_a_window_keeps_its_end(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Home Assistant restarting at ten to seven finds the boiler running its window:
    nothing is switched and the window still ends at quarter past."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "06:50"))

    await restart(hass, entry)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_window_that_started_while_down_runs_for_the_rest(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Home Assistant is down from six to ten to seven: the window began meanwhile, so
    the boiler is switched on when it is back and runs until the window ends."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")

    await restart_after(hass, freezer, entry, minutes=50)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_overnight_restart_does_not_flap(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The boiler is running Sunday's window when Home Assistant goes down for the night
    and comes back in the middle of Monday's: the old window ended and the new one began
    while it was down, and the boiler is not switched off and on for it."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:10"))

    await restart_after(hass, freezer, entry, hours=23, minutes=35)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, SENSOR) == iso(MONDAY, "07:15")
    await advance_to(hass, freezer, local(MONDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


# --- Settings of an interval --------------------------------------------------------


async def test_interval_settings_turn_the_ac_on_cooling(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """An interval that says cooling at 24 turns the AC on that way when it starts."""
    await open_sunday(hass, freezer)
    entry = await setup_target(target=AC_ID)
    await add_interval(hass, entry, start="06:30", end="07:15", settings=COOL24)

    await advance_to(hass, freezer, local(SUNDAY, "06:30"))

    assert fake_climate.call_data == [SET_COOL, SET_24]
    assert state_of(hass, AC_ID) == "cool"
    assert state_of(hass, AC_ENDS_AT) == iso(SUNDAY, "07:15")


async def test_interval_starting_on_a_running_ac_pushes_no_settings(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Somebody started the AC on heat before the window: the window does not change
    what it runs with, and the AC runs on to the end of the window."""
    await open_sunday(hass, freezer)
    entry = await setup_target(target=AC_ID)
    await add_interval(hass, entry, start="06:30", end="07:15", settings=COOL24)
    await advance_to(hass, freezer, local(SUNDAY, "06:10"))
    await fake_climate.set_state("heat")
    assert state_of(hass, AC_ENDS_AT) == iso(SUNDAY, "06:55")

    await advance_to(hass, freezer, local(SUNDAY, "06:30"))

    assert fake_climate.call_data == []
    assert state_of(hass, AC_ID) == "heat"
    assert state_of(hass, AC_ENDS_AT) == iso(SUNDAY, "07:15")
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_climate.calls == [("turn_off", AC_ID)]


async def test_ac_back_already_on_gets_no_interval_settings(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The AC is away when its window starts and comes back running on heat: somebody
    set it up, so the interval does not. The window, not a default countdown of 20
    minutes, still ends the run."""
    await open_sunday(hass, freezer)
    entry = await setup_target(target=AC_ID, default_duration=20)
    await add_interval(hass, entry, start="06:30", end="07:15", settings=COOL24)
    await fake_climate.set_state("unavailable")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_climate.calls == []

    await fake_climate.set_state("heat")

    assert fake_climate.call_data == []
    assert state_of(hass, AC_ID) == "heat"
    assert state_of(hass, AC_ENDS_AT) == iso(SUNDAY, "07:15")


async def test_ac_back_off_is_turned_on_with_interval_settings(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The AC is away when its window starts and comes back off: it is turned on with
    what the interval says."""
    await open_sunday(hass, freezer)
    entry = await setup_target(target=AC_ID)
    await add_interval(hass, entry, start="06:30", end="07:15", settings=COOL24)
    await fake_climate.set_state("unavailable")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))

    await fake_climate.set_state("off")

    assert fake_climate.call_data == [SET_COOL, SET_24]
    assert state_of(hass, AC_ID) == "cool"


async def test_setting_the_ac_no_longer_takes_is_left_out_and_said_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The interval says cooling at 24, as the AC offered cooling when it was saved. An
    update of the AC's integration takes the mode away, and Home Assistant restarts. The
    window turns the AC on at 24 degrees, which it can still do, instead of failing on
    the mode every morning, and the log says once what is left out."""
    await open_sunday(hass, freezer)
    entry = await setup_target(target=AC_ID)
    await add_interval(hass, entry, start="06:30", end="07:15", settings=COOL24)
    fake_climate.capability_attributes["hvac_modes"] = ["off", "heat", "fan_only"]
    fake_climate.write("off")
    await restart(hass, entry)

    await advance_to(hass, freezer, local(SUNDAY, "06:30"))

    assert fake_climate.call_data == [("turn_on", {}), SET_24]
    assert state_of(hass, AC_ID) == "heat"
    assert state_of(hass, AC_ENDS_AT) == iso(SUNDAY, "07:15")
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    await advance_to(hass, freezer, local(MONDAY, "06:30"))
    assert fake_climate.call_data[-2:] == [("turn_on", {}), SET_24]
    assert timerify_warnings(caplog) == [
        "The schedule interval 06:30–07:15, Mon–Sun of climate.ac asks for settings"
        " that the target cannot take now (hvac_mode); it is turned on without them"
    ]


async def test_setting_that_comes_back_and_goes_again_is_said_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_climate: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Saying it once is for as long as the mode is missing: when the AC offers it
    again the interval uses it, and when it is taken away a second time the log says so
    again."""
    await open_sunday(hass, freezer)
    entry = await setup_target(target=AC_ID)
    await add_interval(hass, entry, start="06:30", end="07:15", settings=COOL24)
    offered = fake_climate.capability_attributes["hvac_modes"]
    fake_climate.capability_attributes["hvac_modes"] = ["off", "heat", "fan_only"]
    fake_climate.write("off")
    await restart(hass, entry)
    assert len(timerify_warnings(caplog)) == 1

    fake_climate.capability_attributes["hvac_modes"] = offered
    fake_climate.write("off")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    await advance_to(hass, freezer, local(MONDAY, "06:30"))

    assert fake_climate.call_data[-2:] == [SET_COOL, SET_24]
    assert len(timerify_warnings(caplog)) == 1
    fake_climate.capability_attributes["hvac_modes"] = ["off", "heat", "fan_only"]
    fake_climate.write("off")
    await advance_to(hass, freezer, local(MONDAY, "07:15"))
    await advance_to(hass, freezer, local(SUNDAY + timedelta(days=2), "06:30"))

    assert len(timerify_warnings(caplog)) == 2
    assert fake_climate.call_data[-2:] == [("turn_on", {}), SET_24]


# --- What the log says ----------------------------------------------------------------


async def test_window_start_while_unavailable_is_logged(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Nothing else shows that the boiler is switched on only when it is back: the log
    says so once, when the window starts."""
    caplog.set_level(logging.INFO, logger="custom_components.timerify")
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await fake_target.set_state("unavailable")

    await advance_to(hass, freezer, local(SUNDAY, "06:30"))

    assert timerify_info(caplog) == [WINDOW_STARTED_WHILE_UNAVAILABLE]
    assert fake_target.calls == []

    await fake_target.set_state("off")

    assert fake_target.calls == [TURN_ON]
    assert timerify_info(caplog) == [WINDOW_STARTED_WHILE_UNAVAILABLE]


async def test_window_start_that_leaves_the_timer_alone_is_not_logged(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The timer already runs past the end of the window, so the window turns nothing
    on when the boiler is back, and the log does not say it will."""
    caplog.set_level(logging.INFO, logger="custom_components.timerify")
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    await call_service(hass, "run", {"entity_id": NUMBER}, minutes=120)
    await fake_target.set_state("unavailable")

    await advance_to(hass, freezer, local(SUNDAY, "06:30"))

    assert timerify_info(caplog) == []
    assert state_of(hass, SENSOR) == iso(SUNDAY, "08:00")


# --- The functions that place a window ------------------------------------------------


def interval(start: str, end: str, weekdays: tuple[str, ...] = WEEK) -> Interval:
    return Interval(
        id="boiler-morning",
        days="weekdays",
        weekdays=frozenset(weekdays),
        start=time.fromisoformat(start),
        end=time.fromisoformat(end),
        settings=freeze_settings({"temperature": 24}),
    )


def test_window_on_a_plain_day_is_the_wall_time_in_utc() -> None:
    """The window of an interval carries its settings and its times in UTC."""
    window = window_on(interval("06:30", "07:15"), SUNDAY, ZoneInfo(JERUSALEM))

    assert window == Window(
        "boiler-morning",
        datetime(2026, 1, 4, 4, 30, tzinfo=UTC),
        datetime(2026, 1, 4, 5, 15, tzinfo=UTC),
        freeze_settings({"temperature": 24}),
    )


def test_window_ends_the_next_day_when_the_interval_ends_before_it_starts() -> None:
    window = window_on(interval("22:00", "06:00"), FRIDAY, ZoneInfo(JERUSALEM))

    assert window is not None
    assert window.start == local(FRIDAY, "22:00")
    assert window.end == local(SATURDAY, "06:00")


def test_window_in_the_hour_the_clock_skips_lands_later_by_the_gap() -> None:
    """02:30 does not exist on 2026-03-27 in Jerusalem; the window opens at 03:30."""
    zone = ZoneInfo(JERUSALEM)
    window = window_on(interval("02:30", "04:00"), date(2026, 3, 27), zone)

    assert window is not None
    assert window.start.astimezone(zone).time() == time(3, 30)
    assert window.end.astimezone(zone).time() == time(4, 0)


def test_window_whose_shifted_start_reaches_its_end_is_swallowed() -> None:
    """02:50 does not exist on 2026-03-27 in Jerusalem and happens at 03:50, after the
    03:10 that the window ends at; so do 02:30 to 03:15 and 02:00 to 03:00."""
    zone = ZoneInfo(JERUSALEM)
    day = date(2026, 3, 27)

    assert window_on(interval("02:30", "03:15"), day, zone) is None
    assert window_on(interval("02:00", "03:00"), day, zone) is None
    assert window_on(interval("02:50", "03:10"), day, zone) is None


def test_window_in_the_hour_the_clock_repeats_starts_at_its_first_time() -> None:
    """01:30 comes twice on 2026-10-25 in Jerusalem; the window starts at the first."""
    zone = ZoneInfo(JERUSALEM)
    window = window_on(interval("01:30", "03:00"), date(2026, 10, 25), zone)

    assert window is not None
    assert window.start == datetime(2026, 10, 24, 22, 30, tzinfo=UTC)
    assert window.end == datetime(2026, 10, 25, 1, 0, tzinfo=UTC)


def test_window_never_lasts_longer_than_a_day() -> None:
    """From 06:00 to 05:59 the next day is a minute short of a day by the clock, and a
    day and an hour of real time on the day the clock goes back: it is cut at a day."""
    zone = ZoneInfo(JERUSALEM)
    window = window_on(interval("06:00", "05:59"), date(2026, 10, 24), zone)

    assert window is not None
    assert window.end - window.start == timedelta(minutes=MAX_MINUTES)


def test_days_around_start_with_yesterday_and_reach_the_search_horizon() -> None:
    days = list(days_around(local(SUNDAY, "23:30"), ZoneInfo(JERUSALEM)))

    assert days[0] == SUNDAY - timedelta(days=1)
    assert days[1] == SUNDAY
    assert days[-1] == SUNDAY + timedelta(days=WINDOW_SEARCH_DAYS)
    assert len(days) == WINDOW_SEARCH_DAYS + 2


def test_days_around_follow_the_wall_clock_of_the_zone_not_utc() -> None:
    """Half past midnight in Jerusalem is Monday there and still Sunday in UTC."""
    now = datetime(2026, 1, 4, 22, 30, tzinfo=UTC)

    assert next(days_around(now, ZoneInfo(JERUSALEM))) == SUNDAY
    assert next(days_around(now, ZoneInfo("UTC"))) == SUNDAY - timedelta(days=1)


def test_weekday_window_is_the_open_one_before_the_next_one() -> None:
    """In the middle of the Friday-night window, Saturday morning, that window is the
    one; once it is over it is next Friday's."""
    zone = ZoneInfo(JERUSALEM)
    friday_night = interval("22:00", "06:00", ("fri",))

    inside = weekday_window(friday_night, local(SATURDAY, "02:00"), zone)
    after = weekday_window(friday_night, local(SATURDAY, "06:00"), zone)

    assert inside is not None
    assert (inside.start, inside.end) == (
        local(FRIDAY, "22:00"),
        local(SATURDAY, "06:00"),
    )
    assert after is not None
    assert after.start == local(FRIDAY + timedelta(days=7), "22:00")
