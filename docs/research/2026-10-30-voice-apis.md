# Voice and AI APIs for phase 4: research (2026-10-30)

Verified against the installed Home Assistant 2026.10.4. Paths below are abbreviated:

- `HA/` = `.venv/lib/python3.14/site-packages/homeassistant/`
- `HASSIL/` = hassil 3.12.1, `HAI/` = home-assistant-intents 2026.10.6. These are the exact
  versions pinned by `HA/components/conversation/manifest.json:9-13`, together with
  `gazetteer-matcher==1.1.0`. **None of the three is installed in the project venv**, so the
  `conversation` integration cannot even be imported in our tests today: it imports hassil at
  `HA/components/conversation/__init__.py:7`. I read the wheels and ran a throwaway pytest probe
  with them on `PYTHONPATH`. The probe's results are marked **[probe]**. It is not committed.

Spec context: §6.4 (LLM tools; intent handlers; managed `custom_sentences/<lang>/timerify.yaml`;
takeover of core delayed commands for Timerify targets only; translated responses; `en` and `ru`).

## 1. Intents (`HA/helpers/intent.py`)

- **Registration.** `async_register(hass, handler)` at `:68-82` uses one global registry keyed by
  `intent_type`. A second registration logs a warning and replaces the first (`:75-79`).
  `async_remove(hass, intent_type)` is at `:85-91`. With one config entry per target, the
  handlers must be registered once (in `async_setup`) and must resolve the target to its
  controller themselves.
  - Core alternative: an `intent.py` platform with `async_setup_intents(hass)`
    (`HA/components/intent/__init__.py:103-105, 172-177, 639-643`). The `intent` integration
    processes it only while it is loaded. Example: `HA/components/climate/intent.py:28-31`.
- **`IntentHandler`** (`:884-928`):
  - Attributes: `intent_type`, `platforms: set[str] | None`, `description`, and
    `slot_schema` (a property or class attribute: a dict of `probatio.Required/Optional` to a
    validator).
  - `async_validate_slots` wraps each validator as `{"value": validator}` and allows extra keys
    (`:902-919`).
  - `async_handle(intent_obj) -> IntentResponse` (`:921-924`).
  - `platforms` is not used for dispatch: `async_can_handle` has no caller. Only the `llm.py`
    filters read it (`HA/components/intent/llm.py:104-109`, `HA/components/intent_script/llm.py:33-37`).
  - Core imports `probatio`, not `voluptuous`. Example: `HA/components/intent/timers.py:11, 846-850`.
- **`async_handle(...)`** (`:99-149`) builds an `Intent` with: platform, slots, `text_input`,
  context, language, assistant, `device_id`, `satellite_id` and `conversation_agent_id`.
  - `language` defaults to `hass.config.language` (`:121-122`).
  - `probatio.Invalid` becomes `InvalidSlotInfo` (`:141-143`).
  - `IntentError` subclasses pass through (`:144-145`).
  - Any other exception is logged with a traceback and raised as `IntentUnexpectedError`
    (`:146-148`). So a `ServiceValidationError` from our controller becomes a generic error.
- **`Intent`** (`:1324-1371`) has the fields above. `create_response()` returns
  `IntentResponse(language=self.language, intent=self)`.
- **`IntentResponse`** (`:1436-1556`):
  - `async_set_speech(speech, speech_type="plain")` (`:1459`).
  - `async_set_error(code, message)` sets type ERROR plus the code and speaks the message
    (`:1492-1499`).
  - `async_set_results`, `async_set_states` (`:1501-1517`).
  - `async_set_speech_slots(dict)`: slots for the default agent's response template (`:1519-1522`).
  - `as_dict()` (`:1524-1556`).
  - Types are `ACTION_DONE`, `QUERY_ANSWER` and `ERROR`. `PARTIAL_ACTION_DONE` has been
    deprecated since 2026.3 (`:1374-1396`).
  - Error codes are `no_intent_match`, `no_valid_targets`, `failed_to_handle` and `unknown`
    (`:1399-1412`).
- **Slots as they arrive:**
  - Default agent: `{"value": <list out value or number>, "text": <spoken text>}`
    (`HA/components/conversation/default_agent.py:565-570`).
  - LLM `IntentTool`: `{"value": v}` only, with blank values dropped (`HA/helpers/llm.py:376-380`).
  - [probe] A list value `{in: boiler, out: switch.boiler}` arrives as
    `{"value": "switch.boiler", "text": "boiler"}`.
  - [probe] A range arrives as float `15.0` for digits and int `15` for words. Coerce it with
    `probatio.Coerce(int)` or `cv.positive_int`.
- **Matching** (`async_match_targets`, `:578-845`; constraints dataclass `:311-356`):
  - Constraints: `name`, `area_name`, `floor_name`, `domains`, `device_classes`, `features`,
    `states`, `assistant`, `allow_duplicate_names` and `single_target`.
  - Exposure is checked only when `constraints.assistant` is set. It uses
    `async_should_expose(hass, assistant, entity_id)` (`:599-606`) and is applied at `:632-635`
    (fast path) or `:727-731`. The result is `MatchFailedReason.ASSISTANT`.
  - Names compare by `strip().casefold()` against the entity id or any alias (`:477-503`, `:1559-1577`).
  - Pattern: `HA/components/climate/intent.py:69-89` passes
    `assistant=intent_obj.assistant, single_target=True` and raises `MatchFailedError`.
- **Language in a handler:** use `intent_obj.language`, as in `climate/intent.py:174-176`.
  Values seen:
  - The default agent passes `user_input.language or hass.config.language` (`default_agent.py:605, 637-641`).
  - LLM tools pass `llm_context.language` (`HA/helpers/llm.py:397`).
  - The MCP server passes `language="*"` (`HA/components/mcp_server/http.py:167-173`).
  - So a handler needs a fallback for languages it does not know.
- **Errors, and how each one ends up translated:**
  1. `MatchFailedError`: the default agent maps it to the built-in, translated
     `no_entity`/`no_entity_exposed`/... texts (`default_agent.py:645-656`, `:1861`).
  2. `IntentHandleError(message, response_key=...)`:
     - Default agent: uses `responses.errors[response_key]` of the loaded language, which
       includes keys from custom sentence files. It falls back to the language's `no_intent`
       (`default_agent.py:657-666, 1436-1459`). [probe] A custom file's `responses.errors` key
       was spoken, with code `failed_to_handle`.
     - It is also **logged with a traceback at ERROR** (`:660`).
     - LLM path: the exception propagates and `chat_log` turns it into
       `ToolResult(error=True, data={"error": "IntentHandleError", "error_text": str(e)})`
       (`HA/components/conversation/chat_log.py:481-487`). The text is our raw message.
  3. `response.async_set_error(code, our_translated_text)`: quiet, and works for both agents.
     The text has to come from our own translations
     (`HA/helpers/translation.py:335-358`, `async_get_translations(hass, language, category,
     [DOMAIN])`). Any category name loads at runtime (`:71-83`).
  4. `HomeAssistantError(translation_key=...)` stringifies **in English only**
     (`translation.py:433-458`, `language = "en"` at `:442`).

## 2. LLM tools

- **Discovery:** `HA/components/llm/__init__.py`.
  - `LazyIntegrationPlatforms(hass, "llm", ...)` (`:60-67`) imports `<domain>/llm.py` for loaded
    integrations only (`HA/helpers/integration_platform.py:272-342`).
  - Existence is checked by file name in the integration's directory (`HA/loader.py:1264-1283`).
    Custom integrations get that listing too (`HA/loader.py:305-325` →
    `resolve_from_root` → `os.listdir` at `:707`).
  - [probe] A custom `llm.py` was discovered, and its tool and prompt fragment appeared in the
    Assist API instance.
- **Platform signature** (`:47-57`): `@callback def async_get_tools(hass, llm_context, api_id) ->
  LLMTools | None`.
  - `LLMTools(tools: list[Tool], prompt: str | None = None)` (`:39-44`).
  - Platforms are called in domain order. An exception is logged and skipped (`:78-99`).
- **Rules checked at collection** (`:102-130`):
  - Names must start with `f"{domain}__"`. A custom integration gets a WARNING log; enforcement
    is announced for 2027.3 (`:32`).
  - `tool.integration` must be set (`report_untagged_tool`, `HA/helpers/llm.py:263-280`; breaks 2027.10, `:45`).
  - Returning a plain JSON object instead of `ToolResult` is deprecated, breaking in 2027.11.0
    (`HA/helpers/llm.py:247-258`).
  - Tool-name character set and length limits are provider-specific: UNVERIFIED. `intent_script`
    slugifies "into valid tool names" (`HA/components/intent_script/llm.py:42-47`).
- **API ids:** only the Assist API (`LLM_API_ASSIST = "assist"`, `HA/helpers/llm.py:43`;
  `AssistAPI`, `llm/__init__.py:133-155`) calls the platforms.
  - Other APIs (`mcp` client `HA/components/mcp/__init__.py:69`, `knx/llm_api.py:603`) are their
    own and do not include integration tools.
  - The MCP *server* serves Assist (`HA/components/mcp_server/server.py:80-95`).
  - `async_get_api(hass, id | [ids], llm_context)` merges several ids (`HA/helpers/llm.py:97-121, 454-500`).
- **Types** (`HA/helpers/llm.py`):
  - `LLMContext(platform, context, language, assistant, device_id)` (`:130-147`).
  - `ToolInput(tool_name, tool_args, id, external)` (`:150-158`).
  - `ToolResult(data: JsonObjectType, error=False)` (`:161-166`).
  - `ToolAnnotations(read_only, destructive, idempotent, open_world)`, with the least-safe
    defaults (`:169-179`).
  - `Tool` has `name`, `title`, `description`, `parameters: probatio.Schema`, `annotations`,
    `integration` and `async_call(hass, tool_input, llm_context)` (`:182-203`).
- **`IntentTool(name, handler, *, title, integration, annotations)`** (`:332-401`):
  - `description` comes from `handler.description` and `parameters` from `handler.slot_schema`
    (`preferred_area_id`/`preferred_floor_id` become hidden extras, `:355-369`).
  - Calling it runs `intent.async_handle` with `platform`, `context`, `language`, `assistant` and
    `device_id` from `llm_context`. It does not pass a satellite or agent id (`:390-400`).
  - It returns `IntentResponseDict`, which is `as_dict()` without language and card and includes
    `speech_slots` (`:404-417`).
  - [probe] The tool result was `{'speech': {}, 'response_type': 'action_done', 'speech_slots':
    {...}, 'data': {...}}`.
  - A plain `Tool` subclass sees `llm_context` directly (`HA/components/llm/llm.py:19-45`).
- **Who sets `assistant`:**
  - Conversation agents use `ConversationInput.as_llm_context` → `assistant="conversation"`
    (`HA/components/conversation/models.py:63-71`).
  - The MCP server sets the same (`mcp_server/http.py:171`).
- **Exposure is the tool's job.** `AssistAPI` does no filtering.
  - Patterns:
    - `HA/components/climate/llm.py:27-55`: offer the tools only if an entity of the domain is
      exposed.
    - `HA/components/intent_script/llm.py:14-53` and `HA/components/intent/llm.py:83-109`:
      filter by `handler.platforms & exposed_domains`.
  - The targets themselves are filtered by passing `assistant=` to `async_match_targets`.
- **Core delayed commands are not an LLM tool** unless the device supports timers
  (`HA/components/intent/llm.py:37-46, 91-96`). Timerify's tools would be an LLM's only way to
  do a delayed command for most devices.

## 3. Built-in agent sentences

- **Loading** (`default_agent.py:1220-1317`):
  - The language is resolved with `language_util.matches(language, get_languages())` and the
    first variant wins (`:1227-1235`).
  - It reads `HAI/data/<variant>.json`, then every
    `hass.config.path("custom_sentences", <variant>)` file matching `rglob("*.yaml")` (recursive)
    with `yaml.safe_load`. Files that are not a dict are skipped with a warning (`:1251-1271`).
  - Every custom `intents.*.data[*]` gets metadata `hass_custom_sentence: True` (`:1273-1284`;
    constant `HA/components/conversation/const.py:32`).
  - Then everything is `merge_dict`-ed into one dict (`:1286`): dicts merge, **lists are
    extended**, and scalars are overwritten (`HASSIL/util.py:55-74`).
  - So custom files can use built-in lists and expansion rules (en `<the>`, `<turn>`; ru
    `<turn_on>`, `<turn_off>`). Neither language ships an HVAC-mode list (checked `HAI/data/en.json`
    and `ru.json` `lists`).
  - YAML `conversation: intents:` is merged last (`:1295-1298`).
  - A missing directory is simply skipped (`:1255`).
- **File format** (`HASSIL/intents.py:457-544`):
  - Top level: `language`, `intents.<Name>.data[]`, `lists`, `expansion_rules`, `skip_words`,
    `settings`, `responses`.
  - Per data block: `sentences`, `slots` (fixed slot values), `requires_context`,
    `excludes_context`, a local `expansion_rules`, a local `lists`, `response`, `metadata`,
    `required_keywords`, `inferred_domain`, `name_domains`, `settings`.
  - Lists (`:547-610`):
    - `values`: strings, or `{in, out, context, metadata}`.
    - `range`: `from`, `to`, `step`, `multiplier`, `digits`, `words`, `words_language`, `fractions`.
    - `wildcard: true`.
  - Response templates live under `responses.intents.<Intent>.<key>`, error templates under
    `responses.errors.<key>` (`default_agent.py:1305-1308`).
- **Values are parsed as templates when they contain any of `()[]{}<>|@`** (`HASSIL/util.py:32,
  198-200`; `intents.py:557-577`). This applies to the `in` of `{in,out}` too.
  - [probe] The name `boiler (main` raised `ParseError`. `Boiler [2]` and `A|B lamp` loaded but
    never matched.
  - Backslash-escaping all eight characters made every case match.
  - [probe] **One malformed custom file makes the whole language fail.** Even "turn off fan"
    raised `ParseError` from `conversation.async_converse`. The load has no guard
    (`default_agent.py:1183-1218`).
- **Which response is spoken** (`default_agent.py:594-701`):
  - The handler's own speech wins.
  - Only if the response has no speech is `responses.intents.<intent>.<response_key>` rendered
    (`:676-690`). `response_key` is the data block's `response`, default `"default"`
    (`HASSIL/recognize.py:736`).
  - The template sees:
    - `slots`: each recognized slot's text, or its value, merged with the handler's
      `speech_slots` (`:574-577, 1123`).
    - `state`: the first matched or unmatched state.
    - `query.matched/unmatched` (`:1108-1155`).
  - [probe] `{{ slots.target }}` gave "boiler" (the text), and `{{ slots.left }}` came from the
    handler.
  - [probe] With neither a template nor speech, the response is empty.
  - The LLM path never renders templates.
- **`conversation.reload`** (`HA/components/conversation/services.py:42-47, 72-85, 98-100`;
  `services.yaml`) takes `language` and `agent_id`, both optional.
  - Without `language` it re-reads the YAML `conversation:` config
    (`async_integration_yaml_config`) and clears **all** cached languages
    (`default_agent.py:1157-1167`).
  - With `language` it pops only that exact cache key.
  - The cache is keyed by the language string the user sent, not by the variant (`:1183-1218`).
  - [probe] After the file was removed and `reload(language="en")` called, an `en-GB` request
    still used the old sentences. `en` was refreshed.
  - [probe] Without `language`, reload raised `FileNotFoundError` when the config dir had no
    `configuration.yaml`. That is only an issue in tests.
  - Intents load lazily, so a file written before the first request needs no reload. [probe] A
    file written after the first load was ignored until reload.
- **Ranking** (`default_agent.py:816-949, 1089-1106`):
  - Stage 1: `recognize_best(..., best_metadata_key="hass_custom_sentence", best_slot_name="name")`
    with only exposed names in the `name` list.
  - Stage 2: the same with only unexposed names (`:885-916`).
  - Stage 3: unknown names, for error messages.
  - `recognize_best` (`HASSIL/recognize.py:729-847`): **if any custom sentence matches, all
    built-in results are dropped** (`:766-782`).
  - Among what remains, results with a non-wildcard `name` slot are preferred, longest
    `name` text first (`:784-807`).
  - Then the order is fewer wildcards, more literal text, less wildcard text, intent name (`:819-847`).
  - Sentence triggers (`agent_manager.register_trigger`) run before all intents
    (`default_agent.py:476`). They are not language-scoped and turn every list reference into a
    wildcard (`:1462-1482`). They are internal API.
- **Does a generated list guarantee that only Timerify targets match?** It holds for our
  sentences, but not the other way round.
  - [probe] With "Boiler" in our list and "Fan" not:
    - "turn off boiler in 15 minutes" → our intent.
    - "turn off fan in 15 minutes" → `HassStartTimer`.
    - "Turn off Boiler in 15 minutes." matched (case and punctuation are normalised).
  - Any phrasing we do not mirror falls to core's wildcard delayed command, *with a Timerify
    target inside*. [probe] "turn off **the** boiler in 15 minutes" without `[the]`,
    "in 15 minutes turn off boiler", and "... in 2 hours" all went to core.
  - A static list is the same in stage 1 whatever the exposure, so **the handler must check
    exposure**. [probe] An unexposed target still matched our sentence.
  - A non-Timerify entity that shares a target's name or alias is captured by our sentence.
  - A list value matches only its own spelling.
    - [probe] "kids lamp" missed `kid's lamp`.
    - The default agent strips punctuation from its own names (`default_agent.py:1082`) and
      includes aliases (`:1052-1087`).
    - Duplicate names: the matcher takes the first value only (comment at `:1344-1347`).

## 4. Core delayed commands (`HassStartTimer` with `conversation_command`)

- **en** (`HAI/data/en.json:3206-3277`): seven blocks with `response: "command"`, for
  hours, hours+minutes, hours+minutes+seconds, hours+seconds, minutes, minutes+seconds and
  seconds. Each block has both word orders. The minutes block (`:3250-3251`):
  `"{timer_command:conversation_command} (in|after) {timer_minutes:minutes}( |-)minute[s]"`
  and `"(in|after) {timer_minutes:minutes}( |-)minute[s] {timer_command:conversation_command}"`.
  - Lists (`:4604-4621`): `timer_minutes`/`timer_hours`/`timer_seconds` = `range 1..100`,
    `timer_command` = `wildcard`.
  - Response template: `:83` ("Command will be executed in ...").
- **ru** (`HAI/data/ru.json:2042-2112`): the same seven combinations and both orders, with the
  preposition "cherez" (in transliteration) instead of `(in|after)`. Unit words carry optional
  endings: "minut[u|y]", "chas[a|ov]", "sekund[u|y]". The minutes block is at `:2086-2087`. The
  lists are at `:3128-3145` (ranges 1..100, wildcard). The response is at `:74`, and it chooses
  Russian plural forms in Jinja (`n % 10`, 11-14 rules).
- **Handling** (`HA/components/intent/timers.py`):
  - `StartTimerIntentHandler` (`:841-905`) skips the device check for a delayed command
    (`:863-870`).
  - It validates the command by recognizing it with the default agent, including sentence
    triggers (`:907-947`).
  - It keeps a `TimerInfo` in the in-memory `TimerManager.timers` dict (`:225-227, 247-300`).
  - When the timer finishes, it runs `conversation.async_converse(command_text, ...)` again,
    and only logs a failure (`:453-499`).
  - Delayed-command timers are excluded from cancel and status matching (`:546-549, 681-684`). So they
    are non-persistent and cannot be cancelled, as the spec says.
  - Because the text is re-recognized when the timer fires, a core delayed "turn off boiler"
    would at that point go through our sentences if we ship a bare "turn off {target}".

## 5. Writing the files

- Path: `hass.config.path("custom_sentences", <variant>, "timerify.yaml")`. Use the variants
  `en` and `ru`, the ones `_load_intents` resolves to (`default_agent.py:1235, 1252-1254`).
- The core writes into the config dir from the executor:
  - Blueprints: `mkdir(parents=True, exist_ok=True)` + `write_text` in
    `hass.async_add_executor_job` (`HA/components/blueprint/models.py:332-364`), and `unlink` in
    the executor for removal (`:324-330`).
  - Config editor: `dump` + `write_utf8_file_atomic` via the executor
    (`HA/components/config/view.py:132, 252-257`).
  - Helpers: `HA/util/file.py:18-44` (atomic, fsync) and `:46-82` (temp file + `os.replace`,
    mode 0644).
  - `HA/util/yaml.dump` → `annotatedyaml/dumper.py:21-29`
    (`allow_unicode=True, sort_keys=False`, safe dumper). A header comment has to be prepended
    by hand.
- An absent directory is created by the writer; the reader skips it (`default_agent.py:1255`).
  I found no core integration that writes `custom_sentences` (the feasibility note said the
  same).

## 6. A "global option" with one entry per target: options, not a decision

1. **A second entry kind in the same domain.**
   - Precedent: `group`'s `user` step is a `SchemaFlowMenuStep` of kinds (`HA/components/group/config_flow.py:207`)
     with options routed by kind (`:186-187`). Menu support is in
     `HA/helpers/schema_config_entry_flow.py:107-119`.
   - A singleton is possible with `async_set_unique_id` / `_abort_if_unique_id_configured`
     (`HA/config_entries.py:3318, 3262`).
   - Per-entry hooks: `async_get_supported_subentry_types(cls, config_entry)` (`:3191`) can
     offer no intervals, and `async_supports_options_flow` (`schema_config_entry_flow.py:367`).
   - Pitfalls:
     - `integration_type: helper` covers the whole domain.
     - `async_setup_entry` and `TargetController.__init__` assume a target
       (`custom_components/timerify/controller.py:137-141` raises `target_not_found`).
     - The entry title and the options flow must branch.
     - Removing the entry must delete the files.
2. **A per-target option** ("include in voice sentences"), aggregated over the entries: the files
   exist while at least one target opts in. There is no global switch, and no new entry kind.
3. **`single_config_entry`** is domain-wide (`HA/config_entries.py:1623, 4341-4344`), so it is
   unusable here.
4. **YAML `async_setup` config:** forbidden by the repo rules, and Timerify declares
   `config_entry_only_config_schema` (`custom_components/timerify/__init__.py:19`).
5. **An option entity** (e.g. a switch) still needs an entry and device. A `switch` is
   default-exposed to Assist unless it has an `entity_category`
   (`HA/components/homeassistant/exposed_entities.py:32-44, 304-316`).
6. **Domain-level options without any entry:** I found no such API in `config_entries.py`
   (UNVERIFIED that none exists).

## 7. Languages, numbers, plurals

- `HAI` ships `en` and `ru` (`HAI/languages.py:13, 50`): 42 intents for en and 30 for ru, both
  including `HassStartTimer`, `HassTurnOn/Off` and `HassTimerStatus`.
  - Scores: en-US and en-GB `cloud 3 / focused_local 2 / full_local 3`; ru-RU `3 / 0 / 3`
    (`HAI/language_scores.json:62, 252`).
  - [probe] `en-GB` input loads the `en` variant and our `custom_sentences/en` file.
- **Word numbers:** a range accepts digits and, unless `words: false`, number words from
  `unicode-rbnf` for the request language (`HASSIL/string_matcher.py:881-990, 1086-1114`;
  `numbers.py:41-61`; `intents.py:54-71`). The language is passed by the default agent
  (`default_agent.py:1104`).
  - [probe] With unicode-rbnf 2.4.1 for ru, every case and gender of each number is in the trie
    (e.g. 1 has its feminine accusative form, as in "one minute").
  - [probe] ru "... cherez pyatnadtsat minut" (in Cyrillic) gave `minutes=15` and en
    "fifteen minutes" gave `15`.
  - [probe] The bare ru "in a minute" (no number word) matched nothing, core included.
  - A large range (e.g. 1..1440) builds a larger per-language word trie; it is cached
    (`string_matcher.py:895-905`).
- **Plurals:** backend translations are filled in with `str.format` only
  (`HA/helpers/translation.py:454`), so they have no plural rules. Babel is not in the venv.
  - Core does ru plurals in the response Jinja (`HAI/data/ru.json:74`).
  - So plural-correct speech means one of two things: templates in the managed files (default
    agent only), or code that picks the plural form before formatting.

## 8. Testing

- **Dev dependencies needed:** `hassil==3.12.1`, `home-assistant-intents==2026.10.6`,
  `gazetteer-matcher==1.1.0` (the conversation manifest pins). `holidays==0.106` is the
  existing precedent in `pyproject.toml`.
  - `pytest-homeassistant-custom-component` sets `skip_pip`
    (`pytest_homeassistant_custom_component/common.py:288`), so it does not install them.
- **Config dir:**
  - The default `hass_config_dir` is the plugin's own `testing_config` inside site-packages
    (`plugins.py:684-691`, `common.py:199-201`). Writing there would pollute the venv.
  - Override it with the documented `hass_tmp_config_dir` (`plugins.py:663-681`), which copies
    `testing_config` into `tmp_path`.
  - Pitfall: at setup the loader imports `custom_components` from the config dir
    (`HA/loader.py:1703-1712`). The tmp copy's `custom_components` would shadow ours, unless our
    package was imported first. `tests/conftest.py:38` already imports it, and [probe] the shadow
    happened without that import.
  - Create `configuration.yaml` in the tmp dir if the test calls `conversation.reload` without
    `language`.
- **Driving the default agent** ([probe], works):
  - Set up `homeassistant`, `conversation` and `intent`.
  - Then `await conversation.async_converse(hass, text, None, Context(), language="en")`
    (`HA/components/conversation/agent_manager.py:79-95`). It returns a `ConversationResult`
    with `.response` (an `IntentResponse`).
  - Or call the service `conversation.process` with `return_response=True` (`services.py:50-69`).
  - Or call `intent.async_handle(hass, platform, intent_type, slots, language=...)` directly.
- **Exposure:** the `homeassistant` component creates `ExposedEntities`
  (`HA/components/homeassistant/__init__.py:423-425`).
  - `async_expose_entity(hass, "conversation", entity_id, bool)` (`exposed_entities.py:508-517`).
  - Default exposure is per domain: `switch`, `light`, `fan`, `climate`, `water_heater`, ... are
    exposed when new (`:32-44, 67-69, 304-316`).
- **LLM tools** ([probe], works):
  - `api = await llm.async_get_api(hass, llm.LLM_API_ASSIST, llm.LLMContext(platform="test",
    context=Context(), language="ru", assistant="conversation", device_id=None))`.
  - Check `api.tools` and `api.api_prompt`.
  - Then `await api.async_call_tool(llm.ToolInput("timerify__x", {...}))` (`HA/helpers/llm.py:228-260`).
  - Errors propagate as exceptions. The chat log, not the API, turns them into error results.

## Risks / open questions

1. **A bad managed file takes Assist down for that language.** Names must be escaped (all of
   `()[]{}<>|@\`), and the generated dict should be validated with
   `hassil.intents.Intents.from_dict` before writing. Hassil is a runtime requirement of
   `conversation`. Whether Timerify may import it is a manifest question, probably
   `after_dependencies: ["conversation"]`.
2. **The takeover is only as complete as our sentences.** Every core delayed-command shape
   (seven unit combinations × two word orders × `in|after`, articles; ru likewise) must be
   mirrored for Timerify targets. Otherwise core captures the phrase with our target inside.
   A test can generate the core shapes from `HAI` and assert that none reaches `HassStartTimer`
   for a Timerify target.
3. **Exposure is not reflected in a static list.** Handlers must check
   `async_should_expose(hass, intent_obj.assistant, entity_id)`, or match with
   `assistant=`, and answer in a translated way.
4. **Reload granularity.** `reload` with `language` misses regional keys such as `en-GB`, and
   without it re-reads the YAML config. The plan must choose one.
5. **The name list** must mirror the default agent: aliases, punctuation-stripped forms,
   regeneration on rename, alias edits and entry add/remove. Duplicate target names cannot be
   told apart by the matcher (it takes the first value).
6. **Error style.** `IntentHandleError` logs a traceback on every expected refusal. Using
   `async_set_error` with our own translations is quiet, but needs the translation lookup and a
   fallback for `language="*"` (MCP) or unknown languages.
7. **Plurals in ru:** templates in the managed files cover only the default agent. Handler-made
   speech (LLM, other agents) needs plural selection in code.
8. **Timerify's interval `switch` entities are exposed to Assist by default** (domain `switch`,
   no `entity_category`). That contradicts §6.4's "Timerify's own entities are not meant to be
   exposed", and puts them in the core `name` list and the LLM prompt.
9. **The spec says "turn on X" routes to Timerify (R9).** A bare custom "turn on
   {timerify_target}" overrides core `HassTurnOn` for targets. Whether bare on/off should be
   taken over at all is open.
10. **The LLM path never renders response templates.** Tool results should carry structured
    data, such as remaining minutes and end time, in `speech_slots` or results.
