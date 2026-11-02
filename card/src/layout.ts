// What the two layouts of the card have in common: the icon, what the card says of the timer's
// state, and the styles of the layer that is pressed and of the text above it. Each layout
// (pill.ts, round.ts) draws only its own shape.
import { css, html, nothing, type CSSResult, type TemplateResult } from "lit";
import type { CardConfig } from "./config";
import { formatClock, formatRemaining } from "./format";
import type { HomeAssistant } from "./hass";
import { mush } from "./mushroom";
import { t } from "./strings";
import { hasValue, isRunning, type TimerView } from "./timer";

/** The icon of the timer's target, or the one the config chooses. */
export function renderIcon(view: TimerView): TemplateResult {
  return "stateObj" in view.icon
    ? html`<ha-state-icon .stateObj=${view.icon.stateObj}></ha-state-icon>`
    : html`<ha-icon .icon=${view.icon.icon}></ha-icon>`;
}

/**
 * What the body announces of a tap, to assistive technology: that it opens a dialog, when the
 * tap is set to open the pop-up, and nothing when it is set to do anything else.
 */
export const popupAnnounced = (config: CardConfig): "dialog" | undefined =>
  config.tap === "popup" ? "dialog" : undefined;

/**
 * Whether the body does anything when it is pressed. A body whose tap, double tap and long
 * press are all set to nothing is no button and has no tab stop, as in Home Assistant's own
 * tile card; one that does something on any press is both.
 */
export const isPressable = (config: CardConfig): boolean =>
  config.tap !== "none" || config.double_tap !== "none" || config.hold !== "none";

/**
 * The Turn off button, when the config asks for it and the target runs, with a countdown or
 * without one: a button of its own beside the body, whose press `turnOff` answers and the
 * body never hears of. A timer that is unavailable, or not found yet, is not running.
 */
export function renderTurnOff(
  view: TimerView,
  config: CardConfig,
  hass: HomeAssistant,
  turnOff: () => void,
) {
  if (!config.show_turn_off || !isRunning(view)) {
    return nothing;
  }
  const label = t(hass, "card_turn_off");
  // Both forms are in the button, and the styles choose, from the width of the card, which one
  // shows (`turnOffAsIcon`); the name and the tip are the same in both.
  return html`
    <button class="turn-off" type="button" aria-label=${label} title=${label} @click=${turnOff}>
      <ha-icon class="turn-off-icon" icon="mdi:power"></ha-icon>
      <span class="turn-off-label">${label}</span>
    </button>
  `;
}

/**
 * The width of a card's content, in px, from which the Turn off button shows its words and not
 * its icon alone. The button is 101 px wide in Russian, the longer of the two words, the chip
 * is 78 px, the icon 40 px, the gaps 12 px. The pill keeps 80 px for the name beside the words
 * (about ten characters), so it is 40 + 12 + 80 + 12 + 101 without a chip, and 90 more with
 * one: a longer word in another language is taken up by the name, which gives way first. The
 * round tile has the whole width under its dial, so the words need 101. Measured in a real
 * Home Assistant: see RULINGS and `card/e2e/sizes.spec.ts`.
 */
export const WORDS_FROM = { pill: 245, pillWithChip: 335, round: 101 } as const;

/**
 * The Turn off button as its icon alone, for a card too narrow for its words: a round button
 * that is a comfortable target for a finger, 40 px. `scope` is the selector of the cards it is
 * for, and the rules go in an `@container` block of the layout's own, where the width is. In
 * the Mushroom style it is Mushroom's control instead: as high as the theme says, as wide as
 * that makes it times the ratio of its buttons, and rounded as its controls are.
 */
export const turnOffAsIcon = (scope: CSSResult) => css`
  ${scope} .turn-off {
    width: 40px;
    height: 40px;
    padding: 0;
    border-radius: 20px;
  }
  ${scope} .turn-off-label {
    display: none;
  }
  ${scope} .turn-off-icon {
    display: flex;
  }
  :host([data-mushroom]) ${scope} .turn-off {
    width: calc(${mush.controlHeight} * ${mush.controlButtonRatio});
    height: ${mush.controlHeight};
    padding: 0;
    border-radius: ${mush.controlRadius};
  }
`;

/**
 * What the card says under the name while nothing counts: the state of the target in the
 * user's language, or that the timer is unavailable. A timer that has a value and is only
 * waiting to be found says nothing yet, so a page that has just opened shows no flicker.
 */
function stateText(view: TimerView, config: CardConfig, hass: HomeAssistant): string {
  if (view.state !== "unavailable") {
    return view.target ? hass.formatEntityState(view.target) : "";
  }
  const number = hass.states[config.entity];
  if (hasValue(number)) {
    return "";
  }
  // Home Assistant's own word for it, whatever the entity.
  const unavailable = { entity_id: config.entity, state: "unavailable", attributes: {} };
  return hass.formatEntityState(number ?? unavailable, "unavailable");
}

/**
 * What the card says of the timer's state: the time left and when it ends while counting,
 * else the state of the target (or that the timer is unavailable).
 */
export function renderStatus(
  view: TimerView,
  config: CardConfig,
  hass: HomeAssistant,
  now: number,
) {
  if (view.state !== "counting" || view.endsAt === undefined) {
    return stateText(view, config, hass);
  }
  const time = formatClock(hass, view.endsAt, now);
  return html`
    <span class="remaining">${formatRemaining(view.remaining)}</span>
    <span class="until">${t(hass, "card_until", { time })}</span>
  `;
}

/**
 * What the layouts share. The body is the layer that is pressed: it covers the whole card,
 * border included, under the content, and the content lets presses through to it, as in Home
 * Assistant's tile card. The radius is the layout's own, `--timerify-radius` on `ha-card`.
 */
export const commonStyles = css`
  /*
   * A long touch must bring up neither a text selection nor the browser's callout. The text
   * is in the content, not in the body, so the rule is on the card, and so on all it holds;
   * the pop-up is beside the card, and its text stays selectable.
   */
  ha-card.pill,
  ha-card.round {
    user-select: none;
    -webkit-user-select: none;
    -webkit-touch-callout: none;
  }
  .body {
    position: absolute;
    inset: 0;
    /* Inset reaches the padding box; the card's border is part of what a press hits. */
    margin: calc(-1 * var(--ha-card-border-width, 1px));
    border-radius: var(--timerify-radius);
    /* No flash of the browser's own highlight on a tap, as in the tile card. */
    -webkit-tap-highlight-color: transparent;
  }
  .body[role="button"] {
    cursor: pointer;
  }
  .body:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  .content {
    position: relative;
    box-sizing: border-box;
    height: 100%;
    /* A press anywhere on the card reaches the body underneath, except on a control. */
    pointer-events: none;
  }
  /*
   * The width of the content is what the Turn off button chooses its form by, so the content of
   * a card that has the button is a container, and that of any other card is left as it was.
   */
  .with-turn-off .content {
    container-type: inline-size;
  }
  /* The small buttons that sit on the card beside its body: the pill's chip, and Turn off. */
  .chip,
  .turn-off {
    flex: none;
    height: 32px;
    padding: 0 12px;
    border: none;
    border-radius: 16px;
    background: var(--secondary-background-color);
    color: var(--primary-text-color);
    font: inherit;
    font-size: var(--ha-font-size-m, 14px);
    cursor: pointer;
    pointer-events: auto;
  }
  .turn-off {
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  /* The words by default; a narrow card shows the icon instead, see turnOffAsIcon. */
  .turn-off-icon {
    --mdc-icon-size: 24px;
    display: none;
  }
  .chip:focus-visible,
  .turn-off:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  .icon {
    color: var(--state-icon-color, var(--secondary-text-color));
  }
  .counting .icon,
  .open .icon {
    color: var(--state-active-color, var(--primary-color));
  }
  .unavailable .icon {
    color: var(--state-unavailable-color, var(--disabled-text-color));
  }
  .name {
    overflow: hidden;
    color: var(--primary-text-color);
    font-size: var(--ha-font-size-m, 14px);
    font-weight: var(--ha-font-weight-medium, 500);
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .remaining {
    font-variant-numeric: tabular-nums;
  }
  /* What a layout shows while letting go of a long press would act: it pulses. */
  @keyframes pulse {
    from {
      opacity: 1;
      transform: scale(1);
    }
    to {
      opacity: 0.6;
      transform: scale(1.08);
    }
  }
`;


/**
 * What the Mushroom style changes in what the layouts share, where it is on (`data-mushroom`
 * on the card, see `mushroom.ts`). It only adds to the rules above, with a selector that is
 * more specific than theirs, so a card that is not in the Mushroom style is what it was. The
 * icon becomes Mushroom's icon shape, a circle that is tinted while the device is on; the
 * texts, the chip and the Turn off button take Mushroom's fonts and sizes. What each layout
 * changes for itself is at the end of its own styles.
 */
export const mushroomStyles = css`
  :host([data-mushroom]) .icon {
    display: flex;
    flex: none;
    align-items: center;
    justify-content: center;
    width: ${mush.iconSize};
    height: ${mush.iconSize};
    border-radius: ${mush.iconRadius};
    background: rgba(${mush.disabledRgb}, 0.2);
    color: rgb(${mush.disabledRgb});
    /* The size of the shape is the em of the symbol's size, as in Mushroom. */
    font-size: ${mush.iconSize};
    line-height: 0;
    --mdc-icon-size: ${mush.iconSymbolSize};
    transition:
      background-color 280ms ease-in-out,
      color 280ms ease-in-out;
  }
  :host([data-mushroom]) .counting .icon,
  :host([data-mushroom]) .open .icon {
    background: rgba(${mush.activeRgb}, 0.2);
    color: rgb(${mush.activeRgb});
  }
  :host([data-mushroom]) .name {
    color: ${mush.primaryColor};
    font-size: ${mush.primaryFontSize};
    font-weight: ${mush.primaryFontWeight};
    line-height: ${mush.primaryLineHeight};
    letter-spacing: ${mush.primaryLetterSpacing};
  }
  /* Mushroom's chip: a small pill with a border, as high as the theme says. */
  :host([data-mushroom]) .chip {
    display: flex;
    align-items: center;
    justify-content: center;
    box-sizing: border-box;
    height: ${mush.chipHeight};
    padding: ${mush.chipPadding};
    border: ${mush.chipBorderWidth} solid ${mush.chipBorderColor};
    border-radius: ${mush.chipRadius};
    background: ${mush.chipBackground};
    box-shadow: ${mush.chipBoxShadow};
    /* The size of the chip is the em of its padding and its text, as in Mushroom. */
    font-size: ${mush.chipHeight};
    line-height: 0;
  }
  :host([data-mushroom]) .chip-text {
    font-size: ${mush.chipFontSize};
    font-weight: ${mush.chipFontWeight};
    line-height: 1;
  }
  /* Mushroom's control: its Turn off button has its height, its radius and its fill. */
  :host([data-mushroom]) .turn-off {
    height: ${mush.controlHeight};
    padding: 0 ${mush.controlSpacing};
    border-radius: ${mush.controlRadius};
    background: rgba(var(--rgb-primary-text-color), 0.05);
  }
  :host([data-mushroom]) .turn-off-icon {
    /* The symbol of the control is the em of its height, as in Mushroom. */
    font-size: ${mush.controlHeight};
    --mdc-icon-size: ${mush.controlIconSize};
  }
`;
