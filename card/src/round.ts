// The round layout: a ring that shows the share of the countdown that is left, the time left
// in its centre while it counts (the icon of the timer's target otherwise, under a limit too),
// and the name below.
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
import { mush } from "./mushroom";
import type { PressBinding } from "./press";
import type { TimerView } from "./timer";

/** The ring is drawn in a square of this many units, scaled to the size it has on the page. */
const SIZE = 80;
const STROKE = 6;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
/** The time is this many container units (1cqw is 1 % of the dial's width) high, at most. */
const TIME_CQW = 20;
/** The smallest the time is drawn, in px; a dial too small for it shows the icon instead. */
const MIN_TIME_PX = 9;
/** The dial's width in px from which it shows the time: `TIME_CQW` of it is `MIN_TIME_PX`. */
const TIME_FROM = (MIN_TIME_PX * 100) / TIME_CQW;

/**
 * The time left while the timer counts; the icon of its target otherwise, under a limit too,
 * which has no time left to show. While it counts the dial holds both and the styles choose:
 * the time, except in a dial too small for the time to be read, where the icon is shown instead.
 */
function renderCentre(view: TimerView): TemplateResult {
  const icon = html`<span class="icon">${renderIcon(view)}</span>`;
  if (view.state !== "counting") {
    return icon;
  }
  // The label of the body already says the time, with the end.
  const left = formatRemaining(view.remaining);
  return html`<span class="time" aria-hidden="true">${left}</span>${icon}`;
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
  /*
   * While it counts the dial holds the time and the icon, and shows the time. The icon takes its
   * place only in a dial too small for the time, see the end of these styles; a browser that
   * does not know container queries never shows it. The selector is more specific than the
   * Mushroom rule that shows the icon (mushroomStyles, in layout.ts).
   */
  ha-card.round.counting .icon {
    display: none;
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
  /*
   * The Mushroom style (see mushroomStyles in layout.ts): the dial, the name and the button
   * with the spacing of Mushroom around them. The tile is as high as they make it, and never
   * lower than the rows of the grid it sits in.
   */
  :host([data-mushroom]) ha-card.round {
    height: max(120px, calc(2 * ${mush.spacing} + ${SIZE}px + ${mush.primaryLineHeight}));
  }
  :host([data-mushroom]) ha-card.round.with-turn-off {
    height: max(
      184px,
      calc(
        2 * ${mush.spacing} + ${SIZE}px + ${mush.primaryLineHeight} + 4px + ${mush.controlHeight}
      )
    );
  }
  :host([data-mushroom]) .round .content {
    gap: 0;
    padding: ${mush.spacing};
  }
  :host([data-mushroom]) .progress {
    stroke: rgb(${mush.activeRgb});
  }
  :host([data-mushroom]) .time {
    color: ${mush.primaryColor};
    font-size: ${mush.primaryFontSize};
    font-weight: ${mush.primaryFontWeight};
    letter-spacing: ${mush.primaryLetterSpacing};
  }
  :host([data-mushroom]) .turn-off-slot {
    height: ${mush.controlHeight};
  }
  /*
   * The dial shrinks with its tile: it is 80 px where the tile has room, and as wide as the room
   * where it has less, and the time and the icon follow it in container units. In a dial too
   * small for the time to be read (TIME_FROM, where the time is MIN_TIME_PX high) the ring and
   * the icon are shown and the time is not. The dial is the container and not .content, so that
   * a card without the Turn off button is laid out as before (see turnOffAsIcon: only a card
   * that has the button makes .content a container). All of it is one block, so that a browser
   * that does not know container units keeps the dial at 80 px with its time: a width capped
   * without an aspect ratio would not be a square, and a custom property with cqw in it is
   * invalid only where it is used.
   */
  @supports (width: 1cqw) {
    .dial {
      max-width: 100%;
      height: auto;
      aspect-ratio: 1;
      container-type: inline-size;
    }
    .round .time {
      font-size: min(var(--ha-font-size-l, 16px), ${TIME_CQW}cqw);
    }
    :host(:not([data-mushroom])) .round .icon {
      /* No line of text around a small symbol: the box of the icon is the symbol. */
      line-height: 0;
      --mdc-icon-size: min(32px, 40cqw);
    }
    :host([data-mushroom]) .round .time {
      font-size: min(${mush.primaryFontSize}, ${TIME_CQW}cqw);
    }
    /* 45 % of the full dial, 80 px, is 36 px, the size of Mushroom's icon shape. */
    :host([data-mushroom]) .round .icon {
      width: min(${mush.iconSize}, 45cqw);
      height: min(${mush.iconSize}, 45cqw);
      font-size: min(${mush.iconSize}, 45cqw);
    }
    @container (width < ${TIME_FROM}px) {
      ha-card.round.counting .time {
        display: none;
      }
      ha-card.round.counting .icon {
        display: flex;
      }
    }
  }
`;
