// What the user writes into the card's YAML or the visual editor, checked.
import { lastLoaded, t, type StringKey } from "./strings";

export const DEFAULT_PRESETS = [15, 30, 45, 60, 120] as const;

/** The most minutes a preset or the chip can stand for: a day. */
export const MAX_MINUTES = 1440;

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

/** Checks the config Home Assistant hands to `setConfig`; keys the card does not know are left out. */
export function parseConfig(raw: unknown): CardConfig {
  const given = (typeof raw === "object" && raw !== null ? raw : {}) as Record<string, unknown>;
  const { entity, layout = "pill", name, icon } = given;
  if (typeof entity !== "string" || !/^number\.[a-z0-9_]+$/.test(entity)) {
    throw new ConfigError("card_error_entity");
  }
  if (layout !== "pill" && layout !== "round") {
    throw new ConfigError("card_error_layout");
  }
  const chip = parseChip(given.chip);
  return {
    entity,
    layout,
    ...(typeof name === "string" && name !== "" && { name }),
    ...(typeof icon === "string" && icon !== "" && { icon }),
    presets: parsePresets(given.presets),
    ...(chip !== undefined && { chip }),
  };
}
