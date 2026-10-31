import { describe, expect, it } from "vitest";
import { parseConfig } from "../src/config";
import type { HassEntity, TimerInfo } from "../src/hass";
import { lookupTimer, targetRunning, timerView, type TimerLookup } from "../src/timer";
import {
  BOILER,
  ENDS_AT,
  NUMBER,
  START,
  acTimer,
  boilerTimer,
  fakeHass,
  type FakeHass,
} from "./fake-hass";

const MINUTE = 60_000;
const config = parseConfig({ entity: NUMBER });
const found = (info: TimerInfo = boilerTimer().info): TimerLookup => ({ status: "found", info });

/** A boiler timer whose countdown started `startedAt` and ends `endsAt` (both in ms). */
function counting(endsAt: number, startedAt: number | null = START): FakeHass {
  return fakeHass().state(ENDS_AT, new Date(endsAt).toISOString(), {
    started_at: startedAt === null ? null : new Date(startedAt).toISOString(),
  });
}

describe("what the card shows of a timer", () => {
  it("counts while Ends at holds a time", () => {
    const hass = counting(START + 45 * MINUTE);

    const view = timerView(hass, config, found(), START);

    expect(view.state).toBe("counting");
    expect(view.remaining).toBe(2700);
    expect(view.progress).toBe(1);
    expect(view.endsAt).toEqual(new Date(START + 45 * MINUTE));
  });

  it("empties as the countdown passes", () => {
    const hass = counting(START + 40 * MINUTE);

    expect(timerView(hass, config, found(), START + 10 * MINUTE).progress).toBe(0.75);
    expect(timerView(hass, config, found(), START + 30 * MINUTE).progress).toBe(0.25);
  });

  it("keeps the share left within empty and full", () => {
    const hass = counting(START + 45 * MINUTE);

    const late = timerView(hass, config, found(), START + 50 * MINUTE);
    expect(late.state).toBe("counting");
    expect(late.remaining).toBe(0);
    expect(late.progress).toBe(0);

    const early = timerView(hass, config, found(), START - 5 * MINUTE);
    expect(early.progress).toBe(1);
  });

  it("is full while the beginning is unknown", () => {
    const view = timerView(counting(START + 45 * MINUTE, null), config, found(), START);

    expect(view.state).toBe("counting");
    expect(view.progress).toBe(1);
  });

  it("is full while the target runs without a countdown, and empty while idle", () => {
    const running = fakeHass().state(BOILER, "on", { friendly_name: "Boiler" });

    const open = timerView(running, config, found(), START);
    expect(open.state).toBe("open");
    expect(open.progress).toBe(1);
    expect(open.remaining).toBe(0);
    expect(open.endsAt).toBeUndefined();

    const idle = timerView(fakeHass(), config, found(), START);
    expect(idle.state).toBe("idle");
    expect(idle.progress).toBe(0);
  });

  it("is unavailable when its number or Ends at is", () => {
    const states = [
      fakeHass().state(NUMBER, "unavailable"),
      fakeHass().state(ENDS_AT, "unavailable"),
      fakeHass().with({ states: { [NUMBER]: null } }),
      fakeHass().with({ states: { [ENDS_AT]: null } }),
    ];
    for (const hass of states) {
      expect(timerView(hass, config, found(), START).state).toBe("unavailable");
    }
  });

  it("names the timer after its target and wears the target's icon", () => {
    const hass = fakeHass();

    const view = timerView(hass, config, found(), START);

    expect(view.name).toBe("Boiler");
    expect(view.icon).toEqual({ stateObj: hass.states[BOILER] });
    expect(view.target).toBe(hass.states[BOILER]);
  });

  it("takes the name and the icon the config gives", () => {
    const named = parseConfig({ entity: NUMBER, name: "Water", icon: "mdi:water-boiler" });

    const view = timerView(fakeHass(), named, found(), START);

    expect(view.name).toBe("Water");
    expect(view.icon).toEqual({ icon: "mdi:water-boiler" });
  });

  it("falls back to its number when the target has no state", () => {
    const hass = fakeHass().with({ states: { [BOILER]: null } });

    const view = timerView(hass, config, found(), START);

    expect(view.name).toBe("Boiler Run for");
    expect(view.icon).toEqual({ icon: "mdi:timer-outline" });
    expect(view.target).toBeUndefined();
  });

  it("names a timer it has not found yet after its number", () => {
    const hass = fakeHass();
    for (const lookup of [
      { status: "pending" },
      { status: "not_found" },
      { status: "failed" },
    ] as const) {
      const view = timerView(hass, config, lookup, START);

      expect(view.name).toBe("Boiler Run for");
      expect(view.icon).toEqual({ icon: "mdi:timer-outline" });
      expect(view.state).toBe("unavailable");
    }
  });

  it("names a timer whose number is gone after the entity id it is configured with", () => {
    const hass = fakeHass().with({ states: { [NUMBER]: null } });

    expect(timerView(hass, config, { status: "not_found" }, START).name).toBe(NUMBER);
  });
});

describe("what counts as the target running", () => {
  const state = (entityId: string, value: string): HassEntity => ({
    entity_id: entityId,
    state: value,
    attributes: {},
  });
  const timerRules = { boiler: boilerTimer().info.target_on, ac: acTimer().info.target_on };

  it("counts what Timerify counts as on", () => {
    expect(targetRunning(state(BOILER, "on"), timerRules.boiler)).toBe(true);
    expect(targetRunning(state(BOILER, "off"), timerRules.boiler)).toBe(false);
    expect(targetRunning(state("climate.ac", "heat"), timerRules.ac)).toBe(true);
    expect(targetRunning(state("climate.ac", "off"), timerRules.ac)).toBe(false);
    const player: TimerInfo["target_on"] = { match: "is_not", states: ["off", "standby"] };
    expect(targetRunning(state("media_player.tv", "standby"), player)).toBe(false);
    expect(targetRunning(state("media_player.tv", "playing"), player)).toBe(true);
  });

  it("does not count a target that is missing, unavailable or unknown", () => {
    expect(targetRunning(undefined, timerRules.ac)).toBe(false);
    for (const rule of Object.values(timerRules)) {
      expect(targetRunning(state("climate.ac", "unavailable"), rule)).toBe(false);
      expect(targetRunning(state("climate.ac", "unknown"), rule)).toBe(false);
    }
  });
});

describe("asking Timerify for a timer", () => {
  it("is told which timer a number belongs to", async () => {
    const hass = fakeHass();

    await expect(lookupTimer(hass, NUMBER)).resolves.toEqual({
      status: "found",
      info: boilerTimer().info,
    });
    expect(hass.requests).toEqual([{ type: "timerify/timer", entity_id: NUMBER }]);
  });

  it("tells a number that is no timer's from a command that fails", async () => {
    const hass = fakeHass({ timers: [] });
    await expect(lookupTimer(hass, NUMBER)).resolves.toEqual({ status: "not_found" });

    for (const code of ["unknown_command", "home_assistant_error"]) {
      hass.answerWith(code);
      await expect(lookupTimer(hass, NUMBER)).resolves.toEqual({ status: "failed" });
    }
  });

  it("tells a user who may not read the timer from a failure", async () => {
    const hass = fakeHass();
    hass.answerWith("unauthorized");

    await expect(lookupTimer(hass, NUMBER)).resolves.toEqual({ status: "unauthorized" });
  });

  it("calls a lost connection a failure, not a missing timer", async () => {
    const hass = fakeHass();
    hass.callWS = () => Promise.reject(new Error("Connection lost"));

    await expect(lookupTimer(hass, NUMBER)).resolves.toEqual({ status: "failed" });
  });
});
