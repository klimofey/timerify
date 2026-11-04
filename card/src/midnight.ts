// The redraw at midnight. A time that is not today is written with its day ("Tue 00:30"), and
// nothing redraws a label that does not tick, so after midnight it would keep saying "Tue"
// for a time that is now today. The card draws it once more at the next midnight instead.
import type { ReactiveController, ReactiveControllerHost } from "lit";
import { calendarDay, startOfNextDay } from "./format";

/** The timeout, and what it waits for: the end of a day, in the zone that counts it. */
interface Armed {
  timer: ReturnType<typeof setTimeout>;
  timeZone: string | undefined;
  /** The day that ends, as `calendarDay` counts it; with the zone it fixes the midnight. */
  day: number;
}

/**
 * Draws the host again at the next midnight, for as long as it writes a time that is on a
 * later day than today.
 */
export class MidnightController implements ReactiveController {
  readonly #host: ReactiveControllerHost;
  readonly #moments: () => readonly Date[];
  readonly #now: () => number;
  readonly #timeZone: () => string | undefined;
  #connected = false;
  #armed: Armed | undefined;

  /**
   * `moments` are the times the host writes, `now` is what time it is by the clock the host
   * writes them by (in milliseconds since the epoch) and `timeZone` the zone it writes their
   * days in. `now` and `timeZone` are asked only while there is a moment.
   */
  constructor(
    host: ReactiveControllerHost,
    moments: () => readonly Date[],
    now: () => number,
    timeZone: () => string | undefined,
  ) {
    this.#host = host;
    this.#moments = moments;
    this.#now = now;
    this.#timeZone = timeZone;
    host.addController(this);
  }

  hostConnected(): void {
    this.#connected = true;
    document.addEventListener("visibilitychange", this.#onVisibilityChange);
    this.#follow();
  }

  /** A moment, the zone or the clock can change with any update of the host. */
  hostUpdated(): void {
    this.#follow();
  }

  hostDisconnected(): void {
    this.#connected = false;
    document.removeEventListener("visibilitychange", this.#onVisibilityChange);
    this.#follow();
  }

  /**
   * A page that was hidden may have slept through the midnight, and its timeout with it. When
   * it is seen again the host draws, and that draw waits for the midnight that is left.
   */
  readonly #onVisibilityChange = (): void => {
    if (document.visibilityState === "visible" && this.#armed !== undefined) {
      this.#disarm();
      this.#host.requestUpdate();
    }
  };

  /**
   * Waits for the midnight while the host is on the page and writes a moment on a later day
   * than today. The timeout is kept while it waits for the end of the same day in the same
   * zone, whatever else the host redrew for, so the midnight is looked for only when it arms.
   */
  #follow(): void {
    const wanted = this.#connected ? this.#dayToWaitOut() : undefined;
    if (wanted === undefined) {
      this.#disarm();
      return;
    }
    const { timeZone, day, now } = wanted;
    const armed = this.#armed;
    if (armed !== undefined && armed.timeZone === timeZone && armed.day === day) {
      return;
    }
    this.#disarm();
    // The delay is the difference of two moments of the host's clock, which the browser's
    // timeout measures as it is. If the host's clock is measured against the browser's again
    // while the timeout waits, it may fire before the midnight by the new measure. The draw it
    // makes then still finds the day, and arms again for what is left.
    const timer = setTimeout(() => {
      this.#armed = undefined;
      this.#host.requestUpdate();
    }, startOfNextDay(timeZone, now) - now);
    this.#armed = { timer, timeZone, day };
  }

  /**
   * Today, with the zone and the time it was counted by, when some moment written is on a
   * later day: its label carries a day that the midnight will take away. A moment that has
   * passed on an earlier day keeps its date, whatever the hour.
   */
  #dayToWaitOut(): { timeZone: string | undefined; day: number; now: number } | undefined {
    const moments = this.#moments();
    if (moments.length === 0) {
      return undefined;
    }
    const now = this.#now();
    const timeZone = this.#timeZone();
    const day = calendarDay(timeZone, now);
    return moments.some((moment) => calendarDay(timeZone, moment.getTime()) > day)
      ? { timeZone, day, now }
      : undefined;
  }

  #disarm(): void {
    if (this.#armed !== undefined) {
      clearTimeout(this.#armed.timer);
      this.#armed = undefined;
    }
  }
}
