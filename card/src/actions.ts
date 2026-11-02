// What the card does for its user. Everything goes through Timerify's own services and
// entities, so the card has no behaviour of its own (spec §2); nothing but the entity is
// targeted, and the services are left to report their own errors.
import type { HomeAssistant } from "./hass";

/** The minutes the pop-up's plus and minus add and take off. */
export const STEP_MINUTES = 5;

/**
 * Calls a service on one entity: the timer's "Run for" number, or the switch of an interval.
 * When Home Assistant refuses, it has already shown the user why (the call is left to notify
 * on error), so the card only has to stay as it was.
 */
async function callOnEntity(
  hass: HomeAssistant,
  domain: string,
  service: string,
  data: Record<string, unknown>,
  entityId: string,
): Promise<void> {
  try {
    await hass.callService(domain, service, data, { entity_id: entityId });
  } catch {
    // Reported to the user by Home Assistant.
  }
}

/** Runs the timer for `minutes` from now; 0 stops it. */
export function setMinutes(hass: HomeAssistant, runFor: string, minutes: number): Promise<void> {
  return callOnEntity(hass, "number", "set_value", { value: minutes }, runFor);
}

/** Adds `minutes` to the countdown, or takes them off when negative. */
export function addMinutes(hass: HomeAssistant, runFor: string, minutes: number): Promise<void> {
  return callOnEntity(hass, "timerify", "add_time", { minutes }, runFor);
}

/**
 * Runs the timer with no duration, which Timerify answers as it does a bare `timerify.run`:
 * a strict timer runs for its default duration, a loose one turns its target on with no
 * countdown, and a target that already runs keeps the countdown it has.
 */
export function runWithoutDuration(hass: HomeAssistant, runFor: string): Promise<void> {
  return callOnEntity(hass, "timerify", "run", {}, runFor);
}

/** Stops the timer with Timerify's own action: the countdown ends and the target turns off. */
export function stop(hass: HomeAssistant, runFor: string): Promise<void> {
  return callOnEntity(hass, "timerify", "stop", {}, runFor);
}

/** Turns the switch of a schedule interval on, or off: the interval is then open or not. */
export function setIntervalEnabled(
  hass: HomeAssistant,
  switchId: string,
  on: boolean,
): Promise<void> {
  return callOnEntity(hass, "switch", on ? "turn_on" : "turn_off", {}, switchId);
}

/**
 * Cancels a pending command. The service is aimed at the timer that owns the command, the
 * "Run for" number: another timer does not know it.
 */
export function cancelCommand(
  hass: HomeAssistant,
  runFor: string,
  commandId: string,
): Promise<void> {
  return callOnEntity(hass, "timerify", "cancel_command", { command_id: commandId }, runFor);
}
