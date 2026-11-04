import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { common as english } from "../../custom_components/timerify/translations/en.json";
import { parseConfig } from "../src/config";
import type { TimerifyCardPopup } from "../src/popup";
import type { TimerifyCard } from "../src/timerify-card";
import { lookupTimer, serverNow, timerView } from "../src/timer";
import {
  NEXT_COMMAND,
  NUMBER,
  START,
  fakeHass,
  limited,
  type FakeHass,
  type FakeHassOptions,
} from "./fake-hass";
import { mountCard, popupOf, textOf } from "./mount";

const SECOND = 1000;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;

/** Monday 23:59:30 in Jerusalem (UTC+2 in January): half a minute before Tuesday. */
const LATE = Date.UTC(2026, 0, 5, 21, 59, 30);

const ROUND = { entity: NUMBER, layout: "round" } as const;

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(LATE);
});

afterEach(() => {
  document.body.replaceChildren();
  vi.useRealTimers();
});

const untilLatest = (time: string) => english.card_until_latest.replace("{time}", time);
const status = (card: TimerifyCard) =>
  card.shadowRoot?.querySelector(".status")?.textContent?.replace(/\s+/g, " ").trim();

/** Lets the time pass, and the card draw what the time brought. */
async function pass(card: TimerifyCard, milliseconds: number) {
  await vi.advanceTimersByTimeAsync(milliseconds);
  await card.updateComplete;
}

/** The idle boiler with a command to turn it off at this moment, listed by "Next command". */
function idleUntil(moment: number): FakeHass {
  const at = new Date(moment).toISOString();
  const off = { id: "c1", at, action: "off", minutes: null, settings: {} };
  return fakeHass({ timeFormat: "24" }).state(NEXT_COMMAND, at, { commands: [off] });
}

async function opened(hass: FakeHass) {
  const card = await mountCard(hass);
  const popup = popupOf(card);
  popup.open();
  await popup.updateComplete;
  const rows = () =>
    [...(popup.shadowRoot?.querySelectorAll(".commands .what") ?? [])].map((row) =>
      row.textContent?.replace(/\s+/g, " ").trim(),
    );
  return { card, popup, rows };
}

describe("the weekday of a limit", () => {
  it("drops the weekday of a limit at midnight, with no state change", async () => {
    const card = await mountCard(limited(30.5, {}, LATE));

    expect(textOf(card)).toBe(`Boiler ${untilLatest("Tue 00:30")}`);
    expect(vi.getTimerCount()).toBe(1);

    await pass(card, 31 * SECOND);

    expect(textOf(card)).toBe(`Boiler ${untilLatest("00:30")}`);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("drops the weekday of a limit on the round tile at midnight", async () => {
    const card = await mountCard(limited(30.5, {}, LATE), ROUND);

    expect(status(card)).toBe(untilLatest("Tue 00:30"));
    expect(vi.getTimerCount()).toBe(1);

    await pass(card, 31 * SECOND);

    expect(status(card)).toBe(untilLatest("00:30"));
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("the weekday of a pending command", () => {
  const TUESDAY_07_00 = Date.UTC(2026, 0, 6, 5, 0);

  it("drops the weekday of a pending command in the open pop-up of an idle timer", async () => {
    const { popup, rows } = await opened(idleUntil(TUESDAY_07_00));

    expect(rows()).toEqual(["Off at Tue 07:00"]);
    expect(vi.getTimerCount()).toBe(1);

    await vi.advanceTimersByTimeAsync(31 * SECOND);
    await popup.updateComplete;

    expect(rows()).toEqual(["Off at 07:00"]);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("sets no timeout once the pop-up is shut", async () => {
    const { popup } = await opened(idleUntil(TUESDAY_07_00));
    expect(vi.getTimerCount()).toBe(1);

    popup.close();
    await popup.updateComplete;

    expect(vi.getTimerCount()).toBe(0);
  });

  it("arms nothing for a command that is overdue from yesterday", async () => {
    const sunday = Date.UTC(2026, 0, 4, 5, 0); // 07:00 in Jerusalem, a day before LATE
    const { popup, rows } = await opened(idleUntil(sunday));

    // The date of a moment in the past stays what it is when the day changes.
    expect(rows()).toEqual(["Off at Jan 4, 07:00"]);
    expect(vi.getTimerCount()).toBe(0);

    await vi.advanceTimersByTimeAsync(31 * SECOND);
    await popup.updateComplete;

    expect(rows()).toEqual(["Off at Jan 4, 07:00"]);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("turns a date into a weekday at midnight six days before", async () => {
    const monday12th = Date.UTC(2026, 0, 12, 6, 0); // 08:00 in Jerusalem
    const { popup, rows } = await opened(idleUntil(monday12th));

    // A week ahead, the day is told by its date, in the way the language writes one.
    const date = new Intl.DateTimeFormat("en", {
      month: "short",
      day: "numeric",
      timeZone: "Asia/Jerusalem",
    }).format(monday12th);
    expect(rows()[0]).toMatch(new RegExp(`^Off at ${date}, 08:00$`));

    await vi.advanceTimersByTimeAsync(31 * SECOND);
    await popup.updateComplete;

    expect(rows()).toEqual(["Off at Mon 08:00"]);
  });
});

describe("the pop-up on its own", () => {
  it("drops the weekday of a limit at midnight without the card drawing it again", async () => {
    // The card gives the pop-up a new view whenever it draws, so inside a card the pop-up
    // follows the card's own timeout. Alone, it has to wait for midnight itself.
    const hass = limited(30.5, {}, LATE);
    const config = parseConfig({ entity: NUMBER });
    const lookup = await lookupTimer(hass, NUMBER);
    if (lookup.status !== "found") {
      throw new Error("The boiler timer was not found");
    }
    const popup = document.createElement("timerify-card-popup") as TimerifyCardPopup;
    popup.hass = hass;
    popup.config = config;
    popup.lookup = lookup;
    popup.view = timerView(hass, config, lookup, serverNow(lookup));
    document.body.append(popup);
    popup.open();
    await popup.updateComplete;
    const until = () => popup.shadowRoot?.querySelector(".until")?.textContent?.trim();

    expect(until()).toBe(untilLatest("Tue 00:30"));
    expect(vi.getTimerCount()).toBe(1);

    await vi.advanceTimersByTimeAsync(31 * SECOND);
    await popup.updateComplete;

    expect(until()).toBe(untilLatest("00:30"));
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("the zone the label is written in", () => {
  /** Monday 23:59:30 in New York, 04:59:30 UTC: half a minute before Tuesday there. */
  const NEW_YORK_LATE = Date.UTC(2026, 0, 6, 4, 59, 30);
  /** A limit at 00:30 on Tuesday in New York, 05:30 UTC. */
  const inNewYork = (options: FakeHassOptions) => limited(30.5, options, NEW_YORK_LATE);

  it("follows the zone the label is written in", async () => {
    vi.setSystemTime(NEW_YORK_LATE);
    const card = await mountCard(inNewYork({ localeTimeZone: "local" }));

    expect(textOf(card)).toBe(`Boiler ${untilLatest("Tue 00:30")}`);
    await pass(card, 31 * SECOND);
    expect(textOf(card)).toBe(`Boiler ${untilLatest("00:30")}`);
    card.remove();

    // The same moments in the server's zone are 06:59:30 and 07:30 on one day.
    vi.setSystemTime(NEW_YORK_LATE);
    const sameDay = await mountCard(inNewYork({ localeTimeZone: "server" }));

    expect(textOf(sameDay)).toBe(`Boiler ${untilLatest("07:30")}`);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("follows a change of the profile's time zone", async () => {
    vi.setSystemTime(NEW_YORK_LATE);
    const hass = inNewYork({ localeTimeZone: "local" });
    const card = await mountCard(hass);
    expect(textOf(card)).toBe(`Boiler ${untilLatest("Tue 00:30")}`);
    expect(vi.getTimerCount()).toBe(1);

    card.hass = hass.with({ localeTimeZone: "server" });
    await card.updateComplete;

    expect(textOf(card)).toBe(`Boiler ${untilLatest("07:30")}`);
    expect(vi.getTimerCount()).toBe(0);

    card.hass = hass.with({ localeTimeZone: "local" });
    await card.updateComplete;

    expect(textOf(card)).toBe(`Boiler ${untilLatest("Tue 00:30")}`);
    expect(vi.getTimerCount()).toBe(1);
    await pass(card, 31 * SECOND);
    expect(textOf(card)).toBe(`Boiler ${untilLatest("00:30")}`);
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("the zone the label is written in, when both zones show a day", () => {
  it("waits for the midnight of the zone the profile has now", async () => {
    // Monday 14:00 in Jerusalem, 07:00 in New York; the limit is a day on, in both.
    const noon = Date.UTC(2026, 0, 5, 12);
    vi.setSystemTime(noon);
    const hass = limited(24 * 60, { localeTimeZone: "local" }, noon);
    const card = await mountCard(hass);
    expect(textOf(card)).toBe(`Boiler ${untilLatest("Tue 07:00")}`);

    // Jerusalem's midnight comes 10 hours on, New York's 17.
    card.hass = hass.with({ localeTimeZone: "server" });
    await card.updateComplete;
    expect(textOf(card)).toBe(`Boiler ${untilLatest("Tue 14:00")}`);
    await pass(card, 10 * HOUR + SECOND);

    expect(textOf(card)).toBe(`Boiler ${untilLatest("14:00")}`);
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("the clock the midnight is waited for by", () => {
  it("arms again for the rest when it fires before midnight by a clock measured again", async () => {
    const hass = limited(30.5, {}, LATE);
    const card = await mountCard(hass);
    expect(textOf(card)).toBe(`Boiler ${untilLatest("Tue 00:30")}`);

    // The connection drops and comes back, and Timerify's clock is found to be 5 s behind the
    // browser's: it is 23:59:25 on the server, 35 s from the midnight the timeout waits for.
    hass.setServerClockAhead(-5 * SECOND);
    card.hass = hass.with({ connected: false });
    await card.updateComplete;
    card.hass = hass.with({ connected: true });
    await card.updateComplete;
    expect(textOf(card)).toBe(`Boiler ${untilLatest("Tue 00:30")}`);

    // The timeout fires 30 s on, at 23:59:55 on the server: still Monday, so it waits again.
    await pass(card, 30 * SECOND);
    expect(textOf(card)).toBe(`Boiler ${untilLatest("Tue 00:30")}`);
    expect(vi.getTimerCount()).toBe(1);

    await pass(card, 5 * SECOND);
    expect(textOf(card)).toBe(`Boiler ${untilLatest("00:30")}`);
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("when nothing waits for midnight", () => {
  it("sets no timeout while nothing shown has a day, and none after the card is removed", async () => {
    vi.setSystemTime(START);
    const today = await mountCard(limited(90));
    expect(textOf(today)).toBe(`Boiler ${untilLatest("10:30")}`);
    expect(vi.getTimerCount()).toBe(0);
    today.remove();

    vi.setSystemTime(LATE);
    const card = await mountCard(limited(30.5, {}, LATE));
    expect(vi.getTimerCount()).toBe(1);

    card.remove();

    expect(vi.getTimerCount()).toBe(0);
  });

  it("redraws a label with a day when the page becomes visible after midnight", async () => {
    const card = await mountCard(limited(30.5, {}, LATE));
    expect(textOf(card)).toBe(`Boiler ${untilLatest("Tue 00:30")}`);

    // A tablet that slept through midnight: the clock moved on, and the timeout did not fire.
    vi.setSystemTime(LATE + MINUTE);
    document.dispatchEvent(new Event("visibilitychange"));
    await card.updateComplete;

    expect(textOf(card)).toBe(`Boiler ${untilLatest("00:30")}`);
    expect(vi.getTimerCount()).toBe(0);
  });
});
