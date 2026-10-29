# Follow-ups

Open items that the finished phases did not fix, with where they are as of the end of phase 2.
Each line says what is wrong, why it is not fixed yet, and which phase should take it.
Decisions that were made on purpose are in `RULINGS.md`, not here.

## Phase 3

- **`apply_if_on=False` is not stored, so it is lost when the target is unavailable at the time
  of the command.** A command that must not push its settings onto a running target (a schedule
  interval that starts while the target runs, spec §5.4 and S1) records them as owed only when
  its own turn-on is the reason. A target that is unavailable when the command arrives and
  comes back already `on` receives the owed settings anyway, because the core does not remember
  how they were asked for and the store keeps no such flag. Schedules are the first caller, so
  the phase-3 plan needs a persisted marker on the owed settings (or a ruling that this is
  acceptable). `custom_components/timerify/core.py:223-238` (`set_duration`) and `:258-279`
  (`run_open`), the `apply_if_on` argument, and `custom_components/timerify/store.py:35-48`
  (`_payload`).

## Later

- **A deleted target gives no sign.** `er.async_resolve_entity_id` returns the id even when the
  entity is gone from the registry, so a timer whose target was deleted still loads and drives
  nothing, with no message. `custom_components/timerify/controller.py:104-108`. It needs a
  repairs issue; the spec is silent and no spec-defined behaviour changes, so it waits for a
  later phase.
- **A device that answers each refused call with `unknown` and then its old state is re-sent
  without end.** Each cycle is a real state change, which resets the allowance of automatic
  re-sends by design. Not a regression (phase 1 before the cap behaved the same). A per-wish
  total limit would close it. `custom_components/timerify/core.py:344-347` (the reset in
  `observe`) and `:547-560` (`_resend`).
- **The give-up warning is logged once per allowance, not once per wish.** A refusing target
  that keeps dropping off Wi-Fi logs one warning per reconnect. Bounded by the reconnects.
  `custom_components/timerify/controller.py:410-429` (`_log_gave_up`) and
  `custom_components/timerify/core.py:154-178` (`_Allowance`).
- **`type Actual` has no runtime arguments.** `typing.get_args(Actual)` is `()` because the alias
  is a PEP 695 `type`; use `Actual.__value__` if the values are ever enumerated (for example
  to validate stored data). `custom_components/timerify/domains.py:55`. Do it when needed.
- **Device following is one-way for targets without a device.** A target that gains or loses a
  device is followed, but the fallback device made for a target without one can stay behind
  after the target is linked to a device on a restart.
  `custom_components/timerify/__init__.py:49-68` (`_follow_target`).
- **The options keep a stale default duration after strict to loose.** Harmless: loose mode
  ignores it and it is the prefill when the user switches back.
  `custom_components/timerify/config_flow.py:190-221` (`_after_mode`, `OPTIONS_FLOW`).
- **Brand icon missing.** `custom_components/timerify/brand/icon.png` does not exist, so the
  HACS brand check and Home Assistant's integrations page show no logo. Add it in the final
  release phase.

## Tests

- **The slow-call tests start the controller directly.** They use `asyncio.ensure_future` on
  `controller.async_set_minutes` or `async_run` instead of the user's path, a `number.set_value`
  or `timerify.run` call in a task, as the newer slow-call test in `tests/test_entities.py:288` does.
  Instances: `tests/test_entities.py:251`, `:253`, `:275`, `:277`, `:460`, `:551`,
  `tests/test_restart.py:298`, `:368`, `:393` and `tests/test_settings.py:268`.

## Accepted

- **`services.yaml` hard-codes the limits.** The ranges of `add_time` (plus and minus 1440,
  `custom_components/timerify/services.yaml:12-13`), of the minutes of `run` (`:27-28`) and of
  `add_command` (`:127-128`) and of its delay (1 to 10080, `:114-115`) are written there as well
  as in `const.MAX_MINUTES` and `const.MAX_DELAY_MINUTES`; the test
  `test_services_are_described_for_the_ui` (`tests/test_services.py:371`) fails when they drift.
