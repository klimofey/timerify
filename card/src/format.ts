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

const MS_PER_DAY = 86_400_000;

/** The calendar day of the instant in the time zone, as a number of days since 1970. */
function calendarDay(timeZone: string | undefined, instant: number): number {
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
  const timeZone = locale.time_zone === "server" ? hass.config.time_zone : undefined;
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

/** The settings that are a share of something, given as a number from 0 to 100. */
const PERCENT_SETTINGS = new Set(["brightness_pct", "percentage", "humidity"]);

/**
 * One setting of a pending command, as the user reads it. Home Assistant knows how to say
 * the rest: a thermostat's mode in the words of its states, a temperature with its unit, a
 * fan's or humidifier's mode in the words the integration gives it. Only a share of
 * something is written here, as the user's language writes percentages. A target that has no
 * state has nothing to say them with, and the value is told as it is.
 */
export function settingText(
  hass: HomeAssistant,
  target: HassEntity | undefined,
  key: string,
  value: unknown,
): string {
  if (PERCENT_SETTINGS.has(key) && typeof value === "number") {
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
