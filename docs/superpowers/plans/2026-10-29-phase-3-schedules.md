# Timerify Phase 3 — Schedules with Workday Sensors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A target gets weekly schedule intervals ("weekdays 06:30–07:15", "working days", "non-working days" by a Workday sensor) that run its timer per S1–S5, each with an enable `switch`, added and edited one by one as config subentries, surviving restarts, DST and an unavailable Workday sensor.

**Architecture:** The pure core learns *windows* — concrete occurrences of an interval (`Window(interval_id, start, end, settings, started)`) handed to it by the controller — and folds a window's start (S1) and end into the same catch-up that already folds commands and the end, so one alarm at `next_wakeup` serves all four and a restart never flaps. Every fold ends with a realign (S2): while `scheduled_by` names an interval, the timer follows that interval's active window, or stops when there is none; any other change of the timer clears `scheduled_by` (S3). A window applies S1 once per occurrence: its persisted `started` mark is what S4 needs and survives edits and restarts. The controller (HA side) computes each enabled interval's current-or-next window in the local time zone, asking `workday.check_date` for Workday-based intervals, and refreshes them at start-up, after a window ends, on a switch toggle and when the Workday sensor reports. Subentry add/edit/delete reach the entry only through update listeners in 2026.10.4, so one update listener reloads the entry; the enable flag lives in the timer's store, so a toggle never reloads. Each task is a vertical slice that leaves all four checks green.

**Tech Stack:** Python 3.14, Home Assistant 2026.10.4 (`ConfigSubentryFlow`, `async_get_supported_subentry_types`, `async_add_entities(..., config_subentry_id=...)`, `workday.check_date`, `probatio`, time/select/entity selectors), pytest-homeassistant-custom-component 0.13.375 (`freezer`, `hass_storage`, `async_fire_time_changed`), `holidays==0.106` (dev only, Task 6), ruff, mypy, uv.

**Spec:** `docs/superpowers/specs/2026-10-28-timerify-design.md` — phase 3 of §7: §5.5 (S1–S5), the schedule bullets of §5.4, the schedule bullet of §5.7, the `switch` of §6.1, the subentries and the Workday step of §6.2. Controller decisions: `.superpowers/phase-3-design-notes.md` (D1–D8). Voice, card, runtime counter and the config-flow menu are later plans.

**Starting point:** `main` after phase 2 merges. Shape relied on: `core.py` — pure `TimerCore` with owed settings (`_owe`, `_deliver_settings`, `_settings_for_running_target`, `apply_if_on`), commands, `tick`, one `_catch_up` that folds due items in time order and wants one final wish, `next_wakeup(snapshot)`, resend allowances; `controller.py` — one lock, one wake-up alarm (`_arm`), labelled call lists, `_execute` ending in `assert_never`, `_refresh_entities` notifying on `end`/`commands` changes, `_handle_started` arming the stored wake-up then observing; `store.py` — `TimerStore` v2, strict reads, `_TimerFile._async_migrate_func`; `domains.py` — settings rows, `validate_settings`, `_Capabilities`; `config_flow.py` — `SchemaConfigFlowHandler` with `options_flow_reloads = True`; `__init__.py` — `_follow_target` updates options and schedules a reload; tests — `provide_target`, `fake_target`, `fake_climate`, `setup_target(stored=..., stored_version=...)`, helpers `advance`, `call_service`, `payload`, `saved`, `at`, `state_of`, `timerify_warnings`; `restart` still lives in `tests/test_restart.py`. If the shape differs, adapt names, not behaviour.

## Global Constraints

- Home Assistant `>= 2026.10.4` (`hacs.json`), Python `>= 3.14.2`, `pytest-homeassistant-custom-component==0.13.375`.
- Only public HA mechanisms; schemas with `probatio`, never `voluptuous`; import HA names from the module that defines them (mypy strict). No `RestoreEntity` for the enable flag: it lives in `TimerStore`.
- Every user-facing string in `translations/en.json` (source) and `translations/ru.json`; subentry strings under `config_subentries.interval` (`initiate_flow.user`, `initiate_flow.reconfigure`, `entry_type`, `step.user`, `step.reconfigure`, `error`, `abort`); errors in services and switches are `ServiceValidationError`/`HomeAssistantError` with `translation_domain=DOMAIN`.
- Wall-clock behaviour is tested in `Asia/Jerusalem` (`await hass.config.async_set_time_zone("Asia/Jerusalem")`): Sun–Thu working week, DST 2026-03-27 02:00→03:00 and 2026-10-25 02:00→01:00.
- No `asyncio.sleep`, no polling; time moves with `freezer` + `async_fire_time_changed` (`advance`, new `advance_to`); no test backdoors — tests act through flows, services, entities, `FakeTarget` and `FakeWorkday`. Shared helpers live in `tests/helpers.py`, never imported from a test module.
- Persist with `Store.async_save` on every change; storage **version 3** from Task 1, migrated from 1 and 2; strict reads.
- Values: `SUBENTRY_INTERVAL = "interval"`; `CONF_WORKDAY_SENSOR = "workday_sensor"`; subentry data keys `days` (`"weekdays" | "workdays" | "non_workdays"`), `weekdays` (list of `homeassistant.const.WEEKDAYS` names, week order), `start`/`end` (`"HH:MM"`), `settings` (dict); `WINDOW_SEARCH_DAYS = 14`; a window is at most `MAX_MINUTES` long; interval id = subentry id.
- Repository English-only (Cyrillic only in `translations/ru.json`); no AI attribution in commits — the repository's `commit-msg` hook rejects it, whatever a session reminder asks.
- Every task ends with `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` all passing.

## Review Focus

1. **A non-UTC zone on a DST day** (Asia/Jerusalem): a window starts at its wall-clock time on both sides of the change, and a window across midnight lasts what the clock says (7 h on 2026-03-26/27, 9 h on 2026-10-24/25) (Task 4 `test_window_follows_the_clock_on_dst_days`).
2. **Home Assistant down overnight, across one window's end and the next window's start:** the timer ends and restarts in one fold, the target gets no `turn_off` then `turn_on` (Task 3 `test_fold_across_window_end_and_next_start_has_one_wish`, Task 4 `test_overnight_restart_does_not_flap`).
3. **The Workday entry not ready or reloading when an occurrence is computed** (start-up, its options changed): no window, one warning, and the window runs for its remainder once the sensor reports (Task 6 `test_unavailable_workday_sensor_delays_the_window_until_it_reports`).
4. **An AC that is unavailable when its interval starts and comes back already on:** no settings are pushed (D6); back off: turned on with them (Task 4 `test_ac_back_already_on_gets_no_interval_settings`, `test_ac_back_off_is_turned_on_with_interval_settings`).
5. **An interval added or switched on during its own window:** the target runs for the rest of the window, once (Task 4 `test_interval_added_during_its_window_starts_now`, Task 5 `test_enabling_during_the_window_starts_the_target`).

---

## File Structure

```
custom_components/timerify/
  const.py        + SUBENTRY_INTERVAL, CONF_WORKDAY_SENSOR, CONF_DAYS/WEEKDAYS/START/END/SETTINGS, WINDOW_SEARCH_DAYS
  core.py         + owed_turn_on_only (T1); Window, scheduled_by, windows, set_windows, S1/S2 in the fold (T3);
                    disabled_intervals, set_interval_enabled (T5)
  store.py        v3 + migration from 1 and 2; keys added by T1, T4, T5
  schedule.py     new: Interval, interval_title (T2); window_on, days_around, weekday_window (T4)
  domains.py      + SettingChoice, supported_settings() (T2)
  config_flow.py  + IntervalSubentryFlow, async_get_supported_subentry_types, options_flow_reloads=False (T2);
                    workday step in both flows, day modes (T6)
  __init__.py     update listener that reloads; _follow_target no longer reloads itself (T2); + Platform.SWITCH (T5)
  controller.py   window refresh, intervals from subentries (T4); set_interval_enabled (T5); check_date, Workday tracking (T6)
  switch.py       new: IntervalSwitch (T5)
  entity.py       unique_id override (T5)
  icons.json, translations/en.json, translations/ru.json
tests/
  conftest.py     + FakeWorkday / fake_workday (T6)
  helpers.py      + JERUSALEM, local(), advance_to(), add_interval(), edit_interval(), restart() moved here, payload keys
  test_core.py test_restart.py test_config_flow.py test_interval_flow.py (new, T2) test_schedules.py (new, T4)
  test_interval_switch.py (new, T5) test_workday.py (new, T6) test_translations.py
pyproject.toml, uv.lock  + holidays==0.106 in the dev group (T6)
scripts/smoke/run.py, README.md, RULINGS.md, docs/followups.md, manifest.json (T7)
```

---

### Task 1: Settings that may only travel with a turn-on are stored (D6)

**Files:**
- Modify: `custom_components/timerify/core.py`, `custom_components/timerify/store.py`, `tests/test_core.py`, `tests/test_restart.py`, `tests/helpers.py`

**Interfaces:**
- Produces in `core.py`: `Snapshot.owed_turn_on_only: bool = False` — the owed settings may reach the target only inside a `TurnOn`. `_owe(settings, *, turn_on_only: bool = False)`.
- Produces in `store.py`: `TimerStore.STORAGE_VERSION = 3`; payload key `"owed_turn_on_only": bool`; migration: v1 → `{**old, "owed_settings": {}, "commands": [], "owed_turn_on_only": False}`, v2 → `{**old, "owed_turn_on_only": False}`. Later tasks add keys to version 3 and to both migration branches.
- Produces in `tests/helpers.py`: `payload(..., owed_turn_on_only: bool = False)`.

Core rules:
1. A command with `apply_if_on=False` that causes a turn-on owes its settings with `turn_on_only=True`; non-empty settings with `apply_if_on=True` set the marker to False. An empty command leaves settings and marker alone.
2. `_deliver_settings` never returns `ApplySettings` while the marker is set.
3. A pending `"on"` that settles because the target is found on without our turn-on list having completed — `observe` with `_unsent` and `actual == "on"`, or `_want` finding `last_actual == "on"` — drops marked settings (`_clear_settings`, which also clears the marker). A `TurnOn` that went out still carries them, and `settings_applied` clears both.

- [ ] **Step 1: Write the failing tests** (`COOL24`, `HEAT22` as in phase 2)

```python
def test_turn_on_only_settings_ride_with_the_turn_on():     # "off": set_duration(NOW, 60 min, COOL24, apply_if_on=False)
    # == [Arm(NOW+60), TurnOn(COOL24), Changed()]; snapshot.owed_turn_on_only is True
def test_turn_on_only_settings_are_dropped_when_the_target_comes_back_on():  # "unavailable"; same command → no TurnOn;
    # observe(NOW, "on", by_us=False) has no ApplySettings; owed_settings == NO_SETTINGS and owed_turn_on_only is False
def test_turn_on_only_settings_go_with_the_turn_on_when_the_target_comes_back_off():  # observe("off") → [TurnOn(COOL24)]
def test_manual_on_after_a_failed_turn_on_drops_turn_on_only_settings():  # "off", TurnOn(COOL24), call_failed,
    # observe("on", by_us=False) → no ApplySettings, owed empty
def test_a_command_that_applies_when_on_replaces_the_marker():  # unavailable, apply_if_on=False COOL24, then
    # set_duration(30 min, HEAT22) → marker False; observe("on") → [ApplySettings(HEAT22), ...]
def test_restored_turn_on_only_settings_skip_a_running_target():  # Snapshot(end=NOW+30, pending="on", owed_settings=COOL24,
    # owed_turn_on_only=True); observe(NOW, "on", by_us=False) == [Changed()]; owed empty
```

`tests/test_restart.py`: `test_turn_on_only_settings_survive_a_restart_and_skip_a_running_ac` (stored `payload(end=at(30), pending="on", owed_settings={"hvac_mode": "cool"}, owed_turn_on_only=True)`, `fake_climate` in `"heat"` → `fake_climate.call_data == []`, `saved(...) == payload(end=at(30))`); `test_version_2_store_is_migrated` (stored v2 dict with owed settings → loads, marker False, saved as v3); update `test_version_1_store_is_migrated` and every `saved(...) ==` to the new `payload`.

- [ ] **Step 2: Run `uv run pytest tests/test_core.py tests/test_restart.py -v`** — Expected: new tests FAIL.
- [ ] **Step 3: Implement** the marker, its rules and store v3.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Store whether owed settings may only travel with a turn-on"`

---

### Task 2: Intervals as config subentries; changes reload the entry

**Files:**
- Modify: `const.py`, `domains.py`, `config_flow.py`, `__init__.py`, `translations/en.json`, `translations/ru.json`, `tests/helpers.py`, `tests/test_config_flow.py`, `tests/test_source_changes.py`
- Create: `custom_components/timerify/schedule.py`, `tests/test_interval_flow.py`

**Interfaces:**
- Produces in `const.py`: `SUBENTRY_INTERVAL`, `CONF_DAYS`, `CONF_WEEKDAYS`, `CONF_START`, `CONF_END`, `CONF_SETTINGS` (values in Global Constraints); `type DaysMode = Literal["weekdays", "workdays", "non_workdays"]`.
- Produces in `schedule.py`:
  - `@dataclass(frozen=True) class Interval: id: str; days: DaysMode; weekdays: frozenset[str]; start: time; end: time; settings: Settings` and `@classmethod from_subentry(cls, subentry: ConfigSubentry) -> Interval`.
  - `def interval_title(data: Mapping[str, Any], labels: Mapping[str, str]) -> str` — `"{start}–{end}, {days}"` with an en dash; days: the label of `workdays`/`non_workdays`, or the weekday labels in week order where a cyclic run of three or more is `"First–Last"` and the rest are joined by `", "`; all seven is `"Mon–Sun"`. `labels` maps `"mon"`..`"sun"` (and from Task 6 the two modes) to their translated labels.
- Produces in `domains.py`: `@dataclass(frozen=True) class SettingChoice: name: str; options: tuple[str, ...] = (); low: float | None = None; high: float | None = None` and `def supported_settings(hass, entity_id) -> tuple[SettingChoice, ...]` — the row's settings the entity supports (`_Setting.supported`), options for `_OneOf` (excluded removed), bounds for `_Between`; `()` for an entity known to neither state nor registry.
- Produces in `config_flow.py`: `class IntervalSubentryFlow(ConfigSubentryFlow)` with `async_step_user` and `async_step_reconfigure` sharing one form builder; `TimerifyConfigFlowHandler.async_get_supported_subentry_types` → `{SUBENTRY_INTERVAL: IntervalSubentryFlow}`; `options_flow_reloads = False`.
- Produces in `__init__.py`: `entry.async_on_unload(entry.add_update_listener(_async_entry_updated))`, where `_async_entry_updated` calls `hass.config_entries.async_schedule_reload(entry.entry_id)`; `_follow_target.set_target` only updates the options (the listener reloads).
- Produces in `tests/helpers.py`: `WEEK = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")`; `async def add_interval(hass, entry, *, start: str, end: str, weekdays: Sequence[str] = WEEK, settings: dict[str, Any] | None = None) -> str` (drives `hass.config_entries.subentries.async_init((entry.entry_id, SUBENTRY_INTERVAL), context={"source": "user"})`, returns the new subentry id); `async def edit_interval(hass, entry, subentry_id, **fields) -> FlowResult` (`context={"source": "reconfigure", "subentry_id": ...}`, prefilled with the current data).

Form (both steps, in this order): `weekdays` — `SelectSelector(options=WEEKDAYS, multiple=True, mode=LIST, translation_key="weekday")`, default all seven (edit: current); `start`, `end` — `TimeSelector()`; when `supported_settings` is non-empty, a collapsed section `settings` with one optional field per choice: options → `SelectSelector` (`translation_key="hvac_mode"` for `hvac_mode`), bounds → `NumberSelector(min, max, step=0.5 for temperature else 1, mode=BOX)`. Stored data: `{"days": "weekdays", "weekdays": [...week order], "start": "HH:MM", "end": "HH:MM", "settings": {...}}`. Errors (`config_subentries.interval.error`): `no_weekdays` (empty list), `same_start_and_end`, `whole_minutes_only` (a time with seconds other than 0), `settings_not_supported` (the `ServiceValidationError` of `validate_settings`, field `base`). Title: `interval_title` with labels from `async_get_translations(hass, hass.config.language, "selector", [DOMAIN])` (`selector.weekday.options.*`: short labels Mon … Sun, and the Russian two-letter abbreviations in `ru.json`). Reconfigure: `async_update_and_abort(entry, subentry, data=..., title=...)`, regenerating the title only while it equals the title generated from the old data (a title the user renamed stays). Abort `reconfigure_successful` comes from Home Assistant.

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

`tests/test_config_flow.py`: `test_options_change_reloads_and_keeps_the_countdown` still passes (now through the listener). `tests/test_source_changes.py`: `test_target_rename_keeps_timer` still passes with a single reload.

- [ ] **Step 2: Run `uv run pytest tests/test_interval_flow.py tests/test_config_flow.py tests/test_source_changes.py -v`** — Expected: new tests FAIL.
- [ ] **Step 3: Implement** `schedule.py` (model and title), `supported_settings`, the subentry flow, the listener, the translations (`config_subentries.interval`: `initiate_flow.user` "Add schedule interval", `initiate_flow.reconfigure` "Edit schedule interval", `entry_type` "Schedule interval", step texts per field, the errors; `selector.weekday.options`).
- [ ] **Step 4: Run all checks** — Expected: all pass (intervals are stored and do nothing yet).
- [ ] **Step 5: Commit** — `git commit -m "Add schedule intervals as config subentries of a timer"`

---

### Task 3: Windows in the core — S1, S2, S3, S4 in one fold

**Files:**
- Modify: `custom_components/timerify/core.py`, `tests/test_core.py`

**Interfaces:**
- Consumes: `owed_turn_on_only` and `_owe(..., turn_on_only=True)` (Task 1).
- Produces in `core.py`:
  - `@dataclass(frozen=True) class Window: interval_id: str; start: datetime; end: datetime; settings: Settings = NO_SETTINGS; started: bool = False` — one occurrence of an interval, UTC-aware, `start < end <= start + MAX_MINUTES`; `started` means S1 was applied to it (or left the timer alone) and it never applies again.
  - `Snapshot.scheduled_by: str | None = None` — the interval whose window end the timer carries, while nobody changed the timer since. `Snapshot.windows: tuple[Window, ...] = ()` — sorted by `start`, at most one per interval.
  - `TimerCore.set_windows(now, windows: Iterable[Window], *, configured: AbstractSet[str], keep: AbstractSet[str] = frozenset()) -> list[Effect]` — replaces the windows; the current window of an interval in `keep` stays as it is (its occurrence could not be computed); windows of intervals not in `configured` go. A fresh window active at `now` (`start <= now < end`) inherits `started=True` from an old started window of the same interval that is active at `now` (the same occurrence, perhaps edited). Merges only: returns `[Arm|Disarm]` (+`Changed()`); the next `tick` or `observe` folds.
  - `next_wakeup(snapshot)` = the earliest of `end`, the first command's `at`, the `start` of every window not started, the `end` of every window.
  - `tick(now)` and `observe(...)`: the catch-up folds window starts and ends with commands and the end, then realigns (below), and always realigns even when nothing is due.

Fold (extends `_catch_up`): items at or before `now` in time order; on a tie: window ends, window starts, commands, the timer's end (P3: a command at the same instant as a window start wins). Items:
- *Window end*: the window is removed. Nothing else.
- *Window start* (S1): mark it `started`. If `end is not None and end >= window.end`, leave the timer alone (`scheduled_by` unchanged). Otherwise `end = window.end`, `scheduled_by = window.interval_id`, wish `"on"`, and owe `window.settings` with `turn_on_only=True` only if the target is not running as of this item: `wish != "on" and not (wish is None and last_actual == "on")` (§5.4: a window that starts on a running target pushes nothing).
- *Realign* (S2), after the items, at `now`: if `scheduled_by` names X and X has a window with `start <= now < end` whose `end != snapshot.end` → `end = that end` (wish `"on"`, `scheduled_by` kept); if X has no active window → stop (wish `"off"`, `scheduled_by = None`). A realign that changes the timer counts as "moved the timer" for `observe`'s R3–R5 skip.
- Every other change of the timer — `set_duration`, `add`, `stop`, `run_open`, a command (P3), R3, R4, the end reached — sets `scheduled_by = None` (S3). Implement it once: `_run_until(..., by: str | None = None)`, `_end_timer` clears it.

- [ ] **Step 1: Write the failing tests** (`W = Window("x", NOW, NOW + 45 min)`; helpers `window(id, start_min, end_min, **kw)`)

```python
def test_window_start_runs_the_timer_to_its_end():          # strict "off", set_windows([W(start=NOW+5)]); tick(NOW+5)
    # == [Arm(NOW+45), TurnOn(), Changed()]; scheduled_by == "x"; windows[0].started
def test_window_start_leaves_a_later_end_alone():             # set_duration 60 → end NOW+60; window NOW..NOW+45 → end NOW+60,
    # scheduled_by None, no TurnOn
def test_window_start_extends_an_earlier_end():               # set_duration 10; window to NOW+45 → end NOW+45, scheduled_by "x"
def test_window_settings_go_with_the_turn_on():               # "off", window settings COOL24 → TurnOn(COOL24), marker True
def test_window_settings_skip_a_running_target():             # "on" → no ApplySettings, owed empty
def test_window_after_a_command_in_the_same_fold_pushes_no_settings():  # command on at 06:20 (fold) then window at 06:30 →
    # owed == the command's settings
def test_realign_shortens_extends_and_stops():                # scheduled_by "x": set_windows with x NOW-60..NOW+30 → end NOW+30;
    # ..NOW+90 → NOW+90; x only tomorrow → TurnOff, end None, scheduled_by None
def test_realign_after_a_move_ahead_stops_then_starts_at_the_new_start()
def test_manual_change_ends_realignment():                    # add(+30) → scheduled_by None; set_windows shorter → end unchanged
def test_target_off_during_a_window_stays_off_until_the_next_window():  # R3 at NOW+10 → end None; set_windows with the same
    # occurrence (fresh, started=False) → inherits started; tick → nothing; next occurrence tomorrow → TurnOn at its start
def test_restored_started_window_does_not_start_again()       # Snapshot(windows=(W started,)) + observe("off") → no TurnOn
def test_manual_on_during_a_window_gets_the_default_duration():  # strict R4 → end NOW+10+45, not the window end (S5)
def test_overlapping_windows_follow_the_later_end():          # a 0..60, b 30..120 → end 120, scheduled_by "b"; a then edited → no change
def test_command_at_a_window_start_wins():                    # on-command for 10 min at the start instant → end start+10
def test_fold_across_window_end_and_next_start_has_one_wish():  # Snapshot(end=Mon 07:15, windows=(Mon started,)), target "on",
    # set_windows([Tue 06:30–07:15]); observe(Tue 06:45, "on") → no TurnOff, end Tue 07:15, scheduled_by "x"
def test_kept_window_is_not_realigned():                      # scheduled_by "x", set_windows([], keep={"x"}) → nothing changes
def test_window_of_an_unconfigured_interval_is_dropped_and_its_timer_stops()  # configured=set() while scheduled_by "x" → off
def test_tick_with_nothing_due_and_no_schedule_still_returns_nothing()  # phase-2 contract kept
def test_next_wakeup_includes_window_starts_and_ends()
```

- [ ] **Step 2: Run `uv run pytest tests/test_core.py -v`** — Expected: new tests FAIL.
- [ ] **Step 3: Implement** `Window`, the snapshot fields, `set_windows`, the fold items, realign and `scheduled_by` clearing. No new `Effect` type.
- [ ] **Step 4: Run all checks** — Expected: all pass (the controller does not call `set_windows` yet).
- [ ] **Step 5: Commit** — `git commit -m "Fold schedule windows into the timer core"`

---

### Task 4: Intervals run the timer (days of the week)

**Files:**
- Modify: `schedule.py`, `controller.py`, `store.py`, `tests/helpers.py`, `tests/test_restart.py`
- Create: `tests/test_schedules.py`

**Interfaces:**
- Consumes: `Interval` (Task 2), `Window`, `set_windows`, `tick`, `next_wakeup` (Task 3).
- Produces in `schedule.py`:
  - `def window_on(interval: Interval, day: date, zone: tzinfo) -> Window | None` — the occurrence that starts on `day`: start = `datetime.combine(day, interval.start, zone)` (`fold=0`), end on `day + 1` when `interval.end <= interval.start`; both to UTC; end capped at start + `MAX_MINUTES`; `None` when the end is not after the start (swallowed by a DST gap). A wall time in the spring-forward gap lands by the gap's length later (02:30 → 03:30); an ambiguous one takes its first occurrence.
  - `def days_around(now: datetime, zone: tzinfo) -> Iterator[date]` — the local date of `now` minus one day, then each day up to `WINDOW_SEARCH_DAYS` ahead.
  - `def weekday_window(interval: Interval, now: datetime, zone: tzinfo) -> Window | None` — the first `window_on` over `days_around` whose day's weekday is in `interval.weekdays` and whose end is after `now`.
- Produces in `controller.py`: `self._intervals: dict[str, Interval]` from `entry.get_subentries_of_type(SUBENTRY_INTERVAL)`; `async def _async_windows(self, now) -> tuple[list[Window], frozenset[str]]` (windows, interval ids whose occurrence is unknown — always empty in this task); `async def _refresh_windows(self) -> None` (under the lock: `set_windows(now, windows, configured=set(self._intervals), keep=unknown) + tick(now)`, executed). `_handle_started`: `set_windows` (no tick) before the existing arm and `observe`, so one fold covers stored and fresh windows. `_handle_wakeup`: after executing `tick`, `_refresh_windows()` when a window was removed. Zone: `dt_util.get_default_time_zone()`. R10 log at info when a window started while the target is unavailable: `"A schedule window of %s started while it is unavailable; it is turned on when it is back"`.
- Produces in `store.py`: keys `"scheduled_by": str | None`, `"windows": [{"interval", "start", "end", "settings", "started"}]` (ISO UTC); in both migration branches (`None`, `[]`).
- Produces in `tests/helpers.py`: `JERUSALEM = "Asia/Jerusalem"`; `def local(day: date, clock: str) -> datetime` (UTC of a Jerusalem wall time, `fold=0`); `async def advance_to(hass, freezer, moment: datetime)`; `restart(hass, entry)` moved from `test_restart.py`; `async def restart_after(hass, freezer, entry, **delta)` — unload, move the clock without firing, set up again; `payload(..., scheduled_by=None, windows=())`.

- [ ] **Step 1: Write the failing tests** (`tests/test_schedules.py`; each test sets `JERUSALEM`, moves to `local(SUNDAY, "06:00")` with `SUNDAY = date(2026, 1, 4)`, then `setup_target()` and `add_interval`)

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
async def test_moving_the_running_interval_ahead_stops_and_starts_later()  # at 07:00 edit 07:30–08:30 → TURN_OFF now, TURN_ON 07:30
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
async def test_overlapping_intervals_follow_the_later_end()     # 06:00–07:00 and 06:30–08:00 → ends 08:00; editing the
    # first changes nothing; editing the second to 06:30–07:30 → 07:30
async def test_interval_settings_turn_the_ac_on_cooling(hass, freezer, fake_climate, setup_target):
    # interval with {"hvac_mode": "cool", "temperature": 24}; at start call_data == [set_hvac_mode cool, set_temperature 24]
async def test_interval_starting_on_a_running_ac_pushes_no_settings()   # AC "heat" (R4) → no set_* calls; ends at window end
async def test_ac_back_already_on_gets_no_interval_settings()   # AC unavailable at start, back "heat" → call_data == []
async def test_ac_back_off_is_turned_on_with_interval_settings()  # back "off" → set_hvac_mode cool, set_temperature 24
async def test_interval_added_during_its_window_starts_now()    # at 06:45 add 06:30–07:15 → TURN_ON, ends 07:15
async def test_window_start_while_unavailable_is_logged(caplog)
```

`tests/test_restart.py`: `test_schedule_state_is_stored` (after a window start `saved(...) == payload(end=..., scheduled_by=<id>, windows=[{... "started": True}, ...])` with the next occurrence after the end); migrations carry the new keys.

- [ ] **Step 2: Run `uv run pytest tests/test_schedules.py tests/test_restart.py -v`** — Expected: new tests FAIL.
- [ ] **Step 3: Implement** the window functions, the controller refresh and the store keys.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Run the timer on schedule intervals by day of the week"`

---

### Task 5: One enable switch per interval

**Files:**
- Modify: `core.py`, `store.py`, `controller.py`, `entity.py`, `__init__.py`, `icons.json`, `translations/en.json`, `translations/ru.json`, `tests/test_core.py`, `tests/helpers.py`
- Create: `custom_components/timerify/switch.py`, `tests/test_interval_switch.py`

**Interfaces:**
- Consumes: `set_windows`, `tick`, `_refresh_windows`, `_async_windows` (Tasks 3–4).
- Produces in `core.py`: `Snapshot.disabled_intervals: frozenset[str] = frozenset()`; `TimerCore.set_interval_enabled(now, interval_id: str, enabled: bool) -> list[Effect]` — records the flag; disabling removes the interval's window (the following `tick` realigns, S2); merges only, like `set_windows`. `set_windows` also prunes `disabled_intervals` to `configured`.
- Produces in `controller.py`: `async def async_set_interval_enabled(self, interval_id: str, enabled: bool) -> None` — under the lock: the core call, then `tick` (disable) or `_refresh_windows()` (enable); raises `timer_unloaded` like `add_command`. `_async_windows` skips disabled intervals. `_refresh_entities` also notifies when `disabled_intervals` changed.
- Produces in `store.py`: key `"disabled_intervals": [sorted ids]` (migrations: `[]`).
- Produces in `entity.py`: `TimerifyEntity.__init__(self, hass, entry, *, unique_id: str | None = None)` (default `f"{entry_id}_{key}"`).
- Produces in `switch.py`: `IntervalSwitch(TimerifyEntity, SwitchEntity)`, `SwitchEntityDescription(key="interval", translation_key="interval")`, `_attr_translation_placeholders = {"interval": subentry.title}`, unique id `f"{entry.entry_id}_interval_{subentry_id}"`, `is_on` = id not in `disabled_intervals`, writes its state only when its own flag changed; `async_setup_entry` adds one per interval subentry with `config_subentry_id=subentry.subentry_id`. `PLATFORMS` gains `Platform.SWITCH`. Name `"Schedule {interval}"` (Russian in `ru.json` with the same blank); icon default `mdi:calendar-check`, state `off` `mdi:calendar-remove`.
- Produces in `tests/helpers.py`: `payload(..., disabled_intervals=())`; `async def set_switch(hass, entity_id, on: bool)`.

- [ ] **Step 1: Write the failing tests**

```python
async def test_each_interval_has_a_switch_on_the_target_device(...)  # "switch.boiler_schedule_06_30_07_15_mon_sun" is "on",
    # registry entry has config_subentry_id == the subentry id and device_id == the boiler's device
async def test_switching_off_skips_the_window_without_a_reload(...)  # controller object unchanged; 06:30 → no call
async def test_switch_state_survives_a_restart(...)                  # saved disabled_intervals == [id]; after restart "off"
async def test_disabling_during_the_window_stops_the_target(...)     # at 07:00 → TURN_OFF (S2)
async def test_disabling_after_a_manual_change_leaves_the_timer(...)  # +30 at 07:10, disable → ends 07:45 (S3)
async def test_enabling_during_the_window_starts_the_target(...)     # disabled before 06:30, enabled 06:45 → TURN_ON, ends 07:15
async def test_deleting_an_interval_removes_its_switch(...)          # async_remove_subentry → no state, no registry entry
async def test_switch_is_written_only_when_toggled(...)              # record_writes(switch) over a window start and end == []; after a toggle == ["off"]
```

`tests/test_core.py`: `test_disabling_the_scheduling_interval_stops_the_timer`, `test_disabled_intervals_are_pruned_to_configured`.

- [ ] **Step 2: Run `uv run pytest tests/test_interval_switch.py tests/test_core.py -v`** — Expected: new tests FAIL.
- [ ] **Step 3: Implement** the flag, the switch platform and the strings.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Add a switch that enables each schedule interval"`

---

### Task 6: Working days and non-working days by a Workday sensor

**Files:**
- Modify: `const.py`, `config_flow.py`, `schedule.py`, `controller.py`, `translations/en.json`, `translations/ru.json`, `pyproject.toml`, `uv.lock`, `tests/conftest.py`, `tests/helpers.py`, `tests/test_config_flow.py`, `tests/test_interval_flow.py`
- Create: `tests/test_workday.py`

**Interfaces:**
- Consumes: `Interval`, `days_around`, `window_on` (Tasks 2, 4), `_async_windows`, `_refresh_windows`, `keep` of `set_windows`.
- Config flow and options flow: a step `workday` with `probatio.Optional(CONF_WORKDAY_SENSOR)` — `EntitySelector(EntitySelectorConfig(domain="binary_sensor", integration="workday"))` — after `duration` (strict) or right after the mode step (loose); it is shown only while the entity registry holds a `binary_sensor` of platform `workday`, or (options) the entry already has one. Options: removing it while an interval uses a Workday mode → error `workday_in_use`.
- Subentry form gains `days` first: `SelectSelector(options=["weekdays", "workdays", "non_workdays"], translation_key="interval_days")`, default `workdays` when the target has a sensor, else `weekdays`; `weekdays` is checked only in `weekdays` mode and stored as `[]` otherwise. Error `needs_workday_sensor` for a Workday mode on a target without one. Titles: `"06:30–07:15, Working days"`, `"08:00–09:00, Non-working days"`.
- Controller: `async def _async_is_workday(self, day: date) -> bool` — `hass.services.async_call("workday", "check_date", {"entity_id": sensor, "check_date": day}, blocking=True, return_response=True)` under `SERVICE_CALL_TIMEOUT`, answer `response[sensor]["workday"]`; any `HomeAssistantError`, timeout or missing key raises a private `_WorkdayUnknown`. `_async_windows` takes the first `window_on` over `days_around` with end after now whose day matches (`True` for `workdays`, `False` for `non_workdays`), asking each day at most once per refresh; an interval whose answer is unknown goes into the returned `unknown` set. One warning per outage: `"Could not ask %s whether %s is a working day (%s); the schedule of %s waits until it reports"`, cleared by the next answer. `async_track_state_change_event` on the sensor → `_refresh_windows()`.
- Test fixtures (conftest): `@dataclass class FakeWorkday: hass; entity_id = "binary_sensor.workday_sensor"; workdays = {"sun","mon","tue","wed","thu"}; holidays: set[date]`; registered as a `binary_sensor` of platform `workday` (registry entry of a `MockConfigEntry(domain="workday")`), state `on`/`off`; `async def set_available(on: bool)`; a `workday.check_date` service (`SupportsResponse.ONLY`) that answers `{entity_id: {"workday": ...}}` and raises `ServiceValidationError` while the sensor is unavailable (as Home Assistant does for an entity service that matches no available entity); `fail_next_call()`. Fixture `fake_workday`; `setup_target(..., workday_sensor: str | None = None)`.
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
async def test_an_unknown_answer_leaves_a_running_window_alone()  # window started, sensor unavailable, edit nothing →
    # realign does not stop it (keep)
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

- [ ] **Step 1: README** — section "Schedules": adding, editing and deleting intervals on the timer's entry; the three day modes and the Workday sensor (where to pick it, what an unavailable sensor does); windows across midnight and on DST days; the switch per interval (and that it does not reload); S1–S5 in plain words (a window extends but never shortens a manual run; edits follow while the schedule set the end; a manual change ends that; a manual off holds until the next window, across restarts; a manual on in strict mode runs the default duration); settings of an interval and when they are applied; restart behaviour.
- [ ] **Step 2: RULINGS.md and followups** — a "Phase 3" part with the plan rulings below; rewrite the phase-2 entries they supersede ("Apply is separate…" now names the stored marker; "The store file is version 2…" → version 3 and its keys; "One alarm sits at `next_wakeup`…" → window starts and ends; "The catch-up folds…" → the tie order). In `docs/followups.md` remove the Phase 3 item (closed by Task 1) and leave the section out.
- [ ] **Step 3: Smoke script** — `add_timer` passes through the `workday` step only when the flow asks for it; new scenario `scenario_schedule`: through `/api/config/config_entries/subentries/flow` add to the input_boolean timer an interval for today's weekday (container time zone) starting at the next whole minute plus one and ending two minutes later; expect the target `on` at the start and `off` at the end (state waits over the WebSocket, as the other scenarios do), and the interval's switch `on`.
- [ ] **Step 4: Run hassfest** — `docker run --rm --platform linux/amd64 -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest` — Expected: no errors (subentry translations, selectors, icons).
- [ ] **Step 5: Run the smoke test** — `uv run python scripts/smoke/run.py` — Expected: every scenario passes.
- [ ] **Step 6: Run all checks on the final tree** — `uv run pytest && uv run ruff check && uv run ruff format --check && uv run mypy` — Expected: all pass; report the test count.
- [ ] **Step 7: Commit** — `git commit -m "Document phase 3 and bump the version to 0.3.0"`

---

## Plan rulings

Decision — why — cost if wrong.

- **Spec conflicts: none.** The design notes' `window_started` / `window_changed` (marked "e.g.") become fold items plus a realign — one wake-up path and no flap after a restart (D4's "one alarm" preferred it) — none.
- **One update listener reloads the entry on any change; `options_flow_reloads = False`; `_follow_target` no longer reloads itself** — in 2026.10.4 a subentry add (`ConfigSubentryFlowManager.async_finish_flow` → `async_add_subentry`) and delete (`async_remove_subentry`) only fire update listeners, `async_update_reload_and_abort` raises with a listener, and `OptionsFlowWithReload` raises with one; Home Assistant's own usage report says to schedule reloads from the listener, as ollama/anthropic do — every interval add/edit/delete reloads the timer (entities re-added, start-up path re-run); tests prove a countdown and commands survive it.
- **Realign (S2) runs at the end of every fold, from the persisted `scheduled_by` and the current windows** — after a reload the edit is visible only as new windows, and realign is idempotent when nothing changed — a timer whose end drifted from its window without an edit is pulled back (only possible after the 24-hour cap, which windows respect).
- **S4 is a persisted `started` mark per occurrence: a window applies S1 once.** It survives edits (an active window of the same interval inherits it) and restarts. So any zeroing during a started window — R3, a stop from the card, the end of a manual run, an off command — keeps the target off until the next window — R8 "manual wins", and restart must behave like no restart — a user who stops the boiler from the card and expects a restart to bring the window back (spec §5.7's literal "apply S1" would).
- **Adding an interval or switching one on during its window starts it for the remainder; switching off and on again forgets S4 for that occurrence** — schedules are declarative and a restart does the same (§5.7) — a surprise turn-on when enabling mid-window.
- **Deleting an interval is disabling it for S2; a realign to "stop" does not hand the timer to an overlapping window that already started** — S2 says stop; the hand-over would need a second mark distinguishing started from suppressed — in the rare overlap the target stays off until the other interval's next window.
- **Tie order in the fold: window ends, window starts, commands, the timer's end** — P3: a command at a window's start is a manual set and wins; a window starting as the timer ends extends it without an off — none.
- **At a window start the interval's settings are owed (turn-on only) only if the target is not running as of that item in the fold** — §5.4's bullet, also when the fold replays several items after a restart — none.
- **Turn-on-only settings are dropped, not applied, when the target is found on without our turn-on list completing** (D6, store key `owed_turn_on_only`) — the target is running by someone else's hand — a schedule's `set_*` call that fails right after its own successful turn-on is not retried.
- **Occurrences are computed ahead, one current-or-next window per enabled interval, in Home Assistant's time zone; a Workday answer is asked when an occurrence is computed, not at its start** — `check_date` answers a date deterministically, and computing ahead keeps the core pure and the alarm single — a Workday configuration changed between computing and the start is noticed only when the sensor reports (it reloads, so it does).
- **An unknown Workday answer (sensor unavailable, call failed) keeps the interval's current window as it is (`keep`) and starts nothing new; one warning per outage; refresh on the sensor's next state change** — D3, event-driven — a window of a sensor that never comes back never starts, with the warning saying why.
- **The search horizon is `WINDOW_SEARCH_DAYS = 14`** — weekday intervals always match within 7 days; a Workday-based one with no match is re-searched when the sensor's state flips (it flips the day a matching day begins) — none found.
- **DST: wall times convert with `fold=0`; an occurrence swallowed by the gap is skipped; windows are capped at `MAX_MINUTES`** — zoneinfo's own rule, no private HA helpers — a 02:30–03:15 interval does not run on the spring-forward day.
- **The interval form refuses seconds (`whole_minutes_only`) and stores `"HH:MM"`** — values are never silently dropped — none.
- **Titles are generated in Home Assistant's configured language from the selector labels; a title the user renamed survives edits** — subentry titles are plain strings — a title stays in the language of its creation.
- **The enable flag is `Snapshot.disabled_intervals` in the timer's store, enabled by default** — one store, one save path, a toggle never reloads (D2) — none.
- **The switch is named `"Schedule {interval}"` with the subentry title** — the title identifies the interval and follows edits after the reload — entity ids keep the first title.
- **The Workday step appears only when a Workday sensor exists (or is set, in options)** — §6.2's "three clicks for the common case"; D3's order otherwise kept — a user who adds a Workday sensor later picks it in the options.
- **Store version 3 gets its keys over Tasks 1, 4 and 5 without further versions** — 0.3.0 is unreleased between them; strict reads stay — a v3 file from a development build between those tasks fails to load (developer machines only).
- **`holidays==0.106` joins the dev group for one contract test with the real Workday integration; scenarios use `FakeWorkday`** — the real test pins the response shape and the Israeli week, the fake controls holidays and outages — a dev dependency to bump with Home Assistant.
- **A loose open run is cut at a window's end when the window starts during it** — S1 sets the timer, and a timer above zero means "off at zero" in loose mode — loose users may expect the run to continue.
- **The smoke interval uses days of the week, not a Workday sensor** — the container's date is not under the script's control — the real `check_date` is proven by the pytest contract test, not in the container.

---

## Appendix: pre-flight (shared files and interfaces; gate after each task)

| Pair | Shared | Conflict and resolution | Gate green after the later task |
|---|---|---|---|
| T1 → T3 | `core.py` `_owe(turn_on_only)`, `owed_turn_on_only`; `test_core.py` | T3's S1 uses T1's marker; no signature change | yes |
| T1 → T4, T5 | `store.py` v3 payload and both migration branches; `helpers.payload` | each adds keys with defaults to payload, migration and `payload()`; every `saved == payload(...)` goes through the helper | yes |
| T2 → T4 | `schedule.Interval`, subentry data keys, `add_interval`/`edit_interval` | T4 consumes, no change | yes |
| T2 → T5 | the reload on subentry delete removes the switch (registry clear) | T5 only adds the platform | yes |
| T2 → T6 | `IntervalSubentryFlow` form, `interval_title` labels, `test_interval_flow.py` | T6 adds `days` before `weekdays`; T2 already stores `"days": "weekdays"`, so data stays compatible; `add_interval(days=...)` gains the parameter in T6 | yes |
| T2 → T6 | `config_flow.py` step chain (`_after_mode`), `test_config_flow.add_target` | T6's `workday` step is skipped without a Workday sensor, so existing flow tests and the smoke `add_timer` keep their steps | yes |
| T3 → T4 | `set_windows(..., configured, keep)`, `tick`, `next_wakeup` | defined complete in T3 so T4 needs no signature change; T4 calls `set_windows` before `observe` at start-up | yes |
| T3 → T5 | `set_windows` prunes `disabled_intervals` | T5 extends the body only, not the signature | yes |
| T4 → T5 | `controller._async_windows`, `_refresh_windows`, `_refresh_entities` | T5 adds the disabled filter and the notify condition | yes |
| T4 → T6 | `_async_windows` returns `(windows, unknown)` from T4 on | T6 fills `unknown`; no caller changes | yes |
| T4 → T7 | `restart` moved to `tests/helpers.py` | T4 moves it and updates `test_restart.py` imports in the same task | yes |
| T5 → T7 | `PLATFORMS`, smoke expects the interval switch | the smoke reads the switch by unique id `"{entry_id}_interval_{subentry_id}"` | yes |
| T6 → T7 | `pyproject.toml` (dev deps, version) | T7 edits only `version` | yes |
| all | `translations/en.json` + `ru.json`, `test_translations.py` (same keys and blanks in every language) | every task adds its keys to both files | yes |

No task adds an `Effect` type (window starts reuse `TurnOn`/`TurnOff`/`Arm`), renames a public method, or leaves a caller of a changed signature; each new core method is called by the controller in the task that needs it or, in Task 3, only by `test_core.py`.
