// The Timerify dashboard card: one timer on a dashboard, found through its "Run for" number.
// Everything it shows is read from the states of the timer's entities; everything it does
// goes through Timerify's own services.
import { LitElement, css, html, nothing, type PropertyValues } from "lit";
import { parseConfig, type CardConfig } from "./config";
import type { HassEntity, HomeAssistant } from "./hass";
import { PressController } from "./press";
import { TimerifyCardPopup } from "./popup";
import { lastLoaded, loadStrings, onStringsLoaded, t } from "./strings";
import {
  lookupTimer,
  mattersToRender,
  timerView,
  watchedEntities,
  type TimerLookup,
} from "./timer";

const TAG = "timerify-card";

const GRID_OPTIONS = {
  pill: { columns: 6, rows: 1, min_columns: 3, min_rows: 1, max_rows: 1 },
  round: { columns: 3, rows: 2, min_columns: 2, min_rows: 2, max_rows: 3 },
} as const;

/** Whether an entity has a value: it exists, and is neither unavailable nor unknown. */
const hasValue = (entity: HassEntity | undefined): boolean =>
  entity !== undefined && entity.state !== "unavailable" && entity.state !== "unknown";

export class TimerifyCard extends LitElement {
  static override properties = {
    // `hass` has an accessor of its own: it is replaced on every change in the home, and the
    // card has to look at what changed before it asks anything or draws anything.
    hass: { attribute: false, noAccessor: true },
    _config: { state: true },
    _lookup: { state: true },
  };

  static override styles = css`
    :host {
      display: block;
    }
    ha-card {
      height: 100%;
    }
    .body {
      display: flex;
      align-items: center;
      gap: 12px;
      box-sizing: border-box;
      height: 100%;
      min-height: 56px;
      padding: 8px 16px;
      border-radius: inherit;
      cursor: pointer;
    }
    .body:focus-visible {
      outline: 2px solid var(--primary-color);
      outline-offset: 2px;
    }
    .name {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .warning {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 16px;
      color: var(--warning-color);
    }
  `;

  declare _config: CardConfig | undefined;
  declare _lookup: TimerLookup;

  #hass: HomeAssistant | undefined;
  /** Work that is under way, which `updateComplete` waits for. */
  readonly #pending = new Set<Promise<unknown>>();
  #lookingUp = false;
  #askAgain = false;
  readonly #press = new PressController(this, { tap: () => this.#popup?.open() });
  readonly #binding = this.#press.binding();

  constructor() {
    super();
    this._lookup = { status: "pending" };
  }

  get hass(): HomeAssistant | undefined {
    return this.#hass;
  }

  set hass(hass: HomeAssistant) {
    const previous = this.#hass;
    this.#hass = hass;
    this.requestUpdate("hass", previous);
    this.#follow(previous, hass);
  }

  /** Home Assistant calls this with the card's config; an invalid one is refused with an error. */
  setConfig(raw: unknown): void {
    const config = parseConfig(raw);
    const newTimer = this._config?.entity !== config.entity;
    this._config = config;
    if (newTimer) {
      this._lookup = { status: "pending" };
      this.#ask();
    }
  }

  /** The height in units of 50 pixels, for dashboards in masonry layout. */
  getCardSize(): number {
    return this._config?.layout === "round" ? 3 : 1;
  }

  /** The size in cells, for dashboards in sections layout. */
  getGridOptions() {
    return GRID_OPTIONS[this._config?.layout ?? "pill"];
  }

  /**
   * Also waits for the questions to Timerify and for the strings that are on their way.
   * Only tests await this: no frontend code awaits a card's updateComplete, and none may,
   * since a question that never comes back would hold it.
   */
  protected override async getUpdateComplete(): Promise<boolean> {
    let updated = await super.getUpdateComplete();
    while (this.#pending.size > 0) {
      await Promise.allSettled([...this.#pending]);
      updated = await super.getUpdateComplete();
    }
    return updated;
  }

  /** Looks at what a new `hass` changes for the card, and asks again when it has to. */
  #follow(previous: HomeAssistant | undefined, hass: HomeAssistant): void {
    const reconnected = previous !== undefined && hass.connected && !previous.connected;
    if (previous === undefined || previous.language !== hass.language || reconnected) {
      this.#track(loadStrings(hass));
    }
    const entityId = this._config?.entity;
    if (entityId === undefined) {
      return;
    }
    if (
      previous === undefined ||
      previous.entities !== hass.entities ||
      reconnected ||
      (hasValue(hass.states[entityId]) && !hasValue(previous.states[entityId]))
    ) {
      this.#ask();
    }
  }

  #track(work: Promise<unknown>): void {
    const tracked: Promise<unknown> = work.finally(() => this.#pending.delete(tracked));
    this.#pending.add(tracked);
  }

  /**
   * Asks Timerify which timer the number belongs to. One question is on its way at a time; a
   * reason to ask that comes up meanwhile makes the answer to that question stale, and the
   * newest question is the one whose answer is shown.
   */
  #ask(): void {
    if (this.#lookingUp) {
      this.#askAgain = true;
      return;
    }
    this.#lookingUp = true;
    this.#track(this.#lookUp());
  }

  async #lookUp(): Promise<void> {
    try {
      do {
        this.#askAgain = false;
        const entityId = this._config?.entity;
        if (this.#hass === undefined || entityId === undefined) {
          return;
        }
        const lookup = await lookupTimer(this.#hass, entityId);
        if (!this.#askAgain) {
          this._lookup = lookup;
        }
      } while (this.#askAgain);
    } finally {
      this.#lookingUp = false;
    }
  }

  protected override shouldUpdate(changed: PropertyValues): boolean {
    const info = this._lookup.status === "found" ? this._lookup.info : undefined;
    const watched = this._config ? watchedEntities(this._config.entity, info) : [];
    return mattersToRender(changed, this.#hass, watched);
  }

  get #popup(): TimerifyCardPopup | null {
    return this.renderRoot.querySelector("timerify-card-popup");
  }

  /** What the user is told when the card has no timer to show, if anything. */
  #warning(hass: HomeAssistant, config: CardConfig): string | undefined {
    if (this._lookup.status !== "not_found") {
      return undefined;
    }
    const number = hass.states[config.entity];
    if (number === undefined) {
      return t(hass, "card_entity_not_found", { entity: config.entity });
    }
    // A number that is unavailable or unknown may be a timer that is still starting: it asks
    // again when the number has a value.
    return hasValue(number) ? t(hass, "card_not_a_timer", { entity: config.entity }) : undefined;
  }

  protected override render() {
    const hass = this.#hass;
    const config = this._config;
    if (!hass || !config) {
      return nothing;
    }
    const warning = this.#warning(hass, config);
    if (warning) {
      return html`
        <ha-card>
          <div class="warning" role="alert">
            <ha-icon icon="mdi:alert-outline"></ha-icon>
            <span>${warning}</span>
          </div>
        </ha-card>
      `;
    }
    const view = timerView(hass, config, this._lookup, Date.now());
    const icon =
      "stateObj" in view.icon
        ? html`<ha-state-icon .stateObj=${view.icon.stateObj}></ha-state-icon>`
        : html`<ha-icon .icon=${view.icon.icon}></ha-icon>`;
    return html`
      <ha-card>
        <div
          class="body"
          role="button"
          tabindex="0"
          aria-haspopup="dialog"
          @click=${this.#binding.click}
          @keydown=${this.#binding.keydown}
          @keyup=${this.#binding.keyup}
        >
          ${icon}
          <span class="name">${view.name}</span>
        </div>
      </ha-card>
      ${this._lookup.status === "found"
        ? html`
            <timerify-card-popup
              .hass=${hass}
              .config=${config}
              .info=${this._lookup.info}
              .view=${view}
              @closed=${() => this.renderRoot.querySelector<HTMLElement>(".body")?.focus()}
            ></timerify-card-popup>
          `
        : nothing}
    `;
  }
}

/** What a custom card tells the card picker of itself. */
interface CustomCardEntry {
  type: string;
  name?: string;
  description?: string;
  preview?: boolean;
  documentationURL?: string;
}

declare global {
  interface Window {
    customCards?: CustomCardEntry[];
  }
  interface HTMLElementTagNameMap {
    "timerify-card": TimerifyCard;
    "timerify-card-popup": TimerifyCardPopup;
  }
}

// A second copy of this module (a dashboard resource added by hand next to the one Timerify
// loads) must neither throw nor list the card twice.
if (!customElements.get(TAG)) {
  customElements.define("timerify-card-popup", TimerifyCardPopup);
  customElements.define(TAG, TimerifyCard);
  const entry: CustomCardEntry = {
    type: TAG,
    name: "Timerify",
    description: t(undefined, "card_picker_description"),
    preview: true,
    documentationURL: "https://github.com/klimofey/timerify#dashboard-card",
  };
  // The picker reads the array that is there: it is added to, never replaced.
  (window.customCards ??= []).push(entry);
  onStringsLoaded(() => {
    entry.description = t(lastLoaded(), "card_picker_description");
  });
}
