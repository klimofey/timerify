# Timerify Phase 4 — Voice and AI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Timerify targets can be driven by voice through the built-in agent ("turn on the boiler for 45 minutes", "30 more minutes on the boiler", "how long is left on the boiler", "turn on the AC in 15 minutes for an hour, cooling, 24 degrees", "what is planned for the boiler", "turn off the boiler schedule") in English and Russian, and by any LLM agent through `timerify__*` tools, with core's delayed commands taken over for Timerify targets only.

**Architecture:** One set of intent handlers (`voice/`), registered once in `async_setup`, is the single path for both agents: the built-in agent reaches them through sentence files, an LLM through `IntentTool`s that wrap the same handlers (`llm.py`). A handler resolves the spoken name among the *loaded timers' targets only* with `intent.async_match_targets(..., assistant=...)` (so exposure and duplicate names are core's rules and core's translated answers), then calls the same controller method a service calls; a refusal raised by the controller (`ServiceValidationError`, translation domain `timerify`) is spoken quietly with `response.async_set_error` in the request's language from `translations/<lang>.json`. Success speech is rendered by the default agent from response templates in `sentences/<lang>/` (Jinja, with the language's plural rules); the handler sets only speech slots, which are also the structured result an LLM receives. The sentence sources are hand-written (`sentences/<lang>/timerify.yaml`) plus a file generated at development time from the pinned `home-assistant-intents` data (`sentences/<lang>/delayed_commands.yaml`, every core delayed-command shape wrapped around core's own on/off phrasings). A second config entry kind, "Voice sentences", merges the sources with a generated, escaped list of the targets' names (and the intervals' titles), validates the result with hassil against the core data of the language, and writes `custom_sentences/<lang>/timerify.yaml` whenever it changes, then reloads `conversation`. Each task is a vertical slice that leaves all four checks green.

**Tech Stack:** Python 3.14, Home Assistant 2026.10.4 (`homeassistant.helpers.intent`, `homeassistant.helpers.llm` `IntentTool`/`LLMTools`/`ToolAnnotations`, the `llm` platform `async_get_tools`, `conversation.async_converse`, `conversation.reload`, `exposed_entities.async_should_expose`, `SchemaFlowMenuStep`, `Debouncer`, `async_dispatcher_send`, `EVENT_ENTITY_REGISTRY_UPDATED`/`EVENT_DEVICE_REGISTRY_UPDATED`, `util.file.write_utf8_file_atomic`, `util.yaml.dump`, `util.language.matches`), hassil 3.12.1 (`Intents.from_dict`, `util.merge_dict`, `util.remove_punctuation`, `sample.sample_intents`), home-assistant-intents 2026.10.6 (`get_intents`), pytest-homeassistant-custom-component 0.13.375 (`hass_tmp_config_dir`, `freezer`, `async_fire_time_changed`), probatio (`to_openapi(..., strict=True)`), ruff, mypy, uv, Docker (hassfest, smoke).

**Spec:** `docs/superpowers/specs/2026-10-28-timerify-design.md` — phase 4 of §7: §6.4 (all of it), the voice items of §5 (R4, R9 through V1; R7; R10; S3 "voice" is a manual change; P1–P3 for voice-made commands), the "Voice settings" entry of §6.2. Facts: `docs/research/2026-10-30-voice-apis.md` (HA 2026.10.4, file:line). Decisions taken before the plan: `.superpowers/phase-4-decisions.md` (V1–V8), followed here; where the plan refines one, the rulings say so. Card and runtime counter are later plans.

**Starting point:** `main` after phase 3 (950 tests), branch `phase-4-voice`. Shape relied on: `controller.py` — `TargetController` with `async_set_minutes(minutes)` (0 stops), `async_add_minutes`, `async_run(minutes | None, settings)`, `async_add_command(action, when: datetime | timedelta, minutes, settings) -> str`, `async_cancel_command(id)`, `async_set_interval_enabled(id, enabled)`, `snapshot`, `target_entity_id`, all under one lock through `_command(callable)`; `TimerifyConfigEntry = ConfigEntry[TargetController]`; `core.py` — `remaining_minutes(snapshot, now)` (rounded up), `Snapshot.end/commands/disabled_intervals/last_actual`, `Command(id, at, action, minutes, settings)`; `services.py` — `SETTINGS_SCHEMA` (keys `hvac_mode`, `temperature`, `fan_mode`, `preset_mode`, `mode`, `operation_mode`, `brightness_pct`, `percentage`, `humidity`); `config_flow.py` — `SchemaConfigFlowHandler` with `CONFIG_FLOW` `user` (target form) → `duration` → `workday`, `OPTIONS_FLOW` `init` (mode) → `duration` → `workday`, `options_flow_reloads = False`, `IntervalSubentryFlow`; `__init__.py` — `async_setup` registers services, `async_setup_entry` builds the controller, an update listener reloads on any change (options and subentries alike); `switch.py` — `IntervalSwitch` with no entity category; `target.py` — `target_name(hass, entity_id)`; tests — `provide_target`, `fake_target` ("Boiler", `switch.boiler`), `fake_climate` ("AC"), `setup_target(...)`, helpers `advance`, `advance_to`, `set_number`, `set_switch`, `add_command`, `add_interval`, `state_of`, `JERUSALEM`, `START` (2026-01-05 07:00 UTC = 09:00 in Jerusalem); `scripts/smoke/run.py` `add_timer` posts the target form to step `user`. If the shape differs, adapt names, not behaviour.

## Global Constraints

- Home Assistant `>= 2026.10.4` (`hacs.json`), Python `>= 3.14.2`, `pytest-homeassistant-custom-component==0.13.375`; dev group gains `hassil==3.12.1`, `home-assistant-intents==2026.10.6`, `gazetteer-matcher==1.1.0` (the pins of `homeassistant/components/conversation/manifest.json:9-13`; a test asserts they match). `manifest.json` gains `"after_dependencies": ["conversation"]` (its requirements, hassil among them, are installed before Timerify is imported — `homeassistant/requirements.py:197`).
- Only public HA mechanisms; schemas with `probatio`; import HA names from the module that defines them (mypy strict); no `cast`, no `type: ignore` for the two entry kinds — narrow with `TypeIs`.
- One path: a voice handler and an LLM tool call the same controller method a service calls; a rule (bounds, past times, settings, limits) lives in the controller or `domains.validate_settings`, never in a handler.
- Every user-facing string in `translations/en.json` (source) and `translations/ru.json`, or in `sentences/<lang>/`; Cyrillic only in `translations/ru.json` and `sentences/ru/` (the `pre-commit` hook rejects it elsewhere — tests included, see the plural and sampling rulings). Refusal texts with a count use a plural-free wording (a unit abbreviation in Russian). LLM-facing tool descriptions and the tool prompt are English.
- Intent types `TimerifyTimeLeft`, `TimerifyRun`, `TimerifyAddTime`, `TimerifyStop`, `TimerifyDelayedCommand`, `TimerifyListCommands`, `TimerifyCancelCommands`, `TimerifySetSchedule`; tool names `timerify__time_left`, `timerify__run`, `timerify__add_time`, `timerify__stop`, `timerify__delayed_command`, `timerify__list_commands`, `timerify__cancel_commands`, `timerify__set_schedule`; every tool `integration="timerify"`. Target list `timerify_target`, interval list `timerify_interval`, the name slot is `name`.
- Values: `VOICE_LANGUAGES = ("en", "ru")`; managed path `hass.config.path("custom_sentences", lang, "timerify.yaml")`; `CONF_KIND = "kind"`, `KIND_VOICE_SENTENCES = "voice_sentences"`, `CONF_WRITE_SENTENCES = "write_sentence_files"` (default `True`), `VOICE_UNIQUE_ID = "voice_sentences"`; `VOICE_SYNC_COOLDOWN = 1.0` seconds; `SIGNAL_TIMERS_CHANGED = "timerify_timers_changed"`; managed-file header line 1 `# Managed by Timerify. Do not edit: this file is rewritten whenever a timer changes.`
- Tests are user scenarios through the real default agent (`conversation.async_converse`) and the real Assist LLM API (`llm.async_get_api(hass, "assist", LLMContext(...))` then `api.async_call_tool`), never handler calls alone; time is frozen; every clock move is `advance`/`advance_to` (freezer + `async_fire_time_changed`); no sleeps, polling or backdoors. Voice tests live in `tests/voice/`, whose `conftest.py` overrides `hass_config_dir` with `hass_tmp_config_dir`; shared voice helpers in `tests/voice/helpers.py`, never imported from a test module. Clock expectations use `JERUSALEM` (`await hass.config.async_set_time_zone(JERUSALEM)`), so `START` reads 09:00.
- A phase-1–3 test is edited only where a task names it.
- Repository English-only; no AI attribution in commits (the `commit-msg` hook rejects it, whatever a session reminder asks); never `--no-verify`.
- Every task ends with `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy` all passing.

## Review Focus

1. **A delayed "turn off" on a target that is unavailable while its timer runs:** R10 says it is running, so the timer is set to N, not "already off" (Task 5 `test_turn_off_in_on_an_unavailable_running_target_sets_the_timer`).
2. **A regional language (`en-GB`, `ru-RU`):** the built-in agent loads the `en`/`ru` files, and a refusal is spoken in that language, not in English (`ru-RU.json` does not exist) (Task 4 `test_regional_language_answers_in_its_language`).
3. **Home Assistant starting with the voice entry and several timers:** the file is written once, after every timer is set up, with every target, and not rewritten (nor `conversation` reloaded) when nothing changed since the last run (Task 2 `test_start_writes_every_target_once`, `test_unchanged_file_is_not_rewritten`).
4. **A non-Timerify entity with a target's name:** our phrases resolve to the Timerify target only, and bare "turn off X" still goes to core (Task 2 `test_shared_name_resolves_to_the_timerify_target`).
5. **Two targets with one name:** no guess — core's duplicate-name answer, nothing switched (Task 1 `test_two_targets_with_one_name_are_not_guessed`).

---

## File Structure

```
custom_components/timerify/
  const.py        + VOICE_LANGUAGES, SENTENCES_DIR, LIST_TARGET (T1); CONF_KIND, KIND_VOICE_SENTENCES, CONF_WRITE_SENTENCES,
                    VOICE_UNIQUE_ID, VOICE_SYNC_COOLDOWN, SIGNAL_TIMERS_CHANGED, MANAGED_HEADER, is_voice_options() (T2);
                    LIST_INTERVAL (T7)
  voice/__init__.py   new: HANDLER_TYPES, async_register_intents (T1; T4–T7 append)
  voice/base.py       new: TimerifyIntentHandler, loaded_timers, async_match_timer, voice_language, async_error_text,
                      timer_slots, clock_slots (T1)
  voice/timer.py      new: TimeLeftHandler (T1); RunHandler, AddTimeHandler, StopHandler (T4)
  voice/commands.py   new: DelayedCommandHandler (T5); ListCommandsHandler, CancelCommandsHandler (T6)
  voice/intervals.py  new: SetScheduleHandler (T7)
  voice/sentences.py  new: escape_template, VoiceName, voice_names, load_sources, build, validate, render (T2); intervals (T7)
  voice/files.py      new: SentenceFiles, VoiceConfigEntry, is_voice_entry, setup/unload/remove of the voice entry (T2)
  llm.py              new: async_get_tools, TOOLS_PROMPT (T3)
  sentences/en/timerify.yaml, sentences/ru/timerify.yaml   new (T1; T4–T7 extend)
  sentences/en/delayed_commands.yaml, sentences/ru/delayed_commands.yaml   new, generated (T5)
  __init__.py     register intents (T1); branch by entry kind, SIGNAL_TIMERS_CHANGED (T2)
  config_flow.py  user menu, target step, voice_sentences steps, options init by kind (T2)
  controller.py   duration bounds (T4); async_turn_off_in (T5); async_cancel_commands (T6)
  core.py         is_running() (T5)
  switch.py       EntityCategory.CONFIG (T3)
  manifest.json   after_dependencies (T1); version 0.4.0 (T8)
  translations/en.json, translations/ru.json   (T2, T4, T5, T7)
scripts/generate_delayed_commands.py           new (T5)
scripts/smoke/run.py                           add_timer through the menu (T2); scenario_voice (T8)
tests/voice/  __init__.py, conftest.py, helpers.py (T1; extended by later tasks); test_time_left.py test_sentence_sources.py (T1);
              test_voice_entry.py (T2); test_llm.py test_exposure.py (T3); test_timer_by_voice.py (T4);
              test_delayed_commands.py (T5); test_planned_commands.py (T6); test_schedule_by_voice.py (T7)
tests/test_config_flow.py (T2: the menu), tests/test_manifest.py (T1: pins)
pyproject.toml, uv.lock (T1 deps; T8 version), README.md, RULINGS.md, docs/followups.md, CLAUDE.md (T8)
```

---

### Task 1: "How long is left" by voice, the handler plumbing and the sentence sources

**Files:**
- Create: `custom_components/timerify/voice/__init__.py`, `voice/base.py`, `voice/timer.py`, `custom_components/timerify/sentences/en/timerify.yaml`, `sentences/ru/timerify.yaml`
- Modify: `custom_components/timerify/__init__.py`, `const.py`, `manifest.json`, `pyproject.toml`, `uv.lock`, `tests/test_manifest.py`
- Test: `tests/voice/__init__.py`, `tests/voice/conftest.py`, `tests/voice/helpers.py`, `tests/voice/test_time_left.py`, `tests/voice/test_sentence_sources.py`

**Interfaces:**
- Produces in `const.py`: `VOICE_LANGUAGES: Final = ("en", "ru")`; `SENTENCES_DIR: Final = Path(__file__).parent / "sentences"`; `LIST_TARGET: Final = "timerify_target"`.
- Produces in `voice/base.py`:
  - `loaded_timers(hass) -> list[TimerifyConfigEntry]` — the loaded entries of the domain (T2 leaves out the voice entry).
  - `async_match_timer(hass, intent_obj: intent.Intent, name: str) -> TimerifyConfigEntry` — `intent.async_match_targets(hass, MatchTargetsConstraints(name=name, assistant=intent_obj.assistant, single_target=True), states=[states of loaded_timers' targets])`; raises `intent.MatchFailedError(result=..., constraints=...)` when it does not match (unexposed, unknown, duplicate). A target with no state is not a candidate.
  - `voice_language(language: str) -> str` — the first of `language_util.matches(language, list(VOICE_LANGUAGES))`, `"en"` when none (`"*"`, `"de"`).
  - `async_error_text(hass, language: str, err: HomeAssistantError) -> str` — `component.timerify.exceptions.<translation_key>.message` of `voice_language(language)` (`async_get_translations(..., "exceptions", [DOMAIN])`) formatted with `err.translation_placeholders`.
  - `clock_slots(moment: datetime, now: datetime) -> dict[str, Any]` — `{"at": "HH:MM" (local, 24 h), "in_days": <local date difference>}`.
  - `timer_slots(hass, entry, now) -> dict[str, Any]` — `target` (`target_name`), `state` (`"counting"` when the timer runs, `"open"` when the target is on without one, else `"off"`), `left_total` (`remaining_minutes`), `left_hours`, `left_minutes` (`divmod(left_total, 60)`), and, while counting, `ends_at`/`ends_in_days` (`clock_slots` of the end).
  - `class TimerifyIntentHandler(intent.IntentHandler)` — `tool_name: ClassVar[str]`, `read_only: ClassVar[bool]`; `slot_schema` always has `probatio.Required("name"): cv.string`; `async_handle` (not overridden by subclasses) creates the response, resolves the timer, awaits `async_handle_timer(intent_obj, entry, response) -> None`, and turns a `HomeAssistantError` whose `translation_domain == DOMAIN` into `response.async_set_error(IntentResponseErrorCode.FAILED_TO_HANDLE, await async_error_text(...))`; any other exception propagates. Actions add `IntentResponseTarget(type=ENTITY, name=..., id=entity_id)` to success results; queries set `response_type = QUERY_ANSWER` and matched states. A handler never sets speech on success, only `async_set_speech_slots`.
- Produces in `voice/__init__.py`: `HANDLER_TYPES: Final[tuple[type[TimerifyIntentHandler], ...]]` and `async_register_intents(hass) -> None` (called from `async_setup`, after the services).
- Produces in `voice/timer.py`: `TimeLeftHandler` (`TimerifyTimeLeft`, `timerify__time_left`, read only).
- Sentence source shape (both languages): `language`, `intents.TimerifyTimeLeft.data[].sentences` with `{timerify_target:name}`, `lists.timerify_target.values: []` (empty: the file loads and matches nothing until names are added), `responses.intents.TimerifyTimeLeft.default` branching on `slots.state`. Core rules may be used (`<the>`, `<turn>`; ru `<turn_on>`, `<turn_off>`).
- Produces in `tests/voice/conftest.py`: `hass_config_dir` → `hass_tmp_config_dir`; fixture `assist` (sets up `homeassistant`, `conversation`, `intent`, writes an empty `configuration.yaml` into the config dir, sets `JERUSALEM`); `fake_fan` (`switch.fan`, "Fan", no timer).
- Produces in `tests/voice/helpers.py`: `converse(hass, text, language="en") -> intent.IntentResponse`; `speech(response) -> str`; `expose(hass, entity_id, exposed: bool)`; `copy_sentences(hass, names: Iterable[str])` — the README's manual route: copies `sentences/<lang>/*.yaml` into `custom_sentences/<lang>/` and writes `timerify_names.yaml` with `lists.timerify_target.values` `{in: name, out: name}`; `samples(language, intent_type, *, names, numbers: Mapping[str, int]) -> list[str]` — every sentence of the intent from `merge_dict(get_intents(language), sources)` through `hassil.sample.sample_intents`, with `timerify_target` = `names` and each number list replaced by a one-value digits-only `RangeSlotList`; `EN_ONE = (1,)`, `EN_OTHER = (0, 2, 5, 11, 21)`, `RU_ONE = (1, 21, 31, 101)`, `RU_FEW = (2, 3, 4, 22, 24, 102)`, `RU_MANY = (5, 11, 12, 14, 20, 25, 111, 114)`; `without_digits(text) -> str`.

- [ ] **Step 1: Write the failing tests** (`setup_target()` + `fake_target`, `assist`, `copy_sentences(hass, ["Boiler"])`; the number is set with `set_number`)

```python
async def test_time_left_while_counting():          # 45 → QUERY_ANSWER, intent TimerifyTimeLeft,
    # speech == "45 minutes left on Boiler, it turns off at 09:45."
async def test_time_left_says_hours_and_minutes():  # 90 → "1 hour and 30 minutes left on Boiler, it turns off at 10:30."
async def test_time_left_rounds_up_like_the_run_for_number():  # 45, advance 30 s → "45 minutes left on Boiler, …"
async def test_time_left_past_midnight_says_tomorrow():  # 1440 → "24 hours left on Boiler, it turns off at 09:00 tomorrow."
async def test_time_left_on_an_idle_target():       # → "Boiler is off and has no timer."
async def test_time_left_on_a_loose_target_running_without_a_timer():  # loose, target on → "Boiler is on without a timer."
@pytest.mark.parametrize("text", ["how much time is left on the boiler", "how long is left on boiler",
                                  "how long will the boiler run", "when does the boiler turn off",
                                  "How much time is left on the Boiler?"])
async def test_english_phrasings_ask_time_left(text):  # intent TimerifyTimeLeft, slots name == "Boiler"
async def test_unexposed_target_is_refused():         # expose False → ERROR, NO_VALID_TARGETS; no call to the target
async def test_entity_without_a_timer_is_not_captured():  # fake_fan: "how much time is left on fan" → intent is None or not ours
async def test_two_targets_with_one_name_are_not_guessed():  # two timers on entities named "Lamp" → ERROR, nothing switched
async def test_russian_sentences_reach_time_left():   # every samples("ru", "TimerifyTimeLeft", names=["Boiler"]) → our intent, name "Boiler"
@pytest.mark.parametrize("unit", ["minutes", "hours"])
async def test_russian_counts_follow_the_plural_rules(unit):  # n (× 60 for hours) from RU_ONE/RU_FEW/RU_MANY, one ru sample:
    # without_digits(speech) is equal within a class and differs between classes
async def test_english_counts_follow_the_plural_rules()  # EN_ONE vs EN_OTHER the same way; "1 minute", "2 minutes", "1 hour"
# tests/voice/test_sentence_sources.py
def test_voice_languages_are_the_sentence_directories()  # sorted(VOICE_LANGUAGES) == sorted(dirs of SENTENCES_DIR)
@pytest.mark.parametrize("language", VOICE_LANGUAGES)
def test_sources_load_with_core_and_without_names(language)  # Intents.from_dict(merge_dict(get_intents(lang), sources)) loads;
    # samples(..., names=[]) of every Timerify intent is empty
def test_every_language_has_the_same_intents_and_responses()  # same intent names; every data block's `response` (or
    # "default") has a template under responses.intents in its language
async def test_handlers_are_registered_once_per_intent()  # each HANDLER_TYPES intent_type in intent.async_get(hass), no duplicates
# tests/test_manifest.py
def test_voice_test_dependencies_match_conversation()  # pyproject dev pins == conversation manifest requirements
```

- [ ] **Step 2: Run `uv sync && uv run pytest tests/voice tests/test_manifest.py -v`** — Expected: FAIL (no `voice` package, no sentences).
- [ ] **Step 3: Implement** the deps and `after_dependencies`, `voice/base.py`, `TimeLeftHandler` (slots from `timer_slots`), registration in `async_setup`, both sentence files (en templates exactly as the tests say; ru: the target's name first, in the nominative, then a colon — no declension of names; plural forms by the `n % 10` / `n % 100` rule, as core's `ru.json` HassStartTimer response does).
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Answer how long is left on a timer by voice"`

---

### Task 2: The "Voice sentences" entry writes and keeps the sentence files

**Files:**
- Create: `custom_components/timerify/voice/sentences.py`, `voice/files.py`
- Modify: `custom_components/timerify/__init__.py`, `config_flow.py`, `const.py`, `voice/base.py` (`loaded_timers`), `translations/en.json`, `translations/ru.json`, `scripts/smoke/run.py` (`add_timer`), `tests/test_config_flow.py`
- Test: `tests/voice/test_voice_entry.py`, `tests/voice/helpers.py`

**Interfaces:**
- Consumes: `VOICE_LANGUAGES`, `SENTENCES_DIR`, `LIST_TARGET`, `loaded_timers` (Task 1).
- Produces in `const.py`: the T2 values of Global Constraints; `is_voice_options(options: Mapping[str, Any]) -> bool` (`options.get(CONF_KIND) == KIND_VOICE_SENTENCES`).
- Produces in `voice/sentences.py` (pure but for `voice_names`; the blocking ones run in the executor):
  - `escape_template(text: str) -> str` — a backslash before each of `\ ( ) [ ] { } < > | @` (backslash first).
  - `@dataclass(frozen=True) class VoiceName: spoken: str; name: str; domain: str` — `spoken` is what the list matches, `name` what the handler receives.
  - `voice_names(hass) -> list[VoiceName]` — for each loaded timer's target: every name of `intent.async_get_entity_aliases(hass, registry_entry, state=state)` (or `er.async_get_entity_aliases(hass, entry, allow_empty=False)` while the target has no state), `spoken = remove_punctuation(name).strip()`, skipped when empty — the default agent's own rule (`default_agent.py:1077-1087`).
  - `load_sources(language) -> dict[str, Any]` — `merge_dict` of every `SENTENCES_DIR/<language>/*.yaml`, sorted by file name (blocking).
  - `build(sources, names: Sequence[VoiceName]) -> dict[str, Any]` — the sources with `lists.timerify_target.values` = `{in: escape_template(spoken), out: name, context: {domain: domain}}` per name.
  - `validate(language, built) -> None` — `Intents.from_dict(merge_dict(<copy of get_intents(language)>, built))`; raises what hassil raises (blocking).
  - `render(built) -> str` — `MANAGED_HEADER` + `\n` + `homeassistant.util.yaml.dump(built)`.
- Produces in `voice/files.py`: `class SentenceFiles` (runtime data of the voice entry): `async_start()`, `async_sync()` (build, validate and render every language; write a file only when its text differs, with `write_utf8_file_atomic` after `mkdir(parents=True, exist_ok=True)` in the executor; then `conversation.reload` with no data, once, only if something was written and the service exists), `async_remove_files()` (unlink the files that exist, then the same reload); `type VoiceConfigEntry = ConfigEntry[SentenceFiles]`; `is_voice_entry(entry: TimerifyConfigEntry | VoiceConfigEntry) -> TypeIs[VoiceConfigEntry]`; `async_setup_voice_entry`, `async_unload_voice_entry`, `async_remove_voice_entry`.
  - Lifecycle: setup with the option on → `async_start`: if Home Assistant is running, `await async_sync()` before setup returns (so a flow that creates the entry returns after the files exist), else at `async_at_started`; then a `Debouncer(cooldown=VOICE_SYNC_COOLDOWN, immediate=False, function=async_sync)` is scheduled by `SIGNAL_TIMERS_CHANGED`, `EVENT_ENTITY_REGISTRY_UPDATED` of a target (changes touching `name`, `aliases`, `original_name`, `entity_id`, `device_id`) and `EVENT_DEVICE_REGISTRY_UPDATED` of a target's device (`name`, `name_by_user`). Setup with the option off → `async_remove_files()`. Unload cancels the debouncer and deletes the files only when `entry.disabled_by` is set (a reload or a shutdown keeps them). Remove deletes them.
  - A failed `validate` logs one ERROR naming the language and leaves that language's file as it was.
- Produces in `__init__.py`: `async_setup_entry`/`async_unload_entry`/`async_remove_entry` take `TimerifyConfigEntry | VoiceConfigEntry` and branch with `is_voice_entry`; a timer's setup (after `async_start`) and unload send `SIGNAL_TIMERS_CHANGED`.
- Produces in `config_flow.py`: `CONFIG_FLOW["user"] = SchemaFlowMenuStep(_menu_options)` — `["target", "voice_sentences"]`, without `voice_sentences` while a voice entry exists; `"target"` is the former `user` form; `"voice_sentences"` a form with `probatio.Required(CONF_WRITE_SENTENCES, default=True): BooleanSelector()`, whose validator raises `AbortFlow("voice_sentences_exist")` if a voice entry exists, sets the unique id `VOICE_UNIQUE_ID` (`raise_on_progress=False`), loads the `config` translations of `hass.config.language`, and adds `CONF_KIND`; `async_config_entry_title` returns, for a voice entry, the cached `component.timerify.config.step.voice_sentences.title` of `hass.config.language`. `OPTIONS_FLOW["init"]` keeps the mode form for timers; its schema function returns `None` for a voice entry and its `next_step` sends a voice entry to `"voice_sentences"` (the checkbox, no default). `async_get_supported_subentry_types` gives a voice entry no subentry types.
- Translations: `config.step.user` (title, description, `menu_options.target`, `menu_options.voice_sentences`), `config.step.target` (the former `user` texts), `config.step.voice_sentences` and `options.step.voice_sentences` (title "Voice sentences", description saying the files are `custom_sentences/<lang>/timerify.yaml`, rewritten by Timerify, and that unticking or removing the entry deletes them; `data.write_sentence_files` "Write sentence files for the built-in agent"), `config.abort.voice_sentences_exist`.
- Produces in `tests/voice/helpers.py`: `add_voice_entry(hass, *, write=True) -> ConfigEntry` (through the flow: menu → `voice_sentences`), `managed_file(hass, lang) -> Path`, `listed(hass, lang, list_name=LIST_TARGET) -> list[dict[str, Any]]` (a list's values read back from the managed file), `conversation_reloads(hass) -> list[ServiceCall]` (captured `call_service` events of `conversation.reload`).
- `tests/test_config_flow.py`: every flow that adds a timer first picks `target` from the menu (`{"next_step_id": "target"}`) and expects step `target` where it expected `user`; nothing else changes. `scripts/smoke/run.py` `add_timer` does the same.

- [ ] **Step 1: Write the failing tests** (`tests/voice/test_voice_entry.py`; `assist`, `fake_target`, `setup_target`)

```python
async def test_menu_offers_a_timer_and_voice_sentences()   # step user is a menu: ["target", "voice_sentences"]
async def test_voice_entry_writes_a_file_per_language()      # add_voice_entry → both files exist, line 1 == MANAGED_HEADER,
    # listed == [{"in": "Boiler", "out": "Boiler", "context": {"domain": "switch"}}]; "how long is left on the boiler" works
    # with no copy_sentences; one conversation reload
async def test_menu_hides_voice_sentences_once_it_exists()
async def test_second_voice_entry_is_refused()               # a flow started before the first finished → abort voice_sentences_exist
async def test_voice_entry_title_is_in_the_language_of_the_house()  # language "ru" → title == ru.json's step title, != en's
async def test_voice_entry_has_no_intervals_and_no_timer()   # no subentry types; loaded_timers excludes it; no number entity
async def test_option_off_at_creation_writes_nothing()
async def test_unticking_removes_the_files_and_the_sentences_stop_matching()  # options flow → files gone, one reload,
    # "how long is left on the boiler" no longer reaches TimerifyTimeLeft
async def test_ticking_again_writes_them()
async def test_removing_the_entry_removes_the_files()
async def test_disabling_the_entry_removes_the_files_and_enabling_writes_them()
async def test_reloading_the_entry_keeps_the_files_without_rewriting()  # same mtime and text, no reload
async def test_unchanged_file_is_not_rewritten()             # a timer reload that changes no name → no write, no reload
async def test_start_writes_every_target_once()              # CoreState.not_running: voice entry, then two timers set up,
    # EVENT_HOMEASSISTANT_STARTED → one write per language listing both, one reload
async def test_new_target_is_listed()                        # setup a second timer, advance(seconds=VOICE_SYNC_COOLDOWN) → listed
async def test_removed_target_leaves_the_list()
async def test_renamed_target_follows()                      # registry entity_id rename (timer follows and reloads) → still listed
async def test_new_name_and_alias_are_matched()              # registry name "Water heater", alias "Geyser" → both spoken;
    # "how long is left on the geyser" answers with "Water heater"
async def test_device_rename_follows_the_full_name()         # target with has_entity_name on a device renamed
@pytest.mark.parametrize("name", ["Boiler (main)", "Lamp [2]", "A|B lamp", "<Hall>", "Tea {pot}", "me@home", "Back\\slash"])
async def test_names_with_template_characters_are_escaped(name)  # file validates; "how long is left on <name>" → our intent
async def test_name_is_matched_as_the_default_agent_cleans_it()  # "Boiler!" listed as spoken "Boiler", out "Boiler!"
async def test_name_left_empty_by_punctuation_is_skipped()   # "!!!" → not listed, file valid
async def test_shared_name_resolves_to_the_timerify_target()  # fake_fan renamed "Boiler": "how long is left on boiler" →
    # Boiler's answer; "turn off boiler" → core HassTurnOff (V1)
async def test_unescaped_name_is_refused_before_writing()    # patch voice.sentences.escape_template to identity, name
    # "Boiler (main" → existing file unchanged, one ERROR naming "en"
async def test_files_are_written_without_conversation_and_nothing_is_reloaded()  # conversation not set up
# tests/test_config_flow.py: the flows that add a timer go through the menu; their assertions stay
```

- [ ] **Step 2: Run `uv run pytest tests/voice/test_voice_entry.py tests/test_config_flow.py -v`** — Expected: new tests FAIL, `test_config_flow.py` FAILS on the menu until Step 3.
- [ ] **Step 3: Implement** `sentences.py`, `files.py`, the branches in `__init__.py`, the flow steps and the strings; update `add_timer` in the smoke script.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Add a Voice sentences entry that writes the sentence files for the built-in agent"`

---

### Task 3: LLM tools, and Timerify's own entities kept from Assist

**Files:**
- Create: `custom_components/timerify/llm.py`
- Modify: `custom_components/timerify/switch.py`, `tests/test_interval_switch.py` (only if it asserts the category)
- Test: `tests/voice/test_llm.py`, `tests/voice/test_exposure.py`, `tests/voice/helpers.py`

**Interfaces:**
- Consumes: `HANDLER_TYPES`, `loaded_timers`, `TimerifyIntentHandler.tool_name/read_only` (Task 1).
- Produces in `llm.py`: `@callback def async_get_tools(hass, llm_context: llm.LLMContext, api_id: str) -> llm.LLMTools | None` — `None` unless a loaded timer's target is exposed to `llm_context.assistant` (any target when `assistant` is `None`, as core's matching does); otherwise one `llm.IntentTool(cls.tool_name, cls(), integration=DOMAIN, annotations=llm.ToolAnnotations(read_only=cls.read_only, open_world=False))` per `HANDLER_TYPES` entry and `prompt = TOOLS_PROMPT.format(names=...)` listing the exposed targets' names. `TOOLS_PROMPT` (English): "These devices have a Timerify timer: {names}. To run one for a while, add time, stop it, ask how long is left, plan a command for later, list or cancel planned commands, or switch its schedule on or off, use the timerify__ tools, naming the device as listed here."
- Every handler's `slot_schema` uses only `cv.string`, `cv.boolean`, `probatio.Coerce(int)`, `probatio.Coerce(float)`, `probatio.In(...)`, `probatio.Range(...)`, so each tool's parameters render with `probatio.to_openapi(tool.parameters, custom_serializer=llm.selector_serializer, strict=True)`.
- Produces in `switch.py`: `IntervalSwitch.entity_description` gains `entity_category=EntityCategory.CONFIG` (not exposed by default, `exposed_entities.py:304-309`).
- Produces in `tests/voice/helpers.py`: `async assist_api(hass, language="en", assistant="conversation") -> llm.APIInstance`; `async call_tool(api, name, args) -> dict[str, Any]` (the `ToolResult.data`).

- [ ] **Step 1: Write the failing tests**

```python
async def test_tools_are_offered_while_a_target_is_exposed()  # {t.name for timerify tools} == {c.tool_name for c in HANDLER_TYPES};
    # every name starts "timerify__", integration "timerify"; no WARNING from the llm platform in caplog
async def test_no_tools_without_an_exposed_target()          # target unexposed → no timerify tool, no prompt fragment
async def test_prompt_names_the_exposed_targets_only()       # two timers, one exposed → "Boiler" in api_prompt, the other absent
async def test_tool_parameters_render_as_typed_openapi()     # strict to_openapi for every timerify tool; time_left has
    # {"name": {"type": "string"}} required
async def test_time_left_tool_returns_structured_data()      # 45 → data["response_type"] == "query_answer",
    # data["speech_slots"] == {"target": "Boiler", "state": "counting", "left_total": 45, "left_hours": 0,
    #                          "left_minutes": 45, "ends_at": "09:45", "ends_in_days": 0}
async def test_tool_refuses_an_unexposed_target()            # two timers, Boiler unexposed → MatchFailedError, reason ASSISTANT
async def test_tool_with_language_star_and_unknown_language_works()  # "*" and "de" → same structured data
# tests/voice/test_exposure.py
async def test_timerify_entities_are_not_exposed_by_default()  # number, both sensors, interval switch: should_expose False;
    # switch.boiler True
async def test_interval_switch_is_a_config_entity()          # registry entity_category == EntityCategory.CONFIG
```

- [ ] **Step 2: Run `uv run pytest tests/voice/test_llm.py tests/voice/test_exposure.py -v`** — Expected: FAIL.
- [ ] **Step 3: Implement** `llm.py` and the entity category.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Offer the timer to LLM agents as tools and keep Timerify's own entities from Assist"`

---

### Task 4: Run, add time and stop by voice

**Files:**
- Modify: `custom_components/timerify/voice/timer.py`, `voice/__init__.py`, `voice/base.py` (`SETTING_SLOTS`), `controller.py`, `sentences/en/timerify.yaml`, `sentences/ru/timerify.yaml`, `translations/en.json`, `translations/ru.json`
- Test: `tests/voice/test_timer_by_voice.py`

**Interfaces:**
- Consumes: Task 1's base, Task 2's `add_voice_entry` (scenarios use the managed route), Task 3's `assist_api`/`call_tool`.
- Produces in `voice/base.py`: `SETTING_SLOTS` — one `probatio.Optional` per `SETTINGS_SCHEMA` key, typed `Coerce(float)` (`temperature`, `brightness_pct`), `Coerce(int)` (`percentage`, `humidity`) or `cv.string`; a test asserts the keys equal `SETTINGS_SCHEMA`'s. `duration_of(slots, prefix="") -> int | None` — `60 * hours + minutes` of the slots `<prefix>hours`, `<prefix>minutes` (either may be missing), `None` when both are.
- Produces in `voice/timer.py`:
  - `RunHandler` (`TimerifyRun`, `timerify__run`): slots `name`, `hours`, `minutes` (`Coerce(int)`, `Range(min=0)`), `SETTING_SLOTS` → `controller.async_run(duration_of(slots), settings)`; speech slots `timer_slots` after the call.
  - `AddTimeHandler` (`TimerifyAddTime`, `timerify__add_time`): `name`, `hours`, `minutes` → `controller.async_add_minutes(...)`.
  - `StopHandler` (`TimerifyStop`, `timerify__stop`): `name` → `controller.async_set_minutes(0)`.
- Produces in `controller.py`: `async_run` (with minutes), `async_add_command` (with minutes) and `async_set_minutes` raise `ServiceValidationError(translation_key="duration_out_of_range", translation_placeholders={"max_hours": str(MAX_MINUTES // 60)})` for minutes outside `1..MAX_MINUTES` (`0..MAX_MINUTES` for `async_set_minutes`), before anything runs. Services and the number are unchanged (their schemas already refuse).
- Sentences (en; ru the same meanings): run — "<turn> on [<the>] {name} for <duration> [<settings>]", "<turn> [<the>] {name} on for <duration> [<settings>]", "run [<the>] {name} for <duration>", "set [<the>] {name} timer to <duration>"; add — "add <duration> to [<the>] {name}", "<duration> more on [<the>] {name}", "extend [<the>] {name} by <duration>"; stop — "(stop|cancel) [<the>] {name} timer", "(stop|cancel) the timer (on|of) [<the>] {name}". `<duration>`: `{timerify_hours:hours} hour[s] [and] {timerify_minutes:minutes} minute[s]`, either part alone, and the list `timerify_duration_words` into `minutes` (en "an hour" 60, "half an hour" 30, "an hour and a half" 90; ru the same three). `<settings>`: in any order (hassil permutation), `[,]` separated: `{timerify_hvac_mode:hvac_mode}` (en cooling/cool → cool, heating/heat → heat, drying/dry → dry, fan only → fan_only, auto → auto, heat and cool → heat_cool; ru the equivalents), `[at] {timerify_temperature:temperature} degree[s]` (range 1..100), `at {timerify_percent:brightness_pct} percent` (range 1..100). Ranges: `timerify_hours` 1..24, `timerify_minutes` 1..1440.
- Response templates: run and add — en "Boiler runs for 45 minutes, until 09:45." (hours as in Task 1, "tomorrow" when `ends_in_days`); stop — "Boiler is off."
- Translations: `exceptions.duration_out_of_range` (en "A timer runs for at most {max_hours} hours."; ru with the plural-free abbreviation of "hours").

- [ ] **Step 1: Write the failing tests** (`assist`, `fake_target`/`fake_climate`, `setup_target`, `add_voice_entry`)

```python
async def test_turn_on_for_minutes_runs_the_timer()      # "turn on the boiler for 45 minutes" → turn_on once, NUMBER 45,
    # speech "Boiler runs for 45 minutes, until 09:45."
@pytest.mark.parametrize(("text", "minutes"), [("turn the boiler on for an hour", 60), ("run the boiler for 2 hours", 120),
    ("turn on the boiler for 1 hour and 30 minutes", 90), ("turn on the boiler for half an hour", 30),
    ("set the boiler timer to 20 minutes", 20)])
async def test_run_phrasings(text, minutes)
async def test_run_with_settings_turns_the_ac_on_with_them()  # "turn on the AC for an hour, cooling, 24 degrees" →
    # call_data has hvac_mode "cool" and temperature 24.0; AC_NUMBER 60
async def test_settings_in_another_order()                # "turn on the AC for 30 minutes at 22 degrees heating"
async def test_setting_the_target_cannot_take_is_refused()  # "turn on the boiler for 10 minutes at 40 percent" → ERROR
    # FAILED_TO_HANDLE, speech == en setting_not_supported formatted; no call to the target
async def test_run_longer_than_a_day_is_refused()         # "for 24 hours and 30 minutes" → ERROR, duration_out_of_range text
async def test_add_time_extends_a_running_timer()         # R7: 5 left, "30 more minutes on the boiler" → 35
async def test_add_time_on_an_idle_timer_starts_it()      # → turn_on, 30
async def test_stop_turns_the_target_off()                # R2 → turn_off, NUMBER 0, speech "Boiler is off."
async def test_voice_change_ends_schedule_alignment()     # S3: interval runs the timer; "add 10 minutes to the boiler";
    # edit_interval to end earlier → end unchanged
async def test_strict_manual_rules_still_apply_after_voice()  # R3: voice run, then the target off by hand → timer 0
@pytest.mark.parametrize("intent_type", ["TimerifyRun", "TimerifyAddTime", "TimerifyStop"])
async def test_russian_sentences_reach_their_intent(intent_type)  # samples(numbers={"timerify_minutes": 15,
    # "timerify_hours": 2, ...}) → our intent with the sampled slot values
async def test_russian_run_answer_follows_the_plural_rules()  # classes, as in Task 1
async def test_regional_language_answers_in_its_language()  # "ru-RU": refused setting → text == ru.json message formatted;
    # "en-GB" → en text
async def test_llm_run_add_and_stop()                     # timerify__run {"name": "Boiler", "minutes": 45} →
    # speech_slots.left_total 45; add_time {"minutes": 10} → 55; stop → state "off"
async def test_llm_run_with_settings()                    # AC, {"hvac_mode": "cool", "temperature": 24, "hours": 1}
async def test_llm_error_text_follows_the_request_language()  # unsupported setting: "ru" → ru text, "*" and "de" → en text
async def test_llm_duration_out_of_range_is_refused()     # minutes 1441 → error, nothing runs
def test_setting_slots_are_the_service_settings()
```

- [ ] **Step 2: Run `uv run pytest tests/voice/test_timer_by_voice.py -v`** — Expected: FAIL.
- [ ] **Step 3: Implement** the handlers, the bounds, the sentences, responses and strings.
- [ ] **Step 4: Run all checks** — Expected: all pass (the services' range tests still pass: they refuse in the schema first).
- [ ] **Step 5: Commit** — `git commit -m "Run, extend and stop a timer by voice and through LLM tools"`

---

### Task 5: Core delayed commands are taken over for Timerify targets

**Files:**
- Create: `scripts/generate_delayed_commands.py`, `custom_components/timerify/sentences/en/delayed_commands.yaml`, `sentences/ru/delayed_commands.yaml` (generated), `custom_components/timerify/voice/commands.py`
- Modify: `voice/__init__.py`, `core.py`, `controller.py`, `sentences/en/timerify.yaml`, `sentences/ru/timerify.yaml` (responses, `timerify_run_extras`)
- Test: `tests/voice/test_delayed_commands.py`

**Interfaces:**
- Consumes: `RunHandler`'s `<duration>` and `<settings>` rules and `SETTING_SLOTS`, `duration_of` (Task 4).
- Produces in `core.py`: `is_running(snapshot: Snapshot) -> bool` — `snapshot.end is not None or snapshot.last_actual == "on"` (an unavailable target with a timer runs: R10).
- Produces in `controller.py`: `async_turn_off_in(delay: timedelta, minutes: int | None = None, settings: Mapping[str, Any] | None = None) -> bool` — under the lock: when `is_running`, the timer is set to `delay` (seconds kept) and True; otherwise nothing changes and False. Before anything runs it raises `off_takes_no_duration_or_settings` when `minutes` or `settings` are given (the check `async_add_command` makes, moved into one private helper both call) and `duration_out_of_range` for a delay above `MAX_MINUTES` minutes.
- Produces in `scripts/generate_delayed_commands.py`: `render(language: str) -> str` and `main()` writing `SENTENCES_DIR/<lang>/delayed_commands.yaml` for each `VOICE_LANGUAGES`. Algorithm: header `# Generated by scripts/generate_delayed_commands.py from home-assistant-intents <version>. Do not edit.`; for each `HassStartTimer` data block with `response: command` (the delayed-command shapes) and each data block with `metadata.slot_combination: name_only` of `HassTurnOn` (action `on`) and `HassTurnOff` (action `off`), one `TimerifyDelayedCommand` data block: its sentences are the shape's sentences with `{timer_command:conversation_command}` replaced by `(<the on/off block's sentences, joined by |>)`, `{name}` by `{timerify_target:name}`, `{timer_hours:hours}`/`{timer_minutes:minutes}`/`{timer_seconds:seconds}` by `…:delay_hours`/`delay_minutes`/`delay_seconds`; for `on`, ` [<timerify_run_extras>]` follows the command group and ends every sentence whose delay comes last; `slots: {action: on|off}`; `requires_context` copied from the on/off block except for the blocks whose `response` is `default` and whose context names the generic domain list (those apply to every Timerify target); response `delayed`.
- Produces in `voice/commands.py`: `DelayedCommandHandler` (`TimerifyDelayedCommand`, `timerify__delayed_command`): slots `name`, `action` (`In(["on", "off"])`), `delay_hours`, `delay_minutes`, `delay_seconds` (`Coerce(int)`, `Range(min=0)`), `hours`, `minutes`, `SETTING_SLOTS`. `on` → `controller.async_add_command("on", timedelta(hours=, minutes=, seconds=), duration_of(slots), settings)`; speech slots `outcome: "command_added"`, `clock_slots(at)`, `target`. `off` → `controller.async_turn_off_in(delay, duration_of(slots), settings)` (the controller refuses a duration or settings with an off); `outcome: "timer_set"` + `timer_slots`, or `outcome: "not_running"` + `target`.
- `timerify.yaml` gains `expansion_rules.timerify_run_extras` = `(for <duration>; <settings>)` with both parts optional, and `responses.intents.TimerifyDelayedCommand.delayed` — en "Boiler turns on at 09:15." / "Boiler turns off at 09:10." / "Boiler is already off; nothing changed." ("tomorrow" when `in_days`/`ends_in_days`).

- [ ] **Step 1: Write the failing tests** (`assist`, managed route; the core shapes come from `get_intents(language)`)

```python
async def test_turn_on_in_minutes_adds_a_pending_command()  # "turn on the boiler in 15 minutes" → NEXT == START+15 min,
    # no call; advance 15 min → turn_on, NUMBER 45 (strict default, R9); speech "Boiler turns on at 09:15."
async def test_turn_on_in_minutes_for_an_hour_with_settings()  # spec §6.4: "turn on the AC in 15 minutes for an hour,
    # cooling, 24 degrees" → advance 15 min → turn_on with cool, 24.0; AC_NUMBER 60
async def test_pending_command_by_voice_survives_manual_use()  # P2: target on/off by hand before T → still runs at T
async def test_turn_off_in_minutes_on_a_running_target_sets_the_timer()  # 45 left, "turn off the boiler in 10 minutes" →
    # NUMBER 10, no command; advance 10 → turn_off
async def test_turn_off_in_minutes_replaces_a_shorter_timer()  # 5 left → 10
async def test_turn_off_in_minutes_on_an_off_target_changes_nothing()  # speech "Boiler is already off; nothing changed.",
    # no command, no call, response ACTION_DONE
async def test_turn_off_in_on_a_loose_open_run_sets_the_timer()
async def test_turn_off_in_on_an_unavailable_running_target_sets_the_timer()  # R10
async def test_delay_with_seconds_is_exact()              # "turn off the boiler in 1 minute and 30 seconds" → ENDS == START+90 s;
    # "turn on the boiler in 30 seconds" → NEXT == START+30 s
async def test_delayed_off_beyond_a_day_is_refused()      # running, "turn off the boiler in 30 hours" → duration_out_of_range
@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_every_core_delayed_command_on_a_target_is_taken_over(language)  # V2: every sample of every HassStartTimer
    # "command" shape, its command being every sample of core's name_only HassTurnOn/HassTurnOff sentences for a switch
    # named "Boiler", hours 2, minutes 15, seconds 30 → intent TimerifyDelayedCommand with the right action and delay
@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_core_delayed_commands_on_other_entities_stay_with_core(language)  # the same shapes on fake_fan "Fan" →
    # HassStartTimer; advance → the fan is switched by core
def test_generated_delayed_commands_are_current()         # render(lang) == the committed file, for each language
async def test_llm_delayed_command()                      # timerify__delayed_command: on + delay_minutes 15 + minutes 60 +
    # cool/24 → outcome command_added, at "09:15"; off on a running target → timer_set; off on an idle one → not_running
async def test_llm_delayed_command_beyond_a_week_is_refused()  # delay_minutes 20000 → command_too_far text
async def test_llm_delayed_off_with_a_duration_is_refused()  # off + minutes 10 → off_takes_no_duration_or_settings text
```

- [ ] **Step 2: Run `uv run python scripts/generate_delayed_commands.py && uv run pytest tests/voice/test_delayed_commands.py -v`** — Expected: FAIL (no handler).
- [ ] **Step 3: Implement** `is_running`, `async_turn_off_in`, the generator (run it, commit its output), the handler, `timerify_run_extras` and the responses.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Take over core's delayed commands for Timerify targets"`

---

### Task 6: What is planned, and cancelling it, by voice

**Files:**
- Modify: `custom_components/timerify/voice/commands.py`, `voice/__init__.py`, `controller.py`, `sentences/en/timerify.yaml`, `sentences/ru/timerify.yaml`
- Test: `tests/voice/test_planned_commands.py`

**Interfaces:**
- Consumes: `clock_slots`, `duration_of` (Tasks 1, 4); Task 5's voice-made commands.
- Produces in `controller.py`: `async_cancel_commands(which: Literal["next", "all"]) -> tuple[Command, ...]` — under the lock, the first or every pending command is cancelled; returns them (empty when there were none).
- Produces in `voice/commands.py`:
  - `ListCommandsHandler` (`TimerifyListCommands`, `timerify__list_commands`, read only): `name` → speech slots `target`, `count`, `commands`: `[{"id", "action", "at", "in_days", "minutes" (or None), "settings" (dict)}]` in time order.
  - `CancelCommandsHandler` (`TimerifyCancelCommands`, `timerify__cancel_commands`): `name`, `which` (`In(["next", "all"])`, default `"all"`), `command_id` (`cv.string`, LLM only) → `async_cancel_command(command_id)` when given, else `async_cancel_commands(which)`; speech slots `target`, `which`, `cancelled` (count), `commands` (the cancelled ones, shaped as above).
- Sentences (en; ru the same meanings): list — "what is planned for [<the>] {name}", "what (commands|is) pending (for|on) [<the>] {name}"; cancel — "cancel (the|all) (planned|pending) commands (for|of) [<the>] {name}" (`which: all`), "cancel the next (planned|pending) command (for|of) [<the>] {name}" (`which: next`).
- Responses (en): "Boiler has 2 planned commands: turn on at 09:15 for 1 hour; turn off at 11:00 tomorrow." / "Boiler has no planned commands." / "Cancelled 2 planned commands for Boiler." / "Cancelled the next planned command for Boiler: turn on at 09:15." Settings are not spoken (they are in the data).

- [ ] **Step 1: Write the failing tests**

```python
async def test_what_is_planned_lists_the_commands()        # voice "turn on the boiler in 15 minutes" + add_command off at
    # START+2 h → exact en speech above (no "tomorrow"); QUERY_ANSWER
async def test_what_is_planned_without_commands()
async def test_planned_command_tomorrow_says_tomorrow()
async def test_cancel_all_planned_commands()               # 2 → NEXT unknown, speech "Cancelled 2 planned commands for Boiler."
async def test_cancel_the_next_planned_command()           # the later one stays
async def test_cancel_without_commands_says_so()
async def test_cancelled_command_does_not_run()            # advance past its time → no call
async def test_russian_planned_commands_follow_the_plural_rules()  # count classes (via add_command), as in Task 1
@pytest.mark.parametrize("intent_type", ["TimerifyListCommands", "TimerifyCancelCommands"])
async def test_russian_sentences_reach_their_intent(intent_type)
async def test_llm_lists_and_cancels_by_id()               # list → ids; cancel {"command_id": id} → gone;
    # unknown id → error text of unknown_command
```

- [ ] **Step 2: Run `uv run pytest tests/voice/test_planned_commands.py -v`** — Expected: FAIL.
- [ ] **Step 3: Implement** `async_cancel_commands`, both handlers, sentences and responses.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "List and cancel planned commands by voice and through LLM tools"`

---

### Task 7: The schedule on and off by voice

**Files:**
- Create: `custom_components/timerify/voice/intervals.py`
- Modify: `voice/__init__.py`, `voice/sentences.py` (interval list), `const.py`, `sentences/en/timerify.yaml`, `sentences/ru/timerify.yaml`, `translations/en.json`, `translations/ru.json`
- Test: `tests/voice/test_schedule_by_voice.py`, `tests/voice/test_voice_entry.py` (interval list)

**Interfaces:**
- Consumes: `async_set_interval_enabled` (phase 3); `build`, `VoiceName` (Task 2).
- Produces in `const.py`: `LIST_INTERVAL: Final = "timerify_interval"`. `timerify.yaml` declares `lists.timerify_interval.values: []`.
- Produces in `voice/sentences.py`: `interval_names(hass) -> list[VoiceName]` (each loaded timer's interval subentry titles, punctuation removed as for targets, `domain` of the target); `build(sources, names, intervals)` fills `timerify_interval` too. A title edit reloads the timer, so `SIGNAL_TIMERS_CHANGED` already regenerates.
- Produces in `voice/intervals.py`: `SetScheduleHandler` (`TimerifySetSchedule`, `timerify__set_schedule`): `name`, `enabled` (`cv.boolean`; sentences give it as a fixed slot), `interval` (`cv.string`, optional) — every interval of the target, or the one whose title equals `interval` by `remove_punctuation(...).strip().casefold()`; each through `controller.async_set_interval_enabled(id, enabled)`; speech slots `target`, `enabled`, `interval` (title or None), `count`. Refusals `ServiceValidationError` `no_schedule` (`{target}`) and `unknown_interval` (`{target}`, `{interval}`).
- Sentences (en; ru the same meanings): "<turn> (on|off) [<the>] {name} schedule", "<turn> (on|off) the schedule of [<the>] {name}", "(enable|disable|pause|resume) [<the>] {name} schedule", the same with "[<the>] {timerify_interval:interval} schedule of [<the>] {name}".
- Responses (en): "The schedule of Boiler is off." / "The Morning schedule of Boiler is on."

- [ ] **Step 1: Write the failing tests**

```python
async def test_turning_off_the_schedule_switches_every_interval_off()  # two intervals → both switches off; speech exact
async def test_turning_off_the_schedule_stops_a_scheduled_run()        # S2 through the switch: target off
async def test_turning_the_schedule_on_during_a_window_runs_the_target()  # phase-3 semantics through voice
async def test_one_interval_by_its_title()               # subentry title "Morning" (async_update_subentry) →
    # "turn off the morning schedule of the boiler" → only Morning off
async def test_interval_titles_follow_edits()            # retitle → advance(seconds=VOICE_SYNC_COOLDOWN) → new title matches,
    # listed(hass, "en", LIST_INTERVAL) has it, the old one is gone
async def test_interval_title_with_template_characters_is_escaped()  # "Morning (weekdays)"
async def test_target_without_intervals_is_refused()     # ERROR, no_schedule text
async def test_llm_set_schedule()                        # {"name": "Boiler", "enabled": false} → count 2;
    # {"interval": "Evening"} → unknown_interval text
@pytest.mark.parametrize("enabled", [True, False])
async def test_russian_sentences_reach_set_schedule(enabled)
```

- [ ] **Step 2: Run `uv run pytest tests/voice/test_schedule_by_voice.py tests/voice/test_voice_entry.py -v`** — Expected: FAIL.
- [ ] **Step 3: Implement** the list, the handler, sentences, responses and strings.
- [ ] **Step 4: Run all checks** — Expected: all pass.
- [ ] **Step 5: Commit** — `git commit -m "Switch a timer's schedule on and off by voice and through LLM tools"`

---

### Task 8: Phase verification and docs

**Files:**
- Modify: `README.md`, `RULINGS.md`, `docs/followups.md`, `CLAUDE.md` (status line), `custom_components/timerify/manifest.json` and `pyproject.toml` (`version` `0.4.0`), `uv.lock`, `scripts/smoke/run.py`

- [ ] **Step 1: README** — section "Voice and AI": what can be said (the en phrases of Tasks 1, 4–7, and that the same works in Russian), that bare "turn on/off X" stays with Home Assistant and Timerify sees it as a manual change (strict: default duration); the takeover of "turn on/off X in N" for Timerify targets only, "turn off X in N" on a running target setting the timer and on an off one changing nothing; the **Voice sentences** entry (add it from the Timerify menu, what the files are, rewritten on every timer change, removed by unticking, disabling or removing it); the manual alternative (copy every file of `custom_components/timerify/sentences/<lang>/` into `config/custom_sentences/<lang>/`, add `timerify_names.yaml` with the `timerify_target` list — `in` the name as said, punctuation removed, each of `\()[]{}<>|@` escaped with a backslash, `out` the name as Home Assistant shows it — and optionally `timerify_interval`; redo it after every Timerify update and every rename; a malformed file breaks Assist for the whole language); exposure (the target must be exposed; Timerify's own entities are not, and an interval switch exposed by 0.3.0 keeps the user's earlier choice); LLM agents and their `timerify__` tools; what is not by voice (commands at a clock time, other settings than mode, temperature and brightness by voice). Update "What is not here yet" (card only) and "Verification" (voice tests, the smoke voice scenario).
- [ ] **Step 2: RULINGS.md and followups** — a "Phase 4" part with V1–V8 and the plan rulings below, each Decision — why — cost if wrong; in `docs/followups.md` add "Commands at a clock time by voice and LLM" and "A target that is not in the entity registry: a changed friendly name is listed only after its timer reloads" under Later.
- [ ] **Step 3: Smoke script** — new `scenario_voice`, run before `scenario_restart`: add the Voice sentences entry through the flow (menu → `voice_sentences`, `{"write_sentence_files": true}`); `POST /api/conversation/process` `{"text": "how much time is left on smoke boiler", "language": "en"}` → `response_type` `error`, `data.code` `no_valid_targets` (an input_boolean is not exposed by default); expose it (`homeassistant/expose_entity` over the WebSocket, assistant `conversation`); "turn on smoke boiler for 2 minutes" → `action_done`, the switch turns on (WebSocket wait); "how much time is left on smoke boiler" → `query_answer`, speech starts "2 minutes left on Smoke boiler"; "turn off smoke boiler in 1 minute" → `action_done`, the switch turns off one minute later (`EXPIRY_SLACK`).
- [ ] **Step 4: Run hassfest** — `docker run --rm --platform linux/amd64 -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest` — Expected: no errors (translations with the menu and voice steps, `after_dependencies`).
- [ ] **Step 5: Run the smoke test** — `uv run python scripts/smoke/run.py` — Expected: every scenario passes.
- [ ] **Step 6: Run all checks on the final tree** — `uv run pytest && uv run ruff check && uv run ruff format --check && uv run mypy` — Expected: all pass; report the test count.
- [ ] **Step 7: Commit** — `git commit -m "Document phase 4 and bump the version to 0.4.0"`

---

## Plan rulings

Decision — why — cost if wrong. V1–V8 are followed as written except where an entry below says it refines one.

- **Success speech is rendered by the built-in agent from response templates in `sentences/<lang>/`; handlers set speech slots only; refusals are spoken by the handler (`async_set_error`) from `translations/<lang>.json` `exceptions`** (refines V6) — backend translations have no plural rules (`translation.py:454`) while each language's Jinja carries its own (core's ru `HassStartTimer` does the same), the LLM path never renders templates and gets the slots as data, and the quiet `async_set_error` avoids `IntentHandleError`'s ERROR traceback — a caller of `intent/handle` other than the two agents gets a successful response without speech.
- **A target that does not match (unexposed, unknown, two with one name) raises `intent.MatchFailedError` from core's own matching, restricted to the loaded timers' targets** (refines V5's "translated refusal") — the built-in agent answers with its translated `no_entity_exposed`/duplicate texts, an LLM gets the error result every core tool gives, and exposure is one rule — the LLM's error text is core's, not ours.
- **The takeover shapes are generated at development time by `scripts/generate_delayed_commands.py` from the pinned `home-assistant-intents` and committed; a test fails when the file is stale** (interprets V2's "generated from the installed data") — the manual route needs complete files in the repository, and the generator runs where the package is pinned to Home Assistant's — a user on a newer Home Assistant whose intents add a delayed shape reaches core's delayed command with a Timerify target until Timerify is regenerated and released.
- **The command inside a mirrored shape is core's own `name_only` on/off phrasing; the generic ones apply to every Timerify target, the domain-specific ones (light words, open/close, lock/unlock) keep their domain** (adds to V2) — mirrors what core recognises and nothing more, while every target, whatever its domain, can be delayed — a phrasing core understands only through an area or a device class ("turn off the kitchen lights in 5 minutes") stays with core.
- **Delays may carry seconds; durations are whole minutes** — a delay is a moment ("in 90 seconds" means that), a duration follows the services' and the number's whole-minute rule — a timer set by "turn off X in 90 seconds" shows 2 minutes on the number for its first 30 seconds.
- **The controller refuses a duration outside 1..`MAX_MINUTES` (`duration_out_of_range`), including a delayed off beyond it** (adds to the one-path rule) — the core silently caps at a day, so "for 30 hours" would run 24 without a word; the rule lives where every channel passes — none (services and the number already refuse in their schemas).
- **"Turn off X in N" decides "running" under the lock with `is_running`: a timer above zero, or the target on (a loose open run); unavailable with a timer counts as running** (adds `async_turn_off_in`) — R10 keeps the desired state apart from the actual one, and a check outside the lock could turn a just-stopped target back on — none.
- **"Add" by voice only adds; there is no subtract phrase** — spec §6.4 lists set/add/stop; "set to N" covers shortening — a user who says "10 minutes less" gets no match.
- **Bare "turn on/off X" is not taken over (V1), so no Timerify sentence has a bare on/off shape** — besides V1's reasons, core re-recognises a delayed command's text when it fires (`intent/timers.py:453-499`); a bare shape of ours would capture core's own delayed commands on Timerify targets — none.
- **Voice settings are the HVAC mode, the temperature and the brightness; LLM tools take every service setting** — the spec's examples, and words for fan modes or presets differ per device — "turn on the fan for an hour at speed 3" has no match; an LLM can do it.
- **Pending commands are cancelled by voice as "all" or "the next"; an LLM may cancel by id; voice and LLM make commands only by a delay** (`async_cancel_commands` decides under the lock) — a voice cannot say an id, and a clock time is not in core's delayed shapes — "turn on the boiler at 7:30" has no match (follow-up).
- **The schedule is switched as a whole, or one interval by its title from a generated `timerify_interval` list** — generated titles ("Sun–Thu 06:30–07:15") cannot be said, renamed ones can — a user with generated titles switches all intervals or none.
- **The config flow's `user` step becomes a menu (`target`, `voice_sentences`); the target form is step `target`; the options flow keeps `init` for timers and skips to `voice_sentences` for the voice entry** (V3's menu) — the group integration's precedent; only the first config step's id changes — every existing config-flow test and the smoke `add_timer` pick `target` first.
- **The entry kind is the option `kind: voice_sentences`; target entries carry none; `is_voice_entry` narrows with `TypeIs`** — the group precedent of a kind in the options, no migration of existing entries — none.
- **The voice entry's title is translated into the house's language when it is created, from the `config` translations its form loaded** — `async_config_entry_title` is synchronous — the title stays in the language of its creation (the user can rename it).
- **The voice option aborts a second entry with its own reason `voice_sentences_exist`, not `already_configured`** — that text says "This entity already has a timer" — none.
- **Files are deleted on untick, removal and disable; kept on reload and shutdown; written only when their text changes; then `conversation.reload` without a language** (refines V3, V7; research risk 4) — a reload or restart must not churn the files, a disabled entry no longer keeps them current, and a reload by language misses regional cache keys (`en-GB`) while one without re-reads the YAML `conversation:` config, which is harmless — every regional cache is rebuilt on a change.
- **The names list follows the default agent: every alias including the computed full name, punctuation removed with hassil's `remove_punctuation`, empty names skipped, `in` escaped, `out` the name itself, `context.domain` the target's domain** (V7) — what the user can say is what Home Assistant would match; the handler matches `out` with core's matcher; the context lets a mirrored domain-specific phrasing apply only to its domain — a name differing only in characters the default agent keeps (an apostrophe) must be said with them.
- **A non-Timerify entity sharing a target's name is not reachable through Timerify's phrases** — the handler resolves among Timerify targets only; the static list cannot tell them apart — "turn off X in 5 minutes" always means the Timerify target.
- **Regeneration: a dispatcher signal at every timer setup and unload (which covers options, subentry and rename changes, since each reloads), entity registry updates of a target (name, aliases, original name, entity id, device) and device registry updates of its device (name, user name), debounced by `VOICE_SYNC_COOLDOWN`; the first write runs before the entry's setup returns when Home Assistant is running, else once it has started** — event-driven, one write per burst (a reload is an unload then a setup), and a start-up write lists every timer — a friendly name of a target that has no registry entry is noticed only at its timer's next reload (follow-up).
- **A build that fails hassil validation leaves the existing file untouched and logs an error; escaping makes it impossible by construction, and a test that disables the escaping proves the guard** (V7) — a malformed file breaks Assist for the whole language (research §3) — a valid but stale file stays until the cause is fixed.
- **The files are written while the option is on even with no timer; the sources declare the lists empty** — an empty list loads and matches nothing, so the manual route without a names file is not broken either — none.
- **hassil is imported directly; the manifest declares `after_dependencies: ["conversation"]`** (V8, research risk 1) — Home Assistant installs an after-dependency's requirements before importing the integration (`requirements.py:197`) — an installation without `conversation` still gets hassil installed with it.
- **Handlers are registered once in `async_setup` with `intent.async_register`; they find the timer by name among the loaded entries** — the registry is global by intent type (`intent.py:68-82`) and there is one entry per target — none.
- **Interval switches become `EntityCategory.CONFIG`** (V4) — the switch configures the timer's schedule, which is that category's meaning, and `_is_default_exposed` exposes no categorised entity (`exposed_entities.py:304-309`); number and sensors are not exposed by default already — the switch moves to the device page's configuration section; one already exposed by 0.3.0 keeps the user's stored choice.
- **Tools are offered only while at least one timer's target is exposed to the asking assistant (any, without one); descriptions and the prompt are English** — core's climate pattern and core's language for LLM text; the spec calls tools language-agnostic — an LLM in another language reads English descriptions, as with every core tool.
- **Every slot is typed with renderable validators, checked by `to_openapi(strict=True)`** — a callable without a type hint renders as an open schema and an LLM would get no type — a boolean passed as a number by an LLM is coerced, not refused.
- **Russian is tested without Cyrillic in tests: inputs are sampled from the Russian sentence files with hassil's sampler, plural forms are proven by classes (1, 21… / 2–4, 22… / 5–20, 11–14, 25…) rendering alike within a class and differently between classes; English texts are asserted literally** — the `pre-commit` hook allows Cyrillic only in the product's translations, and escapes would dodge that rule — whether the Russian words themselves read well is for the owner's review of `sentences/ru/` and `ru.json`.
- **Russian answers put the target's name first, in the nominative, followed by a colon; times are local 24-hour `HH:MM`, with "tomorrow" when the day is the next one** — names cannot be declined, and core's Russian sentences accept nominative names too — none.
- **Voice tests run in `tests/voice/` with `hass_tmp_config_dir` and an empty `configuration.yaml`** (V8) — the default config dir is inside site-packages, and `conversation.reload` without a language reads `configuration.yaml` — none.

---

## Appendix: pre-flight (shared files and interfaces; gate after each task)

| Pair | Shared | Conflict and resolution | Gate green after the later task |
|---|---|---|---|
| T1 → T2 | `voice/base.loaded_timers`, `tests/voice/helpers.py` | T2 adds the voice-entry filter to `loaded_timers`; T1's tests keep the manual route (`copy_sentences`), later tasks use `add_voice_entry` | yes |
| T1 → T4–T7 | `voice/__init__.HANDLER_TYPES`, `sentences/<lang>/timerify.yaml` (intents, lists, rules, responses) | each appends its handlers and its own intent, lists and responses; `test_every_language_has_the_same_intents_and_responses` guards parity | yes |
| T1 → T3 | `HANDLER_TYPES`, `tool_name`, `read_only` | T3's tool-set assertion is `== {c.tool_name for c in HANDLER_TYPES}`, so later handlers need no T3 edit; each later task proves its tool in its own LLM test | yes |
| T2 → all | `config_flow.py` `user` menu; `tests/test_config_flow.py`; smoke `add_timer` | T2 edits the target flows to pick `target` and updates `add_timer`; options `init` keeps its id for timers | yes |
| T2 → T7 | `voice/sentences.build(sources, names)` | T7 adds the `intervals` parameter with a default of `()` and the `timerify_interval` list; the empty list is declared in the sources from T7 | yes |
| T2 → T5 | `load_sources` reads every `*.yaml` of a language | T5's generated `delayed_commands.yaml` is picked up without a change to T2's code | yes |
| T4 → T5 | `<duration>`, `<settings>` rules, `SETTING_SLOTS`, `duration_of`, `duration_out_of_range` | T5 reuses them for the extras and for `async_turn_off_in`'s bound | yes |
| T4 → T5, T6 | `controller.py` | T4 adds bound checks to three methods; T5 adds `async_turn_off_in` and moves `async_add_command`'s off check into a private helper both call (same refusal, same key); T6 adds `async_cancel_commands`; none changes another's signature | yes |
| T5 → T6 | `voice/commands.py`, voice-made commands | T6 adds two handlers to the module T5 creates | yes |
| T3 → phase 3 | `switch.py` description | the category changes no unique id or name; `tests/test_interval_switch.py` is edited only if it asserts the category | yes |
| T2, T4, T7 | `translations/en.json` + `ru.json`, `test_translations.py` (same keys and blanks in every language) | every task adds its keys to both files | yes |
| T1 → T8 | `manifest.json`, `pyproject.toml` | T1 adds `after_dependencies` and dev deps; T8 edits only `version` | yes |
