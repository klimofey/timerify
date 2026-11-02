// The round layout: a ring that shows the share of the countdown that is left, the time left
// in its centre while it counts (the icon of the timer's target otherwise), and the name below.
// A press anywhere on the card reaches its body; what a press does is set in the config, and a
// long press starts or stops the timer unless it is set to something else, see `press.ts`. The
// one control beside the body is the optional Turn off button, under the name.
import { css, html, nothing, type TemplateResult } from "lit";
import { ifDefined } from "lit/directives/if-defined.js";
import type { CardConfig } from "./config";
import { formatRemaining } from "./format";
import type { HomeAssistant } from "./hass";
import {
  WORDS_FROM,
  isPressable,
  popupAnnounced,
  renderIcon,
  renderStatus,
  renderTurnOff,
  turnOffAsIcon,
} from "./layout";
import type { PressBinding } from "./press";
import type { TimerView } from "./timer";

/** The ring is drawn in a square of this many units, scaled to the size it has on the page. */
const SIZE = 80;
const STROKE = 6;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** The time left while the timer counts; the icon of its target otherwise. */
function renderCentre(view: TimerView): TemplateResult {
  if (view.state !== "counting") {
    return html`<span class="icon">${renderIcon(view)}</span>`;
  }
  // The label of the body already says it, with the end.
  const left = formatRemaining(view.remaining);
  return html`<span class="time" aria-hidden="true">${left}</span>`;
}

/**
 * The card as a round tile, drawn at the instant `now` that `view` was made for. Its body is
 * an empty layer under the content, as the pill's, pressed through `binding`; the ring and
 * the time are for the eye alone. The state that the ring and the icon show is also said in
 * words that only assistive technology reads, so that the button is named by the name and
 * the state, as the pill's is. The Turn off button is a button of its own below the name,
 * which `turnOff` answers and the body never hears of. Where it goes is kept free whenever
 * the config asks for it, so that the dial does not move when the target goes on or off.
 */
export function renderRound(
  view: TimerView,
  config: CardConfig,
  hass: HomeAssistant,
  binding: PressBinding,
  turnOff: () => void,
  now: number,
): TemplateResult {
  const middle = SIZE / 2;
  const pressable = isPressable(config);
  return html`
    <ha-card class="round ${view.state} ${config.show_turn_off ? "with-turn-off" : ""}">
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
      ></div>
      <div class="content">
        <div class="dial">
          <svg class="ring" viewBox="0 0 ${SIZE} ${SIZE}" aria-hidden="true">
            <circle class="track" cx=${middle} cy=${middle} r=${RADIUS}></circle>
            <circle
              class="progress"
              cx=${middle}
              cy=${middle}
              r=${RADIUS}
              transform="rotate(-90 ${middle} ${middle})"
              stroke-dasharray=${CIRCUMFERENCE}
              stroke-dashoffset=${(1 - view.progress) * CIRCUMFERENCE}
            ></circle>
          </svg>
          <span class="centre">
            ${renderCentre(view)}
          </span>
        </div>
        <span class="text" id="label">
          <span class="name">${view.name}</span>
          <span class="status">${renderStatus(view, config, hass, now)}</span>
        </span>
        ${config.show_turn_off
          ? html`<div class="turn-off-slot">${renderTurnOff(view, config, hass, turnOff)}</div>`
          : nothing}
      </div>
    </ha-card>
  `;
}

export const roundStyles = css`
  ha-card.round {
    --timerify-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
    height: 120px;
  }
  /* A row taller than the tile, for the Turn off button: three rows of the sections grid. */
  ha-card.round.with-turn-off {
    height: 184px;
  }
  .round .content {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 8px;
  }
  .dial {
    position: relative;
    flex: none;
    width: ${SIZE}px;
    height: ${SIZE}px;
  }
  .ring {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }
  .track,
  .progress {
    fill: none;
    stroke-width: ${STROKE};
  }
  .track {
    stroke: var(--divider-color, #e0e0e0);
  }
  .progress {
    stroke: var(--state-active-color, var(--primary-color));
  }
  .centre {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .time {
    color: var(--primary-text-color);
    font-size: var(--ha-font-size-l, 16px);
    font-weight: var(--ha-font-weight-medium, 500);
    font-variant-numeric: tabular-nums;
  }
  .round .icon {
    display: flex;
    --mdc-icon-size: 32px;
  }
  .round .text {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    max-width: 100%;
    min-width: 0;
  }
  .round .name {
    max-width: 100%;
  }
  .turn-off-slot {
    display: flex;
    flex: none;
    align-items: center;
    justify-content: center;
    height: 40px;
    margin-top: 4px;
  }
  @container (width < ${WORDS_FROM.round}px) {
    ${turnOffAsIcon(css`.round`)}
  }
  /* For assistive technology only: what the ring and the icon say. */
  .round .status {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }
  /*
   * While letting go would act, the ring pulses. A timer that is unavailable has nothing to
   * act on, so its ring stays still.
   */
  :host([data-held]) .round:not(.unavailable) .ring {
    animation: pulse 0.8s ease-in-out infinite alternate;
  }
  @media (prefers-reduced-motion: reduce) {
    :host([data-held]) .round:not(.unavailable) .ring {
      animation: none;
      transform: scale(1.08);
    }
  }
`;
