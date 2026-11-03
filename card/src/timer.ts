// What the card knows of a timer, and what it shows of it: asking Timerify which timer a
// number belongs to, reading the timer's entities, and the rule for what needs drawing again.
import type { PropertyValues } from "lit";
import type { CardConfig } from "./config";
import type { HassEntity, HomeAssistant, TimerInfo } from "./hass";

export type TimerLookup =
  | { status: "pending" }
  | {
      status: "found";
      info: TimerInfo;
      /** Milliseconds to add to the browser's clock to get the server's, measured at the lookup. */
      clockOffset: number;
    }
  | { status: "not_found" }
  | { status: "incomplete" }
  | { status: "unauthorized" }
  | { status: "failed" };

/** The error code Home Assistant's websocket answers when the number is no timer's. */
const NOT_FOUND = "not_found";
/**
 * The one Timerify answers when the number is a timer's but the timer cannot be told of: its
 * target or one of its sensors is not in the entity registry.
 */
const INCOMPLETE = "timer_incomplete";
/** The one it answers when the user may not read what the answer would tell. */
const UNAUTHORIZED = "unauthorized";

/** A lookup that found its timer. */
export type FoundLookup = Extract<TimerLookup, { status: "found" }>;

/**
 * Asks Timerify which timer the "Run for" number `entityId` belongs to, and how far the
 * browser's clock is from the server's. The server stamped its answer somewhere between the
 * request leaving and the answer arriving; the middle of the wait is the best guess.
 */
export async function lookupTimer(hass: HomeAssistant, entityId: string): Promise<TimerLookup> {
  const sent = Date.now();
  try {
    const info = await hass.callWS<TimerInfo>({ type: "timerify/timer", entity_id: entityId });
    const stamped = momentOf(info.server_time);
    // Read by the one rule for every moment the server writes. A time it cannot read must not
    // put a NaN into the countdown, so it is counted by the browser's clock.
    const clockOffset = stamped === undefined ? 0 : stamped - (sent + Date.now()) / 2;
    return { status: "found", info, clockOffset };
  } catch (error) {
    const code = typeof error === "object" && error !== null && "code" in error ? error.code : "";
    if (code === NOT_FOUND) {
      return { status: "not_found" };
    }
    if (code === INCOMPLETE) {
      return { status: "incomplete" };
    }
    return { status: code === UNAUTHORIZED ? "unauthorized" : "failed" };
  }
}

/**
 * The time now, in milliseconds since the epoch, by Home Assistant's clock, which the countdown
 * is counted by: the browser's clock moved by what the lookup measured. A countdown is the
 * difference between a moment the server wrote and a clock, and a device whose clock is wrong
 * would count it wrong. Without a lookup that found the timer there is nothing to show, and
 * the browser's clock is all there is.
 */
export const serverNow = (lookup: TimerLookup): number =>
  Date.now() + (lookup.status === "found" ? lookup.clockOffset : 0);

/** Whether a sensor of the timer is disabled in the registry, so that it has no state. */
export const isDisabled = (info: TimerInfo, sensor: string): boolean =>
  info.disabled_sensors.includes(sensor);

/** Whether an entity has a value: it exists, and is neither unavailable nor unknown. */
export const hasValue = (entity: HassEntity | undefined): boolean =>
  entity !== undefined && entity.state !== "unavailable" && entity.state !== "unknown";

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

/**
 * What the timer is doing: counting down to a time someone chose, or running with no countdown
 * under a limit that turns the target off at the latest (`limit`), or with none (`open`).
 */
export type TimerState = "idle" | "counting" | "limit" | "open" | "unavailable";

export interface TimerView {
  name: string;
  icon: { icon: string } | { stateObj: HassEntity };
  target?: HassEntity;
  state: TimerState;
  /** Seconds left of the countdown; 0 unless counting, as a limit is no time that is promised. */
  remaining: number;
  /** The share of the countdown that is left, from 0 (over) to 1 (just started, or not known). */
  progress: number;
  /** When the countdown ends, or the limit turns the target off; set while counting or limited. */
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
  // Ends at holds the time of a limit with the mark `limit`: a bound with no beginning to count
  // a share from, which the card shows as full, like a run with no countdown at all.
  if (endsAt.attributes.limit === true) {
    return { ...view, state: "limit", progress: 1, endsAt: new Date(end) };
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

/**
 * Whether the target runs, with a countdown, under a limit or without either: there is
 * something to stop.
 */
export const isRunning = ({ state }: Pick<TimerView, "state">): boolean =>
  state === "counting" || state === "limit" || state === "open";

/** Whether the target has a time it is turned off at: a countdown's end or a limit. */
export const hasEnd = ({ state }: Pick<TimerView, "state">): boolean =>
  state === "counting" || state === "limit";

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

/**
 * What the words, the times and the look of the card are made of, besides entities. The
 * formatters are here because the frontend recomputes them, after the language or the
 * registry changes, in an update of `hass` that changes nothing else: the last update of
 * such a change is a formatter alone, and the card would stay one step behind without it.
 */
const SHARED_KEYS = [
  "locale",
  "language",
  "localize",
  "config",
  "user",
  "connected",
  "entities",
  "formatEntityName",
  "formatEntityState",
  "formatEntityAttributeValue",
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
