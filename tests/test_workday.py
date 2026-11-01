"""Intervals that run on working days or on days off, as a Workday sensor says.

The scenarios are the owner's boiler in Israel, where the week runs from Sunday to
Thursday: a morning window on working days and another on the days off, a holiday that
the sensor does not call a working day, a sensor that is away, one that is slow. They
run on the wall clock of Jerusalem with the clock frozen on a Sunday morning, and step
to each event with its own jump: one jump is one catch-up.
"""

import copy
import logging
from datetime import date, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import holidays
import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components import workday
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.core import CoreState, HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.json import json_loads_object
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.timerify.const import (
    CONF_DEFAULT_DURATION,
    CONF_MODE,
    CONF_TARGET,
    CONF_WORKDAY_SENSOR,
    DOMAIN,
    WINDOW_SEARCH_DAYS,
    DaysMode,
    freeze_settings,
)
from custom_components.timerify.schedule import Interval, workday_window

from .conftest import NO_ENTITY_MATCHED, FakeTarget, FakeWorkday, SetupTarget
from .helpers import (
    JERUSALEM,
    NUMBER,
    SENSOR,
    SUNDAY,
    TARGET_ID,
    TURN_OFF,
    TURN_ON,
    add_interval,
    advance_to,
    edit_interval,
    iso,
    local,
    open_sunday,
    restart,
    saved,
    set_number,
    set_switch,
    state_of,
    storage_key,
    timerify_info,
    timerify_warnings,
)

pytestmark = pytest.mark.usefixtures("hass_storage")

MONDAY = SUNDAY + timedelta(days=1)
FRIDAY = SUNDAY + timedelta(days=5)
SATURDAY = SUNDAY + timedelta(days=6)
NEXT_SUNDAY = SUNDAY + timedelta(days=7)

WORKING_DAYS_SWITCH = "switch.boiler_schedule_06_30_07_15_working_days"

NOT_ASKED = "Could not ask binary_sensor.workday_sensor whether"
"""How the warning about a day the sensor could not answer for begins."""

RENAMED_SENSOR = "binary_sensor.workday"
"""The entity id the user gives the Workday sensor in the scenarios of a rename."""

WINDOW_STARTED_WHILE_UNAVAILABLE = (
    "A schedule window of switch.boiler started while it is unavailable;"
    " it is turned on when it is back, if the window is still open then"
)


async def set_up_boiler(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_target: SetupTarget,
    fake_workday: FakeWorkday,
) -> MockConfigEntry:
    """A boiler timer that asks the Workday sensor, on Sunday at six in the morning."""
    await open_sunday(hass, freezer)
    return await setup_target(workday_sensor=fake_workday.entity_id)


# --- The owner's week ---------------------------------------------------------------


async def test_owner_boiler_week(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """The boiler runs 06:30 to 07:15 on working days and 08:00 to 09:00 on the days
    off: five mornings from Sunday to Thursday, then Friday and Saturday, then Sunday
    again."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await add_interval(hass, entry, days="non_workdays", start="08:00", end="09:00")
    expected: list[tuple[str, str]] = []

    for day in (SUNDAY + timedelta(days=n) for n in range(5)):
        await advance_to(hass, freezer, local(day, "06:30"))
        expected.append(TURN_ON)
        assert fake_target.calls == expected
        assert state_of(hass, SENSOR) == iso(day, "07:15")
        await advance_to(hass, freezer, local(day, "07:15"))
        expected.append(TURN_OFF)
        assert fake_target.calls == expected
        await advance_to(hass, freezer, local(day, "08:00"))
        assert fake_target.calls == expected  # A working day has no morning off.
        assert state_of(hass, SENSOR) == "unknown"
        await advance_to(hass, freezer, local(day, "09:00"))
        assert fake_target.calls == expected

    for day in (FRIDAY, SATURDAY):
        await advance_to(hass, freezer, local(day, "06:30"))
        assert fake_target.calls == expected  # A day off has no working morning.
        await advance_to(hass, freezer, local(day, "08:00"))
        expected.append(TURN_ON)
        assert fake_target.calls == expected
        assert state_of(hass, SENSOR) == iso(day, "09:00")
        await advance_to(hass, freezer, local(day, "09:00"))
        expected.append(TURN_OFF)
        assert fake_target.calls == expected

    await advance_to(hass, freezer, local(NEXT_SUNDAY, "06:30"))
    expected.append(TURN_ON)
    assert fake_target.calls == expected
    assert state_of(hass, SENSOR) == iso(NEXT_SUNDAY, "07:15")


async def test_holiday_runs_the_non_working_day_interval(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """A holiday in the middle of the week is a day off: Tuesday has no morning window
    of working days, has the one of days off, and Wednesday is a working day again."""
    tuesday = SUNDAY + timedelta(days=2)
    fake_workday.holidays = {tuesday}
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    freezer.move_to(local(MONDAY, "20:00"))
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await add_interval(hass, entry, days="non_workdays", start="08:00", end="09:00")

    await advance_to(hass, freezer, local(tuesday, "06:30"))

    assert fake_target.calls == []

    await advance_to(hass, freezer, local(tuesday, "08:00"))

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(tuesday, "09:00")
    await advance_to(hass, freezer, local(tuesday, "09:00"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    await advance_to(hass, freezer, local(tuesday + timedelta(days=1), "06:30"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]


async def test_workday_interval_across_midnight_asks_about_the_day_it_starts_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """The night from Thursday 22:00 to Friday 06:00 belongs to Thursday, a working
    day, although Friday is not one."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    thursday = SUNDAY + timedelta(days=4)
    freezer.move_to(local(thursday, "12:00"))
    await add_interval(hass, entry, days="workdays", start="22:00", end="06:00")

    await advance_to(hass, freezer, local(thursday, "22:00"))

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(FRIDAY, "06:00")
    await advance_to(hass, freezer, local(FRIDAY, "06:00"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    await advance_to(hass, freezer, local(NEXT_SUNDAY, "22:00"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]


# --- The sensor is away -------------------------------------------------------------


async def test_unavailable_workday_sensor_delays_the_window_until_it_reports(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The sensor is away from before Sunday's window is over, so nobody can say
    whether Monday is a working day. The boiler stays off at 06:30 and the log says why,
    once. When the sensor reports at 06:40 the window is worked out, it is open, and the
    boiler runs for the rest of it."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await fake_workday.set_available(False)
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]  # Sunday's window was known.

    await advance_to(hass, freezer, local(MONDAY, "06:30"))

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    (warning,) = timerify_warnings(caplog)
    assert warning.startswith(NOT_ASKED)
    assert "the schedule of switch.boiler waits until it reports" in warning

    await advance_to(hass, freezer, local(MONDAY, "06:40"))
    await fake_workday.set_available(True)

    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]
    assert state_of(hass, SENSOR) == iso(MONDAY, "07:15")
    await advance_to(hass, freezer, local(MONDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON, TURN_OFF]
    assert len(timerify_warnings(caplog)) == 1


async def test_workday_sensor_that_is_away_at_start_up_delays_the_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Home Assistant starts at ten to seven with the Workday integration still loading:
    the window that is open is not started, the log says why, and it runs for the rest
    of it once the sensor is up."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await fake_workday.set_available(False)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    caplog.clear()
    freezer.move_to(local(SUNDAY, "06:50"))
    await restart(hass, entry)

    assert fake_target.calls == []
    assert state_of(hass, SENSOR) == "unknown"
    (warning,) = timerify_warnings(caplog)
    assert warning.startswith(NOT_ASKED)

    await fake_workday.set_available(True)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")


async def test_failed_check_is_logged_once_per_outage(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """However often the timer asks while the sensor is away, the log has one line; an
    answer ends the outage, and the next one is a line of its own."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")

    await fake_workday.set_available(False)
    await fake_workday.report()
    await fake_workday.report()

    assert len(timerify_warnings(caplog)) == 1

    await fake_workday.set_available(True)
    await fake_workday.report()

    assert len(timerify_warnings(caplog)) == 1

    await fake_workday.set_available(False)

    assert [w.startswith(NOT_ASKED) for w in timerify_warnings(caplog)] == [True] * 2


async def test_failed_check_names_the_reason_in_the_log(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The line says which sensor, which day and what it answered."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")

    fake_workday.fail_next_call(HomeAssistantError("The country is not known"))
    await fake_workday.report()

    assert timerify_warnings(caplog) == [
        "Could not ask binary_sensor.workday_sensor whether 2026-01-04 is a working"
        " day (The country is not known); the schedule of switch.boiler waits until"
        " it reports"
    ]


async def test_check_that_gets_no_answer_in_time_is_unknown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A sensor that does not answer within the time a service call may take counts as
    away: the refresh ends, the boiler is not touched, and the next report asks
    again."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    slow = fake_workday.hold_next_call()
    fake_workday.write()
    await slow.reached.wait()

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    (warning,) = timerify_warnings(caplog)
    assert "no answer within 30 s" in warning
    assert fake_target.calls == []
    slow.release.set()
    await hass.async_block_till_done()
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == [TURN_ON]  # Its window was known, and is kept.


async def test_failed_check_is_asked_again_when_the_sensor_reports_unchanged(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """The sensor fails once, when Sunday's window is over and Monday's is to be worked
    out, and says nothing new: it is on, and stays on. At midnight it writes its state
    again, as Workday does every day, and the window is worked out then."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    fake_workday.fail_next_call()
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]

    await advance_to(hass, freezer, local(MONDAY, "00:00"))
    assert fake_workday.asked == [
        SUNDAY,
        MONDAY,
    ]  # At start-up, then the one that failed.
    await fake_workday.report()

    assert fake_workday.asked == [SUNDAY, MONDAY, MONDAY]
    await advance_to(hass, freezer, local(MONDAY, "06:30"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]
    assert state_of(hass, SENSOR) == iso(MONDAY, "07:15")


async def test_an_unknown_answer_leaves_a_running_window_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """The window began at 06:30. The sensor goes away at 06:40, which asks the timer to
    work its windows out again, and nobody can answer: the boiler is not stopped for
    that, the window ends at 07:15 as it was to, and the boiler goes off then."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "06:40"))

    await fake_workday.set_available(False)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, SENSOR) == "unknown"


async def test_an_unknown_answer_leaves_a_window_that_has_not_begun_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """The window was worked out when the sensor could still answer, and it begins
    though the sensor is away by then: the answer for its day is known."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")

    await fake_workday.set_available(False)
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")


async def test_an_unknown_answer_ends_the_questions_of_that_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """With the sensor away and three intervals that ask it, the timer asks once and
    not three times, nor once for each of the days it would look at."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await add_interval(hass, entry, days="non_workdays", start="08:00", end="09:00")
    await add_interval(hass, entry, days="workdays", start="10:00", end="11:00")
    await fake_workday.set_available(False)
    fake_workday.asked.clear()

    await fake_workday.report()

    assert fake_workday.asked == [SUNDAY]


async def test_each_day_is_asked_once_per_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """Two intervals that look at the same days share the answers: the timer asks about
    Sunday to Friday, once each, to find the first day off."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await add_interval(hass, entry, days="non_workdays", start="08:00", end="09:00")
    fake_workday.asked.clear()

    await restart(hass, entry)

    assert fake_workday.asked == [SUNDAY + timedelta(days=n) for n in range(6)]


async def test_weekday_intervals_ask_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """An interval that names its weekdays does not need the sensor, though the timer
    has one."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, start="06:30", end="07:15", weekdays=["mon"])

    await restart(hass, entry)
    await fake_workday.report()

    assert fake_workday.asked == []


async def test_workday_sensor_state_is_followed_only_while_the_timer_is_loaded(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """An unloaded timer asks nobody anything when the sensor reports."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await hass.config_entries.async_unload(entry.entry_id)
    fake_workday.asked.clear()

    await fake_workday.set_available(False)
    await fake_workday.report()

    assert fake_workday.asked == []


async def test_weekday_intervals_run_while_the_sensor_is_away(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """What is wrong with the sensor is wrong only for the intervals that ask it: one
    that names its weekdays has its window as ever."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await fake_workday.set_available(False)

    await add_interval(hass, entry, start="08:00", end="09:00", weekdays=["mon"])

    await advance_to(hass, freezer, local(MONDAY, "08:00"))

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(MONDAY, "09:00")


async def test_window_that_is_stored_stays_while_the_sensor_is_away_at_start_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """The boiler runs the window of 06:30 and Home Assistant restarts at ten to seven
    with the Workday integration still loading. The answer for the window's day was
    known before: the window goes on, and the boiler is not switched off and on."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "06:50"))
    await fake_workday.set_available(False)

    await restart(hass, entry)

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]


async def test_workday_integration_that_is_not_loaded_is_a_sensor_that_is_away(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """With no `workday.check_date` in the house, the window waits and the log says what
    was missing."""
    await open_sunday(hass, freezer)
    entry = await setup_target(workday_sensor="binary_sensor.workday_sensor")

    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")

    (warning,) = timerify_warnings(caplog)
    assert warning.startswith(NOT_ASKED)
    assert "workday.check_date" in warning
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == []


async def test_answer_that_is_not_about_the_sensor_is_unknown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A service that answers for some other sensor, or in some other words, has not
    said whether the day is a working one."""

    async def answers_for_another(call: ServiceCall) -> dict[str, Any]:
        return {"binary_sensor.other": {"workday": True}}

    hass.services.async_register(
        "workday",
        "check_date",
        answers_for_another,
        supports_response=SupportsResponse.ONLY,
    )
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)

    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")

    (warning,) = timerify_warnings(caplog)
    assert warning.startswith(NOT_ASKED)
    assert "binary_sensor.other" in warning
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == []


async def test_sensor_that_breaks_does_not_stop_a_running_countdown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The boiler runs a ten-minute countdown when Home Assistant restarts, and the
    Workday integration, which has a bug, raises something nobody expected when it is
    asked. The windows wait, the log says why, and the boiler still goes off when its
    countdown is over: a timer is not the thing to break because of a sensor."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await set_number(hass, NUMBER, 10)
    fake_workday.fail_next_call(ValueError("Workday is broken"))

    await restart(hass, entry)

    (warning,) = timerify_warnings(caplog)
    assert warning.startswith(NOT_ASKED)
    assert "ValueError: Workday is broken" in warning
    assert state_of(hass, SENSOR) == iso(SUNDAY, "06:10")
    await advance_to(hass, freezer, local(SUNDAY, "06:10"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]  # Its window was known.


async def test_switching_on_when_the_sensor_breaks_changes_the_flag_and_nothing_else(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The flip succeeds, as it does when the sensor is away: the interval is on, in the
    file and on the dashboard alike, and its window comes when the sensor is heard
    from."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await set_switch(hass, WORKING_DAYS_SWITCH, False)
    fake_workday.fail_next_call(ValueError("Workday is broken"))

    await set_switch(hass, WORKING_DAYS_SWITCH, True)

    assert state_of(hass, WORKING_DAYS_SWITCH) == "on"
    assert saved(hass_storage, entry)["disabled_intervals"] == []
    assert saved(hass_storage, entry)["windows"] == []
    (warning,) = timerify_warnings(caplog)
    assert warning.startswith(NOT_ASKED)
    await fake_workday.report()
    assert len(saved(hass_storage, entry)["windows"]) == 1
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == [TURN_ON]


async def test_timer_without_a_sensor_does_not_load_with_intervals_that_need_one(
    hass: HomeAssistant, fake_target: FakeTarget
) -> None:
    """The form does not let an interval of working days in, nor the sensor out, but a
    file that says it can be edited by hand: the timer says what is wrong instead of
    guessing at the days."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        title="Boiler",
        options={
            CONF_TARGET: TARGET_ID,
            CONF_MODE: "strict",
            CONF_DEFAULT_DURATION: 45,
        },
        subentries_data=[
            ConfigSubentryData(
                data={
                    "days": "workdays",
                    "weekdays": [],
                    "start": "06:30",
                    "end": "07:15",
                    "settings": {},
                },
                subentry_type="interval",
                title="06:30–07:15, Working days",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "workday_sensor_missing"
    assert entry.reason is not None
    assert "no Workday sensor" in entry.reason


# --- The sensor is slow -------------------------------------------------------------


async def test_window_that_ends_while_the_sensor_is_slow_at_start_up_is_replaced(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """Home Assistant starts at ten past seven, inside Sunday's window, and the sensor
    is slow to answer. When it has answered the window is over: the boiler is not
    started for the end of a window, and Monday's window is there."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await hass.config_entries.async_unload(entry.entry_id)
    freezer.move_to(local(SUNDAY, "07:10"))
    slow = fake_workday.hold_next_call()
    await hass.config_entries.async_setup(entry.entry_id)
    await slow.reached.wait()

    freezer.move_to(local(SUNDAY, "07:15"))
    slow.release.set()
    await hass.async_block_till_done()

    assert fake_target.calls == []
    await advance_to(hass, freezer, local(MONDAY, "06:30"))
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(MONDAY, "07:15")


async def test_window_that_ends_while_the_sensor_is_slow_is_replaced_by_tomorrows(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """The boiler is running Sunday's window. At ten past seven the sensor reports, is
    slow to answer, and the window is over when it has: the boiler goes off, and
    Monday's window is still worked out."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    freezer.move_to(local(SUNDAY, "07:10"))
    slow = fake_workday.hold_next_call()
    fake_workday.write()
    await slow.reached.wait()
    freezer.move_to(local(SUNDAY, "07:15"))
    async_fire_time_changed(hass)

    slow.release.set()
    await hass.async_block_till_done()

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, SENSOR) == "unknown"
    await advance_to(hass, freezer, local(MONDAY, "06:30"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]
    assert state_of(hass, SENSOR) == iso(MONDAY, "07:15")


async def test_window_that_starts_while_the_sensor_is_slow_is_logged_when_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The boiler is away and the sensor reports slowly across the start of the window:
    the answer comes when the window is open, the window starts at once, and the log
    says that the boiler is switched on only when it is back, as it does for a window
    that starts at its own time."""
    caplog.set_level(logging.INFO, logger="custom_components.timerify")
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await fake_target.set_state("unavailable")
    freezer.move_to(local(SUNDAY, "06:29:45"))
    slow = fake_workday.hold_next_call()
    fake_workday.write()
    await slow.reached.wait()
    freezer.move_to(local(SUNDAY, "06:30:10"))
    async_fire_time_changed(hass)

    slow.release.set()
    await hass.async_block_till_done()

    assert timerify_info(caplog) == [WINDOW_STARTED_WHILE_UNAVAILABLE]
    await fake_target.set_state("off")
    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")


async def test_window_made_by_a_slow_refresh_comes_before_a_later_command(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """The user switches the morning interval on at 06:29:45 and the sensor is slow to
    answer, so the window comes from that very refresh. The answer arrives after 06:30,
    and the half hour the user asked for at 06:30:10 queues behind it. The window
    opened first and goes first, so the half hour is the later word and sets the end:
    the boiler runs until 07:00:10, not until the window's 07:15. Every time event is
    delivered."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await set_switch(hass, WORKING_DAYS_SWITCH, False)
    freezer.move_to(local(SUNDAY, "06:29:45"))
    async_fire_time_changed(hass)
    slow = fake_workday.hold_next_call()
    enabling = hass.async_create_task(
        hass.services.async_call(
            "switch", "turn_on", {"entity_id": WORKING_DAYS_SWITCH}, blocking=True
        )
    )
    await slow.reached.wait()
    freezer.move_to(local(SUNDAY, "06:30:10"))
    async_fire_time_changed(hass)
    running = hass.async_create_task(
        hass.services.async_call(
            DOMAIN, "run", {"entity_id": NUMBER, "minutes": 30}, blocking=True
        )
    )

    slow.release.set()
    await enabling
    await running
    await hass.async_block_till_done()

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:00:10")


async def test_sensor_that_comes_back_while_the_timer_starts_is_not_missed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """The timer starts at 06:40 and asks a sensor that is away; the answer is slow to
    come, and the sensor is back before it does. The report is not lost: the window is
    worked out again, and the boiler runs for the rest of it."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await fake_workday.set_available(False)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await hass.config_entries.async_unload(entry.entry_id)
    freezer.move_to(local(SUNDAY, "06:40"))
    slow = fake_workday.hold_next_call()
    await hass.config_entries.async_setup(entry.entry_id)
    await slow.reached.wait()

    fake_workday.write(True)
    slow.release.set()
    await hass.async_block_till_done()

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")


async def test_timer_unloaded_while_the_sensor_is_slow_at_start_up_changes_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A timer that is replaced while it waits for the sensor leaves the boiler and its
    file to the one that replaces it."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await hass.config_entries.async_unload(entry.entry_id)
    freezer.move_to(local(SUNDAY, "06:40"))
    slow = fake_workday.hold_next_call()
    await hass.config_entries.async_setup(entry.entry_id)
    await slow.reached.wait()
    await hass.config_entries.async_unload(entry.entry_id)
    stored = copy.deepcopy(hass_storage[storage_key(entry)])

    slow.release.set()
    await hass.async_block_till_done()

    assert fake_target.calls == []
    assert hass_storage[storage_key(entry)] == stored


async def test_timer_unloaded_while_the_sensor_is_slow_changes_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """The window is open and the sensor reports slowly; the timer is replaced while it
    waits, and the window is over when the answer comes: the old timer neither stops the
    boiler nor writes its file."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    freezer.move_to(local(SUNDAY, "07:10"))
    slow = fake_workday.hold_next_call()
    fake_workday.write()
    await slow.reached.wait()
    await hass.config_entries.async_unload(entry.entry_id)
    stored = copy.deepcopy(hass_storage[storage_key(entry)])

    freezer.move_to(local(SUNDAY, "07:15"))
    slow.release.set()
    await hass.async_block_till_done()

    assert fake_target.calls == [TURN_ON]
    assert hass_storage[storage_key(entry)] == stored


async def test_workday_sensor_is_followed_from_the_moment_home_assistant_has_started(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """While Home Assistant is starting, a report of the sensor asks nothing: the
    first look at the windows is the start-up's, after the first look at the target."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await hass.config_entries.async_unload(entry.entry_id)
    hass.set_state(CoreState.not_running)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    fake_workday.asked.clear()

    await fake_workday.report()

    assert fake_workday.asked == []
    await hass.async_start()
    await hass.async_block_till_done()
    assert fake_workday.asked == [SUNDAY]
    await fake_workday.report()
    assert fake_workday.asked == [SUNDAY, SUNDAY]


async def test_editing_a_running_interval_to_days_off_stops_the_boiler(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """The boiler runs the morning of a working day. The interval is changed to the days
    off: today is not one, so the window is not today's any more, the boiler stops at
    once, and runs on the next day off."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    subentry_id = await add_interval(
        hass, entry, days="workdays", start="06:30", end="07:15"
    )
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "06:40"))

    await edit_interval(hass, entry, subentry_id, days="non_workdays")

    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert state_of(hass, SENSOR) == "unknown"
    await advance_to(hass, freezer, local(FRIDAY, "06:30"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]
    assert state_of(hass, SENSOR) == iso(FRIDAY, "07:15")


# --- The interval's switch ----------------------------------------------------------


async def test_switching_an_interval_on_asks_the_sensor_for_its_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """An interval that was off has no window; switching it on works it out, from the
    sensor, and the boiler runs when it comes."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await set_switch(hass, WORKING_DAYS_SWITCH, False)
    fake_workday.asked.clear()

    await set_switch(hass, WORKING_DAYS_SWITCH, True)

    assert fake_workday.asked == [SUNDAY]
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == [TURN_ON]


async def test_switching_an_interval_on_that_is_on_asks_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """Turning on a switch that is on changes nothing, and does not bother the sensor
    to say it again."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    fake_workday.asked.clear()
    stored = copy.deepcopy(hass_storage[storage_key(entry)])

    await set_switch(hass, WORKING_DAYS_SWITCH, True)

    assert fake_workday.asked == []
    assert hass_storage[storage_key(entry)] == stored


async def test_a_switched_off_interval_is_not_asked_about(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """An interval that is off has no window to work out, so a report of the sensor
    asks nothing for it."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await set_switch(hass, WORKING_DAYS_SWITCH, False)
    fake_workday.asked.clear()

    await fake_workday.report()

    assert fake_workday.asked == []


@pytest.mark.parametrize("unload_first", [False, True], ids=["answered", "unloaded"])
async def test_switching_on_while_the_sensor_is_slow(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
    unload_first: bool,
) -> None:
    """The switch is flipped on and the sensor is slow to answer. Until it has, nothing
    is kept: a timer that is replaced meanwhile fails the flip and says nothing was
    changed, which is true, since the flag was never saved; one that stays saves the
    flag and the window together."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await set_switch(hass, WORKING_DAYS_SWITCH, False)
    slow = fake_workday.hold_next_call()
    flipping = hass.async_create_task(
        hass.services.async_call(
            "switch", "turn_on", {"entity_id": WORKING_DAYS_SWITCH}, blocking=True
        )
    )
    await slow.reached.wait()
    assert saved(hass_storage, entry)["disabled_intervals"] != []
    assert state_of(hass, WORKING_DAYS_SWITCH) == "off"
    if unload_first:
        await hass.config_entries.async_unload(entry.entry_id)
    stored = copy.deepcopy(hass_storage[storage_key(entry)])

    slow.release.set()
    if unload_first:
        with pytest.raises(HomeAssistantError) as raised:
            await flipping
        assert raised.value.translation_domain == DOMAIN
        assert raised.value.translation_key == "timer_unloaded"
        assert hass_storage[storage_key(entry)] == stored
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert state_of(hass, WORKING_DAYS_SWITCH) == "off"
    else:
        await flipping
        await hass.async_block_till_done()
        assert state_of(hass, WORKING_DAYS_SWITCH) == "on"
        assert saved(hass_storage, entry)["disabled_intervals"] == []
        assert len(saved(hass_storage, entry)["windows"]) == 1


# --- The sensor is renamed or removed -----------------------------------------------


async def test_renaming_the_workday_sensor_follows_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The user renames the sensor on Sunday morning: the timer keeps the new id in its
    options, asks about Monday when Sunday's window is over, and starts Monday's window
    at its time, with nothing in the log about a sensor that cannot be found."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")

    await fake_workday.rename(RENAMED_SENSOR)

    assert entry.options[CONF_WORKDAY_SENSOR] == RENAMED_SENSOR
    assert entry.state is ConfigEntryState.LOADED
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    await advance_to(hass, freezer, local(MONDAY, "06:30"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]
    assert state_of(hass, SENSOR) == iso(MONDAY, "07:15")
    assert timerify_warnings(caplog) == []
    assert "did not match any entities" not in caplog.text


async def test_renaming_the_workday_sensor_keeps_an_open_window(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
) -> None:
    """The boiler is running its morning window when the sensor is renamed: the timer
    reloads, the boiler stays on, nothing is sent to it, and the window ends at its
    time."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "06:50"))
    assert fake_target.calls == [TURN_ON]

    await fake_workday.rename(RENAMED_SENSOR)

    assert entry.options[CONF_WORKDAY_SENSOR] == RENAMED_SENSOR
    assert entry.state is ConfigEntryState.LOADED
    assert fake_target.calls == [TURN_ON]
    assert fake_target.state == "on"
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]
    assert fake_target.state == "off"


async def test_a_removed_workday_sensor_is_not_followed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    fake_workday: FakeWorkday,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The user deletes the sensor: there is no new id to follow, so the option keeps
    the old one and the timer stays loaded. It behaves as for a sensor that is away,
    with one line in the log, and the windows it has worked out stay."""
    entry = await set_up_boiler(hass, freezer, setup_target, fake_workday)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    controller = entry.runtime_data
    caplog.clear()

    await fake_workday.remove()

    assert entry.options[CONF_WORKDAY_SENSOR] == fake_workday.entity_id
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is controller  # It was not reloaded.
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []
    (warning,) = timerify_warnings(caplog)
    assert warning.startswith(NOT_ASKED)
    assert "did not match any entities" in warning
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == [TURN_ON]
    assert len(timerify_warnings(caplog)) == 1


# --- The search for a window --------------------------------------------------------


def interval_of(days: DaysMode, start: str = "06:30", end: str = "07:15") -> Interval:
    """An interval of working days (or days off) from `start` to `end`."""
    return Interval(
        id="morning",
        days=days,
        weekdays=frozenset(),
        start=time.fromisoformat(start),
        end=time.fromisoformat(end),
        settings=freeze_settings({}),
    )


class IsraeliWeek:
    """Working days from Sunday to Thursday; it records the days it is asked about."""

    def __init__(self) -> None:
        self.asked: list[date] = []

    async def __call__(self, day: date) -> bool:
        self.asked.append(day)
        return day.weekday() in (6, 0, 1, 2, 3)


async def test_search_takes_the_first_window_on_a_working_day() -> None:
    """On Friday noon the morning is over, Saturday is not a working day, Sunday is:
    those are the days asked about, and not the ones whose window is already over."""
    week = IsraeliWeek()

    window = await workday_window(
        interval_of("workdays"),
        local(FRIDAY, "12:00"),
        ZoneInfo(JERUSALEM),
        week,
    )

    assert window is not None
    assert (window.start, window.end) == (
        local(NEXT_SUNDAY, "06:30"),
        local(NEXT_SUNDAY, "07:15"),
    )
    assert week.asked == [SATURDAY, NEXT_SUNDAY]


async def test_search_takes_the_first_window_on_a_day_off() -> None:
    """The open window of a day off is the one; the morning of a working day is not."""
    week = IsraeliWeek()

    inside = await workday_window(
        interval_of("non_workdays"),
        local(FRIDAY, "06:45"),
        ZoneInfo(JERUSALEM),
        week,
    )
    after = await workday_window(
        interval_of("non_workdays"),
        local(FRIDAY, "07:15"),
        ZoneInfo(JERUSALEM),
        week,
    )

    assert inside is not None
    assert inside.start == local(FRIDAY, "06:30")
    assert after is not None
    assert after.start == local(SATURDAY, "06:30")


async def test_search_gives_up_after_the_days_it_looks_at() -> None:
    """With no working day in sight there is no window, and every day ahead is asked
    once, as far as the search looks."""
    asked: list[date] = []

    async def never(day: date) -> bool:
        asked.append(day)
        return False

    window = await workday_window(
        interval_of("workdays"), local(SUNDAY, "08:00"), ZoneInfo(JERUSALEM), never
    )

    assert window is None
    assert asked == [
        SUNDAY + timedelta(days=ahead) for ahead in range(1, WINDOW_SEARCH_DAYS + 1)
    ]


async def test_search_ends_where_the_question_fails() -> None:
    """Whatever the question raises is the search's: no window is made up for a day
    that was not answered."""

    async def fails(_day: date) -> bool:
        raise HomeAssistantError("The sensor is away")

    with pytest.raises(HomeAssistantError):
        await workday_window(
            interval_of("workdays"),
            local(SUNDAY, "06:00"),
            ZoneInfo(JERUSALEM),
            fails,
        )


# --- Against the real Workday -------------------------------------------------------


ISRAEL_WEEK: Any = {
    "country": "IL",
    "workdays": ["sun", "mon", "tue", "wed", "thu"],
    "excludes": ["fri", "sat", "holiday"],
    "days_offset": 0,
    "add_holidays": [],
    "remove_holidays": [],
}


def test_holidays_is_the_version_the_workday_integration_requires() -> None:
    """The tests against the real Workday run on the holiday calendars that Home
    Assistant ships it with: the development dependency follows the integration when
    Home Assistant is upgraded."""
    manifest = json_loads_object(
        Path(workday.__file__).with_name("manifest.json").read_text("utf-8")
    )

    assert manifest["requirements"] == [f"holidays=={holidays.__version__}"]


REAL_SENSOR = "binary_sensor.workday_sensor"
"""The sensor of the real Workday integration, named after its entry."""


async def real_workday_entry(
    hass: HomeAssistant, days_offset: int = 0
) -> MockConfigEntry:
    """Set up the Workday integration of Home Assistant for Israel, its sensor looking
    `days_offset` days ahead, and return its config entry."""
    entry = MockConfigEntry(
        domain="workday",
        title="Workday Sensor",
        version=1,
        minor_version=2,
        options={**ISRAEL_WEEK, "days_offset": days_offset},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def real_workday(hass: HomeAssistant, days_offset: int = 0) -> str:
    """Set up the Workday integration for Israel and return the entity id of its
    sensor."""
    await real_workday_entry(hass, days_offset)
    return REAL_SENSOR


async def test_real_workday_integration_answers_for_israel(hass: HomeAssistant) -> None:
    """The answer the timer reads is what the integration gives: its sensor and its
    `check_date` service, set up for Israel, say that Friday is no working day, that
    Sunday is one, and that a holiday in the middle of the week is not."""
    sensor = await real_workday(hass)
    holiday = next(
        day
        for day in sorted(holidays.country_holidays("IL", years=2026))
        if day.weekday() in (6, 0, 1, 2, 3)
    )

    async def check(day: date) -> Any:
        return await hass.services.async_call(
            "workday",
            "check_date",
            {"entity_id": sensor, "check_date": day},
            blocking=True,
            return_response=True,
        )

    assert await check(date(2026, 1, 9)) == {sensor: {"workday": False}}
    assert await check(date(2026, 1, 11)) == {sensor: {"workday": True}}
    assert await check(holiday) == {sensor: {"workday": False}}


async def test_timer_follows_the_real_workday_integration(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The boiler asks the integration itself: the first holiday in the middle of the
    week is a day off, so its morning is the day off's, not the working one's."""
    sensor = await real_workday(hass)
    holiday = next(
        day
        for day in sorted(holidays.country_holidays("IL", years=2026))
        if day > SUNDAY and day.weekday() in (6, 0, 1, 2, 3)
    )
    await hass.config.async_set_time_zone("Asia/Jerusalem")
    freezer.move_to(local(holiday - timedelta(days=1), "20:00"))
    entry = await setup_target(workday_sensor=sensor)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await add_interval(hass, entry, days="non_workdays", start="08:00", end="09:00")

    await advance_to(hass, freezer, local(holiday, "08:00"))

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(holiday, "09:00")
    assert state_of(hass, TARGET_ID) == "on"


async def test_real_workday_sensor_that_is_renamed_is_followed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The integration itself takes its sensor to the new entity id when the user
    renames it, which is what `FakeWorkday.rename` models: the timer follows, and asks
    the sensor under its new name without a word in the log."""
    sensor = await real_workday(hass)
    await open_sunday(hass, freezer)
    entry = await setup_target(workday_sensor=sensor)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")

    er.async_get(hass).async_update_entity(sensor, new_entity_id=RENAMED_SENSOR)
    await hass.async_block_till_done()

    assert entry.options[CONF_WORKDAY_SENSOR] == RENAMED_SENSOR
    assert hass.states.get(sensor) is None
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    await advance_to(hass, freezer, local(MONDAY, "06:30"))
    assert fake_target.calls == [TURN_ON, TURN_OFF, TURN_ON]
    assert timerify_warnings(caplog) == []


async def test_day_offset_of_the_sensor_shifts_the_days_as_it_answers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A sensor with a day offset of one answers for the day after the one it is asked
    about, and the schedule takes the answer as it comes: the Thursday morning is not a
    working one, since Friday is not, and the Saturday morning is, since Sunday is. A
    timer is meant to be given a sensor with an offset of zero."""
    sensor = await real_workday(hass, days_offset=1)
    await hass.config.async_set_time_zone(JERUSALEM)
    thursday = SUNDAY + timedelta(days=4)
    freezer.move_to(local(thursday, "05:00"))
    entry = await setup_target(workday_sensor=sensor)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")

    await advance_to(hass, freezer, local(thursday, "06:30"))

    assert fake_target.calls == []
    await advance_to(hass, freezer, local(SATURDAY, "06:30"))
    assert fake_target.calls == [TURN_ON]


async def test_real_workday_that_is_unloaded_cannot_answer_and_the_window_waits_for_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A Workday integration that is being reloaded leaves its sensor unavailable, and a
    question about it fails with the error that `FakeWorkday` models, which is why the
    timer takes it for a sensor that is away: the window of the morning waits, and when
    the integration is back the boiler runs for the rest of it."""
    workday_entry = await real_workday_entry(hass)
    await open_sunday(hass, freezer)
    await hass.config_entries.async_unload(workday_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError) as raised:
        await hass.services.async_call(
            "workday",
            "check_date",
            {"entity_id": REAL_SENSOR, "check_date": SUNDAY},
            blocking=True,
            return_response=True,
        )
    assert str(raised.value) == NO_ENTITY_MATCHED
    entry = await setup_target(workday_sensor=REAL_SENSOR)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    (warning,) = timerify_warnings(caplog)
    assert warning.startswith(NOT_ASKED)
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == []

    freezer.move_to(local(SUNDAY, "06:40"))
    await hass.config_entries.async_setup(workday_entry.entry_id)
    await hass.async_block_till_done()

    assert fake_target.calls == [TURN_ON]
    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")
