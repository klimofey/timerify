// What the two layouts of the card have in common: the icon, what the card says of the timer's
// state, and the styles of the layer that is pressed and of the text above it. Each layout
// (pill.ts, round.ts) draws only its own shape.
import { css, html, nothing, type TemplateResult } from "lit";
import type { CardConfig } from "./config";
import { formatClock, formatRemaining } from "./format";
import type { HomeAssistant } from "./hass";
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
  return html`
    <button class="turn-off" type="button" @click=${turnOff}>${t(hass, "card_turn_off")}</button>
  `;
}

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

