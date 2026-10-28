# Per-entity timer/auto-off/schedule HACS integration: research (2026-10-28)

**Verdict.** The gap is real but narrower than it looks. Nobody found attaches a countdown `number` plus remaining-time sensor to the *source device* in the post-2026.8 correct way, and nobody has Assist support. Simple Timer is a near-complete competitor on everything except those two points. Feasible: every mechanism needed exists and is documented. The Assist piece is the riskiest, because 2026.8 changed how intents reach LLMs.

## 1. Prior art (stats via GitHub API, 2026-10-28)

| Project | Status | What it does / difference |
|---|---|---|
| [ArikShemesh/ha-simple-timer](https://github.com/ArikShemesh/ha-simple-timer) | v1.8.0 2026-08-11, 168 stars, in [HACS default](https://github.com/hacs/default/blob/master/integration). GPL-3.0 per GitHub, README says MIT | **Closest.** Per-entity (switch, input_boolean, light, fan, climate) countdown, auto-off when turned on manually, delayed start, one-off/weekly schedule, extend, daily runtime, cancel on external off, bundled card, `start_timer`/`schedule_timer` services. Entities: only a runtime sensor and a status sensor (no number/switch platform). No Assist/intent code (source grepped). Its own test file says that on HA 2026.8.0 sharing another integration's identifiers gives it a **separate device row**, not the source device, and it does not use `entity.device_entry`. Restart: `Store` plus offline compensation. |
| [jozefnad/homeassistant-quick_timer](https://github.com/jozefnad/homeassistant-quick_timer) | 2.0.7 2026-07-24, 56 stars, MIT, HACS default | One-shot delayed actions (start/finish actions, relative or HH:MM), card injected into more-info dialogs, one `sensor.quick_timer_monitor`, services only, `integration_type: service` (no device attach), en/sk/nl/fr/de UI. No recurring schedules, no Assist. Persists via `Store`. |
| [nielsfaber/scheduler-component](https://github.com/nielsfaber/scheduler-component) + [card](https://github.com/nielsfaber/scheduler-card) | 915 stars; last release v3.3.8 2024-11-16 (commits continue); card 1268 stars, v4.0.19 2026-06-30 | Schedules as `switch.schedule_<token>` on its own "Scheduler" device, any service as action. No countdown/auto-off, not attached to source device, no Assist. |
| [rianadon/timer-bar-card](https://github.com/rianadon/timer-bar-card) | 607 stars, v1.31.1 2025-06-14, last push 2025-07 | Display-only card for `timer.*`/attribute countdowns. |
| [gh0stblizz4rd/ha-switch-timer](https://github.com/gh0stblizz4rd/ha-switch-timer) | 41 stars, v2.0.0 2025-08-09 | A `switch_timer` entity per switch, `set_timer` turns on/off/toggle after a delay. |
| [wit3/hacs-auto-off-timer](https://github.com/wit3/hacs-auto-off-timer), [andrei-cmnd/ha-switch-timer](https://github.com/andrei-cmnd/ha-switch-timer), [bhuebschen/delayed_action](https://github.com/bhuebschen/delayed_action) | 0 / 0 / 7 stars; beta 2026-01 / unreleased (created 2026-10-15, needs 2026.10+) / v0.1.5 2024-08 | Auto-off with a remaining sensor; start-from-card timer with its own device; delay services. None has Assist. |
| [scootaash/hass-timer-manager](https://github.com/scootaash/hass-timer-manager) | 0 stars | Mirrors Assist *voice* timers as sensors (not per-entity). |

New low-star entrants appear monthly, so the category is crowded. Differentiation must be (a) correct same-device attachment, (b) a `number` "run for N min" entity with set-0-to-stop semantics, (c) Assist.

## 2. Home Assistant core today

- **Voice timers** (`HassStartTimer`, Cancel, Increase/Decrease, Pause/Unpause, TimerStatus): 2024.6 ([#117199](https://www.home-assistant.io/changelogs/core-2024.6/), [blog](https://www.home-assistant.io/blog/2024/06/26/voice-chapter-7/)). They live on voice satellites and are not `timer.*` entities ([docs](https://www.home-assistant.io/voice_control/builtin_sentences)). Timer management from any device: 2024.7 (#120440). `HassCancelAllTimers`: 2024.12 ([#130873](https://www.home-assistant.io/changelogs/core-2024.12/)).
- **Delayed commands** ("turn off the lights in 5 minutes"): 2024.6 (#118325, `conversation_command` slot on `HassStartTimer`). Sentences are `(in|after) N minute[s]` ([intents repo](https://github.com/home-assistant/intents/blob/main/sentences/en/HassStartTimer/command_minutes.yaml)). Docs: they "cannot be canceled or modified". `intent/timers.py` has no storage in a grep for Store/restore, so they are probably lost on restart (not runtime-tested). Later: validation 2026.3 (#149915); warning when one fails, 2026.10 (#182492).
- **"Turn on X for N minutes"**: no sentence, intent slot or doc found (searched the intents tree and the docs). `HassTurnOn` has no duration.
- **Core `timer` helper** ([docs](https://www.home-assistant.io/integrations/timer/)): `restore` option exists, but `timer.finished` is not fired if it expired while HA was down.
- **Gap the idea fills:** duration semantics ("for"), cancel/query tied to an entity, persistence, per-entity auto-off, device-page entities.

## 3. Attaching entities to another integration's device

- **Old pattern** (stops working in 2026.8): add the helper config entry to the source device (`async_update_device(add_config_entry_id=...)`) or return its identifiers from `device_info`. Source: [2025-07-18 post](https://contributors.home-assistant.io/blog/2025/07/18/updated-pattern-for-helpers-linking-to-devices).
- **Current pattern:** leave `device_info` unset, and in the constructor set `self.device_entry = async_entity_id_to_device(hass, source_entity_id)` (`homeassistant.helpers.device`). Core honours `entity.device_entry` from 2025.8.0 (derivative PR [#148674](https://github.com/home-assistant/core/pull/148674)). In `entity_platform._async_get_entity_device`, a `None` `device_info` returns `entity.device_entry` ([dev source](https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/entity_platform.py), also in 2026.8.0 and 2026.10.0). The entity registry only checks the device exists, not who owns it.
- **2026.8 ([post](https://contributors.home-assistant.io/blog/2026/07/21/device-registry-single-config-entry)):** a device has exactly one config entry. `async_device_info_to_link_from_entity()` and `async_device_info_to_link_from_device_id()` always return `None` (removed 2027.8). Cleanup is `helper_integration.async_remove_helper_devices(hass, *, helper_config_entry_id, source_device_id, remove_all_devices=False, keep_device_ids=())`. `async_handle_source_entity_changes(add_helper_config_entry_to_device=)` is now a no-op.
- **Constraint** ([follow-up](https://contributors.home-assistant.io/blog/2026/08/24/device-registry-follow-up-changes)): an entity needs a `unique_id` and a config entry to attach a device. Otherwise the link is dropped with a warning, and it raises in 2027.8. So build real config-entry platforms (`number`, `sensor`, `switch`), not YAML or helper-collection entities.
- **Powercalc** (1621 stars, v1.26.1 2026-10-19): [`device_binding.py`](https://github.com/bramstroker/homeassistant-powercalc/blob/HEAD/custom_components/powercalc/device_binding.py) sets `entity.device_entry` for config-entry entities. For YAML entities it calls `entity_reg.async_update_entity(device_id=...)` after adding. [`migrate.py`](https://github.com/bramstroker/homeassistant-powercalc/blob/HEAD/custom_components/powercalc/migrate.py) calls `async_remove_helper_devices`, with `getattr` fallback for older HA.

## 4. Extending Assist

- `intent.async_register(hass, handler)` with an `IntentHandler` (`intent_type`, `platforms`, `description`, `slot_schema`) ([helpers/intent.py](https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/intent.py)).
- **LLM exposure changed in 2026.8.** In 2026.7.0 the Assist API exposed all registered intents except `IGNORE_INTENTS` (checked in the tagged source). In 2026.8.0 the `llm` integration ([#174253](https://github.com/home-assistant/core/blob/dev/homeassistant/components/llm/__init__.py)) replaced that. Per the [LLM API docs](https://contributors.home-assistant.io/core/internals/llm-api/): "Registering an intent does not make it a tool." You ship an `llm.py` platform with `async_get_tools(hass, llm_context, api_id) -> LLMTools | None` returning `IntentTool(f"{DOMAIN}__name", handler, integration=DOMAIN)` (pattern: [intent_script/llm.py](https://github.com/home-assistant/core/blob/dev/homeassistant/components/intent_script/llm.py)).
  - Tool names must carry the `<domain>__` prefix (enforced 2027.3).
  - `integration=` is required (custom integrations get a warning until 2027.10).
  - Tools return `ToolResult` ([2026.10 post](https://contributors.home-assistant.io/blog/2026/09/26/llm-tool-result)).
  - The docs do not restrict this to core. I did not see a custom integration using it: UNVERIFIED in practice.
- **Built-in (non-LLM) agent:** `DefaultAgent._load_intents` ([source](https://github.com/home-assistant/core/blob/dev/homeassistant/components/conversation/default_agent.py)) reads only the `home-assistant-intents` package plus `<config>/custom_sentences/<language>/*.yaml` ([docs](https://www.home-assistant.io/voice_control/custom_sentences_yaml)). I found **no public API** for an integration to register sentence templates. Options:
  - Document that the user copies YAML into `custom_sentences/<lang>/`.
  - Write those files on setup. This is hacky, and I found no precedent.
  - Use sentence triggers via `agent_manager.register_trigger`. This is internal and undocumented, so UNVERIFIED as viable.
- **Multi-language:** sentences are one file set per language and you must author each. LLM agents are language-agnostic. A voice feature would therefore be LLM-first, with default-agent support limited to the languages you translate.

## 5. Persistence

- `async_track_point_in_time`, `async_track_point_in_utc_time` and `async_call_later` are in-memory only. Re-arm them at startup and cancel them via `async_on_remove`.
- `RestoreEntity` dumps every 15 min (`STATE_DUMP_INTERVAL`) and at stop; entries expire after 7 days ([restore_state.py](https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/restore_state.py)). After a crash you can lose up to 15 minutes, so a countdown started just before would be missed. Persist the absolute UTC end time in `helpers.storage.Store` on start and cancel, as both competitors do.
- On startup, wait for HA started and entity availability. If the end time has passed, turn the entity off once. Otherwise re-arm for the remainder.
- Manual-off reset needs `async_track_state_change_event`. Use the `Context` to tell your own turn_off from the user's.
- The core `timer` helper is a poor base: it has no config entry (so no device attach, by the rule in section 3, which is my inference), and `finished` is missed during downtime.

## UNVERIFIED
- Core delayed commands being lost on restart (inferred from source, not run).
- A custom integration's `llm.py` platform being discovered in a live instance.
- Whether any integration writes `custom_sentences` files on setup.
- Non-English delayed-command sentence coverage.

## Spot-checked against installed Home Assistant 2026.10.4

- `helpers/device.py`: `async_entity_id_to_device` exists; `async_device_info_to_link_from_entity` now only calls `report_usage` (deprecated).
- `helpers/entity_platform.py`: an entity with `device_info is None` and a set `device_entry` is linked to that device.
- `components/llm/__init__.py`: tools come from `llm` integration platforms discovered through `LazyIntegrationPlatforms` (the generic mechanism, which also covers custom integrations); `helpers/llm.py` `IntentTool.__init__` takes `integration=`.
- `components/conversation/default_agent.py`: custom sentences are read from `<config>/custom_sentences/<language>/` only.
- `helpers/restore_state.py`: `STATE_DUMP_INTERVAL = timedelta(minutes=15)`.
