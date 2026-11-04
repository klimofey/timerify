// Times and lengths of time, written the way the user's Home Assistant writes them: in the
// language of the user's profile, in the clock and the time zone the profile chooses.
import type { HassEntity, HomeAssistant } from "./hass";

type Locale = { locale: Pick<HomeAssistant["locale"], "language"> };

const pad = (value: number): string => String(value).padStart(2, "0");

/**
 * What is left of a countdown, as a clock: `M:SS`, or `H:MM:SS` from an hour on. A part of a
 * second counts as a whole one, like the Run for number, which shows the minutes left rounded up.
 */
export function formatRemaining(seconds: number): string {
  const total = Math.ceil(Math.max(0, seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = pad(total % 60);
  return hours > 0 ? `${hours}:${pad(minutes)}:${rest}` : `${minutes}:${rest}`;
}

/** Whether the user's clock has twelve hours and AM/PM, by the profile's time format. */
function countsTwelveHours({ language, time_format }: HomeAssistant["locale"]): boolean {
  if (time_format === "12" || time_format === "24") {
    return time_format === "12";
  }
  // "language": the way the user's language counts; "system": the way the browser's does.
  const options = new Intl.DateTimeFormat(time_format === "language" ? language : undefined, {
    hour: "numeric",
  }).resolvedOptions();
  return options.hourCycle === "h11" || options.hourCycle === "h12";
}

const MS_PER_SECOND = 1000;
const MS_PER_DAY = 86_400_000;
/** Longer than any day lasts (25 hours where the clocks go back), so the next day has begun. */
const LONGER_THAN_A_DAY = 49 * 3_600_000;

/**
 * The zone the user reads the clock in: the server's when the profile chooses it, else none,
 * which `Intl` takes for the browser's own. The labels and the redraw at midnight both go by
 * this one rule.
 */
export function displayTimeZone(
  hass: Pick<HomeAssistant, "locale" | "config">,
): string | undefined {
  return hass.locale.time_zone === "server" ? hass.config.time_zone : undefined;
}

/** The calendar day of the instant in the time zone, as a number of days since 1970. */
export function calendarDay(timeZone: string | undefined, instant: number): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).formatToParts(instant);
  const part = (type: string) => Number(parts.find((candidate) => candidate.type === type)?.value);
  return Date.UTC(part("year"), part("month") - 1, part("day")) / MS_PER_DAY;
}

/**
 * The first whole second of the day after the one `instant` is in, in the time zone: the
 * midnight that ends the day. A day is 23, 24 or 25 hours where the clocks change, so the
 * calendar is asked. The search halves the span from the second of `instant` to 49 hours on,
 * and keeps the end of it on the later day.
 */
export function startOfNextDay(timeZone: string | undefined, instant: number): number {
  const today = calendarDay(timeZone, instant);
  let before = Math.floor(instant / MS_PER_SECOND) * MS_PER_SECOND;
  let after = before + LONGER_THAN_A_DAY;
  while (after - before > MS_PER_SECOND) {
    const middle = before + Math.floor((after - before) / (2 * MS_PER_SECOND)) * MS_PER_SECOND;
    if (calendarDay(timeZone, middle) > today) {
      after = middle;
    } else {
      before = middle;
    }
  }
  return after;
}

/**
 * The moment `at` as a time of day, with what the day needs besides: nothing on the day it
 * is now (`now`, in milliseconds), the weekday on each of the next six, the date after that
 * and for a moment that has passed. The days are the user's: the server's, or the browser's,
 * by the profile's time zone.
 */
export function formatClock(
  hass: Pick<HomeAssistant, "locale" | "config">,
  at: Date,
  now: number,
): string {
  const { locale } = hass;
  const timeZone = displayTimeZone(hass);
  const daysAhead = calendarDay(timeZone, at.getTime()) - calendarDay(timeZone, now);
  const day: Intl.DateTimeFormatOptions =
    daysAhead === 0
      ? {}
      : daysAhead >= 1 && daysAhead <= 6
        ? { weekday: "short" }
        : { month: "short", day: "numeric" };
  return new Intl.DateTimeFormat(locale.language, {
    ...day,
    hour: "numeric",
    minute: "2-digit",
    hourCycle: countsTwelveHours(locale) ? "h12" : "h23",
    timeZone,
  }).format(at);
}

/** A length of time given in minutes, as hours and minutes: `90` is "1 hr 30 min" in English. */
export function formatMinutes(hass: Locale, minutes: number): string {
  const unit = (count: number, name: "hour" | "minute") =>
    new Intl.NumberFormat(hass.locale.language, {
      style: "unit",
      unit: name,
      unitDisplay: "short",
      useGrouping: false,
    }).format(count);
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  const parts = hours > 0 ? [unit(hours, "hour")] : [];
  if (rest > 0 || hours === 0) {
    parts.push(unit(rest, "minute"));
  }
  return parts.join(" ");
}

/**
 * One setting of a pending command, as the user reads it. Home Assistant knows how to say
 * the rest: a thermostat's mode in the words of its states, a temperature with its unit, a
 * fan's or humidifier's mode in the words the integration gives it. Only a share of
 * something is written here, as the user's language writes percentages; which settings are
 * one, the timer says (`percentSettings`). A target that has no state has nothing to say
 * them with, and the value is told as it is.
 */
export function settingText(
  hass: HomeAssistant,
  target: HassEntity | undefined,
  percentSettings: readonly string[],
  key: string,
  value: unknown,
): string {
  if (percentSettings.includes(key) && typeof value === "number") {
    return new Intl.NumberFormat(hass.locale.language, {
      style: "percent",
      // A brightness may be given to a tenth of a percent.
      maximumFractionDigits: 1,
    }).format(value / 100);
  }
  if (target === undefined) {
    return String(value);
  }
  return key === "hvac_mode"
    ? hass.formatEntityState(target, String(value))
    : hass.formatEntityAttributeValue(target, key, value);
}
