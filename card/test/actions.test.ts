import { describe, expect, it } from "vitest";
import {
  addMinutes,
  cancelCommand,
  runWithoutDuration,
  setIntervalEnabled,
  setMinutes,
  stop,
} from "../src/actions";
import { NUMBER, fakeHass } from "./fake-hass";

const target = { entity_id: NUMBER };

describe("what the card asks Timerify to do", () => {
  it("runs the timer for a number of minutes, and stops it with none", async () => {
    const hass = fakeHass();

    await setMinutes(hass, NUMBER, 45);
    await setMinutes(hass, NUMBER, 0);

    expect(hass.calls).toEqual([
      { domain: "number", service: "set_value", data: { value: 45 }, target },
      { domain: "number", service: "set_value", data: { value: 0 }, target },
    ]);
  });

  it("adds minutes to the countdown, and takes them off with a negative number", async () => {
    const hass = fakeHass();

    await addMinutes(hass, NUMBER, 15);
    await addMinutes(hass, NUMBER, -5);

    expect(hass.calls).toEqual([
      { domain: "timerify", service: "add_time", data: { minutes: 15 }, target },
      { domain: "timerify", service: "add_time", data: { minutes: -5 }, target },
    ]);
  });

  it("runs the timer with no duration at all, and leaves it to Timerify to choose", async () => {
    const hass = fakeHass();

    await runWithoutDuration(hass, NUMBER);

    // Nothing in the data: not even a missing duration, which the service would refuse.
    expect(hass.calls).toEqual([{ domain: "timerify", service: "run", data: {}, target }]);
    expect(Object.keys(hass.calls[0]?.data ?? { none: true })).toEqual([]);
  });

  it("stops the timer with Timerify's own action", async () => {
    const hass = fakeHass();

    await stop(hass, NUMBER);

    expect(hass.calls).toEqual([{ domain: "timerify", service: "stop", data: {}, target }]);
  });

  it("switches an interval of the schedule on and off through its own switch", async () => {
    const hass = fakeHass();
    const interval = "switch.boiler_schedule_06_30_07_15_mon_sun";

    await setIntervalEnabled(hass, interval, false);
    await setIntervalEnabled(hass, interval, true);

    expect(hass.calls).toEqual([
      { domain: "switch", service: "turn_off", data: {}, target: { entity_id: interval } },
      { domain: "switch", service: "turn_on", data: {}, target: { entity_id: interval } },
    ]);
  });

  it("cancels a pending command through the timer that owns it", async () => {
    const hass = fakeHass();

    await cancelCommand(hass, NUMBER, "c1");

    expect(hass.calls).toEqual([
      { domain: "timerify", service: "cancel_command", data: { command_id: "c1" }, target },
    ]);
  });

  it("leaves Home Assistant to tell the user when it refuses", async () => {
    const hass = fakeHass();
    hass.rejectNext(new Error("The timer refused"));

    // Home Assistant has shown its toast by the time the call is rejected; the card has
    // nothing to add, and nothing of it fails.
    await expect(setMinutes(hass, NUMBER, 45)).resolves.toBeUndefined();
    hass.rejectNext(new Error("The timer refused"));
    await expect(addMinutes(hass, NUMBER, 5)).resolves.toBeUndefined();
    hass.rejectNext(new Error("The timer refused"));
    await expect(runWithoutDuration(hass, NUMBER)).resolves.toBeUndefined();
    hass.rejectNext(new Error("The timer refused"));
    await expect(stop(hass, NUMBER)).resolves.toBeUndefined();
    hass.rejectNext(new Error("The switch refused"));
    await expect(setIntervalEnabled(hass, "switch.interval", true)).resolves.toBeUndefined();
    hass.rejectNext(new Error("The timer refused"));
    await expect(cancelCommand(hass, NUMBER, "c1")).resolves.toBeUndefined();
    expect(hass.calls).toHaveLength(6);
  });

  it("lets the service notify on error, as it does by default", async () => {
    const hass = fakeHass();

    await addMinutes(hass, NUMBER, 15);

    expect(hass.calls[0]?.notifyOnError).toBeUndefined();
  });
});
