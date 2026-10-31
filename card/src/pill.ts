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

function renderStatus(view: TimerView, config: CardConfig, hass: HomeAssistant, now: number) {
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
 * The card as a pill. Its body is a button, pressed through `binding`, that opens the pop-up;
 * `chip` is called when the chip is pressed, which the body does not take for a press of its own.
 */
export function renderPill(
  view: TimerView,
  config: CardConfig,
  hass: HomeAssistant,
  binding: PressBinding,
  chip: () => void,
): TemplateResult {
  const filled = Math.round(view.progress * 1000) / 10;
  return html`
    <ha-card class="pill">
      <div
        class="body ${view.state}"
        role="button"
        tabindex="0"
        aria-haspopup="dialog"
        @click=${binding.click}
        @keydown=${binding.keydown}
        @keyup=${binding.keyup}
      >
        <span class="fill-clip" aria-hidden="true">
          <span class="fill" style=${styleMap({ width: `${filled}%` })}></span>
        </span>
        <span class="icon">${renderIcon(view)}</span>
        <span class="text">
          <span class="name">${view.name}</span>
          <span class="status">${renderStatus(view, config, hass, Date.now())}</span>
        </span>
        ${config.chip === undefined
          ? nothing
          : html`
              <button
                class="chip"
                type="button"
                aria-label=${t(hass, "card_add_minutes", { minutes: config.chip })}
                @click=${chip}
              >
                +${formatMinutes(hass, config.chip)}
              </button>
            `}
      </div>
    </ha-card>
  `;
}

export const pillStyles = css`
  ha-card.pill {
    --timerify-radius: 28px;
    height: 56px;
    border-radius: var(--timerify-radius);
  }
  .body {
    position: relative;
    display: flex;
    align-items: center;
    gap: 12px;
    box-sizing: border-box;
    height: 100%;
    padding: 0 12px 0 8px;
    border-radius: var(--timerify-radius);
    cursor: pointer;
  }
  .body:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  .fill-clip {
    position: absolute;
    inset: 0;
    overflow: hidden;
    border-radius: var(--timerify-radius);
    pointer-events: none;
  }
  .fill {
    display: block;
    height: 100%;
    background: var(--state-active-color, var(--primary-color));
    opacity: 0.3;
  }
  .icon {
    position: relative;
    display: flex;
    flex: none;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    color: var(--state-icon-color, var(--secondary-text-color));
  }
  .counting .icon,
  .open .icon {
    color: var(--state-active-color, var(--primary-color));
  }
  .unavailable .icon {
    color: var(--state-unavailable-color, var(--disabled-text-color));
  }
  .text {
    position: relative;
    display: flex;
    flex: 1 1 auto;
    flex-direction: column;
    min-width: 0;
  }
  .name {
    overflow: hidden;
    color: var(--primary-text-color);
    font-size: var(--ha-font-size-m, 14px);
    font-weight: var(--ha-font-weight-medium, 500);
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .status {
    display: flex;
    gap: 6px;
    overflow: hidden;
    color: var(--secondary-text-color);
    font-size: var(--ha-font-size-s, 12px);
    white-space: nowrap;
  }
  .remaining {
    font-variant-numeric: tabular-nums;
  }
  .chip {
    position: relative;
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
  }
  .chip:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
`;
