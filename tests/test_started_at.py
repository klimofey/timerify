"""The "Ends at" sensor says when the countdown it counts down to began.

The dashboard card fills its ring with the share of the countdown that is left, which
needs the length of the countdown, so the sensor carries `started_at` beside its end:
set when a countdown is set, kept while time is added or taken off, and gone when no
countdown runs. A countdown stored before the attribute existed has no beginning.
"""

from datetime import datetime, timedelta
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.translation import async_get_translations

from custom_components.timerify.const import DOMAIN
from custom_components.timerify.core import Snapshot, TimerCore, Window
from custom_components.timerify.store import TimerStore

from .conftest import FakeTarget, SetupTarget
from .helpers import (
    NEXT,
    NUMBER,
    SENSOR,
    START,
    SUNDAY,
    TARGET_ID,
    add_command,
    add_interval,
    advance,
    advance_to,
    at,
    call_service,
    command_json,
    edit_interval,
    iso,
    local,
    open_sunday,
    payload,
    restart,
    restart_after,
    saved,
    set_number,
    state_of,
    storage_key,
)


def began(hass: HomeAssistant) -> datetime | None:
    """When the countdown that the "Ends at" sensor shows began, by its attribute."""
    state = hass.states.get(SENSOR)
    assert state is not None
    started: datetime | None = state.attributes["started_at"]
    return started


def when(minutes: float) -> datetime:
    """The moment `minutes` after `START`, as a datetime."""
    return START + timedelta(minutes=minutes)


# --- Setting, adding and taking off ---------------------------------------------------


async def test_setting_the_timer_begins_its_countdown(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Moving the "Run for" slider to 45 starts a countdown of 45 minutes from now."""
    await setup_target()

    await set_number(hass, NUMBER, 45)

    assert state_of(hass, SENSOR) == at(45)
    assert began(hass) == START


async def test_adding_time_keeps_when_it_began(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Ten minutes into a countdown of 45, a quarter of an hour more makes it a
    countdown of 60 that began where the first did."""
    await setup_target()
    await set_number(hass, NUMBER, 45)
    await advance(hass, freezer, minutes=10)

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=15)

    assert state_of(hass, SENSOR) == at(60)
    assert began(hass) == START


async def test_taking_time_off_keeps_when_it_began(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Taking a quarter of an hour off a countdown that is ten minutes old shortens it
    without moving its beginning."""
    await setup_target()
    await set_number(hass, NUMBER, 45)
    await advance(hass, freezer, minutes=10)

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=-15)

    assert state_of(hass, SENSOR) == at(30)
    assert began(hass) == START


async def test_setting_again_begins_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Moving the slider to 30 ten minutes into a countdown starts a new one."""
    await setup_target()
    await set_number(hass, NUMBER, 45)
    await advance(hass, freezer, minutes=10)

    await set_number(hass, NUMBER, 30)

    assert state_of(hass, SENSOR) == at(40)
    assert began(hass) == when(10)


async def test_setting_the_same_end_again_begins_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """Ten minutes into a countdown of 30, moving the slider to 20 ends it at the same
    moment, but it is a new countdown: it began ten minutes in, which the sensor says
    although its state did not change."""
    await setup_target()
    await set_number(hass, NUMBER, 30)
    await advance(hass, freezer, minutes=10)

    await set_number(hass, NUMBER, 20)

    assert state_of(hass, SENSOR) == at(30)
    assert began(hass) == when(10)


async def test_adding_to_an_idle_timer_begins_it(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Adding twenty minutes to a timer that is not running starts a countdown."""
    await setup_target()

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=20)

    assert state_of(hass, SENSOR) == at(20)
    assert began(hass) == START


# --- Turning the target on ------------------------------------------------------------


async def test_strict_turn_on_by_someone_else_begins_the_default_duration(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """R4: somebody switches the boiler on three minutes in, and the countdown of its
    default duration begins then."""
    await setup_target()
    await advance(hass, freezer, minutes=3)

    await fake_target.set_state("on")

    assert state_of(hass, SENSOR) == at(48)
    assert began(hass) == when(3)


async def test_bare_run_of_an_off_target_begins_now(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """R9 in strict mode: running the boiler without saying for how long counts down
    its default duration from now."""
    await setup_target()

    await call_service(hass, "run", {"entity_id": NUMBER})

    assert state_of(hass, SENSOR) == at(45)
    assert began(hass) == START


async def test_bare_run_of_a_running_target_keeps_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A run without a duration changes nothing about the countdown of a boiler that is
    already running, so the countdown began where it did."""
    await setup_target()
    await set_number(hass, NUMBER, 45)
    await advance(hass, freezer, minutes=5)

    await call_service(hass, "run", {"entity_id": NUMBER})

    assert state_of(hass, SENSOR) == at(45)
    assert began(hass) == START


async def test_open_run_has_no_beginning(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """R9 in loose mode: the boiler runs without a countdown, so there is nothing
    that began."""
    await setup_target(mode="loose")

    await call_service(hass, "run", {"entity_id": NUMBER})

    assert state_of(hass, TARGET_ID) == "on"
    assert state_of(hass, SENSOR) == "unknown"
    assert began(hass) is None


# --- Ending the countdown -------------------------------------------------------------


async def test_stop_and_manual_off_clear_it(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """Stopping the timer, and switching the boiler off by hand during a countdown
    (R3), each leave no countdown and so no beginning."""
    await setup_target()
    await set_number(hass, NUMBER, 45)
    assert began(hass) == START

    await set_number(hass, NUMBER, 0)

    assert state_of(hass, SENSOR) == "unknown"
    assert began(hass) is None

    await set_number(hass, NUMBER, 30)
    assert began(hass) == START

    await fake_target.set_state("off")

    assert state_of(hass, SENSOR) == "unknown"
    assert began(hass) is None


async def test_expired_countdown_has_no_beginning(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """When the countdown runs out, the boiler goes off and nothing began."""
    await setup_target()
    await set_number(hass, NUMBER, 20)

    await advance(hass, freezer, minutes=20)

    assert state_of(hass, TARGET_ID) == "off"
    assert began(hass) is None


# --- Pending commands -----------------------------------------------------------------


async def test_pending_command_begins_at_its_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """P3: a command to turn on in ten minutes for thirty is the same as setting the
    timer to thirty then, so the countdown begins when the command is due."""
    await setup_target()
    await add_command(hass, NUMBER, action="on", delay=10, minutes=30)

    await advance(hass, freezer, minutes=9)

    assert began(hass) is None

    await advance(hass, freezer, minutes=1)

    assert state_of(hass, SENSOR) == at(40)
    assert began(hass) == when(10)


async def test_command_due_while_down_began_at_its_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A command that came due while Home Assistant was down began its countdown at
    its own time, not when Home Assistant noticed."""
    entry = await setup_target()
    await add_command(hass, NUMBER, action="on", delay=10, minutes=30)

    await restart_after(hass, freezer, entry, minutes=15)

    assert state_of(hass, SENSOR) == at(40)
    assert began(hass) == when(10)


async def test_command_that_keeps_the_end_still_shows_its_beginning(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A countdown of 30 that a command to run for 20 minutes, due at ten past, leaves
    ending at the same moment is a new countdown: it began at ten past, which the
    sensor says although its state did not change."""
    await setup_target()
    await set_number(hass, NUMBER, 30)
    await add_command(hass, NUMBER, action="on", delay=10, minutes=20)

    await advance(hass, freezer, minutes=10)

    assert state_of(hass, SENSOR) == at(30)
    assert began(hass) == when(10)
    assert state_of(hass, NEXT) == "unknown"


# --- Schedule windows -----------------------------------------------------------------


async def test_window_begins_at_its_start(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """The boiler's window opens at half past six, and its countdown begins then."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")
    assert began(hass) is None

    await advance_to(hass, freezer, local(SUNDAY, "06:30"))

    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")
    assert began(hass) == local(SUNDAY, "06:30")


async def test_window_that_extends_a_manual_countdown_begins_it_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """S1: half an hour set at six, and a window that opens at twenty past and ends
    later, make the countdown run to the end of the window, and it begins at the
    window's start: the ring is full again."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await set_number(hass, NUMBER, 30)
    assert began(hass) == local(SUNDAY, "06:00")
    await add_interval(hass, entry, start="06:20", end="07:15")

    await advance_to(hass, freezer, local(SUNDAY, "06:20"))

    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")
    assert began(hass) == local(SUNDAY, "06:20")


async def test_window_found_open_after_a_restart_began_at_its_start(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
) -> None:
    """A window that opened while Home Assistant was down began its countdown at its
    start."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    await add_interval(hass, entry, start="06:30", end="07:15")

    await restart_after(hass, freezer, entry, minutes=50)

    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:15")
    assert began(hass) == local(SUNDAY, "06:30")


@pytest.mark.parametrize(
    "edit",
    [{"end": "07:45"}, {"start": "06:40", "end": "07:45"}],
    ids=["end", "start-and-end"],
)
async def test_edited_window_keeps_its_beginning(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    edit: dict[str, str],
) -> None:
    """S2: extending the running window to a quarter to eight, moving its start too or
    not, moves the end of the countdown, and the countdown began where it did."""
    await open_sunday(hass, freezer)
    entry = await setup_target()
    interval = await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    await advance_to(hass, freezer, local(SUNDAY, "06:50"))

    await edit_interval(hass, entry, interval, **edit)

    assert state_of(hass, SENSOR) == iso(SUNDAY, "07:45")
    assert began(hass) == local(SUNDAY, "06:30")


# --- Restarts and the clock -----------------------------------------------------------


async def test_beginning_survives_a_restart(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A restart five minutes into a countdown of 45 leaves a countdown that still
    began at the start, because the file says so."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 45)
    await advance(hass, freezer, minutes=5)
    assert saved(hass_storage, entry) == payload(end=at(45), started_at=at(0))

    await restart(hass, entry)

    assert state_of(hass, SENSOR) == at(45)
    assert began(hass) == START


@pytest.mark.parametrize(
    ("taken_off", "ends"),
    [(20, 25), (50, -5)],
    ids=["end-after-the-old-beginning", "end-before-the-old-beginning"],
)
async def test_clock_set_back_never_puts_the_beginning_after_the_end(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    taken_off: int,
    ends: int,
) -> None:
    """The clock is corrected half an hour back, and minutes are then taken off a
    countdown that began at the old time: the countdown cannot have begun in the
    future, so it begins now, and the timer still loads after a restart. When so many
    minutes go that the end falls before the old beginning, the old beginning would
    make the file one that is refused."""
    entry = await setup_target()
    await set_number(hass, NUMBER, 45)
    freezer.move_to(when(-30))

    await call_service(hass, "add_time", {"entity_id": NUMBER}, minutes=-taken_off)

    assert state_of(hass, SENSOR) == at(ends)
    assert began(hass) == when(-30)

    await restart(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert state_of(hass, SENSOR) == at(ends)
    assert began(hass) == when(-30)


def test_realignment_inside_a_catch_up_is_as_of_its_own_instant() -> None:
    """The file of a timer carried by window b, written while the clock ran ahead,
    says its countdown began at 06:55, after window a ended at 06:40; it is found at
    seven, and a's end is folded first. Realigning the timer as of 06:40 keeps a
    beginning no later than 06:40, not the 06:55 that the clock of seven would let
    through: the timer never holds a beginning that the instant it is reasoned at had
    not reached."""
    carried = Snapshot(
        end=when(30),
        started_at=when(-5),
        scheduled_by="b",
        windows=(
            Window("a", when(-60), when(-20), started=True),
            Window("b", when(-40), when(30), started=True),
        ),
    )
    core = TimerCore("strict", timedelta(minutes=45), carried)

    core.tick(START)

    assert [window.interval_id for window in core.snapshot.windows] == ["b"]
    assert core.snapshot.end == when(30)
    assert core.snapshot.started_at == when(-20)


# --- What the file holds --------------------------------------------------------------


async def test_countdown_stored_by_0_4_0_has_no_beginning(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A countdown that version 0.4.0 stored runs on with no beginning, since nothing
    says when it began, and the file is written in the current version."""
    await fake_target.set_state("on")
    version_3 = {
        k: v
        for k, v in payload(end=at(30)).items()
        if k not in ("started_at", "limit_at")
    }

    entry = await setup_target(stored=version_3, stored_version=3)

    assert state_of(hass, NUMBER) == "30"
    assert began(hass) is None
    assert hass_storage[storage_key(entry)]["version"] == TimerStore.STORAGE_VERSION
    assert saved(hass_storage, entry) == payload(end=at(30))


async def test_version_4_store_is_migrated(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    hass_storage: dict[str, Any],
) -> None:
    """A countdown that version 4 stored, before a limit existed, runs on with its
    beginning and no limit, and the file is written in the current version."""
    await fake_target.set_state("on")
    version_4 = {
        k: v
        for k, v in payload(end=at(30), started_at=at(0)).items()
        if k != "limit_at"
    }

    entry = await setup_target(stored=version_4, stored_version=4)

    assert state_of(hass, NUMBER) == "30"
    assert began(hass) == when(0)
    assert hass_storage[storage_key(entry)]["version"] == TimerStore.STORAGE_VERSION
    assert saved(hass_storage, entry) == payload(end=at(30), started_at=at(0))


@pytest.mark.parametrize("started", [at(30), at(31)])
async def test_beginning_at_or_after_its_end_is_refused(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    started: str,
) -> None:
    """No countdown begins when it ends or after, so a file that says so is refused
    with a reason, as any other file that no timer could have written is."""
    entry = await setup_target(stored=payload(end=at(30), started_at=started))

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "stored_timer_invalid"
    assert entry.reason is not None
    assert "begins at or after its end" in entry.reason
    assert fake_target.calls == []


async def test_beginning_without_an_end_is_refused(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A file that says when a countdown began but holds no countdown is refused."""
    entry = await setup_target(stored=payload(started_at=at(0)))

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "stored_timer_invalid"
    assert entry.reason is not None
    assert "has a beginning but no end" in entry.reason
    assert fake_target.calls == []


NO_OFFSET = "2026-01-05T07:00:00"
"""A time as a file that no timer wrote might hold it: no offset to tell it by."""


@pytest.mark.parametrize(
    ("stored", "complaint"),
    [
        pytest.param(
            {**payload(end=at(30), started_at=at(0)), "end": NO_OFFSET},
            "the end of the countdown must be timezone-aware",
            id="end",
        ),
        pytest.param(
            {**payload(end=at(30), started_at=at(0)), "started_at": NO_OFFSET},
            "the beginning of the countdown must be timezone-aware",
            id="started_at",
        ),
        pytest.param(
            payload(limit_at=NO_OFFSET),
            "the limit of the run must be timezone-aware",
            id="limit_at",
        ),
        pytest.param(
            payload(commands=[command_json(NO_OFFSET, minutes=30)]),
            "the command's time must be timezone-aware",
            id="command",
        ),
    ],
)
async def test_time_without_an_offset_is_refused(
    hass: HomeAssistant,
    fake_target: FakeTarget,
    setup_target: SetupTarget,
    stored: dict[str, Any],
    complaint: str,
) -> None:
    """A time with no offset cannot be told from the clock's, so a file that holds one
    is refused with a reason, not read into a countdown that fails when it is
    compared."""
    entry = await setup_target(stored=stored)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason is not None
    assert complaint in entry.reason
    assert fake_target.calls == []


async def test_stored_times_are_read_in_utc(
    hass: HomeAssistant, fake_target: FakeTarget, setup_target: SetupTarget
) -> None:
    """A file that holds its times with another offset, as a hand-edited one may, is
    read like the windows of the same file: the same moments, in UTC, which is how the
    sensor says them."""
    await fake_target.set_state("on")

    await setup_target(
        stored=payload(
            end="2026-01-05T09:30:00+02:00", started_at="2026-01-05T09:00:00+02:00"
        )
    )

    started = began(hass)
    assert started is not None
    assert started.isoformat() == at(0)
    assert state_of(hass, SENSOR) == at(30)


# --- The name the more-info dialog shows ----------------------------------------------


async def test_attribute_has_a_name_in_the_more_info_dialog(
    hass: HomeAssistant,
) -> None:
    """The dialog names the attribute through the entity's translations, so English
    has a name for it (the other languages are held to English by
    test_translations.py)."""
    texts = await async_get_translations(hass, "en", "entity", [DOMAIN])

    key = f"component.{DOMAIN}.entity.sensor.ends_at.state_attributes.started_at.name"
    assert texts[key] == "Started at"
