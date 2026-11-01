# Timerify 1.1.0 Part A (Engine and Reliability) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the eight engine and reliability issues of Part A (#31, #11, #12, #13, #18, #10, #17, #14). The test harness tells two targets of one domain apart. Re-sends are bounded per piece of work. Nothing folds before Home Assistant has started. Every fold logs what came due while the target was away. Settings are filtered when they are sent. A deleted target and an unreadable stored timer each raise a Repairs issue with a fix flow. #14 is labelled `upstream`.

**Architecture:** No new subsystem. The rules stay in `core.py`: the allowance (#11) and a target never seen being treated as away (#12). Everything that touches Home Assistant stays in `controller.py` and `__init__.py`: the start-up gate (#12), one logging step for every fold (#13), the settings filter in `_execute` (#18) and the life of the deleted-target issue (#10). Two small new modules hold the Repairs side. `issues.py` creates and deletes the issues through `helpers.issue_registry`. `repairs.py` is the integration's repairs platform, with the two fix flows. The harness change (#31) is in `tests/conftest.py`.

**Tech Stack:** Python 3.14, Home Assistant 2026.10.4, checked in `.venv/lib/python3.14/site-packages/homeassistant`:
- `helpers/issue_registry.py`: `async_create_issue` (:337-373), `async_delete_issue` (:415-421, deleting a missing issue is not an error), `IssueSeverity.ERROR` (:46-51).
- `components/repairs`: `RepairsFlow` and `RepairsFlowResult` are exported by `__init__.py:12-21`. The platform protocol is `async_create_fix_flow(hass, issue_id, data) -> RepairsFlow` (`models.py:145-153`). The manager deletes the issue when a flow finishes with `create_entry` (`issue_handler.py:101-114`). The HTTP views are `/api/repairs/issues/fix` and `/api/repairs/issues/fix/{flow_id}` (`websocket_api.py:133-200`). `components/waqi/repairs.py` is the pattern to follow.
- `helpers/helper_integration.py:14-21`: `async_handle_source_entity_changes(..., source_entity_removed: Callable[[], Coroutine[Any, Any, None]] | None)`. A registry "remove" awaits it instead of unlinking the helper's entities (:70-80). A "create" event is ignored by the helper.
- `helpers/entity_registry.py`: `async_get_or_create` restores the registry id of a deleted entity with the same platform and unique id (:1601-1624). `async_device_modified` (:1778-1806) removes a deleted device's own entities and unlinks every other entity on it (`device_id=None`).
- `helpers/start.py:75-90` (`async_at_started`). It runs the job at once, as a task, when Home Assistant is running. Otherwise it runs at `EVENT_HOMEASSISTANT_STARTED`.

**Spec:** `docs/superpowers/specs/2026-11-01-release-1.1.0-design.md`, section "Part A". It extends the base spec `docs/superpowers/specs/2026-10-28-timerify-design.md` and `RULINGS.md`. Each issue's "Where" and "Fix" are binding: `gh issue view N`. The plan's decisions follow the base spec's rules:
- one timer is the single source of truth;
- manual wins;
- pending commands are firm promises;
- R10: unavailable is not off.

**Starting point:** branch `part-a-engine` at 0658d8c (pytest 1998 passed).

## Global Constraints

- Home Assistant `>= 2026.10.4` (`hacs.json`), Python `>= 3.14.2`, `pytest-homeassistant-custom-component==0.13.375`. No new runtime or dev dependency, and no change to `manifest.json` (hassfest confirms that the `repairs` platform needs none).
- Only public Home Assistant APIs, checked in `.venv` before use. mypy is strict, and schemas use `probatio`.
- Tests are user scenarios with frozen time (`freezer`, `advance`, `advance_to`, `restart_after`). No `asyncio.sleep`, no polling and no backdoors. Product code gets no test-only branch. An existing test is edited only where a task names it.
- User-facing strings go in `translations/en.json` (the source) and `translations/ru.json`, with the same keys and the same `{blanks}` (`tests/test_translations.py`). Cyrillic is allowed only in `ru.json` and `docs/ru/`. Write the Russian strings as translations of the English ones. Take Russian Home Assistant screen names from `python3 .superpowers/ui-names/ui-term.py "<English name>"`. For example, "Repairs" gives the `config:ui.panel.config.repairs.caption` string, and "System" gives `ui.panel.config.dashboard.system.main`.
- A user-visible change updates `docs/en/<page>.md` and `docs/ru/<page>.md` in the same commit. Keep the same `##` and `###` headings (`tests/test_docs.py`) and the CLAUDE.md "User documentation" style: short sentences, "you", no long dashes, no rule ids, and no internal words.
- After any change to `en.json`, run `npm --prefix card run build:check`. The card imports only `common` from it (`card/src/strings.ts:5`), so the check must pass with no rebuild. If it fails, run `npm --prefix card run build` and commit the bundle.
- Every task ends with these passing: `uv run pytest`, `uv run ruff check`, `uv run ruff format --check` and `uv run mypy`. A task that changes `translations/` also runs hassfest: `docker run --rm --platform linux/amd64 -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest`.
- English only. Commit messages have no attribution lines. Never use `--no-verify`. `git add` only the files of the task.
- RULINGS: Task 2 adds a section `## Release 1.1.0` with a subsection `### Engine and reliability` after "Release 1.0.0". Later tasks append their bullets to it, in the existing style: a bold decision, then "Why:", then "Cost if wrong:". Where an older ruling is superseded, replace that bullet with one line: its bold title, then "Changed in 1.1.0: see "<new title>" under Release 1.1.0."
- `docs/followups.md`: each task deletes the line of the issue it fixes. #14 stays.
- The PR body names "Closes #31, #11, #12, #13, #18, #10, #17". #14 stays open.

## Review Focus

1. **A deleted target with a countdown running is restored after the countdown's end.** Nothing is sent while it is gone. When it is back it is turned off once, as for an unavailable target (R10). Test: Task 6, `test_a_countdown_ended_while_the_target_was_deleted_turns_it_off_when_back`.
2. **The user deletes the timer on the integration page instead of through the repair.** The issue goes with it, and no stale repair is left. Test: Task 6, `test_deleting_the_timer_on_the_integration_page_clears_the_repair`.
3. **A due command whose only setting the running device no longer takes.** No call goes out, the warning is said once, and nothing is owed or re-sent afterwards. Test: Task 5, `test_a_running_ac_that_no_longer_takes_the_only_setting_of_a_command_gets_no_call`.
4. **A stored file that misses a field, not only one that contradicts itself.** It raises the same repair, not a bare `KeyError` at set-up. Test: Task 7, `test_a_stored_timer_missing_a_field_raises_the_same_repair`.
5. **The target reports while Home Assistant is still starting, with an expired countdown stored.** The report folds nothing. Start-up folds the countdown and the fresh windows once, with no flip-flop. Test: Task 3, `test_a_report_of_the_target_while_starting_folds_nothing_until_started`.

---

## File Structure

```
custom_components/timerify/
  core.py         _Allowance per piece of work (T2); a target never seen is not switched (T3)
  controller.py   _log_gave_up text (T2); start-up gate (T3); _execute_fold logs (T4);
                  _settings_the_target_takes in _execute, _with_settings_the_target_takes gone (T5);
                  target-deleted state and issue (T6)
  __init__.py     source_entity_removed, _follow_target_restored (T6); StoredTimerInvalid -> issue (T7)
  issues.py       new: issue ids, raise and clear (T6, T7)
  repairs.py      new: async_create_fix_flow, DeleteTimerFlow (T6), ResetStoredTimerFlow (T7)
  store.py        StoredTimerInvalid; a missing field is invalid too (T7)
  translations/en.json, ru.json   "issues" (T6, T7); exceptions.stored_timer_invalid (T7)
tests/
  conftest.py     FakeServices (T1); ignore_calls(echo_unknown=) (T2); delete/restore, registered= (T6)
  test_harness.py new (T1)
  test_core.py, test_device_failures.py, test_settings.py (T2, T3, T5)
  test_restart.py (T3, T4, T7), test_schedules.py (T4, T5), test_repairs.py new (T6, T7)
docs/en/timers.md, docs/ru/timers.md (T2 to T7)
RULINGS.md (T2, T3, T5, T6, T7, T8), docs/followups.md (T1 to T7)
```

---

### Task 1: Each fake target takes only its own calls (#31)

**Files:**
- Modify: `tests/conftest.py`. This covers `FakeTarget.provide_services`, `_handler` and `_is_timerify_entity` (`:174-179`, `:273-366`), and the `provide_target` fixture (`:537-588`).
- Create: `tests/test_harness.py`.

**Interfaces:**
- Produces (tests only):
  - `@dataclass class FakeServices` in `tests/conftest.py`. It has `hass: HomeAssistant`, `strays: list[str]` and `provide(self, target: FakeTarget, services: Mapping[str, Obey]) -> None`.
    - It registers one handler per `(domain, service)`, the first time a fake of that domain provides that service. The service that was there before is kept as the place for Timerify's own entities, as today.
    - It records `target` as the owner of its entity, with that fake's own `Obey` per service.
  - The handler dispatches each entity id of a call:
    - Timerify's own (registry platform `timerify`) goes on, all together, to the service that was there before.
    - An entity owned by a fake goes to `owner.take(service, obey, call, entity_id, data)`. That is today's `_take`, made public.
    - Any other entity is appended to `strays` as `"<domain>.<service> <entity_id>"`, and the handler raises `AssertionError(f"no fake target owns {entity_id} ({domain}.{service})")`.
  - Ownership is keyed by the entity's registry id when it has a registry entry, and by its entity id otherwise. A renamed target stays owned (`tests/test_source_changes.py:44-66`). An entity restored with the same unique id gets its old registry id back (`entity_registry.py:1624`), so it stays owned too.
  - `provide_target` becomes a yield fixture. It makes one `FakeServices` per test, and after the test it asserts `services.strays == []`, with the list in the message. The controller catches every exception of a service call (`controller.py:1087-1092`), so the teardown is what makes a stray call fail the test.
  - `FakeTarget.provide_services` is removed. `provide` calls `services.provide(target, services_of_the_domain)`. A module-level `def provide_fake(hass, services: FakeServices, entity_id, obeys, *, name, on_device=True, capability_attributes=None, state_attributes=None) -> FakeTarget` holds today's body of `provide`, so that a test can build fakes on its own `FakeServices`.

- [ ] **Step 1: Write the failing tests** in `tests/test_harness.py`:

```python
async def test_two_switches_with_a_timer_each_get_only_their_own_calls(
    hass, freezer, fake_target, provide_target, setup_target
)  # pump = provide_target("switch.pump", SWITCH_SERVICES, name="Pump"); timers on both;
   # Run for 10 on NUMBER, Run for 20 on "number.pump_run_for"; advance 10 min:
   # fake_target.calls == [TURN_ON, TURN_OFF]; pump.calls == [("turn_on", "switch.pump")];
   # advance 10 more: pump.calls == [("turn_on", "switch.pump"), ("turn_off", "switch.pump")]

async def test_a_call_for_an_entity_no_fake_owns_fails_loudly(hass, clock_at_start)
   # services = FakeServices(hass); provide_fake(hass, services, TARGET_ID, SWITCH_SERVICES, name="Boiler");
   # with pytest.raises(AssertionError, match="switch.stray"):
   #     await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.stray"}, blocking=True)
   # services.strays == ["switch.turn_on switch.stray"]; the boiler's calls == []
```

- [ ] **Step 2: Run** `uv run pytest tests/test_harness.py -v`. Expected: FAIL. `FakeServices` does not exist, and today the pump's calls land on the fake provided last.
- [ ] **Step 3: Implement** the interfaces above. Update the docstring of `provide`, and drop the sentence "so a test with two targets uses two domains".
- [ ] **Step 4: Run** `uv run pytest`, then the rest of the gate. Expected: all pass, with no stray call in any test. A stray found in an existing test is a real bug in that test. Report it, and do not hide it.
- [ ] **Step 5: Commit.** Delete the #31 line from `docs/followups.md`.

```bash
git add tests/conftest.py tests/test_harness.py docs/followups.md
git commit -m "Give each fake target only the calls for its own entity"
```

### Task 2: Bound re-sends and the give-up warning per piece of work (#11)

**Files:**
- Modify:
  - `custom_components/timerify/core.py`: `GaveUp` (`:136-143`), `_Allowance` (`:255-280`), the allowance fields (`:320-327`), the reset in `observe` (`:570-573`), `_want` (`:899`), `_send` (`:915-921`), `_resend` (`:923-936`), `_ask_again` (`:938-950`), `_owe` (`:952-960`), `_deliver_settings` (`:962-992`) and `_clear_settings` (`:1026-1032`).
  - `custom_components/timerify/controller.py`: `_log_gave_up` (`:1012-1031`).
  - `custom_components/timerify/const.py`: the docstring of `MAX_AUTOMATIC_RESENDS` (`:63-67`).
  - `tests/conftest.py`: `FakeTarget.ignore_calls` (`:224-230`) and `take`.
  - `docs/en/timers.md` and `docs/ru/timers.md`: "When the device does not answer", bullets 3 and 4 (en `:77-78`).
  - `RULINGS.md`.
- Test: `tests/test_core.py`, `tests/test_device_failures.py` and `tests/test_settings.py`.

**Interfaces:**
- Consumes: `FakeServices` (Task 1).
- Produces: the rule that every later task relies on. Each piece of work has one allowance for its whole life. A piece of work is the pending wish, or the owed settings.
  - The allowance covers the first delivery, then `automatic_resends` re-sends prompted by reports of any kind: a repeat, a change of state, a return from unavailable, or the first report after a start. Then comes one `GaveUp`, and after that nothing.
  - A report that finds the work never delivered by this core makes the first delivery. That is a restored wish, or one made while the target was away, and it costs no re-send.
  - Only new work renews the allowance:
    - a new pending wish from `_want` (any command, or a fold item that wants a state);
    - the one correction (`_ask_again`);
    - new owed settings (`_owe`);
    - a command that sends the owed settings (`_settings_for_running_target`).
  - The core API for the controller is unchanged. Inside the core:
    - `_Allowance` gets `renew()`, `delivered()` (a command made the first delivery) and `take() -> Literal["send", "give_up", "silent"]` (a report asks to send).
    - `_resend(wish)` loses its `repeated` parameter.
    - `_deliver_settings(*, by_report: bool)` replaces `repeated`.
    - `observe` no longer resets anything.
  - `_log_gave_up` text, exactly:
    - for a wish: `"%s did not turn %s after %d %s; Timerify will not send it again until it is asked again"`;
    - for settings: `"%s did not take its settings after %d %s; Timerify will not send them again until it is asked again"`.
  - `FakeTarget.ignore_calls(*, echo_attribute: bool = False, echo_unknown: bool = False)`. With `echo_unknown`, the device answers each ignored call by writing `unknown` and then the state it had, both with the call's context, at most `ECHO_LIMIT` times.

- [ ] **Step 1: Write the failing tests.** First, the core (`tests/test_core.py`). Replace `test_a_change_of_the_targets_state_gives_a_full_allowance_again` (`:831`) and `test_a_change_of_state_gives_settings_a_full_allowance_again` (`:1317`) with:

```python
def test_a_target_that_comes_back_gets_no_new_allowance_for_the_same_wish()
    # refused_turn_off(); repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1);
    # c.observe(+10, "unavailable"); back = c.observe(+11, "on"):
    # back == [Changed()]; repeat_reports(c, 2) == [[], []]

def test_a_device_that_answers_unknown_then_its_old_state_is_asked_a_limited_number_of_times()
    # refused_turn_off(); 10 cycles of observe("unavailable") then observe("on"), with
    # call_failed after each send: TurnOff() is sent MAX_AUTOMATIC_RESENDS times in all,
    # GaveUp("off") appears exactly once; c.snapshot.pending == "off"

def test_a_wish_made_while_the_target_is_away_is_delivered_when_it_is_back_and_then_limited()
    # core("strict","on"); set_duration(NOW, 10 min); observe(+1, "unavailable"); stop(+2) has no TurnOff();
    # observe(+3, "on") contains TurnOff(); call_failed; repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1)
    # == [[TurnOff()]] * MAX_AUTOMATIC_RESENDS + [[GaveUp("off")]]

def test_a_target_that_comes_back_gets_no_new_allowance_for_the_same_settings()
    # owing("strict","on"); call_failed; repeat_reports(c, MAX_AUTOMATIC_RESENDS + 1);
    # observe("unavailable"); back = observe("on"): back == [Changed()]; repeat_reports(c, 1) == [[]]
```

  `test_the_first_report_after_a_start_gives_a_full_allowance`, `test_a_command_wanting_the_same_wish_always_sends_and_gives_a_full_allowance` and the three settings tests at `:1334-1378` stay as they are. They must still pass.

  Then the controller (`tests/test_device_failures.py`):

```python
async def test_device_that_answers_unknown_then_its_old_state_is_commanded_a_limited_number_of_times(...)
    # strict; Run for 10; fake_target.ignore_calls(echo_unknown=True); advance 10 min:
    # fake_target.calls == [TURN_ON] + [TURN_OFF] * (1 + MAX_AUTOMATIC_RESENDS);
    # timerify_warnings(caplog) == ["switch.boiler did not turn off after 4 attempts;"
    #   " Timerify will not send it again until it is asked again"]

async def test_refusing_device_that_keeps_dropping_off_is_not_commanded_again(...)
    # run_into_a_refusing_device; then 3 x (set_state("unavailable"), set_state("on")):
    # calls unchanged; len(timerify_warnings(caplog)) == 1

async def test_refusing_device_is_commanded_again_on_a_command(...)
    # run_into_a_refusing_device; obey_calls(); set_number(NUMBER, 0):
    # calls == [TURN_ON] + [TURN_OFF] * (2 + MAX_AUTOMATIC_RESENDS); state "off"
```

  Also make these edits in the existing tests:
  - Delete `test_refusing_device_is_commanded_again_when_it_changes_or_on_a_command` (`:196-218`). The two tests above replace it.
  - Change the warning text in `:183-186`, `:277-280`, `:440-443` and `tests/test_settings.py:377-380` to the new text.
  - In `test_media_player_is_not_turned_on_again_by_repeated_reports` (`:257-293`), the last assert becomes `fake_media_player.calls == [("turn_on", "media_player.tv")]`, and its docstring drops "Only a change of its state is answered".
- [ ] **Step 2: Run** `uv run pytest tests/test_core.py tests/test_device_failures.py tests/test_settings.py -v`. Expected: the new tests and the edited ones FAIL. The unknown/old-state test fails with about `ECHO_LIMIT` calls.
- [ ] **Step 3: Implement** the interfaces in the core and the controller, and update the docstrings that say "until the state changes" (`GaveUp`, `_Allowance`, `call_failed`, `_resend`, `_deliver_settings` and `MAX_AUTOMATIC_RESENDS`).
- [ ] **Step 4: Docs.** In `timers.md` (en and ru), "When the device does not answer" changes like this:
  - A device that rejects a command gets at most 3 repeats of it, however often it reports or reconnects.
  - Then Timerify writes one warning in the log and stops sending that command.
  - It is sent again when you ask again, or when the timer itself switches the device: a countdown ends, or a schedule interval starts.
  - Remotes and media players get no repeats at all. They are sent a command again only when you ask again.
- [ ] **Step 5: RULINGS.** Create `## Release 1.1.0` and `### Engine and reliability`. Add **"Each piece of work has one allowance of automatic re-sends for its whole life."**
  - Give the rule from Interfaces.
  - Why: #11. A device that answers each refused call with `unknown` and then its old state reset the count on every cycle. A device that drops off Wi-Fi logged one give-up per reconnect.
  - Cost if wrong: a device that refused four times, and then works again after a reconnect, is not sent the command until it is asked again. A media player whose turn-on failed is turned on only when asked again.
  - Replace the sentence of the phase 1 ruling (`RULINGS.md:52-70`) that begins "Then one warning is logged and nothing more is sent; the count starts again when the target's state changes ...". It now ends at "Then one warning is logged and nothing more is sent", followed by "(per piece of work since 1.1.0, see Release 1.1.0)". Replace the "Owed settings have their own count" bullet (`:281-283`) with the one-line pointer.
- [ ] **Step 6: Run** the gate. Expected: all pass.
- [ ] **Step 7: Commit.** Delete the #11 line from `docs/followups.md`.

```bash
git add custom_components/timerify/core.py custom_components/timerify/controller.py custom_components/timerify/const.py tests/conftest.py tests/test_core.py tests/test_device_failures.py tests/test_settings.py docs/en/timers.md docs/ru/timers.md RULINGS.md docs/followups.md
git commit -m "Bound automatic re-sends and the give-up warning per wish and per set of settings"
```

### Task 3: Before Home Assistant has started, commands record and save, and nothing folds (#12)

**Files:**
- Modify:
  - `custom_components/timerify/core.py`: `_want` (`:903`).
  - `custom_components/timerify/controller.py`: `__init__` (a `_started` flag), `_async_set_interval_enabled_locked` (`:571-588`), `_handle_started` (`:798-830`), `_handle_state_change` (`:849-859`) and `_arm` (`:1143-1150`).
  - `docs/en/timers.md` and `docs/ru/timers.md`: "When Home Assistant restarts".
  - `RULINGS.md`.
- Test: `tests/test_core.py` and `tests/test_restart.py`. The second uses `set_up_while_starting` and `finish_start_up` (`:790-812`). `finish_start_up` brings the target up "on".

**Interfaces:**
- Consumes: the allowance rule of Task 2. The first delivery after start-up is free.
- Produces:
  - Core: a target never observed (`last_actual is None`) is treated as away, the way `"unavailable"` is. `_want` records the wish as unsent and sends nothing. `_deliver_settings` already sends nothing then. The first `observe` delivers it.
  - Controller: `self._started = False` until `_handle_started` sets it to True. It does so under the lock, after the windows are merged and the target observed, and before `_execute_fold`. Until then:
    - `_arm` arms nothing. The stored end, command or window that has long passed is folded by the first observation.
    - `_async_set_interval_enabled_locked` only records the flag. It runs `self._execute(self._core.set_interval_enabled(now, interval_id, enabled))` and returns, so it works out no window and ticks nothing. `_handle_started` works the windows out for every interval that is on.
    - `_handle_state_change` returns without observing. `_handle_started` reads the target's state itself.
  - The decision to record in RULINGS is that a report before start-up is not observed either. The issue names commands only. A report before start-up would fold the stored items without the fresh windows, which start-up merges first (`_handle_started` docstring), and could switch the target twice.

- [ ] **Step 1: Write the failing tests.**

```python
# tests/test_core.py
def test_a_command_before_the_first_report_sends_nothing_and_the_first_report_sends_it()
    # c = TimerCore("strict", minutes(45), Snapshot()); fx = c.set_duration(NOW, minutes(30), COOL24):
    # no TurnOn/TurnOff/ApplySettings in fx; c.snapshot.pending == "on"; c.snapshot.owed_settings == COOL24;
    # c.observe(NOW + minutes(1), "off", by_us=False) contains TurnOn(COOL24)

# tests/test_restart.py
@pytest.mark.parametrize("command", ["run_for", "add_time", "run", "add_command_off"])
async def test_a_command_given_while_starting_is_saved_and_switches_nothing_until_started(...)
    # set_up_while_starting(hass, setup_target, payload()); the command (Run for 30 / add_time 30 /
    # run minutes=30 / add_command action="off" delay=10): fake_target.calls == []; the saved file holds the change
    # (end == at(30) for the first three; one command at at(10) for the last);
    # finish_start_up(hass, fake_target, "after_started"): calls == [] (the target is on);
    # advance to the end (30 min, or 10 min): calls == [TURN_OFF]

async def test_a_command_while_starting_does_not_fold_what_came_due_while_down(...)
    # stored payload(end=at(-10), started_at=at(-40)); set up while starting;
    # add_command(hass, NUMBER, action="on", delay=60, minutes=5):
    # calls == []; saved(...)["end"] == at(-10) (not folded);
    # finish_start_up(..., "before_started"): calls == [TURN_OFF] exactly; one command kept

async def test_switching_an_interval_while_starting_records_the_flag_and_works_out_nothing(...)
    # set up while starting; interval = await add_interval(hass, entry, start="08:00", end="09:00");
    # set_switch("switch.boiler_schedule_08_00_09_00_mon_sun", False): saved disabled_intervals == [interval], calls == [];
    # set_switch(..., True): saved disabled_intervals == [], saved windows == [];
    # finish_start_up: saved windows has one window of `interval`, starting at 08:00 local

async def test_a_report_of_the_target_while_starting_folds_nothing_until_started(...)   # Review Focus 5
    # stored payload(end=at(-10), started_at=at(-40)); set up while starting; fake_target.set_state("on"):
    # calls == []; saved end == at(-10); hass.async_start(): calls == [TURN_OFF] exactly
```

- [ ] **Step 2: Run** `uv run pytest tests/test_core.py tests/test_restart.py -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement** the interfaces above. Update the `_handle_started` comment "Nothing is armed earlier ..." so that it names the gate.
- [ ] **Step 4: Docs.** In `timers.md` (en and ru), "When Home Assistant restarts" gains this bullet: a change you make while Home Assistant is still starting is kept and saved. It is carried out once Home Assistant has started. This covers a **Run for** value, an action and a switched interval.
- [ ] **Step 5: RULINGS.** Add **"Until start-up has taken stock, the timer only records."** Give the three gates and the report decision. Why: #12, and §5.7's single catch-up. Cost if wrong: a report before start-up is answered a few seconds later, at start-up. Replace "A change before Home Assistant has started is not held back" (`RULINGS.md:588-594`) with the one-line pointer.
- [ ] **Step 6: Run** the gate. Expected: all pass.
- [ ] **Step 7: Commit.** Delete the #12 line from `docs/followups.md`.

```bash
git add custom_components/timerify/core.py custom_components/timerify/controller.py tests/test_core.py tests/test_restart.py docs/en/timers.md docs/ru/timers.md RULINGS.md docs/followups.md
git commit -m "Record and save commands before Home Assistant has started, and fold nothing until then"
```

### Task 4: Every fold says what came due while the target is away (#13)

**Files:**
- Modify:
  - `custom_components/timerify/controller.py`: `_handle_started` (`:829`), `_handle_state_change` (`:853-859`), `_fold_due` (`:867-875`) and `_execute_fold` (`:877-892`).
  - `docs/en/timers.md` and `docs/ru/timers.md`: "When the device does not answer", bullet 1.
- Test: `tests/test_restart.py` and `tests/test_schedules.py`.

**Interfaces:**
- Consumes: `_log_due_while_unavailable(before, now, effects)` (`:894-939`), unchanged, and its three `_LOGGER.info` texts.
- Produces: `_execute_fold(self, before: Snapshot, now: datetime, effects: list[Effect]) -> None`. It calls `_log_due_while_unavailable(before, now, effects)` and then carries out the effects as today. All three folds pass through it: `_fold_due`, `_handle_started` (with its `before` read after the merge, as today) and `_handle_state_change` (with the `now` it observed at). `_fold_due` no longer logs by itself.

- [ ] **Step 1: Write the failing tests.** Each `while_down` writes `fake_target.write("unavailable")`.

```python
# tests/test_restart.py
async def test_a_countdown_that_ended_while_down_is_logged_at_start_up_if_the_target_is_away(...)
    # Run for 10; restart_after(minutes=20, while_down=unavailable): timerify_info(caplog) contains
    # "The timer of switch.boiler ended while it is unavailable; it is turned off when it is back"; calls == [TURN_ON]

async def test_a_command_due_while_down_is_logged_at_start_up_if_the_target_is_away(...)
    # add_command(action="on", delay=10, minutes=30); restart_after(minutes=20, while_down=unavailable):
    # contains "A pending command for switch.boiler came due while it is unavailable;"
    # " it is applied when it is back, if it is still relevant then"

# tests/test_schedules.py
async def test_a_window_that_started_while_down_is_logged_at_start_up_if_the_target_is_away(...)
    # open_sunday; interval 06:30-07:15; restart_after across 06:30 (to 06:40) with while_down=unavailable:
    # contains "A schedule window of switch.boiler started while it is unavailable;"
    # " it is turned on when it is back, if the window is still open then"

async def test_a_command_due_as_the_target_drops_off_is_logged_once(...)
    # add_command(action="on", delay=10, minutes=30); freezer.tick(timedelta(minutes=10)) (no timer fired);
    # fake_target.set_state("unavailable"): the command line is in timerify_info once;
    # async_fire_time_changed(hass); block: still once; calls == []
```

- [ ] **Step 2: Run** them. Expected: FAIL, because nothing is logged.
- [ ] **Step 3: Implement** the interface.
- [ ] **Step 4: Docs.** In `timers.md` (en and ru), the first bullet of "When the device does not answer" gains a sentence: the log says what came due while the device was away, also when Home Assistant starts while it is away.
- [ ] **Step 5: Run** the gate. Expected: all pass.
- [ ] **Step 6: Commit.** Delete the #13 line from `docs/followups.md`.

```bash
git add custom_components/timerify/controller.py tests/test_restart.py tests/test_schedules.py docs/en/timers.md docs/ru/timers.md docs/followups.md
git commit -m "Log what came due while the target was away for every fold, start-up and reports included"
```

### Task 5: Filter the settings the target takes when they are sent (#18)

**Files:**
- Modify:
  - `custom_components/timerify/controller.py`. The filter moves into `_execute` (`:946-988`). `_with_settings_the_target_takes` (`:663-697`), its call in `_async_windows` (`:640`) and the per-interval `_left_out` (`:243-247`) are deleted.
  - `docs/en/timers.md` and `docs/ru/timers.md`: "Settings for turning on", the second paragraph (en `:107`).
  - `RULINGS.md`.
- Test: `tests/test_settings.py` and `tests/test_schedules.py`.

**Interfaces:**
- Consumes: `validate_settings(hass, entity_id, {name: value})`, called per setting as today (`controller.py:672-676`). `Settings` and `SettingValue` (`const.py`).
- Produces:
  - `TargetController._settings_the_target_takes(self, settings: Settings) -> Settings`. It returns the settings the target takes now, each judged alone. For each `(name, value)` left out, it logs exactly `"%s cannot take the setting %s=%s now; it is left out"` (target, name, value). The log comes once while that pair stays left out. A later call that carries `name` and finds it taken forgets it. State: `self._left_out: set[tuple[str, SettingValue]]`.
  - `_execute` carries out the following:
    - `TurnOn(settings)` becomes `turn_on_calls(taken)` with `with_settings=bool(settings)`.
    - `ApplySettings(settings)` becomes `apply_calls(taken)` with `with_settings=True`.
    - This holds for owed settings of every origin: `run`, a pending command, a window, or settings carried over.
    - Settings that were all left out count as delivered, because the core is told `settings_applied`. An `ApplySettings` with nothing left makes no call.
  - Windows carry their interval's settings as saved. `async_add_command` and `async_run` still refuse, at once, settings that the target does not take when the request is made.

- [ ] **Step 1: Write the failing tests.**

```python
# tests/test_settings.py
async def test_a_due_command_whose_mode_was_renamed_turns_on_without_it(hass, freezer, fake_climate, setup_target, caplog)
    # add_command(hass, AC_NUMBER, action="on", delay=10, minutes=30, hvac_mode="cool", temperature=24);
    # fake_climate.capability_attributes["hvac_modes"] = ["off", "heat", "fan_only"]; fake_climate.write("off");
    # advance 10 min: fake_climate.call_data == [("turn_on", {}), ("set_temperature", {"temperature": 24.0})];
    # state_of(AC_ID) == "heat"; state_of(AC_NUMBER) == "30";
    # timerify_warnings(caplog) == ["climate.ac cannot take the setting hvac_mode=cool now; it is left out"]

async def test_a_running_ac_that_no_longer_takes_the_only_setting_of_a_command_gets_no_call(...)  # Review Focus 3
    # Run for 60 (plain); add_command(action="on", delay=10, hvac_mode="cool"); remove "cool" as above;
    # calls_before = list(call_data); advance 10 min: call_data == calls_before; one warning;
    # saved(hass_storage, entry)["owed_settings"] == {}; await fake_climate.set_state("heat", rssi=-70): call_data unchanged

# tests/test_schedules.py
async def test_a_climate_that_connects_without_capabilities_keeps_the_settings_of_its_window(...)
    # open_sunday; AC timer; interval 06:30-07:15 COOL24; kept = fake_climate.capability_attributes;
    # fake_climate.capability_attributes = {}; fake_climate.write("unavailable"); restart(hass, entry);
    # advance_to 06:10; fake_climate.capability_attributes = kept; await fake_climate.set_state("off");
    # advance_to 06:30: call_data == [SET_COOL, SET_24]; timerify_warnings(caplog) == []
```

  Also edit these existing tests in `tests/test_schedules.py`:
  - `test_setting_the_ac_no_longer_takes_is_left_out_and_said_once` (`:911-941`): the expected warnings become `["climate.ac cannot take the setting hvac_mode=cool now; it is left out"]`. The calls and the "said once over two mornings" stay.
  - `test_a_switch_flipped_before_a_deleted_interval_unloads_is_not_broken_by_it` (`:944-974`): the evening switch is "on", and `timerify_warnings(caplog) == []`. Nothing is said until a window carries the setting.
  - `test_setting_that_comes_back_and_goes_again_is_said_again` (`:977-1008`): rewrite the timeline as follows.
    1. With the mode missing, Sunday 06:30 runs `[("turn_on", {}), SET_24]`, and there is 1 warning.
    2. With the mode back, Monday 06:30 runs `[SET_COOL, SET_24]`, and there is still 1.
    3. With the mode gone again, Tuesday 06:30 runs `[("turn_on", {}), SET_24]`, and there are 2.
- [ ] **Step 2: Run** `uv run pytest tests/test_settings.py tests/test_schedules.py -v`. Expected: the new and edited tests FAIL.
- [ ] **Step 3: Implement** the interfaces above.
- [ ] **Step 4: Docs.** In `timers.md` (en and ru), after "It checks a request when you make it ..." add a sentence: a device can stop offering a setting later, for example when an update of its integration renames a mode. Then Timerify leaves that setting out when the command or the schedule interval runs. The device gets the rest, and the log names the setting.
- [ ] **Step 5: RULINGS.** Add **"The settings are filtered when they are sent, whoever owes them."** Give the rule and the "once while left out" warning. Why: #18. Cost if wrong: a setting that comes and goes between two calls is warned about again. Replace these with one-line pointers:
  - "A window carries only the settings of its interval that the target takes when the window is worked out" (`RULINGS.md:499-512`);
  - the mention of `_with_settings_the_target_takes` in "A deleted interval is still worked out until the timer reloads" (`:1761`). Drop the words "and the warning about its settings".
- [ ] **Step 6: Run** the gate. Expected: all pass.
- [ ] **Step 7: Commit.** Delete the #18 line from `docs/followups.md`.

```bash
git add custom_components/timerify/controller.py tests/test_settings.py tests/test_schedules.py docs/en/timers.md docs/ru/timers.md RULINGS.md docs/followups.md
git commit -m "Leave out the settings the target no longer takes when they are sent, for commands and windows alike"
```

### Task 6: A deleted target raises a repair that deletes the timer (#10)

**Files:**
- Create:
  - `custom_components/timerify/issues.py`;
  - `custom_components/timerify/repairs.py`;
  - `tests/test_repairs.py`.
- Modify:
  - `custom_components/timerify/controller.py`: `__init__`, `async_start` (`:277-285`), `_handle_started` and `_handle_state_change`.
  - `custom_components/timerify/__init__.py`: `_follow_target` (`:100-121`), `_follow_target_gaining_a_device` (`:124-160`), a new `_follow_target_restored`, `async_setup_entry` (`:48-66`) and `async_remove_entry` (`:88-97`).
  - `translations/en.json` and `translations/ru.json`: a new top-level `"issues"`.
  - `tests/conftest.py`: the `FakeTarget` fields, `delete`, `delete_device` and `restore`, and `provide_target(..., registered=True)`.
  - `tests/test_source_changes.py`: the deleted-target test. `source_entity_removed` switches off Home Assistant's default unlinking, so the timer's entities stay on the target's device.
  - `docs/en/timers.md` and `docs/ru/timers.md`: a new section.
  - `RULINGS.md`.

**Interfaces:**
- Consumes: `source_entity_removed` (`helper_integration.py:21`, :70-72), `async_track_entity_registry_updated_event`, `ir.async_create_issue` and `ir.async_delete_issue`.
- Produces:
  - `issues.py`:
    - `TARGET_DELETED: Final = "target_deleted"` and `type IssueKind = Literal["target_deleted", "stored_timer_invalid"]`.
    - `issue_id(kind: IssueKind, entry_id: str) -> str`, which returns `f"{kind}_{entry_id}"`.
    - `@callback async_raise_target_deleted(hass, entry: ConfigEntry, target: str) -> None`. Its arguments are `is_fixable=True`, `is_persistent=False`, `severity=IssueSeverity.ERROR`, `translation_key="target_deleted"`, `translation_placeholders={"timer": entry.title, "target": target}` and `data={"entry_id": entry.entry_id, "kind": "target_deleted"}`.
    - `@callback async_clear(hass, kind: IssueKind, entry_id: str) -> None`.
  - `repairs.py`:
    - `async def async_create_fix_flow(hass, issue_id: str, data: dict[str, str | int | float | None] | None) -> RepairsFlow` picks the flow by `data["kind"]`.
    - `class DeleteTimerFlow(RepairsFlow)`:
      - `async_step_init` goes to `async_step_confirm`.
      - `confirm` shows `step_id="confirm"`, with `probatio.Schema({})` and the issue's `translation_placeholders`, read from `ir.async_get(hass).async_get_issue(DOMAIN, self.issue_id)`.
      - On submit it aborts with `reason="timer_gone"` when `hass.config_entries.async_get_entry(entry_id)` is None. Otherwise it runs `await hass.config_entries.async_remove(entry_id)` and returns `async_create_entry(data={})`.
  - `TargetController`:
    - `self._target_deleted = False`.
    - `async def async_target_removed(self) -> None` is passed as `source_entity_removed`, and it marks the target deleted.
    - `_target_exists() -> bool` is true when the entity has a registry entry or a state.
    - `_set_target_deleted(deleted: bool) -> None` acts only on a change:
      - on True it raises the issue and warns `"The entity %s of the timer %s was deleted; the timer switches nothing until it is back"` (target, entry title);
      - on False it clears the issue and logs info `"The entity %s of the timer %s is back"`.
    - `_handle_started` calls `_set_target_deleted(not self._target_exists())` before it observes.
    - `_handle_state_change` calls `_set_target_deleted(False)` when `new_state is not None` and `_target_exists()`. The current registry and state are checked, not only the event, so that a report queued before the deletion does not end it.
    - `async_start` registers `entry.async_on_unload(lambda: issues.async_clear(hass, TARGET_DELETED, entry_id))`. The issue lives with the loaded timer, and set-up raises it again.
  - `__init__.py`:
    - `_follow_target` passes `source_entity_removed=entry.runtime_data.async_target_removed`.
    - `_follow_target_restored(hass, entry) -> None` schedules a reload (`async_schedule_reload`) on a registry `"create"` for the target id. The reload puts the timer's entities back on the target's device, and start-up clears the issue.
    - `_follow_target_gaining_a_device` now reacts to `"update"` only. A `"create"` is the restored handler's.
    - `async_remove_entry` clears the issue (both kinds after Task 7).
  - `en.json`, under `"issues"`:

```json
"target_deleted": {
  "title": "The device of timer {timer} was deleted",
  "fix_flow": {
    "step": {
      "confirm": {
        "title": "Delete the timer {timer}",
        "description": "The entity {target} that the timer {timer} switches no longer exists in Home Assistant. Until it is back, the timer switches nothing. Its countdown and pending commands are kept. If you add the device again with the same entity ID, the timer works again by itself and this message goes away. Submit to delete the timer, with its entities, schedule intervals and pending commands."
      }
    },
    "abort": { "timer_gone": "This timer was already deleted." }
  }
}
```

  - `tests/conftest.py`:
    - `FakeTarget` gains `platform: str`, `unique_id: str`, `provider: MockConfigEntry | None` and `name: str`, set by `provide_fake`.
    - `async def delete(self)` removes the registry entry and the state, as the target's integration does when the user deletes the entity.
    - `async def delete_device(self)` removes the device, and the registry removes the entity with it. It also removes the state.
    - `async def restore(self, state: str = "off")` creates the device again if it is gone (same identifiers), then the registry entry (same platform and unique id), then writes `state`.
    - `provide_target(..., registered: bool = True)`. With False, the fake has a state and services and no registry entry, as an entity of YAML without a unique id has.

- [ ] **Step 1: Write the failing tests** in `tests/test_repairs.py`. Use a `repairs` fixture (`assert await async_setup_component(hass, "repairs", {})`) and two helpers on `hass_client`:
  - `start_fix(client, issue_id) -> dict` POSTs `/api/repairs/issues/fix` with `{"handler": "timerify", "issue_id": ...}` and expects 200.
  - `submit_fix(client, flow_id) -> dict` POSTs `/api/repairs/issues/fix/{flow_id}` with `{}`.

```python
async def test_deleting_the_target_raises_a_repair_that_names_the_timer(...)
    # setup_target(); await fake_target.delete(): issue = ir.async_get(hass).async_get_issue(DOMAIN, f"target_deleted_{entry.entry_id}");
    # issue.translation_key == "target_deleted"; issue.translation_placeholders == {"timer": "Boiler", "target": "switch.boiler"};
    # issue.is_fixable; issue.severity == "error"; entry.state is LOADED; state_of(NUMBER) == "0";
    # timerify_warnings(caplog) == ["The entity switch.boiler of the timer Boiler was deleted; the timer switches nothing until it is back"]

async def test_a_countdown_ended_while_the_target_was_deleted_turns_it_off_when_back(...)  # Review Focus 1
    # Run for 30; delete; advance 30 min: calls == [TURN_ON] (no stray call); await fake_target.restore("on"); block:
    # calls == [TURN_ON, TURN_OFF] (one turn-off, whichever of the report and the reload comes first); the issue is gone

async def test_restoring_the_target_clears_the_repair_and_the_timer_works_again(...)
    # delete; restore: issue gone; entry LOADED; set_number(NUMBER, 10): calls == [TURN_ON]

async def test_restoring_a_deleted_device_puts_the_timer_entities_back_on_it(...)
    # delete_device: the timer's entities have device_id None (the registry unlinked them);
    # restore: {e.device_id for e in er.async_entries_for_config_entry(...)} == {fake_target.device_id}

async def test_a_target_deleted_while_home_assistant_was_down_raises_the_repair_at_start_up(...)
    # restart_after(hass, freezer, entry, minutes=5, while_down=<remove registry entry and state>): the issue exists

async def test_a_target_without_registry_entry_raises_the_repair_until_its_state_appears(...)
    # provide_target("switch.heater", SWITCH_SERVICES, name="Heater", registered=False); timer on it;
    # restart_after(while_down=hass.states.async_remove("switch.heater")): the issue exists;
    # await heater.set_state("off"): the issue is gone

async def test_the_repair_deletes_the_timer(hass, hass_client, repairs, ...)
    # delete; flow = await start_fix(...): flow["type"] == "form"; flow["step_id"] == "confirm";
    # flow["description_placeholders"] == {"timer": "Boiler", "target": "switch.boiler"};
    # done = await submit_fix(client, flow["flow_id"]): done["type"] == "create_entry";
    # hass.config_entries.async_get_entry(entry.entry_id) is None; no registry entry of the entry is left;
    # storage_key(entry) not in hass_storage; the issue is gone

async def test_deleting_the_timer_on_the_integration_page_clears_the_repair(...)  # Review Focus 2
    # delete; await hass.config_entries.async_remove(entry.entry_id): the issue is gone

async def test_the_repair_of_a_timer_deleted_meanwhile_does_nothing(...)
    # delete; flow = start_fix; async_remove(entry_id); submit_fix: type == "abort", reason == "timer_gone"
```

- [ ] **Step 2: Run** `uv run pytest tests/test_repairs.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** the interfaces above. Write the Russian `issues` strings in `ru.json`, with the same keys and blanks.
- [ ] **Step 4: Docs.** Add a section `## When the device is deleted` after "When the device does not answer" in `timers.md` (en and ru, the same heading level in both). It says:
  - If the entity of a timer is deleted, for example with its device, Home Assistant shows a repair, "The device of timer Boiler was deleted". You see it at the top of **Settings**, and under **Settings > System > Repairs**.
  - Until you act, the timer switches nothing. It keeps its countdown and its pending commands.
  - Add the device again with the same entity ID, and the timer works again by itself. The repair goes away.
  - Open the repair and submit it to delete the timer, with its entities and schedule intervals. Deleting the timer on its integration page does the same.
- [ ] **Step 5: RULINGS.** Add **"A timer whose target was deleted stays loaded and switches nothing, with a repair that deletes it."** It covers these decisions:
  - It keeps its entities and accepts commands, as for an unavailable target (R10).
  - It is checked at start-up, not at the top of set-up. A target that is not in the registry has no state until its integration has set up.
  - A state, or a registry entry created for the target, ends it. A created entry reloads the timer.
  - The issue lives with the loaded timer: it is cleared at unload and raised again at set-up.
  - The timer's entities stay where they are. Home Assistant unlinks them if the device itself is removed.
  - A registry entry created for a target that never had one also reloads the timer once.

  Why: #10. Cost if wrong: a user who never opens Repairs sees a timer counting down on nothing.
- [ ] **Step 6: Run** the gate, hassfest and `npm --prefix card run build:check`. Expected: all pass.
- [ ] **Step 7: Commit.** Delete the #10 line from `docs/followups.md`.

```bash
git add custom_components/timerify/issues.py custom_components/timerify/repairs.py custom_components/timerify/controller.py custom_components/timerify/__init__.py custom_components/timerify/translations/en.json custom_components/timerify/translations/ru.json tests/conftest.py tests/test_repairs.py docs/en/timers.md docs/ru/timers.md RULINGS.md docs/followups.md
git commit -m "Raise a repair for a timer whose target was deleted, with a fix that deletes the timer"
```

### Task 7: An unreadable stored timer raises a repair that resets it (#17)

**Files:**
- Modify:
  - `custom_components/timerify/store.py`: `async_load` (`:200-221`) and `_read` (`:223-240`).
  - `custom_components/timerify/issues.py` and `custom_components/timerify/repairs.py`.
  - `custom_components/timerify/__init__.py`: `async_setup_entry` and `async_remove_entry`.
  - `translations/en.json` and `ru.json`: `issues.stored_timer_invalid`, and `exceptions.stored_timer_invalid` (`en.json:435-437`).
  - `docs/en/timers.md` and `docs/ru/timers.md`: "When Home Assistant restarts".
  - `RULINGS.md`.
- Test: `tests/test_repairs.py`, and `tests/test_restart.py:478-497` (the reason text).

**Interfaces:**
- Consumes: `issues.issue_id`, `issues.async_clear` and `async_create_fix_flow` (Task 6), and `TimerStore.async_remove` (`store.py:250-253`).
- Produces:
  - `class StoredTimerInvalid(ConfigEntryError)` in `store.py`. Its `__init__(self, reason: str)` sets `translation_domain=DOMAIN`, `translation_key="stored_timer_invalid"`, `translation_placeholders={"reason": reason}` and `self.reason = reason`. `async_load` raises it for `ValueError` as today, and also for a field that is missing (`KeyError`: reason `f"the field {err.args[0]} is missing"`) or of the wrong type (`TypeError`: reason `str(err)`).
  - `issues.STORED_TIMER_INVALID: Final = "stored_timer_invalid"` and `@callback async_raise_stored_timer_invalid(hass, entry, reason: str) -> None`. It has `translation_placeholders={"timer": entry.title, "reason": reason}` and `data={"entry_id": ..., "kind": "stored_timer_invalid"}`, and otherwise the arguments of Task 6.
  - `async_setup_entry` does the following:
    - on `StoredTimerInvalid` it raises the issue and re-raises, so the entry stays in `SETUP_ERROR` with the same reason;
    - after a good load it clears the issue, because a file that was put right needs no repair;
    - `async_remove_entry` clears it as well.
  - `class ResetStoredTimerFlow(RepairsFlow)` shows a `confirm` form like `DeleteTimerFlow`, and aborts with `timer_gone` the same way. On submit it runs `await TimerStore(hass, entry_id).async_remove()`, then `await hass.config_entries.async_reload(entry_id)`, and returns `async_create_entry(data={})`. The entry, its subentries (the intervals) and the runtime file are kept.
  - `en.json`:
    - `exceptions.stored_timer_invalid.message`: "The stored timer of this entry cannot be used: {reason}. Reset it under Settings > System > Repairs."
    - `issues.stored_timer_invalid.title`: "The stored state of the timer {timer} cannot be read".
    - Its `fix_flow.step.confirm`:
      - title: "Reset the stored timer".
      - description: "Timerify cannot read the file in which the timer {timer} keeps its countdown and pending commands: {reason}. The timer does not run until the file is reset. Resetting keeps the timer, its settings, its schedule intervals and its runtime total. It clears the countdown and the pending commands, and switches every schedule interval back on. Submit to reset it."
    - `fix_flow.abort.timer_gone`: as in Task 6.

- [ ] **Step 1: Write the failing tests** in `tests/test_repairs.py`:

```python
async def test_a_stored_timer_that_cannot_be_read_raises_a_repair(...)
    # setup_target(stored=payload(scheduled_by="a")): entry.state is SETUP_ERROR;
    # issue stored_timer_invalid_<entry_id> with placeholders
    # {"timer": "Boiler", "reason": "the timer is scheduled by an interval but has no end"}

async def test_resetting_the_stored_timer_keeps_the_entry_and_its_intervals(hass, hass_client, repairs, ...)
    # setup_target(runtime=True); interval = add_interval(...06:30-07:15); switch it off;
    # write payload(scheduled_by="a") into hass_storage[storage_key(entry)]; restart: SETUP_ERROR;
    # start_fix / submit_fix: done["type"] == "create_entry"; entry LOADED; interval in entry.subentries;
    # its switch is "on" (the flags were in the file); state_of(NUMBER) == "0";
    # the runtime file is unchanged; the issue is gone

async def test_a_stored_timer_that_is_put_right_clears_the_repair(...)
    # invalid store -> SETUP_ERROR; hass_storage[key]["data"] = payload(); reload: LOADED; the issue is gone

async def test_deleting_a_timer_whose_stored_timer_cannot_be_read_clears_the_repair(...)
    # invalid store; async_remove(entry_id): the issue is gone

async def test_a_stored_timer_missing_a_field_raises_the_same_repair(...)   # Review Focus 4
    # stored = payload(); del stored["commands"]; setup_target(stored=stored): SETUP_ERROR,
    # error_reason_translation_key == "stored_timer_invalid"; the issue's reason == "the field commands is missing";
    # "KeyError" not in caplog.text
```

  Also edit `tests/test_restart.py:494`: `"Remove this timer and add it again"` becomes `"Reset it under Settings > System > Repairs"`.
- [ ] **Step 2: Run** `uv run pytest tests/test_repairs.py tests/test_restart.py -v`. Expected: the new tests and the edited one FAIL.
- [ ] **Step 3: Implement** the interfaces above, with the Russian strings in `ru.json`.
- [ ] **Step 4: Docs.** In `timers.md` (en and ru), "When Home Assistant restarts" gains these bullets:
  - Suppose the file in which Timerify keeps a timer's state cannot be read, for example after a fault. Then the timer does not start.
  - **Settings > System > Repairs** shows "The stored state of the timer Boiler cannot be read".
  - Its fix keeps the timer, its settings, its schedule intervals and its runtime. It clears the countdown and the pending commands, and switches every interval back on.
- [ ] **Step 5: RULINGS.** Add **"An unreadable stored timer is reset only by the user, through a repair, and the reset drops the whole file."** It covers these decisions:
  - A missing field or a wrong type is unreadable too.
  - The entry, its intervals and the runtime file are kept. The countdown, the commands and the interval flags are lost, because nothing in a file that contradicts itself can be trusted.
  - The issue is cleared by a good load and by removing the entry.

  Why: #17. Cost if wrong: a user loses the pending commands of a file that was only partly wrong.
- [ ] **Step 6: Run** the gate, hassfest and `npm --prefix card run build:check`. Expected: all pass.
- [ ] **Step 7: Commit.** Delete the #17 line from `docs/followups.md`.

```bash
git add custom_components/timerify/store.py custom_components/timerify/issues.py custom_components/timerify/repairs.py custom_components/timerify/__init__.py custom_components/timerify/translations/en.json custom_components/timerify/translations/ru.json tests/test_repairs.py tests/test_restart.py docs/en/timers.md docs/ru/timers.md RULINGS.md docs/followups.md
git commit -m "Offer a repair that resets a stored timer that cannot be read"
```

### Task 8: #14 waits on Home Assistant; the full gate

There is no code for #14. Home Assistant 2026.11.0b1 fires no signal when "Reload core configuration" sets the time zone. This was checked read-only in the image `ghcr.io/home-assistant/home-assistant:2026.11.0b1`, in `/usr/src/homeassistant/homeassistant/`:
- `components/homeassistant/services.py:208-221`: `_async_handle_reload_config` calls `core_config.async_process_ha_core_config` and fires nothing.
- `core_config.py:357` and `:437`: `async_process_ha_core_config` sets the zone through `Config.async_set_time_zone` (`:725-731`). That only calls `dt_util.set_default_time_zone` (`util/dt.py:82-93`), which notifies nobody.
- `core_config.py:780-784`: `EVENT_CORE_CONFIG_UPDATE` is fired only by `Config.async_update`, the path of the settings page.
- 2026.10.4 is the same (`.venv`: `core_config.py:355`, `:435`, `:723`, `:778-782`; the service handler is `components/homeassistant/__init__.py:305`).

One "signal" was ruled out. `EVENT_CALL_SERVICE` for `homeassistant.reload_core_config` fires before the handler runs, so the zone has not changed yet. It would be a local workaround, which the spec forbids. Writing to Home Assistant (an issue or a PR in core) needs the owner's consent, which this plan does not have.

**Files:**
- Modify: `RULINGS.md`.

- [ ] **Step 1: Check again** that nothing changed in the image:

```bash
docker run --rm --entrypoint sh ghcr.io/home-assistant/home-assistant:2026.11.0b1 -c \
  'cd /usr/src/homeassistant/homeassistant; grep -n "async_set_time_zone\|EVENT_CORE_CONFIG_UPDATE" core_config.py; grep -n "async_process_ha_core_config" components/homeassistant/services.py'
```

  Expected: `EVENT_CORE_CONFIG_UPDATE` only at `:53` (import) and `:784`, and `async_set_time_zone` at `:437`, `:725` and `:773`. Do not start, stop or restart any other container.
- [ ] **Step 2: Label and comment.** Write the comment to a file in the scratchpad, in English and with no attribution. It lists the four facts above with their file:line, says why `EVENT_CALL_SERVICE` was not used, and says what #14 waits for: Home Assistant firing `EVENT_CORE_CONFIG_UPDATE` (or another signal) when `async_process_ha_core_config` changes the zone. Reporting that upstream needs the owner's consent. Then run:

```bash
gh issue edit 14 --add-label upstream
gh issue comment 14 --body-file <scratchpad>/issue-14-comment.md
```

- [ ] **Step 3: RULINGS.** Add **"Windows keep the old time zone after "Reload core configuration" until Home Assistant signals it (#14, upstream)."** Give the facts in brief and the rejected `EVENT_CALL_SERVICE` workaround. Cost if wrong: after a YAML change of the zone and that reload, windows run in the old zone until a window ends, Workday reports or the timer reloads.
- [ ] **Step 4: Run the full gate on the final tree**:
  - `uv run pytest`, `uv run ruff check`, `uv run ruff format --check` and `uv run mypy`;
  - hassfest;
  - `npm --prefix card ci`, `run build:check`, `run typecheck` and `test`;
  - then compare `date -u +%s` with `docker run --rm alpine date -u +%s`, and run `npm --prefix card run e2e`.

  Expected: all pass. Report the counts of pytest, vitest and E2E, against the 1998 pytest tests of the starting point.
- [ ] **Step 5: Commit.**

```bash
git add RULINGS.md
git commit -m "Record that the time zone after a core configuration reload waits on Home Assistant"
```
