// What the end-to-end tests and the Home Assistant they run against agree on.
import { fileURLToPath } from "node:url";

/** `localhost`, not 127.0.0.1: the frontend's service worker registers only there or on https. */
export const BASE_URL = "http://localhost:18124";
export const REPO_ROOT = fileURLToPath(new URL("../..", import.meta.url));
/**
 * What the strict timer's target is called on the dashboard: `scripts.e2e.hass` gives it this
 * name in the entity registry, as a user renames an entity (`STRICT_NAME` there says the same).
 */
export const STRICT_NAME = "Boiler";
/** Written by `scripts.e2e.hass up`, read by the tests; the file goes with `down`. */
export const STATE_FILE = fileURLToPath(new URL(".state.json", import.meta.url));

/** The entities of one timer, as `scripts.e2e.hass` found them. */
export interface TimerEntities {
  entry_id: string;
  /** The entity the timer runs. */
  target: string;
  /** The timer's "Run for" number, the entity the card is configured with. */
  run_for: string;
  ends_at: string;
  next_command: string;
  device_id: string;
}

export interface Account {
  username: string;
  password: string;
  /** A long-lived access token, for the test's own connection to Home Assistant. */
  token: string;
}

export type UserName = "admin" | "viewer";

/** One view of a dashboard, as it is saved. */
export interface DashboardView {
  path: string;
  [field: string]: unknown;
}

/** A dashboard, as it is saved. */
export interface DashboardConfig {
  views: DashboardView[];
  [field: string]: unknown;
}

/** What `scripts.e2e.hass up` leaves in the state file. */
export interface E2EState {
  base_url: string;
  users: Record<UserName, Account>;
  timers: {
    /** On a switch that sits on no device; default duration 30 minutes. */
    strict: TimerEntities;
    /** On a switch that sits on a device of its own. */
    loose: TimerEntities;
    /** Its "Ends at" sensor is disabled in the registry, and stays so. */
    disabled: TimerEntities;
  };
  /** An interval of the strict timer, 12 hours from the start: it is never open in a run. */
  interval: {
    switch: string;
    weekday: string;
    /** `HH:MM` on the clock of the server. */
    start: string;
    end: string;
  };
  /** The command that every test starts with on the loose timer. */
  command: { action: string; delay: number };
  /** The `url_path` of the dashboard that has one view for each file of tests. */
  dashboard: string;
  /** The dashboard as `up` saved it: the reset saves it again after a test changed it. */
  dashboard_config: DashboardConfig;
}
