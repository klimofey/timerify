# Automations

You can use Timerify in an automation without typing YAML. You pick the device, then a Timerify action.

## Pick the device

1. Open **Settings > Automations & scenes**. Choose **Create automation**, then **Create new automation**.
2. Under **Then do**, choose **Add action**. Open the **By target** tab.
3. Pick the device, for example the boiler.
4. The list shows Timerify's actions with the device's other ones. Choose one.

A device that Timerify made for an entity that is on no device works the same.

The **Device** group in the same dialog does not list Timerify's actions. It lists only what the device's own integration offers, and the actions of its kinds of entities, such as setting the value of **Run for**. Home Assistant builds that list itself, so Timerify's actions are under **By target** instead.

## Actions

| Action | What it does |
| --- | --- |
| **Run** | Turns the device on, for the minutes you give, up to a day. |
| **Add time** | Moves the end of the countdown, up to a day either way. |
| **Stop** | Ends the countdown and turns the device off. It also turns off a device that runs without a countdown. |

**Add command** and **Cancel command** are there too. The [Actions](services.md) page lists every field.

For example, to run the boiler for 20 minutes, pick **Run** and set **Minutes** to 20.

## A device with two timers

Say a relay has two channels, each with its own timer. An action aimed at the device acts on both timers. To aim at one, change the target to that channel's **Run for** entity.
