"""The runtime counter adds up the time a target was on, and keeps its total in a file
of its own."""

import math
from datetime import datetime, timedelta
from typing import Any

import pytest
from homeassistant.core import HomeAssistant

from custom_components.timerify.runtime import (
    RUNTIME_STORAGE_VERSION,
    RuntimeCounter,
    RuntimeStore,
    runtime_storage_key,
)

from .helpers import START, timerify_warnings

ENTRY_ID = "01KBOILER"


def after(seconds: float) -> datetime:
    """The moment `seconds` after `START`."""
    return START + timedelta(seconds=seconds)


def test_a_run_counts_its_seconds() -> None:
    """The boiler is on for two minutes: the open run counts up to whenever it is
    read, and the closed one stops counting at the moment it ended."""
    counter = RuntimeCounter()

    counter.observe(START, True)
    assert counter.total(after(90)) == 90.0

    counter.observe(after(120), False)
    assert counter.total(after(600)) == 120.0


def test_runs_add_up() -> None:
    """Two runs with a pause between them count together, not the pause."""
    counter = RuntimeCounter()

    counter.observe(START, True)
    counter.observe(after(60), False)
    counter.observe(after(300), True)
    counter.observe(after(330), False)

    assert counter.total(after(900)) == 90.0


def test_repeated_reports_change_nothing() -> None:
    """A target that says it is on again, or off again, has not started or stopped
    anything: the run began with the first report and ended with the first one that
    followed."""
    counter = RuntimeCounter()

    counter.observe(START, False)
    counter.observe(after(30), True)
    counter.observe(after(60), True)
    counter.observe(after(90), False)
    counter.observe(after(120), False)

    assert counter.total(after(600)) == 60.0


def test_a_new_counter_has_counted_nothing() -> None:
    """A timer that has never seen its target on shows no minutes at all."""
    counter = RuntimeCounter()

    assert counter.total(START) == 0.0
    assert counter.minutes(START) == 0.0


def test_a_counter_starts_from_what_was_counted() -> None:
    """After a restart the counter is given what the file held, and adds to it."""
    counter = RuntimeCounter(300.0)

    assert counter.total(after(10_000)) == 300.0

    counter.observe(START, True)
    assert counter.total(after(60)) == 360.0


def test_minutes_are_rounded_to_two_decimals() -> None:
    """A run of 61 seconds is 1.02 minutes, and a minute and a half is 1.5."""
    counter = RuntimeCounter()
    counter.observe(START, True)

    assert counter.minutes(after(61)) == 1.02
    assert counter.minutes(after(90)) == 1.5


def test_minutes_never_go_below_what_was_shown() -> None:
    """Once 5 minutes were published, the counter never reports fewer, however it came
    to count less; it reports more as soon as it has counted more."""
    counter = RuntimeCounter(240.0)
    counter.mark_shown(5.0)

    assert counter.shown == 5.0
    assert counter.minutes(START) == 5.0

    counter.observe(START, True)
    assert counter.minutes(after(30)) == 5.0
    assert counter.minutes(after(120)) == 6.0


def test_clock_going_back_adds_nothing() -> None:
    """The clock is set back while the target is on (a time server corrects it): a run
    that appears to end before it began counts for nothing, and a reading from before
    the run's beginning is what the closed runs came to."""
    counter = RuntimeCounter(300.0)

    counter.observe(after(60), True)
    assert counter.total(START) == 300.0

    counter.observe(START, False)
    assert counter.total(after(600)) == 300.0


async def test_store_round_trip(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """What the counter saved is in its file at once, and the next start reads it."""
    await RuntimeStore(hass, ENTRY_ID).async_save(125.5)

    stored = hass_storage[runtime_storage_key(ENTRY_ID)]
    assert stored["data"] == {"seconds": 125.5}
    assert stored["version"] == RUNTIME_STORAGE_VERSION == 1
    assert await RuntimeStore(hass, ENTRY_ID).async_load() == 125.5


async def test_store_without_a_file_is_zero(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A timer that never counted has no file, and starts from zero."""
    assert await RuntimeStore(hass, ENTRY_ID).async_load() == 0.0


async def test_store_reads_whole_seconds(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A file edited by hand to hold whole seconds is read as seconds."""
    key = runtime_storage_key(ENTRY_ID)
    hass_storage[key] = {
        "version": RUNTIME_STORAGE_VERSION,
        "minor_version": 1,
        "key": key,
        "data": {"seconds": 300},
    }

    seconds = await RuntimeStore(hass, ENTRY_ID).async_load()

    assert seconds == 300.0
    assert isinstance(seconds, float)


@pytest.mark.parametrize(
    "stored",
    [
        pytest.param({"seconds": -1}, id="negative"),
        pytest.param({"seconds": "x"}, id="text"),
        pytest.param({"seconds": True}, id="boolean"),
        pytest.param({"seconds": math.nan}, id="not a number"),
        pytest.param({"seconds": math.inf}, id="infinite"),
        pytest.param({}, id="empty"),
        pytest.param([300], id="a list"),
    ],
)
async def test_store_refuses_a_bad_file(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    stored: object,
) -> None:
    """A file that no counter wrote is not trusted: the timer starts from zero and the
    log names the file; the first thing the counter saves after that replaces it."""
    key = runtime_storage_key(ENTRY_ID)
    hass_storage[key] = {
        "version": RUNTIME_STORAGE_VERSION,
        "minor_version": 1,
        "key": key,
        "data": stored,
    }
    store = RuntimeStore(hass, ENTRY_ID)

    assert await store.async_load() == 0.0

    (warning,) = timerify_warnings(caplog)
    assert key in warning

    await store.async_save(60.0)
    assert await RuntimeStore(hass, ENTRY_ID).async_load() == 60.0
    assert len(timerify_warnings(caplog)) == 1


async def test_removing_the_store_deletes_the_file(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Deleting the timer deletes what it counted: a timer added again starts anew."""
    store = RuntimeStore(hass, ENTRY_ID)
    await store.async_save(125.5)

    await store.async_remove()

    assert runtime_storage_key(ENTRY_ID) not in hass_storage
    assert await RuntimeStore(hass, ENTRY_ID).async_load() == 0.0
