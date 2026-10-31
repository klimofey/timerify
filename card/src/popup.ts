// The pop-up of the card: a native <dialog> in the card's own shadow DOM, opened modally. The
// platform traps the focus, closes it on Escape and makes the page behind inert, so the card
// needs nothing of the frontend's own dialogs. In it the user runs the timer for a time, adds
// or takes time off, stops it, switches the intervals of its schedule, cancels its pending
// commands and, if an administrator, goes to its settings. Everything is a call to one of
// Timerify's services or entities, and everything shown is read from their states.
import { LitElement, css, html, nothing, type PropertyValues, type TemplateResult } from "lit";
import {
  STEP_MINUTES,
  addMinutes,
  cancelCommand,
  setIntervalEnabled,
  setMinutes,
} from "./actions";
import type { CardConfig } from "./config";
import { formatClock, formatMinutes, formatRemaining, settingText } from "./format";
import type { HassEntity, HomeAssistant, IntervalInfo, TimerInfo } from "./hass";
import { t } from "./strings";
import { mattersToRender, watchedEntities, type TimerView } from "./timer";

/** A command that waits for its time, as the "Next command" sensor lists it. */
interface PendingCommand {
  id: string;
  at: Date;
  action: "on" | "off";
  /** How long a command to turn on runs; none when it turns on with no countdown. */
  minutes: number | null;
  settings: [key: string, value: unknown][];
}

/**
 * The commands the "Next command" sensor lists, in its order. A row the card cannot read
 * (no id, no time, an action it does not know) is left out, so that the others still show.
 */
function pendingCommands(sensor: HassEntity | undefined): PendingCommand[] {
  const rows: unknown = sensor?.attributes["commands"];
  if (!Array.isArray(rows)) {
    return [];
  }
  return rows.flatMap((row: unknown): PendingCommand[] => {
    if (typeof row !== "object" || row === null) {
      return [];
    }
    const { id, at, action, minutes, settings } = row as Record<string, unknown>;
    const time = typeof at === "string" ? new Date(at) : undefined;
    if (
      typeof id !== "string" ||
      time === undefined ||
      Number.isNaN(time.getTime()) ||
      (action !== "on" && action !== "off")
    ) {
      return [];
    }
    return [
      {
        id,
        at: time,
        action,
        minutes: typeof minutes === "number" && minutes > 0 ? minutes : null,
        settings: typeof settings === "object" && settings !== null ? Object.entries(settings) : [],
      },
    ];
  });
}

/** Where Home Assistant shows the timer's settings: its page among the integration's. */
const settingsPath = (entryId: string): string =>
  `/config/integrations/integration/timerify#config_entry=${encodeURIComponent(entryId)}`;

export class TimerifyCardPopup extends LitElement {
  static override properties = {
    hass: { attribute: false },
    config: { attribute: false },
    info: { attribute: false },
    view: { attribute: false },
    opened: { state: true },
  };

  static override styles = css`
    dialog {
      box-sizing: border-box;
      width: 100%;
      max-width: 420px;
      padding: 0;
      border: none;
      border-radius: var(--ha-border-radius-lg, 16px);
      background: var(--card-background-color);
      color: var(--primary-text-color);
    }
    dialog::backdrop {
      background: rgba(0, 0, 0, 0.4);
    }
    @media (max-width: 450px) {
      dialog {
        max-width: 100%;
      }
    }
    .wrapper {
      display: flex;
      flex-direction: column;
      gap: 16px;
      padding: 16px;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    h2 {
      margin: 0;
      font-size: var(--ha-font-size-xl, 1.25rem);
      font-weight: 500;
    }
    h3 {
      margin: 0 0 4px;
      color: var(--secondary-text-color);
      font-size: var(--ha-font-size-m, 14px);
      font-weight: var(--ha-font-weight-medium, 500);
    }
    button,
    a {
      font: inherit;
      cursor: pointer;
    }
    button:focus-visible,
    a:focus-visible {
      outline: 2px solid var(--primary-color);
      outline-offset: 2px;
    }
    button.close {
      padding: 8px 12px;
      border: none;
      border-radius: var(--ha-border-radius-md, 8px);
      background: none;
      color: var(--primary-color);
    }
    .countdown {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 4px 12px;
      margin: 0;
    }
    .remaining {
      font-size: var(--ha-font-size-3xl, 2rem);
      font-variant-numeric: tabular-nums;
      font-weight: var(--ha-font-weight-medium, 500);
    }
    .until {
      color: var(--secondary-text-color);
    }
    .presets,
    .adjust {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    button.action {
      min-width: 40px;
      min-height: 40px;
      padding: 0 16px;
      border: none;
      border-radius: 20px;
      background: var(--secondary-background-color);
      color: var(--primary-text-color);
    }
    button.action:disabled {
      color: var(--disabled-text-color);
      cursor: default;
    }
    button.stop:not(:disabled) {
      color: var(--error-color);
    }
    ul {
      margin: 0;
      padding: 0;
      list-style: none;
    }
    li {
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 48px;
    }
    button.interval {
      display: flex;
      flex: 1 1 auto;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-height: 48px;
      padding: 0;
      border: none;
      background: none;
      color: var(--primary-text-color);
      text-align: start;
    }
    button.interval:disabled {
      color: var(--disabled-text-color);
      cursor: default;
    }
    .label {
      display: flex;
      flex-direction: column;
    }
    .state {
      color: var(--secondary-text-color);
      font-size: var(--ha-font-size-s, 12px);
    }
    .track {
      position: relative;
      flex: none;
      width: 40px;
      height: 22px;
      border-radius: 11px;
      background: var(--disabled-text-color);
      transition: background-color var(--ha-animation-duration-fast, 150ms);
    }
    .knob {
      position: absolute;
      top: 3px;
      inset-inline-start: 3px;
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: var(--card-background-color);
      transition: transform var(--ha-animation-duration-fast, 150ms);
    }
    [aria-checked="true"] .track {
      background: var(--primary-color);
    }
    [aria-checked="true"] .knob {
      transform: translateX(18px);
    }
    [aria-checked="true"]:dir(rtl) .knob {
      transform: translateX(-18px);
    }
    button.interval:disabled .track {
      opacity: 0.5;
    }
    .command {
      display: flex;
      flex: 1 1 auto;
      flex-direction: column;
      min-width: 0;
    }
    .settings {
      color: var(--secondary-text-color);
      font-size: var(--ha-font-size-s, 12px);
    }
    button.cancel {
      flex: none;
      width: 40px;
      height: 40px;
      border: none;
      border-radius: 50%;
      background: none;
      color: var(--secondary-text-color);
      font-size: var(--ha-font-size-xl, 1.25rem);
      line-height: 1;
    }
    button.cancel:disabled {
      color: var(--disabled-text-color);
      cursor: default;
    }
    footer {
      display: flex;
      justify-content: flex-end;
    }
    a {
      color: var(--primary-color);
    }
  `;

  declare hass: HomeAssistant;
  declare config: CardConfig;
  /** What Timerify told of the timer. */
  declare info: TimerInfo;
  /** What the card shows of the timer; the card makes a new one at every render, so it ticks. */
  declare view: TimerView;
  /** Whether the dialog is open; only then does the pop-up have anything to render. */
  declare opened: boolean;

  constructor() {
    super();
    this.opened = false;
  }

  /** Shows the pop-up over the page. */
  open(): void {
    this.opened = true;
  }

  /** Closes the pop-up; the card gets the focus back. */
  close(): void {
    this.#dialog?.close();
    this.#settle();
  }

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    // A dialog that is taken off the page keeps its `open` attribute but is not modal any more.
    this.close();
  }

  get #dialog(): HTMLDialogElement | null {
    return this.renderRoot.querySelector("dialog");
  }

  /**
   * The browser announces a closed dialog some time after it closed. If the pop-up has been
   * opened again since, the announcement is out of date and must not close it.
   */
  readonly #onClose = (): void => {
    if (!this.#dialog?.open) {
      this.#settle();
    }
  };

  /**
   * Whether the press under way has so far been on the backdrop alone. The backdrop is the
   * dialog's own box as far as events go, so a click on it has the dialog as its target. So
   * has a click that follows a press from the content to the backdrop, which is how a text
   * selection ends: the browser sends the click to the nearest element that holds both ends.
   * Only a press that begins and ends on the backdrop is a click on it.
   */
  #pressOnBackdrop = false;

  readonly #onPointerDown = (event: PointerEvent): void => {
    this.#pressOnBackdrop = event.target === event.currentTarget;
  };

  readonly #onPointerUp = (event: PointerEvent): void => {
    this.#pressOnBackdrop &&= event.target === event.currentTarget;
  };

  readonly #onPointerCancel = (): void => {
    this.#pressOnBackdrop = false;
  };

  readonly #onClick = (event: MouseEvent): void => {
    const onBackdrop = this.#pressOnBackdrop && event.target === event.currentTarget;
    this.#pressOnBackdrop = false;
    if (onBackdrop) {
      this.close();
    }
  };

  /** The dialog is closed, however that came about: tell the card, once. */
  #settle(): void {
    if (this.opened) {
      this.opened = false;
      this.dispatchEvent(new CustomEvent("closed"));
    }
  }

  protected override shouldUpdate(changed: PropertyValues): boolean {
    if (!this.hasUpdated || changed.has("opened")) {
      return true;
    }
    const watched = watchedEntities(this.config.entity, this.info);
    return this.opened && mattersToRender(changed, this.hass, watched);
  }

  protected override updated(changed: PropertyValues): void {
    const dialog = this.#dialog;
    if (changed.has("opened") && this.opened && dialog && !dialog.open) {
      dialog.showModal();
    }
  }

  protected override render() {
    return html`
      <dialog
        aria-labelledby="title"
        @cancel=${() => this.close()}
        @close=${this.#onClose}
        @pointerdown=${this.#onPointerDown}
        @pointerup=${this.#onPointerUp}
        @pointercancel=${this.#onPointerCancel}
        @click=${this.#onClick}
      >
        ${this.opened ? this.#content() : nothing}
      </dialog>
    `;
  }

  #content(): TemplateResult {
    const { hass, view } = this;
    const now = Date.now();
    return html`
      <div class="wrapper">
        <header>
          <h2 id="title">${view.name}</h2>
          <button class="close" @click=${() => this.close()}>${t(hass, "card_close")}</button>
        </header>
        ${this.#countdown(now)} ${this.#controls()} ${this.#schedule()} ${this.#commands(now)}
        ${this.#settings()}
      </div>
    `;
  }

  /** The time left and when it ends, while there is a countdown. */
  #countdown(now: number) {
    const { hass, view } = this;
    if (view.state !== "counting" || view.endsAt === undefined) {
      return nothing;
    }
    const time = formatClock(hass, view.endsAt, now);
    return html`
      <p class="countdown">
        <span class="remaining">${formatRemaining(view.remaining)}</span>
        <span class="until">${t(hass, "card_until", { time })}</span>
      </p>
    `;
  }

  /** Run for a preset, take five minutes off or add them, or stop. */
  #controls() {
    const { hass, config, view } = this;
    const step = formatMinutes(hass, STEP_MINUTES);
    const counting = view.state === "counting";
    const running = counting || view.state === "open";
    // A timer that is unavailable has nothing to act on: Home Assistant would leave it out of
    // the call without a word, and a press would seem to do nothing.
    const unavailable = view.state === "unavailable";
    return html`
      <div class="presets">
        ${config.presets.map(
          (minutes) => html`
            <button
              class="action preset"
              ?disabled=${unavailable}
              @click=${() => void setMinutes(hass, config.entity, minutes)}
            >
              ${formatMinutes(hass, minutes)}
            </button>
          `,
        )}
      </div>
      <div class="adjust">
        <button
          class="action step"
          aria-label=${t(hass, "card_subtract_time", { duration: step })}
          ?disabled=${!counting}
          @click=${() => void addMinutes(hass, config.entity, -STEP_MINUTES)}
        >
          −${step}
        </button>
        <button
          class="action step"
          aria-label=${t(hass, "card_add_time", { duration: step })}
          ?disabled=${unavailable}
          @click=${() => void addMinutes(hass, config.entity, STEP_MINUTES)}
        >
          +${step}
        </button>
        <button
          class="action stop"
          ?disabled=${!running}
          @click=${() => void setMinutes(hass, config.entity, 0)}
        >
          ${t(hass, "card_stop")}
        </button>
      </div>
    `;
  }

  /** The intervals of the schedule, each with the switch that enables it. */
  #schedule() {
    const { intervals } = this.info;
    if (intervals.length === 0) {
      return nothing;
    }
    return html`
      <section class="schedule">
        <h3>${t(this.hass, "card_schedule")}</h3>
        <ul>
          ${intervals.map((interval) => html`<li>${this.#interval(interval)}</li>`)}
        </ul>
      </section>
    `;
  }

  /**
   * One interval. Timerify lists the switch of an interval that was disabled in the registry,
   * which has no state: like one that is unavailable, it is shown off, and cannot be pressed.
   */
  #interval({ entity_id: switchId, title }: IntervalInfo) {
    const { hass } = this;
    const state = hass.states[switchId];
    const available = state !== undefined && state.state !== "unavailable";
    const on = available && state.state === "on";
    const gone = state ?? { entity_id: switchId, state: "unavailable", attributes: {} };
    return html`
      <button
        class="interval"
        role="switch"
        aria-checked=${on ? "true" : "false"}
        ?disabled=${!available}
        @click=${() => void setIntervalEnabled(hass, switchId, !on)}
      >
        <span class="label">
          <span class="title">${title}</span>
          ${available
            ? nothing
            : html`<span class="state">${hass.formatEntityState(gone, "unavailable")}</span>`}
        </span>
        <span class="track" aria-hidden="true"><span class="knob"></span></span>
      </button>
    `;
  }

  /** The commands that wait for their time, each with a button that cancels it. */
  #commands(now: number) {
    const { hass, config, info, view } = this;
    const commands = pendingCommands(hass.states[info.next_command]);
    if (commands.length === 0) {
      return nothing;
    }
    const unavailable = view.state === "unavailable";
    return html`
      <section class="commands">
        <h3>${t(hass, "card_commands")}</h3>
        <ul>
          ${commands.map((command, index) => {
            const settings = command.settings.map(([key, value]) =>
              settingText(hass, view.target, key, value),
            );
            return html`
              <li>
                <div class="command" id="command-${index}">
                  <span class="what">${this.#commandText(command, now)}</span>
                  ${settings.length === 0
                    ? nothing
                    : html`<span class="settings">${settings.join(", ")}</span>`}
                </div>
                <button
                  class="cancel"
                  aria-label=${t(hass, "card_cancel_command")}
                  aria-describedby="command-${index}"
                  ?disabled=${unavailable}
                  @click=${() => void cancelCommand(hass, config.entity, command.id)}
                >
                  <span aria-hidden="true">×</span>
                </button>
              </li>
            `;
          })}
        </ul>
      </section>
    `;
  }

  /** What a command does and when: "On at 09:15 for 1 hr", "Off at Tue 07:00". */
  #commandText(command: PendingCommand, now: number): string {
    const { hass } = this;
    const time = formatClock(hass, command.at, now);
    if (command.action === "off") {
      return t(hass, "card_command_off", { time });
    }
    return command.minutes === null
      ? t(hass, "card_command_on", { time })
      : t(hass, "card_command_on_for", { time, duration: formatMinutes(hass, command.minutes) });
  }

  /** The link to the timer's page among the integration's, for an administrator only. */
  #settings() {
    if (!this.hass.user?.is_admin) {
      return nothing;
    }
    return html`
      <footer>
        <a href=${settingsPath(this.info.entry_id)} @click=${this.#onSettingsClick}>
          ${t(this.hass, "card_settings")}
        </a>
      </footer>
    `;
  }

  /**
   * The link is a plain one to a page of the same origin, and Home Assistant's frontend follows
   * every such link itself, in the app and with the history entry its own back arrows need.
   * So the click is left alone, and the pop-up only gets out of the way. A click that asks for
   * a new tab or window (Ctrl, Cmd or Shift, the keys Home Assistant's own link check leaves to
   * the browser) is the browser's, and the pop-up stays.
   */
  readonly #onSettingsClick = (event: MouseEvent): void => {
    if (!event.ctrlKey && !event.metaKey && !event.shiftKey) {
      this.close();
    }
  };
}
