# Timerify Phase 6 — Runtime Counter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A timer can count how long its target was on: an optional "Runtime" sensor, enabled with one checkbox when the timer is added or later in its settings. It counts every "on" of the target, not only Timerify's. It is a `total_increasing` duration in minutes that is written at most once a minute while the target is on, so Home Assistant's long-term statistics split a run across midnight correctly and give daily and weekly views without extra entities.

**Architecture:** The counter records and never decides. A pure `RuntimeCounter` (`runtime.py`, no Home Assistant imports, like `core.py`) keeps the seconds of closed runs and the start of the open one, judged by the existing `domains.actual_state`. A `RuntimeStore` keeps the total in its own file, `timerify.<entry_id>.runtime`, saved before every published value, so a restart or a crash can never make the value go down. A `RuntimeSensor` owns both. It subscribes to the target's state changes on its own, not through the controller or its lock, and publishes at a clock-aligned tick at second 59 of every minute. It ignores the controller's notifications. The timer, its file (`TimerStore`, version 4), the core and the card stay as they are.

**Tech Stack:** Python 3.14, Home Assistant 2026.10.4:
- `homeassistant.components.sensor`: `SensorDeviceClass.DURATION`, `SensorStateClass.TOTAL_INCREASING`, `suggested_display_precision`;
- `homeassistant.const.UnitOfTime.MINUTES`;
- `homeassistant.helpers.event`: `async_track_state_change_event` and `async_track_utc_time_change`;
- `homeassistant.helpers.storage.Store`;
- `homeassistant.helpers.entity_registry`;
- `homeassistant.helpers.selector.BooleanSelector`;
- `pytest-homeassistant-custom-component` 0.13.375 with `recorder_mock` for the statistics scenario.

**Spec:** `docs/superpowers/specs/2026-10-28-timerify-design.md`, phase 6 of §7: §5.8 (all of it), §3 lines 76-80 (no sub-minute writes; minute-valued entities at most once a minute), §5.7 (restarts), §6.1 ("`sensor` 'Runtime' when the counter is enabled"), §6.2 (the counter in the add-target flow and the options flow). Facts, verified in `.venv`: `docs/research/2026-11-01-runtime-counter.md`. Section references below (R§n) point into it.

**Starting point:** `main` after phase 5 (15165ed; pytest 1867, vitest 235, E2E 42), branch `phase-6-runtime-counter`. The code this plan relies on:
- `domains.actual_state(state) -> "on" | "off" | "unavailable"` (`domains.py:555`);
- `TimerifyEntity` (`entity.py:34`), whose `_handle_controller_update` writes the state by default;
- `timer_unique_id(entry_id, key)` (`const.py:123`);
- `TimerStore` with `STORAGE_VERSION = 4` and the key `timerify.<entry_id>` (`store.py:190-254`);
- `async_remove_entry` (`__init__.py:79`);
- `CONFIG_FLOW` / `OPTIONS_FLOW` (`config_flow.py:415-432`), whose first forms are `_target_schema` (entity and mode) and `_options_init_schema` (mode);
- the update listener that reloads the entry when its options change (`__init__.py:61`).

## Global Constraints

- Home Assistant `>= 2026.10.4` (`hacs.json`), Python `>= 3.14.2`, `pytest-homeassistant-custom-component==0.13.375`. No new runtime or dev dependency.
- Only public Home Assistant mechanisms, verified in `.venv`. Import names from the module that defines them (mypy strict). Schemas use `probatio`.
- The counter observes only. It never reads the timer's snapshot, the wish, pending commands or windows, and never writes to the target. "On" is `actual_state(...) == "on"`, nothing else.
- The runtime sensor's state is written at most once a minute and only when its value changed. The one exception is its first write when it is added. No write at a transition, at a controller notification, or at a command.
- The published value never goes down, unless the timer is deleted (and with it the file).
- The option `CONF_RUNTIME = "runtime"` is a `bool` in the entry's options; an entry without it (0.5.0 and earlier) has no counter. The config entry `VERSION` stays 1, and nothing is migrated.
- The entity's unique id is `timer_unique_id(entry_id, KEY_RUNTIME)` with `KEY_RUNTIME = "runtime"`, which gives `f"{entry_id}_runtime"` and, for `switch.boiler`, the entity id `sensor.boiler_runtime`.
- Every user-facing string is in `translations/en.json` (the source) and `translations/ru.json`. Cyrillic appears only in `translations/ru.json` and `sentences/ru/`.
- Tests are user scenarios with frozen time. Every clock move is `advance`, `advance_to` or `restart_after`. No sleeps, no polling, no backdoors. A phase 1–5 test is edited only where a task names it.
- The repository is English-only. Commits carry no AI attribution, and `--no-verify` is never used.
- Every task ends with `uv run pytest`, `uv run ruff check`, `uv run ruff format --check` and `uv run mypy` all passing.

## Review Focus

1. **A relay that flaps** (on and off five times within 30 s, plus a command and a controller notification in between). The sensor writes nothing before the next tick, then writes the final figure once. Test: Task 2, `test_a_flapping_target_is_written_once_a_minute`.
2. **A crash between two ticks.** The file is saved before each published value. On a start from what the file holds, the value is at least the last one shown. Test: Task 2, `test_stored_total_is_never_behind_what_was_shown`.
3. **The clock jumps backwards** (an NTP correction while the target is on). The value never goes down, and the time that was "lived twice" is not counted twice. Test: Task 2, `test_clock_going_back_never_lowers_the_value`.
4. **The counter is switched on in the settings while a countdown runs.** The reload keeps the countdown (R§4), the sensor appears with 0, and it counts from that moment, not back to the countdown's start. Test: Task 3, `test_enabling_the_counter_mid_countdown_keeps_the_countdown_and_counts_from_now`.
5. **The target is renamed during a run.** It keeps the same sensor, entity id and file, with no loss and no double count. Test: Task 2, `test_renaming_the_target_mid_run_keeps_the_counter`.

---

## File Structure

```
custom_components/timerify/
  runtime.py      new: RuntimeCounter, RuntimeStore, RUNTIME_STORAGE_VERSION (T1)
  const.py        + CONF_RUNTIME, KEY_RUNTIME, RUNTIME_TICK_SECOND (T2)
  sensor.py       + RuntimeSensor; async_setup_entry adds it or removes its registry entry (T2)
  __init__.py     async_remove_entry also deletes the runtime file (T2)
  icons.json      + entity.sensor.runtime (T2)
  translations/en.json, ru.json   + entity.sensor.runtime (T2); config.step.target / options.step.init field (T3)
  config_flow.py  the checkbox on the first form of the add flow and the options flow (T3)
tests/
  test_runtime_counter.py   new: the pure counter and its store (T1)
  test_runtime_sensor.py    new: the sensor's scenarios (T2)
  test_runtime_statistics.py new: midnight split with the real recorder (T2)
  test_config_flow.py       the checkbox (T3; edits `test_add_target_with_every_default_takes_three_clicks`)
  test_unique_ids.py        + a case with the counter (T2)
  conftest.py, helpers.py   setup_target(runtime=...), RUNTIME, runtime_storage_key (T2)
scripts/smoke/run.py        the first timer counts its runtime (T4)
README.md, RULINGS.md, docs/followups.md, CLAUDE.md, manifest.json, pyproject.toml, uv.lock (T4)
```

---

### Task 1: The counter and its file

**Files:**
- Create: `custom_components/timerify/runtime.py`, `tests/test_runtime_counter.py`

**Interfaces:**
- Consumes: nothing from this phase.
- Produces, in `runtime.py`:
  - `RUNTIME_STORAGE_VERSION: Final = 1`;
  - `runtime_storage_key(entry_id: str) -> str`, returning `f"timerify.{entry_id}.runtime"`;
  - `class RuntimeCounter` (pure, no Home Assistant import):
    - `__init__(self, seconds: float = 0.0)` — a counter with `seconds` already counted and no open run;
    - `observe(self, at: datetime, on: bool) -> None` — the target is on or not from `at`. On→on and off→off change nothing. Off→on opens a run at `at`. On→off closes it and adds `max(0, at − since)`;
    - `total(self, now: datetime) -> float` — seconds counted up to `now`. The open run adds `max(0, now − since)`;
    - `minutes(self, now: datetime) -> float` — `max(self.shown, round(self.total(now) / 60, 2))`;
    - `seconds_to_store(self, now: datetime) -> float` — `max(self.total(now), self.shown * 60)`: what every save writes, so that a counter rebuilt from the file never shows less than was shown (amended after the Task 1 review: a clock set back and a flush of `total` alone would make the value drop);
    - `shown: float` — the last value published, which `mark_shown(value: float) -> None` records.
  - `class RuntimeStore`:
    - `__init__(self, hass, entry_id)`;
    - `async_load(self) -> float` — the stored seconds, or 0.0 for no file; a file that fails validation logs a warning and gives 0.0 (a record, unlike `TimerStore`, which refuses the entry); a file of a newer major version raises `UnsupportedStorageVersionError` and is left alone;
    - `async_save(self, seconds: float) -> None` — immediate, not delayed;
    - `async_remove(self) -> None`.
  - The payload is `{"seconds": <float >= 0>}`.

- [ ] **Step 1: Write the failing tests** (`tests/test_runtime_counter.py`; datetimes are aware UTC around `START`)

```python
def test_a_run_counts_its_seconds()                 # observe(START, True); total(START+90s) == 90; observe(START+120s, False); total(START+600s) == 120
def test_repeated_reports_change_nothing()           # on, on (later), off, off: total == the one run
def test_a_counter_starts_from_what_was_counted()    # RuntimeCounter(300.0): total(any) == 300 with no run; with a run of 60 s → 360
def test_minutes_are_rounded_to_two_decimals()       # a run of 61 s → minutes == 1.02
def test_minutes_never_go_below_what_was_shown()     # mark_shown(5.0); a counter whose total is 4 min → minutes == 5.0
def test_clock_going_back_adds_nothing()             # open at START+60s, close at START (earlier) → total unchanged; total(now < since) == closed seconds
async def test_store_round_trip(hass, hass_storage)  # save 125.5 → hass_storage[runtime_storage_key(id)]["data"] == {"seconds": 125.5}, version 1; load → 125.5
async def test_store_without_a_file_is_zero(hass)
async def test_store_refuses_a_bad_file(hass, hass_storage, caplog)   # {"seconds": -1}, {"seconds": "x"}, {} → 0.0 and one warning naming the file
async def test_removing_the_store_deletes_the_file(hass, hass_storage)
```

- [ ] **Step 2: Run** `uv run pytest tests/test_runtime_counter.py -v`. Expected: FAIL, because `runtime` does not exist.
- [ ] **Step 3: Implement** `runtime.py`. Follow `store.py`'s `_TimerFile` pattern for the file: a `Store` subclass and strict validation. Use no Home Assistant import in `RuntimeCounter`.
- [ ] **Step 4: Run** the tests and then the gate. Expected: all pass.
- [ ] **Step 5: Commit**: `git commit -m "Add a runtime counter that keeps its total in a file of its own"`

---

### Task 2: The Runtime sensor

**Files:**
- Modify:
  - `custom_components/timerify/const.py` (beside `KEY_NEXT_COMMAND` and `CONF_WORKDAY_SENSOR`; update the `timer_unique_id` docstring);
  - `custom_components/timerify/sensor.py`;
  - `custom_components/timerify/__init__.py:79-87`;
  - `custom_components/timerify/icons.json`;
  - `translations/en.json` and `ru.json` (`entity.sensor.runtime.name`);
  - `tests/conftest.py` (`setup_target` gains `runtime: bool = False`, written into the options only when True);
  - `tests/helpers.py` (`RUNTIME = "sensor.boiler_runtime"`, `runtime_saved(hass_storage, entry) -> float`);
  - `tests/test_unique_ids.py` (one new test; the existing ones are unchanged).
- Create: `tests/test_runtime_sensor.py`, `tests/test_runtime_statistics.py`.

**Interfaces:**
- Consumes: `RuntimeCounter`, `RuntimeStore` and `runtime_storage_key` (Task 1); `actual_state` (`domains.py:555`); `TimerifyEntity`; `timer_unique_id`.
- Produces:
  - In `const.py`:
    - `CONF_RUNTIME: Final = "runtime"`, documented as "absent or False: no counter";
    - `KEY_RUNTIME: Final = "runtime"`;
    - `RUNTIME_TICK_SECOND: Final = 59`.
  - In `sensor.py`, `class RuntimeSensor(TimerifyEntity, SensorEntity)`, with `entity_description = SensorEntityDescription(key=KEY_RUNTIME, translation_key="runtime", device_class=SensorDeviceClass.DURATION, state_class=SensorStateClass.TOTAL_INCREASING, native_unit_of_measurement=UnitOfTime.MINUTES, suggested_display_precision=0)`.
  - `async_setup_entry` adds `RuntimeSensor` when `entry.options.get(CONF_RUNTIME)` is true. Otherwise it removes the registry entry `async_get_entity_id("sensor", DOMAIN, timer_unique_id(entry.entry_id, KEY_RUNTIME))` if there is one (R§4).
  - Strings: `entity.sensor.runtime.name` is "Runtime" in en; the ru text is in the phase's `global-constraints.md` (the repository is English-only outside `ru.json`). In `icons.json`, `entity.sensor.runtime.default` is `"mdi:timer-sand-complete"`.

Behaviour of `RuntimeSensor`:
- **`async_added_to_hass`.**
  - Build a `RuntimeCounter` from the seconds that `sensor.async_setup_entry` loaded (the load happens there, so that a file from a newer release fails the platform visibly instead of dropping the entity in silence).
  - Observe `actual_state(hass.states.get(target)) == "on"` at `dt_util.utcnow()`, where the target is `entry.options[CONF_TARGET]`.
  - Set `native_value = counter.minutes(now)`, then `mark_shown` it.
  - Subscribe to `async_track_state_change_event(target)`. Each event's `new_state` is observed at `event.time_fired`.
  - Subscribe to `async_track_utc_time_change(second=RUNTIME_TICK_SECOND)`.
  - Release both with `async_on_remove`.
- **The tick.** Compute `value = counter.minutes(now)`. If it equals `shown`, return. Otherwise `await store.async_save(counter.seconds_to_store(now))`, then set the value, write the state, and `mark_shown`.
- **`_handle_controller_update`** is a no-op.
- **The flush** saves `counter.seconds_to_store(utcnow())` (R§2). It runs from `async_will_remove_from_hass` and on `EVENT_HOMEASSISTANT_STOP` (`hass.bus.async_listen`, released by `async_on_remove`; while stopping, `Store.async_save` queues for the final write).
- **The sensor never turns unavailable because the target does.** Only an unload makes it unavailable.

- [ ] **Step 1: Write the failing tests.** They are user scenarios with `clock_at_start`, `fake_target` (`switch.boiler`), `setup_target(runtime=True)` and `record_writes(hass, RUNTIME)`. The sensor's state is read as `float(state_of(hass, RUNTIME))`.

```python
# tests/test_runtime_sensor.py
async def test_runtime_sensor_is_a_total_in_minutes()          # device_class duration, state_class total_increasing, unit "min", no last_reset attribute, display precision 0 in the registry options; starts at 0.0
async def test_a_countdown_is_counted_once_a_minute()         # Run for 45 → step advance(minutes=1) 46 times: values 1.0, 2.0, … 45.0 then still 45.0; record_writes == 45 values after the first, one per minute, none after the end
async def test_a_manual_run_outside_timerify_is_counted()     # loose: wall switch on (FakeTarget.set_state) for 20 minutes then off → 20.0 at the next tick; strict: the same 20 minutes counts 20.0 although R4 and R3 ran
async def test_a_flapping_target_is_written_once_a_minute()   # Review Focus 1: within 30 s five on/off pairs, a timerify.add_time and a controller refresh → no write before the tick; one write after it, with the exact seconds on, rounded
async def test_a_restart_while_on_continues_and_never_goes_down()   # 10 min on, restart(hass, entry) → value ≥ 10.0 at once, 11.0 one minute later
async def test_downtime_is_not_counted()                       # 10 min on, restart_after(minutes=30) with the target still on → 10.0 right after; 11.0 one minute later (spec §5.7 applied to a record)
async def test_stored_total_is_never_behind_what_was_shown()  # Review Focus 2: after every tick and after a clock set back and a reload, round(runtime_saved(...) / 60, 2) ≥ the shown value, and the entry started again from that file shows at least the last value
async def test_an_unavailable_target_pauses_the_count()       # 5 min on, unavailable 10 min, unknown 5 min, on 5 min → 10.0; the sensor stays available with its value throughout
async def test_clock_going_back_never_lowers_the_value()      # Review Focus 3: 10 min on, freezer.move_to(5 minutes earlier), 10 more minutes → never below 10.0; ends at 20.0 at most, never counting the repeated minutes twice
async def test_renaming_the_target_mid_run_keeps_the_counter()  # Review Focus 5: 10 min on, rename switch.boiler's entity id (the test_source_changes pattern) → same sensor entity id, value ≥ 10.0, continues counting the new id
async def test_two_timers_count_on_their_own()                 # switch.boiler and a climate (fake_climate): separate files and values; climate heat → cool is one run; unloading one leaves the other counting
async def test_disabling_the_counter_removes_its_entity()     # entry with runtime True, then options without it → no RUNTIME in states or registry, also after a restart; enabled again → same entity id and the old total
async def test_removing_the_timer_deletes_the_runtime_file()  # the test_removing_entry_deletes_stored_state pattern; both keys gone
async def test_a_timer_without_the_option_has_no_runtime_sensor()  # a 0.5.0-style entry: no RUNTIME, and no runtime file is written

# tests/test_runtime_statistics.py (recorder_mock, enable_statistics, the pattern of tests/test_recorder.py)
async def test_a_run_across_midnight_is_split_between_the_days()  # Jerusalem: target on 23:40 → 00:20 (step a minute at a time); compile with do_adhoc_statistics; statistics_during_period by day: 20.0 and 20.0 within 0.02

# tests/test_unique_ids.py
async def test_the_runtime_sensor_has_the_unique_id_of_the_counter()  # setup_target(runtime=True): RUNTIME → f"{entry.entry_id}_runtime", the other ids as in the existing test
```

- [ ] **Step 2: Run** `uv run pytest tests/test_runtime_sensor.py tests/test_runtime_statistics.py tests/test_unique_ids.py -v`. Expected: FAIL, because the sensor does not exist.
- [ ] **Step 3: Implement** the constants, `RuntimeSensor`, the setup and its registry removal, `async_remove_entry`'s second store, the icon and the strings. A test that renames the target follows `tests/test_source_changes.py:24-66`.
- [ ] **Step 4: Run** the tests and then the gate. Expected: all pass. The existing 1867 tests must stay green.
- [ ] **Step 5: Commit**: `git commit -m "Count how long a target was on, once a minute, in a Runtime sensor"`

---

### Task 3: The checkbox when a timer is added and in its settings

**Files:**
- Modify:
  - `custom_components/timerify/config_flow.py` (`_target_schema` at `:169`, `_options_init_schema` at `:399`);
  - `translations/en.json` and `ru.json` (`config.step.target.data.runtime` and `data_description.runtime`, `options.step.init.data.runtime` and `data_description.runtime`);
  - `tests/test_config_flow.py`. Edit `test_add_target_with_every_default_takes_three_clicks`: its expected options gain `CONF_RUNTIME: False`, and it still takes three clicks.

**Interfaces:**
- Consumes: `CONF_RUNTIME` (Task 2) and the sensor's setup (Task 2).
- Produces:
  - On the first form, entity and mode, then `probatio.Required(CONF_RUNTIME, default=False): selector.BooleanSelector()`. The same field goes on the options' `init` form after the mode, filled with the timer's current value.
  - Whatever the user chooses is stored in the options as a `bool`.
  - Strings:
    - en: "Count runtime". Description: "A Runtime sensor adds up how long the target is on, by Timerify or by hand, for daily and weekly statistics."
    - ru: the texts in the phase's `global-constraints.md`.

- [ ] **Step 1: Write the failing tests** (`tests/test_config_flow.py`)

```python
async def test_add_target_with_every_default_takes_three_clicks()          # edited: options == {target, mode "strict", default_duration, runtime: False}
async def test_counting_runtime_is_one_tick_on_the_first_form()            # {target, mode "loose", runtime: True} → entry created with runtime True and sensor.boiler_runtime at 0.0, still in two submits
async def test_settings_show_whether_the_runtime_is_counted()              # options flow on an entry with runtime True: suggested_value(result, CONF_RUNTIME) is True; on one without the key: False
async def test_enabling_the_counter_mid_countdown_keeps_the_countdown_and_counts_from_now()  # Review Focus 4: Run for 45, 10 minutes later enable it in the options → the countdown's end unchanged, RUNTIME 0.0, 1.0 a minute later
async def test_disabling_the_counter_in_the_settings_removes_the_sensor()   # options with runtime False → no RUNTIME; the countdown is kept
```

- [ ] **Step 2: Run** `uv run pytest tests/test_config_flow.py -v`. Expected: the new tests and the edited one FAIL.
- [ ] **Step 3: Implement** the field on both forms and the strings. Check in `.venv` how `SchemaOptionsFlowHandler` fills a form from the current options (`homeassistant/helpers/schema_config_entry_flow.py`). A boolean that is absent from the options must show False. Write no code that guesses this; verify it.
- [ ] **Step 4: Run** the tests and the gate, then `hassfest` (the translations change). Expected: all pass.
- [ ] **Step 5: Commit**: `git commit -m "Offer the runtime counter on the first form of a timer and in its settings"`

---

### Task 4: Documentation, the smoke test, version 0.6.0 and the full gate

**Files:**
- Modify:
  - `README.md` (the status block; the Entities table gains a "Runtime" row; a new section "Runtime counter"; the Setup steps; "What is not here yet"; "Verification");
  - `RULINGS.md` (a new section "Phase 6: runtime counter");
  - `docs/followups.md` (the entries on a `runtime` key for the card and `TimerInfo`'s unused fields: resolve them per ruling 7);
  - `CLAUDE.md` (status: phases 1 to 6);
  - `custom_components/timerify/manifest.json`, `pyproject.toml` and `uv.lock` (`version` `0.6.0`);
  - `scripts/smoke/run.py`.

- [ ] **Step 1: README.** The "Runtime counter" section says:
  - what is counted: every "on" of the target, by Timerify or by hand, judged the way Timerify judges on (climate in any mode but off, a media player neither off nor in standby, and so on);
  - that the value is in minutes, written at most once a minute, and that the display unit can be changed in the entity's settings;
  - that daily and weekly views come from Home Assistant's statistics, the history graph or the statistics card, with no extra entities;
  - that time while Home Assistant is not running, and time while the target is unavailable or unknown, are not counted;
  - that switching the counter off removes the sensor, its statistics stay in Developer tools > Statistics where they can be cleared, and switching it on again continues from the old total;
  - that deleting the timer deletes the total.
- [ ] **Step 2: RULINGS "Phase 6: runtime counter".** Write Plan rulings 1–11 below as Decision — why — cost if wrong, in the style of the earlier phases. Ruling 4 is the owner's decision (2026-11-01). Mention no agents, reviews or task numbers.
- [ ] **Step 3: followups.** Close the entries that planned a `runtime` key in `timerify/timer` and the card (ruling 7). Each one says it was decided, not fixed, and points to RULINGS. Keep every line reference correct.
- [ ] **Step 4: Smoke.** In `scenario_timer` (the first, `input_boolean.smoke_boiler`), the timer is added with `runtime: True`. After the 2-minute run has switched the boolean off, wait (polling the API for the state, as the harness does elsewhere, with a bound of 90 s) until `sensor.smoke_boiler_runtime` is at least 1.95. Then assert it is at most 2.1, and that its unit is `min` and its state class is `total_increasing`. Print one line, in the style of the others.
- [ ] **Step 5: Version** `0.6.0` in `manifest.json`, `pyproject.toml` and `uv.lock` (`uv lock`).
- [ ] **Step 6: Run the full gate on the final tree.**
  - Python: `uv sync && uv run pytest && uv run ruff check && uv run ruff format --check && uv run mypy`.
  - hassfest: `docker run --rm --platform linux/amd64 -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest`.
  - The card: `npm --prefix card ci && npm --prefix card run build:check && npm --prefix card run typecheck && npm --prefix card test`.
  - The E2E: `npm --prefix card run e2e`, after checking that the container's clock matches the host's (`date -u +%s` against `docker run --rm alpine date -u +%s`, within 2 s).
  - The smoke test: `uv run python -m scripts.smoke.run`, after the E2E, never at the same time.
  - Expected: all pass. Report the pytest, vitest and Playwright counts, and confirm `git status` is clean.
- [ ] **Step 7: Commit**: `git commit -m "Document the runtime counter and bump the version to 0.6.0"`

---

## Plan rulings

Each ruling is a decision, then why, then the cost if it is wrong. They apply where the spec leaves the choice open.

1. **The counter has a file of its own, `timerify.<entry_id>.runtime` (version 1, `{"seconds": float}`), and a pure class. Nothing is added to the timer's file, its `Snapshot` or the core.** Why: the counter records what the target did and decides nothing, so the timer stays the single source of truth for what runs, and `TimerStore`'s migration chain is untouched. A `RestoreSensor` is ruled out for the reason §5.7 gives for the timer: it is dumped every 15 minutes, so a crash would make a `total_increasing` value go down, and the recorder subtracts a dip of under 10 % from the sum (R§1). Cost if wrong: a second small file per timer.
2. **Time that was not observed is not counted.** This covers Home Assistant being down, and the target being unavailable or unknown. At start, and when the target becomes available, a run opens at that moment if the target is on. Why: §5.7 handles a restart "as if the change had just happened" and never reconstructs the downtime. A record holds only what was seen. It never overcounts, and it stays monotonic. Pending commands and the wish are promises, not runtime. Cost if wrong: an undercount bounded by the outage, which the README states.
3. **The sensor publishes at second 59 of every UTC minute: the exact total in minutes, rounded to 2 decimals, shown with display precision 0.** Why: the spec's point is attributing runtime to the right hour and day. A tick at second 59, even with its jitter of up to 0.5 s, lands before the minute's boundary, so a run across midnight splits within a second, with one write a minute. Whole minutes at second 0 would land after every boundary and could be off by up to 2 minutes (R§3). Cost if wrong: the raw state carries decimals, which the display hides.
4. **The "Count runtime" checkbox sits on the first form of a new timer, next to the entity and the mode (default off), and on the first form of its settings.** This is the owner's decision of 2026-11-01. Why: §6.2 asks both for the order "entity → mode → duration → runtime → Workday" and for "three clicks for the common case". A separate step would make every timer take four clicks. Within one form, the order is a matter of layout. Cost if wrong: the counter is chosen before the duration.
5. **Switching the counter off and on again keeps the stored total.** Why: no false reset in the statistics and no silent loss. Deleting the timer deletes the file. Cost if wrong: a user who wants a fresh start clears the statistics and deletes the timer.
6. **A counter switched off has its registry entry removed (not disabled).** Why: otherwise an `unavailable` ghost comes back at every start. A removed entry returns with the same entity id and customisations when the counter is switched on again, so history and statistics stay attached (R§4). The statistics are kept, because they are the user's. Cost if wrong: none known.
7. **Neither `timerify/timer` nor the card gets a `runtime` key in this phase.** Why: §6.3's card shows actions and the countdown, not runtime, and a key that nobody reads is dead weight. This settles the earlier plan to add one "with the sensor". Cost if wrong: a later card feature adds the key in three places (the Python `TimerInfo`, `hass.ts` and `watchedEntities`).
8. **There is no reset action.** Why: the spec does not ask for one, and Home Assistant's statistics tools exist. Writing 0 later is safe for statistics. Cost if wrong: a user who wants to reset deletes and re-adds the timer.
9. **The file is saved immediately (`async_save`) before every published value, and flushed on unload and when Home Assistant stops (a stop unloads no entry, so without the second the seconds since the last tick would be lost at every stop; amended after the Task 2 review).** Why: the stored value is always at least the shown one, so no restart or crash can make the value go down. Cost if wrong: one tiny write a minute while the target is on.
10. **The sensor never turns unavailable because its target does.** Why: it is a total, not a reading, and cards and automations read its value. Cost if wrong: none known.
11. **The sensor has one tick listener for its whole life, and subscribes to the target's state on its own.** It does not go through the controller, its lock or its notifications, and it time-stamps a change with `event.time_fired`. Why: the controller's handler can wait up to 30 s behind a service call (R§3), which would date runs late. A no-op tick is a comparison. Cost if wrong: a second state subscription per counted target.

---

## Appendix: pre-flight (shared files and interfaces; gate after each task)

| Pair | Shared | Conflict and resolution | Gate green after the later task |
|---|---|---|---|
| T1 → T2 | `RuntimeCounter`, `RuntimeStore`, `runtime_storage_key` | T2 uses them as T1 defines them; no signature changes | yes |
| T2 → T3 | `CONF_RUNTIME`; sensor setup reads `entry.options.get(CONF_RUNTIME)` | T3 only writes the option; T2's tests set it through `setup_target(runtime=True)` | yes |
| T2, T3 | `translations/en.json` + `ru.json` | T2 adds `entity.sensor.runtime`; T3 adds the two form fields; `test_translations.py` guards parity | yes |
| T2 | `tests/conftest.py` `setup_target`, `tests/helpers.py` | `runtime` defaults to False and adds no key, so every phase 1–5 test sees the options it saw | yes |
| T3 | the flow tests in `tests/test_config_flow.py` that compare the stored options exactly | the field is `Required` with a default, so every flow stores it: each such phase 1–5 test (`test_add_target_with_every_default_takes_three_clicks` and six more) gains `runtime: False` and nothing else | yes |
| T4 | `scripts/smoke/run.py` | the first scenario's flow input gains `runtime: True`; the other scenarios are unchanged | yes |
