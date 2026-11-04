// The dial of the round tile at every size the tile allows, which sizes.spec.ts measures in the
// Home Assistant look and mushroom.spec.ts in the Mushroom style. View "dials": six round tiles
// with no Turn off button, three in each look: the strict timer at the fewest columns a round
// tile may have (2) and at 3, and the loose timer at the fewest. The strict timer counts, and
// the loose one is idle, so its dial holds the icon.
import { expect, type Locator, type Page } from "@playwright/test";
import type { E2EState } from "./constants";
import type { OpenDashboard } from "./fixtures";
import { loadMushroom } from "./mushroom";
import { isReady } from "./ready";
import { DIAL, boxOf, fitsInRing, isInside, reloadAtWidth } from "./sizing";
import type { HassWs } from "./ws";

/** The smallest the time is drawn, in px. */
export const MIN_TIME_FONT = 9;

/** The width of the dial in px from which it shows the time: 20 % of it is `MIN_TIME_FONT`. */
export const TIME_FROM = 45;

/** The widths of the page, a desktop, a big phone and the narrowest phone, and what the dial of
 * the tile of 2 columns holds at each: the time where it is wide enough to be read, else the
 * icon. The tile is 76.7, 55.7 and 44 px wide, its dial 58.7, 37.7 and 26 px (in the Mushroom
 * style, 54.7, 33.7 and 22 px). */
const PAGES = [
  { width: 1280, fewest: ".time" },
  { width: 390, fewest: ".icon" },
  { width: 320, fewest: ".icon" },
] as const;

type Centre = ".time" | ".icon";

/** Shows the view "dials" with the strict timer counting for 90 minutes: `1:29:xx`, the
 * longest text a dial holds. */
export async function showDials(
  page: Page,
  openDashboard: OpenDashboard,
  ws: HassWs,
  state: E2EState,
): Promise<void> {
  const { run_for } = state.timers.strict;
  await ws.callService("number", "set_value", { value: 90 }, { entity_id: run_for });
  await openDashboard(page, "dials");
}

/** The font size of the part in px. */
async function fontSizeOf(part: Locator): Promise<number> {
  return Number.parseFloat(await part.evaluate((element) => getComputedStyle(element).fontSize));
}

/**
 * Checks the dial of a round tile: it is inside the tile, a square of at most its full size,
 * and holds `shown` inside its ring and the other of `.time` and `.icon` not at all. A time that
 * is shown is never drawn smaller than `MIN_TIME_FONT`.
 */
async function expectDialToShow(card: Locator, shown: Centre): Promise<void> {
  const dial = card.locator(".dial");
  const box = await boxOf(dial);
  expect(isInside(box, await boxOf(card.locator("ha-card")))).toBe(true);
  expect(box.width).toBeLessThanOrEqual(DIAL);
  expect(Math.abs(box.width - box.height)).toBeLessThan(0.5);

  await expect(card.locator(shown)).toBeVisible();
  await expect(card.locator(shown === ".time" ? ".icon" : ".time")).toBeHidden();
  expect(await fitsInRing(dial, card.locator(shown))).toBe(true);
  if (shown === ".time") {
    expect(await fontSizeOf(card.locator(".time"))).toBeGreaterThanOrEqual(MIN_TIME_FONT);
  }
}

/**
 * The three tiles of one look of the view, at every width of the page. `first` is the place of
 * the first of them among the six; `mushroom` says that the look is the Mushroom style, which
 * the page gets once it is loaded again.
 */
export async function expectDialsToFit(
  page: Page,
  { first, mushroom }: { first: number; mushroom: boolean },
): Promise<void> {
  for (const { width, fewest } of PAGES) {
    await reloadAtWidth(page, { width, height: 900 });
    const cards = page.locator("timerify-card");
    await expect(cards).toHaveCount(6);
    if (mushroom) {
      await loadMushroom(page);
    }
    const [strictFewest, strictThree, looseFewest] = [0, 1, 2].map((index) =>
      cards.nth(first + index),
    ) as [Locator, Locator, Locator];
    for (const card of [strictFewest, strictThree, looseFewest]) {
      await isReady(card);
      if (mushroom) {
        await expect(card).toHaveAttribute("data-mushroom", "");
      }
    }

    await expectDialToShow(strictFewest, fewest);
    await expectDialToShow(strictThree, ".time");
    await expectDialToShow(looseFewest, ".icon");
    // The time is for the eye alone: the body is named by it for a screen reader.
    for (const card of [strictFewest, strictThree]) {
      await expect(card.locator(".body")).toHaveAccessibleName(/1:29:\d\d/);
    }
    if (width === 1280) {
      expect((await boxOf(strictThree.locator(".dial"))).width).toBe(DIAL);
    }
  }
}

/**
 * Narrows the tile, a px at a time, across the width where the dial stops showing the time:
 * from a dial of `TIME_FROM` px the dial shows the time, at least `MIN_TIME_FONT` px high, and
 * below it the icon.
 */
export async function expectTimeFromTheWidth(card: Locator): Promise<void> {
  await isReady(card);
  const dial = card.locator(".dial");
  // What the tile has around its dial: the border and the padding of the card.
  const chrome = (await boxOf(card.locator("ha-card"))).width - (await boxOf(dial)).width;
  for (let width = TIME_FROM - 5; width <= TIME_FROM + 5; width += 1) {
    await card.evaluate((host, tile) => {
      host.style.width = `${tile}px`;
    }, width + chrome);
    await expect.poll(async () => (await boxOf(dial)).width).toBeCloseTo(width, 1);

    await expectDialToShow(card, width < TIME_FROM ? ".icon" : ".time");
  }
}
