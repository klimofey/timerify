// What the card knows of a timer, and what it shows of it: asking Timerify which timer a
// number belongs to, reading the timer's entities, and the rule for what needs drawing again.
import type { PropertyValues } from "lit";
import type { CardConfig } from "./config";
import type { HassEntity, HomeAssistant, TimerInfo } from "./hass";

export type TimerLookup =
  | { status: "pending" }
  | { status: "found"; info: TimerInfo }
  | { status: "not_found" }
  | { status: "failed" };

/** The error code Home Assistant's websocket answers when the number is no timer's. */
const NOT_FOUND = "not_found";

/** Asks Timerify which timer the "Run for" number `entityId` belongs to. */
export async function lookupTimer(hass: HomeAssistant, entityId: string): Promise<TimerLookup> {
  try {
    const info = await hass.callWS<TimerInfo>({ type: "timerify/timer", entity_id: entityId });
    return { status: "found", info };
  } catch (error) {
    const rejected = typeof error === "object" && error !== null && "code" in error;
    return { status: rejected && error.code === NOT_FOUND ? "not_found" : "failed" };
  }
}

/** Whether the target runs, by the rule Timerify counts it by; a state that is none does not. */
export function targetRunning(
  target: HassEntity | undefined,
  rule: TimerInfo["target_on"],
): boolean {
  if (target === undefined || target.state === "unavailable" || target.state === "unknown") {
    return false;
  }
  return rule.states.includes(target.state) === (rule.match === "is");
}

export type TimerState = "idle" | "counting" | "open" | "unavailable";

export interface TimerView {
  name: string;
  icon: { icon: string } | { stateObj: HassEntity };
  target?: HassEntity;
  state: TimerState;
  /** Seconds left of the countdown; 0 unless counting. */
  remaining: number;
  /** The share of the countdown that is left, from 0 (over) to 1 (just started, or not known). */
  progress: number;
  endsAt?: Date;
}

const FALLBACK_ICON = "mdi:timer-outline";

const isGone = (entity: HassEntity | undefined): boolean =>
  entity === undefined || entity.state === "unavailable";

/** The moment a state or an attribute holds, in milliseconds; undefined if it holds none. */
function momentOf(value: unknown): number | undefined {
  const moment = typeof value === "string" ? Date.parse(value) : Number.NaN;
  return Number.isNaN(moment) ? undefined : moment;
}

/** What the card shows of its timer at the instant `now` (milliseconds since the epoch). */
export function timerView(
  hass: HomeAssistant,
  config: CardConfig,
  lookup: TimerLookup,
  now: number,
): TimerView {
  const info = lookup.status === "found" ? lookup.info : undefined;
  const number = hass.states[config.entity];
  const target = info && hass.states[info.target];
  const name =
    config.name ||
    (target && hass.formatEntityName(target, undefined)) ||
    number?.attributes.friendly_name ||
    config.entity;
  const icon = config.icon
    ? { icon: config.icon }
    : target
      ? { stateObj: target }
      : { icon: FALLBACK_ICON };
  const view = { name, icon, target, remaining: 0 } as const;

  const endsAt = info && hass.states[info.ends_at];
  if (info === undefined || endsAt === undefined || isGone(number) || isGone(endsAt)) {
    return { ...view, state: "unavailable", progress: 0 };
  }
  const end = momentOf(endsAt.state);
  if (end === undefined) {
    return targetRunning(target, info.target_on)
      ? { ...view, state: "open", progress: 1 }
      : { ...view, state: "idle", progress: 0 };
  }
  const start = momentOf(endsAt.attributes.started_at);
  const length = start === undefined ? 0 : (end - start) / 1000;
  const remaining = Math.max(0, (end - now) / 1000);
  return {
    ...view,
    state: "counting",
    remaining,
    progress: length > 0 ? Math.min(1, remaining / length) : 1,
    endsAt: new Date(end),
  };
}

/** The entities whose states the card reads: its number, and what Timerify names as its own. */
export function watchedEntities(entityId: string, info: TimerInfo | undefined): string[] {
  return info
    ? [
        entityId,
        info.ends_at,
        info.next_command,
        info.target,
        ...info.intervals.map(({ entity_id }) => entity_id),
      ]
    : [entityId];
}

/** What the words, the times and the look of the card are made of, besides entities. */
const SHARED_KEYS = [
  "locale",
  "language",
  "localize",
  "config",
  "user",
  "connected",
  "entities",
] as const;

/**
 * Whether an update has to render. `hass` is replaced on every change anywhere in the home,
 * so an update that brings only a new `hass` renders only when something the card shows has
 * changed in it: one of the `watched` entities, or what the words and times are made of. An
 * update that brings anything else renders.
 */
export function mattersToRender(
  changed: PropertyValues,
  hass: HomeAssistant | undefined,
  watched: readonly string[],
): boolean {
  for (const name of changed.keys()) {
    if (name !== "hass") {
      return true;
    }
  }
  const previous = changed.get("hass") as HomeAssistant | undefined;
  if (previous === undefined || hass === undefined) {
    return true;
  }
  return (
    SHARED_KEYS.some((key) => previous[key] !== hass[key]) ||
    watched.some((entityId) => previous.states[entityId] !== hass.states[entityId])
  );
}
