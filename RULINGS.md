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
- **A target whose registry id does not resolve at setup fails the entry** with
  `ConfigEntryError` (`target_not_found`), so Home Assistant shows the entry as failed and
  retries on reload. Changed in 1.1.0: a target entity that is gone at start-up or later
  raises a repair instead, and the timer stays loaded: see "A timer whose target was
  deleted stays loaded and switches nothing, with a repair that deletes it" under Release
  1.1.0.

### The timer

- **A rejected command is retried, an in-flight one is not repeated.** A failed or timed
  out call marks the wish to turn on or off as unsent (in memory only); it is sent again
  when the target next reports its state, or by the next command that wants the same
  thing. A call that returns without error while the target still shows the old state
  counts as not delivered too, so a device that acknowledges and ignores a command (an MQTT
  switch out of range, a cloud integration that only acknowledges) is sent it again. This
  is how "pending commands are firm promises" holds. Cost if wrong: a device that confirms
  its state only after the call returns may get one duplicate, idempotent command.
  Reports send an unsent wish again at most `automatic_resends` times (changed in 1.1.0:
  reports of any kind count, after a free first delivery; see "Engine and reliability"
  under Release 1.1.0), a field of the domain row: `MAX_AUTOMATIC_RESENDS` (three)
  for every row except `remote` and `media_player`, which get none. Then one warning is
  logged and nothing more is sent (per piece of work since 1.1.0, see Release 1.1.0).
  Without the bound, a device that refuses a command and answers it with a report of its
  old state would be commanded for ever. Remotes and media players get none because a
  toggle-based remote can be switched back off by a repeat and a media player that is
  still booting reports a state that is not on; they are sent the command again only when
  it is asked again or when the timer itself switches them. Cost if wrong: an ignoring
  media player is retried only then.
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
  interval. Changed in 1.1.0 (#13): the folds of start-up and of a report of the target
  write them too, through `_execute_fold`; see "Engine and reliability". A command
  dropped because the run it asked for is over is an effect of the core (`CommandDropped`) that the controller logs at info level; the core
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
  applies to every window it is given). Changed in 1.1.0: see "An unreadable stored timer
  is reset only by the user" under Release 1.1.0, for what the set-up fails with and what
  the user does. Only the timer's own code writes the file, so such a file means a defect,
  and it should show when the timer loads, not as a target switched for reasons nobody can
  follow. Versions 2 and
  3 were never released before their keys were complete, so they need no further steps.
  Cost if wrong: a version 2 or 3 file written by a development build from between the
  changes lacks a key and fails to load; that exists on developer machines only.
- **The snapshot is stored before a command is sent.** A restart during a slow call would
  otherwise lose a newly set countdown.
- **At start-up the merge of the windows arms the stored wake-up.** `set_windows` always
  returns the alarm for the merged snapshot, the earliest of the stored end, the first
  stored command and the start and end of every window, and it is the first effect of the
  one `_execute` that also carries the first observation; an unchanged snapshot produces
  no new alarm from the core otherwise. A restored timer arms nothing earlier. Changed in
  1.1.0: a change made while starting first catches up and may arm its own alarm (see
  "Until start-up has taken stock" under Release 1.1.0).

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
  `GaveUp("settings")` once.** Changed in 1.1.0: see "Each piece of work has one allowance
  of automatic re-sends for its whole life" under Release 1.1.0.
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

- **A deleted target still gives no sign.** Changed in 1.1.0: see "A timer whose target was
  deleted stays loaded and switches nothing, with a repair that deletes it" under Release
  1.1.0.

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
  changed in YAML and applied with "reload core configuration" fires no such event (issue
  #14). Cost if wrong: windows in the old zone until the next refresh.
- **The search horizon is `WINDOW_SEARCH_DAYS = 14`.** A weekday interval always matches
  within 7 days; a Workday-based one with no match is searched again when the sensor
  reports, daily. Cost if wrong: none found.
- **A window carries only the settings of its interval that the target takes when the
  window is worked out; the rest are left out and said once.** Changed in 1.1.0: see "The
  settings are filtered when they are sent, whoever owes them" under Release 1.1.0.
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
- **A change before Home Assistant has started is not held back.** Changed in 1.1.0: see
  "Until start-up has taken stock, nothing reaches the target, and a change made
  meanwhile first folds what fell due before it." under Release 1.1.0.

### The entry, the intervals and the entities

- **One update listener reloads the entry on any change (`async_schedule_reload`, which
  does not merge repeated changes: each call runs a reload, and the reloads wait for one
  another on the entry's lock); `options_flow_reloads = False`; `_follow_target` no
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
  device. The made device goes once the target has a device of its own (see "Release
  1.0.0"). Cost if wrong: none.
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
  language after the house language changes (issue #15).
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
- **A renamed Workday sensor is followed, and a removed one is not.** The option holds
  the entity id, and the entry keeps it in step with the registry as it does for the
  target; see "Release 1.0.0". A removed sensor leaves the option as it is, and the
  intervals wait with a warning, as for a sensor that is away. Cost if wrong: the
  schedules of working-day intervals stop until the user picks another sensor.

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
- **The English phrasings of the schedule take "of" and "for", "schedule" or
  "scheduling" with the article optional, and on or off before or after the noun, because a
  phrasing that is left out is not left alone.** The built-in agent takes "turn off the
  schedule for the boiler" and "turn off scheduling for the boiler" for a turn off of the
  boiler, so the near misses that were found are sentences. The set is open ended: a
  phrasing with a device's name that Timerify does not have, and "turn on" or "turn off" in
  it, can still be matched by core's gazetteer (English only), which is issue #21 (see
  Release 1.1.0, Voice). Cost if wrong: the boiler is switched off by a sentence meant for
  its schedule.
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
  beyond a week is not understood, and a test pins that bound too. The delay of a delayed
  command is counted with the same lists, so the week is its bound too (see Release 1.1.0,
  Voice). The tools take any count and the controller decides. Cost if wrong: "for 200
  hours" is answered as not understood, not with the limit.
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
  varies by machine). Cost if wrong: "turn on the boiler for two thousand minutes" said
  in words matches no sentence of Timerify's, and the answer is the built-in agent's
  "Sorry, I am not aware of any device called boiler for two thousand minutes", which
  reads the count as part of the name and so says that the boiler does not exist, while
  "for 2000 minutes" is understood and answered with the limit ("A timer runs for 1 min to
  24 h.").
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
  wrong: "turn on the boiler at 7:30" has no match (issue #19).
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
- **A temperature can be said up to 250, in halves, as words or digits, because the
  sentences do not know the unit of the device.** A house that counts in Fahrenheit sets
  a water heater at 110 to 140 degrees, so a range that ended at 100 made "turn on the
  tank for an hour at 120 degrees" not understood, while an LLM tool, which has no such
  bound, could set it. The sentences cannot know the unit or the range of each device (a
  list that holds a range per device is expressible, and would multiply the sentences by
  the devices), so the range is the widest any device could be given: 250, the bound of
  the service form's selector too, which is above the boiling point in Fahrenheit. The
  controller still judges the number against the range the device reports, so 200 degrees
  said to a heater that takes 100 to 150 is understood and refused with those numbers,
  and a number past 250 is not understood. The numbers may be said as words: the table of
  number words that the first request in a language builds is 500 numbers here (1 to 250
  with the halves), which costs 0.13 s and 15 MB in Russian and 0.01 s and 2 MB in
  English (hassil 3.12, a fresh process, as for the duration above), against 0.05 s and
  5 MB before for a range of 1 to 100; the first Russian request that says a temperature
  went from about 0.38 s to about 0.44 s through Assist. That is small, so the words stay, unlike
  the week of minutes, which is digits only. The structural test that bounds the words
  of every range counts the numbers of a range (the halves too) and where it ends.
  Cost if wrong: a number above 250 is not understood, and a few tenths of a second of
  the first Russian request in a language.
- **The unit of the temperature is optional, so the spec's own "cooling, 24" matches.** A
  bare number after a duration is taken as a temperature, and only for a target that takes
  one (the next entry scopes it). A device without a temperature reads hours followed by a
  bare number up to 59 as minutes instead ("for 1 hour 30" is 90 minutes: see "A scope of
  settings carries every rule of its block" in the voice section of release 1.1.0).
  Cost if wrong: a number that was meant as something else after a duration ("for 1 hour
  30" said to a thermostat, "for 2 hours 120") is a temperature, which a thermostat or a
  water heater then checks and refuses when it is out of its range, while a device
  without one does not understand "for 2 hours 120", since the bare minutes stop at 59.
  The temperature is understood up to 250, so "turn on the AC for 2 hours 120" is answered
  "120 is not a valid Temperature: it must be between 16 and 30." and nothing is switched,
  while a water heater that counts in Fahrenheit takes the same 120 as its temperature
  (probed on both).
- **The HVAC and temperature parts are scoped to the domains that have them (`requires_context`
  on the domain of the name), in blocks of their own.** Before that, any thermostat with an
  "auto" HVAC mode made a bare "auto" an HVAC mode for a fan or a humidifier too, which
  refused it. The managed route always writes the domain of a name; a name listed by hand
  with no domain gets the sentences that fit every device and nothing more, so the README
  shows `context: domain` on a hand-listed thermostat or water heater. Said of a device that
  takes no temperature, "turn on the boiler for an hour at 55 degrees" is not understood,
  and the answer is the built-in agent's "not aware of any device called boiler", which
  says that a device that exists is unknown: the mechanism of the entry above on names that
  are not a device with a timer, where a sentence of Timerify's wins the stage for unknown
  names.
  Before the scoping it was a refusal about the setting "Temperature" that also misled.
  Cost if wrong: that wording; and a user who lists a thermostat by hand without its
  domain gets no HVAC words.
- **The list of HVAC words is the union of the modes of every thermostat.** Two air
  conditioners with different modes, one without "auto": a bare "auto" said of the one that
  lacks it is understood and refused truthfully, naming the modes that AC has ("fan auto"
  and "in auto mode" still reach the fan mode). One block of sentences per distinct set of
  modes would close it and is its own step (issue #25). Cost if wrong: that
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
  device's state, which is the price. The one exception is the answer to a question about
  a timer that wants nothing on (see "Release 1.0.0"). Cost if wrong: a user is told "off"
  of a device that is still on.
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
- **Russian is tested without Cyrillic in the test code: inputs are sampled from the shipped
  Russian files, the plural forms are proved by classes, and the answers for each class of
  counts are pinned by a fixture.** The hook forbids Cyrillic outside the translations,
  `sentences/ru/` and `tests/fixtures/ru/` (see Release 1.1.0, Voice). Sampling proves that
  the Russian templates parse, reach their handlers and outrank core, and the classes that
  the three plural forms partition the counts; the fixture says which word goes with which
  count. Inflected names are not proved: the owner reads the rendered Russian texts of
  each phase. Cost if wrong: a wrong inflected name reaches a user.

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
  languages.** There is no churn at start-up or reload: the first write comes when every
  timer is there, and a write that finds the text unchanged writes nothing and tells
  nobody. The listeners attach just before it, so that a timer set up or a target renamed
  while it runs is not missed (it is written by the write that follows), and they ignore
  events while the entry is stopping; the debouncer is shut down before the files are
  removed, or a write could bring them back. The reload is not by
  language, because a reload by language misses the regional caches of the built-in agent;
  every cached language is rebuilt. Cost if wrong: none.
- **The file is rewritten when a timer is set up, unloaded or reloaded, when a target's
  entity or device changes its name or aliases, and when a schedule interval is added,
  deleted or renamed; the changes are debounced.** A change is written one cooldown
  (`VOICE_SYNC_COOLDOWN`, one second) after the first of the changes that come in a row,
  never twice within a cooldown, so a burst that lasts longer is written more than once;
  Home Assistant's `Debouncer` does not move its timer for the changes that follow and
  drops a call that falls due while a write runs, so a write that finds a change came in
  during it schedules another. The first write happens before set-up returns when Home
  Assistant is running, and at start otherwise. A new mode that a device
  reports later (a firmware update) and a changed friendly name of a target that is not in
  the registry are picked up at the next trigger (issue #20). Cost if wrong: such
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
  decides once, when it first sees an entity, and keeps the decision, so a switch that
  version 0.3.0 made an ordinary one would stay exposed after an upgrade; that version
  was never published (see "Release 1.0.0"). A test pins what each entity is. Cost if
  wrong: a house that ran 0.3.0 exposes its interval switches until the user unexposes
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

## Phase 5: card

The decisions of the dashboard card's phase (`docs/superpowers/plans/2026-10-30-phase-5-card.md`),
in the form they have now. Where a later decision replaced an earlier one, only the final
behaviour is written. Section numbers (§) and rules (R, S) are those of the spec.

### Delivery and registration

- **The card is served by the integration and loaded on every dashboard through
  `frontend.add_extra_js_url`, once, in `async_setup`; no Lovelace resource is created.**
  The module sits in `custom_components/timerify/frontend/` and is served with
  `async_register_static_paths` (a second registration of the same path raises, which is why
  it belongs to the integration and not to a timer). Its address carries
  `?v=<the first 16 hex digits of the file's SHA-256>`, computed in an executor job, so a new
  bundle is fetched at once. `manifest.json` has `http` among the `dependencies` and `frontend`
  among the `after_dependencies`, and the call is made only when `"frontend"` is among the
  loaded components, so a Home Assistant without a frontend still starts. A Lovelace resource
  would be storage-only and admin-only, would conflict with dashboards in YAML mode, which keep
  their resources in YAML, and the user would have to add it. Cost if wrong: a module loaded
  this way meets the known first-load issue on 2026.10 (the last entry of this section), which
  a Lovelace resource does not.
- **The registration is proved in two places: pytest checks the static path and the headless
  case, and the smoke test and the end-to-end tests check what only a real frontend shows.**
  The frontend cannot be set up in pytest without the `home-assistant-frontend` package and a
  dozen components, so that package is not a dev dependency; the test that the call is made once,
  with the right address, across two timers and a reload, patches `add_extra_js_url` and
  declares the `frontend` component. Whether the index page really loads the module is checked
  in the container. Cost if wrong: a regression of `add_extra_js_url` alone is seen by the smoke
  test (about fifteen minutes) and not by pytest.
- **The bundle is committed, and the build is deterministic and checked.** HACS downloads the
  repository, and a zip release would need a release workflow, which stays disabled with
  GitHub Actions. esbuild builds the bundle (one dependency; Lit is used without decorators,
  with `static properties` and `static styles`) and `tsc --noEmit` checks the types, with
  TypeScript 6.0.3, which is what the frontend builds with. `npm --prefix card run build:check`
  rebuilds in memory and fails when the committed file differs, and it is part of the gate.
  Cost if wrong: whoever changes the card rebuilds and commits the bundle with it, and the
  bundle cannot be reviewed; the TypeScript can.
- **The card's sources live in `card/`, a self-contained npm project (its own `package.json`,
  lockfile and configuration), and its checks run as `npm --prefix card ...`.** This keeps Node
  tooling out of the Python root and out of the integration folder that HACS downloads. Cost if
  wrong: one more directory to know.
- **The bundle is minified, with legal comments kept at the end and no source map; it is served
  at `/timerify_frontend/timerify-card.js` with `cache_headers=True`; `.gitattributes` marks it
  `-text -diff linguist-generated=true`.** Every dashboard loads it when it opens, and Lit's BSD
  licence notice has to travel with it; `/timerify` is kept free for a later sidebar page;
  converting line endings would break the byte check, and a one-line file would flood every
  diff. Cost if wrong: an error in the browser points into the minified file, and a reader
  reads the TypeScript.
- **The module defines `timerify-card` and adds itself to `window.customCards` inside one "not
  defined yet" guard, and the entry is added to the array, which is never replaced.** The
  frontend reuses the array, and a second copy of the module (a resource a user added by hand
  beside the one Timerify loads) must neither throw nor list the card twice. Cost if wrong: the
  copy that runs first defines the element, so an old copy added by hand wins over the bundled
  one.
- **After installing or updating, the browser must be refreshed once, and the README says so.**
  The frontend reads the list of modules when the page loads. Cost if wrong: a user who does
  not refresh sees the old card, or none.
- **Every npm package is pinned to an exact version at least two weeks old on 2026-10-30, with
  the lockfile committed and `npm ci` the only install: lit 3.3.3 (the frontend's), esbuild
  0.28.2, typescript 6.0.3 (the frontend's), vitest 5.0.5, happy-dom 21.0.3, @playwright/test
  1.64.1 and @types/node 26.6.5, on Node 26.** The same rule holds for every package, checked
  with `npm view`. Cost if wrong: a bump is a reviewed change of the lockfile; happy-dom 21.0.4,
  which fixes an advisory in a package that only runs the tests, becomes two weeks old on
  2026-11-03 and is pinned then (issue #28).

### Finding the timer

- **The card is configured with the timer's "Run for" number, and Timerify tells it the rest
  through a websocket command, `timerify/timer {entity_id}`.** The answer holds the entry id,
  the target, the mode, the default duration, the entity ids of "Ends at" and "Next command",
  the settings of the target's domain that are percentages (`percent_settings`, see "Release
  1.0.0"), the list of those two that are disabled in the registry (`disabled_sensors`) and
  each interval's switch with its title. The number is the one handle that names exactly one
  timer: the display registry the frontend keeps carries neither the config entry nor the unique
  id of an entity, and two timers can share a device. The answer is configuration, read from
  the entity registry and the entry and never from the running timer, and it is given for any
  Timerify timer entry whatever its state, so a lookup that meets an entry that is still starting
  (at every start and every reload) is answered. Cost if wrong: one more command to keep in step
  with the card.
- **The command is read-only and open to every user, and it tells a user only what the user
  may read.** It checks the permission to read the number first, before anything is looked up,
  so that a user who may not read an entity cannot tell by the answer whether it is a timer's;
  then the target, "Ends at" and "Next command", and it refuses the whole answer when any of
  them is unreadable; the interval switches the user may not read are left out. This is what
  core's commands about entities do. The card reads the refusal (`unauthorized`) as its own
  state and says so: see "The card never goes quiet" below. Cost if wrong: a user restricted by
  custom permissions gets a card that cannot show its timer, and the error is logged as it is
  for core's own commands.
- **`timerify/timer` also returns `target_on`, the target's on-rule from `domains.py` as data
  (`OnRule` replaces `DomainBehaviour.is_on`), and `default_duration` is null in loose mode;
  there is no `runtime` key, because the card does not show the runtime (phase 6).** The card
  must say "on without a countdown" and decide what a long press does exactly as Timerify judges
  the target, without a copy of the domain table in the browser (§2). Cost if wrong: none; a card
  feature that shows the runtime adds the key (see "The forms and the card" in phase 6).
- **The lookup is asked again on a new configured entity, a new `hass.entities` (an interval
  added or deleted shows up there), the connection coming back and the number's state becoming
  available. A `not_found` shows a warning only while the number is missing or has a value,
  never while it is `unavailable`; a refusal (`unauthorized`) shows its own warning; a
  `timer_incomplete` shows its own neutral line in every state of the number (see "Release
  1.0.0"); any other failure (a lost connection, an error code the card does not know) shows
  the card as unavailable until the next trigger and says nothing.** An unavailable number may
  be a timer that is still starting, and a warning would flash at every restart or every
  dropped connection; the card asks again when the number has a value. A `timer_incomplete`
  is read from the registry, which keeps a timer's entities across a restart, so it does not
  flash at one. Cost if wrong: a failure that is
  not one of the two named stays silent until the card asks again.

### What the card shows

- **"Ends at" carries `started_at`, the moment the current countdown began, and it is stored
  with the timer.** §6.3 asks for a fill that shows progress, which needs the length of the
  countdown. A restart keeps it. Cost if wrong: an attribute to keep in step with the card.
- **`started_at` is written only by `_set_end(end, *, began, by=None)`:** the time of the set,
  of R4 or of a strict bare run; a command's own time; a window's start, also when the window
  extends a manual countdown (S1), which makes the fill full again; and, for adding time,
  subtracting it and the realignment of S2, the kept beginning, `_kept_beginning(at)`, which is
  `min(kept, at)` for the instant the writer works at (a bare run of a target that already runs
  writes nothing). It is null otherwise. A file of the previous format migrates to null, so a
  countdown that runs during the update shows a full fill until it is set again. A beginning at
  or after the end, or without an end, is a corrupt file. The fill must be right after a late
  fold or a restart (P3, §5.7); a clock that steps back must never make the stored file
  unreadable; an update must not invent a beginning; and a window over a manual countdown
  restarts the fill. Cost if wrong: a countdown that runs during an update has no progress until
  it is set again.
- **The fill is the share of the countdown that is left, full at the start and empty at the
  end, clamped to 0..1; the time left is `M:SS` or `H:MM:SS`, rounded up, like the "Run for"
  number (§6.1).** Home Assistant's own timer card rounds down. An open run is full, an idle
  timer is empty, and a countdown with no known beginning is full. The format agrees with the
  number on the device page and needs no plural in any language. Cost if wrong: none.
- **The card counts down on a one second interval that runs only while a timer has an end ahead
  and the card is on the page, with the browser's clock against the end time of "Ends at", and
  it writes no state.** Home Assistant's timer card does the same, with no offset to the
  server's clock. The time left never goes below 0:00 and the fill stays between empty and full
  when the browser's clock runs ahead or behind; the end time shown is the server's; every
  action goes to the server. Cost if wrong: a device with a wrong clock shows a time left that
  is wrong by as much; a server offset is issue #8.
- **Clock times: the same local day shows the time, the next six days the short weekday and the
  time, later ones the date and the time.** They honour `locale.time_zone` (`server` is
  `hass.config.time_zone`) and `time_format` (`12`, `24`, `system`, which is the browser's
  locale, and `language`, which is the user's language). Minutes are whole, so `number_format`
  changes nothing but grouping, which is off. A timer ends at most a day ahead and a command at
  most seven. Cost if wrong: none.
- **A new `hass` renders the card only when one of its own entities' state objects, the locale,
  the language, `localize`, `config`, the user, the connection or the registry changed; any
  update that does not carry a new `hass` passes; the pop-up renders its content only while it
  is open, applies the same filter, and gets a fresh view from each card render so that its time
  ticks.** The setter runs on every state change of the home, and strings arrive as a new
  `localize` alone. The filter holds the three formatters (`formatEntityName`,
  `formatEntityState`, `formatEntityAttributeValue`) too: the frontend recomputes them in a
  separate update after a change of language or of the registry, so the update that carries the
  new language can reach the card with the old formatters and the card, having drawn its
  states in the old language, would keep them until a state changed. Cost if wrong: a field of
  `hass` that the card starts to read and is not in the filter shows stale until something else
  changes.
- **`ha-card`, `ha-icon` (`.icon`) and `ha-state-icon` (`.stateObj` only) are the only
  frontend elements the card renders, and nothing waits for their definition.** The icon logic
  of every domain and the theme's card frame exist nowhere else, and they are defined when a
  card connects. `ha-state-icon` reads the formatters and the entities from the frontend's Lit
  contexts, so outside `<home-assistant>` (in the unit tests) it shows no icon, which is
  expected. Cost if wrong: if one of them is renamed, the card loses its frame or its icon, not
  its function.
- **A timer that is unavailable has nothing to act on: its presets, plus, minus, Stop, each
  cancel button, the pill's chip and the round tile's long press do nothing, and the buttons
  and the chip are disabled.** Home Assistant leaves an unavailable entity out of a service
  call without a word, and a press would seem to do nothing. Cost if wrong: none.
- **The card never goes quiet when it cannot work: a missing Ends at, a hidden Next command, a
  refused user and a timer that cannot be told of each say so in words.** With **Ends at** disabled the card shows, in its body
  and in the style of its other warnings (a `role="alert"`), the translated line that names the
  sensor and tells the user to enable it, because without it there is no countdown to draw. With
  **Next command** disabled the card works, and the pop-up puts one translated line naming the
  sensor in the place of the pending commands, because an empty list would claim that nothing is
  pending. A user the server refuses gets the line "You are not allowed to see the timer" with
  the entity id of the number. A timer that cannot be told of gets a neutral line that sends
  the user to the timer's page (see "Release 1.0.0"). A lookup that fails otherwise (a lost
  connection) stays silent: see "Finding the timer". Why: a card that draws an idle timer, or
  nothing, with no word is taken for a broken card, and these are the states where the cause
  is known and the remedy is the user's. The card learns that a sensor is disabled from the server
  (`disabled_sensors` in the `timerify/timer` answer, read from the registry's `disabled_by`,
  whoever disabled it) and never from a missing state: a sensor that is enabled but not loaded
  yet has a restored `unavailable` state, and one that has no state at all may as well be
  hidden or deleted, so a missing state is not proof of a disabled sensor. Cost if wrong:
  a sensor disabled by a mechanism that leaves `disabled_by` empty shows the old silent
  behaviour; and the answer has one more key that the card must keep in step.
- **A pending command whose action is neither on nor off is left out of the pop-up, as a row
  with no id or no time is.** The card shows the rows it can read, and one it cannot read must
  not hide the others. Cost if wrong: a command of a kind added later is not listed until the
  card knows it.
- **The Russian rows of pending commands put a colon between the verb and the time, with no
  preposition before it: "Turn off: Tue 07:00", in Russian words.** The time may begin with a
  weekday ("Tue 07:00"), and a Russian preposition before a clock time depends on the word that
  follows ("at 7:00", but "on Tuesday"), which a template cannot choose for a formatted time. The
  colon is right for every form the time takes. The Cyrillic stays in `ru.json`. Cost if wrong:
  the rows read as terse labels, not as sentences.

### What the card does

- **The card acts only through Timerify's services and entities: `number.set_value` on "Run
  for" (a preset; 0 stops), `timerify.add_time` (plus, minus, the chip), `timerify.run` with no
  data (the long press), `timerify.cancel_command` and `switch.turn_on` or `switch.turn_off`
  (the intervals), each with `target: {entity_id}` and with `notifyOnError` left on.** It reads
  only the states of the entities that `timerify/timer` names and the target's, and
  `hass.entities` for the picker's stub. It adds no state writes and nothing counts down on the
  server (§2). Cost if wrong: none; whatever the card does can be done by an automation.
- **A tap opens the pop-up in both layouts, and a hold on the round layout runs the timer with
  no duration through `timerify.run`, or stops it while it runs; the pill has no hold.**
  `timerify.run` with no duration is R9: in strict mode the default duration, in loose mode an
  open run, and a target that already runs keeps its countdown. A running timer, with or without
  a countdown, is stopped by `number.set_value` 0. Cost if wrong: none.
- **A tap is the `click` event of the card's body (a mouse, a finger, the keyboard and assistive
  technology all produce it); a hold is added on top of it.** The hold fires on release after
  at least 500 ms, as Home Assistant's own handler does, and swallows the click that follows
  it. Enter (on `keydown`, with `preventDefault`) and Space (on `keyup`, with `preventDefault`
  on `keydown`) call the same handler, since a body that is not a native button gets no click
  from the keyboard. A cancelled or moved-off pointer aborts the press, the context menu is
  suppressed while a hold is pending, and `data-held` on the card, which makes the ring pulse,
  says that letting go will act. A visible focus ring (`:focus-visible`) shows keyboard users
  where they are on the card. The pill has no hold: with a mouse a long press there is a tap,
  and on touch it does nothing. Cost if wrong: a user may expect a long press on the pill to
  act; there is none for keyboard users either, who start and stop through the pop-up.
- **The body is an empty layer that covers the whole card, border included, under the content,
  as in Home Assistant's tile card; it carries `role="button"`, `tabindex="0"`,
  `aria-labelledby` the name and the status text, and, on the pill, the fill; the round tile's
  ring is in the content and its body is empty.** The content row above it has
  `pointer-events: none`, so a press anywhere on the card reaches the body; the chip is a
  sibling of the body, not inside it, and has `pointer-events: auto`. A button inside an element
  with `role="button"` is presentational, so assistive technology would not see the chip; as a
  sibling, its presses also never reach the body, so a chip press never opens the pop-up. Cost
  if wrong: a theme with an unusual card border or radius may leave the layer a pixel off the
  card's edge.
- **Only the primary pointer starts a hold, and with a mouse only the main button. A click is
  swallowed only if it comes before the next `pointerdown`: Android sends no click after a long
  press, and a click that never came must not eat the next real tap.** Enter calls
  `preventDefault` on `keydown`: the press opens a dialog that takes the focus, and without it
  the browser would go on to press the button the focus has moved to. The card of each layout
  has `user-select: none` and `-webkit-touch-callout: none`, so that a long touch brings up
  neither a text selection nor the browser's callout, and the body has
  `-webkit-tap-highlight-color: transparent`. The rules are on the card and not on the empty
  body, because the text is in the content. Cost if wrong: the text on the card cannot be
  selected; the pop-up's can.
- **The chip's accessible name is "Add {duration}", with the duration written by `formatMinutes`
  as the chip shows it, so the spoken name contains the visible label (WCAG 2.5.3, "Label in
  Name"); the pop-up's plus and minus use the same strings, "Add {duration}" and "Take off
  {duration}".** Cost if wrong: none.
- **Plus and minus step 5 minutes, which is not configurable; minus is offered only while a
  countdown runs; the chip is ignored by the round layout.** §6.3 lists no step field, and a
  user who wants another step uses a preset. Cost if wrong: a user who wants a step of 10
  minutes adds a preset or a chip.

### The pop-up

- **The pop-up is the card's own native `<dialog>` in its shadow DOM, opened with
  `showModal()`.** The platform traps the focus, closes it on Escape and makes the page behind
  inert, and the card needs no frontend internals (`show-dialog` and `ha-dialog` are internal
  and unversioned). The end-to-end tests prove it in a real Home Assistant: the dialog is modal
  above the application, the page behind it takes no input and Escape closes it and gives the
  focus back to the card. Cost if wrong: it does not look exactly like Home Assistant's own
  dialogs, and takes the theme only through CSS variables.
- **The pop-up closes on Escape, on its close button and on a click on the backdrop, which is a
  press that begins and ends on the dialog itself; the browser's Back is not intercepted; a
  refused action is reported by Home Assistant's own toast and the pop-up stays open.** The
  dialog has no padding of its own, so a click on the backdrop has the dialog as its target, and
  so does the click that ends a text selection dragged from the content to the backdrop, which
  must not close it. Chromium on Android closes a modal dialog on Back by itself (unverified in
  the companion apps), and on iOS Back leaves the view: no history handling that Home
  Assistant's internals own. A refused action is reported by `notifyOnError`, a popover in the
  top layer above the dialog, and the card catches the rejection. Cost if wrong: Back may leave
  the view instead of closing the pop-up in the companion apps.
- **The settings link is shown only to an administrator, and it is a plain same-origin `<a
  href>` to `/config/integrations/integration/timerify#config_entry=<entry_id>`, whose click
  handler only closes the pop-up.** A user who is not an administrator cannot open the page, so
  the link is hidden, not disabled. Home Assistant's own window click listener follows the link,
  with the history entry its back arrow needs, so the card never calls `pushState`. A Ctrl, Cmd
  or Shift click is the browser's and the pop-up stays; an Alt click is Home Assistant's and
  the pop-up closes. Cost if wrong: a change of that listener in the frontend breaks the link;
  the page is still reachable by hand.

### Strings and language

- **The card's words live in `translations/<language>.json` under the top-level `common` key,
  which hassfest accepts, as flat slugs with the prefix `card_`, and are loaded at run time with
  `hass.loadBackendTranslation("common", "timerify")`.** Entity names and states come from the
  existing entity translations through `hass.formatEntityName` and `hass.formatEntityState`.
  Cyrillic stays in `ru.json`. Custom integrations have no `strings.json`; `en.json` is the
  source. Cost if wrong: a language without a file shows English.
- **The card's strings are typed by the keys of `en.json` `common`, and that English is built
  into the bundle and used only before any card has loaded strings.** Config errors and the
  picker's description use `lastLoaded()`, the last `hass` whose strings arrived, since
  `setConfig` and `getConfigForm` run without `hass`; so do the editor's names of the two
  layouts, the labels of its preset options and the text under them, because the form that Home
  Assistant builds is given no way to translate those. The editor's field labels use the
  frontend's own `localize`, and everything else the card's own `hass.localize`. A misspelt key
  fails `tsc`, a stale bundle fails `build:check`, and a page whose first card is invalid shows
  that error in English. Cost if wrong: the editor's option labels and helper come from the last
  strings a card loaded, and are English when none has (issue #9).

### The editor and the picker

- **The editor is Home Assistant's own form, from `getConfigForm`, the documented way for a
  custom card.** The fields are `entity` (an entity selector filtered to Timerify's `number`
  entities), `layout` (`pill` or `round`), `name` and `icon`, `presets` (a multiple `select`
  with custom values, the defaults as options) and `chip` (a number). A card added from the
  picker is written with `layout: pill` and the five default presets, so the editor shows them;
  `getStubConfig` picks the first Timerify timer, by entity id. Cost if wrong: a change of the
  frontend's form components changes the editor, and the end-to-end tests that find them by role
  catch it.
- **Presets default to 15, 30, 45, 60 and 120 minutes. An empty list stands for the defaults, in
  the editor and in YAML, and digit strings are accepted as well as numbers.** Taking the last
  chip away in the editor writes `[]`, and it must not throw the user out of the form; the
  editor's `select` writes strings. A user who adds one preset must not lose the others
  unseen. Cost if wrong: a YAML `presets: []` also means the defaults.
- **The editor's `assertConfig` checks only the shape of a config, as Home Assistant's own cards
  with a form do, and `setConfig` keeps the value rules.** A wrong type (presets that are not a
  list, a layout that is not text) sends the editor to YAML; a value of the right kind that the
  card cannot use (a preset of 0, a chip of 1441, a layout "square") keeps the user in the form
  while the preview shows the card's own message. Cost if wrong: a typed 0 shows an error card
  in the preview and not in the form.
- **A list of numbers that is written by hand shows in the editor as bare chips ("15" and not
  "15 min") and its drop-down offers the defaults again; picking one adds a duplicate, which
  the card removes.** The label lookup of the frontend's select is a strict `option.value ===
  item` and the options are strings; the schema cannot change it. The README tells users to
  write the presets as text. Cost if wrong: the form shows both "15" and "15 min".
- **The editor cannot preselect the layout of a hand-written card that has none, because the
  frontend does not apply the defaults of a card's form (checked in frontend 20260930.5).** A
  card from the picker carries `layout: "pill"`. Cost if wrong: the form shows no layout
  selected for such a card, which is a pill.

### Verification and tooling

- **The end-to-end tests and the smoke test share one harness, `scripts/harness/hass.py`,
  parameterised by project, port and configuration directory; the end-to-end tests use it
  through `python -m scripts.e2e.hass up|restart|down`, which Playwright's global setup and
  teardown call from the repository root.** There is one onboarding and compose path. The
  smoke test (port 18123) and the end-to-end tests (18124) can run side by side. The smoke
  command became `uv run python -m scripts.smoke.run`. Cost if wrong: the smoke test's command
  changed.
- **The end-to-end tests (Node, `@playwright/test`, Chromium) run serially against one container
  at `http://localhost:18124`, in New York time.** They cover both layouts, the pop-up's
  actions, the long press, the editor and the picker, a user who is not an administrator,
  Russian, and a restart of Home Assistant in the middle of a countdown that the card sees
  through. Each test logs in through the real login page, waits until the frontend's service
  worker serves the page and loads it once more before acting. Before each test the fixture is
  restored whole (the numbers 0, the commands cancelled and the fixture command added again,
  the interval switch on; the interval sits 12 hours from the run), and each test creates its
  own starting point. Tests get 60 s and assertions 10 s, the restart test 300 s and 120 s for
  the countdown to return. The restart test proves that the frontend has reconnected from its
  own `connection-status` events (disconnected, then connected again), never from a pause.
  The fixture has three timers: two with Ends at enabled (one strict, one loose) and a third,
  on its own dashboard view, whose Ends at is disabled from the start. The disabled sensor is
  a fixture of its own, not a test that enables one: Home Assistant reloads the entry 30
  seconds after a change to the registry entry of an entity that stays enabled (a disable
  reloads nothing), which would restart a timer in the middle of a later test. Users act with long-lived tokens
  written by `up`; a Russian test
  uses a browser context with `locale: "ru-RU"`; the user who is not an administrator is made
  over the websocket API in the `system-users` group. `localhost` is used because the service
  worker registers only there or on https. The container runs on the real clock and a restart
  takes tens of seconds, and the frontend picks the browser's language for a user who chose
  none. Cost if wrong: a failing run is slower to report, and a host whose Docker clock has
  drifted fails the tests that compare the browser's clock with the server's.
- **Unit and component tests run in vitest with happy-dom, with fake timers, one `fakeHass()`
  and one `mountCard()` helper, and `TZ=America/New_York`; Russian strings are read from
  `ru.json` at run time and never spelled in a test.** The tests are scenarios (a restart while
  the card is open, a renamed number, a clock that runs ahead, two timers on one device,
  Russian). Cost if wrong: happy-dom is not a browser, so the end-to-end tests carry what needs
  real layout and real events.
- **The pictures of the README are taken by a separate Playwright project, `npm --prefix card
  run screenshots`, with the browser's clock fixed 15 minutes into a 45 minute countdown, and
  they are committed, not made by every end-to-end run.** A countdown changes every second, so
  a run that wrote them would leave the tree dirty. The fixed clock fixes the time left and
  the fill; the end time on the pill is the server's real one, so a rerun changes the pictures
  and they are refreshed by hand, and looked at, when the card's look changes. No server data
  is faked for a picture. Cost if wrong: a picture may show an old look until someone refreshes
  it.
- **The gate from this phase on is the Python four (`pytest`, `ruff check`, `ruff format
  --check`, `mypy`), `npm --prefix card ci`, `build:check`, `typecheck`, `test` and `e2e`, and
  hassfest, run locally on the final tree.** GitHub Actions stay disabled and a green CI is
  never a merge gate, so the gate is what runs on the machine; and each check proves what the
  others cannot: `build:check` that the committed bundle is the sources', `tsc` the types, the
  unit tests the logic, and the end-to-end tests and hassfest what only a real Home Assistant
  shows. Cost if wrong: a longer gate, which needs Docker.
- **The smoke test checks the delivery of the card first, before any countdown.** The index
  page `/` must contain `import("/timerify_frontend/timerify-card.js?v=<16 hex digits of the
  SHA-256 of the bundle in the checkout>")`, a GET of that address must return the bytes of
  `custom_components/timerify/frontend/timerify-card.js`, and `timerify/timer` for the first
  timer must answer its entry and entities. The hash is computed in the script and not by the
  integration's own function, so a regression of that function is caught. Cost if wrong:
  the smoke test is a few seconds longer.

### Known issue

- **On Home Assistant 2026.10.x the card can be missing from the first page load that the
  frontend's service worker serves; it is documented, not worked around, and the registration
  above is kept.** On a first visit, after the site data was cleared and after a frontend
  update, a module added with `add_extra_js_url` can run before the application installs its
  scoped custom element registry, and then loses its definition: the dashboard shows "Custom
  element doesn't exist: timerify-card" until the page is loaded again
  ([home-assistant/frontend#53890](https://github.com/home-assistant/frontend/issues/53890),
  fixed by frontend PR #54444, in frontend 20261028.0 and later, which Home Assistant 2026.11 is
  expected to carry; the unchanged bundle was seen to keep its definition on a 2026.11 beta).
  Every card that an integration loads this way meets it, and Lovelace resources do not. No
  fix on 2026.10 uses only the public APIs. The README tells users to refresh once more, and
  `card/e2e/first-load.spec.ts` records the behaviour as an expected failure that Playwright
  reports when the problem goes away. That expected failure rests on a race the card's module
  wins against the application's bundle on the machine it was written on, so a machine on which
  the application wins can see it pass on 2026.10 as well. Raising the minimum Home Assistant
  to 2026.11 would remove the problem; it is not done at 1.0.0 (see "Release 1.0.0") and is
  issue #7.
  Cost if wrong: a user's first load in a fresh browser shows an error card until a refresh.

## Phase 6: runtime counter

The decisions of the runtime counter's phase (`docs/superpowers/plans/2026-11-01-phase-6-runtime-counter.md`),
in the form they have now. Section numbers (§) are those of the spec; "research §n" points into
`docs/research/2026-11-01-runtime-counter.md`.

### The counter and its file

- **The counter has a file of its own, `timerify.<entry_id>.runtime` (version 1,
  `{"seconds": float}`), and a pure class, `RuntimeCounter`. Nothing is added to the timer's
  file, its `Snapshot` or the core.** The counter records what the target did and decides
  nothing, so the timer stays the single source of truth for what runs, and `TimerStore`'s
  migration chain is untouched. A `RestoreSensor` is ruled out for the reason §5.7 gives for the
  timer: it is dumped every 15 minutes, so a crash would make a `total_increasing` value go
  down, and the recorder subtracts a dip of under 10 % from the sum (research §1). Cost if
  wrong: a second small file per timer.
- **Time that was not observed is not counted.** This covers Home Assistant being down, and the
  target being unavailable or unknown. At start, and when the target becomes available, a run
  opens at that moment if the target is on. §5.7 handles a restart "as if the change had just
  happened" and never reconstructs the downtime; a record holds only what was seen, so it never
  overcounts and it stays monotonic. Pending commands and the wish are promises, not runtime.
  Cost if wrong: an undercount bounded by the outage, which the README states.
- **The file is saved immediately (`async_save`) before every published value, and flushed on
  unload and when Home Assistant stops.** A stop unloads no entry, so without the second the
  seconds since the last tick would be lost at every stop. The stored value is then always at
  least the shown one, so no restart or crash can make the value go down, unless the file
  cannot be written (Home Assistant logs a failed write and does not raise it). Cost if wrong:
  one tiny write a minute while the target is on.
- **Switching the counter off and on again keeps the stored total.** No false reset in the
  statistics and no silent loss. Deleting the timer deletes the file. Cost if wrong: a user who
  wants a fresh start clears the statistics and deletes the timer.
- **There is no reset action.** The spec does not ask for one, and Home Assistant's statistics
  tools exist. Writing 0 later is safe for statistics. Cost if wrong: a user who wants to reset
  deletes and re-adds the timer.

### The sensor

- **The sensor publishes at second 59 of every UTC minute: the exact total in minutes, rounded
  to 2 decimals, shown with display precision 0.** The spec's point is attributing runtime to
  the right hour and day. A tick at second 59, even with its jitter of up to 0.5 s, lands before
  the minute's boundary, so a run across midnight splits within a second, with one write a
  minute, provided the file write that precedes the state write finishes promptly: the tick
  saves the file first, and the recorder dates the state by the write of the state.
  Whole minutes at second 0 would land after every boundary and could be off by up to
  2 minutes (research §3). Cost if wrong: the raw state carries decimals, which the display
  hides; a file write slower than about half a second at 23:59:59 (a stalled disk) moves the
  day's last minute to the next day, and nothing is lost.
- **The sensor has one tick listener for its whole life, and subscribes to the target's state on
  its own.** It does not go through the controller, its lock or its notifications, and it
  time-stamps a change with `event.time_fired`. The controller's handler can wait up to 30 s
  behind a service call (research §3), which would date runs late. A no-op tick is a
  comparison. Cost if wrong: a second state subscription per counted target.
- **The sensor never turns unavailable because its target does.** It is a total, not a reading,
  and cards and automations read its value. Cost if wrong: none known.
- **A counter switched off has its registry entry removed (not disabled).** Otherwise an
  `unavailable` ghost would come back at every start. A removed entry returns with the same
  entity id and customisations when the counter is switched on again, so history and statistics
  stay attached (research §4). The statistics are kept, because they are the user's. Cost if
  wrong: none known.

### The forms and the card

- **The "Count runtime" checkbox sits on the first form of a new timer, next to the entity and
  the mode (default off), and on the first form of its settings.** This is the owner's decision
  of 2026-11-01. §6.2 asks both for the order "entity → mode → duration → runtime → Workday" and
  for "three clicks for the common case". A separate step would make every timer take four
  clicks. Within one form, the order is a matter of layout. Cost if wrong: the counter is chosen
  before the duration.
- **Neither `timerify/timer` nor the card gets a `runtime` key in this phase.** §6.3's card
  shows actions and the countdown, not runtime, and a key that nobody reads is dead weight. This
  settles the earlier plan to add one "with the sensor". `mode` and `default_duration`, which
  the answer has carried since phase 5 and the card does not read, stay as they are for the
  same reason: the answer is a contract that the card mirrors key for key, and changing it for
  two fields alone, with no card feature to ask for it, gains nothing; the first card feature
  that changes the answer is the time to reconsider them. Cost if wrong: a later card feature
  adds the key in three places (the Python `TimerInfo`, `hass.ts` and `watchedEntities`), and
  two fields stay in the answer that nothing reads.

### Verification

- **The smoke test adds its first timer with the counter on, and after the first 2 minute run
  checks the sensor against the real container.** The sensor must reach at least 1.95 within 90
  seconds of the target turning off (it publishes at the end of the minute), and then be at most
  2.1, in minutes, with the state class `total_increasing`. The other timers of the smoke test
  and of the end-to-end tests are added as before and have no counter. The statistics
  themselves are proved by pytest with the recorder, not in the container. Cost if wrong: the
  container shows the unit, the class and the figure of one run, not a day's split.

## Release 1.0.0

The decisions of the 1.0.0 release (`docs/superpowers/plans/2026-11-01-release-1.0.0.md`), in
the form they have now. What is still open is a GitHub issue of klimofey/timerify, listed in
`docs/followups.md`; a number such as #10 below is one of those issues.

### The card and the websocket command

- **`timerify/timer` answers `timer_incomplete` when the number is a timer's and the timer
  cannot be told of, and the card says so in a neutral line.** There are two cases: the
  timer's target was stored by registry id and that entry is gone, or one of its two sensors is
  not in the entity registry. The registry keeps a timer's entities across restarts and
  reloads, so that happens only for a moment while a new timer is set up for the first time
  (below), and after a sensor was deleted from the entity registry, until the timer is set up
  again. `not_found` keeps its meaning, "this is no timer's number", and the check that the
  user may read the number still runs first, so the code tells a user who may not read an
  entity nothing. The card shows `card_timer_incomplete` ("The timer of {entity} cannot be
  shown: its target or one of its sensors is missing. Open the timer's page to see why.") in
  every state of the number.
  Why: the one wording for all of these, "is not the Run for number of a Timerify timer", was
  false for a number that is a timer's. A target stored as an entity id, which every flow
  writes, resolves whether or not the entity exists, so a timer whose target was deleted still
  answers `found` and drives nothing (1.1.0 adds a repair for it). Right after a timer is
  added the line can show for a moment, because the platforms are set up together, the number
  first; it clears on the next registry change, when the card asks again. Cost if wrong: that
  moment on a card that points at a brand-new timer, and no word on the card for a deleted
  target stored as an entity id.
- **`timerify/timer` sends `percent_settings`, the settings the card writes with a percent
  sign, and the card keeps no list of its own.** The keys are those of the target's domain row
  with `voice == "percent"`, taken from the row as `target_on` is and not from what this entity
  can do: a light that cannot dim still lists `brightness_pct`, and the card formats only keys
  that a command carries. Why: the card held a copy of three names, so a percentage setting
  added to `domains.py` would have been written raw until the copy changed; as for `target_on`,
  the browser keeps no copy of the domain table (§2). `voice == "percent"` now has two
  meanings, the setting that "at 40 percent" names in voice and every setting the card writes
  with a percent sign. They coincide while each row has at most one percentage setting; a row
  with a second one could not give it `voice == "percent"` (a row has at most one setting for
  each meaning), and it would need a field of its own. Cost if wrong: that field. A bundle that
  is newer than the server's answer, between a HACS update and the restart, has no key to read
  (#30).
- **`card/src/popup.ts` stays one element while it does not grow.** It is about 600 lines,
  about 200 of them the styles, and it has one job; splitting it now adds files that must
  agree on one state, and removes nothing. If it grows, the order is: move the styles out
  first, then the parser of the commands that the "Next command" sensor lists, and give the
  schedule and the commands their own elements last. Cost if wrong: a reader meets a long
  file, and the feature that makes it longer does the move first.

### The entry

- **A renamed Workday sensor is followed, and a removed one is not.** When the registry
  renames the sensor, the `workday_sensor` option is updated to the new entity id and the
  entry's update listener reloads the entry, so the controller asks about the new id and
  listens to it; a window that is open stays open across the reload. A removed sensor
  changes nothing: the option keeps the id, the windows already worked out stay, and no new
  one is worked out, with the one warning an unavailable sensor gets, until the user picks
  another sensor in **Configure**. Why: a rename is a fact about the same sensor, and the
  option is a copy of its id; after a removal there is nothing to follow, and which sensor
  to use instead is the user's choice. The subscription is Timerify's own, because
  `async_handle_source_entity_changes` also moves devices, and the entities follow the
  target's device, not the sensor's. Cost if wrong: as for the target, two renames inside
  one event-loop tick (A to B to A) miss the second one.
- **The device made for a target that had none is removed at set-up once the target has a
  device, and the entities stay.** The entities are moved to the target's device first,
  disabled ones and the interval switches included, and then the made device is removed, so
  the registry, which deletes the entities of a device it removes, deletes none of them; they
  would otherwise vanish from the state machine for a moment and come back. An entity that was
  disabled with the made device (`disabled_by` is the device) is enabled on the target's, as
  the registry does when a device is enabled, unless that device is disabled; one the user
  disabled stays disabled. The device is removed with `async_remove_device`, because
  `async_update_device(remove_config_entry_id=...)` is deprecated and an error from 2027.8. A
  target that is on no device is tracked in the registry, so one that gains its first device
  while Home Assistant runs (a user picks a device in the settings of a helper, its
  integration links it after Timerify set up, or it is registered later with a device) reloads
  the entry once, and the reload runs the same step. The one case with a second reload is a
  made device that the user had disabled: enabling its entities changes their `disabled_by`,
  and Home Assistant's own `EntityRegistryDisabledHandler` reloads the entry 30 seconds
  later (`RELOAD_AFTER_UPDATE_DELAY`). That reload is Home Assistant's, not Timerify's, and
  it is harmless: state survives a reload, and no call is added to the target. A rename is
  left to `_follow_target`, whose update of the `target` option reloads, because
  `async_schedule_reload` does not merge: two calls for one registry update would reload
  twice. Why: a target's integration can link its entity to a device after the timer's
  device was made, and the made one would stay behind, empty. Cost if wrong: a start-up in
  which the target's integration links its entity late costs the timer one more reload.
  Test: `test_entities_disabled_with_the_fallback_device_are_enabled_on_the_boilers`
  moves time past the 30 seconds and finds the entities enabled on the boiler's device and
  a countdown that was started meanwhile still running.

### Voice

- **A command's answer gives the wish it set, whatever the device shows; the answer to a
  question about the timer gives the wish while there is one, and otherwise says what the
  target shows.** "How long is left" is answered with the time left while a countdown runs,
  and "on without a timer" while the timer wants the target on; when nothing is wanted on, it
  says "off", or "unavailable" when the target is unavailable, unknown or has no state (R10):
  "Boiler is unavailable and has no timer." In the slots of the answer `state` is
  `unavailable` then, for the `timerify__time_left` tool and for Stop alike. Stop's spoken
  answer stays "is off", because it gives the wish it set: the target is turned off when it
  is back. Why: a wish is on or off, and "off" said of a target that does not answer was a
  claim about the device that nothing known supports. Cost if wrong: for an unavailable target
  the words of Stop ("off") and of the question ("unavailable") differ, and the tool tells
  the agent "unavailable" for Stop.

### Forms and services

- **A default duration kept through loose mode is the prefill for strict.** Switching a timer
  from strict to loose leaves `default_duration` in the options, and switching back offers it
  in the duration form; a timer made in loose mode has none yet, and the form offers the
  usual 30 minutes. Why: loose mode ignores the value (`timerify/timer` says `null` for it),
  so keeping it harms nothing, and a user who tries loose mode and goes back does not type
  again what was chosen. Cost if wrong: a number in the options that nothing reads. Test:
  `test_options_offer_the_default_duration_kept_through_loose_mode`.
- **`services.yaml` repeats the limits.** The ranges of `add_time` (plus and minus 1440), of
  the minutes of `run` and `add_command` (1 to 1440) and of the delay of `add_command` (1 to
  10080) are written there as well as in `const.MAX_MINUTES` and `const.MAX_DELAY_MINUTES`,
  and `test_services_are_described_for_the_ui` in `tests/test_services.py` fails when they
  drift. Why: Home Assistant reads `services.yaml` as data and cannot name a constant in it,
  and generating the file or patching the descriptions at run time is more machinery than
  five numbers need. Cost if wrong: a limit changes in two places, and the test says which.
- **A deleted interval is still worked out until the timer reloads.** Deleting an interval
  reloads the timer at once, which lets it go; only a reload that waits behind another set-up
  leaves the loaded timer with it, and for that time a window of it can be worked out and
  opened. The commands that name an interval treat it as gone already
  (`async_set_schedule_enabled`), and the reload drops its window
  (`TimerCore.set_windows`, `configured`). Why: the window is short,
  and closing it would need a second judgement of which intervals exist beside the entry.
  Cost if wrong: for as long as a reload waits, a deleted interval can still open a window.

### The release

- **No repairs issue for interval switches exposed under 0.3.0.** Version 0.3.0 made the
  switch of an interval an ordinary entity, and Home Assistant exposed it to Assist the first
  time it saw it; from 0.4.0 it is an entity of the configuration category, which is not
  exposed by default, but the decision stored for the entity stays. 0.3.0 was never published,
  so no house has switches exposed that way, and a repair that names and unexposes them would
  serve nobody. The README does not tell how to take them away. Cost if wrong: a house that
  ran 0.3.0 exposes its interval switches to voice and to an LLM agent until the user
  unexposes them under **Settings > Voice assistants > Expose**.
- **The minimum Home Assistant stays 2026.10.4 at 1.0.0; raising it to 2026.11 is #7.**
  2026.11 carries the frontend that removes the first-load error ("Custom element doesn't
  exist"), but 2026.11.0 was in beta when 1.0.0 was prepared (2026-11-01) and was due on
  2026-11-04, so a minimum of it would have kept Timerify from every house that was still on
  2026.10, and the error is cured by a refresh, which the README says. Raising it moves
  `hacs.json`, the `pytest-homeassistant-custom-component` pin in `pyproject.toml` and the
  image in `scripts/harness/compose.yaml` together; then `card/e2e/first-load.spec.ts` passes
  unexpectedly, and its `test.fail` and the extra reload after `primeServiceWorker` in
  `card/e2e/fixtures.ts` go. Cost if wrong: a user's first load in a fresh browser shows an
  error card until a refresh (see "Known issue" in phase 5).

## Release 1.1.0

The decisions of the 1.1.0 release (`docs/superpowers/specs/2026-11-01-release-1.1.0-design.md`),
in the form they have now. What is still open is a GitHub issue of klimofey/timerify, listed
in `docs/followups.md`.

### Engine and reliability

- **Each piece of work has one allowance of automatic re-sends for its whole life.** A piece
  of work is the pending wish to turn the target on or off, or the owed settings. The
  allowance covers the first delivery, then `automatic_resends` re-sends prompted by reports
  of any kind: a repeat of the state, a change of it, a return from unavailable, or the
  first report after a start. Then comes one `GaveUp`, and after that nothing. A report that
  finds the work never delivered by this core makes the first delivery, and it costs no
  re-send: that is a wish restored from the file, or one made while the target was away.
  Only new work renews the allowance: a new pending wish (any command, or an item of the
  fold that wants a state, such as the end of a countdown or the start of a window), the one
  correction of a late report of our own call, new owed settings, and a command that sends
  the owed settings. A new wish to turn on also renews the allowance of the settings that
  are owed, because it asks for them again: settings given up on are delivered when the
  target returns, after a command made while it was away. Reports renew nothing. The log
  says so: "did not turn off after 4 attempts; Timerify will not send it again until it is
  asked again".
  Why: #11. A device that answers each refused call with `unknown` and then its old state
  looked like a target that went away and came back, and every such cycle reset the count, so
  the device was commanded as often as it answered. A device that drops off Wi-Fi and
  returns logged one give-up for each reconnect.
  Cost if wrong: a device that refused four times, and then works again after a reconnect,
  is not sent the command until it is asked again. A media player whose turn-on failed is
  turned on only when asked again.
- **Until start-up has taken stock, nothing reaches the target, and a change made
  meanwhile first folds what fell due before it.** Before `_handle_started` has merged the
  fresh windows and observed the target, nothing is sent and no report of the target is
  answered. Two gates keep it so. The core treats a target it has never observed
  (`last_actual is None`) as away, as `"unavailable"`: `_want` records a wish as unsent and
  sends nothing, and `_deliver_settings` holds the owed settings back, also when a wish
  restored from the file counts as in flight. The first `observe` delivers the wish and
  the settings, free of the allowance, once. A report of the target before start-up is not
  observed (`_handle_state_change`): `_handle_started` reads the state itself, under the
  lock, and only then sets `_started`. A report would fold the stored items without the
  fresh windows, and could switch the target twice. No alarm needs a gate: a restored timer
  arms nothing at set-up, so a stored end, command or window that has long passed is never
  folded by a tick without the windows of now. The first alarm comes from start-up, or
  from a change made meanwhile once it has caught up (below). Such an alarm folds what
  falls due at its own time, as with Home Assistant running, and sends nothing either.
  Task 3 kept `_arm` from arming before start-up; after the catch-up that gate kept
  nothing out, so it is gone.
  A change made meanwhile takes effect at its own moment, as with Home Assistant running.
  That is every command: the "Run for" number, `add_time`, `run`, `add_command`,
  `turn_off_in`, the cancels, and the switch of an interval or of the whole schedule. It
  first does what start-up does, without the target
  (`_async_catch_up_while_starting_locked`): the windows are worked out now and merged,
  and what fell due while Home Assistant was down is folded in the order it fell due, in
  the core only. That is the stored end (with the S4 suppression of a started window), the
  pending commands, and the windows that opened or closed. Then the change is applied, and
  it wins. Its outcome is saved, so it survives a restart before start-up has finished.
  Several changes apply in the order they were given, each after what fell due before it.
  An interval's switch is such a change too: its flag (`disabled_intervals`) and the
  window it removes or brings are applied as with Home Assistant running, after the
  catch-up. Start-up then folds what fell due since the last change and switches the
  target once. Changes after start-up are unchanged.
  Why: #12 and "the user's last word wins". Before this, a command made while starting was
  recorded on the timer as it was stored, and start-up folded the stored items after it: a
  pending "off" that came due while Home Assistant was down turned the target off after
  "Run for 30", and a countdown set by hand that ended while it was down left its window
  unsuppressed for "Add time". §5.7's single catch-up holds: start-up switches the target
  at most once. Folding with only the stored windows is not enough: the file holds the
  current or next window of each interval as it was when Home Assistant stopped, so after
  a long downtime, or for an interval added while starting, the window that is open now is
  not in it, and "Run for 0" would come before it and be undone by it at start-up. Holding
  the changes back and replaying them at start-up would need each command stored as data
  next to the timer it applies to, to survive a restart before start-up has finished; the
  windows of now are what start-up would work out at that moment, so working them out at
  the change gives the same outcome without a second form of the file.
  Cost if wrong: the catch-up asks the Workday sensor, whose integration may not be up yet
  while Home Assistant starts. Then the interval keeps its stored window, as at any time
  the sensor does not answer, and the warning is logged once. If that window is not the one
  that is open now, start-up merges the right one after the change, and it may start then
  (S1). A change that waits for its turn, behind another change
  or a slow Workday answer, catches up to the moment it
  runs, not the moment it was given, so it also wins over what fell due in between (#42).
  A report of the target before start-up is answered a few seconds later, at start-up.
- **"Add time" counts a countdown whose end has passed as no countdown.** `add` judges the
  end as `wanted_running` does: an end at or before now is over, whether or not it was
  folded. The timer is then idle, and the rule for an idle timer applies (R7 and the
  documented "adding to a timer that is not running starts it"): a positive delta runs the
  target for the added time, counted from now, and a negative one changes nothing. A
  change made while starting catches up first (see the ruling above), so `add` never meets
  a passed end there. It meets one only in a race: `add` was given while the countdown
  still ran, and waited for the lock behind a slow call until after the end. The lock wakes
  its waiters in the order they came, so the alarm of the end, queued later, runs after
  `add`: nothing that the end would fold is missed, and no S4 suppression either. The
  difference is the time. The added minutes count from when the command ran (late by the
  wait for the lock), not from the old end, and the countdown's beginning
  (`started_at`) starts again. #42 tracks carrying out a command at the moment it was
  given, which settles this race.
  Why: an end that has passed is over for every other judgement (`wanted_running`,
  `run_open`, a pending command that falls due).
  Cost if wrong: a countdown that ends exactly now and gets a negative delta is left for
  the next fold instead of being stopped at once. In the race above, the target runs
  longer, by the wait for the lock, than with the command dated when it was given, and the
  card's progress starts again.
- **Every fold says what came due while the target is away, and a fold says it only about
  a target that has reported "unavailable".** `_execute_fold(before, now, effects)` logs it
  (`_log_due_while_unavailable`) and then carries out the effects. All folds pass through
  it: a tick (`_fold_due`: the alarm, the refresh of the windows, the switching off of an
  interval, and the catch-up of a change made while starting), the first observation of the
  target at start-up (`_handle_started`) and each report of it (`_handle_state_change`),
  with the `now` the fold observed at. Before, only the tick logged, so a countdown or a
  command that came due while Home Assistant was down, and a command that fell due as the
  target dropped off, went unsaid. The three texts are unchanged.
  A fold before start-up says nothing. The catch-up of a change made while starting is
  such a fold, and so is an alarm that fires before start-up: the target has not been
  seen (`last_actual is None`), so it is not known to be unavailable, and "while it is
  unavailable" would be a guess. Start-up logs what it folds itself, once: whatever fell
  due since the last change made while starting, judged by the state it observes. What an
  earlier fold took is not logged again, since it is no longer there to be found due.
  Why: #13, and a log that stays true. Nothing else shows that a switch waits for the
  target to come back (R10). A fold before start-up cannot tell the user that the target is
  away. What it folds is also overridden by the change that comes after it, so "the timer
  ended; it is turned off when it is back" could be false by the time start-up knows the
  target is unavailable: "Run for 30" came after the end, and the target is turned on.
  Cost if wrong: a countdown, a command or a window start that falls due after the first
  change made while starting, but before start-up, is folded by its alarm in the core only. If the target
  then turns out to be unavailable, the log does not mention it, though the target is
  switched all the same when it is back. Home Assistant starts within minutes, and a
  change made meanwhile is rare.
- **The settings are filtered when they are sent, whoever owes them.** `_execute` judges the
  settings of every `TurnOn` and `ApplySettings` against what the target takes at that
  moment (`_settings_the_target_takes`, through `validate_settings`), each setting alone, as
  the form offers them, and sends the ones it takes. That holds for settings of every
  origin: a `run`, a pending command, a window, and settings carried over from the file. A
  window carries the settings of its interval as saved, and nothing filters them when it is
  worked out. `async_run` and `async_add_command` still refuse, at once, the settings that
  the target does not take when the request is made.
  A setting that is left out is said once, as a warning that names the target and the
  setting: "climate.ac cannot take the setting hvac_mode=cool now; it is left out". The
  controller remembers the pair of name and value while it stays left out. A later call that
  carries the name and finds it taken forgets every pair of that name, so a setting that
  was left out, then taken with another value, then left out again is said again. The memory
  is in the controller and not stored, so it lasts for one load of the timer: a restart or a
  reload says a setting that is still missing once more. The warning names no interval or
  command, since any origin may owe the setting.
  Settings that were all left out count as delivered. The turn-on goes out plain, or an
  `ApplySettings` with nothing left makes no call, and the core is told `settings_applied`
  as for any delivery: it clears what is owed and touches no allowance. A setting that
  nobody can send must not be owed, sent again and given up on.
  Why: #18. Only a window was filtered, and when it was worked out, not when it was sent.
  A pending command whose mode was renamed failed its call every time. A window worked out
  while the target showed no modes lost the settings until the next window refresh.
  Sending is the one place all settings pass through, and the moment at which what the
  target takes is what matters.
  Cost if wrong: a setting that comes and goes between two calls is warned about again. An
  integration that reports the device as available before it lists its modes gets its
  turn-on without the setting, which is not sent again later: it counts as delivered.
  Start-up and a return from unavailable do not lose settings this way. The core sends
  nothing to a target that is away or has not been seen (`observe`, `_want`,
  `_deliver_settings`), and Home Assistant keeps the capability attributes on an
  unavailable state and on one restored from the registry. So do not keep a setting owed
  for the sake of a target that cannot take it: it would be sent again until the allowance
  gives up.
  Tests: `test_a_due_command_whose_mode_was_renamed_turns_on_without_it`,
  `test_a_running_ac_that_lost_the_only_setting_of_a_command_gets_no_call`,
  `test_a_setting_left_out_is_said_once_when_the_turn_on_is_sent_again`,
  `test_a_mode_left_out_is_said_again_after_another_mode_is_taken`,
  `test_setting_the_ac_no_longer_takes_is_left_out_and_said_once`,
  `test_setting_that_comes_back_and_goes_again_is_said_again`,
  `test_a_climate_without_capabilities_keeps_the_settings_of_its_window`.
- **A timer whose target was deleted stays loaded and switches nothing, with a repair that
  deletes it.** The repair is "The device of timer X was deleted" (`target_deleted_<entry>`,
  severity error, fixable). Its fix has one step, which shows what is deleted; submitting it
  removes the config entry, and so the entities, the intervals and the stored files. A timer
  that was already deleted on its integration page, with the repair still open, aborts with
  `timer_gone`. A step that is shown again or submitted once its issue is gone aborts with
  `issue_gone`, which says only that the problem is no longer open: the target may be
  back, or the timer was unloaded (disabled, or reloaded and not yet checked again). So a
  window of the repair that was left open does not delete a timer that works again. The
  decisions:
  - The timer keeps its entities and accepts commands, as for an unavailable target (R10).
    The controller has no gate of its own. A deleted target has no state, so the core takes
    it for a target that is away: a command, the end of a countdown and the start of a
    window are carried in the core and sent when the target is back. Before start-up the
    target is unseen and the gate of the ruling on start-up holds. A report of the target
    that waited for the lock while it was deleted is read as the target being gone, not as
    the state it carries (`_handle_state_change`), or its "off" would make the core send the
    turn-on that failed to an entity that is not there. The log says it (a warning when the
    target is deleted, an info line when it is back), and so does the repair.
  - It is checked at start-up (`_handle_started`), not at the top of set-up. A target that is
    not in the registry has no state until its integration has set up, and an entity of YAML
    without a unique id is never in the registry. The target is there when it has a registry
    entry or a state (`_target_exists`). It is deleted live when the registry removes it
    (`source_entity_removed` of `async_handle_source_entity_changes`). An entity of YAML
    that loses its state while Home Assistant runs has no registry event to tell it: it is
    an unavailable target until the next start, which finds it gone.
  - A state ends it: the report of a target that exists, judged by what exists when the
    report is read and not by the report alone, since a report may have waited for the lock
    while the target was deleted. A registry entry created for the target ends it too, by
    reloading the timer (`_follow_target_restored`), which also puts its entities back on
    the target's device. Only the same entity id counts. A device added again under another
    entity id leaves the repair standing: the user deletes the timer and adds it again.
  - The issue lives with the loaded timer: it is cleared at unload and raised again at
    set-up, so a reload never leaves a stale one and a restart finds it again. It is not
    persistent. Removing the entry clears it as well. `_follow_target_gaining_a_device` now
    follows registry updates only, as a created entry is the restored handler's, and two
    handlers would reload the timer twice.
  - The timer's entities stay where they are when the entity is deleted: the controller is
    told, and the helper's default of unlinking them is not wanted. Home Assistant unlinks
    them if the device itself is removed, as it does for the entities of any other
    integration on it. At the next start, the entities of a timer whose target has no
    registry entry are put on the device made for it, as for any target that is on none
    (`timer_device`); the reload that a created entry brings moves them back
    (`remove_fallback_device`). The test of 1.0.0 that expected the entities to be unlinked
    when only the entity is deleted is changed to match.
  - A registry entry created for a target that never had one, say a template entity that is
    given a unique id later, also reloads the timer once. `_follow_target_restored` does not
    tell the two apart.
  Why: #10. Before this the timer loaded, kept its entities and drove nothing, and nothing
  told the user. The repair names the timer and says what it does meanwhile; the user can
  restore the device or delete the timer from the same place.
  Cost if wrong: a user who never opens Repairs sees a timer counting down on nothing, and a
  command given to it waits for a device that may never be back. A device re-added under a
  new entity id keeps the repair until the user deletes the timer.
  Tests: `test_deleting_the_target_raises_a_repair_that_names_the_timer`,
  `test_a_countdown_ended_while_the_target_was_deleted_turns_it_off_when_back`,
  `test_a_report_queued_before_the_deletion_is_read_as_a_boiler_that_is_gone`,
  `test_deleting_the_timer_on_the_integration_page_clears_the_repair`,
  `test_a_delete_dialog_left_open_after_the_boiler_is_back_deletes_nothing`.
- **An unreadable stored timer is reset only by the user, through a repair, and the reset
  drops the whole file.** A stored timer that cannot be used raises the repair "The stored
  state of the timer X cannot be read" (`stored_timer_invalid_<entry>`, severity error,
  fixable), and the set-up fails with the same reason (`StoredTimerInvalid`, a
  `ConfigEntryError`), so the entry stays in `SETUP_ERROR`. The reason is the English text
  of the error, also in the Russian message and the repair: it is for the bug report of a
  defect, not for the user. The fix, "Reset the stored timer", has one step, which shows
  the reason and what is kept. Submitting it deletes the file and reloads the entry. It
  shares its steps with the fix of a deleted target. A timer deleted meanwhile aborts with
  `timer_gone`. A step shown again or submitted once its issue is gone aborts with
  `issue_gone`, so a window of the repair left open after the file was put right, or after
  another window reset it, does not reset a timer that works. A reload that fails after the
  reset (the timer cannot be set up for another reason, say an interval by working days
  and no Workday sensor) aborts with `reload_failed`, which says that the file is reset
  and that the timer's page has the reason, instead of ending as if the timer were fine.
  The decisions:
  - A missing field is as unreadable as a file that contradicts itself, and so is a field of
    a type that no timer writes. The reason of a missing field is "the field X is missing",
    and "the field X of a pending command is missing" (or "of a schedule window") for a
    field inside one. For a wrong type it is the text Python gives. Neither is a bare
    `KeyError` or `TypeError` in the log.
  - A file that is not valid JSON is not this repair. Home Assistant's `Store` renames it
    (`.corrupt.<time>`), raises its own `storage_corruption` repair and returns no data, so
    the timer starts idle and every interval is on, without asking.
  - The entry, its intervals (subentries) and the runtime file are kept. The countdown, the
    pending commands and the flags of the switched-off intervals are lost, because nothing
    in a file that contradicts itself can be trusted. Every interval is on again.
  - Nothing resets the file but the user. The timer does not drop a file it cannot read on
    its own, since the countdown and the commands in it may be worth keeping to someone who
    can repair it by hand.
  - The issue is raised at each failed set-up and is not persistent. A good load clears it,
    as does removing the entry. A file put right by hand and a reload end the repair, and a
    step shown again then aborts with `issue_gone`. A timer disabled while it failed to set
    up keeps the repair until it is enabled, since Home Assistant runs no unload of ours
    for an entry that never loaded; the file is still unreadable, so the text stays true.
  - `async_create_fix_flow` refuses data without a known `kind` with one `ValueError`,
    whether the `kind` is missing or unknown.
  Why: #17. Before this the user was told to remove the timer and add it again, which also
  loses the intervals and the runtime total that were fine.
  Cost if wrong: a user loses the pending commands of a file that was only partly wrong.
  Tests: `test_a_stored_timer_that_cannot_be_read_raises_a_repair`,
  `test_a_stored_timer_missing_a_field_raises_the_same_repair`,
  `test_a_stored_field_of_the_wrong_type_raises_the_same_repair`,
  `test_a_field_missing_inside_a_command_or_window_says_whose_it_is`,
  `test_resetting_the_stored_timer_keeps_the_entry_and_its_intervals`,
  `test_a_stored_timer_that_is_put_right_clears_the_repair`,
  `test_deleting_a_timer_whose_stored_timer_cannot_be_read_clears_the_repair`,
  `test_the_reset_of_a_timer_deleted_meanwhile_does_nothing`,
  `test_a_reset_shown_again_after_the_file_was_put_right_does_nothing`,
  `test_a_reset_dialog_left_open_after_the_file_was_put_right_resets_nothing`,
  `test_a_delete_dialog_left_open_after_the_boiler_is_back_deletes_nothing`,
  `test_a_reset_after_which_the_timer_does_not_load_does_not_say_it_worked`,
  `test_an_issue_with_no_known_kind_has_no_fix`.
- **Windows keep the old time zone after "Reload core configuration" until Home Assistant
  signals it (#14, upstream).** Home Assistant 2026.10.4, 2026.11.0b1 and 2026.11.0b2 fire
  nothing when that reload changes the zone: `_async_handle_reload_config` calls
  `async_process_ha_core_config`, which sets the zone through `Config.async_set_time_zone`,
  and that only calls `dt_util.set_default_time_zone`. `EVENT_CORE_CONFIG_UPDATE`, which
  Timerify follows, comes only from `Config.async_update`, the settings page. Following
  `EVENT_CALL_SERVICE` for `homeassistant.reload_core_config` was rejected: it fires before
  the handler runs, so the zone has not changed yet, and waiting after it would be a guess.
  The issue is labelled `upstream`; reporting it to Home Assistant is the owner's call.
  Cost if wrong: after a YAML change of the zone and that reload, windows run in the old
  zone until a window ends, the Workday sensor reports or the timer reloads.

### Forms and entities

- **The maximum of Run for bounds the slider, not the timer.** The option
  (`CONF_RUN_FOR_MAX`, whole minutes, a day when an entry has none) sets the `max` of the
  "Run for" number. Home Assistant's `number.set_value` refuses more, so the slider, the
  more-info dialog and the card's presets (which use `set_value`) follow it. `run`,
  `add_time`, pending commands, voice, the LLM tools and windows keep the 1440-minute
  limit. A countdown they start runs in full, and the number shows its minutes above
  `max`. Lowering the maximum leaves a running countdown as it is.
  The default duration may not be above the maximum. A schema flow has only `base` errors
  (`schema_config_entry_flow.py:285`), so the error is the base error of the duration
  form, whose only field it is. The selector stays 1 to 1440, so the error is translated,
  not a selector's text. The duration form of a new timer starts at the smaller of 30
  minutes and the maximum, so that taking every default still adds the timer.
  A loose timer is not checked: it has no duration form, and a stored default duration is
  used only in strict mode. Switching to strict shows the duration form, which checks it.
  Why: #35. The owner rarely runs a device for more than two hours. Refusing a window or a
  spoken "for 3 hours" would change what the base spec defines.
  Cost if wrong: a card preset longer than the maximum is refused with Home Assistant's own
  message.
  Tests: `test_the_first_form_asks_for_the_maximum_of_run_for`,
  `test_a_default_duration_above_the_maximum_is_refused`,
  `test_the_duration_form_starts_at_a_maximum_below_thirty`,
  `test_a_maximum_in_part_minutes_is_refused`,
  `test_settings_change_the_maximum_of_run_for`,
  `test_lowering_the_maximum_below_the_default_duration_asks_to_lower_it`,
  `test_the_slider_ends_at_the_maximum_of_the_timer`,
  `test_setting_run_for_above_the_maximum_is_refused`,
  `test_actions_and_commands_run_past_the_maximum`,
  `test_lowering_the_maximum_keeps_a_longer_countdown_running`,
  `test_the_settings_reopen_at_the_maximum_the_timer_has`,
  `test_a_loose_timer_is_not_checked_until_it_turns_strict`,
  `test_a_window_longer_than_the_maximum_runs_in_full`,
  `test_a_run_by_voice_goes_past_the_maximum_of_run_for`.
- **The Turn off button is the stop command, and only an option adds it.** Pressing is
  `async_set_minutes(0)`, the stop that voice and Run for 0 use. So it ends a countdown,
  turns off a loose device that runs without one, holds a started window until its next
  occurrence (S4), and sends nothing to a device that is off.
  The button has no entity category, because it switches the device. `button` is not
  exposed to Assist by default, so it adds no phrase that competes with "turn off the
  boiler". Its state is the time of the last press, which Home Assistant keeps, so the
  controller's updates write nothing.
  The option `off_button` is a box after the maximum of Run for on both first forms.
  Absent or false: no button. Unticking removes the registry entry, as for the Runtime
  sensor, and both use `remove_timer_entity`. The card option of #37 is part E.
  Setting Run for to 0 by hand turns off a loose device that runs without a countdown,
  whether it was switched on by hand or by `run` without a duration. Nothing pinned it
  before.
  Why: #37.
  Cost if wrong: an automation that presses the button while a schedule window is open
  stops the device until the next window.
  Tests: `test_a_timer_has_no_turn_off_button_unless_asked`,
  `test_ticking_the_box_puts_a_turn_off_button_on_the_device`,
  `test_pressing_turn_off_stops_the_countdown_and_the_boiler`,
  `test_pressing_turn_off_stops_a_loose_boiler_without_a_countdown`,
  `test_pressing_turn_off_on_a_boiler_that_is_off_sends_nothing`,
  `test_unticking_the_box_removes_the_button`,
  `test_the_turn_off_box_is_on_both_first_forms`,
  `test_run_for_zero_turns_off_a_loose_boiler_without_a_countdown`,
  `test_the_turn_off_button_has_the_unique_id_of_its_key`,
  `test_the_turn_off_button_is_not_exposed_by_default`.
- **A generated interval title is marked by the title itself, kept in the subentry data.**
  A new interval is stored with `generated_title` (`CONF_GENERATED_TITLE`) set to the
  title Timerify gave it, in the language of the house at that time. The mark holds while
  the subentry's title still equals it. An edit then makes the title again in the
  language of the house now, and stores the new title under the key. Any other edit keeps
  the title and stores no key. A rename on the integration page changes only the title
  (`config_entries/subentries/update`), so it ends the mark with no hook of ours, which a
  flag could not tell.
  An interval with no mark falls back to the rule of release 1.0.0: if its title equals
  the title its data makes now, in the language of the house now, the edit makes the title
  again and stores the mark. That covers an interval added or edited by 1.0.0 after a
  downgrade, whose entry is already at minor version 2 and is not migrated again.
  The migration to minor version 2 (`async_migrate_entry`) marks a subentry whose title
  equals the title made from its data in any shipped language
  (`TRANSLATION_LANGUAGES`, pinned to the files of `translations/`), whatever language
  the house speaks now. A user title that happens to equal a generated one is taken as
  generated, and the next edit renames it. A subentry that no title can be made of (a
  missing key, days that are no kind of days, a weekday that is not one) is checked for
  explicitly (`stored_interval_title`) and left unmarked, so that one odd interval does
  not fail the migration. Whether the timer then loads is for the data of that interval,
  as without a migration: one that lacks a time keeps the timer from setting up, one with
  an unknown day or kind of days loads. The voice settings entry only moves to minor
  version 2. `async_title_labels(hass, language)` takes the language, so that the
  migration can compare a title in every shipped language, not only the house's.
  Minor version 2 keeps a downgrade to 1.0.0 loading: that release has no
  `async_migrate_entry`, so Home Assistant accepts the entry (checked by loading an entry
  of minor version 2 with the code of the `v1.0.0` tag). It ignores the key, and its edit
  stores none. The title of an interval it edited is found again by the fallback above
  when 1.1.0 comes back, as long as the house language is the one the title was made in.
  A house language without a translation of Timerify gets English, as Home Assistant
  falls back, for the titles that are made and for the labels that are compared.
  Why: #15. The title was made in the language of the house when the interval was added
  and compared in the language of the house at the edit, so a house that changed language
  took every generated title for a chosen one, and the title never followed.
  Cost if wrong: a title typed to look generated is renamed by an edit. A title that 1.0.0
  made in another language than the house speaks when 1.1.0 comes back is taken as the
  user's, since only the migration of a first upgrade tries every language.
  Tests: `test_a_new_interval_is_marked_as_titled_by_timerify`,
  `test_an_edit_after_the_language_changed_renames_the_interval`,
  `test_a_renamed_interval_keeps_its_name_after_the_language_changed`,
  `test_a_house_language_without_translations_names_in_english`,
  `test_editing_keeps_a_title_the_user_chose`,
  `test_a_title_generated_in_english_is_marked`,
  `test_a_title_generated_in_russian_is_marked_in_an_english_house`,
  `test_a_title_of_working_days_is_marked`,
  `test_a_title_the_user_chose_is_not_marked`,
  `test_an_interval_no_title_can_be_made_of_is_left_unmarked`,
  `test_an_interval_without_the_mark_is_named_again_by_an_edit`,
  `test_a_title_the_user_chose_is_kept_in_an_entry_of_the_current_version`,
  `test_the_voice_settings_entry_is_migrated_too`,
  `test_the_translation_languages_are_the_files`.
- **An interval keeps a setting the form no longer offers, and a warning stands while the
  device does not take it.** An edit saves the settings of the form, which have the user's
  values, then the stored settings whose name the form does not offer
  (`supported_settings`), untouched. A name the form shows is the user's, also when it is
  emptied. The section opens only when a shown setting is one the form offers, so an
  interval whose settings are all hidden shows it closed.
  The warning is judged as the run-time filter judges (`settings_not_taken`, through
  `validate_settings`, which `_settings_the_target_takes` goes by too), so it stands
  exactly while the window would leave the setting out. That includes a value that is no
  longer accepted, which the form shows and the user can change. The names come in the
  order of the form (the row of the domain), whatever order they are stored in. A name the
  form has no label for, which only a hand edit of the stored interval leaves, is shown as
  the name it has.
  The form shows a setting it offers with the value the interval holds, also when the
  device no longer lists that value (`_setting_selector`). A list gets the held value
  added to the values the device lists, a number field widens its range to take it, and
  nothing else widens. Without that, the selector refuses the held value in Home
  Assistant's own words, before `validate_settings` is reached, and a frontend that drops
  a value its list does not hold would make the edit lose the setting without a word.
  With it, saving the form unchanged is refused by `validate_settings` with the
  translated base error `settings_not_supported`, and nothing is saved. A value the
  device takes saves, and an emptied field drops the setting. A held value of another
  kind than its field takes (a number where a mode belongs, which only a hand edit
  leaves) widens nothing. A refused form is shown again with the value typed, so a value
  just refused stays in its field.
  There is one warning per interval, naming all its settings by the labels of the form in
  the language of the house. Its title carries the interval, so that two warnings of a
  timer differ in the Repairs list, and both are quoted in the texts, because a generated
  title has a comma in it. It is a Repairs issue with severity warning and not fixable,
  so it has no fix flow (spec). It is persistent, and its data holds the names it was
  raised with. It is changed only when the names or the interval change, and it is judged after each report
  of the target and after the start-up fold, so that reading the texts never delays what
  the timer owes the target. An interval deleted but not yet reloaded gets no warning.
  Deleting the interval drops a setting the form no longer shows.
  While the target is deleted there is none, whose repair speaks for it.
  While the target is unavailable or unknown, what the device does not take stays as it
  was. An integration may drop its modes and features with the connection, which would
  make every setting "not taken" for the length of an outage, and nothing is sent then.
  The warning still follows the interval itself, which the user edits meanwhile: it is
  raised again with the title the interval has now, and names only the settings the
  interval still holds (one dropped from the interval leaves it, and an interval with
  none left loses it). The target is judged again when it reports a real state. A
  warning that Home Assistant loaded from its file after a restart is shown from the
  first moment, with the names it last had, and stays so until the target reports.
  A warning is updated in place, which keeps the Ignore of the user, when its names are
  the same or fewer. When the interval gains a name that the warning does not list, the
  warning is deleted and raised again, so that an Ignore of the earlier settings does not
  hide the new one. The names of an earlier load, also one before a restart, come from the
  data of its issue. An issue that keeps none, which this code never raises, counts every
  name as new: it is raised again and its Ignore is not kept.
  The warning outlives the unload, unlike the repair of a deleted target. That repair is
  cleared on unload and raised again at start-up: it asks the user to delete the timer,
  and an Ignore of it has nothing to keep. The user may knowingly accept this warning
  and choose Ignore, and every change of an interval reloads the timer. Home Assistant
  keeps `dismissed_version` when an issue is created again under its id
  (`IssueRegistry.async_get_or_create` replaces the other fields), and forgets it when
  the issue is deleted, so deleting on unload would show the warning again after every
  edit. A warning is deleted when its check finds nothing missing, when the load finds
  its interval gone (`_reconcile_settings_warnings`, by the id prefix in the issue
  registry), when the entry is removed (`async_remove_entry`), and when the entry is
  disabled, since it is not loaded again. The load remembers the warnings of the earlier
  one, so that its first judgement raises them again, with the title the interval has
  now, or takes them away. A warning that went away and comes back is new, not ignored.
  A timer that fails to set up (an unreadable stored file, a Workday sensor missing, or
  any other raise) takes its warnings away at once (`async_setup_entry`): it turns
  nothing on, and a disabled timer in that state would keep them, because Home Assistant
  runs no unload callback for it. If it loads again later, the first judgement raises
  them again and an earlier Ignore is lost.
  The warning also outlives a restart of Home Assistant, so it is raised with
  `is_persistent=True`. Home Assistant saves an issue that is not persistent with its
  Ignore only, and loads it back inactive, with no data and no placeholders. The names
  would be lost, and a setting lost while Home Assistant was down would keep the Ignore
  over a warning that grew, against the docs (the Ignore does not hide a new setting).
  A persistent issue is saved whole and loaded back active. After a restart a warning
  that grew is raised again as new, one that is the same or smaller is updated in place
  and keeps its Ignore, and with the target offline at start-up it is shown from the
  first moment with its last names and its Ignore, until the target reports (the freeze
  above). Whatever takes a warning away takes a persistent one away alike, since
  `IssueRegistry.async_delete` does not tell them apart. The names stay in the data of
  the issue, not in the store of the timer: that would change the format of the store
  for what the issue registry keeps through public API.
  The labels and the title in a warning are in the language of the house as of the last
  load of the timer. A change of the house language shows in them after the next reload or
  restart of Home Assistant, the way a generated interval title follows the language only
  on an edit (#15 above). The warning is not raised again for it: its names, the only
  thing the check compares, have not changed.
  Why: #16. An edit dropped the settings the form did not offer, silently, and the window
  left them out with only a line in the log.
  Cost if wrong: a user who never opens Repairs keeps a setting that is never sent, and
  the log is the only other trace. A persistent warning is taken away only by the timer
  that raised it: if the files of the integration are deleted from `custom_components`
  without removing the entry, its warnings stay visible in Repairs, because no code of
  Timerify is left to take them away. A downgrade to 1.0.0 does the same: that release
  loads the entry (minor version 2, see #15) but has neither the texts of the warning nor
  any code that deletes it, so the warnings are listed in Repairs without readable texts
  until 1.1.0 is back. The release notes of 1.1.0 should say so.
  Tests: `test_editing_keeps_a_setting_the_ac_no_longer_offers`,
  `test_editing_changes_the_settings_shown_beside_a_kept_one`,
  `test_editing_keeps_every_setting_while_the_ac_is_gone`,
  `test_an_interval_with_only_settings_not_offered_shows_them_closed`,
  `test_settings_not_taken_are_named_one_by_one_in_the_order_of_the_form`,
  `test_an_interval_setting_the_ac_no_longer_takes_raises_a_warning`,
  `test_the_warning_names_every_setting_the_ac_does_not_take`,
  `test_the_warning_follows_the_settings_the_ac_does_not_take`,
  `test_a_value_the_ac_no_longer_accepts_raises_the_warning`,
  `test_a_setting_no_form_knows_is_named_by_its_own_name`,
  `test_the_form_shows_a_value_the_ac_no_longer_lists`,
  `test_submitting_a_value_the_ac_no_longer_lists_is_refused_in_words`,
  `test_a_value_the_ac_takes_replaces_one_it_no_longer_lists`,
  `test_clearing_a_value_the_ac_no_longer_lists_drops_the_setting`,
  `test_a_value_of_the_wrong_kind_opens_the_form_without_a_wider_field`,
  `test_only_the_interval_that_has_the_lost_setting_is_named`,
  `test_the_warning_names_the_settings_in_the_language_of_the_house`,
  `test_the_warning_clears_when_the_ac_takes_the_setting_again`,
  `test_the_warning_clears_when_the_interval_no_longer_holds_it`,
  `test_the_warning_stands_after_editing_an_interval_it_does_not_concern`,
  `test_deleting_the_interval_clears_its_warning`,
  `test_a_report_before_the_reload_raises_no_warning_for_a_deleted_interval`,
  `test_a_setting_lost_while_down_raises_the_warning_at_start_up`,
  `test_an_unavailable_ac_raises_no_settings_warning`,
  `test_a_deleted_ac_raises_no_settings_warning`,
  `test_the_warnings_of_a_timer_go_with_it`,
  `test_an_ac_that_goes_offline_without_capabilities_raises_no_warning`,
  `test_the_warning_stands_while_the_ac_is_offline_until_it_reports`,
  `test_the_titles_of_two_warnings_of_a_timer_tell_the_intervals_apart`,
  `test_renaming_an_interval_renames_its_warning`,
  `test_the_warning_names_the_settings_in_the_order_of_the_form`,
  `test_an_ignored_warning_stays_ignored_after_a_reload`,
  `test_a_warning_that_went_away_comes_back_unignored`,
  `test_a_warning_of_an_interval_deleted_while_down_is_gone_at_start_up`,
  `test_a_warning_the_ac_takes_back_while_down_is_gone_at_start_up`,
  `test_a_timer_that_cannot_read_its_file_has_no_settings_warning`,
  `test_a_timer_that_cannot_set_up_has_no_settings_warning`,
  `test_an_ignored_warning_returns_when_another_setting_is_lost`,
  `test_an_ignored_warning_stays_ignored_when_a_setting_comes_back`,
  `test_a_setting_lost_while_down_returns_an_ignored_warning`,
  `test_renaming_an_interval_keeps_the_ignore_of_its_warning`,
  `test_an_ignored_warning_survives_a_restart_of_home_assistant`,
  `test_an_ignored_warning_stays_ignored_when_a_setting_returns_while_down`,
  `test_a_warning_stays_shown_after_a_restart_with_the_ac_offline`,
  `test_an_ignored_warning_survives_a_restart_with_the_ac_offline`,
  `test_a_setting_lost_while_the_ac_is_offline_shows_an_ignored_warning`,
  `test_an_interval_renamed_while_the_ac_is_offline_renames_its_warning`,
  `test_a_setting_dropped_from_an_interval_leaves_its_warning_while_offline`,
  `test_an_interval_left_with_no_setting_loses_its_warning_while_offline`,
  `test_disabling_the_timer_takes_its_warnings_away`.
- **The integration page that does not re-render waits on Home Assistant (#40, upstream).**
  After a timer or an interval is added, or an interval is edited, the Timerify page under
  Settings > Devices & services shows nothing new until it is loaded again, on Home
  Assistant 2026.10.4 (frontend 20260930.5) and on 2026.11.0b2 (frontend 20261028.1;
  2026.11.0 was not published when it was tested). The page that behaved the same is the
  one of the built-in Random helper, which also keeps saying "No entries" after a helper is
  added. The pages of `kitchen_sink` (a sensor subentry) and `local_calendar` (a calendar)
  show the change at once. The cause is in the frontend, in both versions: the page
  subscribes with `config_entries/subscribe` and `type_filter` `device`, `hub`, `service`,
  `hardware`, so it is sent no event for an integration of type `helper`; and
  `ha-config-integration-page` loads the entries of an integration of any type but device,
  hub and service once, in `_fetchManifest`, and never again. No local change was made,
  because Timerify sends what `kitchen_sink` sends: a new entry is `added`, `updated`
  (setup_in_progress), `updated` (loaded), and an interval added or edited is `updated`
  (unload_in_progress), `updated` (not_loaded), `updated` (setup_in_progress) twice,
  `updated` (loaded), through the reload that `_async_entry_updated` schedules. A copy of
  Timerify whose manifest said `integration_type` `service` and nothing else different
  showed every change within milliseconds, so the type alone decides it. That is not a
  fix we take: it would move Timerify out of Helpers and its "Add helper" into "Add
  service", a product decision, and a change made to get round a frontend fault. The issue
  is labelled `upstream`; reporting it to Home Assistant is the owner's call.
  Cost if wrong: none for the timers, their schedules or their entities, which are always
  right on the server; the Timerify page lists the old state until it is loaded again.

### Automations

- **Timerify's actions and triggers are offered by target, not in the Device block.** The
  Device block of a device asks the integration that owns the device and the domain of each
  of its entities (`ha/components/device_automation/__init__.py:232-294`: the owner at
  :254-261, the entity domains at :245-247 and :262-263; `RegistryEntry.domain` is the
  domain of the entity id, not the platform, `ha/helpers/entity_registry.py:255` and
  :288-291). A device belongs to one config entry (`ha/helpers/device_registry.py:404`),
  and Timerify puts its entities on the target's device without owning it. So on the
  boiler's device the block asks the boiler's integration and `number`, `sensor`, `switch`
  and `button`, never `timerify`. Timerify owns only the device it made for a target that is
  on none.
  The editor's **By target** tab matches the `target` of every service and trigger against
  the entities of the picked device: the integration and domain filters
  (`ha/components/websocket_api/automation.py:52-83`), with the entities that have an entity
  category left out of a device or area target (:128-131), and the lookup at :223-287. The
  tab is the frontend string `ui.panel.config.automation.editor.tabs.target`, "By target".
  So there is no `device_action` or `device_trigger` platform: one way for every timer,
  wherever its entities are. The owner accepted this at plan review (#38, #39) and
  confirmed it on 2026-11-02: no Device block, also not for the device Timerify made.
  Why: the owner's wish is to pick the boiler and choose an action or a trigger. The Device
  block cannot offer that for a device another integration owns.
  Cost if wrong: a user who looks only in the Device block finds the number's and the
  button's actions there and not Timerify's. The docs send them to **By target**.
  Tests: `test_the_boilers_device_offers_timerifys_actions_by_target`,
  `test_the_device_made_for_a_switch_offers_them_too`.
- **Stop is a service of its own, `timerify.stop`, the stop of Run for 0.** It calls
  `async_set_minutes(0)`, as the Turn off button and voice do. So it ends a countdown, turns
  off a loose device that runs without one, holds a started window until its next
  occurrence (S4), and sends nothing to a device that is off. It has no fields. A target
  names its timers, as for every service.
  Why: #38 asks for Stop beside Run and Add time. `number.set_value` with 0 is not one of
  Timerify's actions, and the button is optional.
  Cost if wrong: none known.
  Tests: `test_stop_ends_the_countdown_and_turns_the_boiler_off`,
  `test_stop_turns_off_a_loose_boiler_without_a_countdown`,
  `test_stop_leaves_a_boiler_that_is_off_alone`,
  `test_stop_aimed_at_one_channel_leaves_the_other_running`,
  `test_stop_aimed_at_a_deleted_timer_lets_the_automation_go_on`.
- **Countdowns and due commands are announced by the core and fired as Timerify's own
  events.** The core decides, in `_set_end` (the only writer of the end) and `_run_command`;
  the controller fires `timerify_countdown_started` (`entity_id`, `ends_at`),
  `timerify_countdown_ended` (`entity_id`, `reason`) and `timerify_command_due`
  (`entity_id`, `command_id`, `action`). `entity_id` is the timer's Run for, looked up in
  the registry when the event is fired, so a renamed Run for is named by its new id.
  `ends_at` is the end in the form of the Ends at state: UTC, to the second.
  - **A start** is a timer with no end getting one (Run, Add time on an idle timer, Run for,
    a strict-mode manual on, a pending "on", a window that opens on an idle timer). A loose
    run without a countdown starts none. A move of a running end, however it is made (Run
    for, Add time, Run with minutes, a pending "on", a window that ends later), announces
    neither a start nor an end. The pending command that came due in the middle of it is
    still announced. A start that the same step moves, because more than one write of the
    end falls in one fold (two intervals that open together, a window and a command due at
    one instant, a start-up catch-up), is announced with the end it leaves, which the Ends
    at sensor shows: `_set_end` carries a start that has not been taken yet to each new end.
  - **An end** has a reason. `expired`: the end was reached, by the alarm, a fold after a
    restart or a report of the target; a window whose end is the timer's end counts too.
    `stopped`: Timerify ended it: Run for 0, Stop, the Turn off button, voice and the LLM
    tools, Add time down to zero, a pending "off", a window taken away by switching off,
    editing or deleting its interval or by a change of the Workday sensor. `turned_off`:
    the target was switched off outside Timerify, by hand, by its app, by another
    automation or by the device itself (`observe` with `by_us=False`). The core already
    takes a different path for each, so the reason costs nothing to tell.
  - **A countdown whose end is not ahead of now is no countdown** (#42), whether or not a
    tick folded it. Run for, Run and Add time (up) on such a timer announce its end as
    `expired` first and then the start of the new countdown. Run for 0 announces only the
    expiry: there is nothing left to stop, and so does the core's `stop()`, which applies
    the same rule. A zero or negative Add time writes nothing and announces nothing; the
    tick that folds the end announces it.
  - **A command that comes due is announced after the drop check** (`CommandDropped` is
    not: it did nothing, and the log says so), and before the start or end it causes. A
    pending "off" on a timer with no countdown is announced too. A command that comes due
    at the very instant the countdown ends finds it run out, so the end it leaves is
    `expired`, as for a zero after a stale end (#42): a pending "off", and a bare "on" in
    loose mode (which leaves the target on with no countdown). An "off" that comes due
    earlier stops the countdown, as `stopped`. A command with minutes at that instant
    moves the end (the target is not switched off and on), so it announces no end. An
    automation that filters on `reason: expired` therefore sees the end of a window whose
    pending "off" is due at the window's end.
  - **The announcements are a channel of their own**, `TimerCore.take_announcements`, not
    effects: they switch nothing, and the effect lists of the steps stay as they were. The
    core keeps them until the controller takes them, so no step has to return them and none
    is taken twice.
  - **They are fired after the save and the refresh of the entities, and before the calls
    to the target.** An automation sees the new Ends at and Run for, and a slow device does
    not delay it. A controller that is unloaded fires nothing.
  - **Start-up announces what it folds.** A countdown that ended while Home Assistant was
    down fires `expired` at start-up, to the automations that are armed by then (Tech
    Stack, "Start-up"); a countdown that still runs fires nothing, because the restored core
    has nothing to say. A command given while Home Assistant is still starting folds its
    catch-up before automations are armed, so its announcements can reach none. That is
    Home Assistant's rule that automations do not fire during start-up.
  - **A timer whose Run for is not in the entity registry fires nothing** and logs a
    warning: an event that cannot name its timer is of no use to a trigger.
  - **A timer that is unloaded during the save fires nothing** (`_execute` fires only for
    a controller that is not stopped): the saved snapshot no longer holds the end, so the
    next load cannot announce it either. This is not tested: it needs an unload exactly
    during the save.
  Why: #39. A state cannot tell a countdown that ended from one that was stopped, or a
  start from a move, and the Next command sensor also changes when a command is added or
  cancelled. The core's decision point is exact, and an event reaches YAML users too.
  Cost if wrong: a user who wants an event when a countdown is changed has none; an
  automation that turns the boiler on again when its countdown ends would loop through
  `stopped` too, so it must check `trigger.reason`. The docs show that. An event that
  falls while its timer is unloaded during the save is not fired, by that load or the next:
  the saved timer no longer holds the end. An `expired` that coincides with a reload of
  the timer can be lost this way.
  Tests: the announcement tests of `tests/test_core.py` (from
  `test_a_countdown_from_idle_is_announced_as_started`) and `tests/test_events.py`, among
  them `test_changing_a_running_countdown_announces_nothing`,
  `test_moving_run_for_while_it_runs_fires_no_event`,
  `test_a_countdown_restored_at_start_up_is_not_announced_again`,
  `test_a_countdown_that_ended_while_down_fires_ended_at_start_up`,
  `test_a_pending_off_due_as_the_countdown_ends_announces_it_expired`,
  `test_stop_after_the_end_passed_announces_that_it_expired`,
  `test_editing_the_running_interval_to_other_days_fires_ended_stopped`,
  `test_a_holiday_that_takes_the_window_away_fires_ended_stopped`,
  `test_the_end_of_a_schedule_window_fires_start_and_expired`,
  `test_two_intervals_that_open_together_fire_the_end_the_boiler_shows`,
  `test_two_windows_that_open_together_announce_the_end_they_leave`,
  `test_switching_the_running_interval_off_fires_ended_stopped`, and
  `test_running_and_stopping_the_boiler_by_voice_fires_start_and_stop` with its LLM twin
  in `tests/voice/test_events_by_voice.py`.
- **The triggers are integration triggers on the Run for entities, matched against their
  target at each event.** The platform is `trigger.py` with `async_get_triggers`, the
  kind behind Home Assistant's own "Timer started" and "Button pressed": every loaded
  integration's `trigger` platform is registered (`ha/helpers/trigger/__init__.py:186-257`),
  the key `timerify.<name>` loads it (:451-476), and a `Trigger`
  (`ha/helpers/trigger/models.py:108-182`, its config at :27-33) validates its config
  and attaches a runner. `ENTITY_STATE_TRIGGER_SCHEMA`
  (`ha/helpers/trigger/entity_trigger.py:99-104`) is a required target and no options.
  The descriptions are read from `triggers.yaml` (`ha/helpers/trigger/descriptions.py:60-80`,
  :158-160). hassfest accepts the `triggers.yaml` and the `triggers` strings of a custom
  integration, and refuses a trigger whose description is missing from `en.json`.
  - **The target filter is the one of the services** (`entity: integration: timerify,
    domain: number`, in the normalised list form so that the description equals it), so
    **By target** offers the actions and the triggers for the same devices.
  - **The target is resolved at each event**, never cached
    (`async_extract_referenced_entity_ids`, `expand_group=False`): a timer added to the
    device, deleted, or moved to another area needs no tracking, and an automation saved
    before the timer existed covers it. A deleted timer is never matched, and nothing is
    logged: its automation stays on and simply hears no event of it. Events come a few
    times a day, so the lookup costs nothing.
  - **No options**: no "for", and no "first" or "last" of several timers. An event has no
    duration, and each timer's event stands alone, so a device with two timers fires the
    trigger twice and `trigger.entity_id` tells which.
  - **An event that names no timer is ignored**, without an error: the events are
    documented for YAML, so a user may fire one by hand from Developer tools.
  - **A hidden Run for drops out of a device or area target**, as every hidden entity does
    in Home Assistant (`helpers/target.py`, `_include_entry`); the docs say to aim at the
    Run for itself to include it.
  Why: #39 and Decision 1 of the plan: pick the boiler and choose a trigger.
  Cost if wrong: an automation aimed at a Run for whose entity id the user renames never
  fires again, as with any entity id in Home Assistant; a device target avoids it, and the
  docs say so.
  Tests: `tests/test_automation_triggers.py`, among them
  `test_the_boilers_device_offers_the_three_triggers_by_target`,
  `test_a_trigger_ignores_the_timers_of_other_devices`,
  `test_a_relay_trigger_names_the_channel_whose_countdown_ended`,
  `test_a_trigger_aimed_at_one_run_for_ignores_the_other_channel`,
  `test_a_trigger_of_a_deleted_timer_never_fires`,
  `test_a_timer_added_later_is_covered_by_the_device_trigger`,
  `test_an_event_fired_by_hand_without_a_timer_is_ignored`,
  `test_a_countdown_that_ended_while_down_triggers_once_at_start_up` and
  `test_a_command_that_came_due_while_down_triggers_at_start_up`.

### Voice

- **Russian answers are pinned by a fixture written by hand, in the one test folder that
  may hold Cyrillic.** `tests/fixtures/ru/answers.yaml` holds, for every answer that says a
  count (time left, the answer of Run for, Add time and Stop, the list of planned commands
  and the cancelling of them) and for each class of counts, the slots of a handler and the
  Russian text a speaker expects. The text is written from the rules of Russian plurals,
  never rendered from the templates, so a fixture does not repeat what it checks.
  `tests/voice/test_russian_answers.py` renders each shipped answer with the slots of a
  case and compares. It fails if a class of counts has no case (1, 2, 5, 11, 21 and, for
  minutes, 22; for the days ahead a command is due, 3 and 5), or if the slots of a case do
  not hold the count it is labelled with. The time left and the answer of Run for also have
  a case of hours with minutes after them, which pins the verb that goes with the hours and
  the word "and" that joins the two. The pre-commit hook allows Cyrillic under
  `tests/fixtures/ru/`, at any depth, and refuses it everywhere else in `tests/`, a
  `fixtures/ru/` of another folder included. The owner decided it on 2026-11-01 (#27).
  Why: the plural classes test (`assert_one_form_per_class`) proves the forms differ, not
  which goes with which count; a swapped "few" and "many" passed it. The folder is under
  `tests/`, not `custom_components/`, so HACS does not ship it.
  Cost if wrong: a Russian answer changed on purpose needs its fixture line changed too.
  Not in the fixture: 1 and 2 days, which are said "tomorrow" and "the day after
  tomorrow", and the "one" form of the days (21), since a command is due at most 7 days
  ahead.
  Tests: `test_each_russian_answer_reads_as_the_fixture_says`,
  `test_the_fixture_has_every_count_class_of_every_counted_answer`,
  `test_each_case_counts_what_it_is_labelled_with`,
  `test_every_case_has_a_name_of_its_own`,
  `test_cyrillic_is_allowed_in_the_russian_files_of_the_repository` and
  `test_cyrillic_is_refused_everywhere_else`.
- **A scope of settings carries every rule of its block, so a scope can change how a
  duration is said.** `Scope.rules` of `scripts/generate_core_commands.py` is every
  expansion rule of a block of `TimerifyRun` that has `timerify_settings`, and the delayed
  blocks of `core_commands.yaml` copy all of them, not `timerify_settings` alone. The first
  rule that uses it is `timerify_duration` (#26). Everywhere it is
  `timerify_spelled_duration`, which is what it was (hours and minutes, each alone or both,
  or a phrase such as "half an hour"), or hours followed by a bare number of minutes from 1
  to 59, with "and" between them or not, in English and in Russian: "for 1 hour 30" and
  "for 1 hour and 30" are 90 minutes. The `climate` and `water_heater` blocks of
  `TimerifyRun` set `timerify_duration` to `timerify_duration_with_and`: the spelled-out
  form, or hours, "and" and the minutes, with "and" required (Russian: its word for "and").
  So for them "for 1 hour 30" stays one hour at 30 degrees, and "for 1 hour and 30" is 90
  minutes. The rule is shared by every sentence that says a duration: "set the boiler timer
  to 1 hour 30", "add 1 hour 30 to the boiler" (a thermostat takes that one too, since
  adding time has no settings) and the delayed command "turn on the boiler in 15 minutes for
  1 hour 30", whose block copies the override for a thermostat and a water heater.
  Why: hours followed by a bare number is a temperature only where there is a temperature;
  for the devices without one the issue's fix adds no new ambiguity, and the devices with
  one keep the old reading. "And" cannot start a setting, so for them the two phrases
  cannot be read each as the other's: the number right after the hours is the temperature,
  and the number after "and" is the minutes (the controller's ruling after the review of
  the first version, which left "for 1 hour and 30" not understood on a thermostat). A
  block's rule replaces a global one inside the global rules that its sentences use
  (`timerify_for_part` is global and says `timerify_duration`), so the override reaches the
  delayed command without a copy of the sentences. The override is not only a label: probed
  with hassil 3.12.1, without it "turn on the AC for 1 hour 30" has two parses of the same
  score (`text_chunks_matched` 16), the temperature and the 90 minutes, and `recognize_best`
  (`hassil/recognize.py:814`, `_get_result_score` at :819) keeps the first of them, which
  is the temperature only because the rule lists the spelled-out form first. With the
  override each phrase has one reading, in both languages, for both kinds of device, alone
  and after a delay.
  Cost if wrong: "for 1 hour 30" said to a thermostat sets 30 degrees, as before. A user
  who means "an hour, and 30 degrees" and says "and" gets 90 minutes, and must say
  "degrees". A thermostat or water heater listed by hand with no domain gets the sentences
  that fit every device, so it takes "for 1 hour 30" as 90 minutes.
  Tests: `test_for_an_hour_and_bare_minutes_runs_a_switch_for_90_minutes`,
  `test_add_an_hour_and_bare_minutes_adds_90_minutes`,
  `test_russian_hours_and_bare_minutes_run_a_switch_for_90_minutes`,
  `test_a_delayed_turn_on_runs_a_switch_for_hours_and_bare_minutes`,
  `test_hours_and_a_number_are_read_one_way_where_a_temperature_is_said`,
  `test_for_an_hour_and_a_bare_number_stays_a_thermostat_s_temperature`,
  `test_for_an_hour_and_a_bare_number_stays_a_water_heater_s_temperature`,
  `test_for_an_hour_and_30_is_90_minutes_to_a_thermostat`,
  `test_a_delayed_turn_on_of_a_thermostat_reads_hours_and_a_number` and
  `test_a_scope_carries_every_rule_of_its_block`.
- **A delay is said with the lists of a duration, and refused by the controller with its
  limit.** The delayed commands of `core_commands.yaml` count the hours of a delay with
  `timerify_hours` (1 to 168) and its minutes with `timerify_minutes` (1 to 1440, which may
  be said as words) or `timerify_long_minutes` (1441 to 10080, in digits): the lists a
  duration uses, filling the slots `delay_hours` and `delay_minutes`. The seconds stay
  core's `timer_seconds`, 1 to 100. `DELAY_LISTS` of the generator maps each unit of a
  shape of core to its list, and `delay_rules` applies it; the handler is as it was,
  since `_delay_of` already sums the three slots (#29). The limits are the controller's: a
  command to turn on is kept at most 7 days ahead, and a command to turn off sets the
  countdown, so it reaches 24 hours. A delay past one is refused with the texts that
  exist, which name the limit: `command_too_far` ("A command can be set at most 7 days
  ahead.") and `duration_out_of_range` ("A timer runs for 1 min to 24 h."). A count past a
  week in one unit is not understood, as for durations. A test ties `DELAY_LISTS` to the
  rules of the sources that count a duration (`timerify_minutes_count`,
  `timerify_hours_part`), so that a change in how the minutes are split reaches the delays
  with it. Why: one bound for every count, already measured for cost (the duration entry
  of "What can be said"), and no new string.
  Cost if wrong: "in 200 hours" is not understood.
  Tests: `test_turn_on_in_2000_minutes_keeps_a_command`,
  `test_turn_on_in_150_hours_keeps_a_command`,
  `test_turn_on_a_week_and_a_minute_ahead_is_refused_with_the_limit`,
  `test_turn_off_in_120_minutes_sets_the_timer`,
  `test_turn_off_in_2000_minutes_is_refused_with_the_limit`,
  `test_russian_delays_past_100_reach_the_handler`,
  `test_turn_on_in_one_hundred_twenty_minutes_keeps_a_command`,
  `test_a_delay_past_100_can_be_said_in_words`,
  `test_a_delay_beyond_a_week_in_one_unit_is_not_understood`,
  `test_a_delay_counts_its_hours_and_minutes_as_a_duration_does` and
  `test_the_file_covers_every_command_of_home_assistant_for_every_kind_of_device`.
- **The phrasings core's gazetteer took are added as they are found; the gazetteer itself
  cannot be told to leave Timerify's devices alone.** In Home Assistant 2026.10.4 the
  built-in agent hands a sentence to the gazetteer when hassil has no result or one with
  unmatched entities (`conversation/default_agent.py:495`), and skips it only for a custom
  sentence that matched with an unmatched entity (`:704-718`). The gazetteer builds its home
  from every exposed entity, with no way to leave one out (`conversation/gazetteer.py:96-136`),
  and reads English only (`:206-208`). So a sentence in English that names a device with a
  timer, has "turn on" or "turn off" in it, and that no sentence of Timerify's matches,
  switches the device at once, with no timer. 2026.11.0b1, the newest release on PyPI
  (2026-10-29), has the same gate (`default_agent.py:502` and `:720-734`), and
  `gazetteer.py` differs only in naming `async_get_matcher` (`:222`, `:263`). There is no
  way to keep a custom intent's names out of it, so #21 stays open, labelled upstream, and
  each phrasing found is made Timerify's own (#21):
  - A delay in days, N from 1 to 365 ("in" or "after", "day" or "days"; Russian "cherez",
    "den'", "dnya", "dney"), and in weeks, N from 1 to 52, as one more way to say a delay
    for every command that takes one. Each count has a slot of its own, `delay_days` and
    `delay_weeks`, a plain range with no multiplier, and the handler adds the units up
    (`_UNIT_SECONDS`). So the tool of an LLM agent takes `delay_days` and `delay_weeks` too.
    A year is understood so that what a command cannot wait is refused with the limit and
    not left to the gazetteer: "turn on in 8 days" or "in 2 weeks" with `command_too_far`
    (7 days), "turn off in 2 days" or "in a week" with `duration_out_of_range` (24 h).
  - A day, half a day and a week, said in a word: "in a day", "in half a day", "in a week"
    (Russian "cherez den'", "cherez poldnya", "cherez nedelyu"). They are a list of fixed
    values, `timerify_delay_words`, that fills `delay_minutes` with 1440, 720 and 10080, as
    `timerify_duration_words` fills `minutes`.
  - English also says all of these ended by "from now", "from today" or "later": "turn
    on the boiler 2 days from now", "a week from today", "2 days later", "a week from now
    turn on the boiler", "half a day later". The same slots and words, in the rule
    `timerify_own_delay`, after "in" or "after" or before one of those endings. Only days,
    weeks and these words: "5 minutes from now", "2 hours from today" and "an hour later"
    were never taken by the gazetteer (no device by that name), and Russian has no phrase
    that is used the same way, so none was added there. A bare "later" is not a delay: it
    says no time, so no sentence reads it (`test_a_bare_later_is_not_a_delay`) and it is
    left to Home Assistant, which turns the device on at once for "turn on the boiler
    later" and does not understand "turn off the boiler later".
  - `delay_rules` of the generator appends `<timerify_own_delay>`, the rule that says all
    of these, to each rule it writes, when the sentences of the language define it.
  - "scheduling" for "schedule" in the English schedule sentences, with the article before
    the noun optional, since "turn off scheduling for the boiler" has none (and "turn off
    schedule for the boiler", which the gazetteer took too, is then a sentence).
  - A range is not given a multiplier to count days as hours. hassil keeps the number words
    of a range by its bounds, not by its multiplier: the cache of the trie is keyed by
    `(start, stop, step, fractions)` per language (`hassil/string_matcher.py:889-904`) and
    the multiplier is applied when the trie is built (`:1094`). Probed with a percentage
    and a list of days in one `Intents`, a range of 1 to 100 with `multiplier: 24` is handed
    the words of the first range of 1 to 100 that was read, and hands out its own: both say
    "two" as 2 when the percentage is read first (so "in two days" would be two hours), and
    both say it as 48 when the days are (so "at forty percent" would be 960). Digits are
    multiplied on the spot and are right either way. Core has the same collision in its own
    sentences (a `0..100` range with `multiplier: -1` next to plain `0..100` ranges, in
    every language), so it is an upstream defect, and no bounds that happen to be free
    today are a safe way around it: a release of Home Assistant, another integration or the
    user's own sentences can add a range with them. Plain ranges share a trie harmlessly,
    since the values are the same.
  What still reaches the gazetteer, probed through the built-in agent with Timerify's
  sentences loaded (English; Russian has no gazetteer). A phrasing that Timerify's
  sentences meet with an unmatched entity is not handed on, so "in a month", "in a year",
  "in 366 days", "in 53 weeks", "in 400 days", "a month from now", "a year from now",
  "a month from today", "a month later", "366 days from now", "366 days later", "53
  weeks from now", "53 weeks from today", "in an hour", "in half an hour", "in 2 days
  and 3 hours", "2 days and 3 hours from now", "2 days and 3 hours later", "a few days
  from now", "a few days later", "the day after tomorrow", "3 days after today" and "in
  200 hours" switch nothing ("Sorry, I couldn't understand that"). That skip is the
  mechanism of
  `default_agent.py:704-718`, which Timerify does not control, so tests pin it for the
  count past a year, a month and a year, in sentences of every command: a release that
  changes it fails them (`test_more_than_a_year_of_days_or_weeks_is_not_understood` and
  its siblings; simulating the change by passing no result to the fallback fails them in
  English and leaves Russian green). These do switch:
  - turn on, the dangerous direction, since in Loose mode the device then runs without a
    countdown: "tomorrow", "tonight", "next week", "next month", "this evening", "later"
    (alone), "in the morning", "on monday", "2 days ahead", and the clock times "at 7",
    "tomorrow at 7" and "at noon";
  - turn off: "tonight", "tomorrow", "tomorrow morning", "this evening" and "at 7".
  Why: each phrasing found is then refused or done as asked, instead of switching the
  device. Cost if wrong: a phrasing not yet found switches the device at once, in English.
  Russian is not affected, since the gazetteer has no Russian.
  Tests: `test_turn_on_in_2_days_keeps_a_command_two_days_ahead`,
  `test_turn_on_in_7_days_is_the_longest_delay_that_is_kept`,
  `test_turn_on_in_8_days_is_refused_with_the_limit`,
  `test_a_delay_in_more_days_or_weeks_is_refused_with_the_limit`,
  `test_turn_off_in_2_days_is_refused_and_leaves_the_boiler_on`,
  `test_a_delay_in_days_can_be_followed_by_how_long_the_boiler_runs`,
  `test_a_thermostat_is_turned_on_in_days_with_its_settings`,
  `test_a_delay_in_days_can_be_said_in_words`,
  `test_every_sentence_that_says_a_delay_in_days_reaches_the_handler`,
  `test_every_sentence_that_says_a_delay_in_weeks_reaches_the_handler`,
  `test_turn_on_so_long_ahead_keeps_a_command`,
  `test_turn_on_beyond_a_week_ahead_is_refused_with_the_limit`,
  `test_turn_off_half_a_day_ahead_sets_the_timer_of_a_running_boiler`,
  `test_turn_off_beyond_a_day_ahead_is_refused_and_leaves_the_boiler_on`,
  `test_every_sentence_of_every_command_can_end_the_delay_in_other_words`,
  `test_a_bare_later_is_not_a_delay`,
  `test_more_than_a_year_of_days_or_weeks_is_not_understood`,
  `test_more_than_a_year_ahead_is_not_understood`,
  `test_in_a_month_or_a_year_is_not_understood`,
  `test_a_month_or_a_year_ahead_is_not_understood`,
  `test_turn_on_in_a_day_or_a_week_keeps_a_command`,
  `test_turn_off_in_half_a_day_sets_the_timer_of_a_running_boiler`,
  `test_turn_off_in_a_week_is_refused_and_leaves_the_boiler_on`,
  `test_a_day_half_a_day_and_a_week_are_said_as_fixed_delays`,
  `test_a_week_is_kept_by_a_turn_on_and_two_weeks_are_refused`,
  `test_the_days_and_weeks_of_a_delay_have_slots_of_their_own`,
  `test_the_own_delay_rule_is_a_delay_only_when_the_sources_have_it`,
  `test_llm_plans_a_command_in_days_and_weeks`,
  `test_turning_off_scheduling_switches_the_schedule_not_the_boiler`,
  `test_scheduling_asked_off_in_other_words_switches_the_schedule_only` and
  `test_scheduling_asked_on_in_other_words_switches_the_schedule_only`.
