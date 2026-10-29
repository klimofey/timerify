# Rulings

Decisions made where the spec (`docs/superpowers/specs/2026-10-28-timerify-design.md`) is
silent or its plan was wrong, recorded so they can be revisited. Each entry: what was
decided, why, and what it costs if it turns out wrong. Process decisions (branching,
tooling) are not listed; only decisions that shape the product or its code.

An entry of phase 1 that a later phase changed is rewritten to what holds now, not
repeated beside its successor.

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
- **A service call that takes longer than 30 seconds counts as failed**
  (`SERVICE_CALL_TIMEOUT`), each call of a list on its own. Home Assistant service calls
  have no timeout of their own, and a hung device would otherwise freeze its timer. Cost if
  wrong: a slow but working device gets one extra command.
- **The longest countdown is one day** (`MAX_MINUTES = 1440`). `timerify.add_time` clamps
  so the remaining time never exceeds it, matching the maximum of the "Run for" number.
  Cost if wrong: users who need longer timers.
- **R10 logging lives in the controller.** When a wake-up comes due while the target is
  unavailable, the controller logs what was due, comparing the snapshot before and after
  `tick`: "ended" only when the countdown really ended and the target is wanted off (a
  command due at that instant that extended it, or that turns the target on, does not
  count), and "command came due" for every command that was carried out (what it wants
  is applied when the target is back, if it is still relevant then, as R10 says). A command dropped because the run it asked for is over
  is an effect of the core (`CommandDropped`) that the controller logs at info level; the
  core stays pure and emits no other signal. Cost if wrong: none.

### Restarts and storage

- **The store keeps the end, the unconfirmed wish to turn on or off, the owed settings and
  the pending commands**, with times as ISO UTC strings, and writes only when one of them
  changes. The last observed state of the target is not stored: on start-up the first
  report of the target is always treated as "came back" (spec §5.7, R10), so a wish stored
  before a restart is enforced. The owed settings are stored under `owed_settings`, the
  commands with `command_to_json`, the shape of the "Next command" attribute, so there is
  one serialisation.
- **The store file is version 2; the pending commands joined it without a further
  version.** The migration from version 1 adds `owed_settings` and `commands`, and the
  store reads version 2 strictly: the migration guarantees the keys, and tolerant reads
  would hide a broken migration. Version 2 was never released before commands existed, so
  it needs no second step. Cost if wrong: a version 2 file written by a development build
  from between the two changes has no `commands` and fails to load; that exists on
  developer machines only.
- **The snapshot is stored before a command is sent.** A restart during a slow call would
  otherwise lose a newly set countdown.
- **The controller arms the stored wake-up itself at start-up**: the earlier of the stored
  end and the first stored command, since an unchanged snapshot produces no new alarm from
  the core.

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
- **"Apply is separate" is the `apply_if_on` keyword of `set_duration` and `run_open`**
  (design note D3), not a public `apply_settings`. The change of the timer and the push of
  settings onto a running target are decided separately but in one atomic core call, which
  meets the §5.4 bullets. Cost if wrong: a phase-3 caller that forgets
  `apply_if_on=False` pushes settings onto a running target, so phase-3 tests must cover
  S1 with settings. `apply_if_on=False` is not stored yet either; see `docs/followups.md`.
- **Owed settings go with the next `TurnOn`; otherwise `ApplySettings` is sent when the
  target is on or a turn-on is in flight.** The lock means an in-flight turn-on has
  returned before the next command runs. Cost if wrong: a device slow to report "on" gets
  its `set_*` calls right after the turn-on.
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
- **One alarm sits at `next_wakeup`, the earlier of the end and the first command**, and
  the core's `tick` (formerly `expire`) handles both kinds of due items. One wake-up path
  for both. Cost if wrong: none.
- **The catch-up folds all due items in time order, a command before the expiry on a tie,
  and wants one final state.** That avoids off/on flaps after a restart and at coinciding
  times. Cost if wrong: a due `on` then `off` never reaches the device, which is intended.
- **`observe` runs the catch-up first, and skips R3 to R5 only when the catch-up moved the
  timer**, that is, a command was carried out or the end was reached. It generalises
  phase 1's "expiry outranks the report": a manual off reported in the same instant a
  command fires is overridden by the command (P1). A command that was merely dropped does
  not move the timer, so R3 to R5 still apply: spec §5.7 lists "execute or drop" and "apply
  R3/R4" as separate steps, and skipping them would leave a strict target that is found on
  after a restart without a countdown. Cost if wrong: none found.
- **The controller notifies the entities when `end` or `commands` changed, and each entity
  gates its own write.** The "Next command" sensor must show a command added to an idle
  timer. Cost if wrong: none.
- **The "Next command" sensor writes its state only when the command list changes, and its
  attribute is unrecorded**, proven with the recorder fixture (§3, a small recorder).
  Cost if wrong: one slower test.

### Deferred

- **A deleted target still gives no sign.** The spec is silent and it changes no
  spec-defined behaviour, so it stays in `docs/followups.md`, under "Later". Cost if wrong:
  timers of deleted targets stay silent until a later phase.
