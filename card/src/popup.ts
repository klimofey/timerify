// The pop-up of the card: a native <dialog> in the card's own shadow DOM, opened modally. The
// platform traps the focus, closes it on Escape and makes the page behind inert, so the card
// needs nothing of the frontend's own dialogs. This is the shell; the timer's controls come
// into it later.
import { LitElement, css, html, nothing, type PropertyValues } from "lit";
import type { CardConfig } from "./config";
import type { HomeAssistant, TimerInfo } from "./hass";
import { t } from "./strings";
import { mattersToRender, watchedEntities, type TimerView } from "./timer";

export class TimerifyCardPopup extends LitElement {
  static override properties = {
    hass: { attribute: false },
    config: { attribute: false },
    info: { attribute: false },
    view: { attribute: false },
    opened: { state: true },
  };

  static override styles = css`
    dialog {
      box-sizing: border-box;
      width: 100%;
      max-width: 420px;
      padding: 0;
      border: none;
      border-radius: var(--ha-border-radius-lg, 16px);
      background: var(--card-background-color);
      color: var(--primary-text-color);
    }
    dialog::backdrop {
      background: rgba(0, 0, 0, 0.4);
    }
    @media (max-width: 450px) {
      dialog {
        max-width: 100%;
      }
    }
    .wrapper {
      padding: 16px;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    h2 {
      margin: 0;
      font-size: var(--ha-font-size-xl, 1.25rem);
      font-weight: 500;
    }
    button.close {
      padding: 8px 12px;
      border: none;
      border-radius: var(--ha-border-radius-md, 8px);
      background: none;
      color: var(--primary-color);
      font: inherit;
      cursor: pointer;
    }
    button.close:focus-visible {
      outline: 2px solid var(--primary-color);
      outline-offset: 2px;
    }
  `;

  declare hass: HomeAssistant;
  declare config: CardConfig;
  /** What Timerify told of the timer. */
  declare info: TimerInfo;
  /** What the card shows of the timer; the card makes a new one at every render, so it ticks. */
  declare view: TimerView;
  /** Whether the dialog is open; only then does the pop-up have anything to render. */
  declare opened: boolean;

  constructor() {
    super();
    this.opened = false;
  }

  /** Shows the pop-up over the page. */
  open(): void {
    this.opened = true;
  }

  /** Closes the pop-up; the card gets the focus back. */
  close(): void {
    this.#dialog?.close();
    this.#settle();
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    // A dialog that is taken off the page keeps its `open` attribute but is not modal any more.
    this.close();
  }

  get #dialog(): HTMLDialogElement | null {
    return this.renderRoot.querySelector("dialog");
  }

  /**
   * The browser announces a closed dialog some time after it closed. If the pop-up has been
   * opened again since, the announcement is out of date and must not close it.
   */
  readonly #onClose = (): void => {
    if (!this.#dialog?.open) {
      this.#settle();
    }
  };

  /** The dialog is closed, however that came about: tell the card, once. */
  #settle(): void {
    if (this.opened) {
      this.opened = false;
      this.dispatchEvent(new CustomEvent("closed"));
    }
  }

  protected override shouldUpdate(changed: PropertyValues): boolean {
    if (!this.hasUpdated || changed.has("opened")) {
      return true;
    }
    const watched = watchedEntities(this.config.entity, this.info);
    return this.opened && mattersToRender(changed, this.hass, watched);
  }

  protected override updated(changed: PropertyValues): void {
    const dialog = this.#dialog;
    if (changed.has("opened") && this.opened && dialog && !dialog.open) {
      dialog.showModal();
    }
  }

  protected override render() {
    return html`
      <dialog
        aria-labelledby="title"
        @cancel=${() => this.close()}
        @close=${this.#onClose}
        @click=${(event: MouseEvent) => {
          // A click on the backdrop has the dialog itself as its target; the dialog has no
          // padding, so a click anywhere else in it has one of the things inside.
          if (event.target === event.currentTarget) {
            this.close();
          }
        }}
      >
        ${this.opened ? this.#content() : nothing}
      </dialog>
    `;
  }

  #content() {
    return html`
      <div class="wrapper">
        <header>
          <h2 id="title">${this.view.name}</h2>
          <button class="close" @click=${() => this.close()}>
            ${t(this.hass, "card_close")}
          </button>
        </header>
      </div>
    `;
  }
}
