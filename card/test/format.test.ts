import { describe, expect, it } from "vitest";
import { formatClock, formatMinutes, formatRemaining, settingText } from "../src/format";
import { AC, START, acTimer, fakeHass, type FakeHass } from "./fake-hass";

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
});

describe("a setting of a pending command", () => {
  /** Home Assistant's formatters, told apart by what they say, over the AC (climate.ac). */
  function formattingHass(language: "en" | "ru" = "en"): FakeHass {
    const hass = fakeHass({ language, timers: [acTimer()] });
    hass.formatEntityState = (entity, state) => `state of ${entity.entity_id}: ${state}`;
    hass.formatEntityAttributeValue = (entity, attribute, value) =>
      `${attribute} of ${entity.entity_id}: ${value}`;
    return hass;
  }
  const settingOf = (hass: FakeHass, key: string, value: unknown) =>
    settingText(hass, hass.states[AC], key, value);

  it("names a mode as the target names its states", () => {
    const hass = formattingHass();

    expect(settingOf(hass, "hvac_mode", "cool")).toBe("state of climate.ac: cool");
  });

  it("writes a percentage as the user's language writes percentages", () => {
    for (const language of ["en", "ru"] as const) {
      const hass = formattingHass(language);
      const percent = new Intl.NumberFormat(language, { style: "percent" });

      for (const key of ["brightness_pct", "percentage", "humidity"]) {
        expect(settingOf(hass, key, 80), `${key} in ${language}`).toBe(percent.format(0.8));
      }
    }
    expect(settingOf(formattingHass(), "brightness_pct", 80)).toBe("80%");
  });

  it("keeps the fraction of a brightness that was not a whole number", () => {
    expect(settingOf(formattingHass(), "brightness_pct", 37.5)).toBe("37.5%");
  });

  it("leaves every other setting to Home Assistant's way of writing the attribute", () => {
    const hass = formattingHass();

    for (const [key, value] of [
      ["temperature", 24],
      ["fan_mode", "auto"],
      ["preset_mode", "sleep"],
      ["mode", "away"],
      ["operation_mode", "eco"],
    ] as const) {
      expect(settingOf(hass, key, value), key).toBe(`${key} of climate.ac: ${value}`);
    }
  });

  it("says the value as it is when the target has no state to write it with", () => {
    const hass = formattingHass();

    expect(settingText(hass, undefined, "hvac_mode", "cool")).toBe("cool");
    expect(settingText(hass, undefined, "temperature", 24)).toBe("24");
    expect(settingText(hass, undefined, "humidity", 55)).toBe(
      new Intl.NumberFormat("en", { style: "percent" }).format(0.55),
    );
  });
});
