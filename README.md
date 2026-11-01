# Timerify

Timers for any Home Assistant entity, without writing automations.

Timerify attaches a countdown to an entity you already have, the way Powercalc attaches a
virtual power sensor to a device. A boiler that is just a smart switch gains, on its own
device page, a "Run for" control: set 10 minutes and the boiler turns on and turns itself
off when the countdown ends.

![The device page of a timer: Run for and Ends at, with a countdown running](docs/screenshots/phase-1-device-page.png)

> **Status:** version 1.0.0, the first release. The core timer, settings for turning on
> ("cooling, 24 degrees"), pending commands ("turn on in 15 minutes"), weekly schedules
> ("working days 06:30 to 07:15"), voice control through Assist ("turn on the boiler for
> 10 minutes", "how long is left on the boiler"), a dashboard card and a runtime counter
> ("how many hours did the boiler run this week") work and are described below. See
> [What is not here yet](#what-is-not-here-yet) for what they leave out.

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
- A card on a dashboard shows the countdown, and its pop-up runs, extends and stops the timer;
  see [Dashboard card](#dashboard-card).

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
after it; if the target is linked to a device later, the entities move to that device with
their names and entity ids, and the device that was made for them is removed.

| Entity | What it shows |
| --- | --- |
| `number` Run for | Minutes left, rounded up. Writing it starts, changes or stops the countdown. |
| `sensor` Ends at | The moment the countdown ends; unknown while no countdown runs. The dashboard shows it as "in 7 minutes" by itself. Its attribute `started_at` is the moment the countdown began (empty while none runs); the card's fill is drawn from it. |
| `sensor` Next command | The moment the next pending command is due; unknown while there is none. See [Next command sensor](#next-command-sensor). |
| `switch` Schedule *06:30–07:15, Sun–Thu* | One per schedule interval: on while the interval is in use, off to skip it. See [The switch of an interval](#the-switch-of-an-interval). |
| `sensor` Runtime | Only when you ask for it: the minutes the target was on, a total that only goes up. See [Runtime counter](#runtime-counter). |

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
  time.** Without minutes, a command to turn on runs a target that is off for the default
  duration in strict mode and without a countdown in loose mode; a target that is running
  keeps its countdown, and the command still sets its settings. A command to turn off
  turns the target off and stops the countdown. A command to turn on that comes due at the
  very moment a countdown ends keeps the target on instead of switching it off and on.

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
only. If you rename the sensor, the timer follows it to the new entity id and reloads, and
a window that is open stays open. If you delete the sensor, the timer keeps its id and
waits as it does for a sensor that is away (below) until you pick another one in
**Configure**.

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
- Switch it on while the window is open and the target runs for the rest of the window,
  unless the timer already ends later (rule 1 below). An interval that is on already is
  left as it is, so a target that was turned off during its window stays off until the
  next one (rule 4 below).
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
   due at the very moment a window opens is carried out after it and wins. Turning on,
   without a duration, a target that already runs changes nothing, so it is not a change
   of yours.
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
without it a target that is off runs for the default duration in strict mode and without a
countdown in loose mode, and one that is running already keeps its countdown. Settings go
along, also to a target that keeps its countdown; a setting the target does not support is
refused before anything happens.

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
declined, so where a sentence would decline it, the sentences put it after a noun
("taymera Boiler") and the nominative is natural; and the answers start with the name and
a colon.

What each does:

- **How long is left** says the time left and when the target turns off, or that it is
  off or unavailable, or on without a timer. It says "unavailable" for a target that
  does not answer (unavailable or unknown) when no timer wants it on.
- **Run for a time** is the same as setting "Run for": the countdown is that long, from
  one minute to 24 hours, and replaces the one that runs. Said longer, as far as a week
  ("for 30 hours"; minutes beyond a day in digits, "for 2000 minutes"), the sentence is
  understood and refused with the limit, and nothing is turned on; a count beyond a week
  is not understood at all. A thermostat, a water heater,
  a light, a fan or a humidifier takes its settings in the same sentence, in any order:
  the HVAC mode ("cooling", "heating", "auto", ...), a temperature ("24 degrees", "at
  22.5", "120 degrees" for a water heater in Fahrenheit; any number up to 250, in digits
  or words, which the device then accepts or refuses by its own range), a percentage
  ("at 40 percent"), and a mode of the device ("eco", "high").
  Only a device that has a setting is understood to be given it, and the request is
  checked against the device as `timerify.run` checks it: what it cannot do is refused,
  by voice and by tool alike.
- **Add time** extends a running countdown, or turns the target on for that long. A
  countdown never ends more than a day ahead: adding 30 hours (any count up to a week)
  gives a day, and the answer says when it ends.
- **Stop** sets the countdown to zero and turns the target off.
- **Turn on or off by name** is the bare "turn on the boiler" and "turn off the boiler".
  For a device that has a timer these are Timerify's commands, not Home Assistant's: on
  turns a device that is off on as the timer's [mode](#modes) says (strict mode: for the
  default duration; loose mode: on, without a countdown), and leaves a device that is
  running as it is: its countdown keeps its end, whoever set it, and the answer says how
  long is left. Off stops the countdown. A target that is unavailable keeps the wish and
  is switched when it is back. Phrasings with an area, a floor or a kind of device ("turn
  off the lights in the kitchen") stay with Home Assistant, and so does every device
  without a timer.
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
  is too much. By voice the hours, the minutes and the seconds of a delay are each at most
  100, as in Home Assistant's own sentences, and a longer delay is not understood: use the
  tool or the service for it. Devices without a timer keep Home Assistant's delayed
  commands untouched.
- **What is planned** lists the pending commands, in the order they are due, by the
  time they run at and for how long. Their settings are not said.
- **Cancel** takes away all of them (the default) or the next one; saying "the next" again
  takes the one after. A cancelled command never runs. An id cannot be said, so cancelling
  one particular command is for an LLM agent or the `timerify.cancel_command` service.
- **Switch the schedule** switches every interval of the timer's schedule on or off, as
  its [switches](#the-switch-of-an-interval) do, and has the same effects, on the same
  conditions (rules 1 to 4 of [how the schedule and your own changes
  meet](#how-the-schedule-and-your-own-changes-meet)). Switching off while a window runs
  stops the timer only if the schedule is running it: its end came from that interval and
  nobody has changed the timer since (otherwise it is yours and stays), or another open
  window takes it over. Switching on inside a window runs the target for the rest of it,
  unless the timer already ends later, and an interval that is on already is left as it
  is, so a target that was turned off during its window stays off until the next one. To
  switch one interval, say its title ("the Morning schedule of the boiler"): give the
  intervals titles of your own, because the title an interval is given when it is made
  ("06:30-07:15, Sun-Thu") cannot be said to the built-in agent. A title that two
  intervals share switches both. A title that another timer has and this one does not is
  refused, and the answer names the first five titles this one has.

The answers are in the language of the request: a regional language such as `en-GB` uses
the sentences of its language, and one Timerify has no texts for is answered in English.
An answer says what the timer is set to do: while a command waits for an unavailable
target, or a device has ignored one, the answer still gives the wish, and the log has the
rest. The question about the time left is the exception when nothing is wanted on: then
it says what the target shows, off or unavailable.

A few things work the way Home Assistant does, not Timerify:

- "Turn it off" and "them" after a question or a command about a device are answered by
  Home Assistant's own commands. They switch the device, and the timer follows, but the
  answer is Home Assistant's, and a target that is unavailable is not given the wish.
- A sentence of Timerify's about a name that is not a device with a timer ("what is
  planned for the fan") is answered with Home Assistant's "not aware of any device".
- A wording that Timerify does not have and that mentions a device with a timer, with
  "turn on" or "turn off" in it ("turn off scheduling for the boiler", "turn off the boiler
  in 2 days"), can still be taken for a plain turn off of the device by Home Assistant,
  which turns it off at once. Use the wordings above.
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
is not exposed is refused ("Sorry, Boiler is not exposed"), and an LLM agent is told only
about the exposed ones.

Timerify's own entities, the `number`, the sensors and the interval switches, are not
exposed by default: the switch of an interval is an entity of the configuration category,
which Home Assistant leaves out.

### LLM agents

An LLM agent that uses the Assist API is offered these tools while a device with a timer
is exposed to its assistant, and the prompt names those devices. A tool takes the device's
name as its argument and does what the sentence above does, through the same code; a
refusal comes back as text in the language of the request.

| Tool | What it does |
| --- | --- |
| `timerify__time_left` | How long is left, and when the device turns off; or that it is off, unavailable, or on without a timer. |
| `timerify__run` | Turn on for `hours` and `minutes` (neither: a device that is off runs for the usual time, and one that is running keeps its countdown), with settings. |
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

## Dashboard card

Timerify brings a card for one timer, `custom:timerify-card`. It shows the countdown at a
glance, and a tap opens a pop-up where you run the timer for a set time, add or take off
minutes, stop it, switch the intervals of its schedule and cancel pending commands. It has two
layouts and a visual editor.

### Loading the card

There is nothing to add. Timerify serves the card and tells Home Assistant to load it on every
dashboard, so there is no resource to create under **Dashboards**, and dashboards in YAML mode
have it too. Home Assistant reads the list of modules to load when a page loads, so **refresh
the browser once after installing or updating Timerify**.

**Known issue on Home Assistant 2026.10.x.** On the first load of Home Assistant in a browser
that has not cached its frontend yet (a first visit, after the site data was cleared, and the
first load after the frontend was updated), a card that an integration loads can be missing:
the dashboard shows "Configuration error" and "Custom element doesn't exist: timerify-card".
Refresh the page once more and the card is there. This is a fault of Home Assistant's frontend
([home-assistant/frontend#53890](https://github.com/home-assistant/frontend/issues/53890)) that
every such card meets. It is fixed in the frontend from version 20261028.0 on
([pull request #54444](https://github.com/home-assistant/frontend/pull/54444)), which Home
Assistant 2026.11 is expected to carry. Timerify does not work around it. Version 1.0.0
still needs only Home Assistant 2026.10.4; raising the minimum to 2026.11 would remove the
problem ([issue #7](https://github.com/klimofey/timerify/issues/7)).

### The two layouts

The **pill** is a card one row high. Its fill grows from the left and shows the share of the
countdown that is left: full when the countdown starts, empty when it ends. On it are the icon
of the target, its name, and the time left with the moment the countdown ends; when nothing
counts, the state of the target stands in their place. An optional chip, "+15 min" in the
picture, adds time without opening the pop-up.

![The pill layout: a countdown at 30:00 with two thirds of the fill left and a chip, above a timer that is off](docs/screenshots/card-pill.png)

The **round** tile is made to sit several in a row. A ring shows the same share; the time left
is in its centre while the countdown runs, and the icon of the target otherwise. The name is
below. The round tile has no chip, and it can be long-pressed; see
[The long press of the round tile](#the-long-press-of-the-round-tile).

![The round layout: a ring two thirds full around 30:00, beside a timer that is off](docs/screenshots/card-round.png)

- The name and the icon are the target's. The icon follows the target's state, as it does on any
  card. Both can be set in the card's configuration.
- A countdown that runs on without an end (loose mode, a target that is on with no countdown)
  shows a full fill and a full ring; the pill says the state of the target in words, and the
  round tile has them for screen readers only. An idle timer shows an empty fill and an empty
  ring.
- A timer whose number is unavailable shows that, and its chip, presets, plus, minus, Stop and
  cancel buttons are off (see [The pop-up](#the-pop-up)). If the
  entity of the card does not exist, or is not the "Run for" number of a Timerify timer, the card
  says so and names it, and finds its timer again by itself when the entity is back. After you
  rename the number, point the card at its new entity id. If the number is a timer's but the
  timer cannot be shown, because its target or one of its two sensors is missing from the
  registry, the card says that and sends you to the timer's page to see why, whatever the
  state of the number. Right after you add a timer the line can show for a moment, and it
  goes away by itself.
- The card never goes quiet when it cannot work. A user who may not see the timer is told so
  (see [Permissions](#permissions)). The card needs the timer's two sensors, **Ends at** and
  **Next command**, and tells you when you have disabled one of them. With **Ends at**
  disabled, the card shows only a warning that names the sensor and says to enable it, since
  without it the card has no countdown to show; with **Next command** disabled, the card works
  and the pop-up says in the place of the pending commands that they are hidden, naming the
  sensor. Enable the sensor in its entity settings: Home Assistant reloads the timer about half
  a minute later, and the card returns by itself.
- A countdown carries on across a restart of Home Assistant or a lost connection, to the same
  end, and the card asks for its timer again when the connection returns.
- In a dashboard with sections the pill starts 6 columns wide and one row high and can be made
  as narrow as 3 columns; the round tile starts 3 columns wide and 2 rows high and can be made
  2 columns wide or 3 rows high.

### Add the card

Edit a dashboard, choose **Add card** and find **Timerify** among the cards. The picker shows
the first timer you have, and the editor opens with the form below. Or write the card in YAML.
Every option is shown here with its default:

```yaml
type: custom:timerify-card
entity: number.boiler_run_for             # required: the "Run for" number of the timer
layout: pill                              # pill (the default) or round
name: Boiler                              # default: the name of the target
icon: mdi:water-boiler                    # default: the icon of the target, which follows its state
presets: ["15", "30", "45", "60", "120"]  # the default: the minutes the pop-up offers
chip: 15                                  # no chip by default: the pill's "+15 min" chip
```

| Option | Default | What it is |
| --- | --- | --- |
| `entity` | none, required | The "Run for" `number` of a timer. The card finds the rest of the timer from it, never by device, so two timers on one device are told apart. |
| `layout` | `pill` | `pill` or `round`. |
| `name` | the target's name | Overrides the name. |
| `icon` | the target's icon | An icon such as `mdi:water-boiler`, which does not follow the state. |
| `presets` | 15, 30, 45, 60 and 120 | The durations the pop-up offers, in whole minutes from 1 to 1440, each shown once, in the order given. Numbers and text of digits (`"30"`) both work. An empty list means the defaults. |
| `chip` | none | Whole minutes from 1 to 1440, added to the countdown by the pill's chip. The round tile ignores it. |

An option the card does not know is ignored. A value it cannot use is shown as a message on the
card that says what is wrong.

The visual editor has a field for each option. It offers only the "Run for" numbers of Timerify
timers, and a card added from the picker is written with `layout: pill` and the five default
presets, so you see them. A few things about the editor:

- It writes presets as text (`"15"`). Write them as text in YAML too if you edit the card in the
  form afterwards: a list of numbers (`[15, 30]`) is shown in the form as bare chips ("15", not
  "15 min"), and its drop-down offers the defaults again even when they are in the list;
  picking one adds a second copy, which the card ignores.
- Taking the last preset away leaves the list empty, which means the defaults.
- A value the form accepts but the card cannot use, such as a preset of 0, stays in the form
  while the preview shows the card's message. Only a value of the wrong kind (presets that are
  not a list) sends the editor to YAML.
- A card written by hand without `layout` is a pill, but the form does not preselect it:
  Home Assistant's editor does not apply the defaults of a form.
- The names of the fields are translated by Home Assistant itself. The names of the two layouts,
  the labels of the preset options and the text under them are in the language of the last card
  the page loaded, and in English before any card has.

### The pop-up

A tap anywhere on the card opens it, the border included, except on the chip, which has its own
job. The card is a button for the keyboard and assistive technology too: focus it with Tab and
press Enter or Space. The pop-up is a modal dialog; Escape, the **Close** button and a click on
the dimmed page behind it close it. From top to bottom it holds:

- **The time left**, and when it ends, while a countdown runs.
- **The presets**: pressing one runs the timer for that long, as setting "Run for" does, and
  restarts a countdown that runs.
- **Take off 5 minutes, add 5 minutes, and Stop.** Taking time off is offered while a countdown
  runs. Adding time to a timer that is idle starts it, as `timerify.add_time` does. Stop is offered
  while the timer runs, with a countdown or without; it turns the target off and ends the
  countdown.
- **Schedule**, when the timer has intervals: a switch for each, named by its title, which
  turns the interval's [switch](#the-switch-of-an-interval) on and off. Creating and editing
  intervals is not done here; use the timer's page. An interval whose switch is unavailable is
  shown as that and cannot be pressed.
- **Pending commands**, when there are some: each as "On at 7:30 AM for 1 hr" or "Off at Tue
  7:00 AM", with its settings ("Cool, 24 °C") and a × button that cancels it. If the **Next
  command** sensor is disabled, one line stands here instead and says that the commands are
  hidden because of it.
- **Settings**, a link to the timer's page among the integration's. Only administrators see it.
  It opens in the same tab and closes the pop-up; Ctrl, Cmd or Shift with the click open it in
  a new tab or window, and the pop-up stays.

A timer that is unavailable has nothing to act on: its presets, plus, minus, Stop and the cancel
buttons are off, and so is the pill's chip. When Home Assistant refuses an action, it shows its
own error message and the pop-up stays open.

Times follow your profile: its language, its 12 or 24 hour clock and its time zone, the server's
or the browser's. A time on the same day is shown as a time, within the next six days with the
short weekday, and further ahead with the date. Durations such as "1 hr 30 min" are written
for your language.

### The long press of the round tile

Hold the round tile for half a second: the ring starts to pulse, which means that letting go
will act.

- A timer that is idle runs, as `timerify.run` with no duration does. In strict mode the target
  runs for the default duration; in loose mode it turns on with no countdown.
- A timer that runs, with or without a countdown, stops.
- A timer that is unavailable does nothing.

Letting go early is an ordinary tap, and moving off the tile before letting go cancels the
press. The pill has no long press: with a mouse a long press on it is a tap, and with a finger
it does nothing. Keyboard users start and stop through the pop-up.

### What the card does

The card keeps no timer of its own. Everything it shows is read from the states of the timer's
entities, and everything it does is a call to a service or an entity of Timerify's:

| The card shows | Read from |
| --- | --- |
| The countdown and the fill | `sensor` Ends at and its `started_at` attribute, which says when the countdown began |
| The state of the target, the name and the icon | The target's state |
| The intervals | The interval switches |
| The pending commands | The `commands` attribute of `sensor` Next command |

| The card does | By |
| --- | --- |
| Runs for a preset, stops | `number.set_value` on "Run for" (0 stops) |
| Adds or takes off time, the chip | `timerify.add_time` |
| The long press on an idle timer | `timerify.run` with no duration |
| Cancels a command | `timerify.cancel_command` |
| Switches an interval | `switch.turn_on` and `switch.turn_off` on its switch |

To tell which entities belong to its timer, the card asks Timerify through a websocket command,
`timerify/timer`, which answers from the entry and the registry alone, so it gets an answer even
while the timer is starting. The answer also names the settings of the target that are
percentages, so that the card writes a brightness or a fan speed of 40 as a percentage and not
as a bare number. Nothing counts down on the server for the card. The card counts
once a second, only while a countdown runs and the card is on the page, with the browser's clock
against the end time that the server reports. A clock that is wrong therefore changes the time
left, never below 0:00, and the fill stays between empty and full; the end time shown, such as
"until 4:42 PM", is the server's, and what you press always goes to the server.

### Permissions

The card and its pop-up work for every user who may see and control the timer's entities,
administrators or not. A user who is not an administrator sees everything but the Settings link:
that page is for administrators only. Timerify's websocket command is open to every user and
tells a user only what the user may read: a user who may not read the number, the target or
the two sensors of the timer gets no answer, and the card shows, in place of the timer, the
warning "You are not allowed to see the timer", followed by the entity id of its number, in the
user's language; an interval whose switch the user may not read is left out of the pop-up.

The card's module is served to everyone, because the browser loads it before anyone has logged
in.

### Languages

The card's own words, its buttons and messages, are in English and Russian, in the language of
your profile; for any other language they are in English. Times, durations and numbers are
written by the browser for your language, so they are right in every language. The names and
states of entities are Home Assistant's.

## Runtime counter

A timer can add up how long its target was on, to answer "how many hours did the boiler run
this week" without an automation. It is off to begin with. Tick **Count runtime** when you add
the timer, or later under **Configure**, and the timer gains a `sensor` **Runtime** on the
same device.

- **Every "on" of the target counts**, whoever caused it: Timerify, the target's own app, a
  switch on the wall, an automation. "On" is judged the way the rest of Timerify judges it: a
  climate or water heater entity is on in any mode but off, a media player when it is neither
  off nor in standby, and any other target when it reports `on`. The counter only watches. It
  never starts or stops the target, and it does not look at the timer's countdown, pending
  commands or schedule.
- **The value is in minutes**, a total that only goes up, and it starts at 0 the first time
  you switch the counter on (a target that is already on counts from that moment, not from
  when its countdown began). It is written at most once a minute, near the end of the
  minute, and only when it has changed; nothing is written when the target turns on or off.
  The sensor shows whole minutes and keeps two decimals in its state. Its display unit can
  be changed in the entity's settings, to hours for instance.
- **Daily and weekly views come from Home Assistant's statistics**, with no extra entities.
  The sensor is a total that only goes up, so Home Assistant keeps its long-term statistics,
  and a run that crosses midnight is split between the two days to within a second, as long as
  the file of the total is written in under half a second (on a stalled disk the last minute
  of a day may fall on the next one). The history graph shows the total; a statistics graph
  card shows the minutes per day or per week:

  ```yaml
  type: statistics-graph
  entities:
    - sensor.boiler_runtime
  chart_type: bar
  period: day
  stat_types: change
  ```

- **Time that Timerify did not see is not counted**: the time Home Assistant is not running,
  and the time the target is unavailable or unknown. When Home Assistant is back, or the
  target reports again, and the target is on, the count goes on from that moment. The total
  never goes down, not even when the clock of the machine is set back, unless its file cannot
  be written (a full or read-only disk), which Home Assistant logs.
- **A restart loses nothing.** The total is stored in a file of its own, before the sensor
  shows it. Stopping or restarting Home Assistant, and reloading the timer, keep every second
  the counter has seen. If Home Assistant crashes, a run loses at most its last minute.
- **Switching the counter off** (untick **Count runtime** under **Configure**) removes the
  sensor from the registry, so that no unavailable entity is left behind. Its statistics stay
  in **Developer tools > Statistics**, where you can clear them. Ticking the box again brings
  the sensor back with the same entity id and customisations, and **continues from the old
  total**; the time in between is not counted.
- **Disabling the Runtime entity** in its own settings is not the same: it pauses the count
  and keeps the total, and enabling it again carries on from there. To stop counting for good,
  switch the option off.
- **There is no reset.** Deleting the timer deletes the total, and a timer added again counts
  from zero. The dashboard card does not show the runtime; use Home Assistant's own cards, as
  above.

## Installation

### With HACS

1. In HACS, open the menu in the top right and choose **Custom repositories**.
2. Add `https://github.com/klimofey/timerify` with the type **Integration**.
3. Find Timerify in HACS, download it, and restart Home Assistant.

Home Assistant 2026.10.4 or newer is required. The dashboard card comes with Timerify; refresh
the browser once after installing or updating, see [Dashboard card](#dashboard-card).

### By hand

Copy the `custom_components/timerify` folder of this repository into the
`custom_components` folder of your Home Assistant configuration, and restart.

## Setup

Add one timer per entity:

1. Open **Settings > Devices & services > Helpers**, choose **Create helper** and then
   **Timerify**, and in the menu choose **Add a timer**. (The **Add integration** button
   on the Integrations tab lists it too, as "Timerify (Helper)". The other item of the
   menu, **Voice settings**, is described under [Voice and AI](#voice-and-ai).)
2. Pick the entity, and the mode, and tick **Count runtime** if you want the timer to add up
   how long the entity is on (it is not ticked to begin with; see
   [Runtime counter](#runtime-counter)).
3. In strict mode, set the default duration.
4. If your house has a Workday sensor, pick the one this timer follows, or leave it empty;
   see [Days](#days).

The timer appears on the entity's device page. To change the mode, the runtime counter, the
default duration or the Workday sensor later, open the timer on the Timerify integration page
and choose **Configure**. The entity itself cannot be changed: add a timer for the other entity
instead. Schedule intervals are added on the same page; see [Schedules](#schedules).

Renaming the target, moving it to another device, or giving it a device when it had none is
followed: the timer keeps running.

## What is not here yet

Every feature planned for Timerify is built. Known faults and wishes are
[GitHub issues](https://github.com/klimofey/timerify/issues), and `docs/followups.md` lists
them by area. What cannot be said to Assist is listed under
[What is not by voice](#what-is-not-by-voice), what the card leaves to the timer's page
(creating and editing schedule intervals) under [The pop-up](#the-pop-up), and what the
runtime counter leaves out (a reset, and a place on the card) under
[Runtime counter](#runtime-counter).

## Verification

What 1.0.0 was checked with before release:

- The test suite (`uv run pytest`): every rule above is a scenario, with time moved
  explicitly, among them the days the clock changes, Home Assistant down overnight, a
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
- A smoke test in a real Home Assistant 2026.10.4 container (see below): the page that Home
  Assistant serves loads the card's module at the address that carries the version of the
  bundle, that address serves the bundle byte for byte, and the card's websocket command
  tells the first timer's entities; the timer is
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
  meant to and leave the switch in the state the REST API reports. The first timer is
  added with the runtime counter ticked, and after its 2 minute run its Runtime sensor
  reads 2 minutes, in minutes, as a total that only goes up.
- A manual walk-through in a real Home Assistant 2026.10.4 container, through the browser;
  its screenshots are in `docs/screenshots/smoke-*.png`. It covered the
  integration page at 1.0.0 with its icon, adding a timer with the runtime counter, a
  countdown running, and a countdown kept across a restart of Home Assistant (the target
  was an `input_boolean`, which restores its state; a demo switch does not, and the timer
  clears the countdown of a target that is no longer on). It went on to a schedule interval
  that turned the target on at its start, two Assist sentences said to the built-in agent,
  and the card in the pill and in the round layout.

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
npm --prefix card run screenshots                   # the two pictures of this README
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
`scripts/harness/configuration.yaml` declares: a switch that sits on no device, the switch of
Home Assistant's demo integration (which sits on a device), and a generic thermostat. It
checks that the page Home Assistant serves loads the card's module and serves its bundle
unchanged, that the card's websocket command knows the first timer, that a 2 minute
countdown turns the first switch on and off, that a schedule
interval for today's weekday, added through the interval form to begin in a minute or two,
turns the first switch on at its start and off two minutes later (its switch is on, on the
timer's device), that the built-in agent, given the Voice settings through the config flow
and talked to over the REST API, runs, shortens and stops the first switch by sentences,
that a 3 minute countdown survives a restart of the container, that a pending command
turns the demo switch on at its time and off a minute later, that the thermostat takes
the mode and the temperature of a run, and that the first timer, added with the runtime
counter ticked, shows its 2 minute run on its Runtime sensor. It takes about fifteen minutes.

```sh
uv run python -m scripts.smoke.run
```

Add `--keep` to leave Home Assistant running afterwards, with a countdown on, at
`http://localhost:18123`; the script prints the address of the device page and the login.
Stop it with `docker compose --project-name timerify-smoke down`.

## License

MIT
