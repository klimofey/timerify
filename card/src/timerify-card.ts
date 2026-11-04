// The Timerify dashboard card: one timer on a dashboard, found through its "Run for" number.
// Everything it shows is read from the states of the timer's entities; everything it does
// goes through Timerify's own services.
import { LitElement, css, html, nothing, type PropertyValues } from "lit";
import { addMinutes, runWithoutDuration, stop } from "./actions";
import { ACTION_KEYS, parseConfig, type CardConfig, type Press } from "./config";
import { CountdownController } from "./countdown";
import { getConfigForm, getStubConfig } from "./editor";
import { displayTimeZone } from "./format";
import type { HomeAssistant } from "./hass";
import { commonStyles, isPressable, mushroomStyles } from "./layout";
import { MidnightController } from "./midnight";
import { MushroomController } from "./mushroom";
import { pillStyles, renderPill } from "./pill";
import { TimerifyCardPopup } from "./popup";
import { PressController, type PressActions } from "./press";
import { renderRound, roundStyles } from "./round";
import { lastLoaded, loadStrings, onStringsLoaded, t } from "./strings";
import {
  hasValue,
  isDisabled,
  isRunning,
  lookupTimer,
  mattersToRender,
  serverNow,
  timerView,
  watchedEntities,
  type TimerLookup,
  type TimerView,
} from "./timer";

const TAG = "timerify-card";

const GRID_OPTIONS = {
  pill: { columns: 6, rows: 1, min_columns: 3, min_rows: 1, max_rows: 1 },
  round: { columns: 3, rows: 2, min_columns: 2, min_rows: 2, max_rows: 3 },
  // The Turn off button needs room: a row taller on the round tile, and columns for the icon
  // form of the button (a narrow card shows only that, see `turnOffAsIcon`) on the narrowest
  // sections Home Assistant makes, a phone 320 px wide. A minimum is one number for every
  // screen, so it is the fewest columns that fit there, and no more: a wider card shows the
  // words. Measured in a real Home Assistant, see RULINGS. A card starts at its old size where
  // that fits on a phone 390 px wide, and at the minimum where it does not (the pill with a
  // chip).
  pillWithTurnOff: { columns: 6, rows: 1, min_columns: 6, min_rows: 1, max_rows: 1 },
  pillWithTurnOffAndChip: { columns: 9, rows: 1, min_columns: 9, min_rows: 1, max_rows: 1 },
  roundWithTurnOff: { columns: 3, rows: 3, min_columns: 3, min_rows: 3, max_rows: 3 },
} as const;

export class TimerifyCard extends LitElement {
  static override properties = {
    // `hass` has an accessor of its own: it is replaced on every change in the home, and the
    // card has to look at what changed before it asks anything or draws anything.
    hass: { attribute: false, noAccessor: true },
    _config: { state: true },
    _lookup: { state: true },
  };

  static override styles = [
    commonStyles,
    pillStyles,
    roundStyles,
    mushroomStyles,
    css`
      :host {
        display: block;
      }
      .warning {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px;
        color: var(--warning-color);
      }
    `,
  ];

  /** The visual editor's form and the config of a card the user has just picked. */
  static getConfigForm = getConfigForm;
  static getStubConfig = getStubConfig;

  declare _config: CardConfig | undefined;
  declare _lookup: TimerLookup;

  #hass: HomeAssistant | undefined;
  /** Work that is under way, which `updateComplete` waits for. */
  readonly #pending = new Set<Promise<unknown>>();
  #lookingUp = false;
  #askAgain = false;
  /** How both layouts are pressed: what a press does is what the config says at that moment. */
  readonly #press = new PressController(this, () => this.#pressActions());
  readonly #binding = this.#press.binding();
  /** The pill's chip: adds its minutes to the timer, whatever the card's clock says. */
  readonly #addChipMinutes = (): void => {
    const { _config: config, hass } = this;
    if (config?.chip !== undefined && hass !== undefined) {
      void addMinutes(hass, config.entity, config.chip);
    }
  };
  /** The Turn off button: stops the timer, as the pop-up's Stop does. */
  readonly #turnOff = (): void => {
    const { _config: config, hass } = this;
    if (config !== undefined && hass !== undefined) {
      void stop(hass, config.entity);
    }
  };
  /** What the last render showed of the timer: the countdown ticks while it has an end ahead. */
  #view: TimerView | undefined;
  /** The Turn off button had the focus when the card began to draw what it shows now. */
  #turnOffHadFocus = false;

  constructor() {
    super();
    this._lookup = { status: "pending" };
    new CountdownController(
      this,
      // A limit shows a time of day alone, which a tick would not change.
      () => (this.#view?.state === "counting" ? this.#view.endsAt : undefined),
      () => serverNow(this._lookup),
    );
    // A limit that ends on another day is written with its weekday, which nothing else redraws
    // when the day changes.
    new MidnightController(
      this,
      () => (this.#view?.state === "limit" && this.#view.endsAt ? [this.#view.endsAt] : []),
      () => serverNow(this._lookup),
      () => (this.#hass ? displayTimeZone(this.#hass) : undefined),
    );
    // The card is marked while its config asks for the Mushroom style and Mushroom is there.
    new MushroomController(this, () => this._config?.mushroom === true);
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
    if (this._config?.layout !== "round") {
      return 1;
    }
    return this._config.show_turn_off ? 4 : 3;
  }

  /** The size in cells, for dashboards in sections layout. */
  getGridOptions() {
    const config = this._config;
    if (config?.layout === "round") {
      return config.show_turn_off ? GRID_OPTIONS.roundWithTurnOff : GRID_OPTIONS.round;
    }
    if (!config?.show_turn_off) {
      return GRID_OPTIONS.pill;
    }
    return config.chip === undefined
      ? GRID_OPTIONS.pillWithTurnOff
      : GRID_OPTIONS.pillWithTurnOffAndChip;
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

  protected override willUpdate(): void {
    this.#turnOffHadFocus = this.shadowRoot?.activeElement?.classList.contains("turn-off") === true;
  }

  /**
   * The Turn off button goes when the device goes off, and the focus goes with it: to the page,
   * so that the next Tab would start from the top of the dashboard. Whoever pressed it, by the
   * keyboard or by any press that leaves the focus on the button (a click in Chrome or Firefox
   * does, a tap on Android), is left on the body of the card, as the pop-up does when it
   * closes. That is harmless for a press that is not the keyboard's: no ring shows without it.
   */
  protected override updated(): void {
    if (this.#turnOffHadFocus && this.shadowRoot?.querySelector(".turn-off") === null) {
      this.#focusBody();
    }
  }

  /** Puts the focus on the body of the card, when it is a button: see `isPressable`. */
  #focusBody(): void {
    const config = this._config;
    if (config !== undefined && isPressable(config)) {
      this.renderRoot.querySelector<HTMLElement>(".body")?.focus();
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

  /**
   * What the card can do for each press. A tap is always there. A double tap and a long press
   * exist only when they are set to something, because a card that has a double tap makes a
   * tap wait for it, and one that has a long press takes the click of a long press away.
   */
  #pressActions(): PressActions {
    const config = this._config;
    const actions: PressActions = { tap: () => this.#perform("tap") };
    if (config !== undefined && config.double_tap !== "none") {
      actions.doubleTap = () => this.#perform("double_tap");
    }
    if (config !== undefined && config.hold !== "none") {
      actions.hold = () => this.#perform("hold");
    }
    return actions;
  }

  /** Does what the config sets a press to. */
  #perform(press: Press): void {
    const { _config: config, hass } = this;
    if (config === undefined || hass === undefined) {
      return;
    }
    switch (config[press]) {
      case "popup":
        // A pointer may still be down on the card, and its release will land on the dialog.
        this.#press.cancelPress();
        this.#popup?.open();
        break;
      case "run":
        void runWithoutDuration(hass, config.entity);
        break;
      case "stop":
        void stop(hass, config.entity);
        break;
      case "run_or_stop":
        this.#runOrStop(hass, config);
        break;
      case "action":
        this.#fireAction(press, config);
        break;
      case "none":
        break;
    }
  }

  /**
   * What "Start or stop" does: stops the timer when it runs, with a countdown, under a limit or
   * without either; starts it, with no duration, when it is idle. A timer that is unavailable
   * has nothing to act on.
   */
  #runOrStop(hass: HomeAssistant, config: CardConfig): void {
    const view = this.#view;
    if (view === undefined) {
      return;
    }
    if (isRunning(view)) {
      void stop(hass, config.entity);
    } else if (view.state === "idle") {
      void runWithoutDuration(hass, config.entity);
    }
  }

  /**
   * Hands a press to Home Assistant's own handler of actions, which does what the user chose
   * in the editor: "more-info" and "toggle" act on the entity the timer runs, not on the
   * card's own number. An action the user did not set is left out: Home Assistant then opens
   * the more-info dialog. Until the card has found its timer it does not know that entity, and
   * does nothing.
   */
  #fireAction(press: Press, config: CardConfig): void {
    if (this._lookup.status !== "found") {
      return;
    }
    const actions = Object.fromEntries(
      ACTION_KEYS.filter((key) => config[key] !== undefined).map((key) => [key, config[key]]),
    );
    this.dispatchEvent(
      new CustomEvent("hass-action", {
        detail: { config: { entity: this._lookup.info.target, ...actions }, action: press },
        bubbles: true,
        composed: true,
      }),
    );
  }

  /**
   * What the user is told when the card has no timer to show, if anything. The card never
   * goes dead without saying why: a timer the user may not see, a timer that lacks a target
   * or a sensor the card cannot work without, and a timer whose "Ends at" sensor is disabled
   * are told. Only a timer that is starting is quiet.
   */
  #warning(hass: HomeAssistant, config: CardConfig): string | undefined {
    const lookup = this._lookup;
    if (lookup.status === "unauthorized") {
      return t(hass, "card_not_allowed", { entity: config.entity });
    }
    // Said whatever the number's state is: a sensor of the timer is missing from the registry
    // only for a moment while a new timer is set up for the first time, when the number may
    // still look like a timer that is starting, and after the sensor was deleted from the
    // registry, until the timer is set up again. The answer is read from the registry and
    // does not change until the registry does, and the card asks again then.
    if (lookup.status === "incomplete") {
      return t(hass, "card_timer_incomplete", { entity: config.entity });
    }
    if (lookup.status === "found" && isDisabled(lookup.info, lookup.info.ends_at)) {
      return t(hass, "card_ends_at_disabled", { sensor: lookup.info.ends_at });
    }
    if (lookup.status !== "not_found") {
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
      this.#view = undefined;
      return html`
        <ha-card>
          <div class="warning" role="alert">
            <ha-icon icon="mdi:alert-outline"></ha-icon>
            <span>${warning}</span>
          </div>
        </ha-card>
      `;
    }
    const now = serverNow(this._lookup);
    const view = timerView(hass, config, this._lookup, now);
    this.#view = view;
    return html`
      ${config.layout === "round"
        ? renderRound(view, config, hass, this.#binding, this.#turnOff, now)
        : renderPill(view, config, hass, this.#binding, this.#addChipMinutes, this.#turnOff, now)}
      ${this._lookup.status === "found"
        ? html`
            <timerify-card-popup
              .hass=${hass}
              .config=${config}
              .lookup=${this._lookup}
              .view=${view}
              @closed=${() => this.#focusBody()}
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
