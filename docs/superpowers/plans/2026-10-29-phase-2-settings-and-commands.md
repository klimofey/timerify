# Timerify Phase 2 — Settings and Pending Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Commands that turn a target on can carry device settings ("cooling, 24°"), and commands can be scheduled for later ("in 15 minutes for an hour"), listed on a "Next command" sensor and cancelled, surviving restarts and outages.

**Architecture:** The pure core (`core.py`) grows two things: owed settings (asked for, not yet confirmed applied; sent with `TurnOn` or as a new `ApplySettings` effect, retried like an on/off wish and within the same limit of automatic re-sends) and an ordered tuple of pending commands executed by a single `tick` at the next wake-up (the earlier of the timer's end and the first command). `domains.py` gains a generic fallback row, per-row turn-on features, per-row limits of automatic re-sends and per-row settings (validation against the target's capabilities, and the service calls that apply them). The controller turns effects into call lists, reports success or failure back, and exposes `run` (now with minutes and settings), `add_command` and `cancel_command`; storage goes to version 2 with a migration. Each task is a vertical slice: an effect lands together with the controller code that carries it out and the scenario tests that prove it, so every commit passes all four checks.

**Tech Stack:** Python 3.14, Home Assistant 2026.10.4 (`probatio` schemas), pytest-homeassistant-custom-component 0.13.375 (`freezer`, `hass_storage`, `async_fire_time_changed`, `recorder_mock`), ruff, mypy, uv.

**Spec:** `docs/superpowers/specs/2026-10-28-timerify-design.md` — this plan covers phase 2 of §7: settings (§5.4), pending commands (§5.6, P1–P3, their part of §5.7 and R10) and the "Next command" sensor of §6.1. Controller decisions: `.superpowers/phase-2-design-notes.md` (D1–D9). Pre-flight scan: `.superpowers/sdd/2026-10-29-phase-2-settings-and-commands/preflight.md` (F1–F34, folded in below). Schedules, voice, card and runtime counter are later plans.

**Starting point:** the phase-1 fix wave has landed: `target_name` lives in `custom_components/timerify/target.py`; `controller._switch` reports a call that returns without error but leaves the target in the wrong state through `core.call_failed`; `FakeTarget` has `ignore_next_call()` and `fail_next_call(error=...)`. Also on main since this plan was drafted: automatic re-sends of an unsent wish on reports that repeat the target's state are capped at `const.MAX_AUTOMATIC_RESENDS` (3) per wish, counted in `TimerCore` and reset by a new wish, a state change, the target coming back or a command; the core emits a `GaveUp(wish)` effect the controller logs once; `Changed` is handled (saved and shown) ahead of the other effects of a batch; `TARGET_ID` and `storage_key(entry)` live in `tests/helpers.py`. Shared test helpers still live in test modules: `call_service` in `tests/test_services.py`, `at`/`saved`/`restart` in `tests/test_restart.py`, `record_writes` in `tests/test_entities.py`. The controller notifies the entities only when `end` changes (`_refresh_entities`), and `_execute` ends in `assert_never`, so every new effect needs its controller arm in the same task. Build on that shape; if it differs, adapt names, not behaviour.

## Global Constraints

- Home Assistant `>= 2026.10.0` (`hacs.json`), Python `>= 3.14.2`; `pytest-homeassistant-custom-component==0.13.375`.
- Only public HA mechanisms; schemas with `probatio` (as `services.py` does), never `voluptuous`. Import HA names from the module that defines them (`homeassistant.components.<domain>.const`, `homeassistant.components.light.helper`): mypy strict rejects package-level re-exports.
- All user-facing strings via `translations/en.json` (source) and `translations/ru.json`; every new key exists in both. Service errors are `ServiceValidationError(translation_domain=DOMAIN, translation_key=..., translation_placeholders=...)` with the message under `exceptions` in both files.
- Precise times only as timestamps; minute-valued state at most once a minute; the "Next command" sensor is written only when the command list changes.
- No `asyncio.sleep`, no polling; tests freeze time and move it with `freezer.tick` + `async_fire_time_changed` (helper `advance`); no test backdoors — tests act through services, entities and `FakeTarget`. Shared helpers live in `tests/helpers.py`, never imported from another test module.
- Persist on every change with `Store.async_save`; storage version 2.
- Limits (D5/D6): at most `MAX_COMMANDS = 20` commands per target; `at` strictly in the future and at most `MAX_COMMAND_AHEAD = timedelta(days=7)` ahead; `delay` 1..`MAX_DELAY_MINUTES = 10080`; `minutes` 1..`MAX_MINUTES` (1440).
- Settings are an immutable mapping (`MappingProxyType`) `name -> str | float | int`, converted with `dict(...)` at every boundary (store, sensor attribute, service data); validated when a command is created, not when it runs.
- Repository English-only (Cyrillic only in `translations/ru.json`), no AI attribution in commits (hooks enforce).
- Every task ends with `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` all passing.

## Review Focus

1. **`at` without a time zone** (the UI datetime picker sends `"2026-01-05 09:30:00"`): it is Home Assistant's local time, not UTC (Task 4 `test_command_at_is_local_time`).
2. **A command due exactly when the timer ends** (on-command at the end instant): the timer is extended with no off/on flap (Task 3 `test_command_at_timer_end_extends_without_flap`).
3. **Target renamed while a command waits:** the command survives the reload and runs on the new entity id (Task 3 `test_command_survives_target_rename`).
4. **Restart with an expired timer and a late on-command whose window is still open:** the target stays on, no `turn_off` then `turn_on` (Task 3 `test_restart_with_expired_timer_and_late_command_does_not_flap` and `test_expired_timer_and_late_command_after_restart_keep_target_on`).
5. **`add_command` aimed at several timers at once** (area or list target): each timer gets its own command and the response maps each "Run for" entity to its id (Task 4 `test_command_for_several_timers_returns_one_id_each`).
6. **A device that accepts calls and ignores them while settings are owed:** the re-sent turn-on still carries the settings (Task 2 `test_ignored_turn_on_keeps_the_settings_owed`).

---

## File Structure

```
custom_components/timerify/
  const.py        + SettingValue, Settings, NO_SETTINGS, freeze_settings(), command limits
  domains.py      + fallback row, behaviour_for_domain(), required turn-on features, automatic_resends,
                    settings per row, TargetCall, validate_settings(), switchable_by_features()
  core.py         + owed settings, ApplySettings, GaveUp("settings"), per-target resend limit, Command,
                    commands, tick() (replaces expire), CommandDropped, next_wakeup()
  store.py        version 2 + migration from 1; command_to_json() shared with the sensor
  controller.py   call lists, settings_applied/call_failed reporting, one alarm at next_wakeup,
                    notify on end or commands, run/add/cancel
  config_flow.py  features from the table (Task 1); picker = table domains + domains with turn_on and
                    turn_off; not_switchable for fallback domains and groups (Task 5)
  number.py       entity-service methods: async_run(minutes, **settings), async_add_command, async_cancel_command
  sensor.py       + NextCommandSensor
  services.py, services.yaml, icons.json, translations/en.json, translations/ru.json
tests/
  conftest.py     FakeTarget generalised (entity id, capability and state attributes, per-service behaviour,
                    call data); fake_climate fixture; setup_target(stored_version=...)
  helpers.py      AC ids and AC_ATTRS, call_service, at, saved, payload, add_command, record_writes
  test_domains.py test_core.py test_config_flow.py test_settings.py (new) test_commands.py (new)
  test_restart.py test_services.py test_translations.py test_device_failures.py test_entities.py
scripts/smoke/    run.py + configuration.yaml (existing, mounted read-only by compose.yaml)
RULINGS.md, docs/followups.md, README.md
```

---

### Task 1: Domain table — fallback, turn-on features, resend limits, settings

**Files:**
- Modify: `custom_components/timerify/const.py`, `custom_components/timerify/domains.py`, `custom_components/timerify/config_flow.py`, `custom_components/timerify/translations/en.json`, `custom_components/timerify/translations/ru.json`, `tests/test_domains.py`, `tests/test_config_flow.py`, `tests/helpers.py`

**Interfaces:**
- Produces in `const.py` (pure, so both `core.py` and `domains.py` import it):
  - `type SettingValue = str | float | int`; `type Settings = Mapping[str, SettingValue]`; `NO_SETTINGS: Final[Settings] = MappingProxyType({})`; `def freeze_settings(values: Mapping[str, SettingValue]) -> Settings` (a `MappingProxyType` copy).
  - `MAX_COMMANDS = 20`, `MAX_COMMAND_AHEAD = timedelta(days=7)`, `MAX_DELAY_MINUTES = 10080`.
- Produces in `domains.py`:
  - `@dataclass(frozen=True) class TargetCall: domain: str; service: str; data: Mapping[str, Any]` (data without `entity_id`).
  - `DomainBehaviour` gains `required_features: tuple[IntFlag, ...]`, `automatic_resends: int` (`MAX_AUTOMATIC_RESENDS`, except `0` for `remote` and `media_player`), `setting_names: frozenset[str]`, `turn_on_calls(settings: Settings) -> tuple[TargetCall, ...]`, `apply_calls(settings: Settings) -> tuple[TargetCall, ...]` (`apply_calls(NO_SETTINGS) == ()`).
  - `def behaviour_for_domain(domain: str) -> DomainBehaviour` — the row, or `FALLBACK` for any domain not in the table. `behaviour_for(entity_id)` goes through it (still `ValueError` for a malformed id). `FALLBACK`: `homeassistant.turn_on`/`turn_off`, on ⇔ state `on`, no features, `MAX_AUTOMATIC_RESENDS`, no settings.
  - `def validate_settings(hass: HomeAssistant, entity_id: str, values: Mapping[str, Any]) -> Settings` — reads capabilities with `homeassistant.helpers.entity.get_capability` / `get_supported_features` (state first, registry when there is no state; Home Assistant keeps capability attributes and `supported_features` on an `unavailable` state); an entity known to neither (`HomeAssistantError`) gives `setting_not_supported`; raises `ServiceValidationError` (keys below, placeholder `target` = `target_name(...)`).
  - `def switchable_by_features(hass: HomeAssistant, entity_id: str) -> bool` — the entity advertises every `required_features` flag of its row; a row without required features is `True` without a lookup; an entity known to neither state nor registry is `False`. It judges features only, not the domain.
- `config_flow.py`: `_REQUIRED_FEATURES` and `_supports_switching` are removed; the picker's filters come from the rows' `required_features`; `_validate_target` keeps its own gate `domain in SUPPORTED_DOMAINS` and then calls `switchable_by_features` (Task 5 replaces the gate).
- `tests/helpers.py`: `AC_ID = "climate.ac"`, `AC_ATTRS = {hvac_modes: [off, heat, cool, fan_only], min_temp: 16, max_temp: 30, fan_modes: [auto, low, high], supported_features: 393}` (capability attributes only; TARGET_TEMPERATURE|FAN_MODE|TURN_OFF|TURN_ON).

Required features (each domain's `turn_on`/`turn_off` require them in 2026.10.4): climate `ClimateEntityFeature.TURN_ON, TURN_OFF`; water_heater `WaterHeaterEntityFeature.ON_OFF`; **fan** `FanEntityFeature.TURN_ON, TURN_OFF`; **media_player** `MediaPlayerEntityFeature.TURN_ON, TURN_OFF`; **siren** `SirenEntityFeature.TURN_ON, TURN_OFF`. Others: none. Enums from `homeassistant.components.<domain>.const`; `brightness_supported` from `homeassistant.components.light.helper`.

Settings (all names are the HA service fields; capability attributes are the HA attribute names):

| Domain | Setting | Valid when / values | Error keys |
|---|---|---|---|
| climate | `hvac_mode` (str) | in `hvac_modes` minus `off` | `setting_not_an_option` |
| climate | `temperature` (float) | `ClimateEntityFeature.TARGET_TEMPERATURE`; `min_temp`..`max_temp` | `setting_not_supported`, `setting_out_of_range` |
| climate | `fan_mode` (str) | `ClimateEntityFeature.FAN_MODE`; in `fan_modes` | both option keys |
| light | `brightness_pct` (float) | `brightness_supported(supported_color_modes)`; 1..100 | |
| fan | `percentage` (int) | `FanEntityFeature.SET_SPEED`; 1..100 | |
| fan | `preset_mode` (str) | `FanEntityFeature.PRESET_MODE`; in `preset_modes` | |
| humidifier | `humidity` (int) | `min_humidity`..`max_humidity` | |
| humidifier | `mode` (str) | `HumidifierEntityFeature.MODES`; in `available_modes` | |
| water_heater | `temperature` (float) | `WaterHeaterEntityFeature.TARGET_TEMPERATURE`; `min_temp`..`max_temp` | |
| water_heater | `operation_mode` (str) | `WaterHeaterEntityFeature.OPERATION_MODE`; in `operation_list` minus `off` | |

Any other name on any domain (fallback included) → `setting_not_supported`. Keys: `setting_not_supported` {target, setting}; `setting_out_of_range` {setting, value, min, max}; `setting_not_an_option` {setting, value, options}.

Call lists (D2, in this order, only for settings given):
- climate on: `set_hvac_mode{hvac_mode}` if given, else `climate.turn_on`; then `set_temperature{temperature}`, `set_fan_mode{fan_mode}`. Apply: the same without `turn_on`.
- light / fan on and apply: one `<domain>.turn_on` carrying the settings as data.
- humidifier on: `humidifier.turn_on`, `set_humidity{humidity}`, `set_mode{mode}`; water_heater on: `water_heater.turn_on`, `set_temperature{temperature}`, `set_operation_mode{operation_mode}`. Apply: the `set_*` calls only.
- Every other row: `turn_on_calls(_) == (TargetCall(*on_service, {}),)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_unlisted_domain_uses_generic_fallback():      # behaviour_for("kettle.tea") is FALLBACK; on_service ("homeassistant","turn_on")
def test_fallback_reads_only_on_as_on():               # actual_state(State("camera.door","idle")) == "off"; "on" → "on"
def test_required_features_per_domain():               # fan/media_player/siren/climate/water_heater as listed; switch == ()
def test_automatic_resends_per_domain():               # remote, media_player == 0; switch, climate, FALLBACK == MAX_AUTOMATIC_RESENDS
@pytest.mark.parametrize(("settings", "expected"), [
    ({"hvac_mode": "cool", "temperature": 24.0},
     [("climate", "set_hvac_mode", {"hvac_mode": "cool"}), ("climate", "set_temperature", {"temperature": 24.0})]),
    ({"temperature": 22.0}, [("climate", "turn_on", {}), ("climate", "set_temperature", {"temperature": 22.0})]),
])
def test_climate_turn_on_calls(settings, expected): ...
def test_climate_apply_calls_never_turn_on():          # apply_calls({"temperature": 22.0}) == (set_temperature,)
def test_light_and_fan_settings_ride_in_turn_on():     # light: (light.turn_on {"brightness_pct": 40},) for both lists
def test_humidifier_and_water_heater_turn_on_then_set()
async def test_every_call_names_a_home_assistant_service(hass, domain):  # parametrized over SUPPORTED_DOMAINS: setup the
    # domain component, build turn_on_calls/apply_calls with every setting of the row, assert hass.services.has_service
async def test_valid_climate_settings_are_frozen(hass):  # AC_ID with AC_ATTRS → returns {"hvac_mode":"cool","temperature":24.0}
@pytest.mark.parametrize(("entity_id", "attributes", "values", "key"), [
    ("climate.ac", AC_ATTRS, {"hvac_mode": "off"}, "setting_not_an_option"),
    ("climate.ac", AC_ATTRS, {"temperature": 31}, "setting_out_of_range"),
    ("climate.ac", AC_ATTRS, {"brightness_pct": 50}, "setting_not_supported"),
    ("light.hall", {"supported_color_modes": ["onoff"]}, {"brightness_pct": 50}, "setting_not_supported"),
    ("light.hall", {"supported_color_modes": ["brightness"]}, {"brightness_pct": 0}, "setting_out_of_range"),
    ("fan.ceiling", {"supported_features": 0}, {"percentage": 50}, "setting_not_supported"),
    ("humidifier.room", {"min_humidity": 30, "max_humidity": 80}, {"humidity": 90}, "setting_out_of_range"),
    ("water_heater.tank", {"supported_features": 3, "operation_list": ["off", "eco"]}, {"operation_mode": "off"}, "setting_not_an_option"),
    ("switch.boiler", {}, {"temperature": 20}, "setting_not_supported"),
])
async def test_invalid_settings_are_rejected(hass, entity_id, attributes, values, key):
    # assert err.value.translation_key == key and err.value.translation_domain == DOMAIN
async def test_settings_validate_while_unavailable(hass):        # state "unavailable" with AC_ATTRS → validated
async def test_settings_validate_from_registry_without_state(hass):  # registry entry with capabilities and supported_features,
    # no state → validated
async def test_settings_of_an_unknown_entity_are_not_supported(hass):  # no state, no registry entry → "setting_not_supported"
```

In `tests/test_config_flow.py`: update `test_picker_offers_only_entities_that_can_be_switched` to the filters from the table (fan, media_player, siren featured, alongside climate and water_heater) and add `("fan.ceiling", 0)`, `("media_player.tv", 0)`, `("siren.yard", 0)` to the parameters of `test_entity_that_cannot_be_turned_on_and_off_is_rejected` (`target_not_supported`). Replace `test_unsupported_domain_raises` with the fallback test above; keep `test_malformed_entity_id_raises` and `test_registry_id_of_an_unsupported_entity_is_rejected` (the domain gate still rejects a `sensor`).

- [ ] **Step 2: Run `uv run pytest tests/test_domains.py tests/test_config_flow.py -v`** — Expected: new tests FAIL.
- [ ] **Step 3: Implement** the table extensions, the move out of `config_flow.py`, the error keys and messages in `en.json`/`ru.json` `exceptions`.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Add settings, turn-on features and a generic fallback to the domain table"`

---

### Task 2: Owed settings end to end — core, controller, `run`, store v2

**Files:**
- Modify: `core.py`, `store.py`, `controller.py`, `number.py`, `services.py`, `services.yaml`, `translations/en.json`, `translations/ru.json`, `tests/conftest.py`, `tests/helpers.py`, `tests/test_core.py`, `tests/test_restart.py`, `tests/test_services.py`, `tests/test_translations.py`, `tests/test_device_failures.py`
- Create: `tests/test_settings.py`

**Interfaces:**
- Consumes: `Settings`, `NO_SETTINGS`, `freeze_settings`, `turn_on_calls`, `apply_calls`, `automatic_resends`, `validate_settings` (Task 1).
- Produces in `core.py`:
  - `Snapshot.owed_settings: Settings = NO_SETTINGS` — settings asked for and not yet confirmed applied.
  - `TurnOn(settings: Settings = NO_SETTINGS)` (so phase-1 `TurnOn()` comparisons hold); new `@dataclass(frozen=True) class ApplySettings: settings: Settings`; `GaveUp(what: Literal["on", "off", "settings"])` (the field was `wish`); `Effect` union extended.
  - `TimerCore(mode, default_duration, snapshot, *, automatic_resends: int = MAX_AUTOMATIC_RESENDS)` — the limit replaces the constant inside the core.
  - `set_duration(now, duration, settings: Settings = NO_SETTINGS, *, apply_if_on: bool = True)` and `run_open(now, settings: Settings = NO_SETTINGS, *, apply_if_on: bool = True)`. `apply_if_on=False` (for phase-3 schedules, D3) sends the settings only with a `TurnOn` this command causes.
  - `settings_applied(now) -> list[Effect]` — clears `owed_settings` (`Changed()`).
  - `call_failed(now)` additionally marks owed settings unsent (also when no wish is pending).
- Produces in `store.py`: `TimerStore.STORAGE_VERSION = 2`; the inner store is a `Store` subclass with an annotated `_async_migrate_func(old_major_version, old_minor_version, old_data)`: version 1 → `{**old_data, "owed_settings": {}}`. Payload: `{"end", "pending", "owed_settings": {name: value}}`. `async_load` reads the v2 keys strictly (the migration guarantees them).
- Produces in `controller.py`:
  - `TargetController.async_run(minutes: int | None = None, settings: Mapping[str, Any] | None = None) -> None` — validates settings (`validate_settings`), then `run_open` (no minutes) or `set_duration`.
  - The core is built with `automatic_resends=self._behaviour.automatic_resends`.
  - Effects become labelled call lists: `TurnOn(s)` → `("on", behaviour.turn_on_calls(s))`; `TurnOff()` → `("off", (TargetCall(*off_service, {}),))`; `ApplySettings(s)` → `("settings", behaviour.apply_calls(s))`. Calls run in order, each with a fresh own `Context` recorded in `_own_contexts` and under `SERVICE_CALL_TIMEOUT`; the first failing call stops the list and reports `core.call_failed`. After an `"on"`/`"off"` list the wrong-state check of the fix wave runs; a wrong state counts as a failure of the whole list. A list carrying settings (a `TurnOn` with settings, or `ApplySettings`) that finished without any failure → `core.settings_applied(now)`.
  - Logging and `_raised_for` are keyed by the label (`Literal["on", "off", "settings"]`): `"Could not turn %s %s: %s"` for on/off, `"Could not apply settings to %s: %s"` for settings; `_raised_for` is cleared when that label's work settles (the wish is no longer pending; the owed settings are cleared or replaced). `GaveUp("settings")` logs `"%s did not take its settings after %d attempts; …"`.
- `timerify.run` schema: optional `minutes` (`whole_minutes`, 1..`MAX_MINUTES`) and the settings fields; `RunForNumber.async_run(self, minutes: int | None = None, **settings: Any)`.
- `services.py`: one private factory `_whole(message)` builds `whole_minutes` (message as today) and `whole_number` (generic message). `SETTINGS_SCHEMA: VolDictType`: `hvac_mode`, `fan_mode`, `preset_mode`, `mode`, `operation_mode` → `cv.string`; `temperature`, `brightness_pct` → `probatio.Coerce(float)`; `percentage`, `humidity` → `whole_number`.
- `services.yaml`: `run` gets `minutes` (number box 1..1440 `min`) and a section `settings: &settings {collapsed: true, fields: ...}` (the anchor is reused by `add_command` in Task 4); selectors: `hvac_mode` select `[heat, cool, heat_cool, auto, dry, fan_only]` with `translation_key: hvac_mode`; `temperature` number box 0..250 step 0.1; `brightness_pct`, `percentage`, `humidity` number slider 1..100 `%`; the other modes `text`. (The service targets the "Run for" number, so `state` selectors cannot list the device's own modes.) Translations: field names/descriptions (repeated per service — custom integrations get no `[%key:…%]` references), `services.run.sections.settings.name`, `selector.hvac_mode.options`.
- Test fixtures (conftest): `FakeTarget` takes `entity_id`, `capability_attributes` and `state_attributes` (both merged under every `set_state`; only `capability_attributes` on `unavailable`/`unknown`, as Home Assistant writes them), and per-service behaviour; `set_state` writes its own `entity_id`; records `calls: list[tuple[str, str]]` (unchanged shape) and `call_data: list[tuple[str, dict[str, Any]]]` (service, data without `entity_id`); `fail_next_call(error=..., service: str | None = None)` fails the next call of that service. `fake_climate`: `AC_ID` on device "AC", state `off`, capability attributes `AC_ATTRS`, state attributes `{temperature: 20, fan_mode: auto}`; services `turn_on` (→ `heat`), `turn_off`, `set_hvac_mode`, `set_temperature`, `set_fan_mode` update state/attributes with `context=call.context`. `setup_target(..., stored_version: int = TimerStore.STORAGE_VERSION)`.
- `tests/helpers.py`: `AC_NUMBER = "number.ac_run_for"`, `AC_ENDS_AT = "sensor.ac_ends_at"`; moved here: `call_service` (from test_services.py), `at`, `saved` (from test_restart.py); new `payload(end=None, pending=None, owed_settings=None) -> dict` — the stored form, used by every stored dict and every `saved(...) ==` assertion in `tests/test_restart.py`.

Core rules:
1. Non-empty settings replace `owed_settings` and are marked unsent (a newer command replaces older owed settings). Owed settings are never invented or dropped by an empty command: R4 and every command without settings leave them alone.
2. Delivery, whenever the core sends or re-sends a wish or sees a report: unsent owed settings go out **with the next `TurnOn`** (`_send("on")` builds `TurnOn(owed)` and marks them sent). If no `TurnOn` goes out and the target is on (observed `on`, or a turn-on is in flight) → `ApplySettings(owed)`. Target unavailable → nothing until it is back (R10).
3. Dropped (set to `NO_SETTINGS`): on `_stop` (any stop, expiry included), on R3 (external off), on `settings_applied`. Invariant: `pending == "off"` implies no owed settings.
4. A restored snapshot with owed settings, and a target that comes back (`last_actual` was `None` or `unavailable`), marks them unsent — the same rule as the pending wish.
5. Re-sends of owed settings follow the wish's limit with their own counter: a report that repeats the target's state sends them at most `automatic_resends` times, then `GaveUp("settings")` once; the count starts again on new settings, a change of the target's state, or the target coming back. The wish's counter and `GaveUp("on"/"off")` use the same constructor limit.

- [ ] **Step 1: Write the failing tests**

`tests/test_core.py` (`COOL24 = freeze_settings({"hvac_mode": "cool", "temperature": 24.0})`):

```python
def test_settings_ride_with_turn_on():                 # "off": set_duration(NOW, 60 min, COOL24) == [Arm(NOW+60), TurnOn(COOL24), Changed()]; owed == COOL24
def test_settings_on_running_target_are_applied():     # "on": == [Arm(NOW+60), ApplySettings(COOL24), Changed()]
def test_apply_if_on_false_leaves_running_target_alone():  # "on": [Arm(...), Changed()], owed empty
def test_loose_open_run_with_settings_on_running_target_applies_them()  # loose "on": run_open(NOW, COOL24) has ApplySettings(COOL24)
def test_settings_applied_clears_them():               # == [Changed()], owed == NO_SETTINGS
def test_failed_settings_are_resent_on_next_report():  # "on", ApplySettings, call_failed, observe(on, by_us=False) == [ApplySettings(COOL24)]
def test_failed_turn_on_resends_settings_with_it():    # "off", TurnOn(COOL24), call_failed, observe(off) → [TurnOn(COOL24)]
def test_settings_wait_for_unavailable_target():       # "unavailable": no TurnOn/ApplySettings; observe("off") → TurnOn(COOL24); variant observe("on") → ApplySettings(COOL24)
def test_settings_while_turn_on_in_flight_are_applied():   # "off", set_duration(10) → TurnOn(); set_duration(60, COOL24) → ApplySettings(COOL24), no TurnOn
def test_newer_settings_replace_owed():                # unavailable, two commands with different settings → owed == second
def test_command_without_settings_keeps_owed():        # unavailable, set_duration(COOL24), then set_duration(30) → owed == COOL24
def test_manual_off_drops_owed_settings():             # "on", ApplySettings sent, observe("off", by_us=False) → owed empty, end None
def test_stop_drops_owed_settings()
def test_manual_on_pushes_no_settings():               # strict idle "off", observe("on") external → no ApplySettings, owed empty
def test_restored_owed_settings_are_resent():          # Snapshot(end=NOW+30, owed_settings=COOL24), observe(NOW, "on", by_us=False)
    # == [ApplySettings(COOL24), Changed()]  (the first observation sets last_actual)
def test_refused_settings_are_resent_a_limited_number_of_times():  # "on", ApplySettings refused each time (call_failed);
    # repeated "on" reports → [[ApplySettings(COOL24)]] * MAX_AUTOMATIC_RESENDS + [[GaveUp("settings")]], then []
def test_a_change_of_state_gives_settings_a_full_allowance_again()  # after GaveUp("settings"): "unavailable", "on" → ApplySettings again
def test_zero_automatic_resends_answers_only_changes():  # TimerCore(..., automatic_resends=0), refused TurnOn: repeated report →
    # [GaveUp("on")]; a changed state ("unavailable" then "off") → TurnOn()
```

Add `settings_applied` to `test_naive_time_is_rejected`; update the `GaveUp` tests for the renamed field.

`tests/test_settings.py`:

```python
async def test_run_with_settings_turns_ac_on_cooling(hass, fake_climate, setup_target):
    await setup_target(target=AC_ID)
    await call_service(hass, "run", {"entity_id": AC_NUMBER}, minutes=60, hvac_mode="cool", temperature=24)
    assert fake_climate.call_data == [("set_hvac_mode", {"hvac_mode": "cool"}), ("set_temperature", {"temperature": 24.0})]
    assert state_of(hass, AC_ID) == "cool" and state_of(hass, AC_NUMBER) == "60"
async def test_run_with_settings_on_running_ac_applies_them():   # AC "heat" (R4 → 45), run hvac_mode=cool → set_hvac_mode only, no turn_on, number "45"
async def test_run_with_minutes_only_sets_the_timer():           # switch: run minutes=20 → [TURN_ON], number "20"
async def test_failed_settings_call_is_retried_on_next_report():  # AC off; fail_next_call(service="set_hvac_mode"); run 60 cool 24
    # → warning, call_data == [set_hvac_mode], AC still "off", number "60"; await fake_climate.set_state("off", signal=70) (a report; an identical state would fire no event)
    # → set_hvac_mode(cool), set_temperature(24) sent again; AC "cool", temperature 24
async def test_failed_apply_is_retried_on_the_targets_report():  # AC "heat"; fail_next_call(service="set_temperature"); run cool 24
    # → set_hvac_mode ok, set_temperature fails ("Could not apply settings to" in caplog); the AC's own report of the mode
    # change re-sends the apply list: call_data ends with [set_hvac_mode(cool), set_temperature(24)], temperature 24
async def test_ignored_turn_on_keeps_the_settings_owed():        # AC off; ignore_next_call(); run 60 cool 24 → the list returns,
    # the AC stays "off"; await fake_climate.set_state("off", signal=70) → set_hvac_mode(cool), set_temperature(24) again; AC "cool", 24
async def test_settings_wait_while_ac_unavailable():             # set_state("unavailable"); run 60 cool 24 → no calls, number "60";
    # set_state("off") → set_hvac_mode(cool), set_temperature(24)
async def test_settings_are_not_resent_once_applied():           # after success, an attribute-only report → no new calls
@pytest.mark.parametrize(("data", "key"), [
    ({"hvac_mode": "dry"}, "setting_not_an_option"), ({"temperature": 35}, "setting_out_of_range"),
    ({"brightness_pct": 50}, "setting_not_supported"), ({"fan_mode": "turbo"}, "setting_not_an_option"),
])
async def test_invalid_settings_are_rejected_before_anything_runs(..., data, key):  # ServiceValidationError key; no calls; number "0"
@pytest.mark.parametrize("minutes", [0, MAX_MINUTES + 1, 2.5])
async def test_run_minutes_outside_range_are_rejected(...)       # pytest.raises(probatio.Invalid)
```

`tests/test_device_failures.py`:

```python
async def test_media_player_is_not_turned_on_again_by_repeated_reports():  # FakeTarget("media_player.tv", ignore_calls()):
    # set "Run for" 30 → one turn_on; three reports that repeat its "off" state (`set_state("off", signal=n)`, an attribute changes each time) → no further call, one warning;
    # the player drops to "unavailable" and reports "off" again (a change; "standby" would still read as off) → turn_on again
```

`tests/test_restart.py`: every stored dict and `saved(...) ==` assertion goes through `payload(...)`; add

```python
async def test_version_1_store_is_migrated(...):   # stored_version=1, stored {"end": at(30), "pending": None} → number "30";
    # after a change the file has version 2 and == payload(end=..., owed_settings={})
async def test_owed_settings_survive_restart(...): # AC, stored payload(end=at(60), pending="on", owed_settings={"hvac_mode": "cool", "temperature": 24.0}),
    # target "off" → set_hvac_mode(cool), set_temperature(24); file then has "owed_settings": {}
```

`tests/test_services.py`: `test_services_are_described_for_the_ui` — `run` now has `minutes` (min 1, max `MAX_MINUTES`) and the settings fields. `tests/test_translations.py`: `test_services_are_translated` descends into sections (a section's fields are translated flat under `fields`, its name under `sections.<name>.name`).

- [ ] **Step 2: Run `uv run pytest tests/test_core.py tests/test_settings.py tests/test_restart.py tests/test_device_failures.py -v`** — Expected: new tests FAIL.
- [ ] **Step 3: Implement** core rules 1–5, store v2, controller call lists and reporting, `run` schema/method/yaml/translations, fixtures and helpers; a private `_settings_unsent` flag mirrors `_unsent` (memory only).
- [ ] **Step 4: Run all checks** — Expected: all pass, phase-1 scenarios included.
- [ ] **Step 5: Commit** — `git commit -m "Apply settings through run and store owed settings"`

---

### Task 3: Pending commands — core, wake-up alarm, store

**Files:**
- Modify: `core.py`, `controller.py`, `store.py`, `tests/test_core.py`, `tests/test_restart.py`, `tests/helpers.py`
- Create: `tests/test_commands.py`

**Interfaces:**
- Consumes: Task 2 (owed settings, call lists, store v2).
- Produces in `core.py`:
  - `@dataclass(frozen=True) class Command: id: str; at: datetime; action: Literal["on", "off"]; minutes: int | None = None; settings: Settings = NO_SETTINGS` (`at` aware UTC; `minutes`/`settings` only for `on`).
  - `Snapshot.commands: tuple[Command, ...] = ()` ordered by `at`, then insertion.
  - `add_command(now, command: Command) -> list[Effect]`; `cancel_command(now, command_id: str) -> list[Effect]` (raises `KeyError` for an unknown id).
  - `tick(now) -> list[Effect]` — **replaces `expire`** in the core, the controller and `tests/test_core.py`; handles every alarm.
  - `@dataclass(frozen=True) class CommandDropped: command: Command` effect.
  - `def next_wakeup(snapshot: Snapshot) -> datetime | None` — the earlier of `end` and `commands[0].at`.
- Produces in `store.py`: the v2 payload gains `"commands": [command_to_json(c)...]` and the migration from 1 adds `"commands": []` (0.2.0 is unreleased, so this needs no further version). `def command_to_json(command: Command) -> dict[str, Any]` → `{"id", "at": ISO UTC, "action", "minutes", "settings": dict}` (store and, in Task 4, sensor share it).
- Produces in `controller.py`: one alarm at `next_wakeup(snapshot)` (`_wakeup_alarm`, `_handle_wakeup` replacing `_expiry_alarm`/`_handle_expiry`) calling `core.tick`; `_handle_started` arms `next_wakeup` instead of `end`. `CommandDropped(c)` → `_LOGGER.info` naming the target, the command's action and time. The unavailable log of a wake-up is worded by what was due, from the snapshot before and after `tick`: the end reached → "The timer of %s ended while it is unavailable; it is turned off when it is back"; commands run → "A pending command for %s came due while it is unavailable; it is carried out when it is back".
- `tests/helpers.py`: `payload(...)` gains `commands=()` (a sequence of `command_to_json` dicts).

Rules:
1. **Wake-up:** wherever phase 1 emitted `Arm(end)`/`Disarm()`, emit `Arm(next_wakeup(snapshot))`, or `Disarm()` when it is `None`. So R3 with commands waiting gives `Arm(first command)`, not `Disarm()`. Without commands, phase-1 effects are unchanged.
2. **Catch-up** (`tick`, and `observe` — rule 4): take the due items — the end if `end <= now`, and every command with `at <= now` — in time order, a command before the end on a tie, and fold them into the timer:
   - end → timer stops (wish `off`);
   - `on` with minutes → end `at + minutes`; `on` without minutes → strict: end `at + default_duration`, loose: open run (end `None`, wish `on`); if that end is not after `now` → `CommandDropped(command)` and the timer is untouched (P3, §5.7);
   - `off` → timer stops (wish `off`), late or not;
   - an executed `on` with settings replaces the owed settings with its own (Task 2 rule 1: one without settings leaves them; P1: applied even when running);
   - every due command leaves `commands`, executed or dropped;
   - the end is an item only while the *current* end (after earlier items moved it) is `<= now`.
   After the fold: one `_want` for the last wish (if any), one wake-up effect, `Changed()`. Due `on` then `off` on an off target therefore switches nothing.
3. **P2:** observations never touch `commands`.
4. **`observe` order:** (a) note "came back" and record `last_actual` (as phase 1); (b) catch-up; (c) `actual == "unavailable"` → return; (d) re-send an unsent wish / settle on own change (as phase 1); (e) the external-change branch (R3–R5) runs only if catch-up changed nothing — due items outrank the report, as expiry did in phase 1; (f) owed-settings delivery (Task 2 rule 2).

- [ ] **Step 1: Write the failing tests**

`tests/test_core.py` (`cmd(minutes_from_now, action="on", minutes=None, settings=NO_SETTINGS, id="c1") -> Command`):

```python
def test_add_command_arms_wakeup():                     # idle: add_command(cmd(15)) == [Arm(NOW+15), Changed()]
def test_wakeup_is_earliest_of_end_and_commands():       # end NOW+45, cmd at +15 → next_wakeup == NOW+15; cancel → NOW+45
def test_commands_ordered_by_time_then_insertion():      # add c2@+20, c1@+10, c3@+10 → ids ("c1", "c3", "c2")
def test_cancel_unknown_command_raises():                # pytest.raises(KeyError)
def test_cancel_last_command_on_idle_timer_disarms():    # == [Disarm(), Changed()]
def test_ac_command_resets_timer_and_applies_settings(): # strict "on", end NOW+45; cmd(15, minutes=60, settings=COOL24); tick(NOW+15)
    # → end == NOW+75, ApplySettings(COOL24) in fx, no TurnOn, commands == ()
def test_command_on_off_target_turns_on_with_settings(): # "off" → TurnOn(COOL24)
def test_command_without_minutes_strict_runs_default_from_at()   # end == at + 45
def test_command_without_minutes_loose_runs_open()       # end None, TurnOn()
def test_off_command_stops():                             # running "on" → TurnOff(), end None
def test_manual_off_keeps_commands():                     # running + cmd(15); observe("off", by_us=False) → commands kept, Arm(NOW+15) in fx, no Disarm
def test_late_command_runs_for_the_remainder():           # cmd(-20, minutes=60), tick(NOW) → end == NOW+40
def test_late_command_past_its_duration_is_dropped():     # cmd(-61, minutes=60) → [CommandDropped(c), ...], end unchanged, commands == ()
def test_late_strict_open_run_past_default_is_dropped()   # cmd(-46) strict → dropped
def test_late_loose_open_run_and_late_off_still_execute()
def test_due_on_then_off_switches_nothing():              # "off": c1 on@0, c2 off@0, tick → no TurnOn, no TurnOff, end None
def test_command_at_timer_end_extends_without_flap():     # end NOW+10, cmd(10, minutes=30); tick(NOW+10) → no TurnOff, end NOW+40
def test_command_due_while_unavailable_changes_timer_at_once():  # "unavailable": tick → end set, no TurnOn; observe("off") → TurnOn(settings)
def test_restart_with_expired_timer_and_late_command_does_not_flap():
    c = TimerCore("strict", timedelta(minutes=45),
                  Snapshot(end=NOW - timedelta(minutes=5), commands=(cmd(-10, minutes=60, settings=COOL24),)))
    fx = c.observe(NOW, "on", by_us=False)
    assert TurnOff() not in fx and not any(isinstance(e, TurnOn) for e in fx)
    assert c.snapshot.end == NOW + timedelta(minutes=50) and ApplySettings(COOL24) in fx
def test_tick_with_nothing_due_is_stale():                # == []
```

Rename `expire` → `tick` in the phase-1 core tests, including the `expire` parameter of `test_naive_time_is_rejected`, and add `add_command` and `cancel_command` to it.

`tests/test_commands.py` (commands reach the timer through the store here; Task 4 adds the services):

```python
async def test_stored_command_runs_on_time():              # stored payload(commands=[on at(10) minutes 30]), boiler "off" →
    # nothing before +10; at +10 → [TURN_ON], number "30"; stored commands == []
async def test_command_due_during_downtime_runs_for_the_rest():  # stored command on at(-10) minutes 30, target "off" → [TURN_ON], number "20"
async def test_command_whose_time_ran_out_during_downtime_is_dropped():  # at(-40) minutes 30 → no calls; caplog INFO names the
    # target, "on" and the time; stored commands == []
async def test_expired_timer_and_late_command_after_restart_keep_target_on():  # stored end at(-5) + command at(-10) minutes 60,
    # target "on" → calls == [], number "50"
async def test_command_due_while_unavailable_runs_when_back():   # stored on at(10) minutes 30; set_state("unavailable") before T →
    # no call at T, number "30", caplog has "came due while it is unavailable"; set_state("off") → [TURN_ON]
async def test_command_survives_target_rename():           # stored on at(10); rename switch.boiler → switch.water_heater before T
    # (as test_source_changes does) → ("turn_on", "switch.water_heater") at T
```

`tests/test_restart.py`: `test_version_1_store_is_migrated` now expects `commands == []` too (through `payload`).

- [ ] **Step 2: Run `uv run pytest tests/test_core.py tests/test_commands.py tests/test_restart.py -v`** — Expected: new tests FAIL.
- [ ] **Step 3: Implement** rules 1–4, the controller's wake-up alarm, logs and `tick` rename, the store's `commands`.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Add pending commands to the timer core, its alarm and its store"`

---

### Task 4: `add_command`, `cancel_command`, "Next command" sensor

**Files:**
- Modify: `controller.py`, `number.py`, `sensor.py`, `services.py`, `services.yaml`, `icons.json`, `translations/en.json`, `translations/ru.json`, `tests/helpers.py`, `tests/test_commands.py`, `tests/test_services.py`, `tests/test_entities.py`

**Interfaces:**
- Consumes: Tasks 2–3.
- Produces:
  - Controller notification: listeners are called when `end` **or** `commands` changed (the controller remembers both); every entity gates its own write — "Ends at" on `end`, "Next command" on `commands`, "Run for" as today (Home Assistant drops identical writes).
  - `TargetController.async_add_command(action: Literal["on", "off"], at: datetime, minutes: int | None, settings: Mapping[str, Any] | None) -> str` — rejects `off` with minutes or settings (`off_takes_no_duration_or_settings`), validates settings, then under the lock: `at <= now` → `command_in_past` {at}; `at > now + MAX_COMMAND_AHEAD` → `command_too_far` {days}; `len(commands) >= MAX_COMMANDS` → `too_many_commands` {target, limit}; id `uuid4().hex`; returns the id.
  - `TargetController.async_cancel_command(command_id: str) -> None` — `KeyError` from the core → `unknown_command` {command_id}.
  - Services (entity services on the "Run for" number, like phase 1):
    - `timerify.add_command`: `action` (`probatio.In(["on", "off"])`, required), `delay` (`whole_minutes`, 1..`MAX_DELAY_MINUTES`), `at` (`cv.datetime`; naive → `dt_util.as_utc`, i.e. HA's time zone), `minutes` (1..`MAX_MINUTES`), `SETTINGS_SCHEMA`; exactly one of `delay`/`at`, else `delay_or_at` (checked in the method so the error is translated). `supports_response=SupportsResponse.OPTIONAL`; `RunForNumber.async_add_command(...) -> ServiceResponse` returns `{"command_id": id}` (HA keys it by entity id).
    - `timerify.cancel_command`: `command_id` (`cv.string`, required). Aimed at the timer that owns the command; another timer answers `unknown_command`.
    - yaml: `action` select `[on, off]` `translation_key: command_action`; `delay` number box 1..10080 `min`; `at` `datetime`; `minutes` number box 1..1440; `settings: *settings`; `command_id` text. Icons `mdi:clock-plus-outline`, `mdi:clock-remove-outline`.
  - `class NextCommandSensor(TimerifyEntity, SensorEntity)` (added by `sensor.async_setup_entry` next to "Ends at"): key/translation key `next_command`, `SensorDeviceClass.TIMESTAMP`, `native_value` = `commands[0].at` or `None`; `extra_state_attributes = {"commands": [command_to_json(c) for c in commands]}`; `_unrecorded_attributes = frozenset({"commands"})`; writes state only when `snapshot.commands` changed; icon `mdi:calendar-clock`; name "Next command", attribute name "Commands".
- `tests/helpers.py`: `AC_NEXT = "sensor.ac_next_command"`, `NEXT = "sensor.boiler_next_command"`; `add_command(hass, number, **data) -> dict` (calls with `return_response=True`); `record_writes` moved from `tests/test_entities.py`.

- [ ] **Step 1: Write the failing scenario tests** (`tests/test_commands.py`)

```python
async def test_ac_in_15_minutes_for_an_hour_cooling_24(hass, freezer, fake_climate, setup_target):
    await setup_target(target=AC_ID)
    await fake_climate.set_state("heat")                               # AC on by remote: strict → 45 min (R4)
    response = await add_command(hass, AC_NUMBER, action="on", delay=15, minutes=60, hvac_mode="cool", temperature=24)
    command_id = response[AC_NUMBER]["command_id"]; assert re.fullmatch(r"[0-9a-f]{32}", command_id)
    assert state_of(hass, AC_NEXT) == "2026-01-05T07:15:00+00:00"
    assert hass.states.get(AC_NEXT).attributes["commands"] == [{"id": command_id, "at": "2026-01-05T07:15:00+00:00",
        "action": "on", "minutes": 60, "settings": {"hvac_mode": "cool", "temperature": 24.0}}]
    await advance(hass, freezer, minutes=15)
    assert fake_climate.call_data == [("set_hvac_mode", {"hvac_mode": "cool"}), ("set_temperature", {"temperature": 24.0})]
    assert state_of(hass, AC_NUMBER) == "60" and state_of(hass, AC_ENDS_AT) == "2026-01-05T08:15:00+00:00"
    assert state_of(hass, AC_NEXT) == "unknown"
async def test_manual_use_does_not_cancel_command():      # boiler: on delay 10 minutes 30; set_state("on") by hand (R4 → 45),
    # set_state("off") at +5 (R3 → 0); at +10 → calls == [TURN_ON], number "30"
async def test_cancel_command_removes_it():               # cancel → next_command "unknown", nothing at T
async def test_cancel_unknown_command_is_rejected():      # key "unknown_command"
async def test_cancel_through_another_timer_is_rejected(): # command on the boiler; cancel_command on AC_NUMBER with its id →
    # "unknown_command"; the boiler's command still runs at T
async def test_off_command_turns_target_off_on_time():    # running 45; off delay 10 → TURN_OFF at +10, number "0"
async def test_command_at_is_local_time():                # await hass.config.async_set_time_zone("Asia/Jerusalem");
    # at="2026-01-05 09:30:00" → next_command "2026-01-05T07:30:00+00:00"
@pytest.mark.parametrize(("data", "key"), [
    ({"action": "on", "delay": 5, "at": "2026-01-05T08:00:00+00:00"}, "delay_or_at"),
    ({"action": "on"}, "delay_or_at"),
    ({"action": "on", "at": "2026-01-05T06:59:00+00:00"}, "command_in_past"),
    ({"action": "on", "at": "2026-01-12T07:01:00+00:00"}, "command_too_far"),
    ({"action": "off", "delay": 5, "minutes": 10}, "off_takes_no_duration_or_settings"),
    ({"action": "off", "delay": 5, "hvac_mode": "cool"}, "off_takes_no_duration_or_settings"),
])
async def test_invalid_commands_are_rejected(..., data, key)
async def test_twenty_first_command_is_rejected():         # 20 accepted, 21st → "too_many_commands"
async def test_command_for_several_timers_returns_one_id_each(hass, fake_target, fake_climate, setup_target):
    # both set up; add_command(entity_id=[NUMBER, AC_NUMBER], action="on", delay=5) → keys {NUMBER, AC_NUMBER}, ids differ; both run at +5
async def test_next_command_shows_a_command_on_an_idle_timer():  # idle boiler: add_command delay 30 → NEXT shows its time at once
async def test_next_command_is_written_only_when_commands_change():  # record_writes(AC_NEXT) over 10 idle minutes: none
async def test_command_list_is_not_recorded(recorder_mock, hass, ...):  # add a command, async_wait_recording_done;
    # get_significant_states (homeassistant.components.recorder.history) for NEXT has the state, and its attributes lack "commands"
```

`tests/test_services.py`: `test_services_are_described_for_the_ui` also checks `add_command` (same target; `delay` max `MAX_DELAY_MINUTES`, `minutes` max `MAX_MINUTES`) and `cancel_command`. Move `record_writes` imports in `tests/test_entities.py` to `tests/helpers.py`.

- [ ] **Step 2: Run `uv run pytest tests/test_commands.py tests/test_services.py -v`** — Expected: FAIL.
- [ ] **Step 3: Implement** the notification change, controller methods, entity-service methods, schemas, yaml, sensor, icons, translations (service/field/section names and descriptions, `selector.command_action`, entity and attribute names, the new `exceptions`), `Platform.SENSOR` already forwarded.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Add pending commands with add_command, cancel_command and Next command sensor"`

---

### Task 5: Config flow — generic fallback and `not_switchable`

**Files:**
- Modify: `config_flow.py`, `translations/en.json`, `translations/ru.json` (`config.error.not_switchable`), `tests/test_config_flow.py`
- Create: none

**Interfaces:**
- Consumes: `SUPPORTED_DOMAINS`, `switchable_by_features`, `behaviour_for_domain` (Task 1).
- Produces: `def offered_domains(hass: HomeAssistant) -> list[str]` — `SUPPORTED_DOMAINS` plus, sorted, every other domain for which `hass.services.has_service(domain, "turn_on")` and `has_service(domain, "turn_off")` at flow time, excluding `homeassistant`. The picker is built per form (a `SchemaFlowFormStep` whose schema is an async callable taking the handler), its feature filters come from each row's `required_features`; fallback domains join the unfiltered filter.
- Validation on submit, in this order: domain not in `offered_domains(hass)` → `target_not_supported`; table domain → `switchable_by_features` else `target_not_supported`; then a fallback domain **or a `group`** whose current state is not `on` or `off` → `not_switchable` (other table domains are never judged by state; their state may legitimately be e.g. `heat`). Task 1's `domain in SUPPORTED_DOMAINS` gate is replaced by the first check.

- [ ] **Step 1: Write the failing tests**

```python
async def test_picker_offers_domains_that_can_be_turned_on_and_off(hass):
    # register kettle.turn_on + kettle.turn_off, scene_like.turn_on only → picker domains == [*SUPPORTED_DOMAINS, "kettle"]
    # (no "scene_like", no "homeassistant"); filters: one unfiltered (table rows without features + "kettle"),
    # one per featured row with its features
@pytest.mark.parametrize("state", ["on", "off"])
async def test_fallback_entity_in_on_off_state_is_accepted(hass, state)   # → step "duration"
@pytest.mark.parametrize("state", ["idle", "streaming", "unavailable"])
async def test_fallback_entity_in_other_state_is_rejected(hass, state)    # errors == {"base": "not_switchable"}
async def test_domain_without_turn_on_and_off_is_not_supported(hass):     # "sensor.temp" in state "on" → "target_not_supported"
@pytest.mark.parametrize(("state", "error"), [("on", None), ("off", None), ("open", "not_switchable"), ("home", "not_switchable")])
async def test_group_is_judged_by_its_state(hass, state, error)           # mixed groups that report open/home are refused
async def test_fallback_target_runs_through_homeassistant_services(hass, setup_target):
    # setup "homeassistant" component; kettle.tea "off" with recording kettle.turn_on/turn_off (homeassistant.turn_on
    # forwards entity_id as a list); setup_target(target="kettle.tea");
    # set "number.tea_run_for" 10 → kettle.turn_on called; manual set_state("off") → number "0" (R3), no extra calls
```

Update `test_picker_offers_only_entities_that_can_be_switched` to the dynamic picker; `test_registry_id_of_an_unsupported_entity_is_rejected` keeps expecting `target_not_supported`.

- [ ] **Step 2: Run `uv run pytest tests/test_config_flow.py -v`** — Expected: new tests FAIL.
- [ ] **Step 3: Implement** the dynamic picker, validation and the `not_switchable` string (`en`, `ru`).
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Offer any entity with turn_on and turn_off as a target"`

---

### Task 6: Phase verification and docs

**Files:**
- Modify: `README.md`, `RULINGS.md`, `docs/followups.md`, `custom_components/timerify/manifest.json` (`"version": "0.2.0"`), `pyproject.toml` (`version = "0.2.0"`), `scripts/smoke/run.py`, `scripts/smoke/configuration.yaml`

- [ ] **Step 1: README** — sections: "Settings" (what they are, when they are applied: run, pending command even while running; never on a manual turn-on), "Supported settings per domain" (the Task 1 table, plus "other domains: none"), "Pending commands" (P1–P3 in user words, limits 20 / 7 days, restart and outage behaviour), "Services" with YAML examples for `timerify.run` (minutes + settings), `timerify.add_command` (the AC example with `response_variable`) and `timerify.cancel_command` using `{{ cmd['number.ac_run_for'].command_id }}` aimed at the same number, "Next command sensor" (state, `commands` attribute format), targets list updated with the generic fallback, `not_switchable` (fallback entities and groups whose state is not on/off) and the fan/media_player/siren feature requirement; remove pending commands from "What is not here yet"; status line 0.2.0.
- [ ] **Step 2: RULINGS.md and followups** — add a "Phase 2" part with the plan rulings below; rewrite the phase-1 entries they supersede ("No generic fallback for unlisted domains", "Climate and water heater targets are filtered by their features", "The store keeps only the end and the pending command", "The controller arms the stored end itself at start-up", "R10 logging lives in the controller", the unloaded-timer services entry for `add_command` with a response). In `docs/followups.md` remove the Phase 2 items this phase closed (mixed groups, remote/media_player re-sends, `actual_state` raise, generic fallback, smoke target on a device) and move "A deleted target gives no sign" to "Later".
- [ ] **Step 3: Smoke script** — extend the existing `scripts/smoke/configuration.yaml` (still mounted read-only by `compose.yaml`): add `demo:` (its `switch.decorative_lights` sits on a device, `homeassistant/components/demo/switch.py:22`), `input_boolean.smoke_heater_relay`, a template `switch.smoke_heater` over it, a template `sensor.smoke_temperature` (18, `device_class: temperature`, `°C`), and `climate: - platform: generic_thermostat` named "Smoke thermostat" (`heater: switch.smoke_heater`, `target_sensor: sensor.smoke_temperature`, `min_temp: 7`, `max_temp: 35`). New scenarios: (a) a timer for the demo switch, checked to sit on the switch's device in the registry (fail loudly if the demo entity or its device is missing); `add_command` `on`, `delay: 1`, `minutes: 1` → switch turns on within `TURN_ON_TIMEOUT` of the command's `at`, `next_command` back to `unknown`, off one minute later; (b) a timer for `climate.smoke_thermostat`, `timerify.run` `minutes: 1`, `hvac_mode: heat`, `temperature: 23` → thermostat state `heat`, attribute `temperature == 23`, then `off` at the end. Keep it repeatable (fresh config every run); update the module docstring; `uv run mypy` covers `scripts/`, so the new code is typed.
- [ ] **Step 4: Run hassfest** — `docker run --rm --platform linux/amd64 -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest` — Expected: no errors (services.yaml sections, anchors, selectors and translations validated).
- [ ] **Step 5: Run the smoke test** — `uv run python scripts/smoke/run.py` — Expected: every scenario passes.
- [ ] **Step 6: Run all checks on the final tree** — `uv run pytest && uv run ruff check && uv run ruff format --check && uv run mypy` — Expected: all pass; record the test count in the report.
- [ ] **Step 7: Commit** — `git commit -m "Document phase 2 and bump version to 0.2.0"`

---

## Plan rulings

Decisions neither the spec nor the design notes fix. Each: decision — why — cost if wrong.

- **Fan, media_player and siren rows require their TURN_ON/TURN_OFF features** — their `turn_on`/`turn_off` services require them in 2026.10.4, so phase 1 accepted targets it cannot switch (a phase-1 defect found while verifying) — a device that advertises no features but works is refused.
- **Required features move into the domain table in Task 1, and the config flow reads them there at once** — one place for "can be switched", no second table between Task 1 and Task 5; `switchable_by_features` judges features only, so the flow keeps a domain gate (Task 1: the table; Task 5: `offered_domains`) — Task 1 touches the config flow.
- **Climate without TURN_ON stays unsupported** although `set_hvac_mode` (no feature needed) could turn it on — a plain run without a mode would have nothing to send — such thermostats wait for a later "turn on with a default mode" option.
- **Settings types and command limits live in `const.py`** — `core.py` imports `domains.py` (for `Actual`), so the shared types cannot live in either — none.
- **Settings are `MappingProxyType` inside and `dict` at every boundary** (store, sensor attribute, service data) — immutable in the core, while `MappingProxyType` is not JSON-serialisable — none.
- **Settings are validated against capability attributes via `get_capability`/`get_supported_features`** — capability attributes stay on an unavailable state and in the registry, so commands with settings can be created during an outage; an entity known to neither gives `setting_not_supported` — a capability exposed only as a state attribute would be missed (none of the ones used are).
- **`hvac_mode` is a fixed select (HVACMode minus off); other modes are free text** — the services target the "Run for" number, so `state` selectors cannot list the device's modes; validation per target rejects wrong values; this is the service form's reading of §5.4 "only offer what the device can do", which the card and voice (phases 4–5) meet from the capabilities — users type fan/preset/operation modes by hand until the card offers them.
- **Temperature step (`target_temp_step`) is not enforced; `brightness_pct` is 1..100, `percentage` 1..100** — devices round; 0 would mean off — a device may round 22.3 to 22.5.
- **D3's "apply is separate" is the `apply_if_on` keyword on `set_duration`/`run_open`**, not a public `apply_settings` — the timer change and the push of settings onto a running target are decided separately but in one atomic core call, which meets the §5.4 bullets — a phase-3 caller that forgets `apply_if_on=False` pushes settings onto a running target (phase-3 tests must cover S1 with settings).
- **Owed settings go with the next `TurnOn`; otherwise `ApplySettings` when the target is on or a turn-on is in flight** — the lock means an in-flight turn-on has returned before the next command runs — a device slow to report "on" gets set_* calls right after its turn-on.
- **A command without settings leaves owed settings alone; only non-empty settings replace them** (also for an executed pending `on`) — settings are never invented or silently dropped — settings asked for during an outage reach the device after a later plain command.
- **"Settings applied" = every call in the list returned without error and, for a turn-on list, the target then reads as on** (attributes are not compared); a wrong state after a turn-on list fails the whole list, settings included — devices round and report late, and the re-sent turn-on must still carry the settings (P1) — a device that silently ignores a setting is not retried.
- **A failing call stops its list; the whole owed set is re-sent later through the apply list** — simple and idempotent — already-applied settings are sent twice.
- **Owed settings have their own automatic-resend counter with the wish's rules, then `GaveUp("settings")` once** — climate entities report attribute changes constantly, and RULINGS forbids unbounded re-sends — a device that applies settings only after the fourth report misses them until the next change or command.
- **The limit of automatic re-sends is per domain row: 0 for `remote` and `media_player`, `MAX_AUTOMATIC_RESENDS` otherwise; the core takes it in its constructor** — a toggle-based remote or a booting media player can be switched back off by a repeat — an ignoring media player is retried only on a state change or a command.
- **The controller's call lists, logs and `_raised_for` are labelled on / off / settings** — an apply has no wish, and `pending` is None while it runs — duplicate tracebacks if the label's settling is misjudged.
- **Tasks are vertical slices: an effect, its controller arm and its scenario tests land together** — `_execute` ends in `assert_never` and `expire` is called by the controller, so a core-only task cannot pass mypy and pytest — larger tasks to review.
- **`expire` is renamed `tick` and one alarm sits at `next_wakeup` (earlier of end and first command)** — one wake-up path for both kinds of due items — none.
- **The unavailable log of a wake-up names what was due** (the end, or a command), from the snapshot before and after `tick` — "the timer ended" is false for a command — none.
- **Catch-up folds all due items in time order, command before expiry on a tie, and wants one final state** — avoids off/on flaps after a restart and at coinciding times — a due `on` then `off` never reaches the device (intended).
- **`observe` runs catch-up first and skips R3–R5 when catch-up changed something** — generalises phase 1's "expiry outranks the report" — a manual off reported in the same instant a command fires is overridden by the command (P1).
- **Dropped commands are an effect (`CommandDropped`) logged at info by the controller** — keeps the core pure, as the phase-1 R10 ruling did — none.
- **The store reads its v2 keys strictly; the `commands` key joins version 2 in Task 3 without a further version** — the migration guarantees the keys, tolerant reads would hide a broken migration, and 0.2.0 is unreleased between Tasks 2 and 3 — none.
- **The controller notifies the entities when `end` or `commands` changed; each entity gates its own write** — the "Next command" sensor must show a command added to an idle timer — none.
- **Service name `add_command` (not `schedule_command`)**, response `{"command_id": ...}` per entity — "schedule" is phase 3's word — renaming later breaks automations.
- **`add_command` with a response variable aimed at an unloaded timer raises Home Assistant's "did not match any entities" error** instead of the phase-1 warning — re-implementing target resolution is what the phase-1 services ruling rejects — none.
- **`cancel_command` stays an entity service aimed at the owning timer; another timer answers `unknown_command`** — the card and the `add_command` response carry the entity — area-targeted cancels report an error.
- **No `cancel_commands` (all) service in this phase** — no user path needs it yet; voice can add it in phase 4 — an extra loop in automations meanwhile.
- **Exactly-one-of `delay`/`at` is checked in the method, not the schema** — schema errors are not translatable per key — none.
- **A naive `at` is Home Assistant's local time** (`dt_util.as_utc`) — the UI datetime picker sends no zone — none.
- **`at` keeps its seconds** — `delay` gives whole minutes anyway; rounding an explicit time would surprise — none.
- **Unknown command id: the core raises `KeyError`, the controller maps it to `unknown_command`** — the snapshot is the single source of truth — none.
- **The humidifier setting is called `mode`** — HA's own field name, so calls map one to one — it reads oddly next to the binding mode in the UI (the translated name says "Humidifier mode").
- **Store key `owed_settings`; commands stored with `command_to_json`, the same shape as the sensor attribute** — one serialisation — none.
- **`whole_minutes` and `whole_number` come from one factory; the settings section of `services.yaml` is written once and reused by anchor** — no duplicated logic or selectors; translations still repeat field texts per service (custom integrations get no `[%key:…%]`) — none.
- **The picker excludes the `homeassistant` domain; a domain without both services is `target_not_supported`; a fallback entity or a group whose state is not on/off (including unavailable at flow time) is `not_switchable`** — D1 read literally, and its reason (don't misread states that are not on/off) fits groups of covers or locks — such groups cannot be targets; the user retries an unavailable entity once it is back.
- **The "Next command" sensor writes state only when the command list changes; its attribute is unrecorded, proven with the recorder fixture** — §3 small recorder — one slower test.
- **Test fixtures model Home Assistant's unavailable state: only capability attributes and `supported_features` stay** — so validation-while-unavailable tests match reality — none.
- **Smoke settable target: a `generic_thermostat` over template entities; smoke target on a device: the `demo` switch** — built into HA; the existing versioned `configuration.yaml` stays mounted read-only — the script breaks (loudly) if those YAML platforms or demo entity ids change.
- **Deferred: a deleted target still gives no sign** — the spec is silent and it changes no spec-defined behaviour; it stays in `docs/followups.md` (moved to "Later") — timers of deleted targets stay silent until a later phase.
