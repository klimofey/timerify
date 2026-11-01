# Timerify 1.1.0 Part B (Timer and Interval Forms, Entities) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the form and entity issues of Part B (#35, #37, #15, #16, #40). A timer chooses the maximum of its Run for slider. A checkbox adds a "Turn off" button entity. A generated interval title is marked, so it follows the language of the house. An interval keeps a setting the device no longer offers, with a warning in Repairs. The integration page that does not re-render (#40) is reproduced, then fixed or labelled `upstream`.

**Architecture:** No new subsystem. The two new timer options are read where the entities are made: `number.py` takes the maximum, and a new `button.py` platform adds the button. The form rules stay in `config_flow.py`. The title mark is a key of the subentry data, written by the interval flow and by a config entry migration in `__init__.py` (minor version 2). The settings warning reuses `issues.py`: one more issue kind, raised and cleared by the controller, which already follows the target's state and has the intervals. #40 is an investigation on two throwaway Home Assistant containers. It changes tracked files only through RULINGS and the follow-ups list, unless it finds Timerify at fault.

**Tech Stack:** Python 3.14, Home Assistant 2026.10.4, checked in `.venv/lib/python3.14/site-packages/homeassistant`:
- `helpers/schema_config_entry_flow.py`: `SchemaFlowError` (:26-27) is caught at :192-193, and the form shows it as `errors = {"base": str(error)}` (:285). A schema flow has no field errors of its own. A failed selector raises `InvalidData` (`data_entry_flow.py:90-103`, :366-378), which the HTTP view returns as untranslated text (`helpers/data_entry_flow.py:124-125`). A schema step may be a callable (`_get_schema`, :170-177). Suggested values default to the flow's options (:266-277).
- `components/number/__init__.py`: `native_max_value` reads `_attr_native_max_value` first (:274-284). The state attributes carry `max` (`capability_attributes`, :216-235). The state is not clamped (:338-340). `components/number/services.py:16-29`: `number.set_value` refuses a value above `max_value` with `ServiceValidationError(translation_domain="number", translation_key="out_of_range")` before the entity sees it.
- `components/button/__init__.py`: `ButtonEntityDescription` (:63), `ButtonEntity` (:74), whose state is the time of the last press, restored (:104-130). The press service runs `_async_press_action` (:115-122), which writes the state, then awaits `async_press` (:136). `generated/entity_platforms.py:17`: `Platform.BUTTON`. `components/homeassistant/exposed_entities.py:32-44`: `button` is not exposed to Assist by default.
- `helpers/issue_registry.py`: `async_create_issue(hass, domain, issue_id, *, data, is_fixable, is_persistent, severity, translation_key, translation_placeholders)` (:339-353), `IssueSeverity.WARNING` (:46-51), `async_delete_issue` (:415-421; deleting a missing issue is not an error).
- Config entry versions: `MINOR_VERSION = 1` is the default of every flow handler (`data_entry_flow.py:643-644`). `ConfigEntry.async_migrate` (`config_entries.py:1234-1290`) calls the component's `async_migrate_entry(hass, entry) -> bool` when the minor version differs. An entry of a newer minor version and the same major version loads without migration, so a downgrade to 1.0.0 still loads (:1278-1281). `async_update_entry(entry, *, minor_version=...)` (:2668-2683) and `async_update_subentry(entry, subentry, *, data, title)` (:2840-2884).
- The integration page renames a subentry with the websocket command `config_entries/subentries/update`, which changes only its title (`components/config/config_entries.py:803-841`). Any change of an entry or a subentry runs its update listeners and dispatches `ConfigEntryChange.UPDATED` (`config_entries.py:2799-2810`). The frontend follows that through `config_entries/subscribe` (`components/config/config_entries.py:677-720`), which sends `as_json_fragment` with `num_subentries` (`config_entries.py:676-703`).
- `helpers/translation.py:335-358`: `async_get_translations(hass, language, category, integrations)` loads any top-level category of the translation files, `config_subentries` too.
- `helpers/entity.py:142-154`: `get_capability` reads the state first and the registry entry second, as `domains._capabilities_of` does.
- The control for #40, `components/kitchen_sink`: it has subentries (`config_flow.py:49-55`, `SubentryFlowHandler` :119-140) and reloads on every update (`__init__.py:111`, :129-131). It is set up only from YAML (`async_step_import`, `config_flow.py:58`).

**Spec:** `docs/superpowers/specs/2026-11-01-release-1.1.0-design.md`, section "Part B". It extends the base spec `docs/superpowers/specs/2026-10-28-timerify-design.md` and `RULINGS.md`. Each issue's "Where" and "Fix" are binding: `gh issue view N`. The decisions follow the base spec's rules:
- one timer is the single source of truth;
- manual wins;
- R2: an explicit 0 or stop turns the target off, in both modes.

**Starting point:** `main` at dc07549, the merge of part A (PR #44): pytest 2086 passed, vitest 241 passed, E2E 42 passed.

## Global Constraints

- Home Assistant `>= 2026.10.4` (`hacs.json`), Python `>= 3.14.2`, `pytest-homeassistant-custom-component==0.13.375`. No new runtime or dev dependency, and no change to `manifest.json`. hassfest confirms that the `button` platform needs none.
- Only public Home Assistant APIs, checked in `.venv` before use. mypy is strict, and schemas use `probatio`.
- Tests are user scenarios with frozen time (`freezer`, `advance`, `advance_to`, `restart_after`). No `asyncio.sleep`, no polling and no backdoors. Product code gets no test-only branch. An existing test is edited only where a task names it.
- A test name fits the 88 columns of `async def <name>(`, so 77 characters at most.
- User-facing strings go in `translations/en.json` (the source) and `translations/ru.json`, with the same keys and the same `{blanks}` (`tests/test_translations.py`). Cyrillic is allowed only in `ru.json` and `docs/ru/`. Write the Russian strings as translations of the English ones. Take Russian Home Assistant screen names from `python3 .superpowers/ui-names/ui-term.py "<English name>"`, for example "Repairs", "Configure", "Rename" and "Press". In Russian, use the product's existing term for pending commands, as in ru.json (not the word for Home Assistant's delayed commands).
- After every change to `en.json`, run `npm --prefix card run build` and commit `custom_components/timerify/frontend/timerify-card.js` with the task: `build:check` fails on any change of `en.json` (#43, part E). Then `npm --prefix card run build:check` must pass.
- A user-visible change updates `docs/en/<page>.md` and `docs/ru/<page>.md` in the same commit. Keep the same `##` and `###` headings (`tests/test_docs.py`) and the CLAUDE.md "User documentation" style: short sentences, "you", no long dashes, no rule ids, and no internal words. Name fields as the form names them. Leave the screenshots: the release's smoke test retakes them.
- Every task ends with these passing: `uv run pytest`, `uv run ruff check`, `uv run ruff format --check` and `uv run mypy`. A task that changes `translations/` or adds a platform also runs hassfest: `docker run --rm --platform linux/amd64 -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest`.
- English only. Commit messages are a plain sentence-case subject, with no attribution lines. Never use `--no-verify`. `git add` only the files of the task.
- RULINGS: Task 1 adds a subsection `### Forms and entities` under `## Release 1.1.0`, after "### Engine and reliability". Later tasks append their bullets to it, in the existing style: a bold decision, then "Why:", then "Cost if wrong:", then the tests that pin it.
- `docs/followups.md`: Task 3 deletes the #15 line, Task 4 the #16 line.
- Docker: start, stop or remove only the containers a task names. Other projects' containers run on this machine.
- Nothing is opened, commented or labelled in any `home-assistant/*` repository. Reporting upstream needs the owner's consent.
- The PR body names "Closes #35, #15, #16" (and #40 only if Task 5 fixes it). It says "Part of #37: the button entity; the card option is part E". #37 stays open.

## Review Focus

1. **The maximum is lowered while a longer countdown runs.** The countdown runs in full. Run for shows its minutes, above the slider's end, and the device turns off at the old end. Test: Task 1, `test_lowering_the_maximum_keeps_a_longer_countdown_running`.
2. **A new strict timer gets a maximum below the default duration of 30 minutes.** The duration form opens at the maximum, not at 30, so taking every default still works. Test: Task 1, `test_the_duration_form_starts_at_a_maximum_below_thirty`.
3. **The target of a timer with settings in its intervals is deleted.** Only the repair of the deleted target is raised, not a settings warning for each interval. Test: Task 4, `test_a_deleted_ac_raises_no_settings_warning`.
4. **The user renames a generated interval on the integration page, then edits it.** The name is the user's from the rename on, and it is kept. Test: Task 3, `test_a_renamed_interval_keeps_its_name_after_the_language_changed`.
5. **The Turn off box is unticked.** The button goes from the registry, not only from the states, so no unavailable entity is left on the device. Ticked again, it comes back with its entity id. Test: Task 2, `test_unticking_the_box_removes_the_button`.

---

## File Structure

```
custom_components/timerify/
  const.py        CONF_RUN_FOR_MAX, run_for_max_minutes (T1); CONF_OFF_BUTTON, KEY_TURN_OFF (T2);
                  CONF_GENERATED_TITLE, TRANSLATION_LANGUAGES (T3)
  config_flow.py  maximum field and duration checks (T1); Turn off box (T2);
                  title mark (T3); keep settings not offered (T4); MINOR_VERSION 2 (T3)
  number.py       the maximum of the slider (T1)
  button.py       new: the Turn off button (T2)
  entity.py       remove_timer_entity, shared with sensor.py (T2)
  sensor.py       _remove_runtime_entry uses remove_timer_entity (T2)
  __init__.py     Platform.BUTTON (T2); async_migrate_entry (T3)
  schedule.py     async_title_labels and the selector keys, moved from config_flow (T3)
  domains.py      settings_not_taken (T4)
  issues.py       the settings warning (T4)
  controller.py   raises and clears the settings warnings (T4)
  translations/en.json, ru.json   (T1 to T4)
  frontend/timerify-card.js        rebuilt after each en.json change (T1 to T4)
tests/
  conftest.py     setup_target(run_for_max=, off_button=) (T1, T2)
  helpers.py      BUTTON, press_button (T2)
  test_config_flow.py (T1, T2), test_duration_bounds.py (T1), test_entities.py (T2)
  test_button.py new (T2), test_unique_ids.py (T2)
  test_interval_flow.py (T3, T4), test_migration.py new (T3), test_translations.py (T3)
  test_repairs.py (T4)
docs/en, docs/ru: timers.md, card.md (T1, T2); schedules.md (T3, T4)
RULINGS.md (T1 to T5), docs/followups.md (T3, T4, T5)
```

---

### Task 1: Choose the maximum of Run for per timer (#35)

**Files:**
- Modify:
  - `custom_components/timerify/const.py`.
  - `custom_components/timerify/config_flow.py`: `_target_schema` (`:171-185`), `_validate_target` (`:188-222`), `_validate_duration` (`:232-239`), `_DURATION_STEP` (`:298-308`), `_options_init_schema` (`:406-422`) and `OPTIONS_FLOW["init"]` (`:444`).
  - `custom_components/timerify/number.py`: `RunForNumber` (`:35-46`).
  - `translations/en.json` and `ru.json`: `config.step.target`, `options.step.init`, `config.error` and `options.error`.
  - `tests/conftest.py`: `setup_target` (`:809-860`).
  - `tests/helpers.py`: `change_options` moves here from `tests/test_config_flow.py:131-141`, unchanged, for `test_duration_bounds.py` and `test_button.py`.
  - `tests/test_config_flow.py`: the exact options dicts of `test_add_strict_target_in_two_steps` (`:158-164`), `test_add_loose_target_skips_duration` (`:178-183`), `test_add_target_with_every_default_takes_three_clicks` (`:193-199`) and the tests at `:752`, `:965`, `:1003` and `:1044` gain `CONF_RUN_FOR_MAX: 1440`.
  - `docs/en/timers.md`, `docs/ru/timers.md`, `docs/en/card.md`, `docs/ru/card.md`.
  - `RULINGS.md`.
- Test: `tests/test_config_flow.py`, `tests/test_duration_bounds.py`.

**Interfaces:**
- Consumes: `MAX_MINUTES` (`const.py:43`) and `default_duration_minutes` (`const.py:153-157`).
- Produces:
  - `const.py`: `CONF_RUN_FOR_MAX: Final = "run_for_max"`, the option holding the end of the Run for slider in whole minutes. An entry of an earlier release has none. `run_for_max_minutes(options: Mapping[str, Any]) -> int` returns the option, or `MAX_MINUTES` without one.
  - `config_flow.py`:
    - The first form of a new timer (`_target_schema`) and of its settings (`_options_init_schema`) gain `probatio.Required(CONF_RUN_FOR_MAX, default=MAX_MINUTES): _duration_selector()`, after `CONF_RUNTIME`. The selector stays 1 to 1440, in a box, in minutes.
    - `_whole_minutes(user_input: dict[str, Any], key: str) -> dict[str, Any]` raises `SchemaFlowError("duration_not_whole")` for a fraction, and returns the input with `key` as an `int`. `_validate_duration` uses it for `CONF_DEFAULT_DURATION`. `_validate_target` uses it for `CONF_RUN_FOR_MAX`, after its checks of the target.
    - `_validate_timer_settings(handler, user_input) -> dict[str, Any]` is the `validate_user_input` of `OPTIONS_FLOW["init"]`. It applies `_whole_minutes` to `CONF_RUN_FOR_MAX`.
    - `_duration_schema(handler) -> probatio.Schema` replaces the fixed schema of `_DURATION_STEP`. Its default is `min(DEFAULT_DURATION_MINUTES, run_for_max_minutes(handler.options))`.
    - `_validate_duration(handler, user_input)` raises `SchemaFlowError("duration_above_maximum")` when the minutes are more than `run_for_max_minutes(handler.options)`. The selector keeps 1440 as its end, so the error is this translated one, not the untranslated `InvalidData` of a selector.
  - `number.py`: `RunForNumber.__init__(self, hass, entry)` calls the base and sets `self._attr_native_max_value = run_for_max_minutes(entry.options)`.
  - `en.json` (the same strings in `config` and `options`):
    - `step.target.data.run_for_max` and `step.init.data.run_for_max`: "Maximum of Run for".
    - Their `data_description.run_for_max`: "The end of the Run for slider, in minutes, up to 1440 (one day). Actions, voice, pending commands and schedules can still run the device for up to a day."
    - `error.duration_above_maximum`: "The default duration must not be longer than the maximum of Run for."
  - `tests/conftest.py`: `setup_target(..., run_for_max: int | None = None)` puts `CONF_RUN_FOR_MAX` in the options when given.

- [ ] **Step 1: Write the failing tests** in `tests/test_config_flow.py`:

```python
async def test_the_first_form_asks_for_the_maximum_of_run_for(hass, fake_target)
    # result = await start_flow(hass): default_value(result, CONF_RUN_FOR_MAX) == 1440;
    # the selector serializes to {"number": {"min": 1, "max": 1440, "step": 1, "mode": "box", "unit_of_measurement": "min"}};
    # submit {CONF_TARGET: TARGET_ID, CONF_MODE: "strict", CONF_RUN_FOR_MAX: 120}, then {CONF_DEFAULT_DURATION: 45}:
    # result["options"][CONF_RUN_FOR_MAX] == 120; hass.states.get(NUMBER).attributes["max"] == 120

async def test_a_default_duration_above_the_maximum_is_refused(hass, fake_target)
    # first form with CONF_RUN_FOR_MAX: 60; submit {CONF_DEFAULT_DURATION: 90}:
    # result["step_id"] == "duration"; result["errors"] == {"base": "duration_above_maximum"};
    # submit {CONF_DEFAULT_DURATION: 60}: CREATE_ENTRY

async def test_the_duration_form_starts_at_a_maximum_below_thirty(hass, fake_target)  # Review Focus 2
    # first form with CONF_RUN_FOR_MAX: 20: default_value(result, CONF_DEFAULT_DURATION) == 20;
    # submit {}: result["options"][CONF_DEFAULT_DURATION] == 20

async def test_a_maximum_in_part_minutes_is_refused(hass, fake_target)
    # first form with CONF_RUN_FOR_MAX: 90.5: step_id "target"; errors == {"base": "duration_not_whole"}

async def test_settings_change_the_maximum_of_run_for(hass, fake_target, setup_target)
    # entry = await setup_target(); the init form: default_value(result, CONF_RUN_FOR_MAX) == 1440;
    # change_options(..., {CONF_MODE: "strict", CONF_RUNTIME: False, CONF_RUN_FOR_MAX: 120}, {CONF_DEFAULT_DURATION: 45}):
    # entry.options[CONF_RUN_FOR_MAX] == 120; attributes["max"] == 120 after the reload

async def test_lowering_the_maximum_below_the_default_duration_asks_to_lower_it(...)
    # setup_target(default_duration=45); options init with CONF_RUN_FOR_MAX: 30:
    # the duration form shows suggested_value(result, CONF_DEFAULT_DURATION) == 45;
    # submit {CONF_DEFAULT_DURATION: 45}: errors == {"base": "duration_above_maximum"}; submit 30: CREATE_ENTRY
```

  Also in `tests/test_duration_bounds.py`, with `setup_target(run_for_max=120)`:

```python
async def test_the_slider_ends_at_the_maximum_of_the_timer(...)
    # attributes["min"] == 0; attributes["max"] == 120; and setup_target() gives max == 1440

async def test_setting_run_for_above_the_maximum_is_refused(...)
    # with pytest.raises(ServiceValidationError) as err: await set_number(hass, NUMBER, 150);
    # err.value.translation_domain == "number"; err.value.translation_key == "out_of_range"; fake_target.calls == []

async def test_actions_and_commands_run_past_the_maximum(...)
    # call_service(hass, "run", {"entity_id": NUMBER, "minutes": 180}): state_of(NUMBER) == "180";
    # call_service(hass, "add_time", {"entity_id": NUMBER, "minutes": 60}): "240";
    # advance 240 min: calls == [TURN_ON, TURN_OFF];
    # add_command(hass, NUMBER, action="on", delay=1, minutes=300); advance 1 min: state_of(NUMBER) == "300"

async def test_lowering_the_maximum_keeps_a_longer_countdown_running(...)  # Review Focus 1
    # setup_target(); set_number(NUMBER, 300); change_options to CONF_RUN_FOR_MAX 120 (and the duration 45):
    # state_of(NUMBER) == "300"; attributes["max"] == 120; advance 300 min: calls == [TURN_ON, TURN_OFF]
```

  Add `CONF_RUN_FOR_MAX: 1440` to the exact options dicts of the tests named under Files.
- [ ] **Step 2: Run** `uv run pytest tests/test_config_flow.py tests/test_duration_bounds.py -v`. Expected: the new tests and the edited ones FAIL.
- [ ] **Step 3: Implement** the interfaces above, with the Russian strings in `ru.json`.
- [ ] **Step 4: Docs** (en and ru):
  - `timers.md`, "Add a timer to a device": after the step of **Count runtime**, a step: "Set **Maximum of Run for**, the end of the slider. It is 1440 minutes (one day) to begin with. If you rarely run the device for more than two hours, set 120."
  - The step of the default duration says it cannot be longer than the maximum.
  - "Change a timer later" lists the maximum among what you can change.
  - "Run a device for a set time" gains the bullets:
    - The slider of **Run for** ends at the maximum you chose.
    - Actions, voice, pending commands and schedules can still start a countdown of up to a day. **Run for** then shows more minutes than the slider's end, and the countdown runs in full.
    - The same holds when you lower the maximum while a longer countdown runs.
  - `card.md`, the `presets` row: Home Assistant refuses a preset that is longer than the timer's maximum of **Run for**.
- [ ] **Step 5: RULINGS.** Add the subsection `### Forms and entities`, and in it **"The maximum of Run for bounds the slider, not the timer."** It covers these decisions:
  - The option sets the number's `max`. Home Assistant's `number.set_value` refuses more, so the slider, the more-info dialog and the card's presets (which use `set_value`) follow it.
  - `run`, `add_time`, pending commands, voice, the LLM tools and windows keep the 1440-minute limit. A countdown they start runs in full, and the number shows its minutes above `max`. Lowering the maximum leaves a running countdown as it is.
  - The default duration may not be above the maximum. A schema flow has only `base` errors (`schema_config_entry_flow.py:285`), so the error is the base error of the duration form, whose only field it is. The selector stays 1 to 1440, so the error is translated, not a selector's text.
  - The duration form of a new timer starts at the smaller of 30 minutes and the maximum.
  - A loose timer is not checked: it has no duration form, and a stored default duration is used only in strict mode. Switching to strict shows the duration form, which checks it.

  Why: #35. The owner rarely runs a device for more than two hours. Refusing a window or a spoken "for 3 hours" would change what the base spec defines. Cost if wrong: a card preset longer than the maximum is refused with Home Assistant's own message. Tests: the ten tests of this task.
- [ ] **Step 6: Run** the gate, hassfest, `npm --prefix card run build` and `npm --prefix card run build:check`. Expected: all pass.
- [ ] **Step 7: Commit.**

```bash
git add custom_components/timerify/const.py custom_components/timerify/config_flow.py custom_components/timerify/number.py custom_components/timerify/translations/en.json custom_components/timerify/translations/ru.json custom_components/timerify/frontend/timerify-card.js tests/conftest.py tests/helpers.py tests/test_config_flow.py tests/test_duration_bounds.py docs/en/timers.md docs/ru/timers.md docs/en/card.md docs/ru/card.md RULINGS.md
git commit -m "Let each timer choose the maximum of its Run for slider"
```

### Task 2: A Turn off button entity, and Run for 0 pinned for Loose mode (#37)

**Files:**
- Create: `custom_components/timerify/button.py`, `tests/test_button.py`.
- Modify:
  - `custom_components/timerify/const.py`: the keys docstring (`:131-135`) and `timer_unique_id`'s docstring name `KEY_TURN_OFF`.
  - `custom_components/timerify/config_flow.py`: `_target_schema` and `_options_init_schema`.
  - `custom_components/timerify/__init__.py`: `PLATFORMS` (`:39`).
  - `custom_components/timerify/entity.py`, and `custom_components/timerify/sensor.py`: `_remove_runtime_entry` (`:64-76`).
  - `translations/en.json` and `ru.json`: `entity.button.turn_off`, and the box on both first forms.
  - `tests/conftest.py`: `setup_target(..., off_button: bool = False)`.
  - `tests/helpers.py`: `BUTTON = "button.boiler_turn_off"` and `press_button`.
  - `tests/test_config_flow.py`: the exact options dicts edited in Task 1 gain `CONF_OFF_BUTTON: False`.
  - `tests/test_entities.py`, `tests/test_unique_ids.py`.
  - `docs/en/timers.md`, `docs/ru/timers.md`, `RULINGS.md`.

**Interfaces:**
- Consumes: `TargetController.async_set_minutes(0)` (`controller.py:316-326`), the stop that voice uses too (`voice/timer.py:159`). `TimerifyEntity` (`entity.py:75-116`).
- Produces:
  - `const.py`: `CONF_OFF_BUTTON: Final = "off_button"`, the option holding whether the timer has a Turn off button, a `bool`. Absent or False: no button. `KEY_TURN_OFF: Final = "turn_off"`.
  - `config_flow.py`: both first forms gain `probatio.Required(CONF_OFF_BUTTON, default=False): selector.BooleanSelector()`, after `CONF_RUN_FOR_MAX`.
  - `entity.py`: `remove_timer_entity(hass: HomeAssistant, entry: TimerifyConfigEntry, domain: str, key: str) -> None` removes the registry entry of the timer's entity with the unique id `timer_unique_id(entry.entry_id, key)`, if there is one. `sensor._remove_runtime_entry` is replaced by `remove_timer_entity(hass, entry, "sensor", KEY_RUNTIME)`.
  - `button.py`:
    - `PARALLEL_UPDATES = 0`.
    - `async_setup_entry(hass, entry, async_add_entities)` adds a `TurnOffButton` when `entry.options.get(CONF_OFF_BUTTON)`. Otherwise it calls `remove_timer_entity(hass, entry, "button", KEY_TURN_OFF)`.
    - `class TurnOffButton(TimerifyEntity, ButtonEntity)` has `entity_description = ButtonEntityDescription(key=KEY_TURN_OFF, translation_key="turn_off")`. It has no entity category: it is a control of the device. `async_press` awaits `self._controller.async_set_minutes(0)`. `_handle_controller_update` writes nothing, since its state is the time of the last press.
  - `__init__.py`: `PLATFORMS = (Platform.BUTTON, Platform.NUMBER, Platform.SENSOR, Platform.SWITCH)`.
  - `en.json`:
    - `entity.button.turn_off.name`: "Turn off".
    - `config.step.target.data.off_button` and `options.step.init.data.off_button`: "Turn off button".
    - Their `data_description.off_button`: "Adds a Turn off button to the device page. Pressing it stops the countdown and turns the device off. It also turns off a device that runs without a countdown."
  - `tests/helpers.py`: `async def press_button(hass, entity_id: str) -> None` calls `button.press` with `blocking=True`, then `hass.async_block_till_done()`.

- [ ] **Step 1: Write the failing tests** in `tests/test_button.py`:

```python
async def test_a_timer_has_no_turn_off_button_unless_asked(...)
    # setup_target(): hass.states.get(BUTTON) is None; er.async_get(hass).async_get(BUTTON) is None

async def test_ticking_the_box_puts_a_turn_off_button_on_the_device(...)
    # setup_target(off_button=True): state_of(BUTTON) == "unknown";
    # attributes["friendly_name"] == "Boiler Turn off";
    # the registry entry's device_id == the one of NUMBER; its entity_category is None

async def test_pressing_turn_off_stops_the_countdown_and_the_boiler(...)
    # set_number(NUMBER, 45); press_button(BUTTON): calls == [TURN_ON, TURN_OFF];
    # state_of(NUMBER) == "0"; state_of(SENSOR) == "unknown"; state_of(BUTTON) == "2026-01-05T07:00:00+00:00"

async def test_pressing_turn_off_stops_a_loose_boiler_without_a_countdown(...)
    # setup_target(mode="loose", off_button=True); fake_target.set_state("on"); press: calls == [TURN_OFF]

async def test_pressing_turn_off_on_a_boiler_that_is_off_sends_nothing(...)
    # press: fake_target.calls == []; state_of(TARGET_ID) == "off"

async def test_unticking_the_box_removes_the_button(...)   # Review Focus 5
    # setup_target(off_button=True); change_options(... CONF_OFF_BUTTON: False ...):
    # hass.states.get(BUTTON) is None; registry.async_get(BUTTON) is None;
    # change_options(... CONF_OFF_BUTTON: True ...): state_of(BUTTON) == "unknown" at the same entity id
```

  In `tests/test_config_flow.py`, `test_the_turn_off_box_is_on_both_first_forms`: `default_value(..., CONF_OFF_BUTTON) is False` on the target form and on the init form. Ticking it on the target form stores `CONF_OFF_BUTTON: True`, and the button is there once the entry loads.

  In `tests/test_entities.py`, the R2 pin for Loose mode. No test covers a loose boiler that runs without a countdown: `test_setting_zero_turns_target_off` (`:99`) is strict, and the loose tests in `test_device_failures.py:336-400` stop a reported-late run.

```python
@pytest.mark.parametrize("started", ["by_hand", "by_run"])
async def test_run_for_zero_turns_off_a_loose_boiler_without_a_countdown(...)
    # setup_target(mode="loose"); by_hand: fake_target.set_state("on"); by_run: call_service(hass, "run", {"entity_id": NUMBER});
    # state_of(NUMBER) == "0"; set_number(NUMBER, 0): the last call is TURN_OFF; state_of(TARGET_ID) == "off"
```

  In `tests/test_unique_ids.py`, `test_the_turn_off_button_has_the_unique_id_of_its_key`: the registry entry of `BUTTON` has `unique_id == f"{entry.entry_id}_turn_off"`.
- [ ] **Step 2: Run** `uv run pytest tests/test_button.py tests/test_config_flow.py tests/test_entities.py tests/test_unique_ids.py -v`. Expected: the new tests FAIL. The R2 pin may already PASS: it pins existing behaviour, and it stays.
- [ ] **Step 3: Implement** the interfaces above, with the Russian strings in `ru.json`.
- [ ] **Step 4: Docs** (en and ru), `timers.md`:
  - "Add a timer to a device" gains a step after the maximum: "Turn on **Turn off button** if you want a button that turns the device off. It is off to begin with."
  - "Change a timer later" lists the button among what you can change.
  - The table of "What a timer adds to the device page" gains a row: **Turn off** (a button), "Only when you ask for it. Pressing it stops the countdown and turns the device off. It also turns off a device that runs without a countdown, in Loose mode."
  - "Run a device for a set time": the bullet "Set **Run for** to 0" says that this also turns off a device that runs without a countdown.
- [ ] **Step 5: RULINGS.** Add **"The Turn off button is the stop command, and only an option adds it."** It covers these decisions:
  - Pressing is `async_set_minutes(0)`, the stop of voice and of Run for 0. So it ends a countdown, turns off a Loose device without one, holds a started window until its next occurrence (S4), and sends nothing to a device that is off.
  - The button has no entity category, because it switches the device. `button` is not exposed to Assist by default, so it adds no phrase that competes with "turn off the boiler".
  - Unticking removes the registry entry, as for the Runtime sensor. Both use `remove_timer_entity`.
  - The card option of #37 is part E.

  Why: #37. Cost if wrong: an automation that presses the button while a schedule window is open stops the device until the next window.
- [ ] **Step 6: Run** the gate, hassfest, `npm --prefix card run build` and `build:check`. Expected: all pass.
- [ ] **Step 7: Commit.**

```bash
git add custom_components/timerify/button.py custom_components/timerify/const.py custom_components/timerify/config_flow.py custom_components/timerify/__init__.py custom_components/timerify/entity.py custom_components/timerify/sensor.py custom_components/timerify/translations/en.json custom_components/timerify/translations/ru.json custom_components/timerify/frontend/timerify-card.js tests/conftest.py tests/helpers.py tests/test_button.py tests/test_config_flow.py tests/test_entities.py tests/test_unique_ids.py docs/en/timers.md docs/ru/timers.md RULINGS.md
git commit -m "Add a Turn off button entity that a timer's settings switch on"
```

### Task 3: A generated interval title follows the language of the house (#15)

**Files:**
- Modify:
  - `custom_components/timerify/const.py`.
  - `custom_components/timerify/schedule.py`: next to `interval_title` (`:128-141`).
  - `custom_components/timerify/config_flow.py`: `_WEEKDAY_SELECTOR`, `_DAYS_SELECTOR` and `_DAYS_MODES` (`:454-460`) move to `schedule.py`. `_async_interval_step` (`:514-552`) changes, `_async_day_labels` (`:646-664`) goes, and `MINOR_VERSION = 2` joins `VERSION` (`:677`).
  - `custom_components/timerify/__init__.py`: a new `async_migrate_entry`.
  - `tests/test_interval_flow.py`: the exact data dicts of `test_adding_an_interval_stores_it_with_a_readable_title` (`:126`), `test_editing_an_interval_updates_data_and_title` (`:545`) and `test_workday_interval_titles` (`:842`) gain `"generated_title": <the title the test asserts>`.
  - `tests/test_translations.py`, `docs/en/schedules.md`, `docs/ru/schedules.md`, `RULINGS.md`, `docs/followups.md`.
- Create: `tests/test_migration.py`.

**Interfaces:**
- Consumes: `interval_title(data, labels)` (`schedule.py:128`), `async_get_translations` and `async_update_subentry`.
- Produces:
  - `const.py`:
    - `CONF_GENERATED_TITLE: Final = "generated_title"`. It is subentry data: the title Timerify gave the interval. The title counts as generated while the subentry's title still equals it. A rename on the integration page changes only the title (`config_entries/subentries/update`), so it ends the mark by itself, which a bare flag could not tell.
    - `TRANSLATION_LANGUAGES: Final = ("en", "ru")`, the languages of `translations/`.
  - `schedule.py`:
    - `WEEKDAY_SELECTOR: Final = "weekday"`, `DAYS_SELECTOR: Final = "interval_days"` and `DAYS_MODES: Final[tuple[DaysMode, ...]]`, moved from `config_flow.py` unchanged.
    - `async def async_title_labels(hass: HomeAssistant, language: str) -> dict[str, str]` is the body of `_async_day_labels`, for any language.
  - `config_flow.py`, `_async_interval_step`:
    - A new interval is created with `data={**data, CONF_GENERATED_TITLE: title}`.
    - An edit regenerates the title when `subentry.title == subentry.data.get(CONF_GENERATED_TITLE)`. It uses the labels of `hass.config.language`, and stores the new title under the key too. Otherwise the edit keeps the title and stores no key.
  - `TimerifyConfigFlowHandler.MINOR_VERSION = 2`.
  - `__init__.py`: `async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool`. For an entry below minor version 2, it builds the labels of every language of `TRANSLATION_LANGUAGES`. Then, for each interval subentry whose title equals `interval_title(subentry.data, labels)` in any of them, it calls `async_update_subentry(entry, subentry, data={**subentry.data, CONF_GENERATED_TITLE: subentry.title})`. Last it calls `async_update_entry(entry, minor_version=2)` and returns True. The voice settings entry only moves to minor version 2.

- [ ] **Step 1: Write the failing tests.** In `tests/test_interval_flow.py`:

```python
async def test_a_new_interval_is_marked_as_titled_by_timerify(...)
    # add_interval 06:30-07:15: data["generated_title"] == subentry.title == "06:30–07:15, Mon–Sun"

async def test_an_edit_after_the_language_changed_renames_the_interval(...)
    # hass.config.language = "ru"; add_interval 06:30-07:15; hass.config.language = "en";
    # edit_interval(end="07:30"): title == "06:30–07:30, Mon–Sun"; data["generated_title"] == that title;
    # the switch's friendly name is "Boiler Schedule 06:30–07:30, Mon–Sun"

async def test_a_renamed_interval_keeps_its_name_after_the_language_changed(...)  # Review Focus 4
    # hass.config.language = "ru"; add_interval; retitle_interval(..., "Morning"); hass.config.language = "en";
    # edit_interval(end="07:30"): title == "Morning"; "generated_title" not in data
```

  `test_editing_keeps_a_title_the_user_chose` (`:613`) stays as it is and must still pass.

  In `tests/test_migration.py`, entries of minor version 1 made with `MockConfigEntry(domain=DOMAIN, version=1, minor_version=1, title="Boiler", options=..., subentries_data=[...])`, set up with `hass.config.language = "en"`:

```python
async def test_a_title_generated_in_english_is_marked(...)
    # subentry "06:30–07:15, Mon–Sun": entry.minor_version == 2; data["generated_title"] == "06:30–07:15, Mon–Sun"

async def test_a_title_generated_in_russian_is_marked_in_an_english_house(...)
    # title from interval_title(data, await async_title_labels(hass, "ru")): it is marked;
    # edit_interval(end="07:30"): title == "06:30–07:30, Mon–Sun"

async def test_a_title_of_working_days_is_marked(...)
    # days "workdays", with a Workday sensor: "06:30–07:15, Working days" is marked

async def test_a_title_the_user_chose_is_not_marked(...)
    # subentry "Morning": "generated_title" not in data; entry.minor_version == 2; edit keeps "Morning"

async def test_the_voice_settings_entry_is_migrated_too(...)
    # a voice settings entry of minor version 1 loads; its minor_version == 2
```

  In `tests/test_translations.py`, `test_the_translation_languages_are_the_files`: `set(TRANSLATION_LANGUAGES) == set(LANGUAGES)`.
- [ ] **Step 2: Run** `uv run pytest tests/test_interval_flow.py tests/test_migration.py tests/test_translations.py -v`. Expected: the new tests and the edited ones FAIL.
- [ ] **Step 3: Implement** the interfaces above.
- [ ] **Step 4: Docs** (en and ru), `schedules.md`, "Add, edit and delete an interval". The paragraph on names says:
  - A name that Timerify made follows the edit, in the language Home Assistant is set to at that time.
  - If you rename the interval on the integration page, the name is yours. It is kept when you edit the interval.
- [ ] **Step 5: RULINGS.** Add **"A generated interval title is marked by the title itself, kept in the subentry data."** It covers these decisions:
  - The mark holds while the title equals `generated_title`. A rename ends it with no hook of ours.
  - The migration marks a title that equals the generated one in any shipped language. A user title that happens to equal a generated one is taken as generated, which the edit then renames.
  - Minor version 2 keeps a downgrade to 1.0.0 loading. That release ignores the key, and its old rule still applies.

  Why: #15. Cost if wrong: a title typed to look generated is renamed by an edit.
- [ ] **Step 6: Run** the gate and hassfest. Expected: all pass. No string changes, so no rebuild.
- [ ] **Step 7: Commit.** Delete the #15 line from `docs/followups.md`.

```bash
git add custom_components/timerify/const.py custom_components/timerify/schedule.py custom_components/timerify/config_flow.py custom_components/timerify/__init__.py tests/test_interval_flow.py tests/test_migration.py tests/test_translations.py docs/en/schedules.md docs/ru/schedules.md RULINGS.md docs/followups.md
git commit -m "Mark generated interval titles and rename them in the current language on edit"
```

### Task 4: An interval keeps a setting the device no longer offers, with a warning (#16)

**Files:**
- Modify:
  - `custom_components/timerify/domains.py`: next to `validate_settings` (`:617-647`).
  - `custom_components/timerify/config_flow.py`: `_async_interval_step` (`:542-552`, the `opened` flag) and `_interval_from` (`:602-644`).
  - `custom_components/timerify/issues.py`.
  - `custom_components/timerify/controller.py`: `__init__`, `async_start` (`:289-304`), `_handle_started` (`:823-861`) and `_handle_state_change` (`:878-895`).
  - `translations/en.json` and `ru.json`: `issues.settings_not_taken`.
  - `docs/en/schedules.md`, `docs/ru/schedules.md`, `RULINGS.md`, `docs/followups.md`.
- Test: `tests/test_interval_flow.py`, `tests/test_repairs.py`.

**Interfaces:**
- Consumes: `supported_settings` and `validate_settings` (`domains.py:598-647`). `_target_exists` and `_target_deleted` (part A, `controller.py:897-931`). `issues._async_raise` and `issue_id` (`issues.py:22-44`).
- Produces:
  - `domains.py`: `settings_not_taken(hass: HomeAssistant, entity_id: str, settings: Settings) -> tuple[str, ...]`. It returns the names in `settings` that the entity cannot take now, in their order. Each is judged alone by `validate_settings`, as `_settings_the_target_takes` does when it sends them. A name whose value is no longer accepted counts too.
  - `config_flow.py`:
    - `_interval_from(entry, user_input, stored: Mapping[str, Any])`. The step passes `subentry.data[CONF_SETTINGS]` for an edit and `{}` for a new interval. The saved settings are the validated ones of the form, then the stored settings whose name the form does not offer (`supported_settings`), untouched.
    - The section is open when a shown setting is one the form offers.
  - `issues.py`:
    - `SETTINGS_NOT_TAKEN: Final = "settings_not_taken"`, added to `IssueKind`.
    - `_async_raise` takes `issue_id: str`, `fixable: bool` and `severity: ir.IssueSeverity`. With `fixable=False` it passes `data=None`. The two existing raises keep `fixable=True` and `ERROR`.
    - `interval_issue_id(entry_id: str, subentry_id: str) -> str` returns `f"settings_not_taken_{entry_id}_{subentry_id}"`.
    - `@callback async_raise_settings_not_taken(hass, entry, subentry: ConfigSubentry, settings: str) -> None` raises with `is_fixable=False`, `severity=IssueSeverity.WARNING` and `translation_placeholders={"timer": entry.title, "interval": subentry.title, "settings": settings}`.
    - `@callback async_clear_settings_not_taken(hass, entry_id: str, subentry_id: str) -> None`.
  - `TargetController`:
    - `self._settings_warned: dict[str, tuple[str, ...]]` maps a subentry id to the names its issue was raised with.
    - `async def _async_check_interval_settings(self) -> None`. For each interval it gets the names: `()` while `not self._target_exists()`, else `settings_not_taken(...)` of its settings. It raises the issue when the names are not empty and differ from the ones it raised with. It clears it when they are empty and it raised one.
    - The `settings` placeholder joins the form's labels with ", ". The labels come from `async_get_translations(hass, hass.config.language, "config_subentries", [DOMAIN])` under `component.timerify.config_subentries.interval.step.user.sections.settings.data.<name>`. `test_every_field_of_the_form_is_labelled` already guarantees that every name has one.
    - `_handle_started` awaits it after `_set_target_deleted(...)`. `_handle_state_change` awaits it after its deleted check, for every report of the target.
    - `async_start` registers `entry.async_on_unload(self._clear_settings_warnings)`, which clears every issue in `_settings_warned`. The warning lives with the loaded timer, like the deleted-target repair. Every change of an interval reloads the timer, so an edit or a deletion clears the old warnings, and the start-up judges again.
  - `en.json`, under `issues`:

```json
"settings_not_taken": {
  "title": "A schedule interval of the timer {timer} has settings the device does not take",
  "description": "The schedule interval {interval} of the timer {timer} turns the device on with settings that the device does not take now: {settings}. Timerify keeps them, and leaves them out when the interval turns the device on. If the device takes them again, they are used again and this message goes away. If the form of the interval shows a setting, pick a value the device takes. To drop a setting the form no longer shows, delete the interval and add it again."
}
```

- [ ] **Step 1: Write the failing tests.** In `tests/test_interval_flow.py`, with `fake_climate`:

```python
async def test_editing_keeps_a_setting_the_ac_no_longer_offers(...)
    # add_interval settings {"hvac_mode": "cool", "temperature": 24, "fan_mode": "low"};
    # fake_climate.capability_attributes["supported_features"] = AC features without FAN_MODE; set_state("off");
    # form = edit form: "fan_mode" not in settings_fields(form);
    # edit_interval(end="07:30"): dict(data["settings"]) == {"hvac_mode": "cool", "temperature": 24, "fan_mode": "low"}

async def test_an_interval_with_only_settings_not_offered_shows_them_closed(...)
    # interval with {"fan_mode": "low"}; FAN_MODE removed: settings_are_open(form) is False
```

  In `tests/test_repairs.py`, with `fake_climate` and `setup_target(target=AC_ID)`. Look the issue up with `ir.async_get(hass).async_get_issue(DOMAIN, f"settings_not_taken_{entry.entry_id}_{subentry_id}")`.

```python
async def test_an_interval_setting_the_ac_no_longer_takes_raises_a_warning(...)
    # interval {"hvac_mode": "cool", "temperature": 24}; capability_attributes["hvac_modes"] = ["off", "heat"]; set_state("off"):
    # issue.severity == "warning"; not issue.is_fixable; issue.translation_key == "settings_not_taken";
    # issue.translation_placeholders == {"timer": "Boiler", "interval": subentry.title, "settings": "HVAC mode"}

async def test_the_warning_names_every_setting_the_ac_does_not_take(...)
    # interval {"hvac_mode": "cool", "temperature": 24, "fan_mode": "low"};
    # hvac_modes lose "cool" and FAN_MODE goes: "settings" == "HVAC mode, Fan mode"

async def test_the_warning_clears_when_the_ac_takes_the_setting_again(...)
    # hvac_modes back to AC_ATTRS; set_state("off"): the issue is gone

async def test_the_warning_clears_when_the_interval_no_longer_holds_it(...)
    # edit_interval(settings={"hvac_mode": "heat", "temperature": 24}): the issue is gone

async def test_deleting_the_interval_clears_its_warning(...)
    # hass.config_entries.async_remove_subentry(entry, subentry_id); block: the issue is gone

async def test_a_setting_lost_while_down_raises_the_warning_at_start_up(...)
    # restart_after(..., while_down=<narrow hvac_modes and write the state>): the issue exists

async def test_an_unavailable_ac_raises_no_settings_warning(...)
    # fake_climate.set_state("unavailable"): no settings_not_taken issue (the capabilities stay on the state)

async def test_a_deleted_ac_raises_no_settings_warning(...)   # Review Focus 3
    # narrowed hvac_modes raised the warning; fake_climate.delete(): the settings issue is gone;
    # only target_deleted_<entry_id> is open; fake_climate.restore("off"): the settings warning is back

async def test_the_warnings_of_a_timer_go_with_it(...)
    # warning raised; hass.config_entries.async_remove(entry.entry_id): no issue of DOMAIN is left
```

  No new test for the run-time skip. Part A pins it: `test_a_climate_without_capabilities_keeps_the_settings_of_its_window` and `test_setting_the_ac_no_longer_takes_is_left_out_and_said_once`.
- [ ] **Step 2: Run** `uv run pytest tests/test_interval_flow.py tests/test_repairs.py -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** the interfaces above, with the Russian strings in `ru.json`.
- [ ] **Step 4: Docs** (en and ru), `schedules.md`, "Settings of an interval", new bullets:
  - Suppose a device stops offering a setting of an interval, for example after an update of its integration. Editing the interval keeps the setting as it is, though the form no longer shows it.
  - While the device does not take it, **Settings > System > Repairs** shows a warning. It names the interval and the setting.
  - When the interval turns the device on, that setting is left out, and the log says so. The other settings go out.
  - The warning goes away when the device takes the setting again. It also goes when you pick a value the device takes, or delete the interval.
- [ ] **Step 5: RULINGS.** Add **"An interval keeps a setting the form no longer offers, and a warning stands while the device does not take it."** It covers these decisions:
  - The edit keeps only names the form does not show. A shown name has the user's value.
  - The warning is judged as the run-time filter judges (`settings_not_taken`, through `validate_settings`), so it stands exactly while the window would leave the setting out. That includes a value no longer accepted, which the form shows and the user can change.
  - There is one warning per interval, naming all its settings, with the form's labels in the house language.
  - It lives with the loaded timer, so a reload clears it and the start-up raises it again. There is none while the target is deleted, whose repair speaks for it.
  - There is no fix flow (spec). Deleting the interval drops a setting the form no longer shows.

  Why: #16. Cost if wrong: a user who never opens Repairs keeps a setting that is never sent, and the log is the only other trace.
- [ ] **Step 6: Run** the gate, hassfest, `npm --prefix card run build` and `build:check`. Expected: all pass.
- [ ] **Step 7: Commit.** Delete the #16 line from `docs/followups.md`.

```bash
git add custom_components/timerify/domains.py custom_components/timerify/config_flow.py custom_components/timerify/issues.py custom_components/timerify/controller.py custom_components/timerify/translations/en.json custom_components/timerify/translations/ru.json custom_components/timerify/frontend/timerify-card.js tests/test_interval_flow.py tests/test_repairs.py docs/en/schedules.md docs/ru/schedules.md RULINGS.md docs/followups.md
git commit -m "Keep interval settings the device no longer offers, with a warning in Repairs"
```

### Task 5: Reproduce the integration page that does not re-render (#40)

This is an investigation. It runs two throwaway containers and edits no tracked file until Step 7. Keep its scripts and configuration in the session scratchpad, written `<scratch>` below.

**Files:**
- Modify: `RULINGS.md`, `docs/followups.md`.

- [ ] **Step 1: Check the clocks and pick the images.** Compare `date -u +%s` with `docker run --rm alpine date -u +%s` (within 2 seconds). Use two images:
  - A: `ghcr.io/home-assistant/home-assistant:2026.10.4`;
  - B: `2026.11.0` if `docker pull` finds it, otherwise the newest 2026.11 beta (`2026.11.0b2` is present locally).
- [ ] **Step 2: Start the containers.** For each of A (port 18125) and B (port 18126), make `<scratch>/repro-40/<a|b>/` with a copy of `scripts/harness/configuration.yaml` that adds the line `kitchen_sink:` (`local_calendar` needs no YAML). Then run, with `b`, 18126 and image B for the second:

```bash
docker run -d --name timerify-repro-40-a -p 127.0.0.1:18125:8123 -e TZ=UTC \
  -v <scratch>/repro-40/a:/config \
  -v /Users/klimofey/GIT/timerify/custom_components:/config/custom_components:ro \
  ghcr.io/home-assistant/home-assistant:2026.10.4
```

  Ports 18123 (smoke) and 18124 (E2E) stay free. Onboard each one with a scratch script (`PYTHONPATH=/Users/klimofey/GIT/timerify uv run python <scratch>/repro-40/setup.py`). It uses `scripts/harness/hass.py`: `Instance("timerify-repro-40-a", 18125, <dir>)` only for its URLs, then `wait_until_up`, `onboard`, `new_access_token` and `open_socket`. It writes the token to `<scratch>`.
- [ ] **Step 3: Drive the page with a scratch Playwright script** (`NODE_PATH=card/node_modules node <scratch>/repro-40/page.cjs <port>`). Log in as `card/e2e/fixtures.ts` does. Record every websocket frame received (`page.on("websocket")`) and take a screenshot before and after each scenario. Open the page first, and never reload it during a scenario. The page re-renders if the change shows within 10 seconds (`expect(locator).toBeVisible({ timeout: 10_000 })`):
  1. on `/config/integrations/integration/timerify`, add a timer for `input_boolean.smoke_boiler` through **Add entry** > **Add a timer**: does the new entry appear?
  2. on that page, add a schedule interval to it through **Add schedule interval**: does the interval appear under the entry?
  3. edit that interval's end time: does its title change?
  4. the control for subentries: on `/config/integrations/integration/kitchen_sink`, add a sensor subentry: does it appear?
  5. the control for entries: on `/config/integrations/integration/local_calendar`, add a calendar: does it appear?
  6. scenarios 1 to 3 again, with the changes made through the API (`add_timer` and `add_interval` of the harness) while the page is open. This tells the path of the dialogs from the path of `config_entries/subscribe`.

  For each scenario note: re-rendered or not, and the `config_entries/subscribe` events that came (`type`, `entry.state` and `entry.num_subentries`, in order).
- [ ] **Step 4: Decide**, on A and on B alike:
  - **Timerify and the controls are stale alike:** it is Home Assistant's frontend. Go to Step 5.
  - **The controls re-render and Timerify does not:** the difference is ours, for example the reload that `_async_entry_updated` schedules (`__init__.py:84-87`) and the events it sends. Stop after Step 6. Report the scenarios, the event sequences of Timerify and of `kitchen_sink` side by side, and the screenshots. The fix is then planned as a task of its own, with a test, because it cannot be planned before the cause is known. Write no workaround.
  - **Nothing is stale on either version:** go to Step 5, with a comment that asks the owner for his browser, version and steps. Add no label.
- [ ] **Step 5: Label and comment** (Home Assistant's frontend, or not reproduced). Write the comment to `<scratch>/repro-40/comment.md`, in English, with no attribution. It gives the exact steps of Step 3, the two versions, what re-rendered and what did not, and the event sequences. It ends with the line: "Reporting this to home-assistant/frontend needs the owner's consent; nothing was filed." Then run `gh issue comment 40 --body-file <scratch>/repro-40/comment.md`. When it is Home Assistant's frontend, also run `gh issue edit 40 --add-label upstream`.
- [ ] **Step 6: Clean up.** Run `docker rm -f timerify-repro-40-a timerify-repro-40-b`. Then empty the two configuration folders, whose files root owns: `docker run --rm -v <scratch>/repro-40/<a|b>:/config alpine find /config -mindepth 1 -delete`.
- [ ] **Step 7: RULINGS and follow-ups** (Home Assistant's frontend, or not reproduced).
  - Add **"The integration page that does not re-render waits on Home Assistant (#40, upstream)"**. If it was not reproduced, the title says "#40 is not reproduced". Give the versions, the control that behaved the same, and why no local change was made: Timerify sends the same events as `kitchen_sink`.
  - In `docs/followups.md`, add under a new section `## Forms` the line `- [#40](https://github.com/klimofey/timerify/issues/40) The integration page does not re-render after a timer or a schedule interval is added`.
  - Run the gate.

```bash
git add RULINGS.md docs/followups.md
git commit -m "Record that the integration page not re-rendering waits on Home Assistant"
```

### Task 6: The full gate

**Files:** none, unless a check fails, and then only the files of the fix.

- [ ] **Step 1: Run the full gate on the final tree:**
  - `uv run pytest`, `uv run ruff check`, `uv run ruff format --check` and `uv run mypy`;
  - hassfest;
  - `npm --prefix card ci`, `npm --prefix card run build:check`, `npm --prefix card run typecheck` and `npm --prefix card test`;
  - then compare `date -u +%s` with `docker run --rm alpine date -u +%s`, and run `npm --prefix card run e2e`.

  Expected: all pass. The E2E harness adds timers through the first form with the new fields left at their defaults (`scripts/harness/hass.py:528`), so it needs no change.
- [ ] **Step 2: Report** the counts of pytest, vitest and E2E, against the starting point: 2086 pytest and 241 vitest tests. Give the PR body lines of Global Constraints: "Closes #35, #15, #16", and "Part of #37: the button entity; the card option is part E". Add #40 only if Task 5 fixed it.
