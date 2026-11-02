# Timerify 1.1.0 Part E (Card) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the card issues of 1.1.0. The committed bundle depends only on the card's strings (#43). The server serves the bundle it registered at start-up (#30). The countdown follows the server's clock (#8). Presets longer than the timer's maximum are hidden (#35 in the card). The card can show a Turn off button (#37) and has configurable tap, double tap and hold actions (#36). A "Mushroom style" option reads Mushroom's theme variables (#41). The editor's helper text is translated, and the option labels go upstream (#9). happy-dom is pinned on or after 2026-11-03 (#28).

**Architecture:** The card is a Lit element in `card/src`, bundled by `card/build.mjs` into the committed `custom_components/timerify/frontend/timerify-card.js`, which `custom_components/timerify/card.py` serves and loads on every dashboard. `timerify/timer` (`websocket.py`) tells the card everything it needs of a timer. New card options are parsed in `config.ts`, offered in `editor.ts`, and drawn in `pill.ts`, `round.ts` and `popup.ts`; presses go through `press.ts`; services through `actions.ts`. New words go into `translations/en.json` and `ru.json` under `common`.

**Tech Stack:** TypeScript 6.0.3, Lit 3.3.3, esbuild 0.28.2, vitest 5.0.5 with happy-dom 21.0.3, Playwright 1.64.1 against a real Home Assistant 2026.10.4 in Docker. Python side: Home Assistant 2026.10.4 in `.venv/lib/python3.14/site-packages` (written `sp/` below). The frontend findings are in `.superpowers/research-part-e-frontend.md` (frontend tags 20260930.5 for 2026.10.4 and 20261028.1 for 2026.11.0b2):
- **Actions.** A custom card performs Home Assistant's standard actions by firing `hass-action` (`{config, action: "tap" | "hold" | "double_tap"}`, `bubbles` and `composed`), as the 2023-07-07 developer blog "Action event for custom cards" documents. `handleAction` reads `config.entity` and `config.tap_action`, `hold_action`, `double_tap_action`; a missing key means more-info; "toggle" and "more-info" act on `config.entity`. The card detects the gestures itself.
- **`ui_action` selector:** `{ui_action: {default_action?}}` offers only the standard actions (more-info, toggle, navigate, url, perform-action, assist, none) and writes `{action, ...}`. It cannot offer Timerify's own choices. Built-in card editors put the action fields in an `expandable` group (`type: "expandable"`, `name`, `title`, `schema`).
- **Config form and translation (#9):** `getConfigForm()` gets no `hass`, and `hui-form-editor` passes `localize` only to `computeLabel(schema, localize)` and `computeHelper(schema, localize)`. Option labels of a select cannot be translated by the form in 2026.10.4 or 2026.11.0b2.
- **Mushroom:** Apache-2.0. Loaded when `customElements.get("mushroom-entity-card")` is defined; it may be defined after the card (`customElements.whenDefined`). The `--mush-*` names and defaults are listed in the research file, section 4.
- **HTTP:** `sp/homeassistant/helpers/http.py:126` `HomeAssistantView` (`url`, `name`, `requires_auth`), `hass.http.register_view`; `sp/homeassistant/components/http/static.py:13-15` `CACHE_HEADERS` (a month, public).
- **2026.11.0** is not published (2026-11-02): the docker manifest is unknown and PyPI's latest is 2026.10.4.

**Spec:** `docs/superpowers/specs/2026-11-01-release-1.1.0-design.md`, section "Part E: the card", with "Non-goals" and "Constraints". The owner's decisions: `.superpowers/issue-triage-1.1.0.md`. Issues: `gh issue view N --json title,body` for N in 8 9 28 30 35 36 37 41 43. The base spec and `RULINGS.md` hold where this is silent.

**Starting point:** `part-e-card` at `main` aaf944b, the merge of part D (PR #50): pytest 2967, vitest 241, E2E 42.

## Global Constraints

- Home Assistant `>= 2026.10.4`. No new runtime or dev dependency except the happy-dom pin of Task 9. No change to `manifest.json`.
- Only public Home Assistant APIs, backend and frontend: the documented card API (`setConfig`, `getConfigForm`, `getStubConfig`, `getCardSize`, `getGridOptions`), the `hass-action` event, and the documented `ha-form` schema (selectors, `grid`, `expandable`). Not `visible` conditions, which the developer docs do not describe.
- Card tests are user scenarios: vitest component tests mount the card on the fake `hass` (`card/test/mount.ts`, `fake-hass.ts`) and press it as a person does (`card/e2e/press.ts` style); time moves with vitest fake timers, never a real wait. E2E tests run against the real Home Assistant. Python tests use frozen time. No `asyncio.sleep`, no polling, no test-only branch in product code.
- Strings: every new word of the card is a key under `common` in `translations/en.json` and `ru.json`, named `card_*`, read with `t(hass, key)`. Russian Home Assistant screen names come from `python3 .superpowers/ui-names/ui-term.py "<English name>"`. After a change of `card/src` or `en.json`, run `npm --prefix card run build` and commit the bundle with the task.
- A new card option is optional, with a default that keeps today's card. `parseConfig` checks it; `assertShape` lets the editor show what it can.
- Docs: a user-visible change updates `docs/en/card.md` and `docs/ru/card.md` (or the page it belongs to) in the same commit, with the same `##`/`###` headings, CLAUDE.md "User documentation" style.
- RULINGS: Task 1 adds `### Card` under `## Release 1.1.0`, after `### Voice`. Later tasks append to it in the existing style (bold decision, "Why:", "Cost if wrong:", tests).
- Every task ends with these passing: `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `npm --prefix card run build:check`, `npm --prefix card run typecheck`, `npm --prefix card test`. A task that changes what E2E covers also runs `npm --prefix card run e2e` (after comparing `date -u +%s` with `docker run --rm alpine date -u +%s`).
- English only outside the allowed Cyrillic files. Commit messages are a plain sentence-case subject, no attribution lines. Never `--no-verify`. `git add` only the task's files.
- Nothing is opened, commented or labelled in any `home-assistant/*` repository. Docker: start, stop or remove only the containers a test or task names.
- The PR body closes with one keyword per issue: "Closes #8. Closes #30. Closes #35. Closes #36. Closes #37. Closes #41. Closes #43." (and "Closes #28." only if Task 9 is in this PR). #9 stays open, labelled `upstream`.

## Review Focus

1. **A double tap set, and a single tap.** With a double tap action set, a single tap still does the tap action, once, after the double-tap window; a double tap does only the double tap action, never the tap one as well. Test: Task 5, `a single tap still opens the pop-up when a double tap is set`.
2. **The keyboard.** Enter and Space on the card do the tap action at once, whatever double tap and hold are set to; a keyboard user is never stuck waiting. Test: Task 5, `Enter does the tap action at once with a double tap set`.
3. **A browser clock that is wrong by minutes.** The countdown and "until 18:30" follow the server; a card whose lookup failed shows the browser's clock as before. Test: Task 3, `the countdown follows the server when the browser is 5 minutes fast`.
4. **A HACS update before the restart.** The browser loads the bundle the running server registered, at the URL it was told; the new file on disk is not served until the restart. Test: Task 2, `test_the_card_served_is_the_one_registered_until_a_restart`.
5. **Every preset above the maximum.** A timer whose maximum is 10 minutes, with the default presets, shows no preset buttons and the pop-up still works (plus, minus, stop). Test: Task 4, `the pop-up shows no presets when each is above the maximum`.

---

### Task 1: The bundle depends only on the card's strings (#43)

**Files:**
- Modify: `card/src/strings.ts`, `card/build.mjs`, `card/test/strings.test.ts`, `custom_components/timerify/frontend/timerify-card.js`, `RULINGS.md`, `docs/followups.md`.

**Interfaces:**
- Produces: the bundle's bytes are a function of `card/src`, the pinned packages and `common` of `en.json` only. `build.mjs --check` behaves as today.

- [ ] **Step 1: Find the cause.** Rebuild after changing one string outside `common` in a scratch copy of `en.json` and diff the two bundles (formatted). Record in the report which identifiers move and why (esbuild bundles the whole JSON module, or orders by it).
- [ ] **Step 2: Write the failing test** `card/test/bundle.test.ts`: `the bundle does not change when a string outside common changes`. It builds with esbuild twice through the build script's own options (export the options from `build.mjs` as `bundleOptions(entryPoint)`, or a `buildBundle(overrides)` function), once with the real `en.json` and once with a copy that differs outside `common` (an esbuild plugin or alias that points the import at the copy), and asserts equal bytes. It also asserts the bundle does change when a `common` string changes.
- [ ] **Step 3: Run** `npm --prefix card test -- bundle`. Expected: the first assertion FAILS.
- [ ] **Step 4: Implement** so that only `common` reaches the bundle. Prefer an esbuild plugin in `build.mjs` that resolves the `en.json` import to a module holding `common` alone, over a generated file in the repo; `strings.ts` keeps its typed `common` import.
- [ ] **Step 5: Run** the test, then `npm --prefix card run build` and `build:check`, `typecheck`, `test`. Expected: PASS.
- [ ] **Step 6: RULINGS.** Add `### Card` under `## Release 1.1.0` with the entry for #43. Remove #43 from `docs/followups.md`.
- [ ] **Step 7: Commit:** `git commit -m "Build the card from the common strings of en.json alone"`.

### Task 2: The server serves the bundle it registered (#30)

**Files:**
- Modify: `custom_components/timerify/card.py`, `tests/test_card_registration.py`, `RULINGS.md`, `docs/followups.md`.

**Interfaces:**
- Produces: `card.CardView(HomeAssistantView)` with `url = CARD_URL`, `name = "timerify:card"`, `requires_auth = False`, holding the bytes read once at registration and answering them with `Content-Type: text/javascript; charset=utf-8` and `CACHE_HEADERS`. `async_register_card(hass)` reads the file once in the executor, registers the view and the module URL from those bytes. `card_module_url(bundle)` is unchanged.

- [ ] **Step 1: Write the failing tests** in `tests/test_card_registration.py`:

```python
async def test_the_card_served_is_the_one_registered_until_a_restart(...)   # Review Focus 4
    # CARD_FILE pointed (monkeypatch) at a copy of the bundle in tmp_path, the one input of the
    # registration; set up Timerify; overwrite the copy with other bytes, as HACS does; GET the
    # module URL the frontend was told: the body is the first bytes, and their sha256 prefix is
    # the ?v= key

async def test_the_card_is_served_with_a_month_of_cache_to_anyone(...)
    # unauthenticated GET: 200, Cache-Control public max-age=2678400, JavaScript content type
```

  The existing `test_card_is_served_to_anyone` and `test_dashboards_load_the_card_once` keep passing unedited.
- [ ] **Step 2: Run** `uv run pytest tests/test_card_registration.py -v`. Expected: the first FAILS.
- [ ] **Step 3: Implement** with `HomeAssistantView` and `hass.http.register_view` (check both in `sp/`); drop the static path. A reload of a timer still registers nothing twice.
- [ ] **Step 4: RULINGS** entry for #30 (cost if wrong: a HACS update shows its card only after the restart, which HACS asks for anyway). Remove #30 from `docs/followups.md`.
- [ ] **Step 5: Run** the gate's Python checks and `npm --prefix card run e2e` (the served path changed). Expected: PASS.
- [ ] **Step 6: Commit:** `git commit -m "Serve the card bundle that was registered at start-up until the restart"`.

### Task 3: The countdown follows the server's clock (#8)

**Files:**
- Modify: `custom_components/timerify/websocket.py`, `tests/test_websocket.py`, `card/src/hass.ts`, `card/src/timer.ts`, `card/src/timerify-card.ts`, `card/src/popup.ts`, `card/src/countdown.ts`, the card tests that build a `TimerInfo` (`card/test/fake-hass.ts`), `card/test/timer.test.ts`, `card/test/card.test.ts`, `card/e2e/ws.spec.ts`, `docs/en|ru/card.md`, `RULINGS.md`, `docs/followups.md`.

**Interfaces:**
- Produces:
  - `TimerInfo.server_time: str`, the server's `dt_util.utcnow().isoformat()` when it answers, in `websocket.py` and `hass.ts`.
  - `TimerLookup` `found` gains `clockOffset: number`: milliseconds to add to `Date.now()` to get the server's time, measured at the lookup as `Date.parse(server_time) - (sent + received) / 2`.
  - `timer.ts` `serverNow(lookup: TimerLookup): number`: `Date.now()` plus the offset of a found lookup, else `Date.now()`. Every "now" of the card, the pop-up and the countdown controller reads it.

- [ ] **Step 1: Write the failing tests.** Python: `test_the_answer_says_the_server_time` (frozen time; `server_time` equals it). vitest, with fake timers and a fake `hass` whose `callWS` answers a `server_time` 5 minutes behind the browser:

```ts
it("the countdown follows the server when the browser is 5 minutes fast")   // Review Focus 3
// Ends at = server now + 10 min: the card shows 10:00 left, not 5:00; the countdown keeps ticking
it("a lookup that failed counts by the browser's clock")
```

  E2E `ws.spec.ts`: the answer has `server_time` within a few seconds of the browser's clock.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement.** The offset is measured at every lookup; a new lookup replaces it.
- [ ] **Step 4: Docs** (en, ru) `card.md`, "What the card does": the countdown is counted by Home Assistant's clock, so a browser clock that is off does not change it. RULINGS entry for #8. Remove #8 from `docs/followups.md`.
- [ ] **Step 5: Run** the task checks, `npm --prefix card run build`, and E2E. Expected: PASS.
- [ ] **Step 6: Commit:** `git commit -m "Count the card's countdown by the server's clock"`.

### Task 4: Presets above the maximum are hidden (#35 in the card)

**Files:**
- Modify: `card/src/popup.ts`, `card/test/popup.test.ts`, `docs/en|ru/card.md`, `RULINGS.md`.

**Interfaces:**
- Produces: `popup.ts` offers `config.presets.filter((minutes) => minutes <= max)`, where `max` is the `max` attribute of the "Run for" number's state, and all presets when it has none.

- [ ] **Step 1: Write the failing tests** in `card/test/popup.test.ts`:

```ts
it("the pop-up hides a preset longer than the timer's maximum")
// number max 60, presets 15 30 45 60 120: buttons 15, 30, 45, 60 min
it("the pop-up shows no presets when each is above the maximum")   // Review Focus 5
// max 10: no preset button; +5, -5 and Stop are there and work
it("the presets follow a maximum that changes")
```

- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement.** **Step 4: Docs** (en, ru) `card.md`, "The pop-up": a preset longer than the timer's maximum is not shown. RULINGS entry.
- [ ] **Step 5: Run** the task checks and `npm --prefix card run build`. **Step 6: Commit:** `git commit -m "Hide the presets of the card that are longer than the timer's maximum"`.

### Task 5: Tap, double tap and hold actions (#36)

**Files:**
- Modify: `card/src/config.ts`, `card/src/press.ts`, `card/src/actions.ts`, `card/src/timerify-card.ts`, `card/src/editor.ts`, `card/test/config.test.ts`, `card/test/card.test.ts` (or a new `card/test/actions-press.test.ts`), `card/test/editor.test.ts`, `card/e2e/round.spec.ts`, `card/e2e/pill.spec.ts`, `card/e2e/editor.spec.ts`, `translations/en.json`, `translations/ru.json`, `docs/en|ru/card.md`, `RULINGS.md`.

**Interfaces:**
- Produces:
  - `config.ts`: `export type PressChoice = "popup" | "run" | "stop" | "run_or_stop" | "action" | "none"`. `CardConfig` gains `tap: PressChoice`, `double_tap: PressChoice`, `hold: PressChoice` and, kept as given, `tap_action?`, `double_tap_action?`, `hold_action?` (Home Assistant action objects). Defaults: `tap: "popup"`; `hold: "run_or_stop"` on the round layout and `"none"` on the pill; `double_tap: "none"`. An unknown choice is a `ConfigError("card_error_press")`.
  - `actions.ts`: `stop(hass, runFor)` calls `timerify.stop`; `run_or_stop` is today's round hold (stop when counting or open, a bare run when idle, nothing when unavailable).
  - `press.ts`: `PressActions` gains `doubleTap?()`. With a double tap, a click waits `DOUBLE_TAP_MS = 250` for a second click; a second click inside the window is the double tap only. Enter and Space act as a tap at once. A hold exists only when `hold` is not `"none"`.
  - `timerify-card.ts`: `"action"` fires `hass-action` with `config: { entity: <the target's entity id>, tap_action, double_tap_action, hold_action }` and `action: "tap" | "double_tap" | "hold"`; before the lookup has found the timer, `"action"` does nothing.
  - `editor.ts`: an `expandable` group "Interactions" with three selects (`tap`, `double_tap`, `hold`; options: Open the pop-up, Run for the default duration, Stop, Start or stop, Home Assistant action, Nothing) and three `ui_action` fields (`tap_action`, `double_tap_action`, `hold_action`) whose helper says they are used when the press is set to "Home Assistant action".

- [ ] **Step 1: Write the failing tests** (vitest, fake timers, pressing as a person does):

```ts
it("a tap opens the pop-up by default on both layouts")
it("a long press on the round tile starts or stops as before; on the pill it does nothing")
it("a single tap still opens the pop-up when a double tap is set")   // Review Focus 1
it("a double tap does the double tap action alone")
it("Enter does the tap action at once with a double tap set")   // Review Focus 2
it("a press set to a Home Assistant action fires hass-action for the target")
// event.detail == { config: { entity: "switch.boiler", tap_action: {action: "more-info"} }, action: "tap" }
it("a press set to stop calls timerify.stop on the Run for number")
it("an unknown press choice is refused with its message")
```

  E2E: on the round tile, `hold: action` with `hold_action: {action: "more-info"}` opens Home Assistant's more-info dialog of the target; the editor shows the Interactions group and writes `tap: run`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** New strings under `common`: `card_editor_interactions`, `card_editor_tap`, `card_editor_double_tap`, `card_editor_hold`, `card_editor_press_popup`, `card_editor_press_run`, `card_editor_press_stop`, `card_editor_press_run_or_stop`, `card_editor_press_action`, `card_editor_press_none`, `card_editor_action_helper`, `card_error_press`, in en and ru.
- [ ] **Step 4: Docs** (en, ru) `card.md`: "The long press of the round tile" becomes "Presses" (`##`), with the defaults, the six choices, the Home Assistant actions acting on the target, and YAML in a code block. RULINGS entry: the two-level choice and why (the `ui_action` selector cannot offer Timerify's choices).
- [ ] **Step 5: Run** the task checks, `npm --prefix card run build`, and E2E. **Step 6: Commit:** `git commit -m "Let the card's tap, double tap and hold be chosen"`.

### Task 6: A Turn off button on the card (#37, the card option)

**Files:**
- Modify: `card/src/config.ts`, `card/src/pill.ts`, `card/src/round.ts`, `card/src/popup.ts`, `card/src/editor.ts`, `card/test/pill.test.ts`, `card/test/round.test.ts`, `card/test/popup.test.ts`, `card/test/editor.test.ts`, `card/e2e/pill.spec.ts`, `translations/en.json`, `translations/ru.json`, `docs/en|ru/card.md`, `RULINGS.md`.

**Interfaces:**
- Consumes: `stop(hass, runFor)` (Task 5).
- Produces: `CardConfig.show_turn_off: boolean` (default `false`; editor field: a boolean selector "Show a Turn off button"). While the target is on (the view's state is `counting` or `open`), the pill shows a "Turn off" button beside its body (before the chip) and the round tile one below its body; pressing it calls `stop`. The pop-up's Stop button, which is shown already, also calls `stop` (one command path, for every card).

- [ ] **Step 1: Write the failing tests:**

```ts
it("the pill shows Turn off while the boiler runs, with or without a countdown")
it("Turn off is hidden while the boiler is off, and without the option")
it("Turn off calls timerify.stop and does not open the pop-up")
it("the round tile shows Turn off below its body while the boiler runs")
it("the pop-up's Stop calls timerify.stop")
```

  E2E `pill.spec.ts`: with `show_turn_off: true`, a running Loose boiler with no countdown is turned off by the button.
- [ ] **Step 2: Run.** **Step 3: Implement.** Strings `card_turn_off`, `card_editor_show_turn_off` (en, ru; the Russian word for Turn off from `ui-term.py "Turn off"`).
- [ ] **Step 4: Docs** (en, ru) `card.md`: the option, when the button shows, and that it is the Stop command (it ends the countdown and turns the device off). RULINGS: the pop-up keeps its Stop button, which is the same command, so the option adds the button to the card itself.
- [ ] **Step 5: Run** the task checks, the build and E2E. **Step 6: Commit:** `git commit -m "Offer a Turn off button on the card while the device is on"`.

### Task 7: Mushroom style (#41)

**Files:**
- Modify: `card/src/config.ts`, `card/src/layout.ts`, `card/src/pill.ts`, `card/src/round.ts`, `card/src/timerify-card.ts`, `card/src/editor.ts`, `card/test/card.test.ts`, `card/test/editor.test.ts`, `translations/en.json`, `translations/ru.json`, `docs/en|ru/card.md`, `RULINGS.md`.

**Interfaces:**
- Produces: `CardConfig.mushroom: boolean` (default `false`; editor: a boolean selector "Mushroom style"). The card host carries `data-mushroom` while the option is on and `customElements.get("mushroom-entity-card")` is defined; it re-renders when `customElements.whenDefined("mushroom-entity-card")` resolves, and a card that waits for it does not hold `updateComplete`. Under `:host([data-mushroom])` the card's spacing, icon size, control height, radii, chip size and fonts read `var(--mush-<name>, <Mushroom's default>)`, names and defaults from the research file (section 4). No Mushroom code is copied. The editor's helper of the field says Mushroom was not found while it is not defined (`computeHelper` with `localize`).

- [ ] **Step 1: Write the failing tests:**

```ts
it("Mushroom style is off by default and the card looks as before")   // no data-mushroom
it("Mushroom style is used once Mushroom's cards are defined")   // define a stub element named mushroom-entity-card after mounting: data-mushroom appears
it("Mushroom style without Mushroom keeps the Home Assistant look")
it("the editor says Mushroom was not found")
it("a theme's --mush-spacing changes the card in Mushroom style")   // computed style of the body
```

- [ ] **Step 2: Run.** **Step 3: Implement.** Strings `card_editor_mushroom`, `card_editor_mushroom_missing` (en, ru).
- [ ] **Step 4: Docs** (en, ru) `card.md`: the option, what it needs (Mushroom installed), and that a theme that sets Mushroom's variables changes the card too. RULINGS entry with the license note (names only, Apache-2.0).
- [ ] **Step 5: Run** the task checks and the build. Run `npm --prefix card run screenshots` and add one Mushroom-style picture per layout to `docs/screenshots/` (names `card-pill-mushroom.png`, `card-round-mushroom.png`), referenced from both card pages. **Step 6: Commit:** `git commit -m "Offer a Mushroom style that reads Mushroom's theme variables"`.

### Task 8: The editor's helper text in the user's language; option labels upstream (#9)

**Files:**
- Modify: `card/src/editor.ts`, `card/test/editor.test.ts`, `docs/en|ru/card.md` ("Languages"), `RULINGS.md`, `docs/followups.md`.

**Interfaces:**
- Produces: `computeHelper(field, localize)` builds every helper with the `localize` it is given (the presets helper lists the default presets in that language). Option labels still come from `lastLoaded()`.

- [ ] **Step 1: Write the failing test** `the presets helper is in the editor's language before any card has loaded` (localize of ru, no card loaded: the helper is the Russian one).
- [ ] **Step 2: Run.** **Step 3: Implement.** **Step 4: Docs** (en, ru) "Languages": before any card has loaded in the session, the names of the layouts and presets in the editor can be in English. RULINGS entry; #9's line in `docs/followups.md` says what is left.
- [ ] **Step 5: Run** the task checks and the build. **Step 6: Commit:** `git commit -m "Translate the card editor's helper text with the editor's language"`.
- [ ] **Step 7 (controller):** label #9 `upstream` and comment in English: what was translated, what cannot be (option labels: `getConfigForm()` gets no `hass` and `hui-form-editor` passes `localize` to `computeLabel` and `computeHelper` only, in 2026.10.4 and 2026.11.0b2), and that a request to the frontend waits for the owner.

### Task 9: Pin happy-dom 21.0.4 (#28), on or after 2026-11-03

**Files:** `card/package.json`, `card/package-lock.json`.

- [ ] **Step 1:** Only on or after 2026-11-03 (`date +%F`). If part E is ready to merge before that date, this task becomes a small PR of its own on that date.
- [ ] **Step 2:** `npm --prefix card install --save-exact --save-dev happy-dom@21.0.4`; check `npm --prefix card audit` no longer lists GHSA-834v-8h66-3h79.
- [ ] **Step 3: Run** `npm --prefix card ci`, `typecheck`, `test`, `build:check`. Expected: PASS.
- [ ] **Step 4: Commit:** `git commit -m "Pin happy-dom 21.0.4"`, closing #28.

### Task 10: The full gate

- [ ] **Step 1:** Run the full gate on the final tree: Python checks, hassfest (`docker run --rm --platform linux/amd64 -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest`), `npm --prefix card ci`, `build:check`, `typecheck`, `test`, the clock comparison and `e2e`. And `git grep -nIP '\p{Cyrillic}' -- ':!README.ru.md' ':!docs/ru' ':!custom_components/timerify/translations' ':!custom_components/timerify/sentences' ':!tests/fixtures/ru'` prints nothing.
- [ ] **Step 2: Report** the counts against pytest 2967, vitest 241, E2E 42.
