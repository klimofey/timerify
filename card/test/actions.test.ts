import { describe, expect, it } from "vitest";
import { addMinutes, runWithoutDuration, setMinutes } from "../src/actions";
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
    expect(hass.calls).toHaveLength(3);
  });

  it("lets the service notify on error, as it does by default", async () => {
    const hass = fakeHass();

    await addMinutes(hass, NUMBER, 15);

    expect(hass.calls[0]?.notifyOnError).toBeUndefined();
  });
});
