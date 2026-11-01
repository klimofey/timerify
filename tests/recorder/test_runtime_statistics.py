"""What Home Assistant's long-term statistics make of the Runtime sensor."""

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.recorder import Recorder
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
    do_adhoc_statistics,
    statistics_during_period,
)

from ..conftest import FakeTarget, SetupTarget
from ..helpers import (
    RUNTIME,
    SUNDAY,
    advance,
    advance_to,
    local,
    open_sunday,
)

MONDAY = SUNDAY + timedelta(days=1)


async def test_a_run_across_midnight_is_split_between_the_days(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The boiler is on from twenty to twelve at night to twenty past, 40 minutes:
    the statistics give each of the two days 20 minutes, to within the second the
    sensor's last tick of the old day came before midnight. The clock moves as a real
    one does, 59 seconds to the tick and one to the next minute, so that a sensor that
    published at the turn of the minute would put a whole minute on the wrong day."""
    await open_sunday(hass, freezer)
    await setup_target(mode="loose", runtime=True)
    await advance_to(hass, freezer, local(SUNDAY, "23:40"))
    await fake_target.set_state("on")

    for _ in range(40):
        await advance(hass, freezer, seconds=59)
        await advance(hass, freezer, seconds=1)
    await fake_target.set_state("off")
    for _ in range(3):
        await advance(hass, freezer, seconds=59)
        await advance(hass, freezer, seconds=1)
    await advance_to(hass, freezer, local(MONDAY, "01:00"))
    await async_wait_recording_done(hass)

    # The statistics begin with the sensor's first figure, as they do where the
    # recorder has been running since the sensor was made; then the hours of the run.
    do_adhoc_statistics(hass, start=local(SUNDAY, "06:00"))
    period = local(SUNDAY, "23:35")
    while period < local(MONDAY, "01:00"):
        do_adhoc_statistics(hass, start=period)
        period += timedelta(minutes=5)
    await async_wait_recording_done(hass)
    days = (
        await recorder_mock.async_add_executor_job(
            statistics_during_period,
            hass,
            local(SUNDAY, "00:00"),
            None,
            {RUNTIME},
            "day",
        )
    )[RUNTIME]

    # A day's `sum` is the total at its end, so the day's own minutes are the step.
    sums = [day["sum"] for day in days]
    assert len(sums) == 2
    assert sums[0] == pytest.approx(20.0, abs=0.02)
    assert sums[1] - sums[0] == pytest.approx(20.0, abs=0.02)
