// The pill: a card one row high, filled from the left by the share of the countdown that is
// left, with the icon, the name, the time left and when it ends, and an optional chip that
// adds a few minutes.
import { css, html, nothing, type TemplateResult } from "lit";
import { ifDefined } from "lit/directives/if-defined.js";
import { styleMap } from "lit/directives/style-map.js";
import type { CardConfig } from "./config";
import { formatMinutes } from "./format";
import type { HomeAssistant } from "./hass";
import { isPressable, popupAnnounced, renderIcon, renderStatus } from "./layout";
import type { PressBinding } from "./press";
import { t } from "./strings";
import type { TimerView } from "./timer";

/**
 * The card as a pill, drawn at the instant `now` that `view` was made for. Its body is an
 * empty layer under the content, as in Home Assistant's tile card: a button, pressed through
 * `binding`, that opens the pop-up, named by the name and the state it covers. The content
 * above lets presses through to it, except the chip, a button of its own beside the body:
 * `chip` is called when it is pressed, and the body never hears of it. A timer that is
 * unavailable has nothing to add time to, and the chip is off.
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
  const pressable = isPressable(config);
  return html`
    <ha-card class="pill ${view.state}">
      <div
        class="body"
        role=${ifDefined(pressable ? "button" : undefined)}
        tabindex=${ifDefined(pressable ? "0" : undefined)}
        aria-haspopup=${ifDefined(popupAnnounced(config))}
        aria-labelledby=${ifDefined(pressable ? "label" : undefined)}
        @click=${binding.click}
        @keydown=${binding.keydown}
        @keyup=${binding.keyup}
        @pointerdown=${binding.pointerdown}
        @pointerup=${binding.pointerup}
        @pointercancel=${binding.pointercancel}
        @pointerleave=${binding.pointerleave}
        @contextmenu=${binding.contextmenu}
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
                ?disabled=${view.state === "unavailable"}
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
  .chip:disabled {
    color: var(--disabled-text-color);
    cursor: default;
  }
  .chip:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  /*
   * The pill has a long press only when the config gives it one. While letting go would act,
   * the icon pulses, as the round tile's ring does; a timer that is unavailable stays still.
   */
  :host([data-held]) .pill:not(.unavailable) .icon {
    animation: pulse 0.8s ease-in-out infinite alternate;
  }
  @media (prefers-reduced-motion: reduce) {
    :host([data-held]) .pill:not(.unavailable) .icon {
      animation: none;
      transform: scale(1.08);
    }
  }
`;
