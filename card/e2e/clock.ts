// A time as the card writes it, for the tests that read what a page says.

/** The browser's time zone, which the user's profile follows by default (the config's). */
const ZONE = "America/New_York";

const dayIn = (moment: number) =>
  new Intl.DateTimeFormat("en-CA", { timeZone: ZONE }).format(moment);

/**
 * A time as the card writes it at this moment: in the user's language and the browser's time
 * zone, with the short weekday when it falls on another day than today, which a command that
 * is due in ten hours does, and a countdown does in its last minutes before midnight.
 */
export function clockText(language: string, hourCycle: "h12" | "h23", moment: number): string {
  const options: Intl.DateTimeFormatOptions = {
    timeZone: ZONE,
    hour: "numeric",
    minute: "2-digit",
    hourCycle,
  };
  if (dayIn(moment) !== dayIn(Date.now())) {
    options.weekday = "short";
  }
  return new Intl.DateTimeFormat(language, options).format(moment).replace(/\s+/g, " ");
}
