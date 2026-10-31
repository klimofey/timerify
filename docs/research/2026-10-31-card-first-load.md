# The card is missing on the first page load the service worker serves (2026-10-31)

Investigated on 2026-10-30 against Home Assistant 2026.10.4 (frontend 20260930.5) in Docker, with
a fresh Playwright Chromium context for every run. The probes were throwaway; nothing from them is
committed. `FE/` below is the frontend source, `POLY/` the npm package
`@webcomponents/scoped-custom-element-registry@0.0.10`, `HA/` the installed Home Assistant core.

## Summary

On the first load that the frontend's service worker serves, a card added with
`add_extra_js_url` can be missing. Its module runs and lists the card for the picker, but the
element is not defined on the registry the frontend uses, and the dashboard shows "Configuration
error" with `Custom element doesn't exist: timerify-card.` until the next load.

It is a known frontend bug, [home-assistant/frontend#53890][issue], fixed by
[frontend PR #54444][pr] (merged 2026-10-28). The fix ships in frontend 20261028.0 and later,
which Home Assistant 2026.11.0b0 and b1 pin. With 2026.11.0b1 the unchanged Timerify bundle was
never lost. On 2026.10.x no fix uses only public APIs. **Owner ruling: document it, keep the
registration (C1), change no card code.** The open question is the minimum Home Assistant version
at 1.0.0 (see `docs/followups.md`).

## Mechanism

- **Two independent imports.** `FE/src/html/index.html.template:146-164` starts the app
  (`core.js`, `app.js`) in one inline script and the extra modules in the next, each with its own
  `import()`. Document order does not decide evaluation order: whichever graph finishes fetching
  first runs first. The order among extra modules is arbitrary too (`HA/components/frontend/
  __init__.py:880-909` passes them as a frozenset).
- **The polyfill drops earlier definitions.** `FE/src/entrypoints/app.ts:1` imports the scoped
  custom element registry polyfill first. `POLY/src/scoped-custom-element-registry.ts:737-741`
  replaces `window.customElements` with a new, empty registry; nothing is copied from the native
  one. On it `get(tag)` returns `undefined` for an element that was defined natively before
  (`:273-276`), and `whenDefined(tag)` never resolves (`:287-298`). A module that runs before the
  polyfill therefore defines its element where nobody looks.
- **The dashboard waits forever.** `FE/src/panels/lovelace/create-element/create-element-base.ts:
  173-201` sees `customElements.get(tag)` falsy, shows the error card and waits on
  `whenDefined`, which cannot resolve. Our module did run: `window.customCards` has the picker
  entry.
- **Why the first load the worker serves.** The frontend registers its service worker on the
  first visit; the worker precaches `frontend_latest/*.js`, claims the page, and the page reloads
  itself on `controllerchange` (`FE/src/util/register-service-worker.ts:19-21`). On that first
  load every script goes through the worker. `app.js` (577 KB) must still be compiled when the
  card module (about 26 KB, no imports) has finished, so the card defines first. On every later
  load `app.js` comes from the renderer's cache in a few milliseconds and wins. The reason the
  cache is not used on the first controlled load is an inference; the per-resource timings are
  what was measured (card lost on 8 of 8 first worker-served loads, 0 of 24 later ones).
- **The worker only decides the race.** Without a worker (`http://127.0.0.1`) 0 of 16 loads lost
  the card. With the worker blocked and `app.js` held back two seconds, 9 of 9 loads lost it. Any
  condition where `app.js` finishes after an extra module loses the card: a cold cache, a
  frontend update that gives `app.js` a new hash, a slow link. The #53890 report measured 9 of 12
  fresh-profile loads lost on a LAN.

## Who is hit

| Card | first worker-served load | other loads | `app.js` held 2 s |
|---|---|---|---|
| Timerify, `add_extra_js_url` | lost 8/8 | 0/28 | lost 9/9 |
| minimal card, `add_extra_js_url`, `define` at top level | lost 8/8 | 0/28 | lost 9/9 |
| minimal card as a Lovelace resource (storage or YAML mode) | 0/8 | 0/28 | 0/9 |
| minimal card as a HACS-style resource `/hacsfiles/...` | 0/8 | 0/28 | 0/9 |

Every module loaded through `add_extra_js_url` or `frontend: extra_module_url` that defines an
element at top level is hit, including cards shipped by other integrations. Lovelace resources
are not: the app loads them after it is running (`FE/src/panels/lovelace/ha-panel-lovelace.ts:
312-316`), so they always run after the polyfill. The polyfill has been there since 2022
(frontend#11776); the bug is not a deliberate change. No 2026 developer documentation mentions
the scoped registry or extra modules.

## Candidate fixes

- **(a) A Lovelace resource instead of `add_extra_js_url`. Rejected.** It avoids the bug in
  both resource modes. But nothing documented lets an integration create one: in storage mode
  only the admin-only command `lovelace/resources/create` or the internal
  `hass.data[LOVELACE_DATA].resources` do, and in YAML mode the collection is read-only. Every
  installation would need a manual step by an administrator, permanently, to avoid a bug that is
  gone in 2026.11. C1 rejected this before the reproduction, and it still does.
- **(b1) Define after the frontend is ready. Rejected.** The module waits for
  `customElements.whenDefined("home-assistant")` and then defines on `window.customElements` as
  it is by then. Reproduced with a patched copy of the real bundle: lost 0 of 6 first loads, 0 of
  18 others, 0 of 4 with `app.js` held back; the pop-up opened as a modal `<dialog>` and closed on
  Escape. But it rests on two undocumented frontend facts (the root element is named
  `home-assistant`, and it is defined only after the polyfill is installed), for a bug upstream has
  fixed. It is the only option that works with `add_extra_js_url` on 2026.10.x if a working first
  load there becomes a hard requirement; it would then be named in `RULINGS.md` and removed when
  the minimum reaches 2026.11.
- **(b2) Define at once, then poll for `home-assistant` and define again. Rejected.** This is the
  UIX pattern and is suggested in #53890. It has the same dependency, plus polling, and a real
  defect: the class ends up defined on both registries, and the shim's attribute patching makes
  `attributeChangedCallback` fire twice per change.
- **(c) Documented guidance. None exists.** `developers.home-assistant.io` documents cards only as
  resources; `add_extra_js_url` appears only in its Python docstring, and the user docs for
  `frontend: extra_module_url` promise no ordering.
- **(d) Require Home Assistant 2026.11. The fix.** With frontend 20261028.1 (Core 2026.11.0b1)
  the extra modules start from `window.__haLoadExtraModules`, after the polyfill. The unchanged
  bundle and the minimal card were lost 0 of 6 first loads, 0 of 18 others, 0 of 4 with `app.js`
  held back. No code change, no internals: C1 stays.

## What follows

- Until the minimum is 2026.11, the defect is a known issue (`docs/followups.md`); plan
  ruling 19 (the README tells users to refresh the browser once after installing or updating)
  covers it.
- Raising the minimum moves together: `hacs.json` `homeassistant`, the
  `pytest-homeassistant-custom-component` pin in `pyproject.toml`, and the image in
  `scripts/harness/compose.yaml`.
- The E2E harness reloads once more after the first load the worker serves
  (`primeServiceWorker` in `card/e2e/fixtures.ts`); `card/e2e/first-load.spec.ts` opens the
  dashboard without that reload and is marked `test.fail`. On a Home Assistant with the fix it
  passes unexpectedly, which is the sign to remove the mark and the extra reload. Waiting for the
  frontend's own reload stays needed, because acting during it races it.

## Sources

- Issue [home-assistant/frontend#53890][issue]: "Custom element registrations from
  extra_module_url / add_extra_js_url are silently lost when the module executes before the
  scoped registry polyfill" (closed as completed 2026-10-28). Related and still open: #52960.
- Fix [home-assistant/frontend#54444][pr]: "Load custom modules after the scoped registry
  polyfill" (merge commit `93efd84`). Release check through the GitHub compare API: 20261028.0
  and 20261028.1 contain it; 20260930.2 to 20260930.5 do not.
- Frontend sources named above, at tag `20260930.5`; the polyfill package at 0.0.10.
- Home Assistant 2026.11.0b0 and b1 pin frontend 20261028.0 and 20261028.1.

[issue]: https://github.com/home-assistant/frontend/issues/53890
[pr]: https://github.com/home-assistant/frontend/pull/54444
