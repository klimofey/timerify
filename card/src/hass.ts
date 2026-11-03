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
  /**
   * The default duration: the minutes a run with no minutes lasts in strict mode, with no
   * schedule window open. Null in loose mode, where such a run has no countdown.
   */
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
  /**
   * The settings of the target that are a share of something, from 0 to 100, which the card
   * writes with a percent sign. Empty for a switch or a thermostat.
   */
  percent_settings: string[];
  /**
   * The ids of the two sensors that are disabled in the registry. A disabled entity has no
   * state, which looks like one that has not started yet, so only this tells them apart.
   */
  disabled_sensors: string[];
  /**
   * Home Assistant's clock when it gave this answer, in UTC as ISO 8601. The card sets its
   * own clock against it, so that a device whose clock is wrong still counts down right.
   */
  server_time: string;
}
