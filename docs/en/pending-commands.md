# Pending commands

A pending command tells a timer to turn its device on or off at a time you choose.

## Turn a device on or off later

A pending command says "at this time, do this". It can turn the device on, or it can turn it off.

- A command to turn on can say for how many minutes the device runs. It can also carry settings, such as cooling at 24 degrees. See [Settings for turning on](timers.md#settings-for-turning-on).
- A timer can hold up to 20 pending commands.
- Each command is at most 7 days ahead.
- Each command can be cancelled on its own.

You make a command with the [**Add command** action](services.md#add-command). By voice, [the built-in agent's](voice.md#the-built-in-agent-and-llm-agents) sentences plan a command to turn on, for example "turn on the boiler in 15 minutes" or "turn on the boiler at 7:30". Its "turn off in 20 minutes" sets the countdown instead. You cancel a command with the [**Cancel command** action](services.md#cancel-command), by voice, or in the [pop-up of the dashboard card](card.md#the-pop-up). The [Actions](services.md), [Voice](voice.md) and [Dashboard card](card.md) pages describe these.

## How a pending command behaves

Some of these rules depend on the timer's mode, which you can read about under [Modes](timers.md#modes). In **Strict** mode a device runs only while a countdown does. In **Loose** mode it may also run without a countdown.

Three rules always hold:

- **A command is carried out at its time, whatever state the device is in then.** Say the air conditioner is already running when "cooling, 24 degrees, for an hour" comes due. It receives cooling and 24 degrees, and the countdown is set to 60 minutes.
- **Using the device by hand does not cancel it.** Between now and then you may turn the device on or off yourself, or a countdown may end. The command stays in place. Only cancelling the command removes it.
- **"Turn on for N minutes" at its time is the same as setting Run for to N minutes at that time.**

What a command does at its time:

- A command to turn on without minutes runs a device that is off to the end of the schedule window. This holds when a window is open at the command's time. In Strict mode the default duration is kept when it ends later. With no window open, a Strict device runs for the default duration. A Loose device runs without a countdown.
- Without minutes, a device that is already running keeps its countdown. The command still sets its settings.
- A command to turn off turns the device off and stops the countdown.
- A command to turn on that comes due at the very moment a countdown ends keeps the device on. The device is not switched off and on.

## Restarts and outages

- Commands are stored on every change, and they survive a restart.
- A command that came due while Home Assistant was down is carried out at start-up for what is left of its run. Say you asked at 07:00 for a run of 60 minutes, and Home Assistant is back at 07:20. The device then runs for 40 more minutes.
- If nothing is left of the run, the command is dropped and the log says so. This is an info line: to see it, choose **Enable debug logging** on the Timerify integration page.
- A command to turn off is carried out however late. So is a command to turn on without a countdown in Loose mode. That is one with no window open at its time.
- If several commands came due, they are applied in time order. Only the final state reaches the device. An "on" and the "off" after it that both came due switch nothing.
- A command that comes due while the device is unavailable changes the countdown at once. The device is switched when it reports again, if the command still matters by then. A run that is already over is never started.

## The Next command sensor

The **Next command** sensor of a timer shows when the next pending command is due, as a time. It is unknown while there is none.

The sensor also lists all the pending commands, the earliest first, for dashboards and templates. The list is not kept in the history database. This is what it looks like:

```yaml
commands:
  - id: 0f5c1e2a7d9b4c3e8a6b1d2c3e4f5a6b # What the Cancel command action takes.
    at: "2026-01-05T07:15:00+00:00" # The time, in UTC.
    action: "on"
    minutes: 60 # Null when the command gives no minutes.
    settings: # Empty when the command carries none.
      hvac_mode: cool
      temperature: 24.0
```

---

[All pages](README.md) · [Back to the README](../../README.md)
