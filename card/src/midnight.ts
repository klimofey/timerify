// The redraw at midnight. A time that is not today is written with its day ("Tue 00:30"), and
// nothing redraws a label that does not tick, so after midnight it would keep saying "Tue"
// for a time that is now today. The card draws it once more at the next midnight instead.
import type { ReactiveController, ReactiveControllerHost } from "lit";
import { calendarDay, startOfNextDay } from "./format";

/** The timeout, and what it waits for: the zone the day is counted in, and its midnight. */
interface Armed {
  timer: ReturnType<typeof setTimeout>;
  timeZone: string | undefined;
  midnight: number;
}

/**
 * Draws the host again at the next midnight, for as long as it writes a time that is on
 * another day than today.
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
   * Waits for the midnight while the host is on the page and writes a moment that is on
   * another day than now. The timeout is kept while it waits for the same midnight in the
   * same zone, whatever else the host redrew for.
   */
  #follow(): void {
    const wanted = this.#connected ? this.#nextMidnight() : undefined;
    if (wanted === undefined) {
      this.#disarm();
      return;
    }
    const { timeZone, midnight, delay } = wanted;
    const armed = this.#armed;
    if (armed !== undefined && armed.timeZone === timeZone && armed.midnight === midnight) {
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
    }, delay);
    this.#armed = { timer, timeZone, midnight };
  }

  /** The midnight that puts an end to the day of some moment written, if there is one. */
  #nextMidnight(): { timeZone: string | undefined; midnight: number; delay: number } | undefined {
    const moments = this.#moments();
    if (moments.length === 0) {
      return undefined;
    }
    const now = this.#now();
    const timeZone = this.#timeZone();
    const today = calendarDay(timeZone, now);
    if (moments.every((moment) => calendarDay(timeZone, moment.getTime()) === today)) {
      return undefined;
    }
    const midnight = startOfNextDay(timeZone, now);
    return { timeZone, midnight, delay: midnight - now };
  }

  #disarm(): void {
    if (this.#armed !== undefined) {
      clearTimeout(this.#armed.timer);
      this.#armed = undefined;
    }
  }
}
