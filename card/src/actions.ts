// What the card does for its user. Everything goes through Timerify's own services and
// entities, so the card has no behaviour of its own (spec §2); nothing but the entity is
// targeted, and the services are left to report their own errors.
import type { HomeAssistant } from "./hass";

/**
 * Calls a service on the timer's "Run for" number. When Home Assistant refuses, it has
 * already shown the user why (the call is left to notify on error), so the card only has to
 * stay as it was.
 */
async function callOnTimer(
  hass: HomeAssistant,
  domain: string,
  service: string,
  data: Record<string, unknown>,
  runFor: string,
): Promise<void> {
  try {
    await hass.callService(domain, service, data, { entity_id: runFor });
  } catch {
    // Reported to the user by Home Assistant.
  }
}

/** Runs the timer for `minutes` from now; 0 stops it. */
export function setMinutes(hass: HomeAssistant, runFor: string, minutes: number): Promise<void> {
  return callOnTimer(hass, "number", "set_value", { value: minutes }, runFor);
}

/** Adds `minutes` to the countdown, or takes them off when negative. */
export function addMinutes(hass: HomeAssistant, runFor: string, minutes: number): Promise<void> {
  return callOnTimer(hass, "timerify", "add_time", { minutes }, runFor);
}
