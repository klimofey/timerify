// How a person presses the card. One rule serves every layout: a tap is the `click` event of
// the card's body, which a mouse, a finger, a keyboard and assistive technology all produce.
// A body that is not a native button gets no `click` from the keyboard, so Enter and Space call
// the same handler. A control beside the body, such as the "+N" chip, is not part of it, so
// its presses never get here.
import type { ReactiveController, ReactiveControllerHost } from "lit";

export interface PressActions {
  tap(): void;
}

/** The listeners to put on the body of the card. */
export interface PressBinding {
  click(event: MouseEvent): void;
  keydown(event: KeyboardEvent): void;
  keyup(event: KeyboardEvent): void;
}

export class PressController implements ReactiveController {
  readonly #actions: PressActions;
  /** Space went down on the body: like a native button, it presses only when it comes up there. */
  #spaceDown = false;

  constructor(host: ReactiveControllerHost, actions: PressActions) {
    this.#actions = actions;
    host.addController(this);
  }

  hostDisconnected(): void {
    this.#spaceDown = false;
  }

  binding(): PressBinding {
    return {
      click: () => this.#actions.tap(),
      keydown: (event) => {
        if (event.key === "Enter") {
          // The press opens a dialog that takes the focus; without this the browser would
          // go on to press the button the focus has moved to.
          event.preventDefault();
          if (!event.repeat) {
            this.#actions.tap();
          }
        } else if (event.key === " ") {
          // Space presses on release; holding it down must not scroll the page.
          event.preventDefault();
          this.#spaceDown = true;
        }
      },
      keyup: (event) => {
        if (event.key !== " ") {
          return;
        }
        const armed = this.#spaceDown;
        this.#spaceDown = false;
        if (armed) {
          this.#actions.tap();
        }
      },
    };
  }
}
