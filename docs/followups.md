# Follow-ups

Open items that the finished phases did not fix, with where they are as of the end of phase 3.
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
  repository is built as a product. `custom_components/timerify/__init__.py:56-76`
  (`_follow_target`, the pattern), `custom_components/timerify/controller.py:159` (the
  option) and `:540-552` (`_follow_workday_sensor`, which subscribes to the id).

## Later

- **A deleted target gives no sign.** `er.async_resolve_entity_id` returns the id even when the
  entity is gone from the registry, so a timer whose target was deleted still loads and drives
  nothing, with no message. `custom_components/timerify/controller.py:136-140`. It needs a
  repairs issue; the spec is silent and no spec-defined behaviour changes, so it waits for a
  later phase.
- **A device that answers each refused call with `unknown` and then its old state is re-sent
  without end.** Each cycle is a real state change, which resets the allowance of automatic
  re-sends by design. Not a regression (phase 1 before the cap behaved the same). A per-wish
  total limit would close it. The same holds for a device that answers each correction of
  a contradicting report of its own call (the entry "A report of our own call that
  contradicts the timer" in `RULINGS.md`) with the opposite state, each time as an answer
  to our call: every change is answered once. `custom_components/timerify/core.py:514-517`
  (the reset in `observe`) and `:814-827` (`_resend`).
- **The give-up warning is logged once per allowance, not once per wish.** A refusing target
  that keeps dropping off Wi-Fi logs one warning per reconnect. Bounded by the reconnects.
  `custom_components/timerify/controller.py:719-738` (`_log_gave_up`) and
  `custom_components/timerify/core.py:250-275` (`_Allowance`).
- **`type Actual` has no runtime arguments.** `typing.get_args(Actual)` is `()` because the alias
  is a PEP 695 `type`; use `Actual.__value__` if the values are ever enumerated (for example
  to validate stored data). `custom_components/timerify/domains.py:55`. Do it when needed.
- **Device following is one-way for targets without a device.** A target that gains or loses a
  device is followed, but the fallback device made for a target without one can stay behind
  after the target is linked to a device on a restart.
  `custom_components/timerify/__init__.py:56-76` (`_follow_target`).
- **The options keep a stale default duration after strict to loose.** Harmless: loose mode
  ignores it and it is the prefill when the user switches back.
  `custom_components/timerify/config_flow.py:261-263` (`_after_mode`) and `:299-306`
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
  be a special case, so it waits for the policy. `custom_components/timerify/controller.py:193-201`
  (`async_start`), `:306-334` (`async_set_interval_enabled`), `:346-355` (`_command`) and
  `:506-538` (`_handle_started`), and `custom_components/timerify/core.py:154-165`
  (`next_wakeup`).
- **The R10 lines are not written by the folds of start-up and of a report of the target.**
  `_fold_due` (the alarm, the refresh of the windows and the switching off of an interval)
  says what came due while the target is unavailable: the countdown that ended, the command
  that came due, the window that started. `_handle_started` and `_handle_state_change` fold
  through `_execute_fold` alone and say nothing, so a window or command that came due
  during downtime, found at start-up with the target unavailable, is applied when it is
  back without a line in the log. The phase-2 lines have the same gap. It changes no
  behaviour. `custom_components/timerify/controller.py:575-583` (`_fold_due`), `:602-647`
  (`_log_due_while_unavailable`), `:506-538` (`_handle_started`) and `:557-567`
  (`_handle_state_change`).
- **A time zone changed in YAML is not noticed.** Changing the zone in the settings fires
  `EVENT_CORE_CONFIG_UPDATE`, which the controller listens to, but `configuration.yaml`
  applied with "Reload core configuration" sets the zone through `async_set_time_zone`
  (`async_process_ha_core_config`) without that event. The windows keep the old zone until
  a window ends, the Workday sensor reports or the timer reloads. It needs a signal that
  Home Assistant does not fire for this path; look for one before working around it.
  `custom_components/timerify/controller.py:500-504` (`_handle_core_config_update`) and
  `:506-538` (where it is subscribed).
- **An old generated title stays in the old language.** An edit renames an interval only if
  its title is still the one generated from its old data in the current language; after the
  house language changes the old title no longer matches and is kept as if the user had
  chosen it. A stored mark that the title was generated would end it. Subentry titles are
  plain strings today. `custom_components/timerify/config_flow.py:395-396`.
- **Settings that the target no longer supports are dropped silently on the next edit.** The
  form offers only what the target can do now, so a stored setting that is no longer
  offered is missing from the submitted form and from the saved interval, with no message.
  `custom_components/timerify/config_flow.py:448-458` (`_interval_schema`, the section) and
  `:460-502` (`_interval_from`).
- **A store file that contradicts itself fails the timer, and the interface cannot repair
  it.** `_validated` refuses a file that no timer could have written (two windows of one
  interval, a window that is suppressed but has not started, and so on), which means a
  defect, and the entry stays failed with a reason in words (`stored_timer_invalid`). The
  only way out is to delete the timer and add it again, which loses its commands and the
  flags of its intervals. A repairs issue with a "reset the stored timer" fix would do. `custom_components/timerify/store.py:60-84`
  (`_validated`) and `:164-188` (`async_load`).
- **A pending command keeps the settings it was made with.** The settings of an interval's
  window are checked again when the window is worked out, and the ones the target no longer
  takes are left out (`RULINGS.md`), but a command is checked only when it is made.
  Made days ahead for an AC whose integration then renames a mode, it fails on that mode
  when it comes due, and the log says so at every attempt. The fix is the same filter
  where the calls are made (`_execute`), which covers the owed settings of every origin;
  it is not a phase 3 regression, so it waits.
  `custom_components/timerify/controller.py:259` (`async_add_command`, the check) and
  `:724-737` (`_execute`, where the calls are made).
- **Brand icon missing.** `custom_components/timerify/brand/icon.png` does not exist, so the
  HACS brand check and Home Assistant's integrations page show no logo. Add it in the final
  release phase.

## Tests

- **The slow-call tests start the controller directly.** They use `asyncio.ensure_future` on
  `controller.async_set_minutes` or `async_run` instead of the user's path, a `number.set_value`
  or `timerify.run` call in a task, as the newer slow-call test in `tests/test_entities.py:287` does.
  Instances: `tests/test_entities.py:250`, `:252`, `:274`, `:276`, `:459`, `:571`,
  `tests/test_restart.py:505`, `:686`, `:711` and `tests/test_settings.py:316`.

## Accepted

- **`services.yaml` hard-codes the limits.** The ranges of `add_time` (plus and minus 1440,
  `custom_components/timerify/services.yaml:12-13`), of the minutes of `run` (`:27-28`) and of
  `add_command` (`:127-128`) and of its delay (1 to 10080, `:114-115`) are written there as well
  as in `const.MAX_MINUTES` and `const.MAX_DELAY_MINUTES`; the test
  `test_services_are_described_for_the_ui` (`tests/test_services.py:401`) fails when they drift.
