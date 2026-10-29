# Timerify

Timers for any Home Assistant entity, without writing automations.

Timerify attaches a countdown to an entity you already have, the way Powercalc attaches a
virtual power sensor to a device. A boiler that is just a smart switch gains, on its own
device page, a "Run for" control: set 10 minutes and the boiler turns on and turns itself
off when the countdown ends.

![The device page of a timer: Run for and Ends at, with a countdown running](docs/screenshots/phase-1-device-page.png)

> **Status:** version 0.1.0, the first phase. The core timer works and is described below.
> Schedules, pending commands and voice control are not built yet; see
> [What is not here yet](#what-is-not-here-yet).

## What it does

Each timer belongs to one entity, its target. Setting the countdown is the only way
Timerify switches the target, so the rules never contradict each other:

- Set "Run for" to a number of minutes: the target turns on and turns off when the time is up.
  Set it to a new number while it runs: the countdown restarts from that number.
- Set "Run for" to 0: the target turns off. Turn the target off yourself, by hand, from its
  app or by an automation: the countdown is cleared.
- Turn the target on from elsewhere in strict mode: the countdown starts for the default
  duration, so a boiler switched on at the wall still turns itself off. Loose mode leaves
  such a target running without a countdown.
- A target that drops off Wi-Fi keeps its countdown. What came due meanwhile is applied
  when it reports again: a countdown that ended turns it off.
- A command the device rejects, or accepts without doing anything, is not forgotten: it is
  sent again when the target next reports its state, or when you ask for the same thing again.
- A countdown survives a Home Assistant restart: it is stored on every change, and on
  start-up the end time is checked against the clock. A countdown that ended while Home
  Assistant was down turns the target off.
- A countdown is whole minutes, up to one day.

Targets can be switches, input booleans, lights, fans, humidifiers, sirens, remotes,
groups, media players, and climate and water heater entities that can be turned on and off.

### Modes

- **Strict** (the default): the target runs only while the countdown does. In this mode
  you also set the default duration, 30 minutes unless changed.
- **Loose**: the target may also run without a countdown. A countdown only means "turn off
  when it reaches zero".

### Entities

Both sit on the target's device. A target that is on no device gets a device named after
it.

| Entity | What it shows |
| --- | --- |
| `number` Run for | Minutes left, rounded up. Writing it starts, changes or stops the countdown. |
| `sensor` Ends at | The moment the countdown ends; unknown while no countdown runs. The dashboard shows it as "in 7 minutes" by itself. |

### Services

Both act on the "Run for" entities of timers. Pick them, or their devices or areas, as the
target.

`timerify.add_time` moves the end of the countdown by a number of minutes, negative to
take time off, up to a day either way. Adding to a timer that is not running starts it;
taking off all the time that is left turns the target off.

```yaml
action: timerify.add_time
target:
  entity_id: number.boiler_run_for
data:
  minutes: 15
```

`timerify.run` turns the target on without saying for how long: for the default duration
in strict mode, without a countdown in loose mode.

```yaml
action: timerify.run
target:
  entity_id: number.boiler_run_for
```

## Installation

### With HACS

1. In HACS, open the menu in the top right and choose **Custom repositories**.
2. Add `https://github.com/klimofey/timerify` with the type **Integration**.
3. Find Timerify in HACS, download it, and restart Home Assistant.

Home Assistant 2026.10 or newer is required.

### By hand

Copy the `custom_components/timerify` folder of this repository into the
`custom_components` folder of your Home Assistant configuration, and restart.

## Setup

Add one timer per entity:

1. Open **Settings > Devices & services > Helpers**, choose **Create helper** and then
   **Timerify**. (The **Add integration** button on the Integrations tab lists it too, as
   "Timerify (Helper)".)
2. Pick the entity, and the mode.
3. In strict mode, set the default duration.

The timer appears on the entity's device page. To change the mode or the default duration
later, open the timer on the Timerify integration page and choose **Configure**. The
entity itself cannot be changed: add a timer for the other entity instead.

Renaming the target, or moving it to another device, is followed: the timer keeps running.

## What is not here yet

Planned for later versions, none of it available in 0.1.0: a weekly schedule, commands
that wait for a moment to turn the target on, a dashboard card, and Assist voice
control ("turn on the boiler for 10 minutes", "how long is left on the boiler?").

## Verification

What 0.1.0 was checked with before release:

- The test suite (`uv run pytest`): every rule above is a scenario, with time moved
  explicitly.
- `hassfest`, Home Assistant's own validation of an integration, reports no problems.
- A smoke test in a real Home Assistant 2026.10.4 container (see below): the timer is
  added through the config flow, "Run for" 2 minutes turns the target on and off on time,
  and a 3 minute countdown survives a restart of the container and still ends on time.

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

### hassfest

```sh
docker run --rm -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest
```

The image exists for `linux/amd64` only; on Apple silicon add `--platform linux/amd64`.

### Smoke test

Needs Docker with Compose. It starts a throwaway Home Assistant 2026.10.4 with this
checkout mounted, onboards it through its HTTP API, creates a switch, adds a timer for it,
and checks that a 2 minute countdown turns the switch on and off, and that a 3 minute
countdown survives a restart of the container. It takes about five minutes.

```sh
uv run python scripts/smoke/run.py
```

Add `--keep` to leave Home Assistant running afterwards, with a countdown on, at
`http://localhost:18123`; the script prints the address of the device page and the login.
Stop it with `docker compose --file scripts/smoke/compose.yaml down`.

## License

MIT
