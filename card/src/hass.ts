// The part of Home Assistant's frontend `hass` object that the card uses, and the answer of
// Timerify's websocket command. Nothing else of `hass` is read, so nothing else is declared.

/** The state of an entity, as `hass.states` holds it. */
export interface HassEntity {
  entity_id: string;
  state: string;
  attributes: { friendly_name?: string; [attribute: string]: unknown };
}

/** The entry of an entity in the registry the frontend keeps: what a card can tell of it. */
export interface RegistryEntry {
  entity_id: string;
  platform: string;
  translation_key?: string;
  device_id?: string;
}

export type Localize = (
  key: string,
  placeholders?: Record<string, string | number>,
) => string;

export interface ServiceTarget {
  entity_id: string;
}

export interface HomeAssistant {
  /** An entity that has no state (it is gone, or disabled) is absent, not an empty object. */
  states: Record<string, HassEntity | undefined>;
  entities: Record<string, RegistryEntry>;
  language: string;
  locale: {
    language: string;
    time_format: "language" | "system" | "12" | "24";
    time_zone: "local" | "server";
  };
  config: { time_zone: string };
  user?: { is_admin: boolean };
  connected: boolean;
  localize: Localize;
  /** Resolves to the `localize` function that holds the strings of the category. */
  loadBackendTranslation(category: string, integration: string): Promise<Localize>;
  callService(
    domain: string,
    service: string,
    data?: Record<string, unknown>,
    target?: ServiceTarget,
    notifyOnError?: boolean,
  ): Promise<unknown>;
  callWS<T>(message: { type: string; [field: string]: unknown }): Promise<T>;
  formatEntityName(entity: HassEntity, name: undefined): string;
  formatEntityState(entity: HassEntity, state?: string): string;
  formatEntityAttributeValue(entity: HassEntity, attribute: string, value?: unknown): string;
}

/** A schedule interval of a timer: the switch that enables it, and its title. */
export interface IntervalInfo {
  entity_id: string;
  title: string;
}

/** Which states of the target count as on: the state is listed (`is`), or it is not (`is_not`). */
export interface OnRule {
  match: "is" | "is_not";
  states: string[];
}

/** What `timerify/timer` answers for the "Run for" number of a timer. Mirrors `websocket.py`. */
export interface TimerInfo {
  entry_id: string;
  target: string;
  mode: "strict" | "loose";
  /** The minutes a bare run lasts in strict mode; null in loose mode. */
  default_duration: number | null;
  /** The entity ids of the two sensors of the timer. */
  ends_at: string;
  next_command: string;
  /**
   * The intervals in the order they were added. A switch that was disabled in the registry is
   * listed but has no state.
   */
  intervals: IntervalInfo[];
  target_on: OnRule;
}
