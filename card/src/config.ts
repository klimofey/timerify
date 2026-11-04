// What the user writes into the card's YAML or the visual editor, checked.
import { lastLoaded, t, type StringKey } from "./strings";

export const DEFAULT_PRESETS = [15, 30, 45, 60, 120] as const;

/** The most minutes a preset or the chip can stand for: a day. */
export const MAX_MINUTES = 1440;

/** What a tap, a double tap or a long press can be set to. */
export const PRESS_CHOICES = ["popup", "run", "stop", "run_or_stop", "action", "none"] as const;
export type PressChoice = (typeof PRESS_CHOICES)[number];

/** The presses of the card, which are also the names of the config keys that set them. */
export const PRESSES = ["tap", "double_tap", "hold"] as const;
export type Press = (typeof PRESSES)[number];

/** A Home Assistant action, such as the visual editor writes for `ui_action`: kept as given. */
export type ActionConfig = Record<string, unknown>;

/** The keys that hold the Home Assistant action of each press. */
export const ACTION_KEYS = ["tap_action", "double_tap_action", "hold_action"] as const;
export type ActionKey = (typeof ACTION_KEYS)[number];

/** The key that holds the Home Assistant action of each press. */
const ACTION_OF: { readonly [P in Press]: `${P}_action` } = {
  tap: "tap_action",
  double_tap: "double_tap_action",
  hold: "hold_action",
};

export interface CardConfig {
  /** The "Run for" number of the timer. */
  entity: string;
  layout: "pill" | "round";
  name?: string;
  icon?: string;
  /** The durations the pop-up offers, in minutes: the defaults when the config gives none. */
  presets: number[];
  /** The minutes the pill's chip adds; the round layout has no chip. */
  chip?: number;
  /** Whether the card shows a Turn off button while the device is on; the pop-up has its Stop. */
  show_turn_off: boolean;
  /** Whether the card takes Mushroom's look, when Mushroom is on the page: see `mushroom.ts`. */
  mushroom: boolean;
  /**
   * What a tap does: it opens the pop-up unless the config sets it to something else, with a
   * choice or with an action alone.
   */
  tap: PressChoice;
  double_tap: PressChoice;
  /**
   * What a long press does: on the round layout it starts or stops, on the pill nothing, unless
   * the config sets it to something else.
   */
  hold: PressChoice;
  /**
   * The Home Assistant action of each press: used when the press is set to `action`, or is not
   * set.
   */
  tap_action?: ActionConfig;
  double_tap_action?: ActionConfig;
  hold_action?: ActionConfig;
}

/** A config the card cannot work with; the message is for the user, in the loaded language. */
export class ConfigError extends Error {
  constructor(readonly key: StringKey) {
    super(t(lastLoaded(), key));
  }
}

/**
 * The minutes a preset or the chip stands for: a whole number from 1 to 1440, given as a
 * number or as digits.
 */
function minutesOf(given: unknown): number | undefined {
  const minutes =
    typeof given === "number"
      ? given
      : typeof given === "string" && /^\d+$/.test(given)
        ? Number(given)
        : undefined;
  const valid =
    minutes !== undefined && Number.isInteger(minutes) && minutes >= 1 && minutes <= MAX_MINUTES;
  return valid ? minutes : undefined;
}

function parsePresets(raw: unknown): number[] {
  // No list, and a list with nothing left in it (what the visual editor writes when the last
  // preset is taken away), both leave it to the defaults.
  if (raw === undefined || (Array.isArray(raw) && raw.length === 0)) {
    return [...DEFAULT_PRESETS];
  }
  if (!Array.isArray(raw)) {
    throw new ConfigError("card_error_presets");
  }
  const presets = new Set<number>();
  for (const preset of raw) {
    const minutes = minutesOf(preset);
    if (minutes === undefined) {
      throw new ConfigError("card_error_presets");
    }
    presets.add(minutes);
  }
  return [...presets];
}

function parseChip(raw: unknown): number | undefined {
  if (raw === undefined) {
    return undefined;
  }
  const minutes = minutesOf(raw);
  if (minutes === undefined) {
    throw new ConfigError("card_error_chip");
  }
  return minutes;
}

const recordOf = (raw: unknown): Record<string, unknown> =>
  (typeof raw === "object" && raw !== null ? raw : {}) as Record<string, unknown>;

const isPressChoice = (given: unknown): given is PressChoice =>
  PRESS_CHOICES.some((choice) => choice === given);

/**
 * The name of the Home Assistant action to do (`toggle`, `more-info`, `none`), or `undefined`
 * when the action names nothing to do: no action, one with no `action` key, or a name that is
 * not text. Such an action counts as not given.
 */
function namedAction(action: ActionConfig | undefined): string | undefined {
  const name = action?.action;
  return typeof name === "string" && name !== "" ? name : undefined;
}

/**
 * What a press does, from the three things the config can say of it: its choice (`raw`), its
 * Home Assistant `action`, and the default (`fallback`).
 *
 * A choice that is given wins, as the user chose it. Without one, an action that is given is
 * done, as every card of Home Assistant does it. The action `none` ("Nothing" in Home
 * Assistant's selector, which reads it as no press at all) makes the press do nothing, with no
 * choice and with the choice `action`: the second would hand Home Assistant an action that does
 * nothing and, for a double tap, make every tap wait for it. With neither a choice nor an
 * action, the press does its default.
 */
function parsePress(
  raw: unknown,
  action: ActionConfig | undefined,
  fallback: PressChoice,
): PressChoice {
  const named = namedAction(action);
  if (raw === undefined) {
    if (named === undefined) {
      return fallback;
    }
    return named === "none" ? "none" : "action";
  }
  if (!isPressChoice(raw)) {
    throw new ConfigError("card_error_press");
  }
  return raw === "action" && named === "none" ? "none" : raw;
}

/** An option that is on only when the config says `true`; `error` is what any other kind says. */
function parseSwitch(raw: unknown, error: StringKey): boolean {
  if (raw === undefined) {
    return false;
  }
  if (typeof raw !== "boolean") {
    throw new ConfigError(error);
  }
  return raw;
}

/** A Home Assistant action is a set of settings; anything else is not one. */
const isAction = (given: unknown): given is ActionConfig =>
  typeof given === "object" && given !== null && !Array.isArray(given);

/** The Home Assistant actions the config gives, as they are given. */
function parseActions(given: Record<string, unknown>): Partial<Record<ActionKey, ActionConfig>> {
  const actions: Partial<Record<ActionKey, ActionConfig>> = {};
  for (const key of ACTION_KEYS) {
    const action = given[key];
    if (action === undefined) {
      continue;
    }
    if (!isAction(action)) {
      throw new ConfigError("card_error_action");
    }
    actions[key] = action;
  }
  return actions;
}

/** A value the visual editor can show as minutes: a number, or the text of one. */
const isMinutesText = (given: unknown): boolean =>
  typeof given === "number" || typeof given === "string";

/**
 * Checks that the config has the right kinds of values, which is all the visual editor needs to
 * show it: a layout the card does not know, a preset of 0 or a chip of 1441 stay in the form,
 * and `parseConfig`, which the card runs, tells the user in the preview. The editor is thrown
 * out of the form only for what it cannot show at all: the way Home Assistant's own cards with
 * a form check their configs.
 */
export function assertShape(raw: unknown): void {
  const given = recordOf(raw);
  const { entity, layout, presets, chip } = given;
  if (entity !== undefined && typeof entity !== "string") {
    throw new ConfigError("card_error_entity");
  }
  if (layout !== undefined && typeof layout !== "string") {
    throw new ConfigError("card_error_layout");
  }
  if (presets !== undefined && !(Array.isArray(presets) && presets.every(isMinutesText))) {
    throw new ConfigError("card_error_presets");
  }
  if (chip !== undefined && !isMinutesText(chip)) {
    throw new ConfigError("card_error_chip");
  }
  if (given.show_turn_off !== undefined && typeof given.show_turn_off !== "boolean") {
    throw new ConfigError("card_error_show_turn_off");
  }
  if (given.mushroom !== undefined && typeof given.mushroom !== "boolean") {
    throw new ConfigError("card_error_mushroom");
  }
  for (const press of PRESSES) {
    if (given[press] !== undefined && typeof given[press] !== "string") {
      throw new ConfigError("card_error_press");
    }
  }
  parseActions(given);
}

/** Checks the config Home Assistant hands to `setConfig`; keys the card does not know are left out. */
export function parseConfig(raw: unknown): CardConfig {
  const given = recordOf(raw);
  const { entity, layout = "pill", name, icon } = given;
  if (typeof entity !== "string" || !/^number\.[a-z0-9_]+$/.test(entity)) {
    throw new ConfigError("card_error_entity");
  }
  if (layout !== "pill" && layout !== "round") {
    throw new ConfigError("card_error_layout");
  }
  const chip = parseChip(given.chip);
  const actions = parseActions(given);
  const pressOf = (press: Press, fallback: PressChoice) =>
    parsePress(given[press], actions[ACTION_OF[press]], fallback);
  return {
    entity,
    layout,
    ...(typeof name === "string" && name !== "" && { name }),
    ...(typeof icon === "string" && icon !== "" && { icon }),
    presets: parsePresets(given.presets),
    ...(chip !== undefined && { chip }),
    show_turn_off: parseSwitch(given.show_turn_off, "card_error_show_turn_off"),
    mushroom: parseSwitch(given.mushroom, "card_error_mushroom"),
    tap: pressOf("tap", "popup"),
    double_tap: pressOf("double_tap", "none"),
    // Only the round tile has had a long press, and it keeps it unless the user turns it off
    // or gives an action of its own.
    hold: pressOf("hold", layout === "round" ? "run_or_stop" : "none"),
    ...actions,
  };
}
