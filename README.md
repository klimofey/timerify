# Timerify

Timers for any Home Assistant entity, without writing automations.

Timerify attaches a countdown to an entity you already have, the way Powercalc attaches a
virtual power sensor to a device. A boiler that is just a smart switch gains, on its own
device page, a "Run for" control: set 10 minutes and the boiler turns on and turns itself
off when the countdown ends.

![The device page of a timer: Run for and Ends at, with a countdown running](docs/screenshots/phase-1-device-page.png)

> **Status:** version 0.4.0, the fourth phase. The core timer, settings for turning on
> ("cooling, 24 degrees"), pending commands ("turn on in 15 minutes"), weekly schedules
> ("working days 06:30 to 07:15") and voice control through Assist ("turn on the boiler for
> 10 minutes", "how long is left on the boiler") work and are described below. The
> dashboard card is not built yet; see [What is not here yet](#what-is-not-here-yet).

## What it does

Each timer belongs to one entity, its target. Starting, changing and stopping the countdown
is the only way Timerify switches the target, so the rules never contradict each other (a
pending command is a change of the countdown that happens later, and so is the start of a
schedule interval's window):

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
- A weekly schedule starts the countdown on its own at set times of the day; see
  [Schedules](#schedules).

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

All of them sit on the target's device. A target that is on no device gets a device named
after it.

| Entity | What it shows |
| --- | --- |
| `number` Run for | Minutes left, rounded up. Writing it starts, changes or stops the countdown. |
| `sensor` Ends at | The moment the countdown ends; unknown while no countdown runs. The dashboard shows it as "in 7 minutes" by itself. |
| `sensor` Next command | The moment the next pending command is due; unknown while there is none. See [Next command sensor](#next-command-sensor). |
| `switch` Schedule *06:30–07:15, Sun–Thu* | One per schedule interval: on while the interval is in use, off to skip it. See [The switch of an interval](#the-switch-of-an-interval). |

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
- The settings of a schedule interval go out only with the turn-on that its window makes,
  and are never pushed onto a target that is already running; see
  [Settings of an interval](#settings-of-an-interval).

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

## Schedules

A schedule interval says "the target should run from this time to that time on these days".
A timer can have any number of them, each with its own days, times and settings: a boiler
that heats on working-day mornings and a little later on days off is two intervals. When an
interval's window opens, Timerify sets the timer to the window's end, so the target turns on
and turns itself off at the end like any other countdown, and everything above applies:
"Run for", `timerify.add_time` and the other services work on a countdown a window started.

### Adding, editing and deleting intervals

Intervals belong to the timer's entry, one at a time. Open **Settings > Devices & services**
and the timer's entry under Timerify, and choose **Add schedule interval**. Each interval
is listed there with a menu to **Edit** or **Delete** it. The form asks for:

- **Days**: the weekdays you pick, the working days, or the non-working days; see
  [Days](#days).
- **Weekdays**: the days the interval starts on, all seven to begin with. It matters only
  when the days are the weekdays.
- **Start time** and **End time**, in whole minutes; the two must differ. An end earlier
  than the start carries the interval past midnight into the next day: 22:00 to 06:00 runs
  the night, and belongs to the day it starts on.
- **Settings**, for a target that has some: see [Settings of an interval](#settings-of-an-interval).
  The section is folded away for a new interval and open when you edit one that has settings.

An interval is named by its times and days, in your language: *06:30–07:15, Sun–Thu*. A
name you gave it yourself is kept when you edit the interval; one that Timerify made follows
the edit.

Adding, editing or deleting an interval reloads the timer for a moment so that it reads its
intervals again. The countdown and the pending commands are stored and carry on. Deleting
an interval removes its switch.

### Days

- **Weekdays**: any set of days of the week.
- **Working days** and **Non-working days**: follow a **Workday sensor**, a binary sensor of
  Home Assistant's [Workday integration](https://www.home-assistant.io/integrations/workday/),
  which knows your country's public holidays and the working week you set in it. Its
  default week is Monday to Friday in every country, so set the week in the sensor's own
  options, both fields: **Days to include** and **Days to exclude** — a day in both lists
  is excluded. In Israel: include Sunday to Thursday, exclude Friday, Saturday and holidays.
  Timerify follows the sensor. A boiler that runs "on working days at 06:30" skips a
  holiday on its own.

The Workday sensor belongs to the timer. If your house has one, the last step of adding a
timer asks for it, and the first interval you add then offers working days from the start.
To set it, change it or take it away later, open the timer's entry and choose **Configure**;
the sensor is the last step. It is optional, and a timer without one has weekday intervals
only.

- **Use a sensor with a days offset of 0**, the default of the Workday integration. Timerify
  asks the sensor about the day an interval starts on and takes its answer as it is: a
  sensor with an offset of 1 answers for the day after, and the schedule would run shifted
  by a day.
- **An interval of working days or non-working days needs the timer's Workday sensor.** The
  interval form refuses these days on a timer without one, and **Configure** refuses to
  remove the sensor while an interval uses it: change or delete those intervals first. (A
  timer whose stored intervals need a sensor it does not have, which only a hand-edited
  file can produce, does not load and says why; reload it after fixing the file.)
- **An unavailable sensor stops new windows, not running ones.** When the sensor is
  unavailable, the Workday integration is not loaded, or its answer fails, Timerify cannot
  tell whether a day is a working one. The windows it has already worked out stay: one that
  is open runs to its end and one that has not begun still begins. No new window of a
  working-day or non-working-day interval is worked out until the sensor answers, so the
  morning after the sensor went away nothing starts. The log carries one warning per outage
  that says which sensor and why. Timerify tries again whenever the sensor changes or
  reports, which the Workday integration does at every midnight; when it answers, a window
  that is open is run for its remainder. Intervals of weekdays do not depend on the sensor.
- **A renamed Workday sensor is not followed.** Timerify keeps the sensor by its entity id,
  and unlike the target it does not follow a rename. After renaming the sensor the working-day
  intervals wait and the log says the sensor could not be asked; open **Configure** on the
  timer and pick the sensor again.

### Windows

Each day an interval applies, it opens a window from its start to its end. Windows follow the
clock on the wall, in Home Assistant's time zone:

- A window across midnight lasts what the clock says. For working days, the day that counts
  is the day it starts on.
- On the days the clock changes, a window starts and ends at its wall times. In Israel in
  2026, from 23:00 to 07:00 lasts 7 hours on the night the clock goes forward and 9 hours
  on the night it goes back. A time that does not exist (02:30 on the night the clock jumps
  from 02:00 to 03:00) happens an hour later, at 03:30, so 02:10 to 02:50 runs from 03:10 to
  03:50 that day. When that puts the start at or after the end (02:30 to 03:15, or 02:50 to
  03:10), the interval does not run that day. A time that happens twice (01:30 when the
  clock goes back) is its first.
- A window is never longer than a day, the length of the longest countdown.
- Changing Home Assistant's time zone moves the windows. (A zone changed in
  `configuration.yaml` and applied with "Reload core configuration" is not noticed until a
  window ends, the Workday sensor reports or the timer is reloaded.)

### The switch of an interval

Every interval has a `switch` on the timer's device, named *Schedule 06:30–07:15, Sun–Thu*.
It is on to begin with.

- Switch it off and the interval is skipped. If its window is open and the schedule is
  running the timer, the timer stops at once, or passes to another open window that wants
  the target running (rule 2 below).
- Switch it on while the window is open and the target runs for the rest of the window.
- The state is stored with the timer and survives restarts. Flipping the switch does not
  reload the timer.
- The name follows edits of the interval after the reload; the entity id keeps the title the
  interval had when it was added.

### How the schedule and your own changes meet

Schedules are declarative: an interval means "the target should run during this window",
and you always win. Five rules, in plain words:

1. **A window extends a manual run, never shortens it.** When a window opens, the timer is
   set to the window's end, unless the timer already ends later, in which case it is left
   alone. If you started a countdown at 06:20 that ends at 06:40, the 06:30 to 07:15 window
   makes it end at 07:15; if you added time so that it ends at 08:00, it stays. In loose
   mode a run without a countdown that is going when a window opens is cut at the window's
   end.
2. **Edits follow the schedule.** While the timer's end was set by a schedule interval and
   you have not changed the timer since, editing, deleting or switching off that interval
   moves or stops the timer at once: edit the interval at 07:00 from 06:00 to 08:00 into 06:00
   to 07:30, and the timer ends at 07:30. Moving an interval ahead stops the target and
   starts it at the new start, which is a new window. With overlapping intervals the timer
   ends at the latest end of the open windows, so deleting one of two overlapping intervals
   does not stop a target that the other still wants.
3. **A change of yours ends that.** "Run for", `timerify.add_time`, `timerify.run`,
   stopping the timer and a pending command are yours: after one, editing an interval no
   longer touches the timer, until the next window sets it. A pending command that falls
   due at the very moment a window opens is carried out after it and wins.
4. **A manual off holds until the next window.** If the target is off during a window,
   whoever turned it off (you at the wall, its own app, an automation, "Run for" 0, the end
   of a countdown you started), the window does not turn it back on; the next window does.
   This is stored, so a restart does not bring the window back either. Two things start the
   target again, because they are your acts too: editing the interval so that its window
   moves out of the present moment (the edit makes a new window, which begins at its own
   start), and switching the interval off and on.
5. **Turning the target on by hand once a window has opened is an ordinary manual start.**
   In strict mode it runs for the default duration, in loose mode without a countdown; the
   window does not stretch it to its own end.

### Settings of an interval

An interval can turn the target on the way you want, with the same settings as a pending
command: cooling at 24 degrees on the air conditioner, a brightness for a light. The form
offers only what the target says it can do.

- The settings go out when the window opens and **Timerify turns the target on for it**: the
  target is off, or a turn-off is on its way and the target has not yet answered. An air
  conditioner gets its mode, then its temperature, then its fan mode.
- **A target that is already running when a window opens gets no settings**, only the
  extended countdown: someone chose the current ones. That includes a run started by another
  interval, and a target that is not on yet but whose turn-on is still wanted (it is on its
  way, it waits for an unavailable target, or the call failed). The same goes for a target
  that was unavailable when the window opened and is already on when it comes back.
- A target that is unavailable at the start keeps the countdown, and is turned on with the
  settings when it is back, if it is off then and the window is still open.
- A window never replaces the settings of a command that is waiting for the target: the
  command's turn-on is still wanted, and its settings stay.
- If the turn-on goes through and a settings call fails, the settings are sent again, with
  the same limits as for a refused turn-on, provided the target reports that it is on in
  response to Timerify's own call. A device that only reports later, when it is polled, has
  the rest of the settings dropped: Timerify does not push settings onto a target that
  someone else may have set.
- Editing an interval while its window is open does not push the new settings onto the
  running target; they are used from the next window.

### Restarts

- Windows are stored with the timer, with whether each has started and whether you stopped
  it.
- A window that is open when Home Assistant starts and had already started leaves the
  countdown as it was: it still ends where the window ends.
- A window that began while Home Assistant was down, and was not applied yet, is applied at
  start-up for the rest of its window: the boiler turns on when it is back.
- A countdown that ended while Home Assistant was down turns the target off, as above. When
  one window ended and the next began during a long outage, the target is not switched off and
  on for it.
- An interval you switched off stays off.

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

## Voice and AI

Timerify answers to Assist, Home Assistant's voice assistant, in English and Russian.
Install Timerify as described under [Installation](#installation) (HACS as a custom
repository, or by hand) and add your timers. The built-in conversation agent then
understands a fixed set of sentences, once you give it them under [The Voice settings
entry](#the-voice-settings-entry); an LLM agent is given tools and chooses its own words.
Both go the way the services go: a timer changes only through its own countdown, so "turn
on the boiler for 10 minutes" said aloud and `timerify.run` do the same thing and are
refused for the same reasons.

### What can be said

A sentence names a device that has a timer, and the device must be exposed to Assist
(see [Exposure](#exposure)). The examples say "the boiler"; say the name as Home
Assistant shows it, or one of its aliases. Each sentence has more wordings than the table
shows: the English "the" is optional, the verbs have synonyms, and a duration is hours,
minutes or both ("half an hour" and "an hour and a half" as well). The complete
sentences are the files under `custom_components/timerify/sentences/<language>/`.

| What | English | Russian, transliterated |
| --- | --- | --- |
| How long is left | how much time is left on the boiler | skol'ko vremeni ostalos' u taymera Boiler |
| Run for a time | turn on the boiler for 10 minutes | vklyuchi Boiler na 10 minut |
| Set the countdown | set the boiler timer to 90 minutes | postav' taymer Boiler na 90 minut |
| Run with settings | turn on the AC for an hour, cooling, 24 degrees | vklyuchi AC na chas v rezhime okhlazhdenie 24 gradusa |
| Run at a level | turn on the lamp for 20 minutes at 40 percent | vklyuchi Lamp na 20 minut na 40 protsentov |
| Add time | add 15 minutes to the boiler | dobav' 15 minut k taymeru Boiler |
| Stop | stop the boiler timer | ostanovi taymer Boiler |
| Turn on or off by name | turn on the boiler, turn off the boiler | vklyuchi Boiler, vyklyuchi Boiler |
| Turn on later | turn on the boiler in 15 minutes for an hour | vklyuchi Boiler cherez 15 minut na chas |
| Turn off later | turn off the boiler in 20 minutes | vyklyuchi Boiler cherez 20 minut |
| What is planned | what is planned for the boiler | chto zaplanirovano u taymera Boiler |
| Cancel what is planned | cancel all planned commands for the boiler | otmeni vse zaplanirovannye komandy u taymera Boiler |
| Cancel the next one | cancel the next planned command for the boiler | otmeni blizhayshuyu zaplanirovannuyu komandu u taymera Boiler |
| Switch the schedule | turn off the boiler schedule, turn on the boiler schedule | vyklyuchi raspisanie taymera Boiler, vklyuchi raspisanie taymera Boiler |
| Switch one interval | turn off the Morning schedule of the boiler | vyklyuchi raspisanie Utro taymera Boiler |

The Russian column is transliterated because this README is English only; the real
sentences are in `custom_components/timerify/sentences/ru/`. A Russian name is not
declined, so the sentences put it after a noun ("taymera Boiler"), where the nominative
is natural, and the answers start with the name and a colon.

What each does:

- **How long is left** says the time left and when the target turns off, or that it is
  off, or on without a timer.
- **Run for a time** is the same as setting "Run for": the countdown is that long, from
  one minute to 24 hours, and replaces the one that runs. A thermostat, a water heater,
  a light, a fan or a humidifier takes its settings in the same sentence, in any order:
  the HVAC mode ("cooling", "heating", "auto", ...), a temperature ("24 degrees", "at
  22.5"), a percentage ("at 40 percent"), and a mode of the device ("eco", "high").
  Only a device that has a setting is understood to be given it, and the request is
  checked against the device as `timerify.run` checks it: what it cannot do is refused,
  by voice and by tool alike.
- **Add time** extends a running countdown, or turns the target on for that long. A
  countdown never ends more than a day ahead: adding 30 hours gives a day, and the
  answer says when it ends.
- **Stop** sets the countdown to zero and turns the target off.
- **Turn on or off by name** is the bare "turn on the boiler" and "turn off the boiler".
  For a device that has a timer these are Timerify's commands, not Home Assistant's: on
  is the turn-on of the timer's [mode](#modes) (strict mode: for the default duration;
  loose mode: on, without a countdown), and off stops the countdown. A target that is
  unavailable keeps the wish and is switched when it is back. Phrasings with an area, a
  floor or a kind of device ("turn off the lights in the kitchen") stay with Home
  Assistant, and so does every device without a timer.
- **Turn on later** and **turn off later** are Home Assistant's own delayed commands,
  which Timerify takes over for the devices that have a timer, in every shape Home
  Assistant has for them in both languages (the delay before or after the command, in
  hours, minutes and seconds, "in" or "after" in English, and the English form that
  has the name last, "in 15 minutes boiler"). A command to turn on is kept as a
  [pending command](#pending-commands): it survives a restart, shows on the Next command
  sensor and can be cancelled. It may say how long the target then runs and its settings
  ("turn on the AC in 15 minutes for an hour, cooling, 24 degrees"). A command to turn off
  sets the countdown of a target that is running, with or without a countdown, to end
  then, replacing its end; for a target that is off nothing changes, and the answer says
  so. A delay is at most a week for a command to turn on and a day for one to turn off,
  and a timer keeps at most 20 pending commands; each is refused with a message when it
  is too much. Devices without a timer keep Home Assistant's delayed commands untouched.
- **What is planned** lists the pending commands, in the order they are due, by the
  time they run at and for how long. Their settings are not said.
- **Cancel** takes away all of them (the default) or the next one; saying "the next" again
  takes the one after. A cancelled command never runs. An id cannot be said, so cancelling
  one particular command is for an LLM agent or the `timerify.cancel_command` service.
- **Switch the schedule** switches every interval of the timer's schedule on or off, as
  its [switches](#the-switch-of-an-interval) do, and has the same effects: switching off
  while a window runs stops the timer, switching on inside a window runs the target for
  the rest of it. To switch one interval, say its title ("the Morning schedule of the
  boiler"): give the intervals titles of your own, because the title an interval is
  given when it is made ("06:30-07:15, Sun-Thu") cannot be said to the built-in agent. A
  title that two intervals share switches both. A title that another timer has and this
  one does not is refused, and the answer names the first five titles this one has.

The answers are in the language of the request: a regional language such as `en-GB` uses
the sentences of its language, and one Timerify has no texts for is answered in English.
An answer says what the timer is set to do: while a command waits for an unavailable
target, or a device has ignored one, the answer still gives the wish, and the log has the
rest.

A few things work the way Home Assistant does, not Timerify:

- "Turn it off" and "them" after a question or a command about a device are answered by
  Home Assistant's own commands. They switch the device, and the timer follows, but the
  answer is Home Assistant's, and a target that is unavailable is not given the wish.
- A sentence of Timerify's about a name that is not a device with a timer ("what is
  planned for the fan") is answered with Home Assistant's "not aware of any device".
- A wording that Timerify does not have and that mentions a device with a timer, with
  "turn on" or "turn off" in it ("turn off scheduling for the boiler"), can still be taken
  for a plain turn off of the device by Home Assistant. Use the wordings above.
- If two entities have the same name and one of them has a timer, "turn off the boiler"
  and the other sentences above mean the one with the timer. Likewise, "turn off the
  boiler schedule" means the schedule of the timer called Boiler even when another exposed
  entity is called "Boiler schedule"; that entity is reached by other wordings and the
  interface.

### The Voice settings entry

This is the way to give the built-in agent the sentences, and the one to use unless you
have a reason not to.

1. Open **Settings > Devices & services > Helpers**, choose **Create helper** and then
   **Timerify**, and in the menu choose **Voice settings**. (There is one such entry; the
   menu does not offer it again.)
2. Tick **Add voice sentences for the built-in agent** (it is ticked to begin with) and
   pick the **Languages**: English, Russian, or both. The house language is picked for
   you if Timerify has it, English otherwise.

Timerify then writes `custom_sentences/<language>/timerify.yaml` in your configuration
folder for each language you picked, with the names of your timers' devices in it, and
tells the built-in agent to read the sentences again. A name is listed the way Home
Assistant lists every entity: with its aliases. The file is written again whenever a timer is
added, removed or reloaded, a target is renamed or gets another alias, or a schedule
interval is added, deleted or renamed, and only when its text changes. It also holds the
words for the HVAC modes the devices have, and the modes of fans, humidifiers and the
like, as the devices name them (with a space for an underscore).

- The file is checked with the parser Home Assistant uses (hassil) before it is written:
  every sentence, every list and every name, which has to be matched as it is said. A
  file Home Assistant could not read would break Assist for the whole language, so when a
  check fails Timerify leaves the old file as it is and logs an error.
- Timerify writes only where there is no file or its own, which is the one whose first
  line is `# Managed by Timerify. ...`; a `timerify.yaml` of yours at that path is left
  as it is, that language is not written, and the log says so once.
- The files are removed again when you untick the option, disable the entry, remove the
  entry, or stop picking a language. They stay when Home Assistant restarts or the entry
  reloads.
- The sentences need Timerify's handlers: **remove the Voice settings entry (or untick its
  option) before you uninstall Timerify**. A file that is left behind makes the built-in
  agent fail on every phrase of it that matches, the delayed commands it took over from
  Home Assistant included, until you remove the file by hand.
- Names are listed when a timer is set up or its device changes. A device that changes
  its own list of modes later (a firmware update) is picked up at the next change, and so
  is a new friendly name of a target that is not in the entity registry.

### The manual alternative

If you do not want Timerify to write into `custom_sentences`, copy the sentences yourself
and keep them current. Use **either** this **or** the entry above, never both: the entry
logs a warning when it finds this copy, and two sets of sentences confuse the agent.

For each language you want (`en`, `ru`):

1. Make the folder `config/custom_sentences/<language>/timerify_manual/`.
2. Copy into it the files at the top of the folder `sentences/<language>/` of Timerify
   (in your installation that is `custom_components/timerify/sentences/<language>/`),
   which are `timerify.yaml` and `core_commands.yaml`, and only those: the folder `src/`
   beside them holds the sources they are generated from and must not be copied (Home
   Assistant reads every folder below `custom_sentences/<language>/`).
3. Add a file of your own, `timerify_names.yaml`, that lists the devices (and, to say an
   interval by its title, the titles):

```yaml
language: en
lists:
  timerify_target:
    values:
      - in: "boiler"
        out: "Boiler"
        context:
          domain: switch
      - in: "AC"
        out: "AC"
        context:
          domain: climate
  timerify_interval:
    values:
      - in: "Morning"
        out: "Morning"
```

   - `in` is the name as it is said, with the punctuation Home Assistant ignores
     removed; if it has any of the characters `( ) [ ] { } < > | @`, put a backslash
     before each of them and before every backslash in it, because Home Assistant would
     read them as a sentence template. `out` is the name as Home Assistant shows it.
   - Give each name its `context: domain`, the part of the entity id before the dot.
     Settings are said only of a device that has them: a thermostat's HVAC mode and
     temperature need `climate`, a water heater's temperature `water_heater`. A name
     with no domain gets the sentences that fit every device and nothing more.
   - `timerify_interval` is needed only to switch a schedule interval by its title
     (the whole schedule needs none). To say the fan mode of a thermostat, the preset of
     a fan or the mode of a humidifier, list the values under `timerify_mode` the same
     way: `in` the mode as it is said, an underscore as a space, and `out` the mode as the
     device names it. The words for the HVAC modes are in `timerify.yaml` already, for
     every mode, and a mode the device does not have is refused when it is said.
4. Restart Home Assistant, or call `conversation.reload`.

Do it again after every update of Timerify (the sentences change between versions) and
after every rename of a device or an interval. A file that is not valid breaks Assist for
the whole language, which the entry above protects you from by checking before it
writes; check yours by reading the log after the reload.

### Exposure

Assist can control only what is exposed to it. Home Assistant exposes new entities of some
kinds by default (among them switches, lights, fans, climate entities, humidifiers and
water heaters) and not those of others (an input boolean, a group). Open **Settings >
Voice assistants > Expose** and expose the targets of your timers that are not. A device that
is not exposed is refused as a device Assist does not know, and an LLM agent is told only
about the exposed ones.

Timerify's own entities, the `number`, the sensors and the interval switches, are not
exposed by default: the switch of an interval is an entity of the configuration category,
which Home Assistant leaves out. An interval switch that Home Assistant already decided
to expose before version 0.4.0 stays exposed; take it away under **Settings > Voice
assistants > Expose**.

### LLM agents

An LLM agent that uses the Assist API is offered these tools while a device with a timer
is exposed to its assistant, and the prompt names those devices. A tool takes the device's
name as its argument and does what the sentence above does, through the same code; a
refusal comes back as text in the language of the request.

| Tool | What it does |
| --- | --- |
| `timerify__time_left` | How long is left, and when the device turns off. |
| `timerify__run` | Turn on for `hours` and `minutes` (neither: for the usual time), with settings. |
| `timerify__add_time` | Add `hours` and `minutes` to the countdown. |
| `timerify__stop` | Stop the timer and turn the device off. |
| `timerify__delayed_command` | Plan to turn on or off (`action`) later, after `delay_hours`, `delay_minutes` and `delay_seconds` or at `at`, a date and time on the house's clock, never both. A turn-on may say how long it then runs (`hours`, `minutes`) and its settings; it may be up to a week ahead, a turn-off up to a day. |
| `timerify__list_commands` | The planned commands, with the ids that cancel them. |
| `timerify__cancel_commands` | Cancel `all` or the `next` command, or one by `command_id`. |
| `timerify__set_schedule` | Switch the schedule, `enabled` true or false, or one interval by its title. |

An agent can plan a command at a clock time, which the built-in agent's sentences
cannot. An empty `interval` means the whole schedule, as an empty argument is no
argument to any tool.

### What is not by voice

- **A command at a clock time** ("turn on the boiler at 7:30"): the sentences take a delay
  only; an LLM agent has `at`.
- **Taking time off** ("10 minutes less"): set the countdown to the new length instead.
- **Planning a command to turn off** ("turn off in 20 minutes" sets the countdown). A
  pending command to turn off is made with `timerify.add_command`.
- **Cancelling one command by its id**: only an LLM agent or the service has the id.
- **An interval by the title it is made with**: rename it first.
- **The settings of a device in Russian** that its device names in Latin ("eco", "high"):
  they are said as written. The HVAC modes have Russian words.
- Two thermostats with different HVAC modes: the words are the modes of all of them, so
  saying a mode only one of them has to the other is refused with the list of the modes
  it has.

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
   **Timerify**, and in the menu choose **Add a timer**. (The **Add integration** button
   on the Integrations tab lists it too, as "Timerify (Helper)". The other item of the
   menu, **Voice settings**, is described under [Voice and AI](#voice-and-ai).)
2. Pick the entity, and the mode.
3. In strict mode, set the default duration.
4. If your house has a Workday sensor, pick the one this timer follows, or leave it empty;
   see [Days](#days).

The timer appears on the entity's device page. To change the mode, the default duration or
the Workday sensor later, open the timer on the Timerify integration page and choose
**Configure**. The entity itself cannot be changed: add a timer for the other entity
instead. Schedule intervals are added on the same page; see [Schedules](#schedules).

Renaming the target, or moving it to another device, is followed: the timer keeps running.

## What is not here yet

Planned for later versions, none of it available in 0.4.0: a dashboard card. What cannot
be said to Assist is listed under [What is not by voice](#what-is-not-by-voice).

## Verification

What 0.4.0 was checked with before release:

- The test suite (`uv run pytest`): every rule above is a scenario, with time moved
  explicitly, among them the days the clock changes, Home Assistant down overnight, a
  Workday sensor that is away, and the real Workday integration for the Israeli week. The
  voice sentences are said to Home Assistant's real built-in agent, in both languages, and
  the LLM tools are called through the real Assist API; the sentence files are generated
  from their sources and checked against the shipped ones.
- `hassfest`, Home Assistant's own validation of an integration, reports no problems.
- A smoke test in a real Home Assistant 2026.10.4 container (see below): the timer is
  added through the config flow, "Run for" 2 minutes turns the target on and off on time,
  and a 3 minute countdown survives a restart of the container and still ends on time. A
  pending command turns a switch that sits on a device on at its time and off a minute
  later, a thermostat run for a minute with a mode and a temperature is set to both and
  switched off at the end, and a schedule interval added through the interval form turns
  a switch on at its start and off at its end, with the interval's own switch on. The
  Voice settings are added through the config flow and the built-in agent is talked to
  over the REST API: it refuses a device that is not exposed to Assist, and once the
  device is exposed, "turn on ... for 2 minutes", "how much time is left", "turn off in 1
  minute", a bare "turn on" and a bare "turn off" each give the answer the sentence is
  meant to and leave the switch in the state the REST API reports.

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
checks that a 2 minute countdown turns the first switch on and off, that a schedule
interval for today's weekday, added through the interval form to begin in a minute or two,
turns the first switch on at its start and off two minutes later (its switch is on, on the
timer's device), that the built-in agent, given the Voice settings through the config flow
and talked to over the REST API, runs, shortens and stops the first switch by sentences,
that a 3 minute countdown survives a restart of the container, that a pending command
turns the demo switch on at its time and off a minute later, and that the thermostat takes
the mode and the temperature of a run. It takes about fifteen minutes.

```sh
uv run python scripts/smoke/run.py
```

Add `--keep` to leave Home Assistant running afterwards, with a countdown on, at
`http://localhost:18123`; the script prints the address of the device page and the login.
Stop it with `docker compose --file scripts/smoke/compose.yaml down`.

## License

MIT
