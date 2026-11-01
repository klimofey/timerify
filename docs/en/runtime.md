# Runtime counter

A timer can add up how long its device was on. This answers "how many hours did the boiler run this week" without an automation.

## Turn the counter on

The counter is off to begin with. Turn on **Count runtime** when you add the timer, or later under **Configure**. The timer then gains a sensor named **Runtime** on the same device.

See [Add a timer to a device](timers.md#add-a-timer-to-a-device) and [Change a timer later](timers.md#change-a-timer-later).

## What counts

- Every "on" of the device counts, whoever caused it. That can be Timerify, the device's own app, a switch on the wall or an automation.
- "On" is judged the way the rest of Timerify judges it. A climate or water heater entity is on in any mode but off. A media player is on when it is neither off nor in standby. Any other device is on when it reports "on".
- The counter only watches. It never starts or stops the device. It does not look at the timer's countdown, pending commands or schedule.
- Time that Timerify did not see is not counted. That is the time Home Assistant is not running, and the time the device is unavailable or unknown.
- When Home Assistant is back, or the device reports again, and the device is on, the count goes on from that moment.

## The value

- The value is in minutes. It is a total that only goes up. It starts at 0 the first time you turn the counter on. A device that is already on counts from that moment, not from when its countdown began.
- Timerify writes the value at most once a minute, near the end of the minute, and only when it has changed. Nothing is written when the device turns on or off.
- The sensor shows whole minutes and keeps two decimals in its state. You can change its display unit in the entity's settings, to hours for instance.
- The total never goes down, not even when the clock of the machine is set back. The exception is a file that cannot be written, such as on a full or read-only disk. Home Assistant logs that.

### Daily and weekly views

Home Assistant's statistics give the daily and weekly views. You need no extra entities. The sensor is a total that only goes up, so Home Assistant keeps its long-term statistics.

The history graph shows the total. A statistics graph card shows the minutes per day or per week:

```yaml
type: statistics-graph
entities:
  - sensor.boiler_runtime
chart_type: bar
period: day
stat_types: change
```

A run that crosses midnight is split between the two days, to within a second. This holds as long as the file of the total is written in under half a second. On a stalled disk, the last minute of a day may fall on the next one.

## Restarts

- A restart loses nothing. The total is stored in a file of its own, before the sensor shows it.
- Stopping or restarting Home Assistant, and reloading the timer, keep every second that the counter has seen.
- If Home Assistant crashes, a run loses at most its last minute.

## Turn the counter off

- Turn off **Count runtime** under **Configure**. This removes the sensor from the registry, so that no unavailable entity is left behind. Its statistics stay in **Developer tools > Statistics**, where you can clear them.
- Turn the option on again, and the sensor comes back with the same entity id and customisations. It continues from the old total. The time in between is not counted.
- Disabling the **Runtime** entity in its own settings is not the same. It pauses the count and keeps the total. Enabling it again carries on from there. To stop counting for good, turn the option off.

## What the counter does not do

- There is no reset. Deleting the timer deletes the total. A timer that you add again counts from zero.
- The dashboard card does not show the runtime. Use Home Assistant's own cards, as above.
