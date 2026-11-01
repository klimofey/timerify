# Follow-ups

Open items that the finished phases did not fix, with where they are as of the end of phase 6.
Each line says what is wrong, why it is not fixed yet, and which phase should take it.
Decisions that were made on purpose are in `RULINGS.md`, not here.

## Before release

- **A renamed Workday sensor is not followed.** The timer keeps its Workday sensor as an
  entity id in its options, and `_follow_target` follows only the target. After a rename
  `workday.check_date` answers "did not match any entities", the windows of working-day and
  non-working-day intervals wait with one warning in the log, and the state listeners sit
  on the old id, so nothing asks again until the user picks the sensor in **Configure** or
  the timer reloads. The fix is the `_follow_target` pattern for a second entity (follow the
  rename and update the option). Found in the review of the Workday task of phase 3 and
  split off; the README states the limit. Take it before the first public release, since the
  repository is built as a product. `custom_components/timerify/__init__.py:92-112`
  (`_follow_target`, the pattern), `custom_components/timerify/controller.py:233` (the
  option) and `:832-844` (`_follow_workday_sensor`, which subscribes to the id).
- **The card can be missing from a browser's first page load on Home Assistant 2026.10.** On
  the first load that the frontend's service worker serves (a first visit, a cold cache, a
  frontend update) the dashboard can show "Configuration error: Custom element doesn't exist:
  timerify-card" until the page is loaded again. It is not a card bug: Home Assistant 2026.10
  starts the app and the modules added with `add_extra_js_url` as independent `import()` calls,
  and a module that defines its element before the app installs its scoped custom element
  registry loses the definition (home-assistant/frontend#53890, fixed by frontend PR #54444 in
  frontend 20261028.0 and later, which Home Assistant 2026.11 is expected to carry). Every card
  added with `add_extra_js_url` is hit; Lovelace resources are not. On 2026.10 no fix uses only
  public APIs, so the owner ruled to document it, keep C1 and change no card code; plan ruling
  19 (the README tells users to refresh the browser once after installing or updating) covers
  it. The question for 1.0.0 is whether to raise the minimum Home Assistant to 2026.11, which
  makes the problem go away: `hacs.json` `homeassistant`, the
  `pytest-homeassistant-custom-component` pin in `pyproject.toml` (`:16`) and the image in
  `scripts/harness/compose.yaml` (`:8`) move together. When the harness runs 2026.11,
  `card/e2e/first-load.spec.ts` passes unexpectedly: remove its `test.fail` (`:30`) and the
  reload after `primeServiceWorker` in `card/e2e/fixtures.ts` (`:157`). The expected failure
  rests on a race the card's module wins against the app's bundle (8 of 8 runs here): on a
  machine where the app's bundle wins, the test can pass unexpectedly on 2026.10 too, and that
  does not mean the frontend fix has arrived.
  `custom_components/timerify/card.py:51` (the registration). Investigation:
  `docs/research/2026-10-31-card-first-load.md`.
- **Bump `happy-dom` from 21.0.3 to 21.0.4.** `npm ci` reports an advisory (GHSA-834v-8h66-3h79,
  an incomplete fix for CVE-2026-33943) against 21.0.3, which 21.0.4 fixes. The package only
  runs the card's tests and is not in the bundle, and every pin must be at least two weeks old
  (`RULINGS.md`, phase 5): 21.0.4 was published on 2026-10-20, so it can be pinned on or after
  2026-11-03. It is a reviewed change of `card/package.json` and `card/package-lock.json`, to be
  made before 1.0.0.

## Later

- **The card's countdown uses the browser's clock, with no offset to the server's.** The time
  left is the server's end time minus `Date.now()`, so a device whose clock is wrong shows a time
  left that is wrong by as much (never below 0:00; the end time shown is the server's). Home
  Assistant's own timer card does the same. A correction would need a reading of the server's
  clock, for example a websocket command that returns it, and it waits until a user needs it,
  since every other card shows the same error. `card/src/timer.ts:78` (`timerView`, which
  takes `now`) and `card/src/timerify-card.ts:270` (`Date.now()`).
- **A timer whose target or sensor cannot be resolved is told to the user as "not the Run for
  number of a Timerify timer".** `timerify/timer` answers `not_found` both when the entity is
  not a timer's number and when it is, but the target is not in the entity registry (a target
  stored as a UUID and then deleted) or a sensor is missing from it; the card has one wording
  for all of them, so in the second case the message is false. It is rare, and the server's own
  message is exact, but the card does not show it. The fix is a second error code that the
  card turns into a neutral line, or one neutral wording; it needs a decision on the code, so it
  waits. `custom_components/timerify/websocket.py:161`, `:166` and `:219` (the three
  `_TimerNotFound` raises) and `card/src/timerify-card.ts:249` (`card_not_a_timer`).
- **`PERCENT_SETTINGS` is a display-only copy of Timerify's knowledge of settings in the
  browser.** The card writes `brightness_pct`, `percentage` and `humidity` as percentages
  because this list says so; a percentage setting added to `domains.py` would be written raw
  until the list is changed too. It is harmless (display only) and a list this short does not
  justify a new key yet. The fix is to send the keys with `timerify/timer`, or to note the list
  in `RULINGS.md` beside the entry "no copy of Timerify's rules". Take it with the next setting
  that is a percentage. `card/src/format.ts:95` (`PERCENT_SETTINGS`) and `:110` (its use).
- **The editor's labels come from the last strings a card loaded.** The names of the layouts,
  the labels of the preset options and the helper under them are in the language of
  `lastLoaded()`, because the form that Home Assistant builds is given no way to translate them
  and `getConfigForm` runs without `hass`. In a session where the editor opens before any card
  has loaded its strings they are in English. The field labels use the frontend's own
  `localize` and are not affected. A frontend that translates a form's option labels itself
  would make `speaking()` unnecessary. `card/src/editor.ts:66-68` (`speaking`).
- **`card/src/popup.ts` is about 610 lines, about 200 of them the styles.** It is one element
  with one job and is left whole while it does not grow. If it grows, move the styles out
  first, then the parser of the commands the "Next command" sensor lists, and give the
  schedule and the commands their own elements last. `card/src/popup.ts:79` (`styles`), `:35`
  (`pendingCommands`) and `:520` (`#commands`).
- **A deleted target gives no sign.** `er.async_resolve_entity_id` returns the id even when the
  entity is gone from the registry, so a timer whose target was deleted still loads and drives
  nothing, with no message. `custom_components/timerify/controller.py:212-217`. It needs a
  repairs issue; the spec is silent and no spec-defined behaviour changes, so it waits for a
  later phase.
- **A device that answers each refused call with `unknown` and then its old state is re-sent
  without end.** Each cycle is a real state change, which resets the allowance of automatic
  re-sends by design. Not a regression (phase 1 before the cap behaved the same). A per-wish
  total limit would close it. A contradicting report of our own call is not part of it:
  it is corrected once for each wish that was settled without a call (the entry "A report
  of our own call that contradicts the timer" in `RULINGS.md`), and a correction that
  does not land is an ordinary unsent wish. `custom_components/timerify/core.py:570-573`
  (the reset in `observe`) and `:923-936` (`_resend`).
- **The give-up warning is logged once per allowance, not once per wish.** A refusing target
  that keeps dropping off Wi-Fi logs one warning per reconnect. Bounded by the reconnects.
  `custom_components/timerify/controller.py:1012-1031` (`_log_gave_up`) and
  `custom_components/timerify/core.py:255-280` (`_Allowance`).
- **`type Actual` has no runtime arguments.** `typing.get_args(Actual)` is `()` because the alias
  is a PEP 695 `type`; use `Actual.__value__` if the values are ever enumerated (for example
  to validate stored data). `custom_components/timerify/domains.py:55`. Do it when needed.
- **Device following is one-way for targets without a device.** A target that gains or loses a
  device is followed, but the fallback device made for a target without one can stay behind
  after the target is linked to a device on a restart.
  `custom_components/timerify/__init__.py:92-112` (`_follow_target`).
- **The options keep a stale default duration after strict to loose.** Harmless: loose mode
  ignores it and it is the prefill when the user switches back.
  `custom_components/timerify/config_flow.py:286-288` (`_after_mode`) and `:443-448`
  (`OPTIONS_FLOW`).
- **One "before started" rule for every command.** Before Home Assistant has started, a
  change folds stored items against a target that has not been seen. A phase-2 command
  (`set_duration`, `add`, `run_open`) returns the alarm of whatever the snapshot waits for,
  and `next_wakeup` includes stored ends, commands and windows that have long passed, so a
  past alarm fires at once and runs a whole fold; the flip of an interval ticks (off) or
  refreshes the windows (on); and the target's reports are followed from `async_start` on.
  It converges, because a wish sent to a target that is not there yet fails, is marked
  unsent, and the first observation sends it again, but it is the opposite of what
  `_handle_started` takes care to avoid. The fix is one policy for the whole controller:
  until `_handle_started` has run, a command records its change and saves it, arms nothing
  and leaves the folding to `_handle_started`. A guard on the interval switch alone would
  be a special case, so it waits for the policy.
  `custom_components/timerify/controller.py:277-285` (`async_start`), `:462-477` and
  `:571-588` (`async_set_interval_enabled` and the `_async_set_interval_enabled_locked` it
  calls), `:601-610` (`_command`) and `:798-830` (`_handle_started`), and
  `custom_components/timerify/core.py:158-169` (`next_wakeup`).
- **The R10 lines are not written by the folds of start-up and of a report of the target.**
  `_fold_due` (the alarm, the refresh of the windows and the switching off of an interval)
  says what came due while the target is unavailable: the countdown that ended, the command
  that came due, the window that started. `_handle_started` and `_handle_state_change` fold
  through `_execute_fold` alone and say nothing, so a window or command that came due
  during downtime, found at start-up with the target unavailable, is applied when it is
  back without a line in the log. The phase-2 lines have the same gap. It changes no
  behaviour. `custom_components/timerify/controller.py:867-875` (`_fold_due`), `:894-939`
  (`_log_due_while_unavailable`), `:798-830` (`_handle_started`) and `:849-859`
  (`_handle_state_change`).
- **A time zone changed in YAML is not noticed.** Changing the zone in the settings fires
  `EVENT_CORE_CONFIG_UPDATE`, which the controller listens to, but `configuration.yaml`
  applied with "Reload core configuration" sets the zone through `async_set_time_zone`
  (`async_process_ha_core_config`) without that event. The windows keep the old zone until
  a window ends, the Workday sensor reports or the timer reloads. It needs a signal that
  Home Assistant does not fire for this path; look for one before working around it.
  `custom_components/timerify/controller.py:792-796` (`_handle_core_config_update`) and
  `:810-814` (where it is subscribed, in `_handle_started`).
- **An old generated title stays in the old language.** An edit renames an interval only if
  its title is still the one generated from its old data in the current language; after the
  house language changes the old title no longer matches and is kept as if the user had
  chosen it. A stored mark that the title was generated would end it. Subentry titles are
  plain strings today. `custom_components/timerify/config_flow.py:537-538`.
- **Settings that the target no longer supports are dropped silently on the next edit.** The
  form offers only what the target can do now, so a stored setting that is no longer
  offered is missing from the submitted form and from the saved interval, with no message.
  `custom_components/timerify/config_flow.py:554-600` (`_interval_schema`, the section) and
  `:602-644` (`_interval_from`).
- **A store file that contradicts itself fails the timer, and the interface cannot repair
  it.** `_validated` refuses a file that no timer could have written (two windows of one
  interval, a window that is suppressed but has not started, and so on), which means a
  defect, and the entry stays failed with a reason in words (`stored_timer_invalid`). The
  only way out is to delete the timer and add it again, which loses its commands and the
  flags of its intervals. A repairs issue with a "reset the stored timer" fix would do.
  `custom_components/timerify/store.py:85-114` (`_validated`) and `:200-220` (`async_load`).
- **A pending command keeps the settings it was made with.** The settings of an interval's
  window are checked again when the window is worked out, and the ones the target no longer
  takes are left out (`RULINGS.md`), but a command is checked only when it is made.
  Made days ahead for an AC whose integration then renames a mode, it fails on that mode
  when it comes due, and the log says so at every attempt. The fix is the same filter
  where the calls are made (`_execute`), which covers the owed settings of every origin;
  it is not a phase 3 regression, so it waits.
  `custom_components/timerify/controller.py:358` (`async_add_command`, the check) and
  `:946-988` (`_execute`, where the calls are made).
- **The settings of an interval are checked when its window is worked out, not when the
  call is made.** A target that reports no capabilities for a moment (some cloud climates
  while they connect) gets a window built without its settings, and keeps it until the
  next refresh, which for a weekday interval is the window's end; the warning says so
  once. Checking in `_execute`, where the calls are made, would close it, and it is the
  same filter as for the pending commands above, so the two go together.
  `custom_components/timerify/controller.py:663-697` (`_with_settings_the_target_takes`).
- **The reason in the Russian `stored_timer_invalid` message is English.** `{reason}` is
  the text of the `ValueError` of the store, which is for the bug report of a defect
  (`RULINGS.md`), so it is not translated. Translating it would mean a key for each of
  the checks of `_validated` and of `checked_window`, which is not worth it for a message
  that a file written by Timerify alone cannot cause.
  `custom_components/timerify/store.py:200-220` (`async_load`) and
  `custom_components/timerify/translations/ru.json:435-437`.
- **Brand icon missing.** `custom_components/timerify/brand/icon.png` does not exist, so the
  HACS brand check and Home Assistant's integrations page show no logo. Add it in the final
  release phase.
- **Voice commands at a clock time.** "Turn on the boiler at 7:30" has no sentence: the
  built-in agent's sentences take a delay ("in 15 minutes") only, and the spec's example is
  a delay. An LLM can plan a command at a clock time (the tool's `at`, read by the same
  parser as the `timerify.add_command` service), so the controller already has the path;
  what is missing is a grammar of clock times in both languages (a 24-hour and a 12-hour
  clock, "tomorrow at", the day change) that does not collide with core's own shapes. It
  waits for a phase that can test every spoken form of a time in both languages.
  `custom_components/timerify/voice/commands.py:31-111` (`DelayedCommandHandler`) and
  `:136-150` (`_clock_time_of`, which only the tool feeds), and
  `scripts/generate_core_commands.py:385-418` (`_delayed_blocks`, where the delayed
  sentences are made).
- **A target that is not in the entity registry: a changed friendly name is listed only
  after its timer reloads.** The sentence file is written again when an entity or a device
  of a target changes in the registries, which a target of a YAML entity with no
  `unique_id` does not have; its name is its state's `friendly_name`, and a change of it
  reaches the file at the next change of any timer or a restart. The same holds for a
  device that changes its own list of modes (a firmware update). The fix is to follow the
  `state_changed` events of the targets when the name or the modes differ from the ones
  last written. The managed entry is the only one affected; the manual route is redone by
  hand anyway. `custom_components/timerify/voice/files.py:357-378` (`_entity_updated`,
  `_device_updated`, the only triggers) and `custom_components/timerify/voice/sentences.py:156-181`
  (`voice_names`, the name of a target with no registry entry).
- **A one-time repair issue listing interval switches exposed under 0.3.0.** Version 0.3.0
  made the switch of an interval an ordinary switch, and Home Assistant exposed it to Assist
  the first time it saw it. From 0.4.0 it is an entity of the configuration category,
  which Home Assistant does not expose by default, but the decision it stored for the
  entity stays, so an upgraded house keeps exposing them: "turn off Schedule 06:30 to 07:15"
  works, and the entity is offered to an LLM agent. The README tells how to take them
  away. A repairs issue at set-up that names the exposed ones and offers to unexpose them
  would do it for the user. `custom_components/timerify/switch.py:33-81` (`IntervalSwitch`,
  `entity_category` at line 47).
- **An unavailable target with no timer is answered "off".** "How long is left on the
  boiler" says "Boiler is off and has no timer" for a target that is unavailable and is not
  wanted on, since the answer reports the timer's wish (`RULINGS.md`, "An answer says what
  the timer is set to do, not what the device shows"), and a wish is on or off. A third
  wording for an unavailable target (and the same in Russian) would say what is known.
  `custom_components/timerify/voice/base.py:246-277` (`timer_slots`, its state `off`) and
  `custom_components/timerify/sentences/en/src/timerify.yaml:201-209` (the answer, and the
  Russian twin).
- **Wider English near-misses that name a device with a timer can reach core's turn off.**
  Timerify's sentences take the phrasings it knows, and a phrasing that it does not have,
  with "turn on" or "turn off" and the name of a timer's device, can be matched by core's
  gazetteer, which looks for any device name in the text ("turn off scheduling for the
  boiler" turns the boiler off and says nothing of a schedule; so does "turn off the boiler
  in 2 days", since core has no delayed shape in days and a delay of days is a natural
  thing to say). The near-misses found in
  review ("the schedule of the boiler off", "deactivate the schedule") were added as
  sentences, but the set is open ended. Home Assistant has no hook to keep a custom
  sentence out of that fallback, so the fix is the cost of listing more phrasings, or a
  request to core. Russian has no gazetteer. `custom_components/timerify/sentences/en/src/timerify.yaml:86-117`
  (the schedule sentences) and `custom_components/timerify/sentences/en/core_commands.yaml`
  (generated).
- **An interval with its generated title cannot be said to the built-in agent.** The title
  an interval is given when it is made, `06:30-07:15, Mon-Sun`, is a string that no speech
  recogniser produces, so by voice such an interval is switched only with the whole schedule,
  and the README tells the owner to give intervals titles of their own. An LLM can use it
  (a hyphen matches the dash of the title). A spoken form of the generated title ("the
  6:30 schedule") would need the times and the days in words in both languages.
  `custom_components/timerify/voice/sentences.py:185-201` (`interval_names`, which lists the
  titles), `custom_components/timerify/schedule.py:128-141` (`interval_title`) and `:158-171`
  (`title_key`).
- **Voice names and titles do not fold the Russian letter yo.** Said as "elka", a name
  or an interval title "Yolka" is not matched, as the letter is in the file as it is
  written; the LLM path folds it (`title_key`). The fix is to list both spellings of a
  value, or to fold in the file and in the matching, so it waits for a decision about
  both. `custom_components/timerify/voice/sentences.py:121-130` (`spoken_form` and
  `spoken_mode`).
- **A Russian speaker says the modes a device names in Latin as they are written.** The
  values of a fan's preset, a humidifier's mode or a thermostat's fan mode are the strings
  the device gives ("eco", "high"), and the list holds them as they are, with underscores
  said as spaces; only the HVAC modes have Russian words. Home Assistant has translations
  of the states of `fan_mode` and `preset_mode` that could supply the words. `custom_components/timerify/voice/sentences.py:127-130`
  (`spoken_mode`) and `:273-281` (`_mode_values`).
- **Two thermostats with different HVAC modes: the words are those of all of them.** The
  list of HVAC words is the union over the timers, so "turn on the AC for an hour, auto"
  said of an AC that has no auto mode, while another AC has it, is understood and then
  refused truthfully with the modes that AC has ("fan auto" and "in auto mode" still reach
  the fan mode). The clean fix is one climate block of sentences per distinct set of HVAC
  modes, with the set in the name's context; it multiplies the sentences and is its own
  step. `custom_components/timerify/voice/sentences.py:205-217` (`voice_setting_values`) and
  `custom_components/timerify/sentences/en/src/timerify.yaml:26-59` (the blocks of
  `TimerifyRun`, scoped by domain, with the list of HVAC words at `:180`).
- **"For 1 hour 30" on a device that has no temperature is not understood.** A bare number
  after a duration is a temperature only for a thermostat or a water heater, since it is
  the spec's own "cooling, 24" with no unit; said of a switch it matches nothing of the
  duration, and the answer is "Sorry, I am not aware of any device called boiler": a
  sentence of Timerify's wins the stage for unknown names, so a device that exists is
  said to be unknown (the same wording as for a fan with no timer). Reading "1 hour 30" as
  ninety minutes for the others would be a sentence of its own in both languages, and
  would remove the wording with the case.
  `custom_components/timerify/sentences/en/src/timerify.yaml:26-59` (the data blocks scoped
  by domain) and `:133` (`timerify_temperature_part`).
- **A delay said by voice is at most 100 hours, 100 minutes and 100 seconds, each.** The
  delayed commands take Home Assistant's own number lists for the delay (`timer_hours`,
  `timer_minutes` and `timer_seconds`, 1 to 100 in both languages), so "turn off the boiler
  in 2000 minutes" is answered "Sorry, I couldn't understand that", and so is "in 120
  minutes", though a turn-off may be a day ahead and a turn-on a week ahead through the
  tools and the services, which is what the README says of the limits. The user hears no
  limit. The fix is delay lists of Timerify's own, digits only past what a table of words
  can bear (as `timerify_long_minutes` is, see the duration entry of RULINGS), and the
  refusal that names the limit. `scripts/generate_core_commands.py:107` (`_DELAY_SLOT`)
  and `:282`, which name core's lists in `sentences/<language>/core_commands.yaml:4-5`.

## Tests

- **The slow-call tests start the controller directly.** They use `asyncio.ensure_future` on
  `controller.async_set_minutes` or `async_run` instead of the user's path, a `number.set_value`
  or `timerify.run` call in a task, as the newer slow-call test in `tests/test_entities.py:287` does.
  Instances: `tests/test_entities.py:250`, `:252`, `:274`, `:276`, `:459`, `:571`,
  `tests/test_restart.py:554`, `:735`, `:760` and `tests/test_settings.py:316`.
- **The voice tests need Cyrillic that they may not hold.** The hook forbids Cyrillic in
  tests, so Russian sentences are proved by sampling the shipped files and the plural
  forms by their classes, which shows that every template parses, reaches its handler and
  outranks core, and that the three forms partition the counts, but not which word goes
  with which class. A swapped "few" and "many" passes. The owner reads the rendered texts
  (the checklist of phase 4), and a fixture file of rendered answers, which the hook would
  allow under `sentences/ru/`, would pin them. `tests/voice/test_time_left.py:345-355` and
  `tests/voice/helpers.py:366` (`assert_one_form_per_class`).
- **The recorder tests repeat two autouse fixtures.** `tests/test_runtime_statistics.py:30-46`
  copies `auto_enable_custom_integrations` (with `recorder_db_url`, so that the recorder's
  database is ready before Home Assistant loads the custom integration) and `quiet_sql_engine`
  (which keeps the recorder's SQL out of the output) from `tests/test_recorder.py:19-39`. Two
  modules do not justify a shared module, and the statistics test did not touch the older one.
  When a third recorder module appears, or a task names `tests/test_recorder.py`, move both
  fixtures into one shared module and delete the copies.

## Accepted

- **`timerify/timer` has no `runtime` key.** Decided, not fixed: the Runtime sensor of phase 6
  is not one of the entities the card reads, because the card shows actions and the countdown,
  not the runtime, and a key that nobody reads is dead weight (`RULINGS.md`, phase 6, "Neither
  `timerify/timer` nor the card gets a `runtime` key in this phase"). A card feature that shows
  the runtime adds the key in three places together:
  `custom_components/timerify/websocket.py:75-96` (`TimerInfo`), `card/src/hass.ts:70-90`
  (`TimerInfo`) and `card/src/timer.ts:122` (`watchedEntities`).
- **`TimerInfo.mode` and `default_duration` are carried and never read by the card.** Decided,
  not fixed: the contract (C3) asks for them, so it is not a defect, and the occasion this item
  waited for, a `runtime` key that would change the same answer, did not come (`RULINGS.md`,
  phase 6, "Neither `timerify/timer` nor the card gets a `runtime` key in this phase"). They
  stay as they are; reconsider them with the first card feature that changes the answer.
  `card/src/hass.ts:73` and `:75`,
  `custom_components/timerify/websocket.py:80` and `:81`.
- **`services.yaml` hard-codes the limits.** The ranges of `add_time` (plus and minus 1440,
  `custom_components/timerify/services.yaml:12-13`), of the minutes of `run` (`:27-28`) and of
  `add_command` (`:127-128`) and of its delay (1 to 10080, `:114-115`) are written there as well
  as in `const.MAX_MINUTES` and `const.MAX_DELAY_MINUTES`; the test
  `test_services_are_described_for_the_ui` (`tests/test_services.py:401`) fails when they drift.
- **A deleted interval is still worked out until the timer reloads.** Deleting an interval
  reloads the timer at once, which lets it go; only a reload that waits behind another setup
  leaves the timer that is loaded with it, and for that time a window of it can be worked
  out and opened. The commands that name an interval, and the warning about its settings,
  already treat it as gone (`async_set_schedule_enabled`, `_with_settings_the_target_takes`),
  and the reload drops its window (`TimerCore.set_windows`, `configured`). Accepted: the
  window is short, and the fix would be a second judgement of which intervals exist.
