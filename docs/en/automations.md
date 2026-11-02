# Automations

You can use Timerify in an automation without typing YAML. You pick the device, then a Timerify action or trigger.

## Pick the device

1. Open **Settings > Automations & scenes**. Choose **Create automation**, then **Create new automation**.
2. Under **Then do**, choose **Add action**. For a trigger, choose **Add trigger** under **When** instead. Open the **By target** tab.
3. Pick the device, for example the boiler.
4. The list shows Timerify's actions or triggers with the device's other ones. Choose one.

A device that Timerify made for an entity that is on no device works the same.

The **Device** group on the **By type** tab does not list Timerify's actions and triggers. It lists what the device's own integration offers. It also lists actions and triggers of the device's kinds of entities. One example is setting the value of **Run for**. Home Assistant builds that list itself, so Timerify's actions and triggers are under **By target** instead.

## Actions

| Action | What it does |
| --- | --- |
| **Run** | Turns the device on, for the minutes you give, up to a day. |
| **Add time** | Moves the end of the countdown, up to a day either way. |
| **Stop** | Ends the countdown and turns the device off. It also turns off a device that runs without a countdown. |

**Add command** and **Cancel command** are there too. The [Actions](services.md) page lists every field.

For example, to run the boiler for 20 minutes, pick **Run** and set **Minutes** to 20.

## Triggers

| Trigger | When it fires |
| --- | --- |
| **Countdown started** | A timer that was not counting down starts. Changing a countdown that already runs does not fire it. Nor does a device that runs without a countdown in **Loose** mode. |
| **Countdown ended** | The countdown runs out, Timerify stops it, or the device is switched off outside Timerify. |
| **Pending command came due** | A pending command is carried out at its time. A command that came too late after a restart does not fire it. The log names it. |

The [Modes](timers.md#modes) section explains **Loose** mode.

A trigger aimed at one **Run for** entity names its entity id. If you rename that entity, change the trigger too, or it never fires. A trigger aimed at the device has no such problem.

### What a trigger tells the automation

Every trigger gives the automation some variables. You can use them in conditions and in templates.

- `trigger.entity_id`: the **Run for** entity of the timer that fired the trigger.
- `trigger.ends_at`: the end of the countdown, for **Countdown started**. It is a time in UTC, the same as the state of the **Ends at** sensor.
- `trigger.reason`: why the countdown ended, for **Countdown ended**.
- `trigger.command_id`: the id of the command, for **Pending command came due**.
- `trigger.action`: `on` or `off`, for **Pending command came due**.

The reason is one of three words:

- `expired`: the countdown ran out.
- `stopped`: Timerify stopped it. You set **Run for** to 0, used **Stop**, or pressed **Turn off**. A voice request or a pending command can stop it too.
- `turned_off`: someone switched the device off outside Timerify, by hand or in its own app.

The [Events](services.md#events) section lists every cause of `stopped`.

For example, this automation sends a notification only when the boiler ran out of time:

```yaml
triggers:
  - trigger: timerify.countdown_ended
    target:
      entity_id: number.boiler_run_for
conditions:
  - condition: template
    value_template: "{{ trigger.reason == 'expired' }}"
actions:
  - action: persistent_notification.create
    data:
      message: The boiler ran out of time.
```

An automation that turns the device on again when its countdown ends should check the reason. Otherwise a stop would start the device again.

### After a restart

A countdown that ended while Home Assistant was down triggers **Countdown ended** once, when Home Assistant has started. The reason is `expired`. The device is turned off then, if it is still on. A countdown that still runs does not trigger again.

A pending command that came due while Home Assistant was down triggers **Pending command came due** at that time too.

## A device with two timers

Say a relay has two channels, each with its own timer. An action aimed at the device acts on both timers. To aim at one, change the target to that channel's **Run for** entity.

A trigger aimed at the device fires for each timer, and `trigger.entity_id` says which one. A timer you add to the device later is covered without editing the automation.

Both **Run for** entities have the same name. They differ by their entity id, for example `number.relay_run_for` and `number.relay_run_for_2`. To see the entity ids in the lists, turn on **Display entity IDs in picker** in your profile.

You can also rename an entity, so that the lists show two different names. Open **Settings > Devices & services > Entities**, choose the entity, open its settings and change its **Name**.
