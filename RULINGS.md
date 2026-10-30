# Rulings

Decisions made where the spec (`docs/superpowers/specs/2026-10-28-timerify-design.md`) is
silent or its plan was wrong, recorded so they can be revisited. Each entry: what was
decided, why, and what it costs if it turns out wrong. Process decisions (branching,
tooling) are not listed; only decisions that shape the product or its code.

An entry of an earlier phase that a later phase changed is rewritten to what holds now,
not repeated beside its successor.

## Phase 1: core timer

### Targets

- **Groups switch through `homeassistant.turn_on` / `turn_off`.** The `group` domain has
  no `turn_on` / `turn_off` services of its own in Home Assistant 2026.10.4. Cost if wrong:
  none; a test checks the services against the installed version.
- **Domains outside the table use the generic fallback** of spec §5.4:
  `homeassistant.turn_on` / `turn_off`, "on" means the state `on`, no required features,
  no settings. The `group` row is this fallback itself. The picker offers the table's
  domains and every other domain that has both a `turn_on` and a `turn_off` service
  (`hass.services`), except `homeassistant` itself; an entity of a domain with only one of
  the two is `target_not_supported`. Why: the table stays a list of exceptions, and a
  domain is added by a row, not by new code paths. The fallback reads every state but `on`
  as off, so it would misread a group of covers or locks (`open`, `locked`): a fallback
  entity or a group whose state is not `on` or `off` when the timer is added is
  `not_switchable`, and so is one that is unavailable or has no state then (the row
  field `judged_by_state`, set on the fallback). Entities of the table's other rows are
  never judged by state (a switch may be unavailable at setup). The picker cannot filter
  by state, so it shows cameras (they have both services) and refuses them on submit as
  `not_switchable`; vacuums are not offered at all because they have no `turn_on` /
  `turn_off` in 2026.10.4. Cost if wrong: a group of covers or locks, and a fallback
  entity that is unavailable while it is added, cannot be targets; the user tries again
  once the entity is back.
- **Climate, water heater, fan, media player and siren targets are filtered by their
  features.** Climate needs `ClimateEntityFeature.TURN_ON` and `TURN_OFF`; water heaters
  need `WaterHeaterEntityFeature.ON_OFF`; fans, media players and sirens need their
  `TURN_ON` and `TURN_OFF`. Their `turn_on` / `turn_off` services require exactly these
  features in 2026.10.4, so phase 1, which accepted fans, media players and sirens
  without a check, accepted targets it could not switch. The required features are a field
  of the domain table and the config flow reads them there, so "can be switched" has one
  home. Cost if wrong: a device that advertises no features but works is refused.
- **Climate without `TURN_ON` stays unsupported**, although `set_hvac_mode` (which needs
  no feature) could turn it on: a plain run without a mode would have nothing to send.
  Such thermostats wait for a later "turn on with a default mode" option.
- **A target missing at setup fails the entry** with `ConfigEntryError`
  (`target_not_found`), so Home Assistant shows the entry as failed and retries on reload.
  A target deleted later is not noticed yet; see `docs/followups.md`.

### The timer

- **A rejected command is retried, an in-flight one is not repeated.** A failed or timed
  out call marks the wish to turn on or off as unsent (in memory only); it is sent again
  when the target next reports its state, or by the next command that wants the same
  thing. A call that returns without error while the target still shows the old state
  counts as not delivered too, so a device that acknowledges and ignores a command (an MQTT
  switch out of range, a cloud integration that only acknowledges) is sent it again. This
  is how "pending commands are firm promises" holds. Cost if wrong: a device that confirms
  its state only after the call returns may get one duplicate, idempotent command.
  Reports that merely repeat the target's state send an unsent wish at most
  `automatic_resends` times, a field of the domain row: `MAX_AUTOMATIC_RESENDS` (three)
  for every row except `remote` and `media_player`, which get none. Then one warning is
  logged and nothing more is sent; the count starts again when the target's state changes
  (including a return from unavailable and start-up) or when a command wants the wish,
  which always sends. Without the bound, a device that refuses a command and answers it
  with a report of its old state would be commanded for ever. Remotes and media players
  get none because a toggle-based remote can be switched back off by a repeat and a media
  player that is still booting reports a state that is not on; they are sent the command
  again on a state change or a command. Cost if wrong: an ignoring media player is retried
  only then.
- **A report of our own call that contradicts the timer, with no wish pending, is a wish
  that has not landed, and the core asks for the state it wished again, once for each
  wish that was settled without a call.** A call that the device accepted but does not
  show yet counts as not delivered (above), so a newer wish for the state the target
  still shows is settled with nothing sent. The older call then lands, and its report,
  which carries our context, leaves the target the opposite of the timer: an interval
  switched off and on again within the report lag of a cloud device, "Run for 0" and at
  once "Run for 30", a start and at once a stop. R6 says our own report is not "someone
  else"; without this rule it was also not "us", and nothing corrected the target until
  some other change came. The core now keeps in memory a permission to correct
  (`_correction`, never stored, since only the core that made a call can be answered by
  it). A wish that is settled with nothing sent, because the target already shows it,
  gives the permission for that state. A call sent for any wish takes it away, so does a
  new wish, and so does a change by someone else (manual wins, R8). A report by one of
  our calls that shows the other state, while the permission stands, uses it up: the
  state becomes the pending wish again and is sent. The report is a change of the
  target's state, so it is always answered; if the new call does not land either, the
  wish is an ordinary unsent one, and the reports that follow are answered within the
  limit of `automatic_resends`, so a device that refuses cannot loop. The permission
  covers a loose timer at zero too: the user's last word (run without a countdown, stop)
  is what is wished, since a loose target may run with the timer at zero but not
  against the last thing the user asked. Why: §5.1, one timer as the single source of
  truth. Why once: Home Assistant credits every write of an entity to the context of
  the last call it took, for five seconds (`CONTEXT_RECENT_TIME_SECONDS`), and every
  correction is a new call that renews it. A correction for every change credited to us
  would command a device that undoes a command by itself within that time (a relay with
  an auto-off time, a plug that trips on overload, a cloud climate that reverts a
  command) at every revert, for ever, and would turn a wall switch back on when it was
  pressed within five seconds of a call, again at every press. Cost if wrong: a change
  credited to a call that was sent for the wish, which is not the answer to an older
  call, is not answered, so a device that undoes a command by itself stays as it undid
  it, and a switch pressed on the wall after a sent call is not overridden, with the
  timer going on as if the target ran (R6, as before this rule); one pressed while a
  wish settled without a call still holds the permission is turned back on, once. Two
  older calls still on their way (a second flip inside the same report lag) can leave
  the answer of the second uncorrected. The settings that a window owes only with a
  turn-on were dropped when the window started again on a target that still read on, so
  the correcting turn-on is plain, and a device that remembers its last mode runs in
  it. Tests:
  `test_run_for_zero_and_at_once_run_for_thirty_leaves_the_boiler_running`,
  `test_start_and_at_once_stop_leave_a_strict_boiler_off`,
  `test_flipping_the_interval_off_and_on_behind_a_late_boiler_leaves_it_on`, for the
  bound `test_boiler_that_switches_itself_back_after_a_command_is_not_commanded_again`,
  `test_late_correction_for_a_boiler_that_switches_itself_back_is_sent_once` and
  `test_wall_switch_pressed_just_after_a_turn_on_is_not_overridden`.
- **A service call that takes longer than 30 seconds counts as failed**
  (`SERVICE_CALL_TIMEOUT`), each call of a list on its own. Home Assistant service calls
  have no timeout of their own, and a hung device would otherwise freeze its timer. Cost if
  wrong: a slow but working device gets one extra command.
- **The longest countdown is one day** (`MAX_MINUTES = 1440`). `timerify.add_time` clamps
  so the remaining time never exceeds it, matching the maximum of the "Run for" number.
  Cost if wrong: users who need longer timers.
- **R10 logging lives in the controller.** When something comes due while the target is
  unavailable, the controller logs what was due, comparing the snapshot before and after
  `tick`: "ended" only when the countdown really ended and the target is wanted off (a
  command due at that instant that extended it, or that turns the target on, does not
  count), "command came due" for every command that was carried out (what it wants is
  applied when the target is back, if it is still relevant then, as R10 says), and "a
  schedule window started" only for a window whose start set the timer, that is, whose
  interval carries the timer's end after the fold. A start that left the timer alone, a
  window that was over, and one that was handed over to a later window wanted nothing,
  so they log nothing. The lines are written by every fold that goes through
  `_fold_due`: the alarm, the refresh of the windows and the switching off of an
  interval. The fold of start-up and of a report of the target writes none; see
  `docs/followups.md`. A command dropped because the run it asked for is over is an
  effect of the core (`CommandDropped`) that the controller logs at info level; the core
  stays pure and emits no other signal. Cost if wrong: none.

### Restarts and storage

- **The store keeps the end, the unconfirmed wish to turn on or off, the owed settings
  (and whether they may only go with a turn-on), the pending commands, the schedule
  windows with the interval whose window end the timer carries, and the intervals that
  are switched off**, with times as ISO UTC strings, and writes only when one of them
  changes. The last observed state of the target is not stored: on start-up the first
  report of the target is always treated as "came back" (spec §5.7, R10), so a wish stored
  before a restart is enforced. The owed settings are stored under `owed_settings` (the
  marker under `owed_turn_on_only`), the commands with `command_to_json`, the shape of the
  "Next command" attribute, and the windows with `window_to_json`, so there is one
  serialisation of each.
- **The store file is version 3; the keys of the later changes joined it without a further
  version.** The migration from version 1 adds `owed_settings`, `commands`,
  `owed_turn_on_only`, `scheduled_by`, `windows` and `disabled_intervals`, the one from
  version 2 the last four, and the store reads version 3 strictly: the migration
  guarantees the keys, and tolerant reads would hide a broken migration. A file that
  contradicts itself is refused when the timer is set up, not repaired: two windows of one
  interval, a window that is suppressed but has not started, a window of a switched-off
  interval, an interval switched off twice, `scheduled_by` without an end, the marker
  without owed settings, a window with a time that has no offset or that does not start
  before it ends or lasts more than a day (the rule of `checked_window`, the one the core
  applies to every window it is given). The set-up fails with a `ConfigEntryError`
  (`stored_timer_invalid`), whose translated reason says what is wrong and tells the
  user to remove the timer and add it again, not with a bare `ValueError`. The reason
  is the English text of the error, also in the Russian message: it is for the bug
  report of a defect, not for the user. Only the timer's own code writes the file, so
  such a file means a defect, and it should show when the timer loads, not as a target
  switched for reasons nobody can follow. Versions 2 and
  3 were never released before their keys were complete, so they need no further steps.
  Cost if wrong: a version 2 or 3 file written by a development build from between the
  changes lacks a key and fails to load; that exists on developer machines only.
- **The snapshot is stored before a command is sent.** A restart during a slow call would
  otherwise lose a newly set countdown.
- **At start-up the merge of the windows arms the stored wake-up.** `set_windows` always
  returns the alarm for the merged snapshot, the earliest of the stored end, the first
  stored command and the start and end of every window, and it is the first effect of the
  one `_execute` that also carries the first observation; an unchanged snapshot produces
  no new alarm from the core otherwise. Nothing is armed earlier, because a stored end,
  command or window that has long passed would switch a target that has not been seen.

### Services

- **Services aimed at an unloaded timer behave like any Home Assistant entity service**:
  a warning that the referenced entities are missing, and nothing else. Re-implementing
  target resolution would duplicate Home Assistant. The one exception is
  `timerify.add_command` called with a response variable: Home Assistant itself raises
  "did not match any entities" there instead of the warning.
- **Every command (the "Run for" number, `add_time`, `run`, `add_command` and
  `cancel_command`) raises `timer_unloaded` when the timer unloads while its call waits
  for the lock.** The call reached the timer, so returning as if the change had been made,
  answering with the id of a command that was never kept, or cancelling nothing, would be
  a lie. Cost if wrong: none.

### Translations

- **The Russian texts were written by the implementer**: the entity names ("turn on for",
  "turns off at", "next command"), the service and field texts, the settings section and
  the error messages in `translations/ru.json`; the HVAC mode names are Home Assistant's
  own Russian ones. The spec gives only English. A message that names the target avoids a
  grammatical case, since the name is a friendly name in the nominative. Cost if wrong: the
  owner rewords a string.

### Verification

- **The minimum Home Assistant version is 2026.10.4** (`hacs.json`), the version
  `pytest-homeassistant-custom-component` is pinned to and the smoke test runs. It is the
  only version the code is verified against; the spec's "2026.10 or newer" still holds.
  Cost if wrong: users on 2026.10.0 to 2026.10.3 must update.
- **The smoke test is a repeatable script** (`scripts/smoke/`) that drives a real Home
  Assistant container, so later phases and the final smoke test reuse it.
- **The smoke script uses Home Assistant's frontend endpoints** (onboarding, config-entry
  flows, registries over WebSocket). No documented API exists for onboarding or creating
  config entries; the script drives a throwaway instance only. Cost if wrong: the script
  breaks on a Home Assistant upgrade, which running it shows at once.
- **The smoke targets are built into Home Assistant**: a target on a device is the `demo`
  integration's `switch.decorative_lights`, and a target that takes settings is a
  `generic_thermostat` over template entities (`switch.smoke_heater`,
  `sensor.smoke_temperature`) and an `input_boolean`. The versioned `configuration.yaml`
  stays mounted read-only. Cost if wrong: the script breaks, loudly, if those YAML
  platforms or the demo entity change.

## Phase 2: settings and pending commands

### Settings

- **Settings are validated against capability attributes** through `get_capability` and
  `get_supported_features`. Capability attributes stay on an unavailable state and in the
  registry, so a command with settings can be made during an outage; an entity known to
  neither gives `setting_not_supported`. Cost if wrong: a capability exposed only as a
  state attribute would be missed (none of the ones used is).
- **`hvac_mode` is a fixed select (the HVAC modes minus `off`); the other modes are free
  text.** The services target the "Run for" number, so a `state` selector cannot list the
  device's modes; the check per target rejects wrong values. This is the service form's
  reading of §5.4 "only offer what the device can do"; the card and voice (later phases)
  meet it from the capabilities. Cost if wrong: users type fan, preset and operation modes
  by hand until the card offers them.
- **The temperature step (`target_temp_step`) is not enforced; `brightness_pct` and
  `percentage` are 1 to 100.** Devices round, and 0 would mean off. Cost if wrong: a device
  may round 22.3 to 22.5.
- **The humidifier setting is called `mode`**, Home Assistant's own field name, so the
  calls map one to one. Cost if wrong: it reads oddly next to the binding mode in the UI
  (the field's description says "The mode of a humidifier").
- **Settings types and the command limits live in `const.py`**, because `core.py` imports
  `domains.py` (for `Actual`), so the shared types can live in neither. Settings are a
  `MappingProxyType` inside the code and a `dict` at every boundary (store, sensor
  attribute, service data), because `MappingProxyType` is not JSON-serialisable. Cost if
  wrong: none.
- **`whole_minutes` and `whole_number` come from one factory, and the settings section of
  `services.yaml` is written once and reused by anchor**, so neither logic nor selectors
  are duplicated. The translations still repeat the field texts per service: custom
  integrations get no `[%key:...%]`. Cost if wrong: none.
- **"Apply is separate": a schedule window owns the settings that may only travel with a
  turn-on, and a stored marker says so; there is no `apply_if_on`.** §5.4: a window that
  opens on a target that already runs pushes no settings, someone chose the current ones.
  The core owes a window's settings with `owed_turn_on_only`, which is stored; S1 is the
  only caller that sets it, and every other way to owe settings (`set_duration`,
  `run_open`, a due pending command) replaces them with unmarked ones, which a command may
  push onto a running target (P1). The change of the timer and the decision what to push
  stay in one atomic core call, which meets the §5.4 bullets. The `apply_if_on` keyword
  that phase 2 gave `set_duration` and `run_open` is gone: it had no caller outside
  the tests, and a keyword was a second place deciding what the marker now decides alone,
  one that was lost when the target was unavailable. Cost if wrong: a future caller that
  must not push onto a running target does what S1 does, `_owe(..., turn_on_only=True)`.
- **Owed settings go with the next `TurnOn`; otherwise `ApplySettings` is sent when the
  target is on or a turn-on is in flight.** The lock means an in-flight turn-on has
  returned before the next command runs. Settings marked turn-on-only are never sent that
  way (see Phase 3). Cost if wrong: a device slow to report "on" gets its `set_*` calls
  right after the turn-on.
- **A command without settings leaves owed settings alone; only non-empty settings replace
  them**, also for an executed pending `on`. Settings are never invented or silently
  dropped. Cost if wrong: settings asked for during an outage reach the device after a
  later plain command.
- **"Settings applied" means every call of the list returned without an error and, for a
  turn-on list, the target then reads as on.** Attributes are not compared, so applied
  settings are not state-checked: P1's "executes at T" means the calls are sent at T. A
  wrong state after a turn-on list fails the whole list, settings included, because
  devices round and report late and the re-sent turn-on must still carry the settings.
  Cost if wrong: a device that silently ignores a setting is not asked again.
- **A failing call stops its list; the whole owed set is sent again later through the
  apply list.** It is simple and idempotent. Cost if wrong: settings that were already
  applied are sent twice.
- **Owed settings have their own count of automatic re-sends with the wish's rules, then
  `GaveUp("settings")` once.** Climate entities report attribute changes constantly, and
  unbounded re-sends are forbidden above. Cost if wrong: a device that applies settings
  only after its fourth report misses them until the next change or command.
- **The controller's call lists, logs and `_raised_for` are labelled on, off or
  settings.** An apply has no wish, and `pending` is `None` while it runs. Cost if wrong:
  duplicate tracebacks if the label's settling is misjudged.

### Pending commands

- **The service is named `add_command`, not `schedule_command`**, and its response is
  `{"command_id": ...}` per entity. "Schedule" is phase 3's word, and renaming later breaks
  automations. Cost if wrong: none now.
- **`cancel_command` is an entity service aimed at the owning timer; another timer answers
  `unknown_command`.** The card and the `add_command` response carry the entity. Cost if
  wrong: an area-targeted cancel reports an error.
- **There is no `cancel_commands` (all) service in this phase.** No user path needs it yet;
  voice can add it. Cost if wrong: an extra loop in automations meanwhile.
- **Exactly one of `delay` and `at` is checked in the method, not in the schema**, because
  schema errors are not translatable per key. Cost if wrong: none.
- **A naive `at` is Home Assistant's local time** (`dt_util.as_utc`), because the UI
  datetime picker sends no zone. Cost if wrong: none.
- **A `delay` counts from the moment the command gets its turn.** The controller takes it
  as a time span and makes a time of it under the timer's lock, so a call that waits
  behind a slow device (each call may take 30 seconds, and a climate turn-on with mode,
  temperature and fan mode is three) is not refused as already passed. `at` is taken as
  given. Cost if wrong: a delay of one minute that waited ninety seconds is due ninety
  seconds after the call, not sixty.
- **`action` accepts the booleans that YAML 1.1 makes of an unquoted `on` and `off`**
  (true is "on", false is "off"), because Home Assistant's own loader does so and a
  hand-written `action: on` would otherwise fail. The README quotes the words anyway. Cost
  if wrong: none.
- **`temperature` and `brightness_pct` refuse a boolean**, as the whole-number settings
  do: `true` would be 1 % for a lamp. Home Assistant's own `light.turn_on` coerces it.
  Cost if wrong: none.
- **`at` keeps its seconds**; `delay` gives whole minutes anyway, and rounding an explicit
  time would surprise. Cost if wrong: none.
- **An unknown command id raises `KeyError` in the core and the controller maps it to
  `unknown_command`**, so the snapshot stays the single source of truth. Cost if wrong:
  none.
- **A loose-mode command to turn on without minutes that came due during downtime is
  carried out however late.** An open run has no end, so "for whatever is left of it"
  never runs out (§5.7), and P1 makes a command a firm promise: "turn the boiler on at
  07:00" with Home Assistant back at 18:00 turns it on at 18:00, with no countdown.
  Strict mode counts the default duration from the command's time, so a stale one is
  dropped; a command to turn off is always carried out. Cost if wrong: a boiler started
  hours late; the user can cancel the command, or give it minutes.
- **One alarm sits at `next_wakeup`, the earliest of the end, the first command, the start
  of every window not yet started and the end of every window**, and the core's `tick`
  (formerly `expire`) handles all four kinds of due items. One wake-up path for all of
  them, which is also what keeps a restart from flapping the target. Cost if wrong: none.
- **The catch-up folds all due items in one order, the key `(time, rank)`, and wants one
  final state.** The ranks at one instant: the end of a window, the start of a window, a
  command, the end of the timer. A command at a window's start is a manual set and wins
  (P3); a window that starts as the timer ends extends it without an off; phase 2's
  "a command before the end on a tie" is kept. That avoids off/on flaps after a restart
  and at coinciding times. Cost if wrong: a due `on` then `off` never reaches the device,
  which is intended.
- **`observe` runs the catch-up first, and skips R3 to R5 only when the catch-up moved the
  timer**, that is, a command was carried out, the end was reached, a window's start set
  the timer (an applied S1) or a realignment changed it. It generalises phase 1's "expiry
  outranks the report": a manual off reported in the same instant a command fires or a
  window opens is overridden by it (P1, P3). Neither a window start that left the timer
  alone (it ends later already, or the window was over), nor a window end, nor a command
  that was merely dropped moves the timer, so R3 to R5 still apply: spec §5.7 lists
  "execute or drop" and "apply R3/R4" as separate steps, and skipping them would leave a
  strict target that is found on after a restart without a countdown. A realignment that
  stops the timer at start-up does count: it must hide R4 from the report of the same
  observation, or a stopped strict target would get the default duration. Cost if wrong:
  none found.
- **The controller notifies the entities when `end`, `commands` or the switched-off
  intervals changed, and each entity gates its own write.** The "Next command" sensor must
  show a command added to an idle timer, and the switch of an interval follows its flag.
  Cost if wrong: none.
- **The "Next command" sensor writes its state only when the command list changes, and its
  attribute is unrecorded**, proven with the recorder fixture (§3, a small recorder).
  Cost if wrong: one slower test.

### Deferred

- **A deleted target still gives no sign.** The spec is silent and it changes no
  spec-defined behaviour, so it stays in `docs/followups.md`, under "Later". Cost if wrong:
  timers of deleted targets stay silent until a later phase.

## Phase 3: schedules

The plan's rulings (`docs/superpowers/plans/2026-10-29-phase-3-schedules.md`) and the ones
the reviews added, in the form they have now. Where a later ruling replaced a plan ruling,
only the final behaviour is written.

### The windows in the core

- **§5.7's "a schedule window that is active now → apply S1" means a window whose S1 has
  not run**: it began during downtime, or was never applied. A window that already started
  keeps its `started` mark across the restart. Re-applying S1 would ignore a manual change
  (R8, and the anti-goal of §2: the user always wins over automation) and make a restart
  mis-fire (§2 goal 5); a window the user stopped (S4) must not come back with it. The
  first sketch of the core's interface had two events, `window_started` and
  `window_changed`; they became fold items plus a realignment: one wake-up path, one alarm
  for windows, commands and the end together, and no flap after a restart. Cost if wrong:
  a user who expects a restart to bring back a window they stopped.
- **S4 is two stored marks per occurrence, `started` and `suppressed`; a window applies S1
  once.** `started` says S1 has dealt with the opening (it set the timer, left it alone
  because it ends later, or found the window over); `suppressed` says the timer was zeroed
  after that. Both survive edits (a new window that is open now and replaces a started
  window that is open now is the same occurrence and inherits them) and restarts. So any
  zeroing during a started window keeps the target off until the next window: R3 (also
  when the timer was idle, so a loose target that someone switches off during a started
  window stays off), a stop from the card, Run for 0, the end of a manual run, an off
  command, a realignment that stops. The timer is never handed to a suppressed window.
  Why: R8 "manual wins", and a restart must behave like no restart. A window that starts
  after the zeroing is not suppressed. Cost if wrong: a user who stops the boiler from the
  card and expects a restart to bring the window back.
- **S1 judges "the target already runs" by the desired state, not by delivery.** At a
  window start the interval's settings are owed (turn-on only) only if the target is not
  wanted running as of that item: the fold's wish so far is "off", or, before any wish,
  the pending wish is "off" (sent or not), or, with none pending, the target is not on. A
  pending "off" counts as wanted off even while the target still reports "on", so a window
  that opens while the end of a timer is being switched off turns the target on with its
  settings. Why: P1, P3, R8, R10: a window must never replace the settings of a command
  because the command's turn-on has not reached the target yet (it is unavailable, the call
  failed, the wish was restored from the file). This replaced the plan's reading, "on or
  its turn-on is in flight". `_deliver_settings` keeps its own question, whether owed
  settings can be sent now. Tests:
  `test_window_start_while_a_turn_on_waits_for_the_target_keeps_its_settings` and
  `test_window_start_after_a_restart_keeps_the_settings_of_an_unconfirmed_on`. Cost if
  wrong: none found.
- **Turn-on-only settings are dropped, not applied, when the target is found on without
  our turn-on list completing** (store key `owed_turn_on_only`, so the rule survives
  unavailability and restarts): it came back already on, someone switched it on, the
  turn-on on its way carries none, the file was restored that way. The target is running
  by someone else's hand. One place decides it, `_deliver_settings`, so no second path can
  disagree. Cost if wrong: none found; the exception is the next entry.
- **One exception, which releases the settings: our own turn-on switched the target on but
  a later call of the same list failed.** When the target then reports "on" in response to
  our own call (`by_us`), the marker is cleared and the settings stay owed, sent again as
  `ApplySettings` under the resend cap. Why: the settings belong to a turn-on Timerify
  itself made on a target that was off (§5.4: a command that turns the target on applies
  its settings); dropping them leaves the air conditioner on the wrong setpoint. The
  release needs the report to carry our context, so a polled climate entity that reports
  later with another context drops the remaining marked settings; that fails safe, as
  phase 2 does, because nothing is pushed onto a target someone else may have set. The
  retry sends the whole owed set again, so the mode is set once more before the
  temperature. Cost if wrong: one extra settings call.
- **Every write of the end goes through `_set_end(end, *, by=None)`; only S1 and the
  realignment pass `by`.** The plan's "`_run_until` and `_end_timer`" missed a loose
  `run_open`, a due on-command and R3, which would have left `scheduled_by` set and broken
  S3. `scheduled_by` is `None` whenever `end` is. Cost if wrong: none.
- **A window start whose window has ended by the fold's `now` is dropped: marked started,
  the timer untouched, no log.** §5.7 lists only active windows and R10 drops an "on" whose
  window passed (the start-while-unavailable line already said so); otherwise a kept
  window that passed during downtime would cut a loose open run. Cost if wrong: a user who
  wants a log for a window missed while Home Assistant was down.
- **While the schedule owns the timer, its end is the latest end among the windows that
  are open, started and not suppressed; the realignment (S2) runs at the end of every fold
  and after every window end.** The timer is the schedule's while `scheduled_by` is set,
  that is, while nobody has changed it since (S3). At every realignment its end becomes
  the latest end among the open windows, and `scheduled_by` the interval of that window (a
  tie keeps the current one); with none open it stops. So an edit, a deletion or a switch
  is one thing for S2, a window that changes or leaves, and: removing or shortening the
  window that carries the end hands the timer to the latest other open window instead of
  stopping it; extending a started window that does not carry the end past the timer's end
  takes the timer at once, without applying that window's S1 again, so no settings are
  pushed; a window end hands the timer over before the timer's own end can end it, at that
  item's instant, and with no other window open it does nothing there, so a window that
  opens at that very instant extends the timer without an off. A timer someone changed is
  never realigned. A realignment with nothing to change gets no effects, so it is
  idempotent; one that finds the end drifted from its window without an edit (possible
  only after the one-day cap, which the windows respect) pulls it back. This replaced the
  plan's "a realign to stop does not hand the timer to an overlapping window". Why: §5.5,
  schedules are declarative ("the target should run during this window"), and §5.4's
  overlap bullet. Cost if wrong: a schedule-owned run lasts to another open window's end
  after the user shortened the one they were looking at.
- **An edit that moves the active occurrence so it is no longer active creates a new
  occurrence.** S2 stops a scheduled timer now, and the moved window applies S1 at its
  start even after a manual off: S2's "start later if the window moved ahead". Why: an
  edit is itself a manual act expressing the user's current intent. Cost if wrong: a
  target turned back on after the user edited its schedule.
- **Adding an interval or switching one on during its window starts it for the remainder;
  switching off and on again forgets S4 for that occurrence.** Schedules are declarative
  and a restart does the same (§5.7). Switching on is the user's own act, newer than the
  manual off, as an edit is. An in-place edit of an open, started window keeps its
  suppression (`_inheriting`) and a toggle does not, because a disabled interval has no
  window to remember it in: the invariant "no window for a disabled interval" has one
  owner. Pinned by `test_enabling_during_a_window_the_user_stopped_starts_the_target_again`
  for the toggle and `test_target_off_during_a_window_stays_off_until_the_next_window`
  for the edit. Cost if wrong: a surprise turn-on when enabling mid-window, also after
  the user stopped the boiler.
- **Deleting an interval is disabling it for S2.** Its window leaves the snapshot and the
  realignment follows, so the timer stops, or passes to another open window, at once. Cost
  if wrong: none.
- **A loose open run is cut at a window's end when the window starts during it.** S1 sets
  the timer, and a timer above zero means "off at zero" in loose mode. Cost if wrong:
  loose users may expect the run to continue.
- **A window is capped at `MAX_MINUTES`, and an occurrence that the change of the clock
  swallows is skipped; wall times convert with `fold=0`.** The spec is silent on a wall
  time that does not exist. zoneinfo's own rule, no private Home Assistant helpers: a time
  in the skipped hour happens later by the length of the gap (02:30 on the night the clock
  goes forward happens at 03:30), and one that comes twice is its first. Both ends convert
  alike, so 02:10 to 02:50 on that day runs from 03:10 to 03:50 (pinned by
  `test_window_inside_the_skipped_hour_runs_an_hour_later`). An occurrence is skipped only
  when the shifted start reaches the end, as 02:30 to 03:15 (start 03:30) and 02:50 to
  03:10 do. Cost if wrong: a 02:30 to 03:15 interval does not run on the spring-forward
  day.

### The controller

- **Occurrences are computed ahead: one current-or-next window per enabled interval, in
  Home Assistant's time zone, refreshed when the zone changes (`EVENT_CORE_CONFIG_UPDATE`);
  a Workday answer is asked when an occurrence is computed, not at its start.**
  `check_date` answers a date deterministically, and computing ahead keeps the core pure
  and the alarm single. A Workday configuration changed between computing and the start is
  noticed only when the sensor reports, which it does, since its entry reloads. A time zone
  changed in YAML and applied with "reload core configuration" fires no such event; see
  `docs/followups.md`. Cost if wrong: windows in the old zone until the next refresh.
- **The search horizon is `WINDOW_SEARCH_DAYS = 14`.** A weekday interval always matches
  within 7 days; a Workday-based one with no match is searched again when the sensor
  reports, daily. Cost if wrong: none found.
- **A window carries only the settings of its interval that the target takes when the
  window is worked out; the rest are left out and said once.** The form checks the
  settings when the interval is saved, but a window is worked out from data that can be
  months old, and what a target takes changes (an update of its integration renames a
  mode, the device is replaced). A setting the target no longer takes fails its call, and
  the window would turn nothing on, with a warning every morning, where a plain turn-on
  would have worked. Each setting is judged alone, as the form offers them and as the next
  edit keeps them (`_with_settings_the_target_takes`, through `validate_settings`), so the
  rest of the settings are still used. The warning names the interval and the settings,
  and is repeated only when what is left out changes, not at every refresh. Windows are
  worked out at start-up, at every window end, when the Workday sensor reports, when the
  zone changes and when an interval is switched, so a change of capabilities is noticed by
  the next of those, and a window worked out before it keeps the settings it had until
  then. A window that is kept because its occurrence could not be worked out keeps the
  settings it was worked out with. Cost if wrong: a setting that the target takes again is
  missing from the window that was worked out while it did not, until the next refresh.
  Pending commands are not covered; see `docs/followups.md`. Tests:
  `test_setting_the_ac_no_longer_takes_is_left_out_and_said_once`,
  `test_setting_that_comes_back_and_goes_again_is_said_again`.
- **Window refreshes run under the one lock through `_async_refresh_windows_locked`; event
  callbacks use `_refresh_windows`, which takes the lock; after every await the controller
  re-checks that it is still loaded and takes `now` afresh.** `asyncio.Lock` is not
  re-entrant (a wake-up or a toggle calling the locking variant deadlocks), and a stale
  controller that outlived a reload during a Workday call must not save over the new one.
  The fresh `now` matters: a command that queues behind a slow refresh must find a window
  that opened meanwhile already folded, so the command, the later word, wins
  (`test_window_made_by_a_slow_refresh_comes_before_a_later_command`). Cost if wrong: none.
- **Every fold of what fell due goes through `_execute_fold`, after `observe` as well as
  `tick`, and a window the fold found over is replaced by the next one of its interval.** A
  report of the target can get the lock before the alarm of a window's end does, and the
  alarm then finds nothing due; the refresh's own fold can find a window over because
  asking the Workday sensor took until its end. Without the replacement the interval would
  have no window until a reload. The R10 lines are written by `_fold_due`, through which
  the alarm, the refresh and the switching off of an interval fold. Tests: `test_window_that_ends_while_the_boiler_is_slow_is_replaced_by_tomorrows`,
  `test_window_that_ends_while_the_sensor_is_slow_is_replaced_by_tomorrows`. Cost if
  wrong: none.
- **Start-up merges the fresh windows, arms `next_wakeup` read after the merge, observes,
  and executes the merge's and the observation's effects together; the time-zone and
  Workday listeners are registered at the top of `_handle_started`, under the lock, not
  after the first fold.** One save and one fold, §5.7's order. The plan put the listeners
  after the first fold, where a change that arrives during start-up could be missed. Their
  handlers need the lock that `_handle_started` holds, so nothing folds before the first
  observation either way, and a change that arrives while the start-up waits for a slow
  device or sensor is no longer lost (`test_time_zone_change_during_start_up_is_not_lost`,
  `test_sensor_that_comes_back_while_the_timer_starts_is_not_missed`). Cost if wrong:
  none.
- **An unknown Workday answer keeps every window the interval already has, started or not
  (`keep`), and computes nothing new for it.** Unknown is a sensor that is unavailable, a
  call that failed with anything (a `HomeAssistantError`, a time-out, a bug or a changed
  service; none of them may stop a timer), a service that is missing, or an answer that is
  not about the sensor. The first unknown answer of a refresh ends that refresh's
  questions, since what is wrong with the sensor is wrong for all its intervals; each day
  is asked at most once per refresh. One warning is logged per outage, the next answer
  ends the outage, and the traceback of an unexpected error is logged only with that first
  warning. The windows are worked out again on the sensor's next state change or state
  report; Workday writes its state every midnight, so a transient failure is retried
  within a day without polling. A kept future window starts although the sensor is down,
  since its answer was known. Why: the sensor is followed by its events, never polled.
  Cost if wrong: a window of a sensor that never comes back never starts, and the warning
  says why.
- **The Workday answer is taken as the sensor gives it, `days_offset` included; the README
  asks for a sensor with an offset of 0.** No reading of another integration's options. A
  sensor with an offset of 1 answers for the day after, and its schedule runs shifted by a
  day (`test_day_offset_of_the_sensor_shifts_the_days_as_it_answers`). Cost if wrong: a
  user with a "tomorrow" sensor gets shifted days until they read the README.
- **A question to the Workday sensor can hold the lock for up to `SERVICE_CALL_TIMEOUT`,
  and a start-up that finds a kept window over asks twice.** A hung `check_date` holds the
  lock for up to 30 seconds once per refresh (the first unknown answer ends the questions),
  as a hung target call does ("A service call that takes longer than 30 seconds counts as
  failed" and "A `delay` counts from the moment the command gets its turn"): target
  reports, commands and the wake-up wait, so an end can fire that late. The real
  `check_date` is a lookup in memory, and an unavailable sensor fails at once. When the
  start-up fold finds a window over that it kept because the sensor was unknown, the
  recompute asks again, bounded at two rounds because the fold removed the window. Cost if
  wrong: a late end during a hung sensor; one extra failed question at start-up.
- **Enabling an interval is one change: the flag and the window refresh are one `_execute`
  and one save, and enabling an interval that is on returns at once.** The flag is
  recorded in the core's memory before the Workday awaits and saved with the windows, so
  a timer unloaded during the wait raises `timer_unloaded` ("nothing was changed") and that
  is true. Disabling is a flag and a tick in one fold. Nothing is asked for an interval
  that is switched off or already on. Cost if wrong: a countdown refresh alarm that fires
  while a flip waits for the sensor writes the switch from memory, so it shows "on" a
  moment before the answer; only if the flip then fails does that matter.
- **A timer whose intervals need a Workday sensor it lacks fails to load**
  (`ConfigEntryError`, `workday_sensor_missing`). The interval form refuses the mode and
  the timer's settings refuse to remove the sensor while an interval uses it, so only a
  hand-edited file gets there, and asking a sensor that is not there would only fail. The
  update listener is added after the controller is built, so fixing the file does not
  reload the entry: the user reloads it. Cost if wrong: a manual reload.
- **A change before Home Assistant has started is not held back.** The flip of an interval
  runs its tick or its refresh, and a phase-2 command arms the alarm of a stored end,
  command or window that has long passed, before the first observation of the target. The
  wish goes out to a target that may not be there yet, fails, is marked unsent, and the
  first observation sends it again, so the state converges, as it does for a restart. One
  rule for every command (record and save, arm nothing, let `_handle_started` fold) is in
  `docs/followups.md`. Cost if wrong: one failed call at start-up.

### The entry, the intervals and the entities

- **One update listener reloads the entry on any change (`async_schedule_reload`, which
  also collapses repeated changes); `options_flow_reloads = False`; `_follow_target` no
  longer reloads itself.** In 2026.10.4 a subentry add
  (`ConfigSubentryFlowManager.async_finish_flow` → `async_add_subentry`), edit
  (`async_update_subentry`) and delete (`async_remove_subentry`) only fire update
  listeners, the subentry `async_update_reload_and_abort` raises with a listener, and
  `OptionsFlowWithReload` raises with one; Home Assistant's usage report says to reload
  from the listener (ollama and anthropic await `async_reload` there). Every interval add,
  edit and delete reloads the timer, entities re-added and the start-up path run again;
  tests prove a countdown survives it (`test_adding_an_interval_keeps_a_running_countdown` and its edit and delete
  siblings), and the pending commands are stored and restored as at a restart. Cost if
  wrong: none.
- **The enable flag is `Snapshot.disabled_intervals` in the timer's store, enabled by
  default; the core drops the windows of disabled intervals and the controller does not
  compute them.** One store, one save path, the invariant has one owner, and a toggle never
  reloads the entry because the flag is not entry data. Cost if wrong: none.
- **Every Timerify entity attaches to its device through `device_entry`: the target's
  device, or the timer's own device got or created once, without a subentry
  (`timer_device`).** In 2026.10.4 an entity of a subentry that brings the shared
  `DeviceInfo` moves the device into the subentry (deprecated, an error from 2027.8); the
  registry then drops the number and the sensors, and deleting the interval deletes the
  device. Cost if wrong: none.
- **The switch is named "Schedule {interval}" with the subentry title.** The title
  identifies the interval and follows edits after the reload; entity ids keep the first
  title. Cost if wrong: a dashboard that matches on the name.
- **The interval form refuses seconds (`whole_minutes_only`), accepts the UI's `HH:MM:00`
  and stores `"HH:MM"`; its settings pass through the services' `SETTINGS_SCHEMA` before
  `validate_settings`.** Values are never silently dropped, and a setting has one type
  whichever channel made it. Weekdays are stored as `[]` for the working-day modes, where
  they mean nothing. Cost if wrong: none.
- **The settings section of the interval form is collapsed unless the form shows
  settings, and it has no default.** It is open when editing an interval that has
  settings and on a refused form that carries some, so a `base` error points at visible
  fields; closed for a new interval and for one without. A default on a section makes the
  real frontend skip the settings inside it, and an edit would clear them. Cost if wrong:
  none.
- **Titles are generated in Home Assistant's configured language from the selector labels;
  a title the user renamed survives edits.** Subentry titles are plain strings, so a title
  stays in the language of its creation. Cost if wrong: an old title stays in the old
  language after the house language changes; see `docs/followups.md`.
- **The Workday step appears only when a Workday sensor exists in the house (or is set, in
  the options); its schema function returns `None` to skip it, and `duration`'s
  `next_step` is a function too.** §6.2's "three clicks for the common case"; the order of
  the steps otherwise follows §6.2, the Workday sensor last. A `next_step` sees only the
  options, so the schema decides. With a string `next_step` the duration form would say
  "Next" in a house with no sensor, where nothing follows; a function leaves `last_step`
  unset and the frontend says "Submit", which is also what it says before a Workday form
  that does follow, exactly as the mode form says before the duration form. The options
  form refuses to clear the sensor while an interval uses it (`workday_in_use`), and a
  sensor whose integration is gone stays on offer so that it can be removed. Cost if
  wrong: a user who adds a Workday sensor later picks it in the options.
- **A renamed Workday sensor is not followed.** The option holds the entity id; after a
  rename `check_date` answers "did not match any entities", the intervals wait with a
  warning, and the listeners sit on the old id. It is in `docs/followups.md` for the
  `_follow_target` pattern, to be done before release. Cost if wrong: the schedules of
  working-day intervals stop until the user picks the sensor again.

### Verification

- **`holidays==0.106` joins the dev group for the contract tests with the real Workday
  integration; scenarios use `FakeWorkday`, which fails the way Home Assistant does
  (`HomeAssistantError`, "did not match any entities").** The real tests pin the response
  shape, the Israeli week and the error of an unloaded sensor; the fake controls holidays
  and outages. A test pins the version to the one Workday requires. Cost if wrong: a dev
  dependency to bump with Home Assistant.
- **One jump of the clock in a test is one catch-up; scenario tests step to each event.**
  Home Assistant fires a chained alarm at once with the frozen time, so a jump over a
  start and an end folds them; that is the downtime behaviour, tested with `restart_after`.
  Cost if wrong: none.
- **The test fake of a switch hands Timerify's own switch to the domain's service.**
  Timerify now sets the real `switch` component up, which re-registers `switch.turn_on`
  and `turn_off`, so the fake routes a call whose entity is registered under platform
  `timerify` to the service that was there before it and keeps every other call. That is
  how Home Assistant dispatches one domain service to the platform that owns each entity;
  it changes no production code and is not a backdoor. Cost if wrong: none.
- **The smoke interval uses days of the week, not a Workday sensor, and takes the time
  zone from Home Assistant.** The date of the container is not under the script's control;
  the real `check_date` is proven by the pytest contract tests, not in the container. The
  script asks Home Assistant for its configured time zone (`get_config`), since that is
  the zone the windows are worked out in, adds the interval through the subentry flow of
  the REST API, finds its switch by the unique id `{entry_id}_interval_{subentry_id}` and
  checks it sits on the timer's device. Cost if wrong: a Workday-based interval is never
  run against a real container.

## Phase 4: voice

The plan's rulings (`docs/superpowers/plans/2026-10-30-phase-4-voice.md`) and the ones the
reviews and the owner added, in the form they have now. Where a later ruling replaced an
earlier one, only the final behaviour is written. Section numbers (§) and rules (R, S) are
those of the spec.

### What Timerify takes over from core

- **A bare "turn on X" and "turn off X" of a device that has a timer is a Timerify
  command.** The first plan left these to core and let Timerify observe the change as a
  manual one; that was reversed because §5 R9 names "voice 'turn on X' routed to Timerify".
  On is R9 for a device that is off (loose mode: an open run; strict mode: the default
  duration; a device that already runs keeps its countdown, see the next entry)
  and off sets the timer to zero and turns the target off, through the controller, as the
  services do, so an unavailable target keeps its wish (R10) and the answer is Timerify's. The phrasings are
  core's own name-only ones, so a phrasing with an area, a floor or a kind of device stays
  with core, and so does every device with no timer. Cost if wrong: a phrasing that core
  adds in a newer release of its sentences reaches core until Timerify is regenerated (see
  the next entry).
- **R9 is for a target that is off: a turn-on without a duration changes nothing about the
  countdown of a target that is already wanted running (a clarification of R9).** R9 says
  that a command that turns the target on without a duration runs it without a countdown
  in loose mode and for the default duration in strict mode. It describes starting a
  target; it says nothing about one that runs, and read literally it cut a run of two hours
  to the default duration (strict mode) and took the auto-off away from a run of twenty
  minutes (loose mode), or erased the end of a schedule window, only because the same
  words were said twice. Before this phase "turn on the boiler" to a boiler that was on was
  Home Assistant's no-op, and R4 sets the default duration only while the timer is zero, so
  the clarification keeps what a user had before and agrees with the spec's goals (one
  timer as the truth, and manual changes win). So a target that the timer already wants
  running (`TimerCore.wanted_running`: a countdown that is not over, else the wish that the
  target has not confirmed yet, else the target last seen on; a target that is away while
  its countdown runs counts) keeps its countdown, or its run without one, in either mode.
  R9 applies only to a target that is off, as before. The rule is in one place,
  `TimerCore.run_open` and its twin for a pending command, and holds for every way of
  asking without a duration: "turn on the boiler" and the name alone, the tool
  `timerify__run` without hours and minutes, the service `timerify.run` without minutes,
  and a command to turn on without minutes when it comes due. The answer is what any run
  gives: how long is left and when the target turns off, or that it is on without a timer.
  What the request carries besides a duration is still done: the settings of the tool, the
  service or the command are set on the running target (P1, a command is a firm promise),
  and a turn-on that has not reached the target is sent again. The timer itself is not
  touched, so the schedule that owns a countdown still owns it (S2: editing the interval
  realigns it) and the request is not a change of the user's (S3). A countdown that has
  reached its end is over whether or not its alarm was handled yet, so a request that
  meets it, or a command due in the very instant it ends, starts the run again by R9 and
  the target is not switched off and on. A command that came due while Home Assistant was
  down is judged as it would have been live: it finds the countdown that was under way at
  its time and leaves it. Cost if wrong: a user who wants the default duration again says
  "for 45 minutes", sets "Run for", or stops the timer first; a pending command without
  minutes no longer shortens or removes the end of a run that is under way.
- **The delayed commands of core are taken over for the devices that have a timer,
  generated from the data that Home Assistant ships.** `scripts/generate_core_commands.py`
  reads the pinned `home-assistant-intents` and writes `core_commands.yaml` for each
  language: every shape of core's delayed on and off (all unit combinations, both word
  orders, "in" or "after", articles, and the English form with the name last) as a sentence
  for the list of Timerify's targets, and the bare on and off, in both languages. It is
  committed, because the manual route needs complete files, and a test fails when the file
  is stale; the generator refuses a block it does not understand, so a release cannot widen
  or narrow the takeover without notice. `requires_context` is dropped exactly when a
  block's domain list contains `switch`, which is core's generic on and off in both
  languages: every target can be switched and delayed, whatever its domain. Cost if wrong:
  on a newer Home Assistant with new shapes, those reach core until a Timerify release.
- **The takeover is proved by a structural test, and behaviour is sampled boundedly, so that
  the voice suite runs in well under a minute.** The proof is that every core shape of every
  command pair is covered by the generated file; one conversation per pair (optional parts
  skipped) shows it reaching Timerify, and a device with no timer still reaches core's
  delayed command. Trying every spoken variant would be 180,544 conversations in English
  alone. Cost if wrong: a substitution bug that shows only with optional words present is
  caught only by the samples of the other intents.
  The bound is held by running the suite in parallel, not by the sampling alone. Measured
  at the end of the phase, on an 18-core machine: `tests/voice` (597 tests) takes 17 s in
  parallel and 86 s in one process (`-n 0`), and the whole suite (1687 tests) takes 18 to
  20 s in parallel and 112 s in one process. Each scenario is a real Home Assistant with
  the real built-in agent, so a serial run is over the bound that the sampling alone was
  meant to keep. `pytest-xdist` is therefore in the dev group at the locked version, and
  `-n auto` is in the pytest options: `uv run pytest` runs in parallel, three full runs in
  a row passed, and a run of one file stays fast (a file of 48 tests takes about 5 s
  against 4 s in one process). The per-test timeout of 60 seconds stays. Cost if wrong: a
  test that shares state with another fails only in parallel; none has in the runs made,
  and `-n 0` runs the suite as before to tell.
- **The takeover sentences name the device in a slot of their own, `timerify_target`, which
  the handlers map back to `name`.** With `name` in the sentence, the built-in agent
  prefers the custom sentence in its stage for names it does not know and then gives up the
  fallback that resolves "it" and "them", which lost the follow-ups. With its own name the
  agent resolves the device as before. The mapping is one function (`named` in
  `voice/base.py`), run before the slots are validated, and an LLM cannot send the slot
  because a tool's parameters come from the handler's own schema. Cost if wrong: none.
- **A follow-up ("turn it off", "turn them off") after a question or a command about a
  device is answered by core.** It switches the device, and the timer follows by observing
  the change, but the answer is core's, and for an unavailable target the call fails and no
  wish is kept (R10 does not apply). Cost if wrong: a user who says "turn it off" to an
  unavailable device gets core's failure, not a kept wish.
- **A sentence of Timerify's about a name that is not a device with a timer is answered
  with core's "not aware of any device".** A custom sentence that takes a list slot wins
  the stage where unknown names are answered, and the fallback of the gazetteer then gives
  up on it. Only the wording of an error changes ("what is planned for the fan", for a fan
  that exists but has no timer), and no successful answer of core is hidden, which was
  checked phrasing by phrasing. Cost if wrong: a better error of core is lost.
- **A device that is not a Timerify target but shares its name with one is not reachable
  through Timerify's phrases, a departure from §6.4.** §6.4 says "Sentences must never match
  a non-Timerify entity". A sentence matches a name, though, and the list of names is
  static and cannot tell two entities that carry it apart, so "turn off X" always means the
  target with the timer, and core's bare and delayed on and off no longer reach the other
  entity by that name. The same holds for "turn on/off the X schedule" when an exposed
  entity is called "X schedule": it means the schedule of the timer called X (a second,
  explicit exception, decided by the owner, to §6.4's "To keep every other entity on core's
  behaviour"). That entity is reached by other phrasings and the interface; the case of a
  timer called Boiler next to one called "Boiler schedule" is the same case. Cost if wrong:
  a user who has an entity with a timer's name, or one called "<timer> schedule", must say
  it another way.
- **The English phrasings of the schedule take "of" and "for", and on or off before or
  after the noun, because a phrasing that is left out is not left alone.** The built-in
  agent takes "turn off the schedule for the boiler" for a turn off of the boiler, so the
  near misses that were found are sentences. The set is open ended: a phrasing with a
  device's name that Timerify does not have, and "turn on" or "turn off" in it, can still be
  matched by core's gazetteer (English only), which `docs/followups.md` carries. Cost if
  wrong: the boiler is switched off by a sentence meant for its schedule.
- **There is no sentence for subtracting time.** §6.4 lists set, add and stop, and setting
  the countdown to the new length covers shortening. "10 minutes less" has no match.
  Cost if wrong: none.

### What can be said

- **A duration is whole minutes, a delay may carry seconds, and the controller refuses a
  duration outside 1 to the day.** A delay is a moment, and a zero delay is refused as a time
  that is not ahead (`command_in_past`), or "turn off in 0 minutes" would stop at once;
  "turn off in 90 seconds" shows 2 minutes on the number and ends after 90 seconds. Core
  silently caps a duration, so "for 30 hours" would run a day without a word: it is refused
  with the limit instead. Adding keeps the clamp of the first phase (the end is never more
  than a day ahead) whatever is asked, and says when the countdown really ends, so "add 30
  hours" gives a day. For the user to hear either, a longer duration has to reach the
  handler, so the sentences understand hours up to 168 and minutes up to 10080, a week in
  each, the same in both languages and equal to the longest delay a command takes; a count
  beyond a week is not understood, and a test pins that bound too. The tools take any count
  and the controller decides. Cost if wrong: "for 200 hours" is answered as not understood,
  not with the limit.
  The shape of the minutes is a matter of cost. A range that allows number words makes
  hassil build, on the first request in a language, a table of the words of every number in
  it, and that table grows with the range: measured on hassil 3.12 in a fresh process, hours
  1..168 cost 0.02 s in Russian and nothing measurable in English; minutes 1..1440 cost
  0.36 s and 16 MB in Russian and 0.02 s in English; minutes 1..10080 cost 4.7 s and 123 MB
  in Russian and 0.19 s and 22 MB in English, which made the first Russian request take
  over 4 s of CPU (4.34 s measured through Assist, against 0.45 s now). So the
  minutes up to a day (1..1440, as many as a timer can run) and the hours (1..168) are
  ranges that may be said as words, and the minutes from a day and a minute to a week
  (1441..10080) are a list of their own, `timerify_long_minutes`, with `words: false`:
  digits only, no table. It fills the same slot, `minutes`, through the expansion rule
  `timerify_minutes_count`, so the handler cannot tell the two apart, and both languages
  have the same shape. A test pins the shape, and another that no range list of Timerify
  that allows words is larger than a day of minutes (the structure, not the time, which
  varies by machine). Cost if wrong: "for two thousand minutes" said in words is not
  understood, while "for 2000 minutes" is, and answered with the limit.
- **"Turn off X in N" decides whether the target is running under the controller's lock,
  from the desired state: a countdown above zero, else the pending wish, else the target
  being on.** A running target gets its countdown set to end then, whatever it was (shorter
  or longer), and a target that is off changes nothing, and the answer says which. The
  desired state is R10's, and covers a command in flight. Such a command is refused when
  it is more than a day ahead, running or not. Cost if wrong: none.
- **A pending command to turn off cannot be planned by voice or by an LLM tool; "turn off
  in N" sets the countdown, and `timerify.add_command` makes the command.** The outcome of
  a countdown is the same, and a second kind of pending command would need a sentence to
  tell them apart. The list of planned commands says them ("turn off at 11:00"), so a
  voice user can hear one that a service made. Cost if wrong: a user who wants a command
  to turn off that survives a later "turn on" uses the service.
- **Commands at a clock time are for an LLM only.** The tool takes `at`, read by the same
  parser as the service's (`command_time`), with exactly one of a delay and `at`
  (`command_when`), through the same controller path. The built-in agent's sentences take
  delays: core has no clock-time shapes to mirror, and §6.4's example is a delay. Cost if
  wrong: "turn on the boiler at 7:30" has no match (`docs/followups.md`).
- **Every setting of §5.4 that a target supports can be said, with one word per
  meaning.** The HVAC mode and the temperature have their own words, and "percent" and
  "mode" are single slots that each domain row declares the meaning of (brightness,
  percentage or humidity; fan mode, preset, humidifier mode or operation mode), so the row
  stays the one description of a domain. The values come from lists that hold only what
  the targets support: the HVAC words are translated per language, and the other modes are
  the device's strings, said with a space for an underscore ("eco plus 2" for `eco_plus_2`).
  The request is checked by the same `validate_settings` as the services, which refuses
  what the device cannot do, by voice and tool alike. Booleans for a number setting and
  fractions for a whole one are refused there, where every channel passes (`Coerce` would
  turn `true` into 1 % and 2.5 into 2). Cost if wrong: a device whose modes are hard to
  say must be said as it is written.
- **The unit of the temperature is optional, so the spec's own "cooling, 24" matches.** A
  bare number after a duration is taken as a temperature, and only for a target that takes
  one (the next entry scopes it). Cost if wrong: a number that was meant as something else
  after a duration ("for 1 hour 30") is a temperature, which a thermostat then checks and a
  device without one does not understand.
- **The HVAC and temperature parts are scoped to the domains that have them (`requires_context`
  on the domain of the name), in blocks of their own.** Before that, any thermostat with an
  "auto" HVAC mode made a bare "auto" an HVAC mode for a fan or a humidifier too, which
  refused it. The managed route always writes the domain of a name; a name listed by hand
  with no domain gets the sentences that fit every device and nothing more, so the README
  shows `context: domain` on a hand-listed thermostat or water heater. Said of a device that
  takes no temperature, "turn on the boiler for 1 hour 30" is not understood, and the
  answer is the built-in agent's "not aware of any device called boiler", which says that a
  device that exists is unknown: the mechanism of the entry above on names that are not a
  device with a timer, where a sentence of Timerify's wins the stage for unknown names.
  Before the scoping it was a refusal about the setting "Temperature" that also misled.
  Cost if wrong: that wording; and a user who lists a thermostat by hand without its
  domain gets no HVAC words.
- **The list of HVAC words is the union of the modes of every thermostat.** Two air
  conditioners with different modes, one without "auto": a bare "auto" said of the one that
  lacks it is understood and refused truthfully, naming the modes that AC has ("fan auto"
  and "in auto mode" still reach the fan mode). One block of sentences per distinct set of
  modes would close it and is its own step (`docs/followups.md`). Cost if wrong: that
  refusal.
- **Pending commands are cancelled by voice as "all" (the default) or "the next one",
  which repeats; an LLM may also cancel by id.** A voice cannot say an id. The tool that
  cancels by id says it cancelled one command, and one by "next" or "all" says that, so the
  answer is true to what was done. `async_cancel_command` returns what it cancelled. Cost
  if wrong: none.
- **The schedule is switched as a whole, or one interval by its title, and the lookup and
  its refusals live in one place, `controller.async_set_schedule_enabled`.** The voice, the
  tool and the interval switches share one path (a manual override wins, switching off
  folds what is due, nothing reloads the entry). The whole schedule is the default; one
  interval is said by the title it has, and the list of titles is one for the house, not
  one per timer, so "the Morning schedule of the pump" is understood and refused by the
  controller when only the boiler has a Morning (a list per timer is expressible, and would
  multiply the sentences by the timers). Two intervals of one timer with the same title are
  switched together, since refusing them as ambiguous would make a generated weekday title
  and weekend title unreachable. The answer counts the intervals that are now as asked,
  whether or not they already were, because switching is idempotent. Cost if wrong:
  titles that are said, not generated ones, are what voice can reach (below).
- **Titles are compared by `schedule.title_key`: the title as the built-in agent hears it,
  without punctuation and case, every dash a hyphen, the Russian yo a ye, runs of space one
  space.** So "morning" means `Morning!` and `06:30-07:15, Mon-Sun` means the generated
  title with en dashes. A title of nothing but punctuation has the key `""`, which matches
  nothing: the built-in agent does not know such a title either, so an LLM cannot ask for it
  and it is reached by the whole schedule or its own switch. Cost if wrong: such an
  interval is not named by an agent.
- **A refusal for an unknown title lists the titles that can be asked for, bare, each
  once, joined by semicolons, at most five; the translation chooses the quotes around the
  asked title.** A placeholder can be put in quotes as a whole but not each element of a
  joined list, and a generated title contains a comma, so the list is bare and
  semicolon-separated, and the asked title gets the quotes of its language (straight in
  English, guillemets in Russian). When more than five could be asked for, the text names
  the first five and counts the rest (`unknown_interval_and_more`), since it is spoken and
  read by an agent; when none can be asked for (every title is punctuation), it says so
  (`no_interval_titles`). Cost if wrong: a title with a semicolon in it reads as two.
- **A blank `interval` of the LLM tool means the whole schedule.** Core's tool wrapper
  drops an empty or whitespace argument for every tool before any handler sees it (blank
  equals absent is core's convention), and the tool's description says that no `interval`
  means the whole schedule. Refusing a blank would need a subclass of core's wrapper that
  fights that convention, and `enabled` is required (no default), so a model must say on or
  off and never toggles. Cost if wrong: a model that passes an empty string switches the
  whole schedule.

### Answers

- **Success speech is rendered by the built-in agent from response templates in
  `sentences/<language>/`; handlers set speech slots only, and refusals are spoken by the
  handler from the `exceptions` of the translations.** Backend translations have no plural
  rules, the LLM path never renders templates, and `async_set_error` is quiet, so each
  refusal is a translated text, with a setting named by its translated field name and a
  time as `HH:MM`, rendered for the language of the request (`async_error_text`). A caller
  of `intent/handle` that is neither agent gets no success speech. A target that does not
  match raises core's `MatchFailedError`, matched among the loaded timers' targets only
  (an empty candidate list would search the whole house), so core's translated answers are
  the ones heard. Cost if wrong: none.
- **A request language that Timerify has no texts for gets English, and a regional language
  gets the texts of its language.** `en-GB` is answered with the English sentences and
  texts, `ru-RU` with the Russian ones; a language with none, and the language `*` that an
  MCP client sends, fall back to English, for the text of a refusal as for a
  template. Cost if wrong: a Ukrainian speaker is told in English.
- **An answer says what the timer is set to do, not what the device shows.** While a
  command waits for an unavailable target, or a device has ignored one, or Timerify has
  given up after its repeats, the answer still gives the wish ("Boiler is on", "Boiler
  is off"), and the log has the rest. It is the desired state of R10 and spec goal 1, one
  source of truth for whether the target should run; the words "is on" can be read as the
  device's state, which is the price. An unavailable target with no timer is answered "off"
  (`docs/followups.md`). Cost if wrong: a user is told "off" of a device that is still on.
- **Russian answers start with the name of the target in the nominative, followed by a
  colon.** A name that the user chose cannot be declined, and a name in a sentence would
  need a case. Cost if wrong: none.
- **The macros of the answers (the words for a day, the plurals) are written once, in
  `sentences/<language>/src/`, and the files that are shipped are generated from them.**
  The sources are the sentences and one `macros.jinja` per language; `scripts/generate_sentences.py`
  writes the expanded `timerify.yaml` with a "generated, do not edit" header; a test says
  the shipped files equal its output and names the command to run, and another renders
  every response template of every language with representative slots through Home
  Assistant's own template engine. The manual route keeps working because it copies the
  expanded files (never `src/`, which Home Assistant would also read, since it loads every
  folder of `custom_sentences/<language>/`), and the hook that keeps Cyrillic out of the
  repository allows it under `sentences/<language>/` and its subfolders. The generator also
  deletes shipped files it no longer produces, and the drift test asserts the set. Cost if
  wrong: a contributor must run the script, and the failing test says how.
- **Russian is tested without Cyrillic in the tests: inputs are sampled from the shipped
  Russian files and the plural forms are proved by classes.** The hook forbids Cyrillic
  outside the translations and `sentences/ru/`. This proves that the Russian templates
  parse, reach their handlers and outrank core, and that the three plural forms partition
  the counts; it does not prove which word goes with which class, nor inflected names. The
  owner reads the rendered Russian texts of each phase; a swapped "few" and "many" passes
  the tests. Cost if wrong: a wrong plural noun reaches a user.

### The Voice settings entry and the sentence files

- **The "Voice settings" entry is a second kind of config entry beside the timers.** The
  user step of the flow is a menu, "Add a timer" and "Voice settings" (the precedent is
  the group helper); the form of a timer is the step `target`, and the options flow keeps
  `init` for a timer and goes straight to `voice_settings` for this entry. The kind is the
  option `kind`, narrowed with `TypeIs`. The menu offers the voice entry only while none
  exists; an abort with its own reason (`voice_settings_exist`) stays as the defence against
  two flows racing, because `already_configured` says "This entity already has a timer". The
  entry holds the option "add voice sentences for the built-in agent" (on at creation) and
  the languages, a choice of those Timerify ships (English and Russian), the house language
  when Timerify has it and English otherwise (§6.2). Its title is translated when it is
  created, so it stays in the language of its creation. Cost if wrong: none.
- **Timerify writes `custom_sentences/<language>/timerify.yaml` only where there is no file
  or its own, and its own is a file whose first line is exactly the managed header.** A
  file of the user at that path is their data (the user's manual change wins, §2): it is
  left as it is, that language is not written, and the log warns once per load, naming
  the path. The files are deleted only when they are Timerify's. Cost if wrong: a user
  whose own file blocks the managed one removes it, as the warning says.
- **Files are removed when the option is unticked, and when the entry is removed or
  disabled, and for a language no longer chosen; they stay across a reload and a restart,
  and are written only when their text changes, then one `conversation.reload` for all
  languages.** There is no churn at start-up or reload: the listeners attach after the
  first write and ignore events while the entry is stopping, and the debouncer is shut down
  before the files are removed, or a write could bring them back. The reload is not by
  language, because a reload by language misses the regional caches of the built-in agent;
  every cached language is rebuilt. Cost if wrong: none.
- **The file is rewritten when a timer is set up, unloaded or reloaded, when a target's
  entity or device changes its name or aliases, and when a schedule interval is added,
  deleted or renamed; the burst is debounced.** The first write happens before set-up
  returns when Home Assistant is running, and at start otherwise. A new mode that a device
  reports later (a firmware update) and a changed friendly name of a target that is not in
  the registry are picked up at the next trigger (`docs/followups.md`). Cost if wrong: such
  a name or mode is missing from the file until then.
- **The names are listed as the built-in agent lists them: every alias with the computed
  name, with punctuation removed, an empty name left out; `in` is escaped only when hassil
  would read it as a template, `out` is the name as Home Assistant shows it, and
  `context.domain` is the target's.** What is matched is what Home Assistant matches. A
  lone backslash is literal in hassil, so a name that differs only in characters the
  default agent keeps must be said with them. A name that is nothing but punctuation would
  match anywhere and is left out. Cost if wrong: a name with an odd character is said as it
  is written.
- **Before a file is written it is parsed, its references are resolved, and every value
  that it lists is checked to match as it is said; if any check fails the old file stays and
  an error is logged.** hassil parses sentences lazily, so building the intents proves
  nothing, and a file Home Assistant cannot read breaks Assist for the whole language. A
  title or name that cannot be said (an unescaped template character, a title that would not
  match as said) therefore refuses the write: a valid but stale file stays until the cause is
  fixed. Cost if wrong: a file that is stale for as long as the cause lasts.
- **The manual route is `custom_sentences/<language>/timerify_manual/`, and the managed
  entry warns when it finds it.** The managed file has the same file name as the copied
  one, and removing a copy by the entry would leave a half-installed manual set that breaks
  matching; two sets of sentences confuse the agent. The route is the sentence files of
  the repository (`timerify.yaml`, `core_commands.yaml`) and a `timerify_names.yaml` of the
  user's with the lists `timerify_target`, `timerify_interval` and, for the modes of
  devices, `timerify_mode`. Cost if wrong: none; the owner redoes it after every update and
  rename, which the README says.
- **A managed file left behind without Timerify's handlers makes the built-in agent raise
  on every phrase of it that matches, core's delayed commands included.** No public API
  catches the unknown intent, so Assist errors on those phrases until the file is removed.
  The README says to remove the entry before uninstalling Timerify. Cost if wrong: a user
  who uninstalls first removes the file by hand.
- **`hassil` is imported directly and listed in the dev group, and the manifest has
  `after_dependencies: ["conversation", "llm"]`.** The requirements of an after-dependency
  are installed first, which the sentence checks need. hassfest requires `conversation`,
  because Timerify imports that component, but removing `llm` still passes: hassfest does
  not check the imports of the other, so the declaration is harmless and kept, and a test
  pins it. Cost if wrong: none.

### LLM tools

- **Tools are offered for the Assist API only, while a target is exposed to the assistant
  that asks; descriptions, titles and the prompt are in English, and the prompt lists the
  names as a JSON list.** An LLM in another language reads English descriptions, as it does
  for every core tool, and a tool's text answers are in the language of the request. The
  tools act only on a target that is exposed to the asking assistant (`async_should_expose`
  with the assistant), and answer a translated refusal otherwise. The handlers return
  structured data; the LLM never sees a template. Cost if wrong: none.
- **The annotations are as core sets them for the same kind of intent.** None reaches
  outside Home Assistant (`open_world=False`). Telling how long is left and listing the
  commands only read. Adding time only adds. Stopping and switching a schedule give the same
  result when repeated (idempotent). Running a timer and planning a command replace the
  countdown and apply settings, as turning a device on and starting a timer do in core, so
  they are destructive; cancelling commands is destructive and not idempotent too, since the
  same call with "next" cancels another command each time (a firm promise). Cost if wrong: a
  client may ask for confirmation more often.

### Exposure

- **Timerify's own entities are not exposed to Assist by default.** In Home Assistant
  2026.10.4 the `number` is not in the default domains and the timestamp sensors are not
  exposed, and the interval switch is an entity of the configuration category
  (`EntityCategory.CONFIG`), which the default leaves out. The switch configures the
  timer's schedule, so the category fits: it moves to the configuration section of the
  device page, leaves the auto-generated dashboards, and is skipped by a service call that
  targets its device or area. The category changes no unique id and no name. Home Assistant
  decides once, when it first sees an entity, and keeps the decision, so a switch that it
  already exposed under 0.3.0 stays exposed after the upgrade (the README says how to take
  it away; a repair issue is in `docs/followups.md`). A test pins what each entity is.
  Cost if wrong: an upgraded house exposes its interval switches until the user unexposes
  them.

### Verification

- **The voice tests run in `tests/voice/` with `hass_tmp_config_dir` and an empty
  `configuration.yaml`, through the real default agent and the real Assist LLM API, with
  frozen time and no sleeps.** The tests that write sentence files write them into the
  temporary configuration folder. The hassil, `home-assistant-intents` and
  `gazetteer-matcher` versions of the dev group are the ones Home Assistant 2026.10.4
  requires, and the manifest test pins the declarations. Cost if wrong: a dev dependency to
  bump with Home Assistant.
- **A suite-wide timeout of 60 seconds fails a hung test instead of stopping the run.** A
  test that waits for something that never comes (a debounce, a reload) would otherwise
  hold the whole local gate. Cost if wrong: a slow machine must raise it.
- **The five tests of the first three phases that cancelled a command through
  `async_cancel_command` call `cancel_commands(NOW, [id])` of the core, with their
  assertions unchanged.** The cancel of one command and of several became one step of the
  core, so that voice cancels "all" or "the next one" in one stored change. Cost if wrong:
  none.
- **The smoke test adds the Voice settings through the menu of the flow and talks to the
  built-in agent over the REST API.** It checks the answer text and, through the REST API,
  the state of the target: an input boolean is refused as not exposed, then, once exposed
  to the `conversation` assistant, "turn on ... for 2 minutes" runs it, "how much time is
  left" answers 2 minutes, "turn off ... in 1 minute" ends it a minute later, a bare "turn
  on" runs it for the default 30 minutes and a bare "turn off" stops it. Cost if wrong:
  Russian and the LLM path are proved by pytest, not in the container.
