# Follow-ups

Open items that phase 1 did not fix, with where they are as of the end of phase 1. Each line
says what is wrong, why it is not fixed yet, and which phase should take it. Decisions that
were made on purpose are in `RULINGS.md`, not here.

## Phase 2

- **Mixed groups read as off.** A group's state counts as on only when it is `on`, so a group
  of covers or locks that reports `home`/`open` is read as off.
  `custom_components/timerify/domains.py:68-71` (the `group` row). Fix it with the domain
  table work of phase 2.
- **`actual_state` raises for an unsupported domain, but returns "unavailable" for a state that
  is unknown.** An entity of an unsupported domain with no state is quietly "unavailable"; with
  a state it raises `ValueError`. `custom_components/timerify/domains.py:95-103`. The generic
  fallback below makes the raise unreachable, so it settles this too.
- **No generic fallback for domains outside the table.** Spec section 5.4 asks for
  `homeassistant.turn_on`/`turn_off` with state `on` for any other domain; `behaviour_for`
  raises instead, and the config flow offers only the table (see the ruling in `RULINGS.md`).
  `custom_components/timerify/domains.py:83-92`. Either amend 5.4 or add a fallback limited to
  entities with on/off states; phase 2 does the domain table work anyway.
- **A deleted target gives no sign.** `er.async_resolve_entity_id` returns the id even when the
  entity is gone from the registry, so a timer whose target was deleted still loads and drives
  nothing, with no message. `custom_components/timerify/controller.py:81-84`. It needs a
  repairs issue; the owner decides whether it is phase 2 or later.
- **The smoke test covers only the target without a device.** The input_boolean in
  `scripts/smoke/configuration.yaml:8` sits on no device, so the path of a target on a device
  is covered by unit tests only. Extend the smoke test in phase 2.

## Later

- **`type Actual` has no runtime arguments.** `typing.get_args(Actual)` is `()` because the alias
  is a PEP 695 `type`; use `Actual.__value__` if the values are ever enumerated (for example
  to validate stored data). `custom_components/timerify/domains.py:18`. Do it when needed.
- **Device following is one-way for targets without a device.** A target that gains or loses a
  device is followed, but the fallback device made for a target without one can stay behind
  after the target is linked to a device on a restart.
  `custom_components/timerify/__init__.py:49-69` (`_follow_target`).
- **The options keep a stale default duration after strict to loose.** Harmless: loose mode
  ignores it and it is the prefill when the user switches back.
  `custom_components/timerify/config_flow.py:141-180` (`_after_mode`, `OPTIONS_FLOW`).
- **Brand icon missing.** `custom_components/timerify/brand/icon.png` does not exist, so the
  HACS brand check and Home Assistant's integrations page show no logo. Add it in the final
  release phase.

## Tests

- **The slow-call tests start the controller directly.** They use `asyncio.ensure_future` on
  `controller.async_set_minutes` instead of the user's path, a `number.set_value` call in a
  task, as the newer slow-call test in `tests/test_entities.py` does. Instances:
  `tests/test_entities.py:265`, `:267`, `:289`, `:291`, `:474`, `:534` and
  `tests/test_restart.py:270`, `:295`.

## Accepted

- **`services.yaml` hard-codes plus and minus 1440.** The range of `add_time` is written in
  `custom_components/timerify/services.yaml:12-13` as well as in `const.MAX_MINUTES`; the test
  `test_services_are_described_for_the_ui` (`tests/test_services.py:286`) fails when they drift.
