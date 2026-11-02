# Timerify 1.1.0 Part C (Automations) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship #38 and #39. In the automation editor a user picks the boiler and finds Timerify's actions "Run", "Add time" and "Stop", and its triggers "Countdown started", "Countdown ended" (by expiry, stop or a manual off, and the trigger says which) and "Pending command came due". This works for every timer: on the target's own device, on the device Timerify made for a target that has none, and on a device with two timers.

**Architecture:** Home Assistant does not ask Timerify for the Device block of a device it does not own (see Decision 1). The editor's **By target** tab does: it lists every action and trigger whose `target` matches an entity of the picked device. So the actions are Timerify's entity services, with a new `timerify.stop`. The triggers are integration triggers (`trigger.py` and `triggers.yaml`, the platform behind Home Assistant's own "Timer started" or "Button pressed") on the Run for entities. They fire on three bus events that the controller sends. The core decides when a countdown starts or ends and why, and which pending command came due. It hands the controller these "announcements" on a channel of their own, apart from the effects it already returns.

**Tech Stack:** Python 3.14, Home Assistant 2026.10.4. Checked in `.venv/lib/python3.14/site-packages/homeassistant` (written `ha/` below) and in the frontend of the `ghcr.io/home-assistant/home-assistant:2026.10.4` image (`hass_frontend` 20260930.5):
- **The Device block.** `ha/components/device_automation/__init__.py:232-294` (`async_get_device_automations`) builds a device's list from two sources: the domain of the config entry that owns the device (:251-261), and the entity domain of each entity on it (:245-247, :262-263). `RegistryEntry.domain` is the domain of the entity id, not the platform (`ha/helpers/entity_registry.py:255`, :288-291). A device belongs to one config entry (`ha/helpers/device_registry.py:404`, :418-437). Timerify puts its entities on the target's device through `Entity.device_entry` without owning it (`custom_components/timerify/entity.py`, `timer_device`). So on the boiler's device the list asks the boiler's integration and `number`, `sensor`, `switch` and `button`, never `timerify`. A `device_action.py` or `device_trigger.py` of Timerify would be asked only for the fallback device, which the timer's entry owns.
- **How core builds device automations, for the record.** On events: `ha/components/shelly/device_trigger.py:147-164` (an `event` trigger with `event_data`). On states: `ha/components/device_automation/toggle_entity.py:149-172` (a `state` trigger). One automation per entity of a device, named by its registry id: `ha/components/number/device_action.py:21-58` (`cv.entity_id_or_uuid`, resolved by `async_validate_entity_schema`, `device_automation/__init__.py:345-358`). Strings: `device_automation.action_type`, `trigger_type` and `extra_fields`, with `{entity_name}` (`ha/components/light/strings.json:84-103`). Capabilities give `extra_fields` (`device_automation/__init__.py:297-330`).
- **By target.** The websocket commands `get_triggers_for_target` and `get_services_for_target` (`ha/components/websocket_api/commands.py:921-985`) resolve the target to entities and match them against the `target` of each trigger and service description: integration and domain filters (`ha/components/websocket_api/automation.py:51-83`), entities with an entity category left out of a device or area target (:117-121), lookup :223-287. A description's `target.entity` is normalised to a list of filters, each `domain` to a list (`ha/helpers/selector.py:173-178`, :2155-2167). The frontend has the tab: `ui.panel.config.automation.editor.tabs.target` = "By target", and calls `device_automation/*/list` only for the Device block. Integration triggers are not behind Labs: the only preview feature of the frontend is `winter_mode` (`ha/components/frontend/manifest.json:23`).
- **Integration triggers.** A platform `trigger` with `async_get_triggers(hass) -> dict[str, type[Trigger]]` is registered for every loaded integration (`ha/helpers/trigger/__init__.py:186-257`). The key `timerify.<name>` loads it (:451-476). `Trigger` (`ha/helpers/trigger/models.py:108-182`) gets a `TriggerConfig(key, target, options)` (:27-33) and implements `async_validate_config` and `async_attach_runner(run_action, did_not_trigger)`. `run_action(payload, description, context)` (:36-50) makes `trigger.<key>` of every payload key (`__init__.py:565-580`). `ENTITY_STATE_TRIGGER_SCHEMA` (`ha/helpers/trigger/entity_trigger.py:99-104`) is a required target and empty options. The descriptions come from `triggers.yaml` (`ha/helpers/trigger/descriptions.py:60-80`, :158-160). Examples: `ha/components/button/trigger.py` with `button/triggers.yaml`, and `ha/components/timer/trigger.py`. Names go under `triggers.<key>.name` and `.description` of the strings (`ha/components/button/strings.json`), icons under `triggers.<key>.trigger` (`ha/components/timer/icons.json`).
- **Targets.** `async_extract_referenced_entity_ids(hass, TargetSelection(config), expand_group, *, primary_entities_only=True)` (`ha/helpers/target.py:68-118`, :196) returns `referenced` and `indirectly_referenced` from the registries as they are now.
- **Services on a missing timer.** An entity service skips an entity that is missing or unavailable. It logs "Referenced entities ... are missing or not currently available" only for an entity named explicitly, and a device or area target with none of them does nothing in silence (`ha/helpers/service.py:700-734`, `ha/helpers/target.py:139-158`).
- **Start-up.** An automation arms its triggers before `EVENT_HOMEASSISTANT_STARTED` (`ha/components/automation/__init__.py:847-866`). Timerify takes stock of the target at that event (`async_at_started`, `ha/helpers/start.py:75-90`, `controller.py` `_handle_started`). So what start-up folds is announced to armed automations.

**Spec:** `docs/superpowers/specs/2026-11-01-release-1.1.0-design.md`, section "Part C", with "Non-goals" and "Constraints". It extends the base spec `docs/superpowers/specs/2026-10-28-timerify-design.md` and `RULINGS.md`. Issues: `gh issue view 38`, `gh issue view 39`. The base spec's rules hold: one timer is the single source of truth; manual wins; R2, an explicit 0 or stop turns the target off, in both modes.

**Starting point:** `main` at 5d3f82e, the merge of part B (PR #45): 2183 pytest tests collected.

## Global Constraints

- Home Assistant `>= 2026.10.4` (`hacs.json`), Python `>= 3.14.2`, `pytest-homeassistant-custom-component==0.13.375`. No new runtime or dev dependency, and no change to `manifest.json`.
- Only public Home Assistant APIs, checked in `.venv` before use. mypy is strict, and schemas use `probatio`. No `device_action.py` or `device_trigger.py` (Decision 1).
- Tests are user scenarios with frozen time (`freezer`, `advance`, `advance_to`, `restart_after`). No `asyncio.sleep`, no polling and no backdoors. Product code gets no test-only branch. An existing test is edited only where a task names it.
- A test name fits the 88 columns of `async def <name>(`, so 77 characters at most.
- User-facing strings go in `translations/en.json` (the source) and `translations/ru.json`, with the same keys and the same `{blanks}` (`tests/test_translations.py`). Cyrillic is allowed only in `ru.json` and `docs/ru/`; this plan has none. The implementer writes the Russian strings and pages as translations of the English ones. Russian Home Assistant screen names come from `python3 .superpowers/ui-names/ui-term.py "<English name>"`: at least "By target", "Add trigger", "Add action", "Automations & scenes", "Create automation", "Device", "Entity", "Targets", "When", "Then do" and "Perform action". A name the script says has no frontend string stays English. Pending commands keep the product's Russian term from `ru.json`, and "countdown" the word `ru.json` already uses for it.
- After every change to `en.json`, run `npm --prefix card run build` and commit `custom_components/timerify/frontend/timerify-card.js` with the task. Then `npm --prefix card run build:check` must pass.
- A user-visible change updates `docs/en/<page>.md` and `docs/ru/<page>.md` in the same commit, with the same `##` and `###` headings (`tests/test_docs.py`) and the CLAUDE.md "User documentation" style: short sentences, "you", no long dashes, no rule ids, no internal words. Name what the editor shows as it shows it. READMEs link with absolute URLs.
- Every task ends with these passing: `uv run pytest`, `uv run ruff check`, `uv run ruff format --check` and `uv run mypy`. A task that changes `translations/`, `services.yaml`, `icons.json` or adds a platform or `triggers.yaml` also runs hassfest: `docker run --rm --platform linux/amd64 -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest`. If hassfest refuses a `triggers` section or file of a custom integration, stop and report it: no workaround.
- English only. Commit messages are a plain sentence-case subject, with no attribution lines. Never use `--no-verify`. `git add` only the files of the task.
- RULINGS: Task 1 adds a subsection `### Automations` under `## Release 1.1.0`, after `### Forms and entities`. Later tasks append their bullets to it, in the existing style: a bold decision, then "Why:", then "Cost if wrong:", then the tests that pin it.
- Docker: start, stop or remove only the containers a task names. Other projects' containers run on this machine.
- Nothing is opened, commented or labelled in any `home-assistant/*` repository.
- The PR body names "Closes #38. Closes #39." (one keyword per issue: GitHub closes only the first number of "Closes #38, #39").

## Review Focus

1. **A device with two timers** (a two-channel relay, a timer on each switch). A trigger aimed at the device fires for each channel and names the one it fired for. A Stop aimed at one channel's **Run for** leaves the other channel running. Tests: Task 3, `test_a_relay_trigger_names_the_channel_whose_countdown_ended`; Task 1, `test_stop_aimed_at_one_channel_leaves_the_other_running`.
2. **Home Assistant restarts.** A countdown that ended while it was down triggers "Countdown ended" once at start-up, with the reason `expired`. A countdown that still runs triggers nothing again. Tests: Task 3, `test_a_countdown_that_ended_while_down_triggers_once_at_start_up`; Task 2, `test_a_countdown_restored_at_start_up_is_not_announced_again`.
3. **A running countdown is changed.** Moving Run for, Add time, a Run with minutes, a pending "on" and a window that ends later all keep one countdown going. They announce neither a start nor an end, so a "started" notification is not sent again. The pending "on" still announces that it came due. Tests: Task 2, `test_changing_a_running_countdown_announces_nothing` (core) and `test_moving_run_for_while_it_runs_fires_no_event` (controller).
4. **The timer an automation names is deleted.** Its trigger stays valid, never fires and logs no error. A Stop aimed at its Run for does nothing, and the automation goes on to its next step. Tests: Task 3, `test_a_trigger_of_a_deleted_timer_never_fires`; Task 1, `test_stop_aimed_at_a_deleted_timer_lets_the_automation_go_on`.
5. **A timer is added to a device after the automation was saved.** A trigger aimed at the device covers it without an edit, because the target is resolved at each event. Test: Task 3, `test_a_timer_added_later_is_covered_by_the_device_trigger`.

## Decisions

1. **Timerify's automations are offered by target, not in the Device block.** The Device block of the boiler's device never asks Timerify (Tech Stack, "The Device block"). A `device_action`/`device_trigger` platform would reach only timers on the device Timerify made, a minority, and give those timers a second, different way. The **By target** tab of the same editor dialogs lists Timerify's actions and triggers for any device that carries a timer. So the plan builds no device automation platform. This changes the wording of the spec ("in the Device block ... on the target's device (or the fallback device)") to keep its goal ("pick the boiler and choose ..."). **Confirmed by the owner on 2026-11-02: By target only.** No Device block, also not for the device Timerify made.
2. **How an action or trigger names its timer.** By Home Assistant's target, not by a field of ours. A device target means every timer on the device. The **Run for** entity means that one timer, and an area or a label means the timers in it. Triggers accept only Timerify's Run for entities (`target.entity: [{integration: timerify, domain: [number]}]`), as the services already do. The payload names the timer: `trigger.entity_id` is its Run for. In the editor, **By target** with the boiler picked lists the actions and the three triggers, with their names and descriptions. Choosing one fills its target with the device, and Home Assistant's target picker narrows it to one Run for. A device with two timers shows each action and trigger once. The docs tell the user to pick the Run for of one channel to aim at it.
3. **The actions are the services.** "Run" is `timerify.run`: minutes optional, 1 to 1440. "Add time" is `timerify.add_time`: minutes required, from -1440 to 1440. Neither is bounded by the slider's maximum (part B ruling). "Stop" is a new `timerify.stop` with no fields, which calls `async_set_minutes(0)`: the path of Run for 0, the Turn off button and voice. A timer that is deleted, or whose Run for is unavailable, is skipped by Home Assistant. It logs its "missing or not currently available" warning when the Run for was named explicitly, and nothing for a device target. A timer unloaded while the call waits for its turn fails with `timer_unloaded`, as every service does now.
4. **"Countdown ended" comes from the core, with a reason the trigger passes on as `trigger.reason`.** `expired`: the end was reached, by the alarm, a fold after a restart or a report of the target. A schedule window whose end is the timer's end counts too. `stopped`: Timerify ended it. That covers Run for 0, Stop, the Turn off button, voice, the LLM tools, Add time down to zero, a pending "off", and a window taken away by switching or editing its interval. `turned_off`: the target was switched off outside Timerify (`observe` with `by_us=False`, `_follow_external_change`). That means by hand, by its app, by another automation or by the device itself. Telling them apart is cheap: the core already takes a different path for each.
5. **"Pending command came due" is announced when the core carries a command out.** That is `_run_command` after its drop check. A command dropped because its run was already over (`CommandDropped`) is not announced: it did nothing, and the log says so. The payload has `command_id` (as in the response of `add_command`) and `action` (`on` or `off`). It comes before the start or end of the countdown that the command causes.
6. **Events, not entity states.** No entity state shows that a command came due: the Next command sensor also changes when a command is added or cancelled. A state of Run for or Ends at cannot tell why a countdown ended. A state written at a restart looks like a change. The core's decision point is exact, and the new trigger platform listens to anything. So the controller fires `timerify_countdown_started`, `timerify_countdown_ended` and `timerify_command_due` on the bus, documented for YAML users too. The triggers listen to them.
7. **"Countdown started" means a timer with no countdown begins one.** In the core, the end goes from none to a moment. That covers Run, Add time on an idle timer, Run for, a strict-mode manual on, a pending "on" and a window that opens on an idle timer. A loose run without a countdown starts none. A change of a running countdown starts none (Review Focus 3).

---

## File Structure

```
custom_components/timerify/
  services.py      SERVICE_STOP, registered (T1)
  services.yaml    stop (T1)
  number.py        RunForNumber.async_stop (T1)
  core.py          EndReason, CountdownStarted, CountdownEnded, CommandCameDue, Announcement,
                   TimerCore.take_announcements and the places that record them (T2)
  const.py         EVENT_COUNTDOWN_STARTED, EVENT_COUNTDOWN_ENDED, EVENT_COMMAND_DUE (T2)
  controller.py    fires the announcements as events in _execute (T2)
  trigger.py       new: the three integration triggers (T3)
  triggers.yaml    new: their targets (T3)
  icons.json       services.stop (T1); triggers (T3)
  translations/en.json, ru.json   services.stop (T1); triggers (T3)
  frontend/timerify-card.js        rebuilt after each en.json change (T1, T3)
tests/
  conftest.py      provide_target(device_id=), fake_relay (T1)
  helpers.py       run_for_of, add_automation, record_action (T1)
  test_services.py (T1), test_automation_actions.py new (T1)
  test_core.py (T2), test_events.py new (T2)
  test_automation_triggers.py new (T3)
docs/en, docs/ru: automations.md new (T1, T3); services.md (T1, T2); README.md (T1)
README.md, README.ru.md (T1); RULINGS.md (T1 to T3)
```

---

### Task 1: The Stop action, and Timerify's actions by target (#38)

**Files:**
- Modify:
  - `custom_components/timerify/services.py`: `SERVICE_STOP` next to the others, and a fifth registration in `async_setup_services`.
  - `custom_components/timerify/services.yaml`: `stop`.
  - `custom_components/timerify/number.py`: `RunForNumber`.
  - `custom_components/timerify/icons.json`: `services.stop`.
  - `translations/en.json` and `ru.json`: `services.stop`.
  - `tests/conftest.py`: `provide_fake` and `provide_target` gain `device_id`; a new fixture `fake_relay`.
  - `tests/helpers.py`: `run_for_of`, `add_automation`, `record_action`.
  - `tests/test_services.py`: `test_services_are_described_for_the_ui` (`:401`) gains the asserts on `stop`.
  - `docs/en/services.md`, `docs/ru/services.md`, `docs/en/README.md`, `docs/ru/README.md`, `README.md`, `README.ru.md`, `RULINGS.md`.
- Create: `docs/en/automations.md`, `docs/ru/automations.md`, `tests/test_automation_actions.py`.

**Interfaces:**
- Consumes: `TargetController.async_set_minutes(0)` (`controller.py:348`). `service.async_register_platform_entity_service` as `services.py:131-170` uses it.
- Produces:
  - `services.py`: `SERVICE_STOP = "stop"`, registered with `entity_domain=NUMBER_DOMAIN`, `schema={}`, `func="async_stop"`.
  - `number.py`: `RunForNumber.async_stop(self) -> None` awaits `self._controller.async_set_minutes(0)`.
  - `services.yaml`: `stop:` with the same `target` as `run` and no `fields`.
  - `icons.json`: `services.stop.service` = `"mdi:timer-stop-outline"`.
  - `en.json`, `services.stop`:
    - `name`: "Stop".
    - `description`: "Ends the countdown of a timer and turns the entity off, as setting Run for to 0 does. It also turns off an entity that runs without a countdown in loose mode. An entity that is off is left as it is."
  - `tests/conftest.py`:
    - `provide_fake(..., device_id: str | None = None)` and the `provide` of `provide_target` pass it on. With a `device_id`, the registry entry goes on that device and no device is made.
    - Fixture `fake_relay(provide_target) -> tuple[FakeTarget, FakeTarget]` gives `switch.relay_1` on a new device called Relay, and `switch.relay_2` on the same device. Both are switched off, at `START`, with `SWITCH_SERVICES`.
  - `tests/helpers.py`:
    - `run_for_of(hass: HomeAssistant, entry: ConfigEntry) -> str` is the entity id of the entry's Run for, from the registry (`timer_unique_id(entry.entry_id, KEY_RUN_FOR)`).
    - `async add_automation(hass: HomeAssistant, trigger: dict[str, Any], actions: list[dict[str, Any]]) -> None` sets up `automation` with one automation, then blocks till done.
    - `record_action(fields: Sequence[str]) -> dict[str, Any]` is `{"action": "test.record", "data": {f: "{{ trigger.<f> }}"}}` for each field. A test gets the calls from `async_mock_service(hass, "test", "record")`.

- [ ] **Step 1: Write the failing tests.** In `tests/test_services.py`:

```python
async def test_stop_ends_the_countdown_and_turns_the_boiler_off(...)
    # setup_target(); set_number(NUMBER, 45); call_service(hass, "stop", {"entity_id": NUMBER}):
    # fake_target.calls == [TURN_ON, TURN_OFF]; state_of(NUMBER) == "0"; state_of(SENSOR) == "unknown"

async def test_stop_turns_off_a_loose_boiler_without_a_countdown(...)
    # setup_target(mode="loose"); fake_target.set_state("on"); stop: calls == [TURN_OFF]

async def test_stop_leaves_a_boiler_that_is_off_alone(...)
    # stop: fake_target.calls == []; state_of(TARGET_ID) == "off"
```

  In `test_services_are_described_for_the_ui`: `descriptions["stop"]["target"] == target` and `descriptions["stop"].get("fields", {}) == {}`.

  In `tests/test_automation_actions.py`, with `websocket_api` set up for `hass_ws_client`. Ask with `{"type": "get_services_for_target", "target": {"device_id": [<device id>]}}` and read the result as a set:

```python
TIMERIFY_ACTIONS = {"timerify.run", "timerify.add_time", "timerify.stop",
                    "timerify.add_command", "timerify.cancel_command"}

async def test_the_boilers_device_offers_timerifys_actions_by_target(...)
    # setup_target(); result for fake_target.device_id >= TIMERIFY_ACTIONS

async def test_a_device_without_a_timer_offers_no_timerify_action(...)
    # provide_target("switch.kettle", SWITCH_SERVICES, name="Kettle"), no timer on it:
    # no item of its result starts with "timerify."

@pytest.mark.parametrize("fake_target", [False], indirect=True)
async def test_the_device_made_for_a_switch_offers_them_too(...)
    # the device of NUMBER (entity registry): result >= TIMERIFY_ACTIONS

async def test_an_automation_runs_the_boiler_for_20_minutes_by_its_device(...)
    # add_automation(hass, {"trigger": "event", "event_type": "timerify_test_go"},
    #   [{"action": "timerify.run", "target": {"device_id": fake_target.device_id}, "data": {"minutes": 20}}]);
    # fire the event; block: calls == [TURN_ON]; state_of(SENSOR) == "2026-01-05T07:20:00+00:00"

async def test_add_time_and_stop_by_the_device_reach_the_boiler(...)
    # automation: run 20, add_time 10 (SENSOR "07:30"), then stop, all by the device:
    # calls == [TURN_ON, TURN_OFF]; state_of(NUMBER) == "0"

async def test_stop_aimed_at_one_channel_leaves_the_other_running(...)   # Review Focus 1
    # relay_1, relay_2 = fake_relay; one = await setup_target(target="switch.relay_1");
    # two = await setup_target(target="switch.relay_2"); set_number on both Run for (run_for_of) to 30;
    # an automation: stop with target {"entity_id": run_for_of(hass, one)}; fire:
    # relay_1.calls == [("turn_on", "switch.relay_1"), ("turn_off", "switch.relay_1")];
    # relay_2.calls == [("turn_on", "switch.relay_2")]; state_of(hass, run_for_of(hass, two)) == "30"

async def test_stop_aimed_at_a_deleted_timer_lets_the_automation_go_on(...)   # Review Focus 4
    # entry = setup_target(); await hass.config_entries.async_remove(entry.entry_id);
    # automation: [stop with target {"entity_id": NUMBER}, record_action(["platform"])]; fire:
    # len(records) == 1; fake_target.calls == [];
    # "Referenced entities number.boiler_run_for are missing or not currently available" in caplog.text
```

- [ ] **Step 2: Run** `uv run pytest tests/test_services.py tests/test_automation_actions.py -v`. Expected: the new tests FAIL (`stop` is not a service). The by-target tests of `run` and `add_time` may PASS already for those two names: they pin what Home Assistant offers, and they stay.
- [ ] **Step 3: Implement** the interfaces above, with the Russian strings in `ru.json`.
- [ ] **Step 4: Docs** (en and ru):
  - New `automations.md`, titled "Automations". Its headings are `## Pick the device`, `## Actions` and `## A device with two timers`. Task 3 adds the triggers.
    - Intro: you can use Timerify in an automation without typing YAML. You pick the device, then a Timerify action.
    - "Pick the device": open **Settings > Automations & scenes**, then **Create automation**. Choose **Add action**, then the **By target** tab. Pick the device, for example the boiler. The list shows Timerify's actions with the device's other ones. A device that Timerify made for an entity that is on no device works the same.
    - Also in that section: the **Device** block lists only what the device's own integration offers, and actions of its kinds of entities, such as setting the value of **Run for**. Home Assistant builds that list itself, so Timerify's actions are under **By target** instead.
    - "Actions": a table of **Run** ("Turns the device on, for the minutes you give, up to a day"), **Add time** ("Moves the end of the countdown, up to a day either way") and **Stop** ("Ends the countdown and turns the device off. It also turns off a device that runs without a countdown"). Then a line that **Add command** and **Cancel command** are there too, and a link to [Actions](services.md) for every field. Example: to run the boiler for 20 minutes, pick **Run** and set **Minutes** to 20.
    - "A device with two timers": for example, a relay with two channels, each with its own timer. An action aimed at the device acts on both timers. To aim at one, change the target to that channel's **Run for** entity.
  - `services.md`: "four actions" becomes "five". The table gains `timerify.stop` | **Stop** | "Ends the countdown and turns the device off." A new `## Stop` section, after `## Run`, has the description above, says it has no fields, and says it is the same as setting **Run for** to 0 or pressing **Turn off**.
  - `docs/<lang>/README.md`: under "How to use Timerify", a bullet "[Automations](automations.md): run, extend and stop a timer from an automation." The Actions bullet says five actions.
  - `README.md` and `README.ru.md`: the same Automations bullet with an absolute link (`https://github.com/klimofey/timerify/blob/main/docs/<lang>/automations.md`), and "five actions" wherever the actions are counted.
- [ ] **Step 5: RULINGS.** Add the subsection `### Automations`, and in it:
  - **"Timerify's actions and triggers are offered by target, not in the Device block."** It covers these decisions:
    - The Device block of a device asks the integration that owns it and the domains of its entities. Give the file:line of Tech Stack, "The Device block". Timerify owns only the device it made for a target on none.
    - The editor's **By target** tab matches the `target` of services and triggers against the entities of the picked device. Give `websocket_api/automation.py:51-83`, :117-121 and the frontend string.
    - So there is no `device_action` or `device_trigger` platform: one way for every timer, wherever its entities are.
    - The owner accepted this at plan review (#38, #39).

    Why: the owner's wish is to pick the boiler and choose an action or trigger; the Device block cannot offer that for a device another integration owns. Cost if wrong: a user who looks only in the Device block finds the number's and the button's actions there and not Timerify's; the docs send them to **By target**. Tests: `test_the_boilers_device_offers_timerifys_actions_by_target`, `test_the_device_made_for_a_switch_offers_them_too`.
  - **"Stop is a service of its own, `timerify.stop`, the stop of Run for 0."** It calls `async_set_minutes(0)`, as the Turn off button and voice do. So it ends a countdown, turns off a loose device without one, holds a started window until its next occurrence (S4), and sends nothing to a device that is off. It has no fields. A target names its timers, as for every service. Why: #38 asks for Stop beside Run and Add time; `number.set_value` 0 is not one of Timerify's actions, and the button is optional. Cost if wrong: none known. Tests: the three `test_stop_*` tests of `tests/test_services.py` and the two of `tests/test_automation_actions.py`.
- [ ] **Step 6: Run** the gate, hassfest, `npm --prefix card run build` and `npm --prefix card run build:check`. Expected: all pass.
- [ ] **Step 7: Commit.**

```bash
git add custom_components/timerify/services.py custom_components/timerify/services.yaml custom_components/timerify/number.py custom_components/timerify/icons.json custom_components/timerify/translations/en.json custom_components/timerify/translations/ru.json custom_components/timerify/frontend/timerify-card.js tests/conftest.py tests/helpers.py tests/test_services.py tests/test_automation_actions.py docs/en/automations.md docs/ru/automations.md docs/en/services.md docs/ru/services.md docs/en/README.md docs/ru/README.md README.md README.ru.md RULINGS.md
git commit -m "Add the Stop action and offer Timerify's actions for a device by target"
```

### Task 2: The core announces countdowns and due commands, and the controller fires them as events

**Files:**
- Modify:
  - `custom_components/timerify/core.py`: the effect types (`:98-156`), `TimerCore.__init__` (`:301-346`), `set_duration` (`:364`), `add` (`:379-395`), `run_open` (`:403-423`), `_catch_up` (the `"end"` case, `:674-676`), `_run_command` (`:770-793`), `_follow_external_change` (`:804-820`), `_end_timer` (`:841-845`), `_set_end` (`:856-879`) and `_clear_end` (`:889-891`).
  - `custom_components/timerify/const.py`.
  - `custom_components/timerify/controller.py`: `_execute` (`:1199-1247`).
  - `docs/en/services.md`, `docs/ru/services.md`, `RULINGS.md`.
- Test: `tests/test_core.py`, and a new `tests/test_events.py`.

**Interfaces:**
- Consumes: `Command` (`core.py:25-37`), `timer_unique_id` and `KEY_RUN_FOR` (`const.py`).
- Produces:
  - `core.py`:
    - `type EndReason = Literal["expired", "stopped", "turned_off"]`.
    - `@dataclass(frozen=True) class CountdownStarted: end: datetime`: a countdown began where none ran, to end at `end`.
    - `@dataclass(frozen=True) class CountdownEnded: reason: EndReason`.
    - `@dataclass(frozen=True) class CommandCameDue: command: Command`: the command was carried out at its time.
    - `type Announcement = CountdownStarted | CountdownEnded | CommandCameDue`.
    - `TimerCore.take_announcements(self) -> list[Announcement]` returns what happened since the last call, in the order it happened, and forgets it. Announcements are not `Effect`s. The lists that the steps return do not change, so the existing exact-list asserts of `tests/test_core.py` stay as they are.
    - The recording rules:
      - `_set_end` is the only writer of the end, and the only place that records a start or an end. Going from no end to an end records `CountdownStarted(end)`. Going from an end to none records `CountdownEnded(ended_by)`, where `ended_by: EndReason = "stopped"` is a new keyword of `_set_end`, `_end_timer` and `_clear_end`. A move of the end records nothing.
      - `"expired"` is passed by the `"end"` item of `_catch_up`.
      - `"turned_off"` is passed by `_follow_external_change` for an "off".
      - Every other clear is `"stopped"` by default.
      - `set_duration`, `add` (only where it starts a countdown) and `run_open` treat an end that is not ahead of `now` as no countdown (#42). Before they write a new end, they clear that one with `ended_by="expired"`. Their snapshot ends as it does now, and they announce the end before the new start. `add` with a delta of zero or less leaves that end for the tick to fold, as it does now, because the tick turns the target off.
      - `_run_command` records `CommandCameDue(command)` once it knows the command is not dropped, before it writes the end. So the command comes before the start or end it causes.
  - `const.py`:
    - `EVENT_COUNTDOWN_STARTED: Final = "timerify_countdown_started"`, with data `{"entity_id": <Run for>, "ends_at": <the end, ISO 8601 in UTC>}`.
    - `EVENT_COUNTDOWN_ENDED: Final = "timerify_countdown_ended"`, with data `{"entity_id": ..., "reason": "expired" | "stopped" | "turned_off"}`.
    - `EVENT_COMMAND_DUE: Final = "timerify_command_due"`, with data `{"entity_id": ..., "command_id": <id>, "action": "on" | "off"}`.
  - `controller.py`:
    - `_execute` takes `self._core.take_announcements()` after the snapshot is saved and the entities are refreshed, and before any call to the target. If the controller is not stopped, it calls `self._announce(announcements)`. So an automation sees the new Ends at and Run for, and a slow device does not delay it.
    - `TargetController._announce(self, announcements: Sequence[Announcement]) -> None` fires one event per announcement with `self._hass.bus.async_fire`. The `entity_id` is looked up at that time: `er.async_get(hass).async_get_entity_id("number", DOMAIN, timer_unique_id(entry_id, KEY_RUN_FOR))`, so a renamed Run for is named by its new id. `ends_at` is `end.isoformat()`, the form of the Ends at state.

- [ ] **Step 1: Write the failing tests.** In `tests/test_core.py`, with `news = c.take_announcements()` after the step:

```python
def test_a_countdown_from_idle_is_announced_as_started()
    # core("strict", "off").set_duration(NOW, minutes(30)): news == [CountdownStarted(NOW + minutes(30))]; a second take is []

def test_changing_a_running_countdown_announces_nothing()   # Review Focus 3
    # running 30 (taken); then set_duration(NOW+5, 60), add(+10), add(-5), run_open, and
    # a window that opens at +15 and ends after the countdown (set_windows, tick): every take == [];
    # a pending "on" for 20 at +10 (tick): the take == [CommandCameDue(that command)] only

def test_the_end_of_a_countdown_is_announced_as_expired()
    # running 30; tick(NOW + minutes(30)): news == [CountdownEnded("expired")]

def test_the_end_of_a_window_that_carries_the_timer_is_expired()
    # a window +0..+30 opens on an idle timer: [CountdownStarted(NOW+30)]; tick at +30: [CountdownEnded("expired")]

@pytest.mark.parametrize("stop", ["zero", "stop", "add_past_the_end", "pending_off"])
def test_ending_a_countdown_by_timerify_is_announced_as_stopped(stop)
    # running 30; Run for 0 / stop() / add(-40) / a pending "off" due at +10 (tick):
    # the last announcement is CountdownEnded("stopped")

def test_disabling_the_interval_of_an_open_window_announces_a_stop()
    # the window carries the timer; set_interval_enabled(off) then tick: [CountdownEnded("stopped")]

def test_a_manual_off_is_announced_as_turned_off()
    # running 30, target on; observe(NOW+5, "off", by_us=False): [CountdownEnded("turned_off")]

def test_a_report_after_the_end_is_announced_as_expired()
    # running 30; observe(NOW+31, "off", by_us=False): [CountdownEnded("expired")]

def test_a_pending_off_announces_the_command_then_the_stop()
    # [CommandCameDue(the command), CountdownEnded("stopped")], in that order

def test_a_pending_on_on_an_idle_timer_announces_the_command_then_the_start()
    # cmd(10, "on", minutes=20); tick at +10: [CommandCameDue(...), CountdownStarted(NOW + minutes(30))]

def test_a_dropped_command_is_not_announced_as_due()
    # a command whose run was over before it was folded: CommandDropped among the effects, news == []

@pytest.mark.parametrize(("mode", "news"), [("strict", [CountdownStarted(NOW + minutes(45))]), ("loose", [])])
def test_a_manual_on_announces_a_start_in_strict_mode_only(mode, news)

def test_a_run_given_after_the_end_passed_announces_the_end_first()
    # end at NOW - 1 min, not folded (#42); add(NOW, minutes(10)): [CountdownEnded("expired"), CountdownStarted(NOW + minutes(10))];
    # the snapshot is the one the step gives today

def test_a_catch_up_that_ends_and_starts_announces_both_in_order()
    # stored end NOW-60 and cmd(-10, "on", minutes=30); observe(NOW, "on", by_us=False):
    # [CountdownEnded("expired"), CommandCameDue(...), CountdownStarted(NOW + minutes(20))]
```

  In `tests/test_events.py`, with `async_capture_events(hass, EVENT_...)` and `[e.data for e in events]`:

```python
async def test_running_the_boiler_fires_countdown_started_with_its_end(...)
    # set_number(NUMBER, 30): started == [{"entity_id": NUMBER, "ends_at": "2026-01-05T07:30:00+00:00"}]

async def test_the_end_of_the_countdown_fires_countdown_ended_expired(...)
    # advance 30 min: ended == [{"entity_id": NUMBER, "reason": "expired"}]; fake_target.calls == [TURN_ON, TURN_OFF]

@pytest.mark.parametrize("how", ["run_for_zero", "stop", "turn_off_button", "pending_off"])
async def test_stopping_the_countdown_fires_ended_stopped(how)
    # ended == [{"entity_id": NUMBER, "reason": "stopped"}]

async def test_turning_the_boiler_off_by_hand_fires_ended_turned_off(...)
    # fake_target.set_state("off") while it runs: [{"entity_id": NUMBER, "reason": "turned_off"}]

async def test_a_pending_command_fires_command_due_with_its_id(...)
    # response = add_command(hass, NUMBER, action="on", delay=10, minutes=20); advance 10 min:
    # due == [{"entity_id": NUMBER, "command_id": response[NUMBER]["command_id"], "action": "on"}]; one countdown_started

async def test_moving_run_for_while_it_runs_fires_no_event(...)   # Review Focus 3
    # set_number 30 (one started), set_number 60, add_time 10, run with minutes 20: started and ended unchanged

async def test_a_countdown_restored_at_start_up_is_not_announced_again(...)   # Review Focus 2
    # set_number 30; restart_after(..., minutes=5): no started and no ended event after the restart

async def test_a_countdown_that_ended_while_down_fires_ended_at_start_up(...)
    # set_number 30; restart_after(..., minutes=60): ended == [{"entity_id": NUMBER, "reason": "expired"}]; TURN_OFF follows

async def test_a_countdown_that_ends_while_the_boiler_is_unavailable_fires(...)
    # fake_target.set_available(False); advance past the end: ended == [{... "reason": "expired"}]; no call until it is back

async def test_the_event_names_the_run_for_by_its_new_id(...)
    # er.async_get(hass).async_update_entity(NUMBER, new_entity_id="number.boiler_minutes"); set_number on it:
    # started[0]["entity_id"] == "number.boiler_minutes"
```

- [ ] **Step 2: Run** `uv run pytest tests/test_core.py tests/test_events.py -v`. Expected: the new tests FAIL; the existing tests of `tests/test_core.py` PASS.
- [ ] **Step 3: Implement** the interfaces above. Check that no step decorated with `_reports_change` calls another one, so each announcement is taken once.
- [ ] **Step 4: Docs** (en and ru), `services.md`: a new `## Events` section, before `## What you can read from a timer`.
  - Timerify fires three events. The [triggers](automations.md) are built on them, and a YAML `event` trigger can use them too.
  - A table: `timerify_countdown_started` (data `entity_id`, `ends_at`), `timerify_countdown_ended` (`entity_id`, `reason`), `timerify_command_due` (`entity_id`, `command_id`, `action`). `entity_id` is the timer's **Run for**.
  - The three reasons, in plain words: `expired` (the countdown ran out), `stopped` (Timerify stopped it: Run for 0, Stop, the Turn off button, voice, a pending "off", Add time down to zero, or a schedule interval switched off while its window ran), `turned_off` (the device was switched off outside Timerify).
  - A change of a running countdown fires nothing. A countdown that ended while Home Assistant was down fires its event once it has started.
- [ ] **Step 5: RULINGS.** Add **"Countdowns and due commands are announced by the core and fired as Timerify's own events."** It covers decisions 4 to 7, and:
  - The announcements are a channel of their own (`take_announcements`), not effects: they switch nothing, and the steps' effect lists stay as they were.
  - They are fired after the save and before the calls to the target.
  - A start-up fold announces what it folds, and armed automations get it (Tech Stack, "Start-up"). A command given while Home Assistant is still starting folds its catch-up before automations are armed, so its announcements can reach none. That is Home Assistant's rule that automations do not fire during start-up.

  Why: #39. Cost if wrong: a user who wants an event when a countdown is changed has none; an automation that turns the boiler on again when its countdown ends would loop through `stopped` too, so it must check `trigger.reason`. The docs show that. Tests: the tests of this task.
- [ ] **Step 6: Run** the gate. Expected: all pass. No string changes, so no rebuild and no hassfest.
- [ ] **Step 7: Commit.**

```bash
git add custom_components/timerify/core.py custom_components/timerify/const.py custom_components/timerify/controller.py tests/test_core.py tests/test_events.py docs/en/services.md docs/ru/services.md RULINGS.md
git commit -m "Announce started and ended countdowns and due commands as Timerify events"
```

### Task 3: The three triggers (#39)

**Files:**
- Create: `custom_components/timerify/trigger.py`, `custom_components/timerify/triggers.yaml`, `tests/test_automation_triggers.py`.
- Modify:
  - `custom_components/timerify/icons.json`: `triggers`.
  - `translations/en.json` and `ru.json`: `triggers`.
  - `docs/en/automations.md`, `docs/ru/automations.md`, `docs/en/README.md`, `docs/ru/README.md`, `README.md`, `README.ru.md`, `RULINGS.md`.

**Interfaces:**
- Consumes: the three events of Task 2 and their data. `add_automation`, `record_action`, `run_for_of` and `fake_relay` of Task 1.
- Produces:
  - `trigger.py`:
    - `class TimerEventTrigger(Trigger)` has the class variables `_event_type: ClassVar[str]` and `_what: ClassVar[str]` ("countdown started", "countdown ended", "pending command came due").
    - `async_validate_config(cls, hass, config) -> ConfigType` returns `ENTITY_STATE_TRIGGER_SCHEMA(config)`.
    - `__init__` keeps `TargetSelection(config.target)`.
    - `async_attach_runner(run_action, did_not_trigger=None) -> CALLBACK_TYPE` returns `hass.bus.async_listen(self._event_type, handler)`. For each event, the `@callback` handler resolves the target as it is then: `async_extract_referenced_entity_ids(hass, selection, expand_group=False)`. If `referenced | indirectly_referenced` holds `event.data["entity_id"]`, it calls `run_action(dict(event.data), f"{self._what} of {entity_id}", event.context)`. The target is resolved per event, never cached: events come a few times a day, and registry changes need no tracking.
    - `CountdownStartedTrigger`, `CountdownEndedTrigger` and `CommandDueTrigger` set the two class variables.
    - `TRIGGERS: dict[str, type[Trigger]] = {"countdown_started": ..., "countdown_ended": ..., "command_due": ...}`, and `async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]` returns it.
  - `triggers.yaml`: each of the three keys has `target: {entity: [{integration: timerify, domain: [number]}]}` (one YAML anchor), written in the normalised form so that the description equals it, and no `fields`.
  - `icons.json`, `triggers.<key>.trigger`: `countdown_started` `"mdi:timer-play-outline"`, `countdown_ended` `"mdi:timer-off-outline"`, `command_due` `"mdi:calendar-clock"`.
  - `en.json`, `triggers`:
    - `countdown_started`:
      - `name`: "Countdown started".
      - `description`: "Triggers when a timer that was not counting down starts a countdown: by an action, by hand in strict mode, by a pending command or by a schedule window. A change of a countdown that is already running does not trigger it."
    - `countdown_ended`:
      - `name`: "Countdown ended".
      - `description`: "Triggers when the countdown of a timer ends. Its reason says how: expired when it ran out, stopped when Timerify stopped it, turned_off when the entity was switched off outside Timerify."
    - `command_due`:
      - `name`: "Pending command came due".
      - `description`: "Triggers when a pending command of a timer comes due and is carried out. It gives the id of the command and whether it turns the entity on or off."
  - Trigger variables: `trigger.entity_id` always. Then `trigger.ends_at` for a start, `trigger.reason` for an end, and `trigger.command_id` and `trigger.action` for a command. `trigger.platform` is the trigger's key, such as `timerify.countdown_ended`.

- [ ] **Step 1: Write the failing tests** in `tests/test_automation_triggers.py`. A trigger is `{"trigger": "timerify.<key>", "target": {...}}`, and the action is `record_action([...])`:

```python
TIMERIFY_TRIGGERS = {"timerify.countdown_started", "timerify.countdown_ended", "timerify.command_due"}

async def test_the_triggers_are_described_for_the_editor(...)
    # helpers.trigger.async_get_all_descriptions(hass): for each key of TIMERIFY_TRIGGERS,
    # description["target"] == {"entity": [{"integration": DOMAIN, "domain": ["number"]}]} and description["fields"] == {}

async def test_the_boilers_device_offers_the_three_triggers_by_target(...)
    # automation set up; ws get_triggers_for_target for fake_target.device_id: result >= TIMERIFY_TRIGGERS;
    # a device without a timer (switch.kettle): none of them

@pytest.mark.parametrize("fake_target", [False], indirect=True)
async def test_the_device_made_for_a_switch_offers_the_triggers_too(...)

async def test_countdown_started_gives_the_automation_its_end(...)
    # trigger countdown_started, target the boiler's device; set_number(NUMBER, 30):
    # records[0].data == {"entity_id": NUMBER, "ends_at": "2026-01-05T07:30:00+00:00"}

@pytest.mark.parametrize(("how", "reason"), [("expiry", "expired"), ("stop", "stopped"), ("by_hand", "turned_off")])
async def test_countdown_ended_tells_the_automation_how(how, reason)
    # records[0].data == {"entity_id": NUMBER, "reason": reason}; one record

async def test_command_due_names_the_command_and_its_action(...)
    # add_command off in 10 min; advance: records[0].data == {"entity_id": NUMBER, "command_id": <id>, "action": "off"}

async def test_a_trigger_ignores_the_timers_of_other_devices(...)
    # timers on the boiler and on the kettle; trigger on the kettle's device; run the boiler: records == []

async def test_a_relay_trigger_names_the_channel_whose_countdown_ended(...)   # Review Focus 1
    # fake_relay with a timer on each channel; trigger countdown_ended on the relay's device;
    # run channel 1 for 10 and channel 2 for 20; advance 10: one record, entity_id == run_for_of(hass, one);
    # advance 10 more: the second names run_for_of(hass, two)

async def test_a_trigger_aimed_at_one_run_for_ignores_the_other_channel(...)
    # target {"entity_id": run_for_of(hass, one)}: the end of channel 2 records nothing

async def test_a_trigger_of_a_deleted_timer_never_fires(...)   # Review Focus 4
    # trigger aimed at {"entity_id": NUMBER}; remove the entry; a timer on the kettle runs out:
    # records == []; state_of(hass, "automation.<id>") == "on"; no ERROR record in caplog

async def test_a_timer_added_later_is_covered_by_the_device_trigger(...)   # Review Focus 5
    # trigger on the relay's device with only channel 1 timed; then setup_target(target="switch.relay_2");
    # run it 5 min, advance: one record naming run_for_of(hass, two)

async def test_a_countdown_that_ended_while_down_triggers_once_at_start_up(...)   # Review Focus 2
    # trigger countdown_ended on the boiler's device; set_number 30; restart_after(..., minutes=60):
    # records == one record with reason "expired"; a second restart_after(minutes=5) adds none
```

- [ ] **Step 2: Run** `uv run pytest tests/test_automation_triggers.py -v`. Expected: FAIL, "Invalid trigger 'timerify.countdown_started' specified" or no `trigger` platform.
- [ ] **Step 3: Implement** the interfaces above, with the Russian strings in `ru.json`.
- [ ] **Step 4: Docs** (en and ru), `automations.md`:
  - A new `## Triggers` section, after `## Actions`. Pick the device under **By target** after **Add trigger**, as for actions. A table:
    - **Countdown started**: when a timer that was not counting down starts. Not when a running countdown changes. Not for a loose run without a countdown.
    - **Countdown ended**: when the countdown runs out, is stopped, or the device is switched off outside Timerify.
    - **Pending command came due**: when a pending command is carried out. Not for one that came too late after a restart, which the log names.
  - `### What a trigger tells the automation`: `trigger.entity_id` (the timer's **Run for**), `trigger.ends_at`, `trigger.reason`, `trigger.command_id` and `trigger.action`, each in one line. Then the three reasons in plain words. Then a YAML code block: an automation that sends a notification only when the countdown ran out, with the condition `{{ trigger.reason == 'expired' }}`. Then one sentence: an automation that turns the device on again when its countdown ends should check the reason, or a stop would start it again.
  - `### After a restart`: a countdown that ended while Home Assistant was down triggers **Countdown ended** once, when Home Assistant has started. The device is turned off then. A countdown that still runs does not trigger again. A pending command that came due while it was down triggers **Pending command came due** at that time too.
  - `## A device with two timers` gains: a trigger aimed at the device fires for each timer, and `trigger.entity_id` says which. A timer you add to the device later is covered without editing the automation.
  - The intro and "Pick the device" name triggers too: "a Timerify action or trigger", and **Add action** or **Add trigger**. The **Device** block sentence says "actions and triggers".
  - The Automations bullet of `docs/<lang>/README.md`, `README.md` and `README.ru.md` ends with "and react when a countdown starts or ends, or a pending command comes due."
- [ ] **Step 5: RULINGS.** Add **"The triggers are integration triggers on the Run for entities, matched against their target at each event."** It covers these decisions:
  - The platform is `trigger.py` with `async_get_triggers`. Give the file:line of Tech Stack, "Integration triggers".
  - The target filter is the one of the services, so **By target** offers both for the same devices.
  - The target is resolved per event, so a timer added, deleted or moved to another area needs no tracking. A deleted one is never matched, and nothing is logged.
  - No options: no "for", and no "first" or "last" of several timers, because an event has no duration and each timer's event stands alone.

  Why: #39, Decision 1. Cost if wrong: an automation aimed at a Run for whose entity id the user renames never fires again, as with any entity id in Home Assistant; a device target avoids it, and the docs say so. Tests: the tests of this task.
- [ ] **Step 6: Run** the gate, hassfest, `npm --prefix card run build` and `npm --prefix card run build:check`. Expected: all pass.
- [ ] **Step 7: Commit.**

```bash
git add custom_components/timerify/trigger.py custom_components/timerify/triggers.yaml custom_components/timerify/icons.json custom_components/timerify/translations/en.json custom_components/timerify/translations/ru.json custom_components/timerify/frontend/timerify-card.js tests/test_automation_triggers.py docs/en/automations.md docs/ru/automations.md docs/en/README.md docs/ru/README.md README.md README.ru.md RULINGS.md
git commit -m "Add the Countdown started, Countdown ended and Pending command came due triggers"
```

### Task 4: The full gate

**Files:** none, unless a check fails, and then only the files of the fix.

- [ ] **Step 1: Run the full gate on the final tree:**
  - `uv run pytest`, `uv run ruff check`, `uv run ruff format --check` and `uv run mypy`;
  - hassfest;
  - `npm --prefix card ci`, `npm --prefix card run build:check`, `npm --prefix card run typecheck` and `npm --prefix card test`;
  - then compare `date -u +%s` with `docker run --rm alpine date -u +%s`, and run `npm --prefix card run e2e`.

  Expected: all pass. The card does not use the new service or the events, so the E2E needs no change.
- [ ] **Step 2: Report** the counts of pytest, vitest and E2E, against the starting point of 2183 pytest tests. Say that the release's smoke test is where the editor's **By target** lists are seen and photographed (spec, "Release"). Give the PR body line of Global Constraints: "Closes #38. Closes #39." (one keyword per issue: GitHub closes only the first number of "Closes #38, #39"), with a sentence that the actions and triggers are under **By target** because the Device block of a device that another integration owns does not ask Timerify (RULINGS, "Automations").
