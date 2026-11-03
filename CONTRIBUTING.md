# Contributing

This page is for people who work on Timerify itself. If you only want to use it, start with the
[README](README.md) or the [user pages](docs/en/README.md).

Where things live:

- `custom_components/timerify/`: the integration.
- `card/`: the dashboard card, a separate npm project (see [The card](#the-card)).
- `tests/`: the Python tests. They are written as scenarios, from the user's point of view.
- `docs/en/` and `docs/ru/`: the pages for people who use Timerify. A change to one is made in
  the other in the same commit; `tests/test_docs.py` checks the pairs.
- `docs/superpowers/specs/`, `docs/superpowers/plans/` and `docs/research/`: the design specs,
  the plans and the research notes. `RULINGS.md` holds the decisions made where a spec was
  silent. `docs/followups.md` lists the open items, which are
  [GitHub issues](https://github.com/klimofey/timerify/issues).

Everything in the repository is in English: code, comments, commit messages and documentation.
Cyrillic is allowed only in the translations of the product and of its user pages, and in
`tests/fixtures/ru/`, the Russian answers that the tests are checked against. Git hooks in
`.githooks/` enforce this (see [Development](#development) for turning them on), and they must
never be bypassed.

## Verification

What a release is checked with before it is published:

- The test suite (`uv run pytest`): every rule of the user pages is a scenario, with time
  moved explicitly, among them the days the clock changes, Home Assistant down overnight, a
  Workday sensor that is away or renamed, a target that is given a device while Home
  Assistant runs or is down, and the real Workday integration for the Israeli week. The
  voice sentences are said to Home Assistant's real built-in agent, in both languages, and
  the LLM tools are called through the real Assist API; the sentence files are generated
  from their sources and checked against the shipped ones. The beginning of a countdown
  (`started_at`) is checked in every path that sets an end, across restarts, and the card's
  websocket command for a user who may and one who may not read the timer's entities.
  The runtime counter is checked the way a user meets it: a manual run, a countdown, a
  flapping relay, Home Assistant stopped, restarted or crashed between two writes of the
  sensor, a target that goes unavailable, a clock set back, a renamed target, the counter
  switched off and on again, and a file written by a newer release; and, through Home
  Assistant's real recorder, a run across midnight whose minutes land on the right day.
- The card's own tests (`npm --prefix card test`): both layouts, the pop-up, the long press, the
  editor and the picker, in English and Russian, with a stand-in for Home Assistant's frontend
  object and time moved explicitly.
- End-to-end tests of the card (`npm --prefix card run e2e`) in a real Home Assistant 2026.10.4
  container with a real browser: both layouts, the pop-up's actions, the long press, the editor
  and the picker, a user who is not an administrator, Russian, and a restart of Home Assistant
  in the middle of a countdown. One test records the known issue on 2026.10 as an expected
  failure.
- `hassfest`, Home Assistant's own validation of an integration, reports no problems.
- A smoke test in a real Home Assistant 2026.10.4 container (see [Smoke test](#smoke-test)):
  the page that Home Assistant serves loads the card's module at the address that carries
  the version of the bundle, that address serves the bundle byte for byte, and the card's
  websocket command tells the first timer's entities; the timer is
  added through the config flow, "Run for" 2 minutes turns the target on and off on time,
  and a 3 minute countdown survives a restart of the container and still ends on time. A
  pending command turns a switch that sits on a device on at its time and off a minute
  later, a thermostat run for a minute with a mode and a temperature is set to both and
  switched off at the end, a loose timer with a limit of 1 minute, added through the
  config flow with its limit step, turns a switch off a minute after someone turned it on
  by hand, while its "Ends at" sensor names that moment and says it is a limit, and a
  schedule interval added through the interval form turns a switch on at its start and
  off at its end, with the interval's own switch on. The Voice settings are added through
  the config flow and the built-in agent is talked to over the REST API: it refuses a
  device that is not exposed to Assist, and once the device is exposed, "turn on ... for 2
  minutes", "how much time is left", "turn off in 1 minute", a bare "turn on" and a bare
  "turn off" each give the answer the sentence is meant to and leave the switch in the
  state the REST API reports. The first timer is added with the runtime counter ticked,
  and after its 2 minute run its Runtime sensor reads 2 minutes, in minutes, as a total
  that only goes up.
- A manual walk-through in a real Home Assistant 2026.10.4 container, through the browser;
  its screenshots are in `docs/screenshots/smoke-*.png`. It covered the
  integration page at 1.0.0 with its icon, adding a timer with the runtime counter, a
  countdown running, and a countdown kept across a restart of Home Assistant (the target
  was an `input_boolean`, which restores its state; a demo switch does not, and the timer
  clears the countdown of a target that is no longer on). It went on to a schedule interval
  that turned the target on at its start, two Assist sentences said to the built-in agent,
  and the card in the pill and in the round layout. At 1.1.0 it went on to the new fields
  of the timer form (Maximum of Run for, Turn off button), the Turn off button entity
  turning a running target off, Timerify's actions and triggers under By target in the
  automation editor, a turn-on at a clock time said to Assist and kept as a pending
  command, the card's Turn off button in both layouts, and the Interactions group of the
  card editor (`smoke-2` and `smoke-11` to `smoke-16`).

## Development

Requires Python 3.14.2+ and [uv](https://docs.astral.sh/uv/).

```sh
git config core.hooksPath .githooks
uv sync
uv run pytest
uv run ruff check
uv run ruff format --check
uv run mypy
```

The tests run in parallel, one worker per core (`pytest-xdist`, set in `pyproject.toml`).
`uv run pytest -n 0` runs them in one process, which a debugger or a plain stack trace needs.

### The card

The card is TypeScript ([Lit](https://lit.dev/)) in `card/`, a self-contained npm project that
needs Node 26. esbuild bundles it into one file,
`custom_components/timerify/frontend/timerify-card.js`. That file is committed, because HACS
downloads the repository and there is no release build. The build is deterministic, and
`build:check` rebuilds the bundle in memory and fails when the committed file differs, so a
change of the sources and the bundle it makes go together. The words of the card are the
`card_*` keys under `common` in `custom_components/timerify/translations/`, and the English
ones are built into the bundle.

```sh
npm --prefix card ci                                # the exact locked packages
npm --prefix card exec playwright install chromium  # once, for the end-to-end tests
npm --prefix card run build                         # rebuild the committed bundle
npm --prefix card run build:check                   # fail if the committed bundle is stale
npm --prefix card run typecheck
npm --prefix card test                              # unit and component tests: vitest, happy-dom
npm --prefix card run e2e                           # end-to-end tests, in Docker
npm --prefix card run screenshots                   # the two pictures of the card page
```

The end-to-end tests need Docker with Compose. They start a throwaway Home Assistant 2026.10.4
through the same harness as the smoke test (`scripts/harness/hass.py`), at
`http://localhost:18124`, log in through the real login page in a real Chromium, run one after
the other in New York time (so that a test can tell the browser's clock from the server's) and
remove the container. The smoke test uses port 18123, so the two can run side by side.

The pictures are not part of that run, because a countdown changes every second: the
`screenshots` project fixes the browser's clock 15 minutes into a 45 minute countdown, which
fixes the time left and the fill. The end time on the pill is the server's real one, so a rerun
changes the pictures; refresh them by hand, and look at them, when the card's look changes.

### hassfest

```sh
docker run --rm -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest
```

The image exists for `linux/amd64` only; on Apple silicon add `--platform linux/amd64`.

### Smoke test

Needs Docker with Compose. It starts a throwaway Home Assistant 2026.10.4 with this
checkout mounted, onboards it through its HTTP API, and adds timers for the entities that
`scripts/harness/configuration.yaml` declares: a switch that sits on no device, two switches
of Home Assistant's demo integration (which sit on devices), and a generic thermostat. It
checks that the page Home Assistant serves loads the card's module and serves its bundle
unchanged, that the card's websocket command knows the first timer, that a 2 minute
countdown turns the first switch on and off, that a schedule
interval for today's weekday, added through the interval form to begin in a minute or two,
turns the first switch on at its start and off two minutes later (its switch is on, on the
timer's device), that the built-in agent, given the Voice settings through the config flow
and talked to over the REST API, runs, shortens and stops the first switch by sentences,
that a 3 minute countdown survives a restart of the container, that a pending command
turns the demo switch on at its time and off a minute later, that the thermostat takes
the mode and the temperature of a run, that a loose timer with a limit of 1 minute, added
through the config flow, turns the second demo switch off a minute after someone turned it
on by hand (its "Ends at" sensor names that moment and says it is a limit), and that the
first timer, added with the runtime counter ticked, shows its 2 minute run on its Runtime
sensor. It takes about fifteen minutes.

```sh
uv run python -m scripts.smoke.run
```

Add `--keep` to leave Home Assistant running afterwards, with a countdown on, at
`http://localhost:18123`; the script prints the address of the device page and the login.
Stop it with `docker compose --project-name timerify-smoke down`.
