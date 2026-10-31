import { describe, expect, it } from "vitest";
import { formatClock, formatMinutes, formatRemaining } from "../src/format";
import { START, fakeHass } from "./fake-hass";

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/** 09:45 in Jerusalem on Monday, 5 January 2026: three-quarters of an hour after `START`. */
const NINE_FORTY_FIVE = new Date(START + 45 * MINUTE);

describe("the time left", () => {
  it("shows minutes and seconds, then hours", () => {
    expect(formatRemaining(2699.2)).toBe("45:00");
    expect(formatRemaining(2700)).toBe("45:00");
    expect(formatRemaining(59)).toBe("0:59");
    expect(formatRemaining(3599)).toBe("59:59");
    expect(formatRemaining(3600)).toBe("1:00:00");
    expect(formatRemaining(3661)).toBe("1:01:01");
    expect(formatRemaining(24 * 3600)).toBe("24:00:00");
    expect(formatRemaining(0)).toBe("0:00");
  });

  it("rounds a part of a second up, as the Run for number does", () => {
    expect(formatRemaining(0.2)).toBe("0:01");
    expect(formatRemaining(59.001)).toBe("1:00");
  });
});

describe("the time a countdown ends", () => {
  const clock = (options: Parameters<typeof fakeHass>[0], at = NINE_FORTY_FIVE) =>
    formatClock(fakeHass(options), at, START);

  it("follows each clock setting of the user", () => {
    expect(clock({ timeFormat: "24" })).toBe("09:45");
    expect(clock({ timeFormat: "12" })).toMatch(/^9:45\sAM$/);
    // In the language's own way: English counts twelve hours, Russian twenty-four.
    expect(clock({ timeFormat: "language", language: "en" })).toMatch(/^9:45\sAM$/);
    expect(clock({ timeFormat: "language", language: "ru" })).toBe("9:45");
  });

  it("follows the browser's way of counting hours when the user chose the system's", () => {
    const systemCountsTwelve = /^h1[12]$/.test(
      new Intl.DateTimeFormat(undefined, { hour: "numeric" }).resolvedOptions().hourCycle ?? "",
    );

    // Russian by itself would count twenty-four hours.
    const shown = clock({ timeFormat: "system", language: "ru" });

    expect(/AM|PM/.test(shown)).toBe(systemCountsTwelve);
  });

  it("uses the server's time zone when the user chose it, the browser's otherwise", () => {
    // Jerusalem is two hours ahead of UTC in January, New York five behind.
    expect(clock({ timeFormat: "24", localeTimeZone: "server" })).toBe("09:45");
    expect(clock({ timeFormat: "24", localeTimeZone: "local" })).toBe("02:45");
    expect(clock({ timeFormat: "24", localeTimeZone: "server", timeZone: "Europe/London" })).toBe(
      "07:45",
    );
  });

  it("adds the weekday for another day and the date beyond a week", () => {
    const later = (days: number) => new Date(NINE_FORTY_FIVE.getTime() + days * DAY);

    expect(clock({ timeFormat: "24" }, later(1))).toBe("Tue 09:45");
    expect(clock({ timeFormat: "24" }, later(6))).toBe("Sun 09:45");
    expect(clock({ timeFormat: "24" }, later(7))).toBe("Jan 12, 09:45");
    expect(clock({ timeFormat: "24" }, later(-1))).toBe("Jan 4, 09:45");
  });

  it("changes the day at midnight in the zone the user reads the clock in", () => {
    const lateEvening = Date.UTC(2026, 0, 5, 21, 30); // 23:30 in Jerusalem
    const justAfterMidnight = new Date(Date.UTC(2026, 0, 5, 22, 10)); // 00:10 the next day there

    // Forty minutes later, but tomorrow by the wall clock.
    const inJerusalem = fakeHass({ timeFormat: "24" });
    expect(formatClock(inJerusalem, justAfterMidnight, lateEvening)).toBe("Tue 00:10");
    // In New York the same two moments are 16:30 and 17:10 on the same day.
    const inNewYork = fakeHass({ timeFormat: "24", localeTimeZone: "local" });
    expect(formatClock(inNewYork, justAfterMidnight, lateEvening)).toBe("17:10");
  });

  it("speaks the user's language", () => {
    const later = new Date(NINE_FORTY_FIVE.getTime() + DAY);

    expect(clock({ timeFormat: "24", language: "ru" }, later)).toBe(
      new Intl.DateTimeFormat("ru", {
        timeZone: "Asia/Jerusalem",
        weekday: "short",
        hour: "numeric",
        minute: "2-digit",
        hourCycle: "h23",
      }).format(later),
    );
  });
});

describe("a length of time in minutes", () => {
  const units = (language: string, unit: "hour" | "minute") => {
    const format = new Intl.NumberFormat(language, {
      style: "unit",
      unit,
      unitDisplay: "short",
      useGrouping: false,
    });
    return (value: number) => format.format(value);
  };

  it("says minutes, hours, and both", () => {
    const hass = fakeHass();

    expect(formatMinutes(hass, 15)).toBe("15 min");
    expect(formatMinutes(hass, 60)).toBe("1 hr");
    expect(formatMinutes(hass, 90)).toBe("1 hr 30 min");
    expect(formatMinutes(hass, 125)).toBe("2 hr 5 min");
  });

  it("speaks the user's language, with its forms for 1, 2, 5 and 21", () => {
    const hass = fakeHass({ language: "ru" });
    const [hours, minutes] = [units("ru", "hour"), units("ru", "minute")];

    for (const count of [1, 2, 5, 21]) {
      expect(formatMinutes(hass, count)).toBe(minutes(count));
    }
    expect(formatMinutes(hass, 90)).toBe(`${hours(1)} ${minutes(30)}`);
    // Not a word of the English file, which the card never glues to a number.
    expect(formatMinutes(hass, 90)).not.toMatch(/\b(min|hr)\b/);
  });

  it("writes minutes without grouping", () => {
    // The longest a timer runs: a day. Nothing of it is written with a group separator.
    expect(formatMinutes(fakeHass(), 1440)).toBe(units("en", "hour")(24));
    expect(formatMinutes(fakeHass({ language: "ru" }), 1440)).toBe(units("ru", "hour")(24));
  });
});
