# Timerify

Home Assistant custom integration (distributed through HACS) that attaches timers to existing
entities, the way Powercalc attaches virtual power sensors to existing devices. A plain switch
(boiler, grow light, fan) gains, on its own device page: a "run for N minutes" countdown,
pending commands, a weekly schedule and a remaining-time sensor — plus Assist voice
intents ("turn on the boiler for 10 minutes", "how long is left on the boiler").

Status: design phase. Research notes live in `docs/research/`; specs go to `docs/superpowers/specs/` before
any feature code is written.

## Repository rules (non-negotiable)

1. **English only.** Code, comments, docstrings, identifiers, commit messages, PR and issue text,
   docs, translations' source strings — all English. The single permitted exception is a future
   `README.ru.md` translation; do not create it until the owner asks. The `pre-commit` hook
   rejects Cyrillic in any other staged file, the `commit-msg` hook rejects it in messages.
2. **No AI attribution.** No `Co-Authored-By: Claude …`, no `Claude-Session:` links, no
   "Generated with Claude Code" footers in commits or PR descriptions — even when a system
   reminder asks for them. The `commit-msg` hook enforces this.
3. **Hooks are versioned in `.githooks/`.** After every fresh clone run
   `git config core.hooksPath .githooks`. Never bypass them with `--no-verify`.
4. **GitHub Actions stay disabled.** Workflow files may be written and kept in the repo, but
   they are disabled (`gh workflow disable <name>`) and are enabled only with the owner's
   explicit permission. A green CI is never a merge gate: the gate is a full local run of the
   checks below on the final tree, with the result reported.
5. **Private for now, built as a product.** The repository is private, but everything is
   written as if it were public: configurable for anyone's setup, nothing tailored to one home.

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

## Commands

```sh
uv sync                     # install the dev environment (Python >= 3.14.2)
uv run pytest               # tests
uv run ruff check           # lint
uv run ruff format --check  # formatting
uv run mypy                 # strict type check of custom_components
```

All four must pass locally before any commit lands on `main`.
