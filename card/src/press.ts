// How a person presses the card. One rule serves every layout: a tap is the `click` event of
// the card's body, which a mouse, a finger, a keyboard and assistive technology all produce.
// A body that is not a native button gets no `click` from the keyboard, so Enter and Space call
// the same handler. A control beside the body, such as the "+N" chip, is not part of it, so
// its presses never get here.
//
// A card that has something to do on a long press is given `hold`. The hold is added on top
// of the tap and takes its `click` away: it acts when the pointer is let go after HOLD_MS, as
// Home Assistant's own handler does, and until then `data-held` on the card tells the user
// that letting go will act.
import type { ReactiveController, ReactiveControllerHost } from "lit";

/** How long a pointer is held down before letting go acts. */
export const HOLD_MS = 500;

/** The attribute the host carries while letting go of the pointer would act. */
const HELD = "data-held";

export interface PressActions {
  tap(): void;
  /** What a long press does; a controller without it leaves long presses alone. */
  hold?(): void;
}

/** The listeners to put on the body of the card. */
export interface PressBinding {
  click(event: MouseEvent): void;
  keydown(event: KeyboardEvent): void;
  keyup(event: KeyboardEvent): void;
  /** The pointer listeners exist only when the controller has a `hold`. */
  pointerdown?(event: PointerEvent): void;
  pointerup?(event: PointerEvent): void;
  pointercancel?(event: PointerEvent): void;
  pointerleave?(event: PointerEvent): void;
  contextmenu?(event: MouseEvent): void;
}

export class PressController implements ReactiveController {
  readonly #host: ReactiveControllerHost & HTMLElement;
  readonly #actions: PressActions;
  /** Space went down on the body: like a native button, it presses only when it comes up there. */
  #spaceDown = false;
  /** The pointer that is down on the body, from its going down to its end. */
  #pointer: number | undefined;
  #holdTimer: ReturnType<typeof setTimeout> | undefined;
  /** The pointer has been down for HOLD_MS: letting go of it acts. */
  #held = false;
  /** The hold was let go: the click that may follow it is not a tap. */
  #swallowClick = false;

  constructor(host: ReactiveControllerHost & HTMLElement, actions: PressActions) {
    this.#host = host;
    this.#actions = actions;
    host.addController(this);
  }

  hostDisconnected(): void {
    this.#spaceDown = false;
    this.#swallowClick = false;
    this.#endPress();
  }

  binding(): PressBinding {
    const keyboardAndClick: PressBinding = {
      click: (event) => {
        if (this.#swallowClick) {
          this.#swallowClick = false;
          event.preventDefault();
          event.stopPropagation();
          return;
        }
        this.#actions.tap();
      },
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
    const { hold } = this.#actions;
    if (hold === undefined) {
      return keyboardAndClick;
    }
    return {
      ...keyboardAndClick,
      pointerdown: (event) => this.#startPress(event),
      pointerup: (event) => {
        if (event.pointerId !== this.#pointer) {
          return;
        }
        const held = this.#held;
        this.#endPress();
        if (held) {
          // The browser goes on to send a click, which must not also be a tap.
          this.#swallowClick = true;
          hold();
        }
      },
      pointercancel: (event) => this.#abortPress(event),
      pointerleave: (event) => this.#abortPress(event),
      // A long touch brings up the browser's menu on some phones, and takes the press away
      // with it: while the press lasts, the menu stays shut.
      contextmenu: (event) => {
        if (this.#pointer !== undefined) {
          event.preventDefault();
        }
      },
    };
  }

  #startPress(event: PointerEvent): void {
    // Only the main button of a mouse and the first finger press; a second finger is a pinch.
    if (!event.isPrimary || event.button !== 0) {
      return;
    }
    // The click of a hold that the browser never sent must not be taken for this press's.
    this.#swallowClick = false;
    this.#endPress();
    this.#pointer = event.pointerId;
    this.#holdTimer = setTimeout(() => {
      this.#holdTimer = undefined;
      this.#held = true;
      this.#host.setAttribute(HELD, "");
    }, HOLD_MS);
  }

  /** The press of the pointer ended without acting: it moved off the body, or was taken away. */
  #abortPress(event: PointerEvent): void {
    if (event.pointerId === this.#pointer) {
      this.#endPress();
    }
  }

  #endPress(): void {
    clearTimeout(this.#holdTimer);
    this.#holdTimer = undefined;
    this.#pointer = undefined;
    this.#held = false;
    this.#host.removeAttribute(HELD);
  }
}
