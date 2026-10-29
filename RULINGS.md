# Rulings

Decisions made where the spec (`docs/superpowers/specs/2026-10-28-timerify-design.md`) is
silent or its plan was wrong, recorded so they can be revisited. Each entry: what was
decided, why, and what it costs if it turns out wrong. Process decisions (branching,
tooling) are not listed; only decisions that shape the product or its code.

## Phase 1: core timer

### Targets

- **Groups switch through `homeassistant.turn_on` / `turn_off`.** The `group` domain has
  no `turn_on` / `turn_off` services of its own in Home Assistant 2026.10.4. Cost if wrong:
  none; a test checks the services against the installed version.
- **No generic fallback for unlisted domains.** A domain outside the supported table
  raises `ValueError`, and the config flow offers only supported domains. Adding a domain
  stays a table entry (spec §5.4); a fallback that no UI path reaches would be dead code.
  Cost if wrong: one table row later.
- **Climate and water heater targets are filtered by their features.** Climate needs
  `ClimateEntityFeature.TURN_ON` and `TURN_OFF`; water heaters need
  `WaterHeaterEntityFeature.ON_OFF`. Their `turn_on` / `turn_off` services exist only on
  entities that advertise these. Cost if wrong: such devices cannot be added until
  settings-based turn-on lands in phase 2.
- **A target missing at setup fails the entry** with `ConfigEntryError`
  (`target_not_found`), so Home Assistant shows the entry as failed and retries on reload.

### The timer

- **A rejected command is retried, an in-flight one is not repeated.** A failed or timed
  out `turn_on` / `turn_off` marks the wish as unsent (in memory only); it is sent again
  when the target next reports its state, or by the next command that wants the same
  thing. A call that returns without error while the target still shows the old state
  counts as not delivered too, so a device that acknowledges and ignores a command (an MQTT
  switch out of range, a cloud integration that only acknowledges) is sent it again. This
  is how "pending commands are firm promises" holds. Cost if wrong: a device that confirms
  its state only after the call returns may get one duplicate, idempotent command.
  Reports that merely repeat the target's state send an unsent wish at most three times
  (`MAX_AUTOMATIC_RESENDS`), then one warning is logged and nothing more is sent; the count
  starts again when the target's state changes (including a return from unavailable and
  start-up) or when a command wants the wish, which always sends. Without the bound, a
  device that refuses a command and answers it with a report of its old state would be
  commanded for ever.
- **The generic domain fallback of spec §5.4 is built in phase 2**, together with the rest
  of §5.4; phase 1 supported only the listed domains.
- **A service call that takes longer than 30 seconds counts as failed**
  (`SERVICE_CALL_TIMEOUT`). Home Assistant service calls have no timeout of their own, and a
  hung device would otherwise freeze its timer. Cost if wrong: a slow but working device
  gets one extra command.
- **The longest countdown is one day** (`MAX_MINUTES = 1440`). `timerify.add_time` clamps
  so the remaining time never exceeds it, matching the maximum of the "Run for" number.
  Cost if wrong: users who need longer timers.
- **R10 logging lives in the controller.** When an alarm comes due while the target is
  unavailable, the controller logs it; the pure core emits no extra signal.

### Restarts and storage

- **The store keeps only the end and the pending command**, as ISO UTC strings, and writes
  only when one of them changes. The last observed state of the target is not stored: on
  start-up the first report of the target is always treated as "came back" (spec §5.7,
  R10), so a pending command stored before a restart is enforced.
- **The snapshot is stored before a command is sent.** A restart during a slow call would
  otherwise lose a newly set countdown.
- **The controller arms the stored end itself at start-up**, since an unchanged running
  countdown produces no new alarm from the core.

### Services

- **Services aimed at an unloaded timer behave like any Home Assistant entity service**:
  a warning that the referenced entities are missing, and nothing else. Re-implementing
  target resolution would duplicate Home Assistant.

### Translations

- **The Russian entity names were chosen by the implementer** ("turn on for" and "turns off
  at", see `translations/ru.json`); the spec gives only the English ones. Cost if wrong:
  the owner renames a string.

### Verification

- **The smoke test is a repeatable script** (`scripts/smoke/`) that drives a real Home
  Assistant container, so later phases and the final smoke test reuse it.
- **The smoke script uses Home Assistant's frontend endpoints** (onboarding, config-entry
  flows, registries over WebSocket). No documented API exists for onboarding or creating
  config entries; the script drives a throwaway instance only. Cost if wrong: the script
  breaks on a Home Assistant upgrade, which running it shows at once.
