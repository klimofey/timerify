# Timerify Phase 3 — Schedules with Workday Sensors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A target gets weekly schedule intervals ("weekdays 06:30–07:15", "working days", "non-working days" by a Workday sensor) that run its timer per S1–S5, each with an enable `switch`, added and edited one by one as config subentries, surviving restarts, DST and an unavailable Workday sensor.

**Architecture:** The pure core learns *windows* — concrete occurrences of an interval (`Window(interval_id, start, end, settings, started)`) handed to it by the controller — and folds a window's start (S1) and end into the same catch-up that already folds commands and the end, so one alarm at `next_wakeup` serves all four and a restart never flaps. Every fold ends with a realign (S2): while `scheduled_by` names an interval, the timer follows that interval's active window, or stops when there is none; every other write of the end goes through one setter that clears `scheduled_by` (S3). A window applies S1 once per occurrence: its persisted `started` mark is what S4 needs and survives edits and restarts. S1 is the only place that owes settings which may travel only with a turn-on, so the phase-2 `apply_if_on` keyword goes and a stored marker (D6) replaces it. The controller (HA side) computes each enabled interval's current-or-next window in the local time zone, asking `workday.check_date` for Workday-based intervals, and refreshes them at start-up, after a window ends, on a switch toggle, on a time-zone change and when the Workday sensor reports — always under the one lock, through one locked helper. Subentry add/edit/delete reach the entry only through update listeners in 2026.10.4, so one update listener reloads the entry; the enable flag lives in the timer's store, so a toggle never reloads. Every Timerify entity attaches to its device through `device_entry`, so a subentry's switch never moves a device. Each task is a vertical slice that leaves all four checks green.

**Tech Stack:** Python 3.14, Home Assistant 2026.10.4 (`ConfigSubentryFlow`, `async_get_supported_subentry_types`, `async_add_entities(..., config_subentry_id=...)`, `workday.check_date`, `async_track_state_report_event`, `EVENT_CORE_CONFIG_UPDATE`, `device_registry.async_get_or_create`, `probatio`, time/select/entity selectors, `section`), pytest-homeassistant-custom-component 0.13.375 (`freezer`, `hass_storage`, `async_fire_time_changed`), `holidays==0.106` (dev only, Task 6), ruff, mypy, uv.

**Spec:** `docs/superpowers/specs/2026-10-28-timerify-design.md` — phase 3 of §7: §5.5 (S1–S5), the schedule bullets of §5.4, the schedule bullet of §5.7, the `switch` of §6.1, the subentries and the Workday step of §6.2. Controller decisions: `.superpowers/phase-3-design-notes.md` (D1–D8). Pre-flight scan and its rulings: `.superpowers/sdd/2026-10-29-phase-3-schedules/preflight.md`. Voice, card, runtime counter and the config-flow menu are later plans.

**Starting point:** `main` after phase 2 merges (its final fix wave included). Shape relied on: `core.py` — pure `TimerCore` with owed settings (`_owe`, `_deliver_settings`, `_settings_for_running_target`, `apply_if_on` on `set_duration`/`run_open`/`_run_until`/`_want`), commands, `tick`, one `_catch_up` that folds due items in time order (`_next_due` returns `Command | "end" | None`, a command before the end on a tie) and wants one final wish, writes of `end` by `replace` in `_run_until`, `_end_timer`, `run_open` (loose), `_run_command` and `_follow_external_change`, `next_wakeup(snapshot)`, resend allowances; `controller.py` — one lock, `_command(sync callable)` raising the translated `timer_unloaded` HomeAssistantError when the timer unloaded while the call waited, `async_add_command(action, when: datetime | timedelta, ...)` computing `at` under the lock, one wake-up alarm (`_arm`), labelled call lists, `_execute` ending in `assert_never`, `_refresh_entities` notifying on `end`/`commands` changes, `_handle_started` arming the stored wake-up then observing, `_log_due_while_unavailable` (R10 lines "…; it is turned off when it is back" and "…; it is applied when it is back, if it is still relevant then"); `store.py` — `TimerStore` v2, strict reads, `_TimerFile._async_migrate_func`; `domains.py` — settings rows (`_Setting.supported`, `_OneOf` with `excluded`, `_Between` with attribute bounds), `validate_settings`, `_Capabilities`, the named predicate `judged_by_state`; `services.py` — `SETTINGS_SCHEMA` (numbers refuse booleans, `percentage`/`humidity` whole); `config_flow.py` — `SchemaConfigFlowHandler` with `options_flow_reloads = True`, `_after_mode(options)` (a `next_step` gets the options only, no hass); `entity.py` — `device_entry` of the target, else a `DeviceInfo` fallback device; `__init__.py` — `_follow_target` updates options and schedules a reload; tests — `provide_target`, `fake_target` (indirect `False`: on no device), `fake_climate`, `setup_target(stored=..., stored_version=...)`, helpers `advance`, `call_service`, `set_number`, `payload`, `saved`, `at`, `state_of`, `record_writes`, `timerify_warnings`, `timerify_info`; `tests/test_core.py` — `NOW`, `COOL24`, `core()`, `minutes()`, `cmd()`; `restart` still lives in `tests/test_restart.py`; `test_options_change_mode_keeps_running_timer` in `tests/test_config_flow.py`. If the shape differs, adapt names, not behaviour.

## Global Constraints

- Home Assistant `>= 2026.10.4` (`hacs.json`), Python `>= 3.14.2`, `pytest-homeassistant-custom-component==0.13.375`.
- Only public HA mechanisms; schemas with `probatio`, never `voluptuous`; import HA names from the module that defines them (mypy strict). No `RestoreEntity` for the enable flag: it lives in `TimerStore`.
- Every user-facing string in `translations/en.json` (source) and `translations/ru.json`; subentry strings under `config_subentries.interval` (`initiate_flow.user`, `initiate_flow.reconfigure`, `entry_type`, `step.user`, `step.reconfigure`, `error`, `abort`); errors in services and switches are `ServiceValidationError`/`HomeAssistantError` with `translation_domain=DOMAIN`.
- Wall-clock behaviour is tested in `Asia/Jerusalem` (`await hass.config.async_set_time_zone("Asia/Jerusalem")`): Sun–Thu working week, DST 2026-03-27 02:00→03:00 and 2026-10-25 02:00→01:00.
- No `asyncio.sleep`, no polling; time moves with `freezer` + `async_fire_time_changed` (`advance`, new `advance_to`); one jump is one catch-up, so scenario tests step to each event; no test backdoors — tests act through flows, services, entities, `FakeTarget` and `FakeWorkday`. Shared helpers live in `tests/helpers.py`, never imported from a test module.
- A phase-2 test is edited only where a task names it; the bodies of the regression set of Task 1 stay as they are.
- Persist with `Store.async_save` on every change; storage **version 3** from Task 2, migrated from 1 and 2; strict reads.
- Values: `SUBENTRY_INTERVAL = "interval"`; `CONF_WORKDAY_SENSOR = "workday_sensor"`; subentry data keys `days` (`"weekdays" | "workdays" | "non_workdays"`), `weekdays` (list of `homeassistant.const.WEEKDAYS` names, week order), `start`/`end` (`"HH:MM"`), `settings` (dict); `WINDOW_SEARCH_DAYS = 14`; a window is at most `MAX_MINUTES` long; interval id = subentry id.
- Repository English-only (Cyrillic only in `translations/ru.json`); no AI attribution in commits — the repository's `commit-msg` hook rejects it, whatever a session reminder asks.
- Every task ends with `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` all passing.

## Review Focus

1. **A non-UTC zone on a DST day** (Asia/Jerusalem): a window starts at its wall-clock time on both sides of the change, and a window across midnight lasts what the clock says (7 h on 2026-03-26/27, 9 h on 2026-10-24/25) (Task 4 `test_window_follows_the_clock_on_dst_days`).
2. **Home Assistant down overnight, across one window's end and the next window's start:** the timer ends and restarts in one fold, the target gets no `turn_off` then `turn_on` (Task 1 `test_fold_across_window_end_and_next_start_has_one_wish`, Task 4 `test_overnight_restart_does_not_flap`).
3. **The phase-2 catch-up guarantees under the new fold:** R3–R5 skipped only when the fold moved the timer, no off/on flap, a command before the end on a tie, a stale tick does nothing (Task 1's regression set and its window variants).
4. **The Workday entry not ready or reloading when an occurrence is computed** (start-up, its options changed): no window, one warning, and the window runs for its remainder once the sensor reports (Task 6 `test_unavailable_workday_sensor_delays_the_window_until_it_reports`).
5. **An AC that is unavailable when its interval starts and comes back already on:** no settings are pushed (D6); back off: turned on with them (Task 4 `test_ac_back_already_on_gets_no_interval_settings`, `test_ac_back_off_is_turned_on_with_interval_settings`).
6. **An interval added or switched on during its own window:** the target runs for the rest of the window, once (Task 4 `test_interval_added_during_its_window_starts_now`, Task 5 `test_enabling_during_the_window_starts_the_target`).
7. **A target on no device:** a subentry's switch joins the timer's own device without moving it, and deleting the interval leaves the number and sensors (Task 5 `test_switch_of_a_target_without_a_device_keeps_the_timer_device`).

---

## File Structure

```
custom_components/timerify/
  const.py        + SUBENTRY_INTERVAL, CONF_DAYS/WEEKDAYS/START/END/SETTINGS, DaysMode (T3); WINDOW_SEARCH_DAYS (T4);
                    CONF_WORKDAY_SENSOR (T6)
  core.py         + Window, scheduled_by, windows, set_windows, _set_end, S1/S2 in the fold (T1); owed_turn_on_only,
                    apply_if_on removed (T2); disabled_intervals, set_interval_enabled (T5)
  store.py        v3 + migration from 1 and 2; keys added by T2, T4, T5
  schedule.py     new: interval_title (T3); Interval, window_on, days_around, weekday_window (T4)
  domains.py      + SettingChoice, supported_settings() (T3)
  config_flow.py  + IntervalSubentryFlow, async_get_supported_subentry_types, options_flow_reloads=False (T3);
                    workday step in both flows, day modes (T6)
  __init__.py     update listener that reloads; _follow_target no longer reloads itself (T3); + Platform.SWITCH (T5)
  controller.py   window refresh, intervals from subentries, time-zone listener (T4); set_interval_enabled,
                    _raise_if_unloaded (T5); check_date, Workday tracking (T6)
  switch.py       new: IntervalSwitch (T5)
  entity.py       timer_device(), device_entry for every entity, unique_id override (T5)
  icons.json, translations/en.json, translations/ru.json
tests/
  conftest.py     + FakeWorkday / fake_workday (T6)
  helpers.py      + payload keys (T2, T4, T5), WEEK, add_interval(), edit_interval() (T3); JERUSALEM, local(), advance_to(),
                    restart() moved here, restart_after() (T4); set_switch() (T5)
  test_core.py test_restart.py test_config_flow.py test_interval_flow.py (new, T3) test_schedules.py (new, T4)
  test_interval_switch.py (new, T5) test_workday.py (new, T6) test_translations.py
pyproject.toml, uv.lock  + holidays==0.106 in the dev group (T6)
scripts/smoke/run.py, README.md, RULINGS.md, docs/followups.md, CLAUDE.md, manifest.json (T7)
```

---

### Task 1: Windows in the core — S1, S2, S3, S4 in one fold

**Files:**
- Modify: `custom_components/timerify/core.py`, `tests/test_core.py`

**Interfaces:**
- Produces in `core.py`:
  - `@dataclass(frozen=True) class Window: interval_id: str; start: datetime; end: datetime; settings: Settings = NO_SETTINGS; started: bool = False` — one occurrence of an interval, UTC-aware, `start < end <= start + MAX_MINUTES`; `started` means S1 was applied to it (or left the timer alone, or it was dropped as over) and it never applies again.
  - `Snapshot.scheduled_by: str | None = None` — the interval whose window end the timer carries, while nobody changed the timer since; always `None` while `end is None`. `Snapshot.windows: tuple[Window, ...] = ()` — sorted by `start` (the constructor sorts a restored snapshot, as it sorts commands), at most one per interval.
  - `TimerCore.set_windows(now, windows: Iterable[Window], *, configured: AbstractSet[str], keep: AbstractSet[str] = frozenset()) -> list[Effect]` — replaces the windows; an interval in `keep` keeps whatever window it has, started or not (its occurrence could not be computed); windows of intervals not in `configured` go. A fresh window active at `now` (`start <= now < end`) inherits `started=True` from an old started window of the same interval that is active at `now` (the same occurrence, perhaps edited). Merges only: returns `[Arm|Disarm]` (+`Changed()`); the next `tick` or `observe` folds.
  - `next_wakeup(snapshot)` = the earliest of `end`, the first command's `at`, the `start` of every window not started, the `end` of every window.
  - `tick(now)` and `observe(...)`: the catch-up folds window starts and ends with commands and the end, then realigns (below), and always realigns even when nothing is due; it still returns `[]` when nothing was due and the realign changed nothing.
  - In `tests/test_core.py`: `HEAT22 = freeze_settings({"hvac_mode": "heat", "temperature": 22.0})` beside `COOL24`; `window(id, start_min, end_min, **kw)`.
  - Private: `_set_end(end: datetime | None, *, by: str | None = None)` — the only writer of `end` (`_run_until`, `_end_timer`, loose `run_open`, `_run_command`, R3 in `_follow_external_change`, S1, realign); it sets `scheduled_by = by`, so every write but S1's and the realign's clears it (S3). `_runs_as_of(wish)` — the target runs as of a fold item: the fold's wish so far is `"on"`, or, with no wish yet, `last_actual == "on"` or a turn-on is in flight (`pending == "on"` and not unsent) — the same notion `_deliver_settings` uses, which calls it with no wish.

Fold (extends `_catch_up`): items at or before `now`, ordered by `(time, rank)` with ranks window end 0, window start 1, command 2, the timer's end 3 (P3: a command at the same instant as a window start wins; a window starting as the timer ends extends it without an off); the timer's end is an item only while it is still `<= now` after the items before it (phase-2 rule). Items:
- *Window end*: the window is removed. Nothing else; it does not count as moving the timer.
- *Window start* (S1): mark it `started`. If the window's end is `<= now` (the window is over before it was noticed) → nothing else, it does not count as moving the timer (R10/§5.7: nothing remains). If `end is not None and end >= window.end` → leave the timer alone (`scheduled_by` unchanged; not a move). Otherwise `_set_end(window.end, by=window.interval_id)`, wish `"on"`, and owe `window.settings` (plain `_owe` here; Task 2 adds the marker) only if `not _runs_as_of(wish)` (§5.4: a window that starts on a running target pushes nothing).
- *Realign* (S2), after the items, at `now`: if `scheduled_by` names X and X has a window with `start <= now < end` whose `end != snapshot.end` → `_set_end(that end, by=X)`, wish `"on"`; if X has no active window → stop (`_set_end(None)`, wish `"off"`). A realign that changes the timer counts as "moved the timer" for `observe`'s R3–R5 skip, like an executed command or the end reached.

- [ ] **Step 1: Write the failing tests** (`W = Window("x", NOW, NOW + 45 min)`; `window(...)` and `HEAT22` from the interfaces above)

```python
def test_window_start_runs_the_timer_to_its_end():          # strict "off", set_windows([W(start=NOW+5)]); tick(NOW+5)
    # == [Arm(NOW+45), TurnOn(), Changed()]; scheduled_by == "x"; windows[0].started
def test_window_start_leaves_a_later_end_alone():             # set_duration 60 → end NOW+60; window NOW..NOW+45 → end NOW+60,
    # scheduled_by None, no TurnOn
def test_window_start_extends_an_earlier_end():               # set_duration 10; window to NOW+45 → end NOW+45, scheduled_by "x"
def test_window_settings_go_with_the_turn_on():               # "off", window settings COOL24 → TurnOn(COOL24)
def test_window_settings_skip_a_running_target():             # "on" → no ApplySettings, owed empty
def test_window_after_a_command_in_the_same_fold_pushes_no_settings():  # command on at 06:20 (fold) then window at 06:30 →
    # owed == the command's settings
def test_window_start_while_a_turn_on_is_in_flight_keeps_the_commands_settings():  # set_duration(30, COOL24) on "off" →
    # TurnOn(COOL24) in flight; a window with HEAT22 starts → owed == COOL24, no ApplySettings
def test_window_that_ended_before_it_was_noticed_does_nothing():  # loose, target "on" open; restored window NOW-90..NOW-45
    # not started; observe(NOW, "on") → no TurnOff, end None, window started/removed, scheduled_by None
def test_realign_shortens_extends_and_stops():                # scheduled_by "x": set_windows with x NOW-60..NOW+30 → end NOW+30;
    # ..NOW+90 → NOW+90; x only tomorrow → TurnOff, end None, scheduled_by None
def test_realign_after_a_move_ahead_stops_then_starts_at_the_new_start()
@pytest.mark.parametrize("change", [set_duration, add_plus, add_minus, stop, run_open_strict, run_open_loose,
                                    due_on_command, due_off_command, manual_off, end_reached])
def test_every_other_change_ends_realignment(change):         # scheduled_by "x" before; after: scheduled_by None, and a
    # shorter set_windows + tick leaves the end where the change put it (S3)
def test_target_off_during_a_window_stays_off_until_the_next_window():  # R3 at NOW+10 → end None; set_windows with the same
    # occurrence (fresh, started=False) → inherits started; tick → nothing; next occurrence tomorrow → TurnOn at its start
def test_restored_started_window_does_not_start_again()       # Snapshot(windows=(W started,)) + observe("off") → no TurnOn
def test_manual_on_during_a_window_gets_the_default_duration():  # strict R4 → end NOW+10+45, not the window end (S5)
def test_overlapping_windows_follow_the_later_end():          # a 0..60, b 30..120 → end 120, scheduled_by "b"; a then edited → no change
def test_command_at_a_window_start_wins():                    # on-command for 10 min at the start instant → end start+10
def test_window_start_at_the_timer_end_extends_without_flap():  # end NOW+30 (set), window NOW+30..NOW+75; tick(NOW+30) →
    # no TurnOff, end NOW+75, scheduled_by "x"
def test_tie_order_at_one_instant():                          # at T: window a ends, window b starts, an off-command, the timer's
    # end → final wish off once, b started, end None, scheduled_by None
def test_fold_across_window_end_and_next_start_has_one_wish():  # Snapshot(end=Mon 07:15, scheduled_by "x", windows=(Mon
    # started,)), target "on", set_windows([Tue 06:30–07:15]); observe(Tue 06:45, "on") → no TurnOff, end Tue 07:15
def test_window_start_that_leaves_the_timer_alone_lets_a_manual_off_clear_it():  # end NOW+60 (set); window NOW+5..NOW+45
    # due; observe(NOW+5, "off", by_us=False) → R3: end None (not skipped)
def test_window_end_alone_lets_a_manual_on_start_the_default_duration():  # strict, idle; window end due;
    # observe("on", by_us=False) → R4: end now+45
def test_realign_that_stops_hides_the_startup_report():       # strict, restored end + scheduled_by "x", set_windows without x's
    # active window; observe("on") with last_actual None → TurnOff, end None (no R4 default duration)
def test_kept_window_is_not_realigned():                      # scheduled_by "x", set_windows([], keep={"x"}) → nothing changes
def test_window_of_an_unconfigured_interval_is_dropped_and_its_timer_stops()  # configured=set() while scheduled_by "x" → off
def test_tick_with_nothing_due_and_an_aligned_schedule_returns_nothing()  # scheduled_by "x", end == x's active window end → []
def test_next_wakeup_includes_window_starts_and_ends()
```

Regression set — these phase-2 tests pass with their bodies unedited: `tests/test_core.py` `test_stale_tick_is_ignored`, `test_tick_on_idle_timer_is_ignored`, `test_tick_with_nothing_due_is_stale`, `test_tick_on_idle_timer_without_commands_is_stale`, `test_observing_after_the_end_expires_the_timer_once`, `test_expiry_noticed_with_a_manual_on_does_not_start_a_new_timer`, `test_due_on_then_off_switches_nothing`, `test_due_off_then_on_switches_on_once`, `test_command_at_timer_end_extends_without_flap`, `test_command_at_the_end_keeps_the_settings_that_are_owed`, `test_restart_with_expired_timer_and_late_command_does_not_flap`, `test_command_due_with_a_manual_off_still_runs`, `test_dropped_command_leaves_a_manual_start_to_strict_mode`, `test_wakeup_is_earliest_of_end_and_commands`; `tests/test_commands.py` `test_command_at_the_end_of_the_timer_extends_it_without_a_flap`, `test_expired_timer_and_late_command_after_restart_keep_target_on`.

- [ ] **Step 2: Run `uv run pytest tests/test_core.py -v`** — Expected: new tests FAIL, the regression set passes.
- [ ] **Step 3: Implement** `Window`, the snapshot fields, `set_windows`, `_set_end` replacing every `replace(..., end=...)`, `_runs_as_of`, the ranked fold items, realign. No new `Effect` type.
- [ ] **Step 4: Run all checks** — Expected: all pass (the controller does not call `set_windows` yet).
- [ ] **Step 5: Commit** — `git commit -m "Fold schedule windows into the timer core"`

---

### Task 2: Settings that may only travel with a turn-on are stored (D6)

**Files:**
- Modify: `custom_components/timerify/core.py`, `custom_components/timerify/store.py`, `tests/test_core.py`, `tests/test_restart.py`, `tests/helpers.py`

**Interfaces:**
- Consumes: S1's owing of window settings and `_runs_as_of` (Task 1).
- Produces in `core.py`: `Snapshot.owed_turn_on_only: bool = False` — the owed settings may reach the target only inside a `TurnOn`. `_owe(settings, *, turn_on_only: bool = False)`; S1 calls it with `turn_on_only=True`. Removes `apply_if_on` from `set_duration`, `run_open`, `_run_until`, `_want` and `_settings_for_running_target` (S1 is its only intended caller, and it owes inside the fold); their docstrings lose the "see followups" caveat.
- Produces in `store.py`: `TimerStore.STORAGE_VERSION = 3`; payload key `"owed_turn_on_only": bool`; migration: v1 → `{**old, "owed_settings": {}, "commands": [], "owed_turn_on_only": False}`, v2 → `{**old, "owed_turn_on_only": False}`. Later tasks add keys to version 3 and to both migration branches.
- Produces in `tests/helpers.py`: `payload(..., owed_turn_on_only: bool = False)`.

Core rules:
1. S1 owes window settings with `turn_on_only=True`; non-empty settings owed by anything else (a command, `set_duration`, `run_open`) set the marker to False. Empty settings leave settings and marker alone.
2. `_deliver_settings` never returns `ApplySettings` while the marker is set.
3. A pending `"on"` that settles because the target is found on without our turn-on list having completed — `observe` with `_unsent` and `actual == "on"`, or `_want` finding `last_actual == "on"` — drops marked settings (`_clear_settings`, which also clears the marker). A `TurnOn` that went out still carries them, and `settings_applied` clears both.

- [ ] **Step 1: Write the failing tests** (windows of Task 1 carry `COOL24`; Task 1's `test_window_settings_go_with_the_turn_on` gains `assert snapshot.owed_turn_on_only`)

```python
def test_turn_on_only_settings_are_dropped_when_the_target_comes_back_on():  # "unavailable"; window starts → no TurnOn;
    # observe(NOW, "on", by_us=False) has no ApplySettings; owed_settings == NO_SETTINGS and owed_turn_on_only is False
def test_turn_on_only_settings_go_with_the_turn_on_when_the_target_comes_back_off():  # observe("off") → [TurnOn(COOL24)]
def test_manual_on_after_a_failed_turn_on_drops_turn_on_only_settings():  # "off", window → TurnOn(COOL24), call_failed,
    # observe("on", by_us=False) → no ApplySettings, owed empty
def test_a_command_with_settings_replaces_the_marker():       # unavailable, window owes COOL24 marked, then
    # set_duration(30 min, HEAT22) → marker False; observe("on") → [ApplySettings(HEAT22), ...]
def test_restored_turn_on_only_settings_skip_a_running_target():  # Snapshot(end=NOW+30, pending="on", owed_settings=COOL24,
    # owed_turn_on_only=True); observe(NOW, "on", by_us=False) == [Changed()]; owed empty
```

Deleted, each replaced by the named test: `test_apply_if_on_false_leaves_running_target_alone` → `test_window_settings_skip_a_running_target`; `test_apply_if_on_false_still_sends_settings_with_the_turn_on_it_causes` → `test_window_settings_go_with_the_turn_on`; `test_apply_if_on_false_keeps_settings_for_a_turn_on_that_waits` → `test_turn_on_only_settings_go_with_the_turn_on_when_the_target_comes_back_off`; `test_apply_if_on_false_sends_no_settings_while_a_turn_on_is_in_flight` → `test_window_start_while_a_turn_on_is_in_flight_keeps_the_commands_settings`.

`tests/test_restart.py`: `test_turn_on_only_settings_survive_a_restart_and_skip_a_running_ac` (stored `payload(end=at(30), pending="on", owed_settings={"hvac_mode": "cool"}, owed_turn_on_only=True)`, `fake_climate` in `"heat"` → `fake_climate.call_data == []`, `saved(...) == payload(end=at(30))`); `test_version_2_store_is_migrated` (stored v2 dict with owed settings → loads, marker False, saved as v3); update `test_version_1_store_is_migrated` and every `saved(...) ==` to the new `payload`.

- [ ] **Step 2: Run `uv run pytest tests/test_core.py tests/test_restart.py -v`** — Expected: new tests FAIL.
- [ ] **Step 3: Implement** the marker, its rules, the removal of `apply_if_on` and store v3.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Store whether owed settings may only travel with a turn-on"`

---

### Task 3: Intervals as config subentries; changes reload the entry

**Files:**
- Modify: `const.py`, `domains.py`, `config_flow.py`, `__init__.py`, `translations/en.json`, `translations/ru.json`, `tests/helpers.py`, `tests/test_config_flow.py`, `tests/test_source_changes.py`
- Create: `custom_components/timerify/schedule.py`, `tests/test_interval_flow.py`

**Interfaces:**
- Produces in `const.py`: `SUBENTRY_INTERVAL`, `CONF_DAYS`, `CONF_WEEKDAYS`, `CONF_START`, `CONF_END`, `CONF_SETTINGS` (values in Global Constraints); `type DaysMode = Literal["weekdays", "workdays", "non_workdays"]`.
- Produces in `schedule.py`: `def interval_title(data: Mapping[str, Any], labels: Mapping[str, str]) -> str` — `"{start}–{end}, {days}"` with an en dash; days: the label of `workdays`/`non_workdays`, or the weekday labels in week order where a cyclic run of three or more is `"First–Last"` and the rest are joined by `", "`; all seven is `"Mon–Sun"`. `labels` maps `"mon"`..`"sun"` (and from Task 6 the two modes) to their translated labels. (`Interval` joins in Task 4, where it is read.)
- Produces in `domains.py`: `@dataclass(frozen=True) class SettingChoice: name: str; options: tuple[str, ...] = (); low: float | None = None; high: float | None = None` and `def supported_settings(hass, entity_id) -> tuple[SettingChoice, ...]` — the row's settings the entity supports (`_Setting.supported`), options for `_OneOf` (excluded removed), bounds for `_Between` (attribute bounds resolved); `()` for an entity known to neither state nor registry.
- Produces in `config_flow.py`: `class IntervalSubentryFlow(ConfigSubentryFlow)` with `async_step_user` and `async_step_reconfigure` sharing one form builder; `TimerifyConfigFlowHandler.async_get_supported_subentry_types` → `{SUBENTRY_INTERVAL: IntervalSubentryFlow}`; `options_flow_reloads = False`.
- Produces in `__init__.py`: `entry.async_on_unload(entry.add_update_listener(_async_entry_updated))`, where `_async_entry_updated` calls `hass.config_entries.async_schedule_reload(entry.entry_id)`; `_follow_target.set_target` only updates the options (the listener reloads).
- Produces in `tests/helpers.py`: `WEEK = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")`; `async def add_interval(hass, entry, *, start: str, end: str, weekdays: Sequence[str] = WEEK, settings: dict[str, Any] | None = None) -> str` (drives `hass.config_entries.subentries.async_init((entry.entry_id, SUBENTRY_INTERVAL), context={"source": "user"})` and `async_configure`, blocks till done, returns the new subentry id); `async def edit_interval(hass, entry, subentry_id, **fields) -> SubentryFlowResult` (`context={"source": "reconfigure", "subentry_id": ...}`, prefilled with the current data, blocks till done).

Form (both steps, in this order): `weekdays` — `SelectSelector(options=WEEKDAYS, multiple=True, mode=LIST, translation_key="weekday")`, default all seven (edit: current); `start`, `end` — `TimeSelector()`; when `supported_settings` is non-empty, a collapsed `section` `settings` with one optional field per choice: options → `SelectSelector` (`translation_key="hvac_mode"` for `hvac_mode`), bounds → `NumberSelector(min, max, step=0.5 for temperature else 1, mode=BOX)`. The section's values go through `probatio.Schema(SETTINGS_SCHEMA)` (from `services.py`, so `percentage` and `humidity` are whole numbers as in commands) and then `validate_settings`. Stored data: `{"days": "weekdays", "weekdays": [...week order], "start": "HH:MM", "end": "HH:MM", "settings": {...}}`. Errors (`config_subentries.interval.error`): `no_weekdays` (empty list), `same_start_and_end`, `whole_minutes_only` (a time with seconds other than 0; the UI's `"HH:MM:00"` is accepted), `settings_not_supported` (the `ServiceValidationError` of `validate_settings`, field `base`). Title: `interval_title` with labels from `async_get_translations(hass, hass.config.language, "selector", [DOMAIN])` (`selector.weekday.options.*`: short labels Mon … Sun, and the Russian two-letter abbreviations in `ru.json`). Reconfigure: `async_update_and_abort(entry, subentry, data=..., title=...)` (never `async_update_reload_and_abort`, which raises with a listener), regenerating the title only while it equals the title generated from the old data (a title the user renamed stays). Abort `reconfigure_successful` comes from Home Assistant.

- [ ] **Step 1: Write the failing tests** (`tests/test_interval_flow.py`, `setup_target` + `fake_target`/`fake_climate`)

```python
async def test_adding_an_interval_stores_it_with_a_readable_title(hass, fake_target, setup_target):
    entry = await setup_target()
    subentry_id = await add_interval(hass, entry, start="06:30", end="07:15", weekdays=["sun", "mon", "tue", "wed", "thu"])
    subentry = entry.subentries[subentry_id]
    assert subentry.subentry_type == "interval" and subentry.title == "06:30–07:15, Sun–Thu"
    assert dict(subentry.data) == {"days": "weekdays", "weekdays": ["mon", "tue", "wed", "thu", "sun"],
                                   "start": "06:30", "end": "07:15", "settings": {}}
@pytest.mark.parametrize(("weekdays", "title"), [(WEEK, "22:00–06:00, Mon–Sun"), (["fri", "sat"], "22:00–06:00, Fri, Sat"),
                                                 (["mon", "wed"], "22:00–06:00, Mon, Wed")])
async def test_interval_titles(...)                     # an interval across midnight is accepted (end before start)
@pytest.mark.parametrize(("fields", "error"), [({"weekdays": []}, "no_weekdays"), ({"end": "06:30"}, "same_start_and_end"),
                                               ({"start": "06:30:15"}, "whole_minutes_only")])
async def test_invalid_intervals_are_refused(...)       # form shown again with errors == {...: error}
async def test_times_from_the_ui_are_stored_as_hours_and_minutes(...)  # start "06:30:00" → data["start"] == "06:30"
async def test_settings_section_offers_what_the_ac_can_do(hass, fake_climate, setup_target):
    # hvac_mode options == ["heat", "cool", "fan_only"]; temperature 16..30; fan_mode ["auto", "low", "high"]
async def test_a_plain_switch_gets_no_settings_section(...)
async def test_interval_settings_are_validated_and_stored(...)   # hvac_mode=cool, temperature=24 → data["settings"]
async def test_editing_an_interval_updates_data_and_title(...)   # edit end 07:30 → title "06:30–07:30, Mon–Sun", abort reason
async def test_editing_keeps_a_title_the_user_chose(...)         # async_update_subentry(title="Morning") then edit → "Morning"
async def test_adding_an_interval_keeps_a_running_countdown(hass, freezer, fake_target, setup_target):
    # set_number 30; advance 10; add_interval → entry reloaded (entry.runtime_data is a new controller), NUMBER == "20",
    # fake_target.calls == [TURN_ON]; advance 20 → [TURN_ON, TURN_OFF]
async def test_deleting_an_interval_keeps_a_running_countdown(...)  # hass.config_entries.async_remove_subentry(entry, id)
```

`tests/test_config_flow.py`: `test_options_change_mode_keeps_running_timer` still passes (now through the listener). `tests/test_source_changes.py`: `test_target_rename_keeps_timer` still passes with a single reload.

- [ ] **Step 2: Run `uv run pytest tests/test_interval_flow.py tests/test_config_flow.py tests/test_source_changes.py -v`** — Expected: new tests FAIL.
- [ ] **Step 3: Implement** `schedule.interval_title`, `supported_settings`, the subentry flow, the listener, the translations (`config_subentries.interval`: `initiate_flow.user` "Add schedule interval", `initiate_flow.reconfigure` "Edit schedule interval", `entry_type` "Schedule interval", step texts per field, the errors; `selector.weekday.options`).
- [ ] **Step 4: Run all checks** — Expected: all pass (intervals are stored and do nothing yet).
- [ ] **Step 5: Commit** — `git commit -m "Add schedule intervals as config subentries of a timer"`

---

### Task 4: Intervals run the timer (days of the week)

**Files:**
- Modify: `const.py`, `schedule.py`, `controller.py`, `store.py`, `tests/helpers.py`, `tests/test_restart.py`
- Create: `tests/test_schedules.py`

**Interfaces:**
- Consumes: `interval_title` data keys and `add_interval`/`edit_interval` (Task 3), `Window`, `set_windows`, `tick`, `next_wakeup` (Task 1).
- Produces in `const.py`: `WINDOW_SEARCH_DAYS = 14`.
- Produces in `schedule.py`:
  - `@dataclass(frozen=True) class Interval: id: str; days: DaysMode; weekdays: frozenset[str]; start: time; end: time; settings: Settings` and `@classmethod from_subentry(cls, subentry: ConfigSubentry) -> Interval`.
  - `def window_on(interval: Interval, day: date, zone: tzinfo) -> Window | None` — the occurrence that starts on `day`: start = `datetime.combine(day, interval.start, zone)` (`fold=0`), end on `day + 1` when `interval.end <= interval.start`; both to UTC; end capped at start + `MAX_MINUTES`; `None` when the end is not after the start (swallowed by a DST gap). A wall time in the spring-forward gap lands by the gap's length later (02:30 → 03:30); an ambiguous one takes its first occurrence.
  - `def days_around(now: datetime, zone: tzinfo) -> Iterator[date]` — the local date of `now` minus one day, then each day up to `WINDOW_SEARCH_DAYS` ahead.
  - `def weekday_window(interval: Interval, now: datetime, zone: tzinfo) -> Window | None` — the first `window_on` over `days_around` whose day's weekday is in `interval.weekdays` and whose end is after `now`.
- Produces in `controller.py`:
  - `self._intervals: dict[str, Interval]` from `entry.get_subentries_of_type(SUBENTRY_INTERVAL)`.
  - `async def _async_windows(self, now) -> tuple[list[Window], frozenset[str]]` — windows, and the interval ids whose occurrence is unknown (always empty in this task). Zone: `dt_util.get_default_time_zone()`.
  - `async def _async_refresh_windows_locked(self) -> bool` — the caller holds the lock: computes the windows, returns False without touching the core if the controller stopped meanwhile, else takes `now` after the computation and executes `set_windows(now, windows, configured=set(self._intervals), keep=unknown) + tick(now)` in one `_execute`, returning True. `async def _refresh_windows(self) -> None` — for event callbacks: takes the lock, returns quietly when unloaded, calls the locked helper. Nothing that holds the lock calls `_refresh_windows`.
  - `_handle_started`: computes the windows (returns if stopped meanwhile), `set_windows` (merge), arms `next_wakeup(self.snapshot)` read after the merge, then `observe`; the effects of `set_windows` and `observe` go through one `_execute`, so one fold covers stored and fresh windows. Then subscribes to `EVENT_CORE_CONFIG_UPDATE` (data with `time_zone` → `_refresh_windows()`), unsubscribed on unload.
  - `_handle_wakeup`: executes `tick` as today; when a window was removed by it, `await self._async_refresh_windows_locked()`.
  - R10 log at info, in `_log_due_while_unavailable`, for a window whose start set the timer in that tick while the target is unavailable: `"A schedule window of %s started while it is unavailable; it is turned on when it is back, if the window is still open then"`.
- Produces in `store.py`: keys `"scheduled_by": str | None`, `"windows": [{"interval", "start", "end", "settings", "started"}]` (ISO UTC); in both migration branches (`None`, `[]`).
- Produces in `tests/helpers.py`: `JERUSALEM = "Asia/Jerusalem"`; `def local(day: date, clock: str) -> datetime` (UTC of a Jerusalem wall time, `fold=0`); `async def advance_to(hass, freezer, moment: datetime)` (one jump is one catch-up: everything due by `moment` folds at `moment`); `restart(hass, entry)` moved from `test_restart.py` (its imports updated); `async def restart_after(hass, freezer, entry, **delta)` — unload, move the clock without firing, set up again; `payload(..., scheduled_by=None, windows=())`.

- [ ] **Step 1: Write the failing tests** (`tests/test_schedules.py`; each test sets `JERUSALEM`, moves to `local(SUNDAY, "06:00")` with `SUNDAY = date(2026, 1, 4)`, then `setup_target()` and `add_interval`; every expected event is reached with its own `advance_to`)

```python
async def test_interval_runs_the_boiler_through_its_window(hass, freezer, fake_target, setup_target):
    entry = await setup_target(); await add_interval(hass, entry, start="06:30", end="07:15")
    await advance_to(hass, freezer, local(SUNDAY, "06:30"))
    assert fake_target.calls == [TURN_ON] and state_of(hass, SENSOR) == local(SUNDAY, "07:15").isoformat()
    await advance_to(hass, freezer, local(SUNDAY, "07:15"))
    assert fake_target.calls == [TURN_ON, TURN_OFF]
async def test_interval_skips_days_it_does_not_name()           # weekdays=["mon"]: Sunday 06:30 nothing; Monday 06:30 on
async def test_plus_thirty_wins_and_edits_no_longer_touch_it()  # at 07:10 add_time +30 → ends 07:45; edit to 06:30–07:00 →
    # still 07:45; off at 07:45 (S3)
async def test_shortening_the_running_interval_moves_the_end()  # 06:00–08:00, at 07:00 edit end 07:30 → SENSOR 07:30; off 07:30 (S2)
async def test_extending_the_running_interval_moves_the_end()   # → 08:30
async def test_moving_the_running_interval_ahead_stops_and_starts_later()  # at 07:00 edit 07:30–08:30 → TURN_OFF now and
    # SENSOR unknown (no default-duration run after the reload); TURN_ON 07:30
async def test_deleting_the_running_interval_stops_the_boiler()
async def test_manual_off_keeps_the_boiler_off_until_the_next_window_across_a_restart()  # set_state("off") at 06:40; restart;
    # nothing until Monday 06:30 → TURN_ON (S4)
async def test_manual_on_during_a_window_runs_the_default_duration()  # after manual off, set_state("on") at 06:50 →
    # ends 07:35 (45 min), not 07:15 (S5)
async def test_restart_in_the_middle_of_a_window_keeps_its_end()       # restart at 06:50 → SENSOR 07:15, calls == [TURN_ON]
async def test_window_that_started_while_down_runs_for_the_rest()      # unload 06:00, restart_after → 06:50: TURN_ON, ends 07:15
async def test_overnight_restart_does_not_flap()                # target on at 07:10 Sunday, down until Monday 06:45 → no
    # TURN_OFF; ends Monday 07:15
async def test_window_across_midnight_belongs_to_its_start_day()  # weekdays=["fri"], 22:00–06:00: Fri 22:00 on, Sat 06:00 off,
    # Sat 22:00 nothing
async def test_window_follows_the_clock_on_dst_days()           # 06:30–07:15 on 2026-03-27 starts at local 06:30 (03:30 UTC);
    # 23:00–07:00 from 2026-03-26 ends local 07:00 (7 h); from 2026-10-24 ends local 07:00 (9 h)
async def test_time_zone_change_moves_the_next_window()         # hass.config.async_update(time_zone="Europe/Berlin") on Sunday
    # 05:00 → Monday's window starts at Berlin 06:30
async def test_overlapping_intervals_follow_the_later_end()     # 06:00–07:00 and 06:30–08:00 → ends 08:00; editing the
    # first changes nothing; editing the second to 06:30–07:30 → 07:30
async def test_interval_settings_turn_the_ac_on_cooling(hass, freezer, fake_climate, setup_target):
    # interval with {"hvac_mode": "cool", "temperature": 24}; at start call_data == [set_hvac_mode cool, set_temperature 24]
async def test_interval_starting_on_a_running_ac_pushes_no_settings()   # AC "heat" (R4) → no set_* calls; ends at window end
async def test_ac_back_already_on_gets_no_interval_settings()   # AC unavailable at start, back "heat" → call_data == []
async def test_ac_back_off_is_turned_on_with_interval_settings()  # back "off" → set_hvac_mode cool, set_temperature 24
async def test_interval_added_during_its_window_starts_now()    # at 06:45 add 06:30–07:15 → TURN_ON, ends 07:15
async def test_window_start_while_unavailable_is_logged(caplog)  # info line once; none when the timer already ends later
```

`tests/test_restart.py`: `test_schedule_state_is_stored` (after the window start `saved(...) == payload(end=..., scheduled_by=<id>, windows=[{... "started": True}])`; after its end `payload(windows=[{next occurrence, "started": False}])`, `scheduled_by` None); migrations carry the new keys.

- [ ] **Step 2: Run `uv run pytest tests/test_schedules.py tests/test_restart.py -v`** — Expected: new tests FAIL.
- [ ] **Step 3: Implement** `Interval`, the window functions, the controller refresh (locked helper, start-up, wake-up, time zone) and the store keys.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Run the timer on schedule intervals by day of the week"`

---

### Task 5: One enable switch per interval

**Files:**
- Modify: `core.py`, `store.py`, `controller.py`, `entity.py`, `__init__.py`, `icons.json`, `translations/en.json`, `translations/ru.json`, `tests/test_core.py`, `tests/helpers.py`
- Create: `custom_components/timerify/switch.py`, `tests/test_interval_switch.py`

**Interfaces:**
- Consumes: `set_windows`, `tick`, `_async_refresh_windows_locked`, `_refresh_windows`, `_async_windows` (Tasks 1, 4).
- Produces in `core.py`: `Snapshot.disabled_intervals: frozenset[str] = frozenset()`; `TimerCore.set_interval_enabled(now, interval_id: str, enabled: bool) -> list[Effect]` — records the flag; disabling removes the interval's window (the following `tick` realigns, S2); merges only, like `set_windows`. `set_windows` prunes `disabled_intervals` to `configured` and drops windows of disabled intervals (the core holds the invariant).
- Produces in `controller.py`: `def _raise_if_unloaded(self) -> None` factored out of `_command`; `async def async_set_interval_enabled(self, interval_id: str, enabled: bool) -> None` — under the lock: `_raise_if_unloaded()`, the core call, then `tick` (disable, one `_execute`) or `_async_refresh_windows_locked()` (enable), raising `timer_unloaded` when that returns False. `_async_windows` does not compute disabled intervals (no Workday call for them). `_refresh_entities` also notifies when `disabled_intervals` changed.
- Produces in `store.py`: key `"disabled_intervals": [sorted ids]` (migrations: `[]`).
- Produces in `entity.py`: `def timer_device(hass, entry) -> DeviceEntry` — the target's device, else the timer's own device got or created with `dr.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, entry.entry_id)}, name=controller.device_name)` and no subentry; every `TimerifyEntity` sets `device_entry = timer_device(...)` and the `DeviceInfo` fallback goes (a subentry entity with that `DeviceInfo` would move the device into its subentry). `TimerifyEntity.__init__(self, hass, entry, *, unique_id: str | None = None)` (default `f"{entry_id}_{key}"`).
- Produces in `switch.py`: `IntervalSwitch(TimerifyEntity, SwitchEntity)`, `PARALLEL_UPDATES = 0`, `SwitchEntityDescription(key="interval", translation_key="interval")`, `_attr_translation_placeholders = {"interval": subentry.title}`, unique id `f"{entry.entry_id}_interval_{subentry_id}"`, `is_on` = id not in `disabled_intervals`, writes its state only when its own flag changed; `async_setup_entry` calls `async_add_entities([...], config_subentry_id=subentry.subentry_id)` once per interval subentry. `PLATFORMS` gains `Platform.SWITCH`. Name `"Schedule {interval}"` (Russian in `ru.json` with the same blank); icon default `mdi:calendar-check`, state `off` `mdi:calendar-remove`.
- Produces in `tests/helpers.py`: `payload(..., disabled_intervals=())`; `async def set_switch(hass, entity_id, on: bool)`.

- [ ] **Step 1: Write the failing tests**

```python
async def test_each_interval_has_a_switch_on_the_target_device(...)  # "switch.boiler_schedule_06_30_07_15_mon_sun" is "on",
    # registry entry has config_subentry_id == the subentry id and device_id == the boiler's device
@pytest.mark.parametrize("fake_target", [False], indirect=True)
async def test_switch_of_a_target_without_a_device_keeps_the_timer_device(...)  # switch, number and sensors share one
    # device named Boiler; async_remove_subentry → number and sensors still registered on that device, no report of a
    # device moved to another subentry in caplog
async def test_switching_off_skips_the_window_without_a_reload(...)  # controller object unchanged; 06:30 → no call
async def test_switch_state_survives_a_restart(...)                  # saved disabled_intervals == [id]; after restart "off"
async def test_disabling_during_the_window_stops_the_target(...)     # at 07:00 → TURN_OFF (S2)
async def test_disabling_after_a_manual_change_leaves_the_timer(...)  # +30 at 07:10, disable → ends 07:45 (S3)
async def test_enabling_during_the_window_starts_the_target(...)     # disabled before 06:30, enabled 06:45 → TURN_ON, ends 07:15
async def test_deleting_an_interval_removes_its_switch(...)          # async_remove_subentry → no state, no registry entry
async def test_switch_is_written_only_when_toggled(...)              # record_writes(switch) over a window start and end == []; after a toggle == ["off"]
```

`tests/test_core.py`: `test_disabling_the_scheduling_interval_stops_the_timer`, `test_disabled_intervals_are_pruned_to_configured`, `test_windows_of_disabled_intervals_are_not_kept`. `tests/test_source_changes.py` passes unchanged (the device-move and no-device tests now go through `timer_device`).

- [ ] **Step 2: Run `uv run pytest tests/test_interval_switch.py tests/test_core.py tests/test_source_changes.py tests/test_entities.py -v`** — Expected: new tests FAIL.
- [ ] **Step 3: Implement** the flag, `timer_device`, the switch platform and the strings.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Add a switch that enables each schedule interval"`

---

### Task 6: Working days and non-working days by a Workday sensor

**Files:**
- Modify: `const.py`, `config_flow.py`, `schedule.py`, `controller.py`, `translations/en.json`, `translations/ru.json`, `pyproject.toml`, `uv.lock`, `tests/conftest.py`, `tests/helpers.py`, `tests/test_config_flow.py`, `tests/test_interval_flow.py`
- Create: `tests/test_workday.py`

**Interfaces:**
- Consumes: `Interval`, `days_around`, `window_on` (Task 4), `interval_title` (Task 3), `_async_windows`, `_refresh_windows`, `_async_refresh_windows_locked`, `keep` of `set_windows`.
- Config flow and options flow: a step `workday` with `probatio.Optional(CONF_WORKDAY_SENSOR)` — `EntitySelector(EntitySelectorConfig(domain="binary_sensor", integration="workday"))`. `_after_mode` returns `"duration"` (strict) or `"workday"` (loose); `duration`'s `next_step` is `"workday"`. The step's schema is a function of the handler that returns `None` — which skips the step — unless the entity registry holds a `binary_sensor` of platform `workday` or (options) the entry already has one (a `next_step` sees only the options, not hass). Options: removing it while an interval uses a Workday mode → error `workday_in_use`.
- Subentry form gains `days` first: `SelectSelector(options=["weekdays", "workdays", "non_workdays"], translation_key="interval_days")`, default `workdays` when the target has a sensor, else `weekdays`; `weekdays` is checked only in `weekdays` mode and stored as `[]` otherwise. Error `needs_workday_sensor` for a Workday mode on a target without one. Titles: `"06:30–07:15, Working days"`, `"08:00–09:00, Non-working days"`.
- Controller: `async def _async_is_workday(self, day: date) -> bool` — `hass.services.async_call("workday", "check_date", {"entity_id": sensor, "check_date": day}, blocking=True, return_response=True)` under `SERVICE_CALL_TIMEOUT`, answer `response[sensor]["workday"]`; any `HomeAssistantError` (including `ServiceNotFound` and "did not match any entities"), timeout or missing key raises a private `_WorkdayUnknown`. `_async_windows` takes the first `window_on` over `days_around` with end after now whose day matches (`True` for `workdays`, `False` for `non_workdays`), asking each day at most once per refresh; the first unknown answer makes every Workday interval of that refresh unknown (no further questions) and puts it in the returned `unknown` set. The answer is taken as the sensor gives it (its `days_offset` included). One warning per outage: `"Could not ask %s whether %s is a working day (%s); the schedule of %s waits until it reports"`, cleared by the next answer. In `_handle_started`, after the first fold: `async_track_state_change_event` and `async_track_state_report_event` on the sensor → `_refresh_windows()` (Workday writes its state every local midnight).
- Test fixtures (conftest): `@dataclass class FakeWorkday: hass; entity_id = "binary_sensor.workday_sensor"; workdays = {"sun","mon","tue","wed","thu"}; holidays: set[date]`; registered as a `binary_sensor` of platform `workday` (registry entry of a `MockConfigEntry(domain="workday")`), state `on`/`off`; `async def set_available(on: bool)`; a `workday.check_date` service (`SupportsResponse.ONLY`) that answers `{entity_id: {"workday": ...}}` and, while the sensor is unavailable, raises `HomeAssistantError("Service call requested response data but did not match any entities")` as Home Assistant does; `fail_next_call()`. Fixture `fake_workday`; `setup_target(..., workday_sensor: str | None = None)`.
- `tests/helpers.py`: `add_interval(..., days: DaysMode = "weekdays")`.
- `pyproject.toml` dev group: `holidays==0.106` (the version Home Assistant 2026.10.4's Workday requires).

- [ ] **Step 1: Write the failing tests** (`tests/test_workday.py`, Jerusalem time)

```python
async def test_owner_boiler_week(hass, freezer, fake_target, fake_workday, setup_target):
    entry = await setup_target(workday_sensor=fake_workday.entity_id)
    await add_interval(hass, entry, days="workdays", start="06:30", end="07:15")
    await add_interval(hass, entry, days="non_workdays", start="08:00", end="09:00")
    # Sunday 2026-01-04: on 06:30, off 07:15, nothing at 08:00; Friday 2026-01-09: nothing at 06:30, on 08:00, off 09:00
async def test_holiday_runs_the_non_working_day_interval()      # holidays={date(2026, 1, 6)}: Tuesday 06:30 nothing, 08:00 on
async def test_unavailable_workday_sensor_delays_the_window_until_it_reports(caplog)  # unavailable before Sunday's refill;
    # Monday 06:30 nothing, one warning; set_available(True) at 06:40 → TURN_ON, ends 07:15
async def test_failed_check_is_logged_once_per_outage(caplog)
async def test_failed_check_is_asked_again_when_the_sensor_reports_unchanged()  # fail_next_call at a refill, the sensor
    # rewrites "on" at midnight (state report) → the window is computed and runs
async def test_an_unknown_answer_leaves_a_running_window_alone()  # window started at 06:30; set_available(False) at 06:40
    # (its state change refreshes, the answer is unknown, keep) → no TURN_OFF before 07:15, SENSOR still 07:15, TURN_OFF at 07:15
async def test_real_workday_integration_answers_for_israel(hass):  # MockConfigEntry(domain="workday", options={country "IL",
    # workdays sun..thu, excludes ["fri", "sat", "holiday"], days_offset 0, add_holidays [], remove_holidays []}); check_date
    # through hass.services: Friday 2026-01-09 False, Sunday 2026-01-11 True, the first 2026 holiday of
    # holidays.country_holidays("IL", years=2026) that falls Sun–Thu False — pins the response shape Timerify reads
```

`tests/test_config_flow.py`: `test_workday_step_is_skipped_without_a_workday_sensor` (existing flows unchanged), `test_workday_sensor_is_asked_after_the_duration`, `test_loose_mode_asks_for_the_workday_sensor_after_the_mode`, `test_options_set_and_remove_the_workday_sensor`, `test_workday_sensor_in_use_cannot_be_removed`. `tests/test_interval_flow.py`: `test_workday_modes_need_a_workday_sensor`, `test_workday_interval_titles`, `test_days_default_to_working_days_with_a_sensor`.

- [ ] **Step 2: Run `uv sync && uv run pytest tests/test_workday.py tests/test_config_flow.py tests/test_interval_flow.py -v`** — Expected: new tests FAIL.
- [ ] **Step 3: Implement** the step, the day modes, the Workday questions and tracking, the strings (`selector.interval_days.options`, step and error texts).
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Run intervals on working or non-working days from a Workday sensor"`

---

### Task 7: Phase verification and docs

**Files:**
- Modify: `README.md`, `RULINGS.md`, `docs/followups.md`, `CLAUDE.md` (status line), `custom_components/timerify/manifest.json` (`"version": "0.3.0"`), `pyproject.toml` (`version = "0.3.0"`), `scripts/smoke/run.py`

- [ ] **Step 1: README** — section "Schedules": adding, editing and deleting intervals on the timer's entry; the three day modes and the Workday sensor (where to pick it, that it must answer for the same day — offset 0 —, what an unavailable sensor does); windows across midnight and on DST days; the switch per interval (and that it does not reload); S1–S5 in plain words (a window extends but never shortens a manual run; edits follow while the schedule set the end; a manual change ends that; a manual off holds until the next window, across restarts; a manual on in strict mode runs the default duration); settings of an interval and when they are applied; restart behaviour.
- [ ] **Step 2: RULINGS.md and followups** — a "Phase 3" part with the plan rulings below; rewrite the phase-2 entries they supersede ("Apply is separate…" → S1 owns turn-on-only settings, `apply_if_on` is gone, the stored marker; "The store file is version 2…" → version 3 and its keys; "One alarm sits at `next_wakeup`…" → window starts and ends; "The catch-up folds…" → the tie order and window items; "`observe` runs the catch-up first…" → a realign or an applied S1 counts as moving the timer; the R10 logging entry → the window line). In `docs/followups.md` remove the Phase 3 item (closed by Task 2) and leave the section out.
- [ ] **Step 3: Smoke script** — `add_timer` passes through the `workday` step only when the flow asks for it; new scenario `scenario_schedule`: through `/api/config/config_entries/subentries/flow` add to the input_boolean timer an interval for today's weekday (container time zone) starting at the next whole minute plus one and ending two minutes later; expect the target `on` at the start and `off` at the end (state waits over the WebSocket, as the other scenarios do), and the interval's switch `on`.
- [ ] **Step 4: Run hassfest** — `docker run --rm --platform linux/amd64 -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest` — Expected: no errors (subentry translations, selectors, icons).
- [ ] **Step 5: Run the smoke test** — `uv run python scripts/smoke/run.py` — Expected: every scenario passes.
- [ ] **Step 6: Run all checks on the final tree** — `uv run pytest && uv run ruff check && uv run ruff format --check && uv run mypy` — Expected: all pass; report the test count.
- [ ] **Step 7: Commit** — `git commit -m "Document phase 3 and bump the version to 0.3.0"`

---

## Plan rulings

Decision — why — cost if wrong.

- **Spec interpretation, not a conflict: §5.7's "a schedule window that is active now → apply S1" means a window whose S1 has not run** (it started during downtime, or was never applied); a window already started keeps its `started` mark across the restart. Re-applying S1 would ignore a manual change (R8, §2 anti-goal) and make a restart mis-fire (§2 goal 5); D5 already says "unless suppressed". The design notes' `window_started` / `window_changed` (marked "e.g.") become fold items plus a realign — one wake-up path and no flap after a restart (D4's "one alarm" preferred it) — a user who expects a restart to bring back a window they stopped.
- **One update listener reloads the entry on any change (`async_schedule_reload`, which also collapses repeated changes); `options_flow_reloads = False`; `_follow_target` no longer reloads itself** — in 2026.10.4 a subentry add (`ConfigSubentryFlowManager.async_finish_flow` → `async_add_subentry`), edit (`async_update_subentry`) and delete (`async_remove_subentry`) only fire update listeners, the subentry `async_update_reload_and_abort` raises with a listener, and `OptionsFlowWithReload` raises with one; Home Assistant's usage report says to reload from the listener (ollama and anthropic await `async_reload` there) — every interval add/edit/delete reloads the timer (entities re-added, start-up path re-run); tests prove a countdown and commands survive it.
- **Realign (S2) runs at the end of every fold, from the persisted `scheduled_by` and the current windows; one with nothing to change returns no effects** — after a reload the edit is visible only as new windows, and realign is idempotent when nothing changed — a timer whose end drifted from its window without an edit is pulled back (only possible after the 24-hour cap, which windows respect).
- **Every write of the end goes through `_set_end(end, *, by=None)`; only S1 and the realign pass `by`** — the plan's "`_run_until` and `_end_timer`" missed loose `run_open`, a due on-command and R3, which would have left `scheduled_by` set (S3 broken); `scheduled_by` is `None` whenever `end` is — none.
- **Fold order is one key `(time, rank)`: window ends, window starts, commands, the timer's end** — P3: a command at a window's start is a manual set and wins; a window starting as the timer ends extends it without an off; phase 2's "command before the end" is kept — none.
- **A window start, a window end, a dropped command and an S1 that leaves the timer alone do not count as moving the timer; an applied S1 and a realign that changes it do** — phase 2's R3–R5 skip rule generalised; a realign that stops at start-up must hide R4, or a stopped strict target would get the default duration — none found.
- **A window start whose window has ended by the fold's `now` is dropped: marked started, timer untouched, no log** — §5.7 lists only active windows and R10 drops an "on" whose window passed (the start-while-unavailable line already said so); otherwise a kept window that passed during downtime would cut a loose open run — a user who wants a log for a window missed while Home Assistant was down.
- **S4 is a persisted `started` mark per occurrence: a window applies S1 once.** It survives edits (an active window of the same interval inherits it) and restarts. So any zeroing during a started window — R3, a stop from the card, the end of a manual run, an off command — keeps the target off until the next window — R8 "manual wins", and restart must behave like no restart — a user who stops the boiler from the card and expects a restart to bring the window back.
- **An edit that moves the active occurrence so it is no longer active creates a new occurrence** — S2 stops a scheduled timer now, and the moved window applies S1 at its start even after a manual off — S2's "start later if the window moved ahead" — moving an interval ahead can undo a manual off for that day (it is a new window).
- **Adding an interval or switching one on during its window starts it for the remainder; switching off and on again forgets S4 for that occurrence** — schedules are declarative and a restart does the same (§5.7) — a surprise turn-on when enabling mid-window.
- **Deleting an interval is disabling it for S2; a realign to "stop" does not hand the timer to an overlapping window that already started** — S2 says stop; the hand-over would need a second mark distinguishing started from suppressed — in the rare overlap the target stays off until the other interval's next window.
- **At a window start the interval's settings are owed (turn-on only) only if the target does not run as of that item: the fold's wish so far is "on", or, before any wish, it is on or its turn-on is in flight** — §5.4's bullet, also when the fold replays several items; the in-flight case keeps a command's settings (P1); one predicate shared with `_deliver_settings` — none.
- **S1 is the only source of turn-on-only settings, so `apply_if_on` is removed** (Task 2 replaces its four phase-2 tests with named window tests) — two places deciding the same rule, one of them a parameter without a production caller — a future caller that must not push onto a running target re-adds a keyword.
- **Turn-on-only settings are dropped, not applied, when the target is found on without our turn-on list completing** (D6, store key `owed_turn_on_only`) — the target is running by someone else's hand — a schedule's `set_*` call that fails right after its own successful turn-on is not retried.
- **Window refreshes run under the one lock through `_async_refresh_windows_locked`; event callbacks use `_refresh_windows`, which takes the lock; after every await the controller re-checks that it is still loaded and takes `now` afresh** — `asyncio.Lock` is not re-entrant (a wake-up or a toggle calling the locking variant deadlocks), and a stale controller that outlived a reload during a Workday call must not save over the new one — none.
- **Start-up merges the fresh windows, arms `next_wakeup` read after the merge, observes, and executes the merge's and the observation's effects together; event subscriptions (time zone, Workday) start only after that first fold** — one save and one fold, §5.7's order — none.
- **Occurrences are computed ahead, one current-or-next window per enabled interval, in Home Assistant's time zone, refreshed when the zone changes (`EVENT_CORE_CONFIG_UPDATE`); a Workday answer is asked when an occurrence is computed, not at its start** — `check_date` answers a date deterministically, and computing ahead keeps the core pure and the alarm single — a Workday configuration changed between computing and the start is noticed only when the sensor reports (its entry reloads, so it does).
- **An unknown Workday answer (sensor unavailable, call failed, service missing) keeps every window the interval already has, started or not (`keep`), and computes nothing new for it; the first unknown answer of a refresh ends that refresh's questions; one warning per outage; refresh on the sensor's next state change or state report** — D3, event-driven, and Workday writes its state every midnight, so a transient failure is retried within a day without polling — a window of a sensor that never comes back never starts, with the warning saying why.
- **The Workday answer is taken as the sensor gives it, `days_offset` included; the README asks for a sensor with offset 0** — no reading of another integration's options — a user with a "tomorrow" sensor gets shifted days until they read the README.
- **The search horizon is `WINDOW_SEARCH_DAYS = 14`** — weekday intervals always match within 7 days; a Workday-based one with no match is re-searched when the sensor reports (daily) — none found.
- **DST: wall times convert with `fold=0`; an occurrence swallowed by the gap is skipped; windows are capped at `MAX_MINUTES`** — zoneinfo's own rule, no private HA helpers — a 02:30–03:15 interval does not run on the spring-forward day.
- **The interval form refuses seconds (`whole_minutes_only`), accepts the UI's `HH:MM:00`, and stores `"HH:MM"`; its settings pass through the services' `SETTINGS_SCHEMA` before `validate_settings`** — values are never silently dropped, and a setting has one type whichever channel made it — none.
- **Titles are generated in Home Assistant's configured language from the selector labels; a title the user renamed survives edits** — subentry titles are plain strings — a title stays in the language of its creation.
- **The enable flag is `Snapshot.disabled_intervals` in the timer's store, enabled by default; the core drops windows of disabled intervals and the controller does not compute them** — one store, one save path, a toggle never reloads (D2), the invariant has one owner — none.
- **Every Timerify entity attaches to its device through `device_entry`: the target's device, or the timer's own device got or created once without a subentry (`timer_device`)** — in 2026.10.4 an entity of a subentry that brings the shared `DeviceInfo` moves the device into the subentry (deprecated, an error from 2027.8), the registry then drops the number and sensors, and deleting the interval deletes the device — none.
- **The switch is named `"Schedule {interval}"` with the subentry title** — the title identifies the interval and follows edits after the reload — entity ids keep the first title.
- **The Workday step appears only when a Workday sensor exists (or is set, in options); its schema function returns `None` to skip it** — §6.2's "three clicks for the common case"; D3's order otherwise kept; a `next_step` sees only the options, so the schema decides — a user who adds a Workday sensor later picks it in the options.
- **Store version 3 gets its keys over Tasks 2, 4 and 5 without further versions** — 0.3.0 is unreleased between them; strict reads stay — a v3 file from a development build between those tasks fails to load (developer machines only).
- **`holidays==0.106` joins the dev group for one contract test with the real Workday integration; scenarios use `FakeWorkday`, which fails the way Home Assistant does (`HomeAssistantError`, "did not match any entities")** — the real test pins the response shape and the Israeli week, the fake controls holidays and outages — a dev dependency to bump with Home Assistant.
- **A loose open run is cut at a window's end when the window starts during it** — S1 sets the timer, and a timer above zero means "off at zero" in loose mode — loose users may expect the run to continue.
- **One jump of the clock in a test is one catch-up; scenario tests step to each event** — Home Assistant fires a chained alarm at once with the frozen time, so a jump over a start and an end folds them (that is the downtime behaviour, tested with `restart_after`) — none.
- **The smoke interval uses days of the week, not a Workday sensor** — the container's date is not under the script's control — the real `check_date` is proven by the pytest contract test, not in the container.

---

## Appendix: pre-flight (shared files and interfaces; gate after each task)

Full scan with HA API checks and the 33 findings: `.superpowers/sdd/2026-10-29-phase-3-schedules/preflight.md`.

| Pair | Shared | Conflict and resolution | Gate green after the later task |
|---|---|---|---|
| T1 → T2 | `core.py` S1 owing, `_runs_as_of`, `_owe`; `test_core.py` | T2 adds `turn_on_only=True` to S1's `_owe` and removes `apply_if_on` with its four phase-2 tests (each replaced by a named window test) | yes |
| T2 → T4, T5 | `store.py` v3 payload and both migration branches; `helpers.payload` | each adds keys with defaults to payload, migration and `payload()`; every `saved == payload(...)` goes through the helper | yes |
| T3 → T4 | subentry data keys, `add_interval`/`edit_interval`, `schedule.py` | T4 adds `Interval.from_subentry` reading the keys T3 stores | yes |
| T3 → T5 | the reload on subentry delete removes the switch (registry clear); the timer's own device | T5 attaches every entity through `device_entry` (`timer_device`), so no device moves into a subentry | yes |
| T3 → T6 | `IntervalSubentryFlow` form, `interval_title` labels, `test_interval_flow.py` | T6 adds `days` before `weekdays`; T3 already stores `"days": "weekdays"`, so data stays compatible; `add_interval(days=...)` gains the parameter in T6 | yes |
| T3 → T6 | `config_flow.py` step chain (`_after_mode`), `test_config_flow.add_target` | T6's `workday` step skips itself by a schema function returning `None` without a Workday sensor, so existing flow tests and the smoke `add_timer` keep their steps | yes |
| T1 → T4 | `set_windows(..., configured, keep)`, `tick`, `next_wakeup` | defined complete in T1 so T4 needs no signature change; T4 merges at start-up, arms after the merge, observes, one `_execute` | yes |
| T1 → T5 | `set_windows` prunes `disabled_intervals`, drops disabled windows | T5 extends the body only, not the signature | yes |
| T4 → T5 | `_async_refresh_windows_locked`, `_refresh_windows`, `_async_windows`, `_refresh_entities`, `_command` | T5's enable path calls the locked helper (never `_refresh_windows` under the lock), shares `_raise_if_unloaded`, adds the disabled filter and the notify condition | yes |
| T4 → T6 | `_async_windows` returns `(windows, unknown)` from T4 on; subscriptions in `_handle_started` | T6 fills `unknown`, re-checks `_stopped` after its awaits, subscribes to the sensor after the first fold; no caller changes | yes |
| T4 → T7 | `restart` moved to `tests/helpers.py` | T4 moves it and updates `test_restart.py` imports in the same task | yes |
| T5 → T7 | `PLATFORMS`, smoke expects the interval switch | the smoke reads the switch by unique id `"{entry_id}_interval_{subentry_id}"` | yes |
| T6 → T7 | `pyproject.toml` (dev deps, version) | T7 edits only `version` | yes |
| all | `translations/en.json` + `ru.json`, `test_translations.py` (same keys and blanks in every language) | every task adds its keys to both files | yes |

No task adds an `Effect` type (window starts reuse `TurnOn`/`TurnOff`/`Arm`), renames a public method, or leaves a caller of a changed signature (`apply_if_on` has no caller outside the tests Task 2 replaces); each new core method is called by the controller in the task that needs it or, in Tasks 1 and 2, only by `test_core.py`.
