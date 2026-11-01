# Phase 6 research: the runtime counter

Branch phase-5-card, HA 2026.10.4. `HA/` = `.venv/lib/python3.14/site-packages/homeassistant`,
`PHCC/` = `.venv/lib/python3.14/site-packages/pytest_homeassistant_custom_component`.
Everything below was read in source; nothing was run (no pytest, no Docker). The only
commands executed were two `python -I` one-liners that import HA helpers to evaluate pure
functions (display-precision ratios, unit conversion). Anything not verified is in "Not
verified" at the end.

Spec anchors: §3 lines 76-80 (no sub-minute writes), §5.7 (restarts), §5.8, §6.1 line 240,
§6.2 lines 246-248. §6.3 and §6.4 do not mention runtime (grep of the spec: "runtime" only at
lines 40, 48, 79, 87, 224, 238, 248).

## 1. Sensor semantics

Device class, state class, unit
- `SensorDeviceClass.DURATION` allows every `SensorStateClass`: `HA/components/sensor/const.py:830`
  (`DURATION: set(SensorStateClass)`), so `TOTAL_INCREASING` raises no warning
  (check at `HA/components/sensor/__init__.py:621-640`).
- Allowed native units: d, h, min, s, ms, us (`const.py:669-676`, docs `const.py:230-233`). Any other
  unit only logs a warning once (`sensor/__init__.py:764-786`).
- Core precedent for exactly this pair: `HA/components/nibe_heatpump/sensor.py:112-125`
  (DURATION + TOTAL_INCREASING in h, min, s). history_stats uses h with precision 2
  (`history_stats/sensor.py:239-247`) but it is a window measure, not a lifetime total.
- Unit to use: minutes (`UnitOfTime.MINUTES`, "min"). §3 line 78 already calls the counter a
  "number of minutes", like "Run for" (`number.py:46`). Users can switch the display unit to
  hours or days in the entity settings: the converter exists (`const.py:614` ->
  `HA/util/unit_conversion.py:329-350`), the stored unit is picked by
  `_custom_unit_or_undef` (`sensor/__init__.py:911-933`, used at `:963-970`) and statistics stay consistent via
  the unit class (`sensor/recorder.py:252-272`).
- `suggested_unit_of_measurement`: not worth it. It is applied once, when the registry entry is
  first made, then stored in private options (`sensor/__init__.py:416-466`); it would only
  make Timerify's taste override the spec's minutes for new entities.
- `suggested_display_precision`: worth it, set to 0. Without it HA infers 2 decimals for a
  duration in minutes (`UNITS_PRECISION[DURATION] = (ms, 0)` at `const.py:785`,
  `DEFAULT_PRECISION_LIMIT = 2` at `const.py:765`, rule at `sensor/__init__.py:819-886`;
  evaluated here: ms->min gives 4, capped to 2), so the page would show "12.00 min". With
  precision 0 and a user switching to hours the display adapts to 1 decimal, to days 3
  (evaluated with `_calculate_precision_from_ratio`, `sensor/__init__.py:148-171`). The value
  goes into registry options on first add (`_update_suggested_precision`, `:889-909`).
- `last_reset` must stay unset for TOTAL_INCREASING, else `ValueError`
  (`sensor/__init__.py:468-483`).

How the recorder reads a decrease (long-term statistics)
- Statistic kind for total_increasing is `sum` only (`sensor/recorder.py:65-74`).
- A drop below 90 percent of the previous value is a new cycle (meter reset): the sum is kept,
  counting restarts from the lower value (`recorder.py:481-500`, condition at `:499`; sum
  bookkeeping `:784-825`).
- A drop of up to 10 percent is NOT a reset: it is subtracted from the sum, and after two such
  dips a warning is logged (`recorder.py:491-493` -> `warn_dip` `:420-455`). So a small
  backwards step silently corrupts the sum; a big one (more than 10 percent) is harmless to the
  sum but double counts the run again. Negative values are dropped with a warning (`:495-497`).
- Non-numeric states (`unavailable`, `unknown`) are skipped when compiling
  (`recorder.py:226-241`), so the unload "restored unavailable" state is harmless
  (`HA/helpers/entity.py:1479-1512` writes it on unload).
- Periods: 5-minute statistics are compiled at minute 0,5,.. second 10 of the clock
  (`HA/components/recorder/core.py:649-652`); the states used for a period are those with
  `start < last_updated < end` plus the last state before it (`recorder/history/__init__.py:206-209`;
  `sensor/recorder.py:~556-561` passes `start - timedelta.resolution`). Hours and days are
  aggregates of these periods.

Can the value go down in our design?
- Restore from stale data: only if state is restored from something older than the last
  published value. Avoided by persisting before publishing (section 2).
- Wall-clock step backwards (NTP): the accumulator must clamp each interval at zero and never
  publish less than the last published value.
- Deleting the timer and adding it again, or a user deleting the file: a new cycle, which
  the recorder handles as a reset (drop to 0 is below 90 percent).
- Nothing else. Disabling then re-enabling keeps the file (decision D5), so no drop.

Reset action
- HA has no generic reset for sensors; the reset in `utility_meter` is that integration's own.
  Users correct statistics through Developer tools > Statistics (the `no_state` and unit
  issues, `sensor/recorder.py:1098-1107`) or `recorder/clear_statistics`
  (`HA/components/recorder/statistics.py:967`, websocket `recorder/websocket_api.py:395-400`).
- Recommendation: no reset in phase 6 (D8). If added later, writing 0 is safe for statistics
  (`recorder.py:499`).

## 2. Restore across restarts

Options
- `RestoreSensor` / `RestoreEntity`: `async_get_last_sensor_data()` returns
  `SensorExtraStoredData(native_value, native_unit)` (`sensor/__init__.py:1029-1042`,
  `:973-1000`), read from `core.restore_state` loaded once at start
  (`HA/helpers/restore_state.py:144-170`). It is dumped every 15 minutes, at start and at
  stop (`:30`, `:218-262`), keyed by entity_id (`:107-111`, `:330-340`), entries older than
  7 days dropped (`:33`). A crash loses up to 15 minutes, so after restart the value is below
  the last recorded state: a dip (section 1). This is the reason §5.7 gives for not using it
  for the timer (spec line 217-218), and it applies unchanged to a total_increasing value. A
  renamed entity_id also loses its restore data.
- Timerify's own store: `TimerStore` writes the timer file on every change, immediately
  (`store.py:193-254`, `async_save` at `:241`), keyed by entry id
  (`f"timerify.{entry_id}"`, `store.py:196`), deleted in `async_remove_entry`
  (`__init__.py:79-87`). The core is deliberately pure (`core.py:1-8`) and `Snapshot`
  (`core.py:65`) is "the state of the timer"; the file is validated strictly
  (`store.py:_validated`).
- Which fits "one timer as the single source of truth" (goal 1, spec line 29): the counter
  does not decide whether the target runs; it records what the target did. It must not read the
  timer, must not write to the target, and must not sit in the core's `Snapshot`. Put it in
  its own small store (D1): `RuntimeStore`, key `timerify.<entry_id>.runtime`, version 1,
  payload `{"seconds": <float>}`. No change to `TimerStore.STORAGE_VERSION = 4` or its
  migration chain (`store.py:150-190`).
- Persist-before-publish: at each minute tick, `await store.async_save()` then write the
  state, so stored >= published always and a restart can never produce a dip
  (`Store.async_save` is immediate, `HA/helpers/storage.py:464`). `async_delay_save` plus its
  final-write listener (`storage.py:480-548`) would cut the writes but loses up to the delay
  on a crash (D9). One small file write a minute while the target is on is far below what
  the recorder already writes for the same state change.
- On unload (reload for any option or interval edit, rename, delete) the entity closes the open
  run at `utcnow()` and saves in `async_will_remove_from_hass`. Entry removal then deletes the
  file (`async_remove_entry`, add the second store next to `__init__.py:87`).

Time the target was on while Home Assistant was down
- §5.7 re-arms what is PROMISED (the timer's absolute end, pending commands, windows) and, when
  the target disagrees with the timer, applies R3/R4 "as if the change had just happened"
  (spec lines 206-215, `core.py:555-600`). It never reconstructs what happened while down.
- A counter is a record, not a promise. Recommendation (D2): count nothing for downtime. At
  start the counter reads the target's current state; if it is on it opens a run at that
  moment. This is "as if the change had just happened" applied to the record, never
  overcounts, and keeps the value monotonic. The error is bounded by the downtime, which is
  one to a few minutes for a restart.
- Rejected: back-dating the run across the downtime when the target was on before and after
  (a manual off and on during downtime would be counted as on), and crediting up to the timer's
  end (counts only Timerify's runs; the spec counts "every on").
- README must say so: "Time while Home Assistant is not running is not counted."

## 3. Counting

"On" exactly as Timerify judges it
- `actual_state(state) -> "on" | "off" | "unavailable"` (`domains.py:555-564`), which uses the
  entity's domain row: `OnRule.matches(state)` (`domains.py:270-286`, `is`/`is_not` over a set),
  rows `_ONLY_ON` (generic `FALLBACK`, `:345`/`:369-372`), `_NOT_OFF`, and media players
  `_NOT_OFF_OR_STANDBY` (`:347`, `:504-516`). A missing state, `unavailable` and `unknown` are all
  "unavailable" (`domains.py:555-564`, docstring: none can be trusted).
- Reuse `actual_state` unchanged. Climate heat -> cool stays "on" and is not a transition
  (OnRule is over the state string; `core.py:581-583` records `last_actual` the same way).
- The counter judges the ACTUAL state only. Pending commands (firm promises, P1/P2) and the
  wish (`Snapshot.pending`) are never read: a promise not yet carried out is not runtime,
  and when it is carried out the target's own report starts the run. This is R10's
  desired/actual split applied to the counter.

Event APIs
- `async_track_state_change_event(hass, entity_id, @callback)` (`HA/helpers/event.py:304-330`)
  gives every change in order with `event.time_fired` (`HA/core.py:1392`). Use `time_fired`,
  not `utcnow()`: the controller's handler runs under a lock that can wait up to
  `SERVICE_CALL_TIMEOUT` (30 s) behind a service call (`controller.py:849-858`, lock
  `:247`), so hooking into the controller's `_handle_state_change` would time-stamp runs
  late. A second subscription to the same entity is a dict lookup, so the counter subscribes
  on its own (inside the sensor's `async_added_to_hass`, released by `async_on_remove`) and
  is independent of the controller's lock and `_stopped` logic.
- First observation: read `hass.states.get(target)` when the sensor is added. No
  `async_at_started` wait is needed (the controller waits because it acts on the target; the
  counter only observes). At boot a not-yet-loaded target reads as "unavailable"; its first
  report arrives as a state change.
- Tick: `async_track_time_interval(60 s)` re-arms `loop.call_at(loop.time() + 60)` after each
  firing (`event.py:1577-1649`, re-arm at `:1604-1611`): drifts, and its phase is the moment
  of registration, so it is not aligned to any minute, hour or midnight. Use
  `async_track_utc_time_change(hass, cb, second=N)` (`event.py:1750-1849`): aligned to the
  clock, UTC (`local=False`), fires at second N plus a per-listener jitter of 50-500 ms
  (`event.py:87-88`, applied at `:1778`). The jitter means a tick "at second 0" is always
  written AFTER the boundary and so lands in the NEXT 5-minute/hour/day period
  (`history/__init__.py:206-209`); a tick at second 59 lands BEFORE it. This is why the
  second matters (D3).
- A tick callback only publishes. It never counts ticks: the total is
  `stored + (now - since)` from timestamps, so a missed or merged tick (a test jumping 10
  minutes fires the handle once: `PHCC/common.py:539-564`; a busy loop) loses nothing.

Partial minutes and the off transition
- Keep exact seconds internally (a pure `RuntimeCounter`: `seconds`, `since`;
  `observe(now, actual)`, `total(now)`); intervals clamped at >= 0.
- Publish only at ticks, and never at a transition: the sensor value changes only in a tick
  callback, and only when the published number differs from the last one written. A write
  at the off transition WOULD break "at most once a minute" for a relay that flaps (five
  on/off pairs in 30 s are ten writes). Instead the off transition marks the counter dirty;
  the next tick publishes the final figure and a clean counter publishes nothing. The
  tick listener stays registered for the life of the entity (D11); it returns at once when
  nothing changed.
- Published value (D3, recommended): minutes = `round(total_seconds / 60, 2)` as a float
  written by a tick at second 59, display precision 0. Attribution error at any minute
  boundary (hour, midnight) is under one second, because the tick at 23:59:59.x reports the
  total as of 23:59:59.x and lands in the old period; the whole run splits correctly with no
  sub-minute write. Alternative, simpler to test: tick at second 0 and whole minutes
  (`floor`). It never overreports, but a run is credited a full minute late at every boundary
  and the floor loses up to a minute again: a 23:30-00:30 run reads 29 + 31 minutes (error 1
  minute, up to 2 minutes for runs not minute-aligned).
- Monotonic guard: publish `max(last_published, computed)`.

Unavailable or unknown targets
- Recommendation (D2): do not count, pause. On a change to "unavailable" close the open run at
  the event time; on a change back to "on" open a run at that event time. Counts only what
  was observed (same rule as downtime), consistent with `actual_state`'s own rule that
  these states "cannot be commanded or trusted". A Wi-Fi plug that drops for 5 minutes with
  the relay still on loses those 5 minutes: bounded, documented.
- The runtime SENSOR itself never goes unavailable because the target does: it keeps its
  last value (gaps would only be skipped by the recorder, `recorder.py:226-241`, but cards and
  automations read a value). It is unavailable only when unloaded.
- Pitfall: `TimerifyEntity._handle_controller_update` writes the state by default
  (`entity.py:64-75`) and the controller notifies every minute while a countdown runs
  (`controller.py:1158-1176`, `_notify` `:1184`). The runtime sensor must override it as a
  no-op (it follows its own tick), or it would write at every command and every refresh.

## 4. Lifecycle

Enabling and disabling in the options flow
- The options flow ends in `async_update_entry(entry, options=...)`
  (`HA/config_entries.py:4085-4123`); when the options differ, listeners run
  (`:2780-2802`) and Timerify's `_async_entry_updated` calls `async_schedule_reload`
  (`__init__.py:61-64`, `config_entries.py:2587-2594`). `options_flow_reloads = False`
  (`config_flow.py:656-659`) is required: HA raises `ValueError` if an update listener
  exists with `OptionsFlowWithReload` (`config_entries.py:4106-4112`). An unchanged form
  reloads nothing (`:2780-2783`, `changed` stays False).
- So the toggle reloads the whole entry, including the controller's startup reconciliation
  (`controller.py:798-835`), exactly as changing the mode does today (test
  `test_options_change_mode_keeps_running_timer`, `tests/test_config_flow.py:652-671`).
  Intervals (subentries) reload it too, so the counter will be reloaded often and must be
  loss-free across unload/setup (the unload flush above).
- Enabled: the sensor is added by the platform. The counter starts from the stored total (or 0)
  and counts from that moment, never retroactively.
- Disabled: nothing removes the registry entry automatically (`entity_platform.py` has no
  stale-entity cleanup; only `async_clear_config_entry`, `HA/helpers/entity_registry.py:2542`,
  runs, on entry removal). Without action the entity stays as an `unavailable` ghost with
  `restored: true`, re-created at every start (`entity_registry.py:2827-2837`, written on
  unload by `entity.py:1479-1512`). So the sensor platform must remove it: in
  `sensor.async_setup_entry`, when the option is off,
  `registry.async_get_entity_id("sensor", DOMAIN, timer_unique_id(entry_id, KEY_RUNTIME))`
  (`entity_registry.py:1340-1348`) and `registry.async_remove(...)` (`:1728`), which also
  drops the restored state (`cleanup_restored_states`, `:2787-2815`). The removed entry is
  kept as a deleted entry and, when re-enabled, comes back with the same entity_id, id and
  customisations (`async_get_or_create`, `:1596-1630`), so history and statistics stay
  attached to the same `sensor.<target>_runtime`.
- Statistics after disabling or deleting: kept. The recorder reacts to registry events only for
  an entity_id rename (`HA/components/recorder/entity_registry.py:21-37, 54-62`, which also
  moves the statistics to the new id); there is no removal handler, so long-term statistics
  stay and show up as the `no_state` issue in Developer tools > Statistics
  (`sensor/recorder.py:1098-1107`), where the user can clear them. States follow the normal
  purge. Timerify should not clear them (the user's data); the README says where.

Rename, delete, disappearing target
- Target renamed: `_follow_target` updates the `target` option and the entry reloads
  (`__init__.py:90-110`; `tests/test_source_changes.py:24-66`). The test shows the old id's
  state removed (new_state None -> "unavailable" -> run closed) and the new id appearing; the
  store is keyed by the entry id and the sensor's unique id by the entry id, so the file and
  the entity survive (`const.py:123-132`).
- Timer deleted: `async_remove_entry` deletes the timer file (`__init__.py:79-87`; test
  `tests/test_config_flow.py:747-761`); add the runtime file. The registry entries go with the
  entry (`entity_registry.py:2542-2549`). Unload runs before removal, so its flush is then
  deleted.
- Target removed from the registry: entities are left on no device (`__init__.py:90-110`;
  `tests/test_source_changes.py:111-121`). The target state disappears -> "unavailable" -> the
  counter pauses for good; the sensor keeps its value.
- Entry disabled by the user: platforms unload, nothing counts.

## 5. Where it touches the existing code

Config and options flow
- `const.py:17` area: add `CONF_RUNTIME = "runtime"` (doc: absent means off; same convention as
  `CONF_WORKDAY_SENSOR`, `const.py:17-19`, and `default_duration_minutes`, `const.py:141-145`),
  `KEY_RUNTIME = "runtime"` beside `KEY_RUN_FOR/KEY_ENDS_AT/KEY_NEXT_COMMAND` (`const.py:116-118`),
  update the `timer_unique_id` docstring (`:123-132`). Unique id `f"{entry_id}_runtime"`.
- `config_flow.py:279-289` `_after_mode` (loose goes to "runtime" instead of "workday") and
  `_after_duration` (to "runtime"); new `_RUNTIME_STEP` (`BooleanSelector`, e.g.
  `probatio.Required(CONF_RUNTIME, default=False)`, `next_step` -> "workday") beside
  `_DURATION_STEP`/`_WORKDAY_STEP` (`:291-306`); register it in `CONFIG_FLOW` (`:415-425`) and
  `OPTIONS_FLOW` (`:427-432`). The options init step reaches it through `_after_mode`
  (`:409-412`); suggested values are the current options (SchemaCommonFlowHandler); the voice
  entry path is unaffected. The Workday step still skips itself (`:243-259`).
- Entry version: `VERSION = 1` (`config_flow.py:661`), no `async_migrate_entry` anywhere. A new
  optional key whose absence means off needs no migration; 0.5.0 entries load without the
  sensor.
- Translations (`translations/en.json`, `ru.json`; `tests/test_translations.py:49-60` demands
  the same keys and blanks): `config.step.runtime` and `options.step.runtime` (title,
  description, `data.runtime`, `data_description.runtime`), `entity.sensor.runtime.name`
  ("Runtime" in English, its Russian in ru.json), and `icons.json` `entity.sensor.runtime.default`
  (`icons.json:6-14`). Existing structure: `en.json` `config.step.*` lines 3-60, `options`
  62-104, `entity` 258-287.

Entities
- `sensor.py:23-29` `async_setup_entry`: add `RuntimeSensor(hass, entry, counter, store)` when
  `entry.options.get(CONF_RUNTIME)`, else remove the stale registry entry (section 4).
  Class beside `EndsAtSensor`/`NextCommandSensor` (`:32`, `:70`) on `TimerifyEntity`
  (`entity.py:34-75`): `device_class=DURATION`, `state_class=TOTAL_INCREASING`,
  `native_unit_of_measurement=UnitOfTime.MINUTES`, `suggested_display_precision=0`,
  `translation_key="runtime"`, `_handle_controller_update` as no-op, tick and state-change
  subscriptions in `async_added_to_hass`, flush in `async_will_remove_from_hass`.
- New pure `RuntimeCounter` (own module, e.g. `runtime.py`, no HA imports, like `core.py`) and
  `RuntimeStore` (in `store.py` or the same module; same `Store` subclass pattern as `_TimerFile`,
  `store.py:147`).
- `__init__.py:79-87` `async_remove_entry`: also `RuntimeStore(...).async_remove()`.
  `PLATFORMS` (`:28`) already has SENSOR; nothing else changes there.

Card, websocket, voice, docs
- Websocket `TimerInfo` (`websocket.py:75-96`) and `_timer_of_number` (`:151-190`), card
  `card/src/hass.ts:70-90`, `card/src/timer.ts:122-131` (`watchedEntities`): RULINGS.md:1228-1232
  and `docs/followups.md:58-62, 79-83` planned a `runtime` key "with the sensor". The spec does
  not ask the card to show it: §4 makes the card "actions only" and §6.3 lists icon, name,
  remaining time, end time, pop-up actions. Recommendation (D7): do not add it; update the
  followups instead. If added later, it moves in three places together (python TypedDict,
  `hass.ts`, `watchedEntities`) and the entity id would be `str | None`.
- Voice and LLM: §6.4 does not mention runtime; `llm.py`, `voice/`, `sentences/` untouched. The
  sensor is a Timerify entity "not meant to be exposed" (spec line 275-277).
- README: status block `README.md:10-17`, entity table `:79-89` (new row), Setup `:988-1000`
  (new step between 3 and 4), a new "Runtime counter" section (what is counted, minutes,
  statistics, downtime and unavailable not counted, how to clear statistics), "What is not
  here yet" `:1008-1013` (remove the runtime clause), "Verification" `:1015`. Release
  housekeeping: version in `manifest.json:13`, `pyproject.toml:3`, README text "0.5.0".
- Tests infrastructure: `tests/conftest.py:607-640` `setup_target` gets `runtime: bool = False`
  (options built at `:627-633`); `tests/helpers.py` constants (`NUMBER`, `SENSOR`, `NEXT`
  at `:27-31`) get `RUNTIME = "sensor.boiler_runtime"` and a `runtime_storage_key(entry)`
  (`storage_key` at `:387`); `tests/test_unique_ids.py:36-52` pins the exact set of ids of a
  timer without the counter, which must stay unchanged, plus a case with the counter.
  `tests/test_config_flow.py:177-189` (`takes_three_clicks`) changes if the step is a separate
  form (D4); `add_target` helper `:75-88` needs the runtime submit.
- E2E (`scripts/smoke/run.py`, `scripts/e2e/`): optional, not needed for correctness.

## 6. Tests

How time is frozen and moved
- `clock_at_start` freezes `START = 2026-01-05 07:00 UTC` (`tests/conftest.py:478`,
  `tests/helpers.py:26`); `fake_target`/`fake_climate` (`conftest.py:560`, `:576`),
  `FakeTarget.set_state` (`:195`) is the wall switch; `setup_target` (`:607`).
- `advance(hass, freezer, **delta)` = `freezer.tick` + `async_fire_time_changed` +
  `block_till_done` (`helpers.py:233-240`); `advance_to` jumps (`:242-253`); `restart` reloads
  (`:276`); `restart_after` unloads, ticks, sets up (`:282-293`: "nothing fires while down");
  `local(day, "HH:MM")` and `open_sunday` give Jerusalem wall time (`:256`, `:263`);
  `record_writes` counts state changes AND reports (`:368-378`); `state_of` (`:381`).
- `async_fire_time_changed` adds up to 0.5 s to the mocked time and runs every overdue timer
  handle ONCE (`PHCC/common.py:509-564`). It is built to match `async_track_utc_time_change`'s
  50-500 ms jitter, so a tick at second 59 fires when the test moves to 59.5 s or later. A
  multi-minute jump fires the minute listener once; counting writes requires stepping
  (see `test_number_counts_down_once_a_minute`, `tests/test_entities.py:72-96`).
- Real statistics: `recorder_mock` and `quiet_sql_engine` in `tests/test_recorder.py:19-60`;
  helpers `PHCC/components/recorder/common.py:106` (`do_adhoc_statistics`, 5-minute
  aligned) and `:200` (`statistics_during_period`), and the `enable_statistics` fixture
  (`PHCC/plugins.py:1559`, parametrize it True).

Scenarios (user's point of view)
1. A countdown run: "Run for 45" -> target on; the sensor follows once a minute and at the end
   shows 45 and stops. `record_writes` shows one write per tick, none between, none while off.
2. A manual on and off outside Timerify (wall switch, loose and strict): 20 minutes by hand
   counts 20 (strict: R4 started the default countdown and R3 cleared it; both do not matter).
3. A run across midnight, in Jerusalem time: 23:40 to 00:20 gives 20 minutes to each day in the
   compiled long-term statistics (real recorder, hour and day periods), within a second.
4. At most one write a minute: a relay that flaps five times in 30 s, and a command and a
   controller notification between ticks, cause no write before the tick; the final figure is
   published at the next tick after the off.
5. A restart while on (`restart`): continues, value never goes down; `restart_after(minutes=30)`:
   the 30 minutes of downtime are not counted; a cold start from a seeded file with the target
   already on opens a run now.
6. Crash safety: file saved before each published state; with a reload that skips the flush
   (simulate by unloading without the final flush) the restored value is >= the last published one.
7. Options flow: enable from the settings page (runtime step shown in the right place,
   defaults off), sensor appears and counts from then on; disable removes the sensor and its
   registry entry and leaves no unavailable ghost after a restart; enable again gives the same
   entity_id and the old total.
8. A target that is unavailable then unknown then back on: counting pauses and resumes, the
   sensor stays available with its value, nothing is counted for the gap.
9. Two targets (a switch and a climate): independent counters and files; climate heat to cool
   is one run; one unloading does not touch the other.
10. A reload in the middle of a run (an interval added, the target renamed): no loss, no double
    count, no dip, and the entity id and the file stay.
11. Time goes backwards (freezer set to an earlier time): the value never decreases.
12. Removing the timer deletes both files (`test_removing_entry_deletes_stored_state`
    pattern, `tests/test_config_flow.py:747-761`); a 0.5.0 entry without the option loads with
    no runtime sensor and the registry set of `tests/test_unique_ids.py:36-52` unchanged.
13. Metadata: device class duration, state class total_increasing, unit min, no `last_reset`
    attribute (`sensor/__init__.py:468-483`).

## 7. Open decisions

D1. Where the counter lives. Recommend its own store file `timerify.<entry_id>.runtime`, a pure
    counter class and a sensor that owns both. Why: it observes and never decides, so the
    timer stays the single source of truth for whether the target runs, `core.py` stays pure
    and `TimerStore`'s v4 migrations are untouched; RestoreEntity is excluded by the spec's own
    §5.7 reason. Runner-up: a field in the timer's file (v5, one file per timer).
D2. Time not observed (downtime, unavailable, unknown): not counted. Why: a record contains
    only what was seen, which is §5.7's "as if the change had just happened" applied to the
    record; it never overcounts, stays monotonic and does not depend on the timer, pending
    commands or R10's wish (firm promises are not runtime until the target reports on).
    Cost if wrong: under-count bounded by the outage.
D3. Tick and published figure. Recommend `async_track_utc_time_change(second=59)` and exact
    minutes rounded to 2 decimals (display precision 0). Why: the spec's point is correct
    attribution to the hour and the day; this gives sub-second error at every boundary with one
    write a minute, where second 0 and whole minutes give up to 2 minutes. Alternative: second
    0 and whole minutes (integers in the state, simpler tests). Open for the owner: whether
    decimals in the raw state matter more than boundary accuracy.
D4. Placement in the add flow. Recommend a separate "runtime" step after the duration and
    before the Workday sensor, default off, same step in the options flow (§6.2 line 246).
    Why: spec order and one concern per form. Cost: one more Submit for every user; the test
    called "three clicks" becomes four if the menu is counted. If the owner holds "three
    clicks" over the order (anti-goal 1, spec line 52-54), put the checkbox on the first form
    instead.
D5. Re-enabling after disabling keeps the stored total. Why: no false reset in statistics and
    no silent loss; the file is deleted with the timer.
D6. A disabled counter removes its registry entry (not `disabled_by`). Why: avoids an
    `unavailable` ghost at every start; customisations return on re-enable.
D7. No `runtime` key in the websocket answer or the card in phase 6. Why: the spec's card is
    actions only (§4, §6.3); a field nobody reads is already a followup
    (`docs/followups.md:79-83`). Update RULINGS/followups to say so.
D8. No reset action for users in phase 6. Why: not in the spec; statistics tools exist; 0 is
    safe to add later.
D9. Persist with `async_save` before each publish, not `async_delay_save`. Why: keeps stored >=
    published, so a crash cannot create the silent small dip. Cost: one tiny write a minute
    while the target is on or settling.
D10. The sensor never turns unavailable with its target. Why: it is a total, not a reading.
D11. One permanent tick listener per counter, no arm/disarm. Why: fewer states to get wrong;
    the callback returns at once when nothing changed.

## Not verified
- End-to-end behaviour in a real recorder (statistics split at midnight): derived from source
  (`recorder/history/__init__.py:206-209`, `sensor/recorder.py:744-825`, tick jitter) only; the
  test in scenario 3 is what proves it.
- `Store.async_save` durability details (fsync) and `async_on_unload` with coroutines (it
  accepts them: `config_entries.py:1325-1337`, not used here).
- How the frontend sends an unchecked Boolean field; `Required(..., default=False)` covers the
  omitted case.
- Frontend rendering of a 2-decimal state with precision 0.
