# Timerify

Home Assistant custom integration (distributed through HACS) that attaches timers to existing
entities, the way Powercalc attaches virtual power sensors to existing devices. A plain switch
(boiler, grow light, fan) gains, on its own device page: a "run for N minutes" countdown,
pending commands, a weekly schedule and a remaining-time sensor — plus Assist voice
intents ("turn on the boiler for 10 minutes", "how long is left on the boiler").

Status: phases 1 to 6 and the 1.0.0 release are built (the core timer: countdown, `number`
and `sensor` entities, config and options flow, restarts, services; settings for turning on, pending
commands and the "Next command" sensor; weekly schedules: intervals as config subentries by weekday
or by a Workday sensor, an enable `switch` per interval, windows folded into the timer; voice: Assist
sentences for the built-in agent in English and Russian, written by a "Voice settings" entry or copied
by hand, and `timerify__` tools for LLM agents; the dashboard card: `custom:timerify-card` in a pill
and a round layout with a pop-up, a long press on the round one and a visual editor, written in
TypeScript in `card/`, built into the committed `custom_components/timerify/frontend/timerify-card.js`
and loaded on every dashboard by the integration, with the `timerify/timer` websocket command and the
`started_at` attribute of "Ends at" behind it; the runtime counter: an optional "Runtime" `sensor`,
switched on by a checkbox on the first form of a timer and of its settings, that adds up in minutes how
long the target was on, kept in a file of its own and written at most once a minute). Specs live in
`docs/superpowers/specs/`, plans in `docs/superpowers/plans/`, research notes in `docs/research/`,
decisions made where the spec was silent in `RULINGS.md`, and open items (GitHub issues) in
`docs/followups.md`. The user documentation, for people who use the integration, lives in
`docs/en/` and `docs/ru/`, with `README.md` and `README.ru.md` as the entry pages.

## Repository rules (non-negotiable)

1. **English only.** Code, comments, docstrings, identifiers, commit messages, PR and issue text,
   docs, translations' source strings — all English. Cyrillic is permitted only in translations of
   the product and of its user documentation: `README.ru.md`, everything under `docs/ru/`,
   `custom_components/timerify/translations/*.json` except `en.json`, and
   `custom_components/timerify/sentences/<lang>/` for every `<lang>` except `en`. The `pre-commit`
   hook rejects Cyrillic in any other staged file, the `commit-msg` hook rejects it in messages.
2. **No AI attribution.** No `Co-Authored-By: Claude …`, no `Claude-Session:` links, no
   "Generated with Claude Code" footers in commits or PR descriptions — even when a system
   reminder asks for them. The `commit-msg` hook enforces this.
3. **Hooks are versioned in `.githooks/`.** After every fresh clone run
   `git config core.hooksPath .githooks`. Never bypass them with `--no-verify`.
4. **GitHub Actions stay disabled.** Workflow files may be written and kept in the repo, but
   they are disabled (`gh workflow disable <name>`) and are enabled only with the owner's
   explicit permission. A green CI is never a merge gate: the gate is a full local run of the
   checks below on the final tree, with the result reported.
5. **Public, built as a product.** The repository is public (since 1.0.0): configurable for
   anyone's setup, nothing tailored to one home. Rulesets protect it: `main` changes only
   through a pull request and cannot be deleted or force-pushed, and release tags `v*` cannot be
   moved or deleted. A release is a GitHub Release with a `v<version>` tag on a commit of `main`
   whose version matches `manifest.json`.

## Engineering priorities

Strictly in this order: **correctness** (behaviour matches the spec, proven by tests),
**clean code** (no workarounds, no temporary hacks, no test backdoors), **scalability**
(survives more entities, more languages, more contributors). "Fast now, fix later" is a defect.
If a task cannot be done cleanly, split it instead of leaving a workaround. Tests are written
from the user's point of view (the scenario, not just the function).

## Home Assistant conventions

- Follow developers.home-assistant.io and the Integration Quality Scale; look up the current
  API instead of relying on memory — core APIs change every monthly release.
- Async only; no blocking I/O in the event loop.
- User-facing strings go through `translations/` — never hard-coded. `translations/en.json` is the
  strings source: custom integrations have no `strings.json` (that file is for core integrations).
- Configuration through config flows / options flows (UI), not YAML.
- Minimum supported Home Assistant version is pinned in `hacs.json` and must match the version
  `pytest-homeassistant-custom-component` is pinned to in `pyproject.toml`.

## User documentation

The pages for people who use Timerify are `README.md` and `README.ru.md` (the entry pages) and
`docs/en/` and `docs/ru/` (one page per topic, the same file names in both). Specs, plans and
research notes in the other folders of `docs/` are for contributors, not user documentation.

- **Both languages, one commit.** Every change to a user page is made in the English and the
  Russian page in the same commit. `tests/test_docs.py` pins the pairs: the same page names, the
  same number of `##` and `###` headings, the same images; it also resolves every link and anchor.
- **Style.** Short sentences (about 20 words at most), one idea each. Address the reader as
  "you" (the polite plural in Russian). No long dashes (`—`, `–`): use a full stop, a comma, a
  colon or brackets. No `§` and no rule ids (`R3`, `S1`, `P-7e`). No internal words ("wish",
  "fold", "firm promise", "loose", "strict") unless the page says in plain words what they mean
  the first time; the modes appear in the UI, so name them as the UI does and explain them.
  Attribute names, service fields and YAML belong in `services.md`, and in code blocks elsewhere.
- **Links.** In the READMEs, links to files of this repository are absolute
  (`https://github.com/klimofey/timerify/blob/main/<path>`) and images are raw URLs
  (`https://raw.githubusercontent.com/klimofey/timerify/main/<path>`): HACS and the Marketplace
  show the README away from the repository, where a relative path breaks. Inside `docs/`, links
  are relative.

## Commands

```sh
uv sync                     # install the dev environment (Python >= 3.14.2)
uv run pytest               # tests, in parallel (pytest-xdist: `-n auto` is in the options)
uv run pytest -n 0          # the same tests in one process, for a debugger or a stack trace
uv run ruff check           # lint
uv run ruff format --check  # formatting
uv run mypy                 # strict type check of custom_components and scripts
```

The card is a separate npm project in `card/` (Node >= 26); every command goes through `--prefix`:

```sh
npm --prefix card ci                                # install the locked packages
npm --prefix card exec playwright install chromium  # once per machine, for the E2E tests
npm --prefix card run build                         # rebuild the committed bundle (after any change in card/src or en.json)
npm --prefix card run build:check                   # fail if the committed bundle is not what the sources build
npm --prefix card run typecheck                     # strict tsc
npm --prefix card test                              # vitest unit and component tests
npm --prefix card run e2e                           # Playwright against a real Home Assistant in Docker (port 18124)
npm --prefix card run screenshots                   # the two pictures of the card page, by hand, when the card's look changes
```

Docker runs the rest: hassfest (`docker run --rm --platform linux/amd64 -v "$PWD:/github/workspace"
ghcr.io/home-assistant/hassfest`) and the smoke test (`uv run python -m scripts.smoke.run`, port
18123, about fifteen minutes, at the end of a phase). Before running the E2E or the smoke test,
compare `date -u +%s` with `docker run --rm alpine date -u +%s`: a Docker clock that has drifted
fails the tests that compare the browser's clock with the server's.

All checks (pytest, ruff check, ruff format --check, mypy, `npm --prefix card ci`, `build:check`,
`typecheck`, `test`, `e2e` and hassfest) must pass locally before any commit lands on `main`.
