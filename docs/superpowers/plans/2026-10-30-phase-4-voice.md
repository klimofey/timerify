# Timerify Phase 4 — Voice and AI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Timerify targets can be driven by voice through the built-in agent ("turn on the boiler", "turn on the boiler for 45 minutes", "30 more minutes on the boiler", "how long is left on the boiler", "turn on the AC in 15 minutes for an hour, cooling, 24", "what is scheduled for the boiler", "turn off the boiler schedule") in English and Russian, and by any LLM agent through `timerify__*` tools; core's name-only on/off and delayed commands are taken over for Timerify targets only.

**Architecture:** One set of intent handlers (`voice/`), registered once in `async_setup`, is the single path for both agents: the built-in agent reaches them through sentence files, an LLM through `IntentTool`s that wrap the same handlers (`llm.py`). A handler resolves the spoken name among the *loaded timers' targets only* with `intent.async_match_targets(..., assistant=...)` (exposure and duplicate names are core's rules and core's translated answers), then calls the same controller method a service calls; a refusal raised by the controller or by `validate_settings` (`ServiceValidationError`, translation domain `timerify`) is spoken quietly with `response.async_set_error` in the request's language from `translations/<lang>.json`. Success speech is rendered by the default agent from response templates in `sentences/<lang>/` (Jinja, with the language's plural rules); the handler sets only speech slots, which are also the structured result an LLM receives. The sentence sources are hand-written (`sentences/<lang>/timerify.yaml`) plus a file generated at development time from the pinned `home-assistant-intents` data (`sentences/<lang>/core_commands.yaml`: core's name-only on/off phrasings, bare and inside every core delayed-command shape). A second config entry kind, "Voice settings" (spec §6.2), holds the option and the languages; it merges the sources with generated, escaped lists (the targets' names, the intervals' titles, the setting values the targets support), validates the result with hassil against the core data of the language, and writes `custom_sentences/<lang>/timerify.yaml` for each chosen language whenever it changes, then reloads `conversation`. Each task is a vertical slice that leaves all four checks green.

**Tech Stack:** Python 3.14, Home Assistant 2026.10.4 (`homeassistant.helpers.intent`, `homeassistant.helpers.llm` `IntentTool`/`LLMContext`/`ToolAnnotations`/`LLM_API_ASSIST`/`selector_serializer`, `homeassistant.components.llm.LLMTools` and the `llm` platform `async_get_tools`, `homeassistant.components.homeassistant.exposed_entities.async_should_expose` (the defining module: the package only re-exports it, which mypy strict refuses), `conversation.async_converse`, `conversation.reload`, `SchemaFlowMenuStep`, `Debouncer`, `async_dispatcher_send`, `EVENT_ENTITY_REGISTRY_UPDATED`/`EVENT_DEVICE_REGISTRY_UPDATED`, `util.file.write_utf8_file_atomic`, `util.yaml.dump`, `util.language.matches`), hassil 3.12.1 (`Intents.from_dict`, `util.merge_dict`/`remove_punctuation`/`is_template`/`normalize_text`, `sample.sample_sentence`, `expression.ListReference`/`RuleReference`/`TextChunk`), home-assistant-intents 2026.10.6 (`get_intents`), pytest-homeassistant-custom-component 0.13.375 (`hass_tmp_config_dir`, `freezer`, `async_fire_time_changed`), probatio (`to_openapi(..., strict=True)`, `MultipleOf`), ruff, mypy, uv, Docker (hassfest, smoke).

**Spec:** `docs/superpowers/specs/2026-10-28-timerify-design.md` — phase 4 of §7: §6.4 (all of it), §6.2's "Voice settings" entry, the voice items of §5 (R9 "voice 'turn on X' routed to Timerify", R4, R7, R10, S3 "voice" is a manual change, P1–P3 for voice-made commands), §5.4's "voice only offer what the device can do", §6.1's voice "what is scheduled". Facts: `docs/research/2026-10-30-voice-apis.md`. Decisions: `.superpowers/phase-4-decisions.md` (V1–V8), the pre-flight `.superpowers/sdd/2026-10-30-phase-4-voice/preflight.md` (36 findings) and the controller's rulings on it `preflight-rulings.md` (P-1 reverses V1; P-2 refines V3; P-3–P-6). Card and runtime counter are later plans.

**Starting point:** `main` after phase 3 (950 tests), branch `phase-4-voice`. Shape relied on: `controller.py` — `TargetController` with `async_set_minutes(minutes)` (0 stops), `async_add_minutes`, `async_run(minutes | None, settings)` (`None` is R9's open run), `async_add_command(action, when: datetime | timedelta, minutes, settings) -> str` (computes `at` under the lock, refuses `command_in_past`, `command_too_far`, `too_many_commands`, `off_takes_no_duration_or_settings`), `async_cancel_command(id) -> None`, `async_set_interval_enabled(id, enabled)`, `snapshot`, `target_entity_id`, all under one lock through `_command(callable)`; `TimerifyConfigEntry = ConfigEntry[TargetController]`; `core.py` — `remaining_minutes`, `TimerCore._runs_as_of(wish)`, `Snapshot.end/pending/commands/disabled_intervals/last_actual`, `Command`; `domains.py` — `_Setting` rows, `supported_settings(hass, entity_id) -> tuple[SettingChoice, ...]`, `validate_settings`; `services.py` — `SETTINGS_SCHEMA`, `ADD_COMMAND_SCHEMA` (`at`: `probatio.All(cv.datetime, dt_util.as_utc)`); `number.py` — `async_add_command` checks "exactly one of `delay` and `at`" (`delay_or_at`); `config_flow.py` — `SchemaConfigFlowHandler`, `CONFIG_FLOW` `user` (target form) → `duration` → `workday`, `OPTIONS_FLOW` `init` (mode) → …, `options_flow_reloads = False`; `__init__.py` — the timer's update listener `_async_entry_updated` reloads on any change; `switch.py` — `IntervalSwitch` with no entity category; tests — `provide_target`, `fake_target` ("Boiler", `switch.boiler`), `fake_climate` ("AC"), `setup_target(...)`, helpers `advance`, `set_number`, `add_command`, `add_interval`, `JERUSALEM`, `START` (2026-01-05 07:00 UTC = 09:00 in Jerusalem); smoke `add_timer` posts the target form to step `user`. If the shape differs, adapt names, not behaviour.

## Global Constraints

- Home Assistant `>= 2026.10.4` (`hacs.json`), Python `>= 3.14.2`, `pytest-homeassistant-custom-component==0.13.375`; dev group gains `hassil==3.12.1`, `home-assistant-intents==2026.10.6`, `gazetteer-matcher==1.1.0` (the pins of `homeassistant/components/conversation/manifest.json:9-13`; a test asserts they match). `manifest.json` gains `"after_dependencies": ["conversation", "llm"]` (their requirements are installed before Timerify is imported, `requirements.py:197`; hassfest wants imported components declared).
- Only public HA mechanisms; schemas with `probatio`; import HA names from the module that defines them (mypy strict); no `cast`, no `type: ignore` for the two entry kinds — narrow with `TypeIs` on `entry.options`.
- One path: a voice handler and an LLM tool call the same controller method a service calls; a rule (bounds, past times, settings, booleans, whole numbers, limits, interval lookup) lives in the controller or `domains`, never in a handler. A handler translates slots into a call and a result into speech slots.
- Every user-facing string in `translations/en.json` (source) and `translations/ru.json`, or in `sentences/<lang>/`; Cyrillic only in `translations/ru.json` and `sentences/ru/` (tests included). Refusal texts are plural-free (counts as unit abbreviations). LLM-facing tool descriptions, titles and the tool prompt are English.
- Intent types `TimerifyTimeLeft`, `TimerifyRun`, `TimerifyAddTime`, `TimerifyStop`, `TimerifyDelayedCommand`, `TimerifyListCommands`, `TimerifyCancelCommands`, `TimerifySetSchedule`; tool names `timerify__<snake case of the intent without the prefix>` (`timerify__time_left`, `timerify__run`, …, `timerify__set_schedule`); every tool `integration="timerify"`. Every list and expansion rule the sources define starts with `timerify_`; the name slot is `name`. Fixed slot values in hand-written YAML are quoted (`"on"`, `"off"`, `"all"`, `"next"`) or real booleans (`true`, `false`).
- No `default=` in any `slot_schema`; durations and delays use the hinted validator `whole_slot(value: float) -> int` (renders as `number`, refuses booleans, fractions, negatives); numeric settings `probatio.Any(int, float)` (no coercion: `validate_settings` refuses booleans).
- Values: `VOICE_LANGUAGES = ("en", "ru")`; managed path `hass.config.path("custom_sentences", lang, "timerify.yaml")`; manual route directory `custom_sentences/<lang>/timerify_manual/`; `CONF_KIND = "kind"`, `KIND_VOICE_SETTINGS = "voice_settings"`, `CONF_WRITE_SENTENCES = "write_sentence_files"` (default `True`), `CONF_LANGUAGES = "languages"` (default: the house language when shipped, else `["en"]`), `VOICE_UNIQUE_ID = "voice_settings"`; `VOICE_SYNC_COOLDOWN = 1.0` seconds; `SIGNAL_TIMERS_CHANGED = "timerify_timers_changed"`; `MANAGED_HEADER = "# Managed by Timerify. Do not edit: this file is rewritten whenever a timer changes."`
- Tests are user scenarios through the real default agent (`conversation.async_converse`) and the real Assist LLM API (`llm.async_get_api(hass, LLM_API_ASSIST, LLMContext(...))`, `api.async_call_tool`); time is frozen; every clock move is `advance`/`advance_to`; no sleeps, polling or backdoors. Voice tests live in `tests/voice/` (`conftest.py` overrides `hass_config_dir` with `hass_tmp_config_dir`; helpers in `tests/voice/helpers.py`). Sampling is bounded (Task 1 `samples`); `uv run pytest tests/voice` takes well under a minute. Clock expectations use `JERUSALEM`, so `START` reads 09:00.
- A phase-1–3 test is edited only where a task names it.
- Repository English-only; no AI attribution in commits; never `--no-verify`.
- Every task ends with `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` all passing.

## Review Focus

1. **Bare "turn on X" / delayed "turn off X in N" on a target that is unavailable while its timer runs:** R10 — the wish is kept and applied on return, and a delayed off sets the timer, not "already off" (Task 5 `test_bare_turn_on_of_an_unavailable_target_keeps_the_wish`, `test_turn_off_in_on_an_unavailable_running_target_sets_the_timer`).
2. **A regional language (`en-GB`, `ru-RU`):** the built-in agent loads the `en`/`ru` files, and a refusal is spoken in that language (`ru-RU.json` does not exist) (Task 4 `test_regional_language_answers_in_its_language`).
3. **Home Assistant starting with the voice entry and several timers:** one write per chosen language after every timer is set up, none (and no `conversation` reload) when nothing changed since the last run (Task 2 `test_start_writes_every_target_once`, `test_unchanged_file_is_not_rewritten`).
4. **A non-Timerify entity with a target's name, or the only target without a state:** Timerify phrases never touch the other entity (Task 1 `test_only_timer_with_no_state_is_not_matched_among_other_entities`, Task 2 `test_shared_name_is_not_resolved_to_the_other_entity`).
5. **A command in flight when "turn off X in N" arrives** (an open run not yet confirmed, a stop not yet confirmed): the desired state decides (Task 5 `test_turn_off_in_follows_a_turn_on_in_flight`, `test_turn_off_in_after_a_stop_in_flight_changes_nothing`).

---

## File Structure

```
custom_components/timerify/
  const.py        + VOICE_LANGUAGES, SENTENCES_DIR, LIST_TARGET (T1); CONF_KIND, KIND_VOICE_SETTINGS, CONF_WRITE_SENTENCES,
                    CONF_LANGUAGES, VOICE_UNIQUE_ID, VOICE_SYNC_COOLDOWN, SIGNAL_TIMERS_CHANGED, MANAGED_HEADER,
                    is_voice_options() (T2); LIST_HVAC_MODE, LIST_MODE (T4); LIST_INTERVAL (T7)
  voice/__init__.py   new: HANDLER_TYPES, async_register_intents (T1; T4–T7 append)
  voice/base.py       new: TimerifyIntentHandler, whole_slot, loaded_timers, async_match_timer, voice_language,
                      async_error_text, timer_slots, clock_slots (T1); SETTING_SLOTS, duration_of, settings_of (T4)
  voice/timer.py      new: TimeLeftHandler (T1); RunHandler, AddTimeHandler, StopHandler (T4)
  voice/commands.py   new: DelayedCommandHandler (T5); ListCommandsHandler, CancelCommandsHandler (T6)
  voice/intervals.py  new: SetScheduleHandler (T7)
  voice/sentences.py  new: escape_template, VoiceName, voice_names, load_sources, build, validate, render (T2);
                      setting values (T4); interval titles (T7)
  voice/files.py      new: SentenceFiles, VoiceConfigEntry, is_voice_entry, async_remove_sentence_files,
                      setup/unload/remove of the voice entry (T2)
  llm.py              new: async_get_tools, TOOLS_PROMPT (T3)
  sentences/<lang>/timerify.yaml        new (T1; T4–T7 extend)
  sentences/<lang>/core_commands.yaml   new, generated (T5)
  __init__.py     register intents (T1); branch by entry kind, SIGNAL_TIMERS_CHANGED (T2)
  config_flow.py  user menu, target step, voice_settings steps, options init by kind (T2)
  domains.py      voice aliases of settings, voice_settings(), booleans and whole numbers refused (T4)
  controller.py   duration bounds (T4); command_when, async_turn_off_in (T5); async_cancel_command returns, async_cancel_commands (T6);
                  async_set_schedule_enabled (T7)
  core.py         TimerCore.wanted_running() (T5)
  number.py       uses controller.command_when (T5)
  services.py     command_time exported (T5)
  switch.py       EntityCategory.CONFIG (T3)
  manifest.json   after_dependencies (T1); version 0.4.0 (T8)
  translations/en.json, translations/ru.json   (T2, T4, T5, T7)
scripts/generate_core_commands.py              new (T5)
scripts/smoke/run.py                           add_timer through the menu (T2); scenario_voice (T8)
tests/voice/  __init__.py conftest.py helpers.py test_time_left.py test_sentence_sources.py (T1); test_voice_entry.py (T2);
              test_llm.py test_exposure.py (T3); test_timer_by_voice.py (T4); test_core_commands.py (T5);
              test_planned_commands.py (T6); test_schedule_by_voice.py (T7)
tests/test_config_flow.py (T2: the menu), tests/test_manifest.py (T1), tests/test_domains.py (T4: booleans, voice aliases),
tests/test_commands.py (T5: number uses command_when — assertions unchanged)
pyproject.toml, uv.lock (T1 deps; T8 version), README.md, RULINGS.md, docs/followups.md, CLAUDE.md (T8)
```

---

### Task 1: "How long is left" by voice, the handler plumbing and the sentence sources

**Files:**
- Create: `custom_components/timerify/voice/__init__.py`, `voice/base.py`, `voice/timer.py`, `sentences/en/timerify.yaml`, `sentences/ru/timerify.yaml`
- Modify: `custom_components/timerify/__init__.py`, `const.py`, `manifest.json`, `pyproject.toml`, `uv.lock`, `tests/test_manifest.py`
- Test: `tests/voice/__init__.py`, `tests/voice/conftest.py`, `tests/voice/helpers.py`, `tests/voice/test_time_left.py`, `tests/voice/test_sentence_sources.py`

**Interfaces:**
- Produces in `const.py`: `VOICE_LANGUAGES`, `SENTENCES_DIR: Final = Path(__file__).parent / "sentences"`, `LIST_TARGET: Final = "timerify_target"`.
- Produces in `voice/base.py`:
  - `whole_slot(value: float) -> int` — the duration/delay slot validator of Global Constraints.
  - `loaded_timers(hass) -> list[TimerifyConfigEntry]` — the loaded entries of the domain (T2 leaves out the voice entry).
  - `async_match_timer(hass, intent_obj, name: str) -> TimerifyConfigEntry` — candidates are the states of the loaded timers' targets; with no candidate it raises `intent.MatchFailedError(result=MatchTargetsResult(False, MatchFailedReason.NAME), constraints=...)` without calling the matcher (an empty `states` would match the whole house, `intent.py:591-594`); otherwise `intent.async_match_targets(hass, MatchTargetsConstraints(name=name, assistant=intent_obj.assistant, single_target=True), states=candidates)`, raising `MatchFailedError` when it does not match.
  - `voice_language(language: str) -> str` — the first of `language_util.matches(language, list(VOICE_LANGUAGES))`, `"en"` when none (`"*"` gives `["en", "ru"]`, `"de"` gives `[]`).
  - `async_error_text(hass, language, err: HomeAssistantError) -> str` — `component.timerify.exceptions.<key>.message` of `voice_language(language)` formatted with the placeholders, where a `setting` placeholder is replaced by `component.timerify.services.run.fields.<setting>.name` of that language when it exists, and an `at` placeholder by local `HH:MM`.
  - `clock_slots(moment, now) -> dict[str, Any]` — `{"at": "HH:MM" (local, 24 h), "in_days": <local date difference>}`.
  - `timer_slots(hass, entry, now) -> dict[str, Any]` — `target` (`target_name`), `state` (`"counting"` | `"open"` (on without a timer) | `"off"`), `left_total` (`remaining_minutes`), `left_hours`, `left_minutes` (`divmod(left_total, 60)`), and while counting `ends_at`/`ends_in_days`.
  - `class TimerifyIntentHandler(intent.IntentHandler)` — ClassVars `tool_name`, `title` (short English), `description` (English: what the tool does and what each slot means, `name` being the device name from the prompt), `read_only`, `destructive`, `idempotent`; `slot_schema` keys are `probatio.Required`/`Optional` without `default`, always `Required("name"): cv.string`; `async_handle` (final) creates the response, validates the slots once (`async_validate_slots`), resolves the timer, awaits `async_handle_timer(intent_obj, entry, slots, response) -> None` with the validated `slots` (a handler never validates them again), and turns a `HomeAssistantError` with `translation_domain == DOMAIN` into `response.async_set_error(FAILED_TO_HANDLE, await async_error_text(...))`; other exceptions propagate. Actions add the target to success results; queries set `QUERY_ANSWER` and matched states; success never sets speech, only `async_set_speech_slots`.
- Produces in `voice/__init__.py`: `HANDLER_TYPES: Final[tuple[type[TimerifyIntentHandler], ...]]`, `async_register_intents(hass)` (from `async_setup`, after the services).
- Produces in `voice/timer.py`: `TimeLeftHandler` (`TimerifyTimeLeft`, read only).
- Sentence source shape (both languages): `language`, `intents.TimerifyTimeLeft.data[].sentences` with `{timerify_target:name}`, `lists.timerify_target.values: []`, `responses.intents.TimerifyTimeLeft.default` branching on `slots.state`. Plural rule in the ru templates: one `n % 10 == 1 and n % 100 != 11`, few `n % 10 in [2, 3, 4] and n % 100 not in [12, 13, 14]`, else many.
- Produces in `tests/voice/conftest.py`: `hass_config_dir` → `hass_tmp_config_dir`; `assist` (sets up `homeassistant`, `conversation`, `intent`, writes an empty `configuration.yaml`, sets `JERUSALEM`); `fake_fan` (`switch.fan`, "Fan", no timer).
- Produces in `tests/voice/helpers.py`: `converse(hass, text, language="en") -> intent.IntentResponse`; `speech(response) -> str`; `expose(hass, entity_id, exposed)`; `copy_sentences(hass, names)` — the README's manual route into `custom_sentences/<lang>/timerify_manual/` (sources plus `timerify_names.yaml`); `samples(language, intent_type, *, names=("Boiler",), numbers: Mapping[str, int], texts: Mapping[str, str] = {}) -> list[str]` — bounded by definition: every number list and every text list replaced by one value (`names[0]`, `texts[list]` or its first value), each sentence sampled twice with `hassil.sample.sample_sentence` (the first expansion, optionals present and the first permutation order; the first with `skip_optionals=True`), deduplicated; `MINUTE_CLASSES`, `HOUR_CLASSES`, `COMMAND_CLASSES` (below); `without_digits(text)`.

  | Classes | ru one | ru few | ru many | en other (en one is `(1,)`) |
  |---|---|---|---|---|
  | `MINUTE_CLASSES` | 1, 21, 31, 41, 51 | 2, 3, 4, 22, 23, 24, 32, 54 | 5, 9, 11, 12, 13, 14, 15, 20, 25, 30, 59 | 2, 5, 11, 21, 59 |
  | `HOUR_CLASSES` (× 60 minutes) | 1, 21 | 2, 3, 4, 22, 23, 24 | 5, 11, 12, 14, 20 | 2, 5, 11, 24 |
  | `COMMAND_CLASSES` | 1 | 2, 3, 4 | 5, 11, 12, 14, 20 | 2, 5, 20 |

- [ ] **Step 1: Write the failing tests** (`setup_target()` + `fake_target`, `assist`, `copy_sentences(hass, ["Boiler"])`)

```python
async def test_time_left_while_counting():          # 45 → QUERY_ANSWER, TimerifyTimeLeft,
    # speech == "45 minutes left on Boiler, it turns off at 09:45."
async def test_time_left_says_hours_and_minutes():  # 90 → "1 hour and 30 minutes left on Boiler, it turns off at 10:30."
async def test_time_left_rounds_up_like_the_run_for_number():  # 45, advance 30 s → still "45 minutes left …"
async def test_time_left_past_midnight_says_tomorrow():  # 1440 → "24 hours left on Boiler, it turns off at 09:00 tomorrow."
async def test_time_left_on_an_idle_target():       # "Boiler is off and has no timer."
async def test_time_left_on_a_loose_target_running_without_a_timer():  # "Boiler is on without a timer."
@pytest.mark.parametrize("text", ["how much time is left on the boiler", "how long is left on boiler",
    "how long will the boiler run", "when does the boiler turn off", "How much time is left on the Boiler?"])
async def test_english_phrasings_ask_time_left(text)  # TimerifyTimeLeft, name "Boiler"
async def test_unexposed_target_is_refused()        # ERROR, NO_VALID_TARGETS; no call to the target
async def test_entity_without_a_timer_is_not_captured()  # fake_fan: "how much time is left on fan" → not our intent
async def test_two_targets_with_one_name_are_not_guessed()  # two timers on entities named "Lamp" → ERROR, nothing switched
async def test_only_timer_with_no_state_is_not_matched_among_other_entities()  # the target's state removed, fake_fan
    # renamed "Boiler" → ERROR NO_VALID_TARGETS, the fan untouched
async def test_russian_sentences_reach_time_left()  # every samples("ru", "TimerifyTimeLeft") → our intent, name "Boiler"
@pytest.mark.parametrize("classes", [MINUTE_CLASSES, HOUR_CLASSES])
async def test_russian_counts_follow_the_plural_rules(classes)  # one ru sample: without_digits(speech) equal within a
    # class, different between the three classes
async def test_english_counts_follow_the_plural_rules()  # en one vs other the same way; "1 minute", "2 minutes", "1 hour"
# tests/voice/test_sentence_sources.py
def test_voice_languages_are_the_sentence_directories()
@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_sources_load_with_core_and_without_names(language)  # from_dict(merge_dict(get_intents(lang), sources)) and every
    # Timerify intent's sentences parse (data.sentences touched); samples with names=() is empty
def test_every_language_has_the_same_intents_and_responses()  # same intents; every data block's response has a template
def test_source_lists_and_rules_are_prefixed()      # every list and expansion rule the sources define starts "timerify_"
def test_fixed_slot_values_have_their_intended_types()  # strings stay str, booleans bool (no YAML 1.1 on/off surprise)
async def test_handlers_are_registered_once_per_intent()
def test_voice_test_dependencies_match_conversation()  # tests/test_manifest.py
```

- [ ] **Step 2: Run `uv sync && uv run pytest tests/voice tests/test_manifest.py -v`** — Expected: FAIL (no `voice` package).
- [ ] **Step 3: Implement** the deps and `after_dependencies`, `voice/base.py`, `TimeLeftHandler`, the registration, both sentence files (en templates exactly as the tests say; ru: the target's name first, in the nominative, then a colon).
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Answer how long is left on a timer by voice"`

---

### Task 2: The "Voice settings" entry writes and keeps the sentence files

**Files:**
- Create: `custom_components/timerify/voice/sentences.py`, `voice/files.py`
- Modify: `custom_components/timerify/__init__.py`, `config_flow.py`, `const.py`, `voice/base.py` (`loaded_timers`), `translations/en.json`, `translations/ru.json`, `scripts/smoke/run.py` (`add_timer`), `tests/test_config_flow.py`
- Test: `tests/voice/test_voice_entry.py`, `tests/voice/helpers.py`

**Interfaces:**
- Consumes: `VOICE_LANGUAGES`, `SENTENCES_DIR`, `LIST_TARGET`, `loaded_timers` (Task 1).
- Produces in `const.py`: the T2 values of Global Constraints; `is_voice_options(options) -> bool` (`options.get(CONF_KIND) == KIND_VOICE_SETTINGS`).
- Produces in `voice/sentences.py` (blocking ones run in the executor):
  - `escape_template(text) -> str` — `text` unchanged unless `hassil.util.is_template(text)`; then a backslash before each of `\ ( ) [ ] { } < > | @`, backslash first (a backslash alone is literal, `util.py:32`).
  - `@dataclass(frozen=True) class VoiceName: spoken: str; name: str; domain: str`.
  - `voice_names(hass) -> list[VoiceName]` — for each loaded timer's target, every name of `intent.async_get_entity_aliases(hass, registry_entry, state=state)` (or `er.async_get_entity_aliases(hass, entry, allow_empty=False)` while it has no state), `spoken = remove_punctuation(name).strip()`, empty ones skipped (`default_agent.py:1077-1087`).
  - `load_sources(language) -> dict[str, Any]` — `merge_dict` of every `SENTENCES_DIR/<language>/*.yaml`, sorted by name.
  - `build(sources, names: Sequence[VoiceName]) -> dict[str, Any]` — `lists.timerify_target.values` = `{in: escape_template(spoken), out: name, context: {domain: domain}}` per name.
  - `validate(language, built) -> None` — (a) `Intents.from_dict(merge_dict(<copy of get_intents(language)>, built))`; (b) touch `data.sentences` of every Timerify intent (parsed lazily, `intents.py:356-361`); (c) every `ListReference` and `RuleReference` in a Timerify sentence or rule resolves to a list or rule of the merge (or the data block's own); (d) every generated list value's parsed `text_in` is one text chunk equal to `normalize_text(spoken)`. Raises on the first failure.
  - `render(built) -> str` — `MANAGED_HEADER` + `\n` + `util.yaml.dump(built)`.
- Produces in `voice/files.py`:
  - `async_remove_sentence_files(hass, languages: Iterable[str] = VOICE_LANGUAGES) -> None` — module function: unlinks the managed files of those languages that exist (executor), then `conversation.reload` once if one existed and the service exists. Used by the entry's removal (whose `runtime_data` is gone, `config_entries.py:1138-1139`) and by `SentenceFiles`.
  - `class SentenceFiles` (runtime data): `async_start()`, `async_sync()` (per chosen language: build, validate, render; write only when the text differs, `mkdir(parents=True, exist_ok=True)` + `write_utf8_file_atomic` in the executor; remove the files of languages not chosen; one `conversation.reload` with no data if anything changed and the service exists; a failed `validate` logs one ERROR naming the language and leaves that file as it was; one WARNING when a `timerify_manual/` directory exists: "manual and managed sentences are both installed").
  - `type VoiceConfigEntry = ConfigEntry[SentenceFiles]`; `is_voice_entry(entry: TimerifyConfigEntry | VoiceConfigEntry) -> TypeIs[VoiceConfigEntry]` (by `is_voice_options(entry.options)`); `async_setup_voice_entry`, `async_unload_voice_entry`, `async_remove_voice_entry`.
  - Lifecycle: setup registers `entry.add_update_listener` → `async_schedule_reload` (as the timers do). Option on → `async_start`: when Home Assistant is running `await async_sync()` before setup returns, else at `async_at_started`; only after that first sync it subscribes to `SIGNAL_TIMERS_CHANGED`, `EVENT_ENTITY_REGISTRY_UPDATED` of a target (`name`, `aliases`, `original_name`, `entity_id`, `device_id`) and `EVENT_DEVICE_REGISTRY_UPDATED` of a target's device (`name`, `name_by_user`), each scheduling a `Debouncer(cooldown=VOICE_SYNC_COOLDOWN, immediate=False, function=async_sync)`; events while `hass.is_stopping` are ignored. Option off → `async_remove_sentence_files(hass)`. Unload cancels the debouncer and removes the files only when `entry.disabled_by` is set. Removal removes them.
- Produces in `__init__.py`: setup/unload/remove take `TimerifyConfigEntry | VoiceConfigEntry` and branch with `is_voice_entry`; a timer's setup (after `async_start`) and unload send `SIGNAL_TIMERS_CHANGED`.
- Produces in `config_flow.py`: `CONFIG_FLOW["user"] = SchemaFlowMenuStep(_menu_options)` — `["target", "voice_settings"]`, `voice_settings` only while no voice entry exists; `"target"` is the former `user` form; `"voice_settings"` a form (schema function) with `Required(CONF_WRITE_SENTENCES, default=True): BooleanSelector()` and `Required(CONF_LANGUAGES, default=<house language if in VOICE_LANGUAGES else "en">): SelectSelector(multiple, options=VOICE_LANGUAGES, translation_key="voice_language")`; its validator refuses an empty choice (`SchemaFlowError("languages_required")`), raises `AbortFlow("voice_settings_exist")` if a voice entry exists (a race: the menu already hides it), sets the unique id `VOICE_UNIQUE_ID` (`raise_on_progress=False`), loads the `config` translations of `hass.config.language`, and adds `CONF_KIND`; `async_config_entry_title` returns, for a voice entry, the cached `component.timerify.config.step.voice_settings.title`. `OPTIONS_FLOW["init"]` keeps the mode form for timers; its schema function returns `None` for a voice entry and its `next_step` sends it to `"voice_settings"` (the same two fields, no defaults). `async_get_supported_subentry_types` gives a voice entry none.
- Translations: `config.step.user` (title, description, `menu_options.target`, `menu_options.voice_settings`), `config.step.target` (the former `user` texts), `config.step.voice_settings` and `options.step.voice_settings` (title "Voice settings"; description: the files are `custom_sentences/<lang>/timerify.yaml`, rewritten by Timerify, removed by unticking, disabling or removing; `data.write_sentence_files` "Add voice sentences for the built-in agent", `data.languages` "Languages"), `config.error.languages_required`, `options.error.languages_required`, `config.abort.voice_settings_exist`, `selector.voice_language.options.{en,ru}`.
- Produces in `tests/voice/helpers.py`: `add_voice_entry(hass, *, write=True, languages=("en", "ru")) -> ConfigEntry` (through the menu), `managed_file(hass, lang) -> Path`, `listed(hass, lang, list_name=LIST_TARGET) -> list[dict[str, Any]]`, `conversation_reloads(hass) -> list[ServiceCall]`.
- `tests/test_config_flow.py` and smoke `add_timer`: pick `target` from the menu first, expect step `target` where they expected `user`; nothing else changes.

- [ ] **Step 1: Write the failing tests** (`tests/voice/test_voice_entry.py`; `assist`, `fake_target`, `setup_target`)

```python
async def test_menu_offers_a_timer_and_voice_settings()   # step user is a menu: ["target", "voice_settings"]
async def test_languages_default_to_the_house_language()  # house "ru" → ["ru"]; house "de" → ["en"]
async def test_voice_entry_writes_a_file_per_chosen_language()  # languages en+ru → both files, line 1 == MANAGED_HEADER,
    # listed == [{"in": "Boiler", "out": "Boiler", "context": {"domain": "switch"}}]; "how long is left on the boiler"
    # works without copy_sentences; one conversation reload
async def test_only_the_chosen_languages_are_written()    # ["en"] → no ru file; options → ["ru"] → en removed, ru written
async def test_empty_language_choice_is_refused()          # errors {"base": "languages_required"}, in creation and options
async def test_menu_hides_voice_settings_once_it_exists()
async def test_second_voice_entry_is_refused()             # a flow opened before the first finished → abort voice_settings_exist
async def test_voice_entry_title_is_in_the_language_of_the_house()
async def test_voice_entry_has_no_intervals_and_no_timer()
async def test_option_off_at_creation_writes_nothing()
async def test_unticking_removes_the_files_and_the_sentences_stop_matching()  # options flow → reload → files gone, one reload
async def test_ticking_again_writes_them()
async def test_removing_the_entry_removes_the_files()
async def test_disabling_the_entry_removes_the_files_and_enabling_writes_them()
async def test_reloading_the_entry_keeps_the_files_without_rewriting()
async def test_unchanged_file_is_not_rewritten()           # a timer reload that changes no name → no write, no reload
async def test_start_writes_every_target_once()            # CoreState.not_running: voice entry, two timers, STARTED → one write
    # per language listing both, one reload
async def test_new_target_is_listed()                      # second timer, advance(seconds=VOICE_SYNC_COOLDOWN)
async def test_removed_target_leaves_the_list()
async def test_renamed_target_follows()
async def test_new_name_and_alias_are_matched()            # registry name "Water heater", aliases [COMPUTED_NAME, "Geyser"]
async def test_device_rename_follows_the_full_name()
@pytest.mark.parametrize("name", ["Boiler (main)", "Lamp [2]", "A|B lamp", "<Hall>", "Tea {pot}", "me@home",
                                  "Back\\slash", "A\\(b"])
async def test_names_are_listed_so_that_they_match_as_said(name)  # file validates; "how long is left on <name>" → ours
async def test_name_is_matched_as_the_default_agent_cleans_it()  # "Boiler!" spoken "Boiler", out "Boiler!"
async def test_name_left_empty_by_punctuation_is_skipped()
async def test_shared_name_is_not_resolved_to_the_other_entity()  # fake_fan renamed "Boiler": "how long is left on boiler" →
    # Boiler's answer, the fan untouched
async def test_unescaped_name_is_refused_before_writing()  # patch escape_template to identity, "Boiler (main" → file
    # unchanged, one ERROR naming "en"
async def test_list_value_that_would_not_match_as_said_is_refused()  # patch escape_template to drop escaping of "<": "<Hall>"
    # → check (d) refuses, file unchanged
async def test_manual_copy_beside_the_managed_file_is_warned_about()
async def test_files_are_written_without_conversation_and_nothing_is_reloaded()
```

- [ ] **Step 2: Run `uv run pytest tests/voice/test_voice_entry.py tests/test_config_flow.py -v`** — Expected: new tests FAIL; `test_config_flow.py` FAILS on the menu until Step 3.
- [ ] **Step 3: Implement** `sentences.py`, `files.py`, the branches, the flow steps and strings; update `add_timer` in the smoke script.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Add a Voice settings entry that writes the sentence files for the built-in agent"`

---

### Task 3: LLM tools, and Timerify's own entities kept from Assist

**Files:**
- Create: `custom_components/timerify/llm.py`
- Modify: `custom_components/timerify/switch.py`, `tests/test_interval_switch.py` (only if it asserts the category)
- Test: `tests/voice/test_llm.py`, `tests/voice/test_exposure.py`, `tests/voice/helpers.py`

**Interfaces:**
- Consumes: `HANDLER_TYPES` and the handler ClassVars, `loaded_timers` (Task 1).
- Produces in `llm.py` (imports: `LLMTools` from `homeassistant.components.llm`; `IntentTool`, `LLMContext`, `ToolAnnotations`, `LLM_API_ASSIST` from `homeassistant.helpers.llm`; `async_should_expose` from `homeassistant.components.homeassistant.exposed_entities`): `@callback def async_get_tools(hass, llm_context, api_id) -> LLMTools | None` — `None` when `api_id != LLM_API_ASSIST`, when `llm_context.assistant` is empty (core's guard: an empty name would get a decision written into every target's registry entry), or when no loaded timer's target is exposed to `llm_context.assistant`; otherwise one `IntentTool(cls.tool_name, cls(), title=cls.title, integration=DOMAIN, annotations=ToolAnnotations(read_only=cls.read_only, destructive=cls.destructive, idempotent=cls.idempotent, open_world=False))` per `HANDLER_TYPES` entry, and `prompt = TOOLS_PROMPT.format(names=json.dumps(names, ensure_ascii=False))` of the exposed targets (a JSON list, so that a name with a comma, a quote or a line break stays one name). `TOOLS_PROMPT`: "These devices have a Timerify timer: {names}. To run one for a while, add time, stop it, ask how long is left, plan a command for later, list or cancel planned commands, or switch its schedule on or off, use the timerify__ tools, naming the device as listed here."
- Annotations per handler (set in the tasks that add them; as core annotates the tools of its kind, `intent/llm.py`): time_left, list_commands read only; add_time `destructive=False`; stop, cancel_commands, set_schedule `idempotent=True`; run, delayed_command no flag besides `open_world=False` (so destructive and not idempotent, as `HassTurnOn` and `HassStartTimer`: they replace the countdown and apply settings). `tests/voice/test_llm.py` holds the table for all eight.
- Produces in `switch.py`: `IntervalSwitch.entity_description` gains `entity_category=EntityCategory.CONFIG`.
- Produces in `tests/voice/helpers.py`: `assist_api(hass, language="en", assistant="conversation")`, `call_tool(api, name, args) -> dict[str, Any]` (the `ToolResult.data`).

- [ ] **Step 1: Write the failing tests**

```python
async def test_tools_are_offered_while_a_target_is_exposed()  # names == {c.tool_name for c in HANDLER_TYPES}, prefixed,
    # integration "timerify"; no WARNING from the llm platform
async def test_tools_have_their_own_descriptions_and_titles()  # none is "Execute Home Assistant … intent"; titles set
async def test_annotations_follow_each_tool()                  # time_left read_only, destructive as set
async def test_no_tools_without_an_exposed_target()
async def test_no_tools_for_another_llm_api()                  # async_get_tools(hass, ctx, "other") is None
async def test_prompt_names_the_exposed_targets_only()
async def test_tool_parameters_render_as_typed_openapi()       # strict to_openapi for every timerify tool
async def test_time_left_tool_returns_structured_data()        # 45 → data["speech_slots"] == {"target": "Boiler",
    # "state": "counting", "left_total": 45, "left_hours": 0, "left_minutes": 45, "ends_at": "09:45", "ends_in_days": 0}
async def test_tool_refuses_an_unexposed_target()              # MatchFailedError, reason ASSISTANT
async def test_tool_with_language_star_and_unknown_language_works()
# tests/voice/test_exposure.py
async def test_timerify_entities_are_not_exposed_by_default()  # number, both sensors, interval switch False; switch.boiler True
async def test_interval_switch_is_a_config_entity()
```

- [ ] **Step 2: Run `uv run pytest tests/voice/test_llm.py tests/voice/test_exposure.py -v`** — Expected: FAIL.
- [ ] **Step 3: Implement** `llm.py` and the entity category.
- [ ] **Step 4: Run all checks and hassfest** — the four checks, then `docker run --rm --platform linux/amd64 -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest` — Expected: all pass, hassfest clean (the dependency check sees `conversation` and `llm` declared).
- [ ] **Step 5: Commit** — `git commit -m "Offer the timer to LLM agents as tools and keep Timerify's own entities from Assist"`

---

### Task 4: Run, add time and stop by voice, with every setting the target supports

**Files:**
- Modify: `custom_components/timerify/voice/timer.py`, `voice/__init__.py`, `voice/base.py`, `voice/sentences.py`, `voice/files.py` (settings values in the sync), `domains.py`, `controller.py`, `const.py`, `sentences/en/timerify.yaml`, `sentences/ru/timerify.yaml`, `translations/en.json`, `translations/ru.json`
- Test: `tests/voice/test_timer_by_voice.py`, `tests/voice/test_voice_entry.py` (setting lists), `tests/test_domains.py`

**Interfaces:**
- Consumes: Task 1's base, Task 2's builder and `add_voice_entry`, Task 3's `assist_api`/`call_tool`.
- Produces in `domains.py`: `_Setting` gains `voice: Literal["percent", "mode"] | None = None` — light `brightness_pct`, fan `percentage`, humidifier `humidity` are `"percent"`; climate `fan_mode`, fan `preset_mode`, humidifier `mode`, water heater `operation_mode` are `"mode"` (at most one of each per row, tested); `voice_settings(hass, entity_id, *, percent: float | None, mode: str | None) -> dict[str, Any]` names them by the target's row and raises `ServiceValidationError(translation_key="voice_setting_not_supported", placeholders={"target"})` when the row has none; `validate_settings` refuses a boolean for any number setting and a fraction for `percentage`/`humidity` (`setting_out_of_range` as today) — the rule services already had in their schema, now in its single home.
- Produces in `voice/base.py`: `SETTING_SLOTS` — one `probatio.Optional` per `SETTINGS_SCHEMA` key, `probatio.Any(int, float)` for numbers, `cv.string` otherwise (keys tested equal); `duration_of(slots, prefix="") -> int | None` (`60 * hours + minutes`, `None` when neither); `settings_of(hass, entry, slots) -> dict[str, Any]` — the `SETTING_SLOTS` values plus `voice_settings(...)` of the sentence-only slots `percent` and `mode`.
- Produces in `voice/sentences.py`: `voice_setting_values(hass) -> VoiceSettingValues(hvac_modes: frozenset[str], modes: frozenset[str])` from `supported_settings` of the loaded targets (hvac options; options of `voice == "mode"` settings); `build(sources, names, settings)` keeps the source word table `timerify_hvac_mode` values whose `out` is in `hvac_modes`, and fills `timerify_mode` with `{in: escape_template(remove_punctuation(m.replace("_", " ")).strip()), out: m}` per mode. The source declares `timerify_hvac_mode` (every `HVACMode` but off, with synonyms: en cool/cooling, heat/heating, dry/drying, fan only, auto, heat and cool; ru the equivalents) and `timerify_mode: values: []`. Regenerated with the names (same triggers).
- Produces in `voice/timer.py`:
  - `RunHandler` (`TimerifyRun`, default annotations: destructive, it replaces the countdown): slots `name`, `hours`, `minutes` (`whole_slot`), `SETTING_SLOTS` → `controller.async_run(duration_of(slots), settings_of(...))`; speech slots `timer_slots` after the call.
  - `AddTimeHandler` (`TimerifyAddTime`, `destructive=False`): `name`, `hours`, `minutes` → `controller.async_add_minutes(...)`.
  - `StopHandler` (`TimerifyStop`, `idempotent=True`): `name` → `controller.async_set_minutes(0)`.
- Produces in `controller.py`: `async_run` (with minutes), `async_add_command` (with minutes) and `async_set_minutes` raise `ServiceValidationError("duration_out_of_range", {"max_hours": str(MAX_MINUTES // 60)})` outside `1..MAX_MINUTES` (`0..` for `async_set_minutes`). `async_add_minutes` keeps the phase-1 clamp (see rulings).
- Sentences (en; ru the same meanings): run — "<turn> on [<the>] {name} for <timerify_duration> [<timerify_settings>]", "<turn> [<the>] {name} on for <timerify_duration> [<timerify_settings>]", "run [<the>] {name} for <timerify_duration>", "set [<the>] {name} timer to <timerify_duration>"; add — "add <timerify_duration> to [<the>] {name}", "<timerify_duration> more on [<the>] {name}", "extend [<the>] {name} by <timerify_duration>"; stop — "(stop|cancel) [<the>] {name} timer", "(stop|cancel) the timer (on|of) [<the>] {name}". `timerify_duration`: `{timerify_hours:hours} hour[s] [and] {timerify_minutes:minutes} minute[s]`, either part alone, and `{timerify_duration_words:minutes}` (en "an hour" 60, "half an hour" 30, "an hour and a half" 90; ru the same three). `timerify_settings`: a hassil permutation of optional parts — `{timerify_hvac_mode:hvac_mode} [mode]`, `[at] {timerify_temperature:temperature} [degree[s]]` (range 1..100, halves), `[at] {timerify_percent:percent} percent` (1..100), `[in] {timerify_mode:mode} [mode]`; no `[,]` (punctuation never reaches templates). Ranges: `timerify_hours` 1..24, `timerify_minutes` 1..1440.
- Responses (en): run and add "Boiler runs for 45 minutes, until 09:45." (hours as in Task 1, "tomorrow" when `ends_in_days`); open run "Boiler is on."; stop "Boiler is off."
- Translations: `exceptions.duration_out_of_range` (en "A timer runs for 1 min to {max_hours} h."), `exceptions.voice_setting_not_supported` (en "{target} cannot be turned on with that setting.").

- [ ] **Step 1: Write the failing tests** (`assist`, `fake_target`/`fake_climate`, a fake fan with presets and a fake light, `add_voice_entry`)

```python
async def test_turn_on_for_minutes_runs_the_timer()      # "turn on the boiler for 45 minutes" → turn_on once, NUMBER 45,
    # "Boiler runs for 45 minutes, until 09:45."
@pytest.mark.parametrize(("text", "minutes"), [("turn the boiler on for an hour", 60), ("run the boiler for 2 hours", 120),
    ("turn on the boiler for 1 hour and 30 minutes", 90), ("turn on the boiler for half an hour", 30),
    ("set the boiler timer to 20 minutes", 20)])
async def test_run_phrasings(text, minutes)
async def test_run_with_settings_turns_the_ac_on_with_them()  # "turn on the AC for an hour cooling 24" → cool, 24.0, AC 60
async def test_settings_in_every_order()                  # one sentence, every order of the timerify_settings permutation
async def test_every_hvac_word_reaches_its_mode()         # each timerify_hvac_mode value of the AC's modes, one sentence
async def test_hvac_words_are_listed_only_for_supported_modes()  # listed(..., LIST_HVAC_MODE) has cool/heat of AC_ATTRS only
async def test_percent_means_the_targets_own_setting()    # light "at 40 percent" → brightness_pct 40; fan → percentage 40
async def test_mode_means_the_targets_own_setting()       # AC "fan high" → fan_mode; fan "in eco mode" → preset_mode;
    # listed(..., LIST_MODE) has the targets' strings
async def test_setting_the_target_cannot_take_is_refused()  # boiler "at 40 percent" → voice_setting_not_supported text;
    # AC "heat and cool" when unsupported → setting_not_an_option text with the field's translated name; nothing switched
async def test_run_longer_than_a_day_is_refused()         # "for 24 hours and 30 minutes" → duration_out_of_range text
async def test_add_time_extends_a_running_timer()         # R7: 5 left, "30 more minutes on the boiler" → 35
async def test_add_time_on_an_idle_timer_starts_it()
async def test_add_time_past_a_day_runs_a_day()           # 1430 left, "add 30 minutes" → ends a day from now (clamp)
async def test_stop_turns_the_target_off()                # R2
async def test_voice_change_ends_schedule_alignment()     # S3
async def test_strict_manual_rules_still_apply_after_voice()  # R3
@pytest.mark.parametrize("intent_type", ["TimerifyRun", "TimerifyAddTime", "TimerifyStop"])
async def test_russian_sentences_reach_their_intent(intent_type)  # bounded samples → our intent, sampled slot values
async def test_russian_run_answer_follows_the_plural_rules()  # MINUTE_CLASSES and HOUR_CLASSES
async def test_regional_language_answers_in_its_language()  # "ru-RU" refusal → ru.json text formatted; "en-GB" → en
async def test_llm_run_add_and_stop()                     # timerify__run {"name": "Boiler", "minutes": 45} → left_total 45; …
async def test_llm_run_with_settings()                    # AC {"hvac_mode": "cool", "temperature": 24, "hours": 1}
@pytest.mark.parametrize("args", [{"minutes": 2.5}, {"minutes": True}, {"minutes": -5}])
async def test_llm_duration_must_be_a_whole_number(args)  # refused, nothing runs
async def test_llm_boolean_setting_is_refused()           # light {"brightness_pct": true} → setting_out_of_range text
async def test_llm_error_text_follows_the_request_language()  # "ru" → ru, "*" and "de" → en
async def test_llm_duration_out_of_range_is_refused()     # minutes 1441, minutes 0
def test_setting_slots_are_the_service_settings()
# tests/test_domains.py
def test_number_settings_refuse_booleans()                # validate_settings, every number setting
def test_each_domain_has_at_most_one_percent_and_one_mode_setting()
```

- [ ] **Step 2: Run `uv run pytest tests/voice/test_timer_by_voice.py tests/test_domains.py -v`** — Expected: FAIL.
- [ ] **Step 3: Implement** the domain aliases and refusals, the slots, the handlers, the bounds, the setting lists, sentences, responses and strings.
- [ ] **Step 4: Run all checks** — Expected: all pass (the services' own range and boolean tests still pass).
- [ ] **Step 5: Commit** — `git commit -m "Run, extend and stop a timer by voice and through LLM tools, with the target's settings"`

---

### Task 5: Core's on/off and delayed commands are taken over for Timerify targets

**Files:**
- Create: `scripts/generate_core_commands.py`, `custom_components/timerify/sentences/en/core_commands.yaml`, `sentences/ru/core_commands.yaml` (generated), `custom_components/timerify/voice/commands.py`
- Modify: `voice/__init__.py`, `core.py`, `controller.py`, `number.py`, `services.py`, `sentences/<lang>/timerify.yaml` (responses, `timerify_run_extras`), `translations/en.json`, `translations/ru.json`
- Test: `tests/voice/test_core_commands.py`

**Interfaces:**
- Consumes: `RunHandler`, `StopHandler`, `timerify_duration`, `timerify_settings`, `SETTING_SLOTS`, `settings_of`, `duration_of` (Task 4).
- Produces in `core.py`: `TimerCore.wanted_running() -> bool` — `snapshot.end is not None or self._runs_as_of(None)` (the pending wish first, then `last_actual`; an unavailable target with a timer runs, R10).
- Produces in `services.py`: `command_time: Final = probatio.All(cv.datetime, dt_util.as_utc)`, used by `ADD_COMMAND_SCHEMA["at"]`.
- Produces in `controller.py`:
  - `command_when(delay: timedelta | None, at: datetime | None) -> datetime | timedelta` — exactly one, else `ServiceValidationError("delay_or_at")`; `number.async_add_command` uses it (its tests unchanged).
  - `async_turn_off_in(when: datetime | timedelta, minutes: int | None = None, settings: Mapping[str, Any] | None = None) -> bool` — before anything runs: `off_takes_no_duration_or_settings` (the private check `async_add_command` now shares), then under the lock `at` from `when` as `async_add_command` computes it, `command_in_past` when `at <= now` (a zero delay), `duration_out_of_range` beyond `MAX_MINUTES`; when `wanted_running()`, the timer is set to end at `at` and True; otherwise nothing changes and False.
- Produces in `scripts/generate_core_commands.py`: `render(language) -> str`, `main()` writing `SENTENCES_DIR/<lang>/core_commands.yaml` for each language, plus the pure helpers the structural test uses: `command_blocks(data) -> list[CommandBlock]` (each data block of `HassTurnOn` (`"on"`) / `HassTurnOff` (`"off"`) with `metadata.slot_combination == "name_only"`; raises if a used block has `excludes_context`, local `expansion_rules`/`lists`, or a `requires_context` key other than `domain`), `delayed_shapes(data) -> list[str]` (the sentences of `HassStartTimer` blocks with `response: command`), `command_group(block) -> str` (`(s1|s2|…)` with `{name}` → `{timerify_target:name}`), `delayed_sentences(shape, block) -> list[str]`. Output, header `# Generated by scripts/generate_core_commands.py from home-assistant-intents <version>. Do not edit.`:
  - bare: per command block one data block of `TimerifyRun` (`on`) or `TimerifyStop` (`off`), sentences = the block's sentences with `{name}` substituted;
  - delayed: per (shape block, command block) one `TimerifyDelayedCommand` data block, `slots: {action: "on"|"off"}`, response `delayed`; `{timer_command:conversation_command}` → `command_group(block)`, `{timer_hours:hours}`/`minutes`/`seconds` → `…:delay_hours`/`delay_minutes`/`delay_seconds`; for `on`, a delay-last shape gives three sentences — bare, `(cmd) <timerify_run_extras> (in|after) …` and `(cmd) (in|after) … <timerify_run_extras>` — and a delay-first shape gives `(in|after) … (cmd) [<timerify_run_extras>]`, so each sentence carries the extras at most once;
  - every block: `requires_context` dropped exactly when its `domain` list contains `"switch"` (the generic phrasings apply to every Timerify target), copied otherwise.
- Produces in `voice/commands.py`: `DelayedCommandHandler` (`TimerifyDelayedCommand`, default annotations: destructive, it replaces the countdown and applies settings): slots `name`, `action` (`In(["on", "off"])`), `delay_hours`, `delay_minutes`, `delay_seconds` (`whole_slot`), `at` (`cv.string`, LLM only; parsed with `services.command_time`, an `Invalid` spoken as `invalid_command_time`), `hours`, `minutes`, `SETTING_SLOTS`. `when = command_when(<delay or None>, <at or None>)`. `on` → `controller.async_add_command("on", when, duration_of(slots), settings_of(...))`, then `at` read from `controller.snapshot.commands` by the returned id; speech slots `outcome: "command_added"`, `clock_slots(at)`, `target`. `off` → `controller.async_turn_off_in(when, duration_of(slots), settings)`; `outcome: "timer_set"` + `timer_slots`, or `outcome: "not_running"` + `target`.
- `timerify.yaml` gains `expansion_rules.timerify_run_extras` = permutation of optional `for <timerify_duration>` and `<timerify_settings>` with at least one present, and `responses.intents.TimerifyDelayedCommand.delayed` — en "Boiler turns on at 09:15." / "Boiler turns off at 09:10." / "Boiler is already off; nothing changed." ("tomorrow" as before). The bare blocks use Task 4's `TimerifyRun`/`TimerifyStop` `default` responses.
- Translations: `exceptions.invalid_command_time` (en "That is not a time Timerify can understand.").

- [ ] **Step 1: Write the failing tests** (`assist`, managed route; core data from `get_intents(language)`)

```python
async def test_bare_turn_on_runs_the_default_duration_in_strict_mode()  # P-1/R9: "turn on the boiler" → TimerifyRun,
    # NUMBER 45, "Boiler runs for 45 minutes, until 09:45."
async def test_bare_turn_on_in_loose_mode_runs_without_a_timer()  # → "Boiler is on.", NUMBER 0, target on
async def test_bare_turn_off_stops_the_timer()            # → TimerifyStop, NUMBER 0, turn_off
async def test_bare_turn_on_of_an_unavailable_target_keeps_the_wish()  # R10: target unavailable; "turn on the boiler" →
    # no failure; target back → turn_on
async def test_bare_on_off_with_an_area_stays_with_core()  # "turn off the lights in the kitchen" → HassTurnOff
async def test_turn_on_in_minutes_adds_a_pending_command()  # NEXT == START+15 min; advance → turn_on, NUMBER 45 (R9)
async def test_spec_example_without_a_unit_word()         # §6.4: "turn on the AC in 15 minutes for an hour, cooling, 24" →
    # advance 15 min → cool, 24.0; AC_NUMBER 60
async def test_extras_before_the_delay()                  # "turn on the AC for an hour in 15 minutes" → the same command
async def test_pending_command_by_voice_survives_manual_use()  # P2
async def test_turn_off_in_minutes_on_a_running_target_sets_the_timer()  # 45 left → NUMBER 10, no command
async def test_turn_off_in_minutes_replaces_a_shorter_timer()  # 5 left → 10
async def test_turn_off_in_minutes_on_an_off_target_changes_nothing()  # ACTION_DONE, "Boiler is already off; nothing changed."
async def test_turn_off_in_on_a_loose_open_run_sets_the_timer()
async def test_turn_off_in_on_an_unavailable_running_target_sets_the_timer()  # R10
async def test_turn_off_in_follows_a_turn_on_in_flight()  # loose run_open held (fake holds the call) → timer set, True
async def test_turn_off_in_after_a_stop_in_flight_changes_nothing()  # stop held → "already off", no turn_on
async def test_delay_with_seconds_is_exact()              # off "in 1 minute and 30 seconds" → ENDS START+90 s; on "in 30 seconds"
async def test_delayed_off_beyond_a_day_is_refused()      # "in 30 hours" → duration_out_of_range
@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_generated_file_covers_every_core_shape_and_command(language)  # P-6 structural proof: for every delayed shape ×
    # command block and every bare command block, a generated block with that action/intent, slots and context contains
    # delayed_sentences(shape, block) (resp. the bare sentences)
@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_core_commands_on_a_target_are_taken_over(language)  # bounded: per (shape sentence × command sentence) pair
    # and per bare command sentence one sample, optionals skipped, only blocks whose context admits "switch", name
    # "Boiler", delay 2 h / 15 min / 30 s → our intent, the action, the delay; never HassTurnOn/HassTurnOff/HassStartTimer
@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_core_commands_on_other_entities_stay_with_core(language)  # the same samples on fake_fan "Fan" → HassTurnOn/
    # HassTurnOff/HassStartTimer; advance for three of them → the fan is switched by core
def test_generated_core_commands_are_current()            # render(lang) == committed file
def test_generator_refuses_a_block_it_does_not_understand()  # excludes_context / local lists → raises
async def test_llm_delayed_command()                      # on + delay_minutes 15 + minutes 60 + cool/24 → command_added at
    # "09:15"; off running → timer_set; off idle → not_running
async def test_llm_delayed_command_at_a_clock_time()      # P-5: {"action": "on", "at": "2026-01-05 10:30:00"} (local) →
    # NEXT == 08:30 UTC; delay and at together → delay_or_at text; "soon" → invalid_command_time text
async def test_llm_zero_delay_off_is_refused()            # all delays 0 → command_in_past text, target still on
async def test_llm_delayed_command_beyond_a_week_is_refused()  # command_too_far
async def test_llm_delayed_off_with_a_duration_is_refused()  # off_takes_no_duration_or_settings
```

- [ ] **Step 2: Run `uv run python scripts/generate_core_commands.py && uv run pytest tests/voice/test_core_commands.py tests/test_commands.py -v`** — Expected: new tests FAIL.
- [ ] **Step 3: Implement** `wanted_running`, `command_time`, `command_when`, `async_turn_off_in`, the generator (run it, commit its output), the handler, `timerify_run_extras`, responses and strings.
- [ ] **Step 4: Run all checks** — Expected: all pass; `uv run pytest tests/voice` well under a minute.
- [ ] **Step 5: Commit** — `git commit -m "Take over core's on/off and delayed commands for Timerify targets"`

---

### Task 6: What is scheduled, and cancelling it, by voice

**Files:**
- Modify: `custom_components/timerify/voice/commands.py`, `voice/__init__.py`, `controller.py`, `sentences/en/timerify.yaml`, `sentences/ru/timerify.yaml`
- Test: `tests/voice/test_planned_commands.py`

**Interfaces:**
- Consumes: `clock_slots`, `duration_of` (Tasks 1, 4); Task 5's voice-made commands.
- Produces in `controller.py`: `async_cancel_command(command_id) -> Command` (now returns the cancelled command; the number entity ignores it); `async_cancel_commands(which: Literal["next", "all"]) -> tuple[Command, ...]` — under the lock, the first or every pending command; empty when none.
- Produces in `voice/commands.py`:
  - `ListCommandsHandler` (`TimerifyListCommands`, read only): `name` → speech slots `target`, `count`, `commands`: `[{"id", "action", "at", "in_days", "minutes" (or None), "settings"}]` in time order.
  - `CancelCommandsHandler` (`TimerifyCancelCommands`, `idempotent=True`): `name`, `which` (`In(["next", "all"])`, no default), `command_id` (`cv.string`); in the handler `which = slots.get("which", {}).get("value", "all")`; `command_id` given → `async_cancel_command`, else `async_cancel_commands(which)`; speech slots `target`, `which`, `cancelled`, `commands` (the cancelled ones). Its description says `which` defaults to all.
- Sentences (en; ru the same meanings): list — "what is (planned|scheduled) for [<the>] {name}", "what (commands are|is) pending (for|on) [<the>] {name}"; cancel — "cancel (the|all) (planned|pending) commands (for|of) [<the>] {name}" (`slots: {which: "all"}`), "cancel the next (planned|pending) command (for|of) [<the>] {name}" (`slots: {which: "next"}`).
- Responses (en): "Boiler has 2 planned commands: turn on at 09:15 for 1 hour; turn off at 11:00." / "Boiler has no planned commands." / "Cancelled 2 planned commands for Boiler." / "Cancelled the next planned command for Boiler: turn on at 09:15." Settings are not spoken.

- [ ] **Step 1: Write the failing tests**

```python
async def test_what_is_scheduled_lists_the_commands()      # "turn on the boiler in 15 minutes for an hour" + add_command off
    # at START+2 h → "Boiler has 2 planned commands: turn on at 09:15 for 1 hour; turn off at 11:00."; QUERY_ANSWER
@pytest.mark.parametrize("text", ["what is planned for the boiler", "what is scheduled for the boiler",
                                  "what commands are pending for the boiler"])
async def test_list_phrasings(text)
async def test_what_is_planned_without_commands()
async def test_planned_command_tomorrow_says_tomorrow()
async def test_cancel_all_planned_commands()
async def test_cancel_the_next_planned_command()
async def test_cancel_without_commands_says_so()
async def test_cancelled_command_does_not_run()
async def test_russian_planned_commands_follow_the_plural_rules()  # COMMAND_CLASSES (at most MAX_COMMANDS)
@pytest.mark.parametrize("intent_type", ["TimerifyListCommands", "TimerifyCancelCommands"])
async def test_russian_sentences_reach_their_intent(intent_type)
async def test_llm_lists_and_cancels_by_id()               # list → ids; cancel {"name", "command_id"} only → gone, the
    # cancelled command in the data; unknown id → unknown_command text
async def test_llm_cancel_without_which_cancels_all()
```

- [ ] **Step 2: Run `uv run pytest tests/voice/test_planned_commands.py -v`** — Expected: FAIL.
- [ ] **Step 3: Implement** the controller changes, both handlers, sentences and responses.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "List and cancel planned commands by voice and through LLM tools"`

---

### Task 7: The schedule on and off by voice

**Files:**
- Create: `custom_components/timerify/voice/intervals.py`
- Modify: `voice/__init__.py`, `voice/sentences.py`, `voice/files.py`, `const.py`, `controller.py`, `sentences/en/timerify.yaml`, `sentences/ru/timerify.yaml`, `translations/en.json`, `translations/ru.json`
- Test: `tests/voice/test_schedule_by_voice.py`, `tests/voice/test_voice_entry.py`

**Interfaces:**
- Consumes: `async_set_interval_enabled` (phase 3); `build`, `VoiceName` (Task 2).
- Produces in `const.py`: `LIST_INTERVAL: Final = "timerify_interval"`; the source declares it empty.
- Produces in `voice/sentences.py`: `interval_names(hass) -> list[VoiceName]` (the loaded timers' interval subentry titles, cleaned and escaped as targets are); `build(..., intervals=...)` fills `timerify_interval`. A title edit reloads the timer, so `SIGNAL_TIMERS_CHANGED` regenerates.
- Produces in `controller.py`: `async_set_schedule_enabled(enabled: bool, interval: str | None = None) -> tuple[str, ...]` — the titles of the intervals switched: every interval of the timer, or the one whose title equals `interval` by `remove_punctuation(...).strip().casefold()`; refuses `no_schedule` (`{target}`) and `unknown_interval` (`{target}`, `{interval}`) before switching; each through the existing enable path, under the lock.
- Produces in `voice/intervals.py`: `SetScheduleHandler` (`TimerifySetSchedule`, `idempotent=True`): `name`, `enabled` (`cv.boolean`; sentences give `true`/`false`), `interval` (`cv.string`) → `async_set_schedule_enabled`; speech slots `target`, `enabled`, `interval`, `count`.
- Sentences (en; ru the same meanings): "<turn> (on|off) [<the>] {name} schedule", "<turn> (on|off) the schedule of [<the>] {name}", "(enable|disable|pause|resume) [<the>] {name} schedule", and the same with "[<the>] {timerify_interval:interval} schedule of [<the>] {name}" (on/off as separate data blocks with `slots: {enabled: true|false}`).
- Responses (en): "The schedule of Boiler is off." / "The Morning schedule of Boiler is on."

- [ ] **Step 1: Write the failing tests**

```python
async def test_turning_off_the_schedule_switches_every_interval_off()
async def test_turning_off_the_schedule_stops_a_scheduled_run()   # S2
async def test_turning_the_schedule_on_during_a_window_runs_the_target()
async def test_one_interval_by_its_title()               # title "Morning" → only Morning off
async def test_interval_titles_follow_edits()            # retitle → advance(seconds=VOICE_SYNC_COOLDOWN) → listed has the new one
async def test_interval_title_with_template_characters_is_escaped()  # "Morning (weekdays)"
async def test_target_without_intervals_is_refused()     # no_schedule text
async def test_llm_set_schedule()                        # {"name": "Boiler", "enabled": false} → count 2; "Evening" → unknown_interval
@pytest.mark.parametrize("enabled", [True, False])
async def test_russian_sentences_reach_set_schedule(enabled)
```

- [ ] **Step 2: Run `uv run pytest tests/voice/test_schedule_by_voice.py tests/voice/test_voice_entry.py -v`** — Expected: FAIL.
- [ ] **Step 3: Implement** the list, the controller method, the handler, sentences, responses and strings.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Switch a timer's schedule on and off by voice and through LLM tools"`

---

### Task 8: Phase verification and docs

**Files:**
- Modify: `README.md`, `RULINGS.md`, `docs/followups.md`, `CLAUDE.md` (status line), `manifest.json` and `pyproject.toml` (`version` `0.4.0`), `uv.lock`, `scripts/smoke/run.py`

- [ ] **Step 1: README** — section "Voice and AI": what can be said (the en phrases of Tasks 1, 4–7 and the bare and delayed on/off; Russian too), that bare "turn on/off X" of a Timerify target is a Timerify command (strict: the default duration; loose: on without a timer), that core's delayed commands are taken over for Timerify targets only, including the bare-name form "in 15 minutes boiler"; "turn off X in N" on a running target sets the timer, on an off one changes nothing; the **Voice settings** entry (from the Timerify menu; the languages; the files, rewritten on every timer change; removed by unticking, disabling or removing it); remove the entry before uninstalling Timerify; the manual alternative (copy every file of `custom_components/timerify/sentences/<lang>/` into `config/custom_sentences/<lang>/timerify_manual/`, add `timerify_names.yaml` with the `timerify_target` list — `in` the name as said with punctuation removed, escaped only if it contains one of `()[]{}<>|@`, then backslashes escaped too; `out` the name as Home Assistant shows it; never both routes; redo after every update and rename; a malformed file breaks Assist for the whole language); exposure (the target must be exposed; Timerify's own entities are not by default; an interval switch that Home Assistant already decided to expose under 0.3.0 stays exposed — unexpose it under Settings → Voice assistants → Expose); LLM agents and the `timerify__` tools (they also take a clock time for a planned command); what is not by voice (a clock time, subtracting time). Update "What is not here yet" and "Verification".
- [ ] **Step 2: RULINGS.md and followups** — a "Phase 4" part with V1 (as reversed by P-1), V2–V8 and the plan rulings below, P-1–P-6 among them, each Decision — why — cost if wrong; `docs/followups.md` Later: "Voice commands at a clock time" (P-5), "A target that is not in the entity registry: a changed friendly name is listed only after its timer reloads", "A one-time repair issue listing interval switches exposed under 0.3.0".
- [ ] **Step 3: Smoke script** — `scenario_voice`, before `scenario_restart`: add the Voice settings entry through the menu (`{"write_sentence_files": true, "languages": ["en"]}`); `POST /api/conversation/process` "how much time is left on smoke boiler" → `error`, `no_valid_targets` (an input_boolean is not exposed by default); expose it (`homeassistant/expose_entity`, assistant `conversation`); "turn on smoke boiler for 2 minutes" → `action_done`, on; "how much time is left on smoke boiler" → `query_answer`, speech starts "2 minutes left on Smoke boiler"; "turn off smoke boiler in 1 minute" → `action_done`, off a minute later; "turn on smoke boiler" → on with the 30-minute default (number reads 30); "turn off smoke boiler" → off. The script logs every speech it got.
- [ ] **Step 4: Owner checklist (report, not a gate)** — render every ru template for counts 1, 2 and 5 (one ru sample per intent through the test helpers) into the report so the owner can read the Russian wording; the class tests prove only the three-way partition.
- [ ] **Step 5: Run hassfest** — as in Task 3 — Expected: no errors.
- [ ] **Step 6: Run the smoke test** — `uv run python scripts/smoke/run.py` — Expected: every scenario passes.
- [ ] **Step 7: Run all checks on the final tree** — `uv run pytest && uv run ruff check && uv run ruff format --check && uv run mypy` — Expected: all pass; report the test count and the time of `tests/voice`.
- [ ] **Step 8: Commit** — `git commit -m "Document phase 4 and bump the version to 0.4.0"`

---

## Plan rulings

Decision — why — cost if wrong. V1 is reversed by P-1; V2–V8 are followed except where an entry says it refines one.

- **P-1: bare name-only "turn on X" / "turn off X" of a Timerify target is a Timerify command** (reverses V1) — spec R9 names "voice 'turn on X' routed to Timerify": on is R9 (loose: open run; strict: default duration) and off stops the timer, through the controller, so an unavailable target keeps its wish (R10) and the answer is Timerify's; the phrasings are core's own `name_only` ones, generated, so phrasings with an area, a floor or a device class stay with core — a phrasing that core adds in a newer intents release reaches core until Timerify is regenerated.
- **P-2: the Voice settings entry holds the option and the languages; the menu offers it only while none exists; an abort with its own reason `voice_settings_exist` remains for a race** (refines V3, spec §6.2) — the spec's entry; `already_configured` says "This entity already has a timer" — none.
- **P-3: voice offers every §5.4 setting the target supports: HVAC mode and temperature by their own words, and one "percent" and one "mode" slot whose meaning each domain row declares (brightness/percentage/humidity; fan mode/preset/humidifier mode/operation mode); the mode lists carry only values the targets support, the HVAC words are translated per language, device mode strings as the device names them** (spec §5.4) — one word per meaning, the row stays the single description of a domain, and `validate_settings` refuses as for the services — a device mode string that is hard to say ("eco_plus_2") must be said as written, underscores as spaces.
- **P-4: the temperature's unit word is optional, so the spec's "…, cooling, 24" matches** — the spec's own example — a bare number after a duration is taken as a temperature, and a target without one refuses it.
- **P-5: an LLM may plan a command at a clock time (`at`, parsed by the service's own `command_time`, exactly one of delay and `at` by `command_when`); voice sentences stay delay-only** — the tool gets the service's reach through the same controller path; a clock-time grammar is not in core's delayed shapes and the spec's example is a delay — "turn on the boiler at 7:30" has no match (follow-up).
- **P-6: the takeover is proven by a structural test over every core shape × command pair; behaviour is sampled boundedly (one sample per pair, optionals skipped); the voice suite runs in well under a minute** (refines V2) — exhaustive sampling is 180,544 conversations for en alone (pre-flight finding 1) — a substitution bug that only shows with optionals present is caught only by the bounded samples of the other intents.
- **The core phrasings are generated at development time by `scripts/generate_core_commands.py` from the pinned intents and committed; a test fails when the file is stale; the generator refuses blocks it does not understand** (interprets V2's "generated from the installed data") — the manual route needs complete files in the repository; a future release cannot silently widen or narrow the takeover — users on a newer Home Assistant with new shapes reach core until a Timerify release.
- **`requires_context` is dropped exactly when a block's domain list contains `switch`** — that is core's generic on/off block in both languages; every Timerify target, whatever its domain, can be switched and delayed — a light-words or open/close phrasing still needs a light or cover target.
- **Success speech is rendered by the built-in agent from response templates in `sentences/<lang>/`; handlers set speech slots only; refusals are spoken by the handler from `translations/<lang>.json` `exceptions`, with a setting named by its translated field name and a time as `HH:MM`** (refines V6) — backend translations have no plural rules, the LLM path never renders templates, `async_set_error` is quiet — a caller of `intent/handle` other than the two agents gets no success speech.
- **A target that does not match raises core's `MatchFailedError`, matched among the loaded timers' targets only; no candidate at all fails as an unknown name without asking the matcher** (refines V5) — core's translated answers; an empty `states` would search the whole house — the LLM's error text is core's.
- **Delays may carry seconds; durations are whole minutes; a zero delay is `command_in_past`** — a delay is a moment; the services' whole-minute rule for durations; a zero "turn off in" would otherwise stop at once — "turn off in 90 seconds" shows 2 minutes on the number for 30 seconds.
- **The controller refuses a duration outside 1..`MAX_MINUTES`; adding keeps the phase-1 clamp (the end is never more than a day ahead), whatever a voice or an LLM asks** — the core silently caps a duration, so "for 30 hours" would run 24 without a word; adding was ruled a clamp in phase 1 and the answer says the real end — "add 30 hours" gives a day and says until when.
- **Booleans for number settings and fractions for whole ones are refused in `validate_settings`; duration slots use a hinted whole-number validator** (pre-flight finding 6) — the phase-2 rulings, in the one place every channel passes; `Coerce` would turn `true` into 1 % and 2.5 into 2 — none.
- **"Turn off X in N" decides under the lock by `TimerCore.wanted_running()`: a timer above zero, else the pending wish, else the target on** — the desired state (R10), including commands in flight — none.
- **Pending commands are cancelled by voice as "all" (default) or "the next"; an LLM may cancel by id; `async_cancel_command` returns what it cancelled** — a voice cannot say an id — none.
- **The schedule is switched as a whole or one interval by its title; the lookup and its refusals live in `controller.async_set_schedule_enabled`** — one path; generated titles cannot be said — a user with generated titles switches all or none.
- **No subtract phrase** — §6.4 lists set/add/stop; set covers shortening — "10 minutes less" has no match.
- **The config flow's `user` step is a menu (`target`, `voice_settings`); the target form is step `target`; the options flow keeps `init` for timers and skips to `voice_settings` for the voice entry; the kind is the option `kind`, narrowed with `TypeIs`** — the group precedent — existing flow tests and the smoke `add_timer` pick `target` first.
- **The voice entry's title is translated when it is created** — `async_config_entry_title` is synchronous — it stays in the language of its creation.
- **Files are removed on untick, removal, disable and for languages no longer chosen; kept on reload; written only when their text changes; then one `conversation.reload` without a language; listeners attach after the first sync and ignore events while stopping** (refines V3, V7) — no churn at start-up or reload; a reload by language misses regional caches — every cached language is rebuilt on a change.
- **The names list follows the default agent (aliases with the computed name, `remove_punctuation`, empty names skipped); `in` is escaped only when hassil would read it as a template; `out` is the name; `context.domain` is the target's** (V7) — what Home Assistant matches; a lone backslash is literal in hassil — a name differing only in characters the default agent keeps must be said with them.
- **Validation before writing parses every Timerify sentence, resolves every list and rule reference, and checks that every generated value round-trips to its spoken text; a failure leaves the old file and logs an error** (V7) — `from_dict` alone parses sentences lazily, and one bad file breaks Assist for its language — a valid but stale file stays until the cause is fixed.
- **A non-Timerify entity sharing a target's name is not reachable through Timerify's phrases (bare on/off included)** — the static list cannot tell them apart — "turn off X" always means the Timerify target.
- **Regeneration triggers: timer setup/unload signal, entity and device registry name changes, debounced; the first write before setup returns when running, else at start; capability changes (new modes) are picked up at the next trigger** — event-driven, one write per burst — a friendly name of an unregistered target, or a mode added by a firmware update, is listed only after the next trigger.
- **The manual route lives in `custom_sentences/<lang>/timerify_manual/`; the managed entry warns when both exist** — the managed file has the same name, and removing it would leave a half-installed manual copy that breaks matching — none.
- **A managed file without Timerify's handlers (Timerify failed to load or was uninstalled with its entry left) makes the built-in agent raise on matched phrases, core's delayed commands on targets included; the README says to remove the entry first** — no public API catches `UnknownIntent` — Assist errors on those phrases until the file is removed.
- **hassil is imported directly; `after_dependencies: ["conversation", "llm"]`** (V8) — requirements of after-dependencies are installed first; hassfest checks component imports — none.
- **Interval switches are `EntityCategory.CONFIG`** (V4) — the switch configures the timer's schedule; categorised entities are not exposed by default — it moves to the device page's configuration section, leaves auto-generated dashboards and is skipped by service calls that target its device or area; one Home Assistant already decided to expose under 0.3.0 stays exposed (follow-up: a repair issue).
- **Tools are offered for the Assist API only, while a target is exposed to the asking assistant; descriptions, titles and the prompt are English; annotations as core sets them (running a timer and planning a command are destructive and not idempotent, as turning on and starting a timer are in core; adding time is additive; the prompt lists the names as a JSON list)** — core's patterns — an LLM in another language reads English descriptions, as with every core tool.
- **Russian is tested without Cyrillic in tests: inputs sampled from the Russian files, plural forms proven by classes** — the pre-commit hook; this proves that the ru templates parse, reach our handlers and outrank core, and that the three forms partition the counts, not which word goes with which class nor that Cyrillic, inflected names work — the owner reads the rendered ru texts (Task 8 Step 4); a swapped "few"/"many" passes the tests.
- **Russian answers put the target's name first, in the nominative, followed by a colon** — names cannot be declined — none.
- **Voice tests run in `tests/voice/` with `hass_tmp_config_dir` and an empty `configuration.yaml`** (V8) — none.

---

## Appendix: pre-flight (shared files and interfaces; gate after each task)

| Pair | Shared | Conflict and resolution | Gate green after the later task |
|---|---|---|---|
| T1 → T2 | `voice/base.loaded_timers`, `tests/voice/helpers.py` | T2 adds the voice-entry filter; T1's tests keep the manual route (`copy_sentences` into `timerify_manual/`), later tasks use `add_voice_entry` | yes |
| T1 → T4–T7 | `HANDLER_TYPES`, `sentences/<lang>/timerify.yaml` | each appends handlers, its intent, lists (prefixed) and responses; the source tests guard parity, prefixes and slot types | yes |
| T1 → T3 | handler ClassVars (`tool_name`, `title`, `description`, annotations) | T3's assertions iterate `HANDLER_TYPES`, so later handlers need no T3 edit | yes |
| T2 → all | `config_flow.py` `user` menu; `tests/test_config_flow.py`; smoke `add_timer` | T2 edits the target flows to pick `target` and updates `add_timer`; options `init` keeps its id for timers | yes |
| T2 → T4, T7 | `voice/sentences.build(sources, names, ...)`, `SentenceFiles.async_sync` | T4 adds `settings: VoiceSettingValues = <empty>`, T7 `intervals=()`, both keyword with defaults; each source declares its list empty | yes |
| T2 → T5 | `load_sources` reads every `*.yaml` of a language; `validate` (c) | T5's `core_commands.yaml` is picked up unchanged; its references (`timerify_run_extras`, core rules) resolve in the merge | yes |
| T4 → T5 | `RunHandler`/`StopHandler` responses, `timerify_duration`, `timerify_settings`, `SETTING_SLOTS`, `settings_of`, `duration_of`, `duration_out_of_range` | T5's bare blocks reuse T4's intents and `default` responses; the extras reuse T4's rules | yes |
| T4 → T5 → T6 → T7 | `controller.py` | T4 bounds; T5 `command_when`, the shared off check, `async_turn_off_in`; T6 `async_cancel_command` returns a `Command` (callers that ignore it unchanged), `async_cancel_commands`; T7 `async_set_schedule_enabled`; none changes another's signature | yes |
| T5 | `number.py`, `services.py` | `number.async_add_command` calls `command_when`; `ADD_COMMAND_SCHEMA["at"]` uses `command_time`; `tests/test_commands.py` assertions unchanged | yes |
| T4 | `domains.py`, `tests/test_domains.py` | `voice` field and boolean refusal; the services' own boolean tests still pass (schema refuses first) | yes |
| T5 → T6 | `voice/commands.py` | T6 adds two handlers to T5's module | yes |
| T3 → phase 3 | `switch.py` | the category changes no unique id or name | yes |
| T2, T4, T5, T7 | `translations/en.json` + `ru.json`, `test_translations.py` | every task adds its keys to both files | yes |
| T1 → T3 → T8 | `manifest.json`, hassfest | T1 adds `after_dependencies` (`conversation`, `llm`); T3 runs hassfest first; T8 edits only `version` | yes |
