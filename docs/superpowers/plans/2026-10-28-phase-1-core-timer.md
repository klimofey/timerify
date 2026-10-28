# Timerify Phase 1 — Core Timer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Attach a working per-target timer to any on/off entity: a "Run for" number and an "Ends at" sensor on the target's device, rules R1–R10, persistence and restart reconciliation, add-time/run services, UI setup.

**Architecture:** A pure, Home-Assistant-free state machine (`core.py`) decides everything and returns effects; a thin controller (`controller.py`) feeds it events (commands, target state changes, alarms), executes its effects (service calls with Timerify's own `Context`, alarms, persistence) and notifies entities. One config entry per target; state persisted per entry in a versioned `Store`.

**Tech Stack:** Python 3.14, Home Assistant 2026.10.4, pytest-homeassistant-custom-component 0.13.375 (includes `freezer`, `hass_storage`, `async_fire_time_changed`), ruff, mypy, uv.

**Spec:** `docs/superpowers/specs/2026-10-28-timerify-design.md` — this plan covers phase 1 of §7 (rules §5.1–5.3, §5.7, entities §6.1 `number`/`sensor` "Ends at", setup §6.2 "Add target" without runtime counter and Workday sensor). Settings (§5.4), pending commands, schedules, voice, card and runtime counter are later plans.

## Global Constraints

- Home Assistant `>= 2026.10.0` (`hacs.json`), Python `>= 3.14.2`; `pytest-homeassistant-custom-component==0.13.375`.
- Only public HA mechanisms; attach to the target's device by `entity.device_entry = async_entity_id_to_device(hass, target)`, never by copying identifiers.
- UI configuration only (no YAML); `CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)`.
- All user-facing strings via translations; ship `en` and `ru`.
- Precise remaining time is published only as the "Ends at" timestamp; minute-valued state updates at most once a minute; no other periodic writes.
- No `asyncio.sleep`, no polling loops; startup and availability are event-driven.
- Persist on every change with `Store.async_save` (not `RestoreEntity`, not delayed saves).
- Repository English-only, no AI attribution (hooks enforce); MIT; no code copied from GPL projects.
- Every task ends with `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` all passing.

## Review Focus

1. **Wi-Fi drop around expiry:** target `unavailable` when the timer expires → turned off as soon as it reports again (Task 2 `test_expiry_while_unavailable_turns_off_when_back`, Task 6 scenario).
2. **Service call fails** (device rejects `turn_on`, `HomeAssistantError`): timer stays set, warning logged, the command is retried when the target next reports a state; no crash (Task 4 `test_failed_turn_on_is_retried`).
3. **Slider dragged quickly** (several `number.set_value` in a row): exactly one `turn_on` call (Task 2 `test_repeated_set_while_turning_on_emits_one_turn_on`).
4. **Target renamed** while a timer runs: the timer keeps running and turns off the renamed entity (Task 7 `test_target_rename_keeps_timer`).
5. **DST change** during a countdown (`Asia/Jerusalem`): expiry happens after the real elapsed duration (Task 4 `test_timer_across_dst_change`).

---

## File Structure

```
custom_components/timerify/
  __init__.py        entry setup/unload/remove, source-entity tracking, CONFIG_SCHEMA, service registration call
  const.py           DOMAIN, option keys, mode values, limits
  domains.py         per-domain "is on" + turn on/off table
  core.py            pure state machine: Snapshot, Effect types, TimerCore
  store.py           TimerStore: versioned per-entry persistence of Snapshot
  controller.py      TargetController: HA glue around TimerCore
  entity.py          TimerifyEntity base: device attachment, listener wiring
  number.py          RunForNumber
  sensor.py          EndsAtSensor
  services.py        add_time / run entity services
  config_flow.py     config + options flow (SchemaConfigFlowHandler)
  services.yaml, icons.json, translations/en.json, translations/ru.json
tests/
  conftest.py        fake target fixture (registry entry + device + controllable state + recorded service calls)
  test_domains.py  test_core.py  test_config_flow.py  test_entities.py
  test_restart.py  test_services.py  test_source_changes.py
```

`translations/en.json` is the single source of strings (custom integrations load `translations/`, not `strings.json`).

---

### Task 1: Domain table and tooling

**Files:**
- Create: `custom_components/timerify/domains.py`, `tests/test_domains.py`
- Modify: `pyproject.toml` (add `mypy` to dev group, `[tool.mypy]` strict for `custom_components`), `CLAUDE.md` (Commands: add `uv run mypy`; HA conventions: `translations/en.json` is the strings source, not `strings.json`)

**Interfaces:**
- Produces:
  - `Actual = Literal["on", "off", "unavailable"]`
  - `@dataclass(frozen=True) class DomainBehaviour: on_service: tuple[str, str]; off_service: tuple[str, str]; is_on: Callable[[State], bool]`
  - `SUPPORTED_DOMAINS: Final[tuple[str, ...]]`
  - `def behaviour_for(entity_id: str) -> DomainBehaviour` (raises `ValueError` for unsupported domains)
  - `def actual_state(state: State | None) -> Actual` (`None`, `unavailable`, `unknown` → `"unavailable"`)

Table (simple rows use state `"on"`): `switch`, `input_boolean`, `light`, `fan`, `humidifier`, `siren`, `remote`, `group`; special rows: `climate` (on ⇔ state != `off`; `climate.turn_on`/`turn_off`), `water_heater` (on ⇔ state != `off`; `water_heater.turn_on`/`turn_off`), `media_player` (on ⇔ state not in `off`, `standby`; `media_player.turn_on`/`turn_off`).

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize(("entity_id", "state", "expected"), [
    ("switch.boiler", "on", "on"), ("switch.boiler", "off", "off"),
    ("climate.ac", "cool", "on"), ("climate.ac", "off", "off"),
    ("media_player.tv", "standby", "off"), ("media_player.tv", "playing", "on"),
    ("water_heater.tank", "eco", "on"),
    ("switch.boiler", "unavailable", "unavailable"), ("switch.boiler", "unknown", "unavailable"),
])
def test_actual_state(entity_id, state, expected): ...
def test_actual_state_of_missing_entity_is_unavailable(): assert actual_state(None) == "unavailable"
def test_services_per_domain(): assert behaviour_for("climate.ac").on_service == ("climate", "turn_on")
def test_unsupported_domain_raises(): with pytest.raises(ValueError): behaviour_for("sensor.temp")
```

- [ ] **Step 2: Run `uv run pytest tests/test_domains.py -v`** — Expected: FAIL (module missing).
- [ ] **Step 3: Implement `domains.py`** per the Interfaces block; add mypy config (`strict = true`, `files = ["custom_components"]`).
- [ ] **Step 4: Run `uv run pytest tests/test_domains.py -v && uv run mypy`** — Expected: PASS, `Success: no issues found`.
- [ ] **Step 5: Commit** — `git commit -m "Add per-domain on/off behaviour table"`

---

### Task 2: Core state machine — commands and expiry

**Files:**
- Create: `custom_components/timerify/core.py`, `tests/test_core.py`
- Modify: `custom_components/timerify/const.py` (add `Mode = Literal["strict", "loose"]`)

**Interfaces:**
- Consumes: `Actual` (Task 1).
- Produces:
  - `@dataclass(frozen=True) class Snapshot: end: datetime | None = None; pending: Literal["on", "off"] | None = None; last_actual: Actual | None = None` — `end` is timezone-aware UTC.
  - Effects: `TurnOn()`, `TurnOff()`, `Arm(at: datetime)`, `Disarm()`, `Changed()` (frozen dataclasses; `type Effect = TurnOn | TurnOff | Arm | Disarm | Changed`).
  - `class TimerCore(mode: Mode, default_duration: timedelta, snapshot: Snapshot)` with `snapshot` property and methods, each `(now: datetime, ...) -> list[Effect]`:
    `set_duration(now, duration: timedelta)`, `add(now, delta: timedelta)`, `stop(now)`, `run_open(now)`, `expire(now)`.
  - `def remaining_minutes(snapshot: Snapshot, now: datetime) -> int` — `ceil((end - now) / 1 min)`, `0` when idle or past.

Rules this task pins (spec R1, R2, R7, R9). Both turning directions go through one private
algorithm, because a command can arrive while the opposite service call is still in flight:

```python
def _want(self, target: Literal["on", "off"]) -> list[Effect]:
    if self._pending == target:
        return []                                  # already on its way
    if self._pending is None and self._last_actual == target:
        return []                                  # already there
    self._pending = target                         # replaces an opposite in-flight wish
    if self._last_actual == "unavailable":
        return []                                  # applied when the target is back (R10)
    return [TurnOn() if target == "on" else TurnOff()]
```

- `set_duration(d > 0)`: `end = now + d`; `Arm(end)`; `_want("on")`. `set_duration(0)` ≡ `stop`.
- `stop`: `end = None`, `Disarm()`; `_want("off")`.
- `add`: idle + positive delta ≡ `set_duration(delta)`; idle + non-positive → `[]`; running → `end + delta`, which at or before `now` ≡ `stop`.
- `run_open`: strict ≡ `set_duration(default_duration)`; loose → `end = None`, `Disarm()`, `_want("on")`.
- `expire(now)`: if `end` and `end <= now` ≡ `stop`; otherwise `[]` (stale alarm).
- Every method that changes the snapshot appends `Changed()`; no change → no `Changed()`.

- [ ] **Step 1: Write the failing tests** (use `NOW = datetime(2026, 1, 5, 7, 0, tzinfo=UTC)`, `core(mode, actual)` helper building `TimerCore(mode, timedelta(minutes=45), Snapshot(last_actual=actual))`)

```python
def test_set_duration_on_off_target_turns_on_and_arms():
    c = core("strict", "off"); fx = c.set_duration(NOW, timedelta(minutes=45))
    assert fx == [Arm(NOW + timedelta(minutes=45)), TurnOn(), Changed()]
    assert c.snapshot.end == NOW + timedelta(minutes=45) and c.snapshot.pending == "on"
def test_set_duration_on_running_target_only_rearms(): # last_actual "on" → [Arm(...), Changed()], pending None
def test_set_zero_stops_and_turns_off():                # running, "on" → [Disarm(), TurnOff(), Changed()], end None
def test_add_extends_running_timer():                   # end 07:05, add 30 → end 07:35
def test_add_below_now_stops():                         # end 07:05, add -10 → stop effects
def test_add_on_idle_starts_timer():                    # idle, add 30 → same as set_duration(30)
def test_add_negative_on_idle_does_nothing():           # → [] and snapshot unchanged
def test_run_open_strict_uses_default_duration():       # end == NOW + 45 min
def test_run_open_loose_turns_on_without_countdown():   # end None, [Disarm(), TurnOn(), Changed()]
def test_expire_at_end_turns_off():                     # end == NOW → TurnOff
def test_stale_expire_is_ignored():                     # end NOW+5 → []
def test_repeated_set_while_turning_on_emits_one_turn_on():
    c = core("strict", "off"); c.set_duration(NOW, timedelta(minutes=10))
    assert TurnOn() not in c.set_duration(NOW, timedelta(minutes=20))
def test_stop_while_turn_on_in_flight_turns_off():
    c = core("strict", "off"); c.set_duration(NOW, timedelta(minutes=10))
    assert TurnOff() in c.stop(NOW) and c.snapshot.pending == "off"
def test_set_while_turn_off_in_flight_turns_on():
    c = core("strict", "on"); c.set_duration(NOW, timedelta(minutes=10)); c.stop(NOW)
    assert TurnOn() in c.set_duration(NOW, timedelta(minutes=5)) and c.snapshot.pending == "on"
def test_set_while_unavailable_records_pending_without_service_call():
    c = core("strict", "unavailable"); fx = c.set_duration(NOW, timedelta(minutes=10))
    assert TurnOn() not in fx and c.snapshot.pending == "on"
def test_remaining_minutes_rounds_up():                 # end NOW+61s → 2; NOW+60s → 1; idle → 0; past → 0
```

- [ ] **Step 2: Run `uv run pytest tests/test_core.py -v`** — Expected: FAIL (module missing).
- [ ] **Step 3: Implement `core.py`** — `TimerCore` holds a mutable copy and rebuilds the frozen `Snapshot` via `dataclasses.replace`; no Home Assistant imports.
- [ ] **Step 4: Run `uv run pytest tests/test_core.py -v`** — Expected: PASS.
- [ ] **Step 5: Commit** — `git commit -m "Add timer core: commands and expiry"`

---

### Task 3: Core state machine — observing the target

**Files:**
- Modify: `custom_components/timerify/core.py`, `tests/test_core.py`

**Interfaces:**
- Produces: `TimerCore.observe(now: datetime, actual: Actual, *, by_us: bool) -> list[Effect]` — called on every target state change and once at startup (with the stored `last_actual`, or `None` on first start).

Rules (spec R3–R6, R10, §5.7):
1. Always first: `expire(now)` semantics if `end <= now`.
2. `actual == "unavailable"` → record `last_actual`, nothing else.
3. **Came back** (`last_actual` is `None` or `"unavailable"`):
   - `pending` set and differs from `actual` → `TurnOn()`/`TurnOff()` (enforce; R10);
   - `pending` equals `actual` → clear it;
   - no `pending`: disagreement handled as an external change (rule 5).
4. **Own change** (`by_us`): clear `pending` if it now matches.
5. **External change** (not `by_us`, value changed): clear `pending`; `actual == "off"` and `end` set → `end = None`, `Disarm()` (R3); strict, `actual == "on"`, no `end` → `end = now + default`, `Arm` (R4); loose `"on"` → nothing (R5).
6. Record `last_actual`; append `Changed()` iff the snapshot changed.

- [ ] **Step 1: Write the failing tests**

```python
def test_manual_off_clears_timer():                    # running "on", observe "off" by_us=False → end None, [Disarm(), Changed()]
def test_manual_on_in_strict_starts_default_duration(): # idle "off", observe "on" → end NOW+45, Arm
def test_manual_on_in_loose_leaves_timer_idle():        # → end None, only Changed() (last_actual)
def test_own_turn_on_clears_pending():                  # pending "on", observe "on" by_us=True → pending None, no Arm
def test_expiry_while_unavailable_turns_off_when_back():
    c = TimerCore("strict", timedelta(minutes=45), Snapshot(end=NOW, last_actual="unavailable"))
    assert TurnOff() in c.observe(NOW + timedelta(minutes=3), "on", by_us=False)
def test_set_while_unavailable_turns_on_when_back():   # pending "on", unavailable → observe "off" → TurnOn()
def test_wifi_drop_does_not_clear_timer():             # running "on", observe "unavailable" → end unchanged
def test_startup_with_running_timer_and_target_on_rearms_nothing_else():  # last_actual None, "on", end future → no TurnOn/TurnOff
def test_startup_target_off_with_running_timer_clears_it():   # §5.7 + R3
def test_startup_after_expiry_turns_off():             # end in the past, "on" → TurnOff()
```

- [ ] **Step 2: Run `uv run pytest tests/test_core.py -v`** — Expected: new tests FAIL.
- [ ] **Step 3: Implement `observe`** following rules 1–6 in order.
- [ ] **Step 4: Run `uv run pytest tests/test_core.py -v`** — Expected: PASS.
- [ ] **Step 5: Commit** — `git commit -m "Add timer core: target observation and reconciliation"`

---

### Task 4: Controller, store, entry setup and the "Run for" number

**Files:**
- Create: `store.py`, `controller.py`, `entity.py`, `number.py`, `tests/conftest.py` (rewrite), `tests/test_entities.py`
- Modify: `__init__.py`, `const.py`, `translations/en.json`, `translations/ru.json` (entity names), `icons.json`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces:
  - `const.py`: `CONF_TARGET = "target"`, `CONF_MODE = "mode"`, `CONF_DEFAULT_DURATION = "default_duration"` (minutes, int), `MAX_MINUTES = 1440`, `DEFAULT_DURATION_MINUTES = 30`.
  - `type TimerifyConfigEntry = ConfigEntry[TargetController]`; options hold `target` (entity id or registry UUID), `mode`, `default_duration`.
  - `class TimerStore(hass, entry_id)`: `STORAGE_VERSION = 1`, key `f"timerify.{entry_id}"`; `async_load() -> Snapshot`, `async_save(snapshot) -> None`, `async_remove() -> None`. Datetimes stored as ISO-8601 UTC strings.
  - `class TargetController(hass, entry, store, snapshot)`:
    `target_entity_id: str` (resolved via `er.async_validate_entity_id`), `snapshot: Snapshot`,
    `async_start() -> None`, `async_set_minutes(minutes: int)`, `async_add_minutes(minutes: int)`, `async_run()`,
    `async_add_listener(cb: Callable[[], None]) -> CALLBACK_TYPE`.
  - `class TimerifyEntity(Entity)`: `_attr_has_entity_name = True`; unique id `f"{entry.entry_id}_{key}"`; sets `device_entry` (fallback device in Task 5).
  - `class RunForNumber(TimerifyEntity, NumberEntity)`: key/translation key `run_for`, min 0, max `MAX_MINUTES`, step 1, unit `min`, `NumberMode.SLIDER`; `native_value = remaining_minutes(...)`; `async_set_native_value(v)` → `async_set_minutes(int(v))`.

Controller behaviour:
- `async_start`: subscribe with `async_track_state_change_event` on the target; on `async_at_started` call `observe(now, actual_state(state), by_us=False)` once; `by_us` for later events is `event.context.id in self._own_context_ids`.
- Effects: `TurnOn`/`TurnOff` → `hass.services.async_call(domain, service, {"entity_id": target}, blocking=True, context=Context())`, recording the context id first; on `HomeAssistantError` log a warning and leave `pending` set (the next `observe` retries it). `Arm(at)` → replace the single `async_track_point_in_utc_time` alarm that calls `expire`; `Disarm` cancels it. `Changed` → `await store.async_save(snapshot)`, schedule the minute refresh, notify listeners.
- Minute refresh: while `end` is set, one alarm at `end - (remaining_minutes(snapshot, now) - 1) minutes` (the instant the rounded-up value changes) that notifies listeners and re-schedules itself.
- All core calls and effect execution run under one `asyncio.Lock`, so commands, state events and alarms are applied strictly one after another.
- All alarms and listeners released through `entry.async_on_unload`.

Test fixture `fake_target` (conftest): creates a device and a registry entry `switch.boiler` on it, sets state `off`, registers fake `switch.turn_on`/`turn_off` handlers that record calls and set the state with `context=call.context`, exposes `set_state(value)` for external changes and `fail_next_call()`; plus `setup_target(mode="strict", default_duration=45)` creating and loading a `MockConfigEntry`.

- [ ] **Step 1: Write the failing scenario tests** (time moved with `freezer.tick` + `async_fire_time_changed`)

```python
async def test_setting_run_for_turns_target_on(hass, fake_target, setup_target):
    await setup_target(); await set_number(hass, "number.boiler_run_for", 45)
    assert fake_target.calls == [("turn_on", "switch.boiler")]
    assert hass.states.get("number.boiler_run_for").state == "45"
async def test_timer_expiry_turns_target_off(...):        # 45 min later → turn_off called, number "0"
async def test_number_counts_down_once_a_minute(...):     # after 61 s → "44"; state writes between ticks: none
async def test_setting_zero_turns_target_off(...)
async def test_manual_off_resets_run_for_to_zero(...):    # fake_target.set_state("off") → number "0", no service calls
async def test_manual_on_in_strict_runs_default_duration(...)  # set_state("on") → number "45"
async def test_manual_on_in_loose_keeps_zero(...)
async def test_failed_turn_on_is_retried(...):            # fail_next_call(); set 10 → warning in caplog, number "10";
                                                          # set_state("unavailable"); set_state("off") → turn_on called again
async def test_timer_across_dst_change(hass, freezer, ...):  # hass tz Asia/Jerusalem; start 30 min at 2026-10-25 01:45 local
                                                          # (DST ends 02:00); turn_off exactly 30 real minutes later
async def test_entities_attach_to_target_device(...):     # entity registry device_id of number == boiler device id; no new device
```

- [ ] **Step 2: Run `uv run pytest tests/test_entities.py -v`** — Expected: FAIL.
- [ ] **Step 3: Implement** `store.py`, `controller.py`, `entity.py`, `number.py`, `__init__.py` (`async_setup_entry` builds store → snapshot → controller, `entry.runtime_data = controller`, forwards `Platform.NUMBER`, starts controller; `async_unload_entry`); entity names in `en.json`/`ru.json`; icon `mdi:timer-outline`.
- [ ] **Step 4: Run all checks** — `uv run pytest && uv run ruff check && uv run ruff format --check && uv run mypy` — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Add timer controller, storage and Run for number"`

---

### Task 5: "Ends at" sensor and fallback device

**Files:**
- Create: `custom_components/timerify/sensor.py`; Modify: `entity.py`, `__init__.py` (forward `Platform.SENSOR`), translations, `icons.json`, `tests/test_entities.py`

**Interfaces:**
- Consumes: `TimerifyEntity`, `TargetController` (Task 4).
- Produces: `class EndsAtSensor(TimerifyEntity, SensorEntity)`: key `ends_at`, `SensorDeviceClass.TIMESTAMP`, `native_value = snapshot.end` (or `None`). Fallback in `TimerifyEntity`: when `async_entity_id_to_device` returns `None`, `device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=<target friendly name>)`.

- [ ] **Step 1: Write the failing tests**

```python
async def test_ends_at_shows_end_time_and_clears(...):   # set 45 at 07:00 UTC → state "2026-01-05T07:45:00+00:00"; stop → "unknown"
async def test_ends_at_is_not_rewritten_while_running(...):  # count state_changed events for the sensor across 10 min: 0
async def test_target_without_device_gets_own_device(...):   # target registered with no device → one Timerify device named after it, both entities on it
```

- [ ] **Step 2: Run `uv run pytest tests/test_entities.py -v`** — Expected: new tests FAIL.
- [ ] **Step 3: Implement** the sensor (listener writes state only when `end` changes) and the fallback device.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Add Ends at sensor and fallback device"`

---

### Task 6: Restarts and persistence

**Files:**
- Create: `tests/test_restart.py`; Modify: `controller.py`/`store.py` only if tests expose gaps

**Interfaces:**
- Consumes: `TimerStore` format (Task 4). Restart is simulated by pre-filling `hass_storage[f"timerify.{entry_id}"]` (version 1) before setting up the entry, and by unloading/reloading the entry.

- [ ] **Step 1: Write the failing tests**

```python
async def test_running_timer_survives_reload(...):        # set 45, reload entry at +10 min → number "35", turn_off at +45
async def test_timer_expired_during_downtime_turns_off_on_start(...):  # stored end in the past, target "on" → turn_off once after start
async def test_target_off_at_start_clears_stored_timer(...)            # stored end future, target "off" → number "0", no calls
async def test_target_unavailable_at_start_waits_for_it(...):  # stored end past, target "unavailable" → no call; set_state("on") → turn_off
async def test_state_is_saved_on_every_change(...):       # after set 45: hass_storage key holds end ISO string; after stop: end null
async def test_expiry_while_unavailable_turns_off_when_back(...)  # Review Focus 1, full HA path
```

- [ ] **Step 2: Run `uv run pytest tests/test_restart.py -v`** — Expected: any gap FAILS (fix in Step 3).
- [ ] **Step 3: Fix gaps** in `controller.py`/`store.py`.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Cover restarts and persistence"`

---

### Task 7: Config flow, options flow, source-entity changes, removal

**Files:**
- Create: `config_flow.py`, `tests/test_config_flow.py`, `tests/test_source_changes.py`
- Modify: `manifest.json` (`"config_flow": true`), `__init__.py` (`async_handle_source_entity_changes`, `async_remove_entry`), `translations/en.json`, `translations/ru.json`, `.githooks/pre-commit`, `CLAUDE.md` (rule 1)

**Interfaces:**
- Consumes: `CONF_*`, `SUPPORTED_DOMAINS`, `TimerStore.async_remove`.
- Produces: `class TimerifyConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN)` with `options_flow`; `async_config_entry_title` returns the target's friendly name.

Flow (spec §6.2, "three clicks"):
- Step `user`: `target` (`EntitySelector`, domains `SUPPORTED_DOMAINS`) + `mode` (`SelectSelector`, options `strict`/`loose`, translated, default `strict`). Abort `already_configured` when the target already has an entry (unique id = target registry UUID, or entity id when unregistered).
- Step `duration` (only when `mode == "strict"`): `default_duration` (`NumberSelector` minutes 1–`MAX_MINUTES`, default `DEFAULT_DURATION_MINUTES`).
- Options flow: `mode` and `default_duration`; saving reloads the entry (state survives via the store).
- Source changes like core helpers (`homeassistant/components/derivative/__init__.py`): rename → update `target` option and reload; removal of the target → remove the entry's entities' device link per the helper's default.
- `async_remove_entry` → `TimerStore(hass, entry.entry_id).async_remove()`.
- Pre-commit hook: additionally allow Cyrillic in `custom_components/timerify/translations/*.json` except `en.json`, and in `custom_components/timerify/sentences/*/` except `sentences/en/` (localized product content). Update CLAUDE.md rule 1 to say exactly this.

- [ ] **Step 1: Write the failing tests**

```python
async def test_add_strict_target_in_two_steps(hass, fake_target):   # user → duration → entry with options {target, mode: strict, default_duration: 45}, title "Boiler"
async def test_add_loose_target_skips_duration(...)                 # user → create_entry directly
async def test_same_target_twice_aborts(...)                        # reason "already_configured"
async def test_options_change_mode_keeps_running_timer(...)         # timer 30 running, switch to loose → number still counts down
async def test_target_rename_keeps_timer(...)                       # rename switch.boiler → switch.water_heater mid-countdown → turn_off on the new id at expiry
async def test_removing_entry_deletes_stored_state(...)             # hass_storage key gone
```

- [ ] **Step 2: Run `uv run pytest tests/test_config_flow.py tests/test_source_changes.py -v`** — Expected: FAIL.
- [ ] **Step 3: Implement** flow, translations (`en`, `ru`), source tracking, removal, hook and CLAUDE.md change; verify the hook with one staged Cyrillic file outside the allowlist (rejected) and `translations/ru.json` (accepted).
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Add setup and options flows with source tracking"`

---

### Task 8: Add-time and run services

**Files:**
- Create: `services.py`, `services.yaml`, `tests/test_services.py`; Modify: `__init__.py` (`async_setup` registers services, `CONFIG_SCHEMA`), `number.py`, translations, `icons.json`

**Interfaces:**
- Consumes: `TargetController.async_add_minutes`, `async_run`.
- Produces: services registered in `async_setup` with `async_register_platform_entity_service(hass, DOMAIN, ..., entity_domain="number", ...)`, targeting Timerify "Run for" numbers:
  - `timerify.add_time` — `minutes: int` in `[-MAX_MINUTES, MAX_MINUTES]`, func `async_add_time`.
  - `timerify.run` — no fields; func `async_run` (strict: default duration; loose: on without countdown).

- [ ] **Step 1: Write the failing tests**

```python
async def test_add_time_extends_running_timer(...)      # 07:10 with 5 left, add 30 → ends_at 07:45 (spec R7 example)
async def test_add_time_on_idle_target_starts_it(...)
async def test_negative_add_time_to_zero_turns_off(...)
async def test_run_strict_uses_default_duration(...)    # number "45", turn_on
async def test_run_loose_turns_on_without_countdown(...) # number "0", turn_on, ends_at "unknown"
```

- [ ] **Step 2: Run `uv run pytest tests/test_services.py -v`** — Expected: FAIL.
- [ ] **Step 3: Implement** services, `services.yaml`, translated service names/descriptions, service icons.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Add add_time and run services"`

---

### Task 9: Phase verification and docs

**Files:**
- Modify: `README.md` (what phase 1 does, installation via HACS custom repository, setup steps, services), `custom_components/timerify/manifest.json` (`"version": "0.1.0"`), `pyproject.toml` version

- [ ] **Step 1: Run hassfest locally** — `docker run --rm -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest` — Expected: no errors.
- [ ] **Step 2: Run all checks on the final tree** — `uv run pytest && uv run ruff check && uv run ruff format --check && uv run mypy` — Expected: all pass; record the test count.
- [ ] **Step 3: Manual smoke test in a real HA 2026.10 container** (`docker run -v ./config:/config -v ./custom_components:/config/custom_components ghcr.io/home-assistant/home-assistant:2026.10.4`): add a template/virtual switch, add it in Timerify, set 2 minutes, watch it turn off; restart the container mid-countdown and confirm the off still happens. Capture screenshots of the device page.
- [ ] **Step 4: Update README** with what was verified.
- [ ] **Step 5: Commit** — `git commit -m "Document phase 1 and bump version to 0.1.0"`
