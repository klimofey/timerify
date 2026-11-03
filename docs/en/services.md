# Actions

Timerify adds five actions to Home Assistant. This page lists them with their fields and ranges. It also lists the three events that Timerify fires.

| Action | Name in the form | What it does |
| --- | --- | --- |
| `timerify.add_time` | **Add time** | Moves the end of the countdown. |
| `timerify.run` | **Run** | Turns the device on. |
| `timerify.stop` | **Stop** | Ends the countdown and turns the device off. |
| `timerify.add_command` | **Add command** | Keeps a pending command. |
| `timerify.cancel_command` | **Cancel command** | Removes a pending command. |

## Calling the actions

All the actions act on the **Run for** entities of timers. Pick them, or their devices or areas, as the target.

In YAML, you write the settings next to the other fields. The form of an action puts them in a collapsed **Settings** section.

A call can wait its turn behind a slow device. If the timer is unloaded meanwhile, the call fails with a message. It does not report success.

## Add time

`timerify.add_time` moves the end of the countdown by a number of minutes. A negative number takes time off. One call moves the end by a day at most, either way. Adding to a timer that is not running starts it. Taking off all the time that is left turns the device off. If the device runs under a [limit](timers.md#turn-off-a-device-that-was-left-on), the minutes are added to the limit. The result is an ordinary countdown that you chose, and the limit is gone.

| Field | Type | What it is |
| --- | --- | --- |
| `minutes` | number, required | Minutes to move the end by, from -1440 to 1440. |

```yaml
action: timerify.add_time
target:
  entity_id: number.boiler_run_for
data:
  minutes: 15
```

## Run

`timerify.run` turns the device on.

- With `minutes` (1 to 1440), the countdown is that long.
- Without it, a device that is off runs to the end of the schedule window, if one is open. In **Strict** mode the default duration is kept when it ends later. With no window open, a **Strict** device runs for the default duration. A **Loose** device runs without a countdown, and the timer's limit, if it has one, turns it off in the end. A device that is running already keeps its countdown or its limit. The [Modes](timers.md#modes) section explains both modes.

Settings go along, also to a device that keeps its countdown. A setting that the device does not support is refused before anything happens.

| Field | Type | What it is |
| --- | --- | --- |
| `minutes` | number | How long to run, in whole minutes, from 1 to 1440. |
| The settings | See [Settings](#settings) | What to turn the device on with. |

```yaml
action: timerify.run
target:
  entity_id: number.ac_run_for
data:
  minutes: 60
  hvac_mode: cool
  temperature: 24
```

### Settings

**Run** and **Add command** take the same settings. The table gives each field, its label in the form and what it accepts. For when settings are applied, see [Settings for turning on](timers.md#settings-for-turning-on).

| Field | Label in the form | Device | Valid values |
| --- | --- | --- | --- |
| `hvac_mode` | HVAC mode | Climate | One of the modes the entity lists, except `off`. |
| `temperature` | Temperature | Climate | From the entity's minimum to its maximum temperature. The device must be able to set a target temperature. |
| `fan_mode` | Fan mode | Climate | One of the entity's fan modes. The device must support fan modes. |
| `brightness_pct` | Brightness | Light | 1 to 100 percent. Only lights that can dim. |
| `percentage` | Speed | Fan | 1 to 100 percent. Only fans that set their speed. |
| `preset_mode` | Preset mode | Fan | One of the fan's preset modes. The fan must support preset modes. |
| `humidity` | Humidity | Humidifier | From the entity's minimum to its maximum humidity. |
| `mode` | Mode | Humidifier | One of the humidifier's modes. The humidifier must support modes. |
| `temperature` | Temperature | Water heater | From the entity's minimum to its maximum temperature. The heater must be able to set a target temperature. |
| `operation_mode` | Operation mode | Water heater | One of the entity's operation modes, except `off`. The heater must support operation modes. |

Other kinds of devices have no settings. If you ask for a setting that the device does not have, Timerify refuses. Timerify does not check the temperature step that the entity reports. A device may round 22.3 to 22.5.

## Stop

`timerify.stop` ends the countdown and turns the device off. It also turns off a device that runs without a countdown in **Loose** mode. A device that is off is left as it is.

It has no fields. It does the same as setting **Run for** to 0, or pressing **Turn off**.

```yaml
action: timerify.stop
target:
  entity_id: number.boiler_run_for
```

## Add command

`timerify.add_command` keeps a pending command. See [Pending commands](pending-commands.md).

Give `action` (`"on"` or `"off"`) and either `delay` or `at`, not both. `delay` is the minutes from now, from 1 to 10080. `at` is a moment up to a week ahead. A time without a time zone is in Home Assistant's time zone, and its seconds are kept. `minutes` and the settings are for a command to turn on.

| Field | Type | What it is |
| --- | --- | --- |
| `action` | `"on"` or `"off"`, required | Whether to turn the device on or off at that time. |
| `delay` | number | The minutes from now, from 1 to 10080. Give this or `at`. |
| `at` | date and time | A moment up to a week ahead. Give this or `delay`. |
| `minutes` | number | How long a command to turn on runs, in whole minutes, from 1 to 1440. |
| The settings | See [Settings](#settings) | What a command to turn on sets up. |

The response holds the id of the command, for each timer. The id is what cancels the command:

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

In YAML, an unquoted `on` is the boolean true. Timerify reads true as `"on"` and false as `"off"`. So `action: on` works too. The examples quote the words anyway.

A command at a moment looks like this. `at` must lie ahead and at most a week away. So this one is refused once 22:30 has passed:

```yaml
action: timerify.add_command
target:
  entity_id: number.boiler_run_for
data:
  action: "off"
  at: "{{ today_at('22:30') }}"
```

### When Add command refuses

`timerify.add_command` is refused, with a message and nothing kept, in these cases:

- Neither or both of `delay` and `at` are given (`delay_or_at`).
- `at` has already passed (`command_in_past`), or is more than 7 days ahead (`command_too_far`).
- `action` is `"off"`, and `minutes` or settings are given (`off_takes_no_duration_or_settings`).
- The device cannot take a setting, as for `timerify.run`.
- The timer already keeps 20 commands (`too_many_commands`).

## Cancel command

`timerify.cancel_command` removes one pending command by its id. Aim it at the timer that holds the command. Another timer does not know the id, and says so (`unknown_command`).

| Field | Type | What it is |
| --- | --- | --- |
| `command_id` | text, required | The id of the command to cancel. |

The id is in the response of `timerify.add_command`. It is also in the `commands` attribute of the [Next command sensor](#what-you-can-read-from-a-timer).

## Events

Timerify fires three events. The [triggers](automations.md#triggers) are built on them. A YAML `event` trigger can use them too.

| Event | Data | When it fires |
| --- | --- | --- |
| `timerify_countdown_started` | `entity_id`, `ends_at`, `limit` | A timer that was not counting down starts a countdown, or sets a limit on a device left on. |
| `timerify_countdown_ended` | `entity_id`, `reason` | A countdown or a limit is over. |
| `timerify_command_due` | `entity_id`, `command_id`, `action` | A pending command is carried out at its time. |

`entity_id` is the **Run for** entity of the timer. `ends_at` is the end of the countdown in UTC, in the form of the state of the **Ends at** sensor. The dashboard shows that time in your local time. `limit` is `true` when `ends_at` is the moment of a limit. It is `false` when `ends_at` is the end of a countdown that someone chose. `command_id` is the id that `timerify.add_command` gave the command. `action` is `on` or `off`.

A countdown or a limit ends for one of four reasons. The event names it in `reason`.

- `expired`: the countdown ran out.
- `stopped`: Timerify stopped it. The cause is one of these:
  - **Run for** set to 0, **Stop**, or the **Turn off** button.
  - A voice request, or the tools of an LLM agent.
  - A pending "off".
  - **Add time** down to zero.
  - A schedule interval that you switched off or deleted while its window ran.
  - A schedule interval that you edited, so that its window no longer runs.
  - The Workday sensor changed its answer, so that the window of a working day or day off interval no longer runs.
- `turned_off`: the device was switched off outside Timerify, for example by hand or in its own app. Another automation, or the device itself, counts too.
- `limit`: the limit of a device left on came, and Timerify turned the device off. A limit that ends because the device is switched off has the reason `turned_off`.

An automation about the end of a countdown should check `reason`. Say it starts something when the boiler runs out of time. Without the check, it would also start after **Stop**.

```yaml
triggers:
  - trigger: event
    event_type: timerify_countdown_ended
    event_data:
      entity_id: number.boiler_run_for
      reason: expired
actions:
  - action: persistent_notification.create
    data:
      message: The boiler ran out of time.
```

Changing a countdown that runs fires nothing. That covers a new **Run for**, **Run** with minutes, **Add time** and a schedule window that ends later. A pending command that comes due in the middle still fires its event.

A limit is not a countdown. Choosing a time while a limit runs ends no countdown: the device keeps running, and `timerify_countdown_started` fires with `limit` set to `false`. So does **Add time** to a limit. No `timerify_countdown_ended` event fires for the limit then.

A countdown that ended while Home Assistant was down fires its event once Home Assistant has started. So does a limit that came meanwhile, with the reason `limit`. A countdown or a limit that still runs after a restart fires nothing.

One exception: if you give an action while Home Assistant is still starting, the events that follow can reach no automation. Home Assistant does not run automations during start-up.

## What you can read from a timer

Two sensors of a timer carry attributes for dashboards and templates.

- The sensor **Ends at** has the attributes `started_at` and `limit`. `started_at` holds the moment the countdown began. It is empty while no countdown runs, and while a limit runs. `limit` is `true` while the time of the sensor is the [limit](timers.md#turn-off-a-device-that-was-left-on) of a device left on, and `false` otherwise. The [dashboard card](card.md) draws its fill from `started_at`.
- The sensor **Next command** has the attribute `commands`. It lists all the pending commands, the earliest first. The list is not kept in the history database. [The Next command sensor](pending-commands.md#the-next-command-sensor) shows what it looks like.

## The command of the dashboard card

The dashboard card asks Timerify which entities belong to its timer. It does so through a websocket command, `timerify/timer`.

- The answer comes from the timer's entry and Home Assistant's registry alone. So the card gets an answer even while the timer is starting.
- The answer also names the settings of the device that are written as percentages.
- The answer says what time it is on the server. The card counts by that clock, not by the browser's.
- The command is open to every user. It tells a user only what the user may read.

See [What the card does](card.md#what-the-card-does).

---

[All pages](README.md) · [Back to the README](../../README.md)
