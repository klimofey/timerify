// The pill: a card one row high, filled from the left by the share of the countdown that is
// left, with the icon, the name, the time left and when it ends, and an optional chip that
// adds a few minutes.
import { css, html, nothing, type TemplateResult } from "lit";
import { styleMap } from "lit/directives/style-map.js";
import type { CardConfig } from "./config";
import { formatClock, formatMinutes, formatRemaining } from "./format";
import type { HomeAssistant } from "./hass";
import type { PressBinding } from "./press";
import { t } from "./strings";
import { hasValue, type TimerView } from "./timer";

/** The icon of the timer's target, or the one the config chooses. */
export function renderIcon(view: TimerView): TemplateResult {
  return "stateObj" in view.icon
    ? html`<ha-state-icon .stateObj=${view.icon.stateObj}></ha-state-icon>`
    : html`<ha-icon .icon=${view.icon.icon}></ha-icon>`;
}

/**
 * What the pill says under the name while nothing counts: the state of the target in the
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
 * The card as a pill, drawn at the instant `now` that `view` was made for. Its body is an
 * empty layer under the content, as in Home Assistant's tile card: a button, pressed through
 * `binding`, that opens the pop-up, named by the name and the state it covers. The content
 * above lets presses through to it, except the chip, a button of its own beside the body:
 * `chip` is called when it is pressed, and the body never hears of it.
 */
export function renderPill(
  view: TimerView,
  config: CardConfig,
  hass: HomeAssistant,
  binding: PressBinding,
  chip: () => void,
  now: number,
): TemplateResult {
  const filled = Math.round(view.progress * 1000) / 10;
  return html`
    <ha-card class="pill ${view.state}">
      <div
        class="body"
        role="button"
        tabindex="0"
        aria-haspopup="dialog"
        aria-labelledby="label"
        @click=${binding.click}
        @keydown=${binding.keydown}
        @keyup=${binding.keyup}
      >
        <span class="fill-clip" aria-hidden="true">
          <span class="fill" style=${styleMap({ width: `${filled}%` })}></span>
        </span>
      </div>
      <div class="content">
        <span class="icon">${renderIcon(view)}</span>
        <span class="text" id="label">
          <span class="name">${view.name}</span>
          <span class="status">${renderStatus(view, config, hass, now)}</span>
        </span>
        ${config.chip === undefined
          ? nothing
          : html`
              <button
                class="chip"
                type="button"
                aria-label=${t(hass, "card_add_time", {
                  duration: formatMinutes(hass, config.chip),
                })}
                @click=${chip}
              >
                +${formatMinutes(hass, config.chip)}
              </button>
            `}
      </div>
    </ha-card>
  `;
}

/**
 * What the layouts share. The body is the layer that is pressed: it covers the whole card,
 * border included, under the content, and the content lets presses through to it, as in Home
 * Assistant's tile card. The radius is the layout's own, `--timerify-radius` on `ha-card`.
 */
export const commonStyles = css`
  .body {
    position: absolute;
    inset: 0;
    /* Inset reaches the padding box; the card's border is part of what a press hits. */
    margin: calc(-1 * var(--ha-card-border-width, 1px));
    border-radius: var(--timerify-radius);
    cursor: pointer;
    /* A long touch must bring up neither a selection nor the browser's callout. */
    user-select: none;
    -webkit-user-select: none;
    -webkit-touch-callout: none;
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
`;

export const pillStyles = css`
  ha-card.pill {
    --timerify-radius: 28px;
    height: 56px;
    border-radius: var(--timerify-radius);
  }
  .fill-clip {
    position: absolute;
    inset: 0;
    overflow: hidden;
    border-radius: var(--timerify-radius);
  }
  .fill {
    display: block;
    height: 100%;
    background: var(--state-active-color, var(--primary-color));
    opacity: 0.3;
  }
  .pill .content {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0 12px 0 8px;
  }
  .pill .icon {
    display: flex;
    flex: none;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
  }
  .pill .text {
    display: flex;
    flex: 1 1 auto;
    flex-direction: column;
    min-width: 0;
  }
  .pill .status {
    display: flex;
    gap: 6px;
    overflow: hidden;
    color: var(--secondary-text-color);
    font-size: var(--ha-font-size-s, 12px);
    white-space: nowrap;
  }
  .chip {
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
  .chip:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
`;
