// The one stand-in for Home Assistant's `hass` object that every scenario uses.
//
// It behaves the way the real one does where the card can tell: a change gives a new `hass`
// object (`with`, `state`) in which the states that did not change are the same objects, the
// strings of a category arrive through `loadBackendTranslation` and reach the card as a new
// `localize`, and the websocket answers `timerify/timer` from the timers it was given.
import { common as english } from "../../custom_components/timerify/translations/en.json";
import { common as russian } from "../../custom_components/timerify/translations/ru.json";
import type {
  HassEntity,
  HomeAssistant,
  Localize,
  RegistryEntry,
  ServiceTarget,
  TimerInfo,
} from "../src/hass";

/** 09:00 in Jerusalem, as the Python scenarios start. */
export const START = Date.UTC(2026, 0, 5, 7, 0);

export const NUMBER = "number.boiler_run_for";
export const ENDS_AT = "sensor.boiler_ends_at";
export const NEXT_COMMAND = "sensor.boiler_next_command";
export const BOILER = "switch.boiler";
export const AC_NUMBER = "number.ac_run_for";
export const AC_ENDS_AT = "sensor.ac_ends_at";
export const AC_NEXT_COMMAND = "sensor.ac_next_command";
export const AC = "climate.ac";

export type Language = "en" | "ru";

const strings: Record<Language, Record<string, string>> = { en: english, ru: russian };
const STRINGS_PREFIX = "component.timerify.common.";

/** The `localize` function of a frontend that holds the card's strings in `language`. */
export function localizeFor(language: Language): Localize {
  return (key, placeholders) => {
    const text = key.startsWith(STRINGS_PREFIX)
      ? (strings[language][key.slice(STRINGS_PREFIX.length)] ?? "")
      : "";
    return text.replace(/\{(\w+)\}/g, (blank, name: string) =>
      String(placeholders?.[name] ?? blank),
    );
  };
}

/** A frontend that has not loaded the card's strings: it translates nothing. */
const translatesNothing: Localize = () => "";

export interface FakeState {
  state: string;
  attributes?: Record<string, unknown>;
}

/** A timer of Timerify as the scenarios set it up: the answer about it and the states of its entities. */
export interface FakeTimer {
  /** The "Run for" number, the entity the card is configured with. */
  number: string;
  /** What `timerify/timer` answers for that number. */
  info: TimerInfo;
  states: Record<string, FakeState>;
}

function timerOf(number: string, name: string, info: TimerInfo, target: FakeState): FakeTimer {
  const states: Record<string, FakeState> = {
    [number]: {
      state: "0",
      attributes: { friendly_name: `${name} Run for`, unit_of_measurement: "min" },
    },
    [info.ends_at]: {
      state: "unknown",
      attributes: { friendly_name: `${name} Ends at`, device_class: "timestamp", started_at: null },
    },
    [info.next_command]: {
      state: "unknown",
      attributes: { friendly_name: `${name} Next command`, commands: [] },
    },
    [info.target]: target,
  };
  for (const interval of info.intervals) {
    states[interval.entity_id] = {
      state: "on",
      attributes: { friendly_name: `${name} Schedule ${interval.title}` },
    };
  }
  return { number, info, states };
}

/** A strict timer on `switch.boiler` ("Boiler", off), 45 minutes by default, no intervals. */
export function boilerTimer(overrides: Partial<TimerInfo> = {}): FakeTimer {
  const info: TimerInfo = {
    entry_id: "boiler_entry",
    target: BOILER,
    mode: "strict",
    default_duration: 45,
    ends_at: ENDS_AT,
    next_command: NEXT_COMMAND,
    intervals: [],
    target_on: { match: "is", states: ["on"] },
    ...overrides,
  };
  return timerOf(NUMBER, "Boiler", info, {
    state: "off",
    attributes: { friendly_name: "Boiler" },
  });
}

/** A loose timer on `climate.ac` ("AC", off), where anything but off counts as on. */
export function acTimer(): FakeTimer {
  const info: TimerInfo = {
    entry_id: "ac_entry",
    target: AC,
    mode: "loose",
    default_duration: null,
    ends_at: AC_ENDS_AT,
    next_command: AC_NEXT_COMMAND,
    intervals: [],
    target_on: { match: "is_not", states: ["off"] },
  };
  return timerOf(AC_NUMBER, "AC", info, {
    state: "off",
    attributes: { friendly_name: "AC", temperature: 20, hvac_modes: ["off", "heat", "cool"] },
  });
}

export interface ServiceCall {
  domain: string;
  service: string;
  data?: Record<string, unknown>;
  target?: ServiceTarget;
  notifyOnError?: boolean;
}

export interface WsRequest {
  type: string;
  [field: string]: unknown;
}

export interface Changes {
  language?: Language;
  connected?: boolean;
  entities?: Record<string, RegistryEntry>;
  localize?: Localize;
  /** A state to set; `null` removes it, as when an entity is deleted or unavailable to the registry. */
  states?: Record<string, FakeState | null>;
}

export interface FakeHass extends HomeAssistant {
  /** Every service the card called, in order, over all the `hass` objects made from this one. */
  readonly calls: ServiceCall[];
  /** Every websocket request the card made. */
  readonly requests: WsRequest[];
  /** Every `[category, integration]` whose strings were asked for. */
  readonly translationLoads: [string, string][];
  /** The next service call is refused with `error`. */
  rejectNext(error: unknown): void;
  /** The next load of strings fails with `error`. */
  rejectNextTranslations(error: unknown): void;
  /** Every `timerify/timer` request fails with the error code `code`, until `answerNormally`. */
  answerWith(code: string): void;
  answerNormally(): void;
  /** From now on a `timerify/timer` request waits until `answerNext` lets its answer through. */
  holdAnswers(): void;
  /** Lets the answer to the oldest request that waits through. */
  answerNext(): void;
  /** A new `hass` object with the changes, as Home Assistant makes one for every change. */
  with(changes: Changes): FakeHass;
  /** A new `hass` object in which the entity has this state. */
  state(entityId: string, state: string, attributes?: Record<string, unknown>): FakeHass;
}

export interface FakeHassOptions {
  language?: Language;
  isAdmin?: boolean;
  /** `hass.config.time_zone`, the server's. */
  timeZone?: string;
  /** The user's choice of `hass.locale.time_zone`. */
  localeTimeZone?: "server" | "local";
  timeFormat?: "language" | "system" | "12" | "24";
  /** The timers Timerify has; a boiler timer if none are given. */
  timers?: FakeTimer[];
  /** States on top of the timers' own; `null` removes one. */
  states?: Record<string, FakeState | null>;
  /** Whether the card's strings are in `localize` already; they are not when a page has just opened. */
  stringsLoaded?: boolean;
}

/** What the `hass` objects made from one another share: the log and the way the server behaves. */
interface World {
  timers: FakeTimer[];
  calls: ServiceCall[];
  requests: WsRequest[];
  translationLoads: [string, string][];
  failingCode?: string;
  /** The requests that wait for their answer to be let through, oldest first; set while held. */
  held?: (() => void)[];
  callRejection?: { error: unknown };
  translationRejection?: { error: unknown };
}

type States = Record<string, HassEntity | undefined>;

function entityOf(entityId: string, { state, attributes }: FakeState): HassEntity {
  return { entity_id: entityId, state, attributes: { ...attributes } };
}

function withStates(states: States, changes: Record<string, FakeState | null>): States {
  const next = { ...states };
  for (const [entityId, change] of Object.entries(changes)) {
    if (change === null) {
      delete next[entityId];
    } else {
      next[entityId] = entityOf(entityId, change);
    }
  }
  return next;
}

/** The registry entries of the entities of the timers and their targets, one device per target. */
function registryOf(timers: FakeTimer[]): Record<string, RegistryEntry> {
  const entries: Record<string, RegistryEntry> = {};
  for (const { number, info } of timers) {
    const device_id = `device_of_${info.target.replace(".", "_")}`;
    const own = (entity_id: string, translation_key: string): RegistryEntry => ({
      entity_id,
      platform: "timerify",
      translation_key,
      device_id,
    });
    entries[number] = own(number, "run_for");
    entries[info.ends_at] = own(info.ends_at, "ends_at");
    entries[info.next_command] = own(info.next_command, "next_command");
    for (const { entity_id } of info.intervals) {
      entries[entity_id] = own(entity_id, "interval");
    }
    entries[info.target] = { entity_id: info.target, platform: "demo", device_id };
  }
  return entries;
}

/** What a `hass` object is made of; the objects among it are the same from one `hass` to the next. */
interface Parts {
  language: Language;
  connected: boolean;
  entities: Record<string, RegistryEntry>;
  localize: Localize;
  states: States;
  locale: HomeAssistant["locale"];
  config: HomeAssistant["config"];
  user: NonNullable<HomeAssistant["user"]>;
}

function lookupError(code: string): { code: string; message: string } {
  return { code, message: `The server answered ${code}` };
}

function build(world: World, parts: Parts): FakeHass {
  const hass: FakeHass = {
    states: parts.states,
    entities: parts.entities,
    language: parts.language,
    locale: parts.locale,
    config: parts.config,
    user: parts.user,
    connected: parts.connected,
    localize: parts.localize,
    calls: world.calls,
    requests: world.requests,
    translationLoads: world.translationLoads,

    async loadBackendTranslation(category, integration) {
      world.translationLoads.push([category, integration]);
      const failure = world.translationRejection;
      world.translationRejection = undefined;
      if (failure) {
        throw failure.error;
      }
      return localizeFor(parts.language);
    },

    async callService(domain, service, data, target, notifyOnError) {
      world.calls.push({ domain, service, data, target, notifyOnError });
      const failure = world.callRejection;
      world.callRejection = undefined;
      if (failure) {
        throw failure.error;
      }
      return {};
    },

    async callWS<T>(message: WsRequest): Promise<T> {
      world.requests.push(message);
      if (message.type !== "timerify/timer") {
        throw lookupError("unknown_command");
      }
      const held = world.held;
      if (held) {
        await new Promise<void>((letThrough) => held.push(letThrough));
      }
      if (world.failingCode !== undefined) {
        throw lookupError(world.failingCode);
      }
      const timer = world.timers.find(({ number }) => number === message.entity_id);
      if (timer === undefined) {
        throw lookupError("not_found");
      }
      return structuredClone(timer.info) as T;
    },

    formatEntityName: (entity) => entity.attributes.friendly_name ?? entity.entity_id,
    formatEntityState: (entity, state) => state ?? entity.state,
    formatEntityAttributeValue(entity, attribute, value) {
      const shown = `${value ?? entity.attributes[attribute]}`;
      return attribute === "temperature" ? `${shown} °C` : shown;
    },

    rejectNext(error) {
      world.callRejection = { error };
    },
    rejectNextTranslations(error) {
      world.translationRejection = { error };
    },
    answerWith(code) {
      world.failingCode = code;
    },
    answerNormally() {
      world.failingCode = undefined;
    },
    holdAnswers() {
      world.held = [];
    },
    answerNext() {
      world.held?.shift()?.();
    },
    with(changes) {
      const { states, ...rest } = changes;
      return build(world, {
        ...parts,
        ...rest,
        locale: changes.language
          ? { ...parts.locale, language: changes.language }
          : parts.locale,
        states: states ? withStates(parts.states, states) : parts.states,
      });
    },
    state(entityId, state, attributes) {
      return hass.with({ states: { [entityId]: { state, attributes } } });
    },
  };
  return hass;
}

export function fakeHass(options: FakeHassOptions = {}): FakeHass {
  const language = options.language ?? "en";
  const timers = options.timers ?? [boilerTimer()];
  const world: World = { timers, calls: [], requests: [], translationLoads: [] };
  const timerStates = Object.assign({}, ...timers.map(({ states }) => states)) as Record<
    string,
    FakeState
  >;
  return build(world, {
    language,
    connected: true,
    entities: registryOf(timers),
    localize: options.stringsLoaded === false ? translatesNothing : localizeFor(language),
    states: withStates({}, { ...timerStates, ...options.states }),
    locale: {
      language,
      time_format: options.timeFormat ?? "language",
      time_zone: options.localeTimeZone ?? "server",
    },
    config: { time_zone: options.timeZone ?? "Asia/Jerusalem" },
    user: { is_admin: options.isAdmin ?? true },
  });
}
