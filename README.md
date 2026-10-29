# Timerify

Timers for any Home Assistant entity, without writing automations.

Timerify attaches a countdown to an entity you already have, the way Powercalc attaches a
virtual power sensor to a device. A boiler that is just a smart switch gains, on its own
device page, a "Run for" control: set 10 minutes and the boiler turns on and turns itself
off when the countdown ends.

![The device page of a timer: Run for and Ends at, with a countdown running](docs/screenshots/phase-1-device-page.png)

> **Status:** version 0.2.0, the second phase. The core timer, settings for turning on
> ("cooling, 24 degrees") and pending commands ("turn on in 15 minutes") work and are
> described below. Schedules and voice control are not built yet; see
> [What is not here yet](#what-is-not-here-yet).

## What it does

Each timer belongs to one entity, its target. Starting, changing and stopping the countdown
is the only way Timerify switches the target, so the rules never contradict each other (a
pending command is a change of the countdown that happens later):

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
  sent again when the target next reports its state, or when you ask for the same thing
  again. A target that keeps reporting the same state gets at most 3 such repeats; after
  that Timerify logs a warning and waits for the state to change or for a new command.
  Remotes and media players get no repeats from their reports: a repeat could switch a
  toggle remote back or disturb a player that is still starting up. They are sent the
  command again only when their state changes or when you ask again.
- A countdown survives a Home Assistant restart: it is stored on every change, and on
  start-up the end time is checked against the clock. A countdown that ended while Home
  Assistant was down turns the target off.
- A countdown is whole minutes, up to one day.

### Targets

Targets can be switches, input booleans, lights, fans, humidifiers, sirens, remotes,
groups, media players, and climate and water heater entities, and any other entity of a
kind that has `turn_on` and `turn_off` services, such as an automation. Timerify turns
those other entities, and groups, on and off through `homeassistant.turn_on` and
`homeassistant.turn_off`.

- Fans, media players, sirens and climate entities must advertise that they can be turned on
  and off (the feature `TURN_ON` and `TURN_OFF`), and water heaters that they support on
  and off. A device that works but does not say so is not offered, because Home Assistant
  itself refuses to switch it.
- Groups and the other entities (those outside the list of kinds above) must report `on` or
  `off` when you add the timer. A group of covers or locks reports `open` or `locked`, and
  Timerify could not tell whether it is running, so it answers "does not report on or off".
  So does an entity that is unavailable at that moment: try again once it is back.
- The picker lists every entity of a kind with both services, so it also shows cameras. A
  camera reports `idle` or `streaming`, which is not on or off, so adding one is refused
  with the same answer. Vacuum cleaners have no `turn_on` and `turn_off` in Home
  Assistant 2026.10, so they are not offered.

### Modes

- **Strict** (the default): the target runs only while the countdown does. In this mode
  you also set the default duration, 30 minutes unless changed.
- **Loose**: the target may also run without a countdown. A countdown only means "turn off
  when it reaches zero".

### Entities

All three sit on the target's device. A target that is on no device gets a device named
after it.

| Entity | What it shows |
| --- | --- |
| `number` Run for | Minutes left, rounded up. Writing it starts, changes or stops the countdown. |
| `sensor` Ends at | The moment the countdown ends; unknown while no countdown runs. The dashboard shows it as "in 7 minutes" by itself. |
| `sensor` Next command | The moment the next pending command is due; unknown while there is none. See [Next command sensor](#next-command-sensor). |

## Settings

A command that turns the target on can say how: the HVAC mode and temperature of an air
conditioner, the brightness of a light, the speed of a fan. These are the target's
settings. Timerify offers only what the target itself says it can do (its supported
features and lists such as the HVAC modes it has), and checks a request against that when
you make it, so a wrong request is refused at once with a message, not when the device
is already waiting for it.

Settings are applied in these cases:

- `timerify.run` with settings turns the target on with them. If the target is already
  running, it gets them anyway: you asked for them.
- A pending command that turns the target on carries its settings the same way, at its time,
  whether the target is running then or not.
- Settings that still wait for the device (see below) go out with the next turn-on of any
  kind, whatever causes it: setting "Run for", `timerify.add_time` on a timer that is not
  running, a command that gives no settings of its own. If the target is found running
  instead, even when you turned it on by hand, they are set then.

When no settings wait, a manual turn-on, setting "Run for" and `timerify.add_time` turn the
target on plainly.

An air conditioner (any climate entity) is turned on by setting the HVAC mode when one is
given, and by `climate.turn_on` otherwise. The calls go one after the other: the turn-on
(or the mode), then the temperature, then the fan mode.

What happens when the device cannot take them yet:

- The target is unavailable, or a call fails: the settings are kept and sent again, with the
  same limits as a refused turn-on, when the target reports again. The countdown runs
  meanwhile.
- Settings given later replace the ones that wait. A command that gives none leaves them
  alone, so they go out with the next turn-on, whatever causes it.
- The countdown ending, or you turning the target off by hand, drops them.

Timerify trusts what the device accepts: a settings call that returns without an error counts
as applied, and the device's attributes are not compared afterwards (devices round and
report late). Only the turn-on is checked against the target's state: a device that says
yes and stays off gets the turn-on again, with its settings.

### Supported settings per domain

| Domain | Setting | Valid values |
| --- | --- | --- |
| climate | `hvac_mode` | One of the modes the entity lists, except `off` |
| climate | `temperature` | From the entity's minimum to its maximum temperature; needs the target temperature feature |
| climate | `fan_mode` | One of the entity's fan modes; needs the fan mode feature |
| light | `brightness_pct` | 1 to 100; lights that can dim |
| fan | `percentage` | 1 to 100; fans that set their speed |
| fan | `preset_mode` | One of the fan's preset modes; needs the preset mode feature |
| humidifier | `humidity` | From the entity's minimum to its maximum humidity |
| humidifier | `mode` | One of the humidifier's modes; needs the modes feature |
| water_heater | `temperature` | From the entity's minimum to its maximum temperature; needs the target temperature feature |
| water_heater | `operation_mode` | One of the entity's operation modes, except `off`; needs the operation mode feature |

Other domains have no settings. Asking for a setting a target does not have is refused. The
temperature step the entity reports is not enforced: a device may round 22.3 to 22.5.

## Pending commands

A pending command is "at time T, do this": turn the target on (for some minutes if you like,
with settings if you like) or turn it off. A timer can hold up to 20 of them, each at most
7 days ahead, and each can be cancelled on its own. Three promises hold:

- **A command is carried out at its time whatever state the target is in then.** If the air
  conditioner is already running when "cooling, 24 degrees, for an hour" comes due, it
  receives cooling and 24 degrees, and the countdown is set to 60 minutes.
- **Using the target by hand does not cancel it.** Turning the target on or off yourself, or
  the countdown ending, between now and then leaves the command in place. Only
  `timerify.cancel_command` removes it.
- **"Turn on for N minutes" at its time is the same as setting "Run for" to N at that
  time.** Without minutes, a command to turn on runs for the default duration in strict mode
  and without a countdown in loose mode. A command to turn off turns the target off and
  stops the countdown. A command to turn on that comes due at the very moment a countdown
  ends keeps the target on instead of switching it off and on.

Restarts and outages:

- Commands are stored on every change and survive a restart.
- A command that came due while Home Assistant was down is carried out at start-up for what
  is left of its run: asked at 07:00 to run for 60 minutes, with Home Assistant back at
  07:20, it runs for 40 more. If nothing is left, it is dropped and the log says so. A
  command to turn off, or to turn on without a countdown in loose mode, is carried out
  however late.
- If several commands came due, they are applied in time order and only the final state
  reaches the target: an "on" and the "off" after it that were both due switch nothing.
- A command that comes due while the target is unavailable changes the countdown at once,
  and the target is switched when it reports again, if the command still matters by then. A
  run that is already over is never started.

### Next command sensor

The sensor `Next command` of a timer shows when the next pending command is due, as a time,
and is unknown while there is none. Its attribute `commands` lists all the pending commands,
the earliest first, for dashboards and templates:

```yaml
commands:
  - id: 0f5c1e2a7d9b4c3e8a6b1d2c3e4f5a6b
    at: "2026-01-05T07:15:00+00:00"
    action: "on"
    minutes: 60
    settings:
      hvac_mode: cool
      temperature: 24.0
```

`id` is what `timerify.cancel_command` takes, `at` is in UTC, `minutes` is null when the
command gives none, and `settings` is empty when it carries none. The list is not kept in
the history database.

## Services

All of them act on the "Run for" entities of timers. Pick them, or their devices or areas,
as the target. Settings are written next to the other fields in YAML; the service form
folds them into a collapsed "Settings" section. A call that waits behind a slow device
while its timer is unloaded fails with a message instead of reporting success.

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

`timerify.run` turns the target on. With `minutes` (1 to 1440) the countdown is that long;
without it the target runs for the default duration in strict mode and without a countdown
in loose mode. Settings go along; a setting the target does not support is refused before
anything happens.

```yaml
action: timerify.run
target:
  entity_id: number.ac_run_for
data:
  minutes: 60
  hvac_mode: cool
  temperature: 24
```

`timerify.add_command` keeps a pending command. Give `action` (`"on"` or `"off"`) and
either `delay`, the minutes from now (1 to 10080), or `at`, a moment up to a week ahead,
not both. A time without a time zone is Home Assistant's time zone, and its seconds are
kept. `minutes` and the settings are for a command to turn on. The response holds the id
of the command, per timer, which is what cancels it:

```yaml
- action: timerify.add_command
  target:
    entity_id: number.ac_run_for
  data:
    action: "on"
    delay: 15
    minutes: 60
    hvac_mode: cool
    temperature: 24
  response_variable: cmd
- action: timerify.cancel_command
  target:
    entity_id: number.ac_run_for
  data:
    command_id: "{{ cmd['number.ac_run_for'].command_id }}"
```

In YAML an unquoted `on` is the boolean true. Timerify reads true as `"on"` and false as
`"off"`, so `action: on` works too; the examples quote the words anyway.

A command at a moment looks like this. `at` must lie ahead and at most a week away, so
this one is refused once 22:30 has passed:

```yaml
action: timerify.add_command
target:
  entity_id: number.boiler_run_for
data:
  action: "off"
  at: "{{ today_at('22:30') }}"
```

`timerify.add_command` is refused, with a message and nothing kept, when:

- neither or both of `delay` and `at` are given (`delay_or_at`);
- `at` has already passed (`command_in_past`) or is more than 7 days ahead
  (`command_too_far`);
- `action` is `"off"` and `minutes` or settings are given
  (`off_takes_no_duration_or_settings`);
- the target cannot take a setting, as for `timerify.run`;
- the timer already keeps 20 commands (`too_many_commands`).

`timerify.cancel_command` removes one pending command by its id. Aim it at the timer that
holds the command: another timer does not know the id and says so
(`unknown_command`). The id is in the response of `timerify.add_command` and in the
`commands` attribute of the [Next command sensor](#next-command-sensor).

## Installation

### With HACS

1. In HACS, open the menu in the top right and choose **Custom repositories**.
2. Add `https://github.com/klimofey/timerify` with the type **Integration**.
3. Find Timerify in HACS, download it, and restart Home Assistant.

Home Assistant 2026.10.4 or newer is required.

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

Planned for later versions, none of it available in 0.2.0: a weekly schedule, a dashboard
card, and Assist voice control ("turn on the boiler for 10 minutes", "how long is left on
the boiler?").

## Verification

What 0.2.0 was checked with before release:

- The test suite (`uv run pytest`): every rule above is a scenario, with time moved
  explicitly.
- `hassfest`, Home Assistant's own validation of an integration, reports no problems.
- A smoke test in a real Home Assistant 2026.10.4 container (see below): the timer is
  added through the config flow, "Run for" 2 minutes turns the target on and off on time,
  and a 3 minute countdown survives a restart of the container and still ends on time. A
  pending command turns a switch that sits on a device on at its time and off a minute
  later, and a thermostat run for a minute with a mode and a temperature is set to both and
  switched off at the end.

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
checkout mounted, onboards it through its HTTP API, and adds timers for the entities that
`scripts/smoke/configuration.yaml` declares: a switch that sits on no device, the switch of
Home Assistant's demo integration (which sits on a device), and a generic thermostat. It
checks that a 2 minute countdown turns the first switch on and off, that a 3 minute
countdown survives a restart of the container, that a pending command turns the demo switch
on at its time and off a minute later, and that the thermostat takes the mode and the
temperature of a run. It takes about ten minutes.

```sh
uv run python scripts/smoke/run.py
```

Add `--keep` to leave Home Assistant running afterwards, with a countdown on, at
`http://localhost:18123`; the script prints the address of the device page and the login.
Stop it with `docker compose --file scripts/smoke/compose.yaml down`.

## License

MIT
