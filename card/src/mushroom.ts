// The Mushroom style: a card whose config asks for it takes the look of Mushroom's cards (the
// styles read Mushroom's theme variables, see `layout.ts`) while Mushroom is on the page.
//
// Mushroom is a resource of the dashboard that loads on its own, before or after this card, and
// the page can only be asked whether its cards are defined: `customElements.get`. So a card
// asks again when Mushroom's cards become defined, and until then it keeps the Home Assistant
// look. Only the names of Mushroom's theme variables are shared; none of its code is used.
import {
  unsafeCSS,
  type CSSResult,
  type ReactiveController,
  type ReactiveControllerHost,
} from "lit";

/** One of Mushroom's cards, whose definition says that Mushroom is on the page. */
export const MUSHROOM_CARD = "mushroom-entity-card";

/** The attribute of the card that its styles select the Mushroom style by. */
const STYLE_ATTRIBUTE = "data-mushroom";

/** Mushroom's theme variable `--mush-<name>`, falling back on `fallback`: Mushroom's default. */
const variable = (name: string, fallback: string): CSSResult =>
  unsafeCSS(`var(--mush-${name}, ${fallback})`);

/**
 * The theme variables of Mushroom that the card reads in the Mushroom style, each with the
 * value Mushroom itself uses when a theme does not set it. Only the names and the values are
 * Mushroom's; the styles that use them are the card's own. Values in `em` are, as in Mushroom,
 * relative to the size of the part they are for, which the styles give as its font size.
 */
export const mush = {
  spacing: variable("spacing", "10px"),
  iconSize: variable("icon-size", "36px"),
  iconRadius: variable("icon-border-radius", "50%"),
  iconSymbolSize: variable("icon-symbol-size", "0.667em"),
  primaryColor: variable("card-primary-color", "var(--primary-text-color)"),
  primaryFontSize: variable("card-primary-font-size", "14px"),
  primaryFontWeight: variable("card-primary-font-weight", "500"),
  primaryLineHeight: variable("card-primary-line-height", "20px"),
  primaryLetterSpacing: variable("card-primary-letter-spacing", "0.1px"),
  secondaryColor: variable("card-secondary-color", "var(--primary-text-color)"),
  secondaryFontSize: variable("card-secondary-font-size", "12px"),
  secondaryFontWeight: variable("card-secondary-font-weight", "400"),
  secondaryLineHeight: variable("card-secondary-line-height", "16px"),
  secondaryLetterSpacing: variable("card-secondary-letter-spacing", "0.4px"),
  controlHeight: variable("control-height", "42px"),
  controlRadius: variable("control-border-radius", "12px"),
  controlButtonRatio: variable("control-button-ratio", "1"),
  controlIconSize: variable("control-icon-size", "0.5em"),
  controlSpacing: variable("control-spacing", "12px"),
  chipHeight: variable("chip-height", "36px"),
  chipRadius: variable("chip-border-radius", "19px"),
  chipPadding: variable("chip-padding", "0 0.25em"),
  chipFontSize: variable("chip-font-size", "0.3em"),
  chipFontWeight: variable("chip-font-weight", "bold"),
  chipBorderWidth: variable("chip-border-width", "var(--ha-card-border-width, 1px)"),
  chipBorderColor: variable(
    "chip-border-color",
    "var(--ha-card-border-color, var(--divider-color, #e0e0e0))",
  ),
  chipBoxShadow: variable("chip-box-shadow", "var(--ha-card-box-shadow, none)"),
  chipBackground: variable(
    "chip-background",
    "var(--ha-card-background, var(--card-background-color, white))",
  ),
  /*
   * Colours, each as the triplet of red, green and blue that `rgb()` takes. What is on is
   * Mushroom's blue; what is off or unavailable is its disabled grey, which is light or dark
   * with the theme, as Home Assistant's own disabled text is.
   */
  activeRgb: variable("rgb-state-entity", "var(--mush-rgb-blue, 33, 150, 243)"),
  disabledRgb: variable("rgb-disabled", "var(--rgb-disabled-text-color, 189, 189, 189)"),
} as const;

/** Whether Mushroom has defined its cards on this page. */
export const mushroomIsDefined = (): boolean => customElements.get(MUSHROOM_CARD) !== undefined;

/**
 * The cards that are on the page and wait for Mushroom. A card is in the set only while it is
 * connected, so that a card which leaves the page before Mushroom arrives is not kept by a wait
 * that may never end; the one wait for all of them holds nothing but this set.
 */
const waiting = new Set<ReactiveControllerHost>();
let waitingForMushroom = false;

function wait(host: ReactiveControllerHost): void {
  waiting.add(host);
  if (waitingForMushroom) {
    return;
  }
  waitingForMushroom = true;
  void customElements.whenDefined(MUSHROOM_CARD).then(() => {
    for (const card of waiting) {
      card.requestUpdate();
    }
    waiting.clear();
  });
}

/**
 * Marks its host `data-mushroom` while the host's config asks for the Mushroom style and
 * Mushroom is on the page. The wait for Mushroom is never part of the host's `updateComplete`:
 * nothing is tracked, and a host that is not on the page waits for nothing.
 */
export class MushroomController implements ReactiveController {
  readonly #host: ReactiveControllerHost & HTMLElement;
  readonly #asked: () => boolean;

  /** `asked` says whether the host's config asks for the Mushroom style, now. */
  constructor(host: ReactiveControllerHost & HTMLElement, asked: () => boolean) {
    this.#host = host;
    this.#asked = asked;
    host.addController(this);
  }

  hostConnected(): void {
    this.#follow();
  }

  /** The config can change the answer with any update of the host. */
  hostUpdate(): void {
    this.#follow();
  }

  hostDisconnected(): void {
    waiting.delete(this.#host);
  }

  #follow(): void {
    const asked = this.#asked();
    const defined = mushroomIsDefined();
    this.#host.toggleAttribute(STYLE_ATTRIBUTE, asked && defined);
    if (asked && !defined && this.#host.isConnected) {
      wait(this.#host);
    } else {
      waiting.delete(this.#host);
    }
  }
}
