# Follow-ups

Open items that the finished phases did not fix, with where they are as of the end of phase 4.
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
  repository is built as a product. `custom_components/timerify/__init__.py:86-106`
  (`_follow_target`, the pattern), `custom_components/timerify/controller.py:236` (the
  option) and `:811-823` (`_follow_workday_sensor`, which subscribes to the id).

## Later

- **A deleted target gives no sign.** `er.async_resolve_entity_id` returns the id even when the
  entity is gone from the registry, so a timer whose target was deleted still loads and drives
  nothing, with no message. `custom_components/timerify/controller.py:213-217`. It needs a
  repairs issue; the spec is silent and no spec-defined behaviour changes, so it waits for a
  later phase.
- **A device that answers each refused call with `unknown` and then its old state is re-sent
  without end.** Each cycle is a real state change, which resets the allowance of automatic
  re-sends by design. Not a regression (phase 1 before the cap behaved the same). A per-wish
  total limit would close it. A contradicting report of our own call is not part of it:
  it is corrected once for each wish that was settled without a call (the entry "A report
  of our own call that contradicts the timer" in `RULINGS.md`), and a correction that
  does not land is an ordinary unsent wish. `custom_components/timerify/core.py:556-560`
  (the reset in `observe`) and `:872-885` (`_resend`).
- **The give-up warning is logged once per allowance, not once per wish.** A refusing target
  that keeps dropping off Wi-Fi logs one warning per reconnect. Bounded by the reconnects.
  `custom_components/timerify/controller.py:990-1009` (`_log_gave_up`) and
  `custom_components/timerify/core.py:251-276` (`_Allowance`).
- **`type Actual` has no runtime arguments.** `typing.get_args(Actual)` is `()` because the alias
  is a PEP 695 `type`; use `Actual.__value__` if the values are ever enumerated (for example
  to validate stored data). `custom_components/timerify/domains.py:55`. Do it when needed.
- **Device following is one-way for targets without a device.** A target that gains or loses a
  device is followed, but the fallback device made for a target without one can stay behind
  after the target is linked to a device on a restart.
  `custom_components/timerify/__init__.py:86-106` (`_follow_target`).
- **The options keep a stale default duration after strict to loose.** Harmless: loose mode
  ignores it and it is the prefill when the user switches back.
  `custom_components/timerify/config_flow.py:279-281` (`_after_mode`) and `:427-432`
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
  `custom_components/timerify/controller.py:274-282` (`async_start`), `:452-467` and
  `:553-570` (`async_set_interval_enabled` and the `_async_set_interval_enabled_locked` it
  calls), `:583-592` (`_command`) and `:777-809` (`_handle_started`), and
  `custom_components/timerify/core.py:154-165` (`next_wakeup`).
- **The R10 lines are not written by the folds of start-up and of a report of the target.**
  `_fold_due` (the alarm, the refresh of the windows and the switching off of an interval)
  says what came due while the target is unavailable: the countdown that ended, the command
  that came due, the window that started. `_handle_started` and `_handle_state_change` fold
  through `_execute_fold` alone and say nothing, so a window or command that came due
  during downtime, found at start-up with the target unavailable, is applied when it is
  back without a line in the log. The phase-2 lines have the same gap. It changes no
  behaviour. `custom_components/timerify/controller.py:846-854` (`_fold_due`), `:873-918`
  (`_log_due_while_unavailable`), `:777-809` (`_handle_started`) and `:828-838`
  (`_handle_state_change`).
- **A time zone changed in YAML is not noticed.** Changing the zone in the settings fires
  `EVENT_CORE_CONFIG_UPDATE`, which the controller listens to, but `configuration.yaml`
  applied with "Reload core configuration" sets the zone through `async_set_time_zone`
  (`async_process_ha_core_config`) without that event. The windows keep the old zone until
  a window ends, the Workday sensor reports or the timer reloads. It needs a signal that
  Home Assistant does not fire for this path; look for one before working around it.
  `custom_components/timerify/controller.py:771-775` (`_handle_core_config_update`) and
  `:788-792` (where it is subscribed, in `_handle_started`).
- **An old generated title stays in the old language.** An edit renames an interval only if
  its title is still the one generated from its old data in the current language; after the
  house language changes the old title no longer matches and is kept as if the user had
  chosen it. A stored mark that the title was generated would end it. Subentry titles are
  plain strings today. `custom_components/timerify/config_flow.py:521-522`.
- **Settings that the target no longer supports are dropped silently on the next edit.** The
  form offers only what the target can do now, so a stored setting that is no longer
  offered is missing from the submitted form and from the saved interval, with no message.
  `custom_components/timerify/config_flow.py:538-584` (`_interval_schema`, the section) and
  `:586-628` (`_interval_from`).
- **A store file that contradicts itself fails the timer, and the interface cannot repair
  it.** `_validated` refuses a file that no timer could have written (two windows of one
  interval, a window that is suppressed but has not started, and so on), which means a
  defect, and the entry stays failed with a reason in words (`stored_timer_invalid`). The
  only way out is to delete the timer and add it again, which loses its commands and the
  flags of its intervals. A repairs issue with a "reset the stored timer" fix would do.
  `custom_components/timerify/store.py:65-89` (`_validated`) and `:169-189` (`async_load`).
- **A pending command keeps the settings it was made with.** The settings of an interval's
  window are checked again when the window is worked out, and the ones the target no longer
  takes are left out (`RULINGS.md`), but a command is checked only when it is made.
  Made days ahead for an AC whose integration then renames a mode, it fails on that mode
  when it comes due, and the log says so at every attempt. The fix is the same filter
  where the calls are made (`_execute`), which covers the owed settings of every origin;
  it is not a phase 3 regression, so it waits.
  `custom_components/timerify/controller.py:348` (`async_add_command`, the check) and
  `:925-967` (`_execute`, where the calls are made).
- **The settings of an interval are checked when its window is worked out, not when the
  call is made.** A target that reports no capabilities for a moment (some cloud climates
  while they connect) gets a window built without its settings, and keeps it until the
  next refresh, which for a weekday interval is the window's end; the warning says so
  once. Checking in `_execute`, where the calls are made, would close it, and it is the
  same filter as for the pending commands above, so the two go together.
  `custom_components/timerify/controller.py:645-676` (`_with_settings_the_target_takes`).
- **The reason in the Russian `stored_timer_invalid` message is English.** `{reason}` is
  the text of the `ValueError` of the store, which is for the bug report of a defect
  (`RULINGS.md`), so it is not translated. Translating it would mean a key for each of
  the checks of `_validated` and of `checked_window`, which is not worth it for a message
  that a file written by Timerify alone cannot cause.
  `custom_components/timerify/store.py:169-189` (`async_load`) and
  `custom_components/timerify/translations/ru.json:423-425`.
- **The store does not check the offset of the stored end and of the time of a command.**
  A window is read through `checked_window`, which refuses a time with no offset; the
  end of the countdown and the `at` of a command are read as they are, so a naive one
  from a hand-edited file raises in the first fold instead of when the timer loads.
  Only a hand-edited file can hold one, because the store writes UTC. The fix is one
  helper in the store that reads a time and refuses a naive one, used by the three.
  `custom_components/timerify/store.py:27-34` (`_command_from_json`) and `:192-206`
  (`_read`, the end).
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
  `scripts/generate_core_commands.py:385-420` (`_delayed_blocks`, where the delayed
  sentences are made).
- **A target that is not in the entity registry: a changed friendly name is listed only
  after its timer reloads.** The sentence file is written again when an entity or a device
  of a target changes in the registries, which a target of a YAML entity with no
  `unique_id` does not have; its name is its state's `friendly_name`, and a change of it
  reaches the file at the next change of any timer or a restart. The same holds for a
  device that changes its own list of modes (a firmware update). The fix is to follow the
  `state_changed` events of the targets when the name or the modes differ from the ones
  last written. The managed entry is the only one affected; the manual route is redone by
  hand anyway. `custom_components/timerify/voice/files.py:333-354` (`_entity_updated`,
  `_device_updated`, the only triggers) and `custom_components/timerify/voice/sentences.py:156-181`
  (`voice_names`, the name of a target with no registry entry).
- **A one-time repair issue listing interval switches exposed under 0.3.0.** Version 0.3.0
  made the switch of an interval an ordinary switch, and Home Assistant exposed it to Assist
  the first time it saw it. From 0.4.0 it is an entity of the configuration category,
  which Home Assistant does not expose by default, but the decision it stored for the
  entity stays, so an upgraded house keeps exposing them: "turn off Schedule 06:30 to 07:15"
  works, and the entity is offered to an LLM agent. The README tells how to take them
  away. A repairs issue at set-up that names the exposed ones and offers to unexpose them
  would do it for the user. `custom_components/timerify/switch.py:33-79` (`IntervalSwitch`,
  `entity_category` at line 47).
- **An unavailable target with no timer is answered "off".** "How long is left on the
  boiler" says "Boiler is off and has no timer" for a target that is unavailable and is not
  wanted on, since the answer reports the timer's wish (`RULINGS.md`, "Answers state what
  the timer wants"), and a wish is on or off. A third wording for an unavailable target
  (and the same in Russian) would say what is known. `custom_components/timerify/voice/base.py:246-278`
  (`timer_slots`, its state `off`) and `custom_components/timerify/sentences/en/src/timerify.yaml:184-192`
  (the answer, and the Russian twin).
- **Wider English near-misses that name a device with a timer can reach core's turn off.**
  Timerify's sentences take the phrasings it knows, and a phrasing that it does not have,
  with "turn on" or "turn off" and the name of a timer's device, can be matched by core's
  gazetteer, which looks for any device name in the text ("turn off scheduling for the
  boiler" turns the boiler off and says nothing of a schedule). The near-misses found in
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
  titles), `custom_components/timerify/schedule.py:128-155` (`interval_title`) and `:158-174`
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
  `TimerifyRun`, scoped by domain, with the list of HVAC words at `:163`).
- **"For 1 hour 30" on a device that has no temperature is not understood.** A bare number
  after a duration is a temperature only for a thermostat or a water heater, since it is
  the spec's own "cooling, 24" with no unit; said of a switch it matches nothing, and the
  built-in agent answers that it did not understand, which is true. Reading "1 hour 30" as
  ninety minutes for the others would be a sentence of its own in both languages.
  `custom_components/timerify/sentences/en/src/timerify.yaml:26-59` (the data blocks scoped
  by domain) and `:132` (`timerify_temperature_part`).
- **A directory at the path of the managed file stops the check of who owns it.**
  `_first_line` reads the first line of the file and treats only a missing file as
  nothing; a directory (or a file that cannot be read) at `custom_sentences/<language>/timerify.yaml`
  raises `IsADirectoryError` or `PermissionError` out of the writing of that language.
  It should count as a file that is not Timerify's: not written, and the warning that
  names the path. `custom_components/timerify/voice/files.py:99-107`.

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
- **The translation markup test claims to be the check hassfest makes.** It runs Home
  Assistant's `string_with_no_html` on every text, which is the check that hassfest failed
  a string on, but hassfest checks the same strings in other ways too (the review named
  placeholders in single quotes, space at either end, and links written as URLs). The
  docstring should say what it checks, or the other checks should be added, and the
  hassfest run stays the proof. `tests/test_translations.py:79-82`.
- **One generator test reads the sources with another loader than the product.**
  `test_shipped_answers_are_blocks_not_lines_of_escapes` reads each source file with
  `load_yaml_dict` while the product reads them with `voice.sentences.load_sources`; both
  read the same files today, but a test that reads as the product does cannot drift from
  it. `tests/voice/test_sentence_generator.py:11` (the import) and `:77`.
- **The suite runs serially.** The full run takes about a minute and a half, and
  `tests/voice` alone about a minute. `pytest-xdist` 3.8.0 is already in `uv.lock`, brought
  by `pytest-homeassistant-custom-component`, and `uv run pytest -n 6` passed all of the
  suite three times in a row in about 22 seconds on an 18-core machine. It is not on by
  default: it is a transitive dependency, not one of the dev group; the per-test
  timeout and the load of a small machine have not been tried with more workers than
  cores; and "the full local run on the final tree" stays the gate, whichever way it
  runs. To take it, name `pytest-xdist` in the dev group, decide the worker count (a
  fixed one, not `auto`), and say so in `CLAUDE.md` and the README. `pyproject.toml:28`
  (`timeout`) and `pyproject.toml:10-19` (the dev group).

## Accepted

- **`services.yaml` hard-codes the limits.** The ranges of `add_time` (plus and minus 1440,
  `custom_components/timerify/services.yaml:12-13`), of the minutes of `run` (`:27-28`) and of
  `add_command` (`:127-128`) and of its delay (1 to 10080, `:114-115`) are written there as well
  as in `const.MAX_MINUTES` and `const.MAX_DELAY_MINUTES`; the test
  `test_services_are_described_for_the_ui` (`tests/test_services.py:401`) fails when they drift.
