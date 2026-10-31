// The ticking of a countdown. Nothing counts down on the server: the card draws again every
// second from the time "Ends at" holds, and only while there is something to count.
import type { ReactiveController, ReactiveControllerHost } from "lit";

const TICK_MS = 1000;

export class CountdownController implements ReactiveController {
  readonly #host: ReactiveControllerHost;
  readonly #endsAt: () => Date | undefined;
  #connected = false;
  #timer: ReturnType<typeof setInterval> | undefined;

  /** `endsAt` says when the countdown the host shows ends, if it shows one. */
  constructor(host: ReactiveControllerHost, endsAt: () => Date | undefined) {
    this.#host = host;
    this.#endsAt = endsAt;
    host.addController(this);
  }

  hostConnected(): void {
    this.#connected = true;
    this.#follow();
  }

  /** A countdown can begin, move or end with any update of the host. */
  hostUpdated(): void {
    this.#follow();
  }

  hostDisconnected(): void {
    this.#connected = false;
    this.#follow();
  }

  /** Ticks while the host is on the page and its countdown has an end that is still ahead. */
  #follow(): void {
    const end = this.#endsAt();
    const counting = this.#connected && end !== undefined && end.getTime() > Date.now();
    if (counting && this.#timer === undefined) {
      this.#timer = setInterval(() => this.#host.requestUpdate(), TICK_MS);
    } else if (!counting && this.#timer !== undefined) {
      clearInterval(this.#timer);
      this.#timer = undefined;
    }
  }
}
