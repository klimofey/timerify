// What the tests of the cards' sizes measure, and the state they measure them in.
import type { Locator } from "@playwright/test";
import type { E2EState } from "./constants";
import type { HassWs } from "./ws";

/** The width of the narrowest phone a dashboard is meant for. */
export const PHONE = { width: 320, height: 700 };

/** The side of a button that a finger may press, at least. */
export const TARGET = 40;

export interface Box {
  left: number;
  right: number;
  top: number;
  bottom: number;
  width: number;
  height: number;
}

/** Where a part of the card is on the page, which it must be. */
export async function boxOf(part: Locator): Promise<Box> {
  const box = await part.boundingBox();
  if (box === null) {
    throw new Error("The part of the card should be on the page");
  }
  return {
    left: box.x,
    right: box.x + box.width,
    top: box.y,
    bottom: box.y + box.height,
    width: box.width,
    height: box.height,
  };
}

/** Whether the part is wider inside than it shows: something of it is cut off. */
export function isCutOff(part: Locator): Promise<boolean> {
  return part.evaluate((element) => element.scrollWidth > element.clientWidth);
}

/**
 * The state both timers are put in: the loose one runs with no countdown, the strict one
 * counts.
 */
export async function runBothTimers(ws: HassWs, state: E2EState): Promise<void> {
  const { strict, loose } = state.timers;
  await ws.callService("timerify", "run", {}, { entity_id: loose.run_for });
  await ws.callService("number", "set_value", { value: 30 }, { entity_id: strict.run_for });
}
