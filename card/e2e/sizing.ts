// What the tests of the cards' sizes measure, and the state they measure them in.
import { expect, type Locator, type Page } from "@playwright/test";
import type { E2EState } from "./constants";
import type { HassWs } from "./ws";

/** The width of the narrowest phone a dashboard is meant for. */
export const PHONE = { width: 320, height: 700 };

/** The side of a button that a finger may press, at least. */
export const TARGET = 40;

/** The side of the round tile's dial where the tile has room for it. */
export const DIAL = 80;

/** The inner diameter of the dial's ring as a share of the dial: the ring is 6 thick in 80. */
export const RING_INNER = 68 / 80;

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

/** Whether the box of `part` is inside the box of `whole`. */
export function isInside(part: Box, whole: Box): boolean {
  return (
    part.left >= whole.left &&
    part.right <= whole.right &&
    part.top >= whole.top &&
    part.bottom <= whole.bottom
  );
}

/**
 * Whether the part of the dial, the time or the icon, is in the circle inside its ring: the
 * corner of its box that is farthest from the middle of the dial is no farther from it than the
 * radius of that circle.
 */
export async function fitsInRing(dial: Locator, part: Locator): Promise<boolean> {
  const [whole, inner] = await Promise.all([boxOf(dial), boxOf(part)]);
  const dx = (inner.left + inner.right) / 2 - (whole.left + whole.right) / 2;
  const dy = (inner.top + inner.bottom) / 2 - (whole.top + whole.bottom) / 2;
  const corner = Math.hypot(Math.abs(dx) + inner.width / 2, Math.abs(dy) + inner.height / 2);
  return corner <= (RING_INNER * whole.width) / 2;
}

/**
 * Sets the page to the size and loads it again, as a device of that size loads it: the login
 * waits for the sidebar, which a phone hides, so a page is narrowed after it.
 */
export async function reloadAtWidth(
  page: Page,
  size: { width: number; height: number },
): Promise<void> {
  await page.setViewportSize(size);
  await page.reload({ waitUntil: "load" });
  await expect(page.locator("#ha-launch-screen")).toHaveCount(0);
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
