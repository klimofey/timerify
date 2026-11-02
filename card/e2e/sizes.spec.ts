// The narrowest a card with a Turn off button can be made, on the narrowest phone, in the
// longer of the two languages: everything it shows is inside it, and nothing is cut off or
// laid over something else. View "sizes": a sections view of one section, whose cards ask
// for one column, which is less than they declare, so Home Assistant gives each the fewest
// columns it declares (`min_columns`, which `getGridOptions` of the card pins).
import type { Locator, Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { isReady } from "./ready";
import { stringsIn } from "./strings";

/** The width of the narrowest phone a dashboard is meant for. */
const PHONE = { width: 320, height: 700 };

test.use({ locale: "ru-RU" });

interface Box {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

/** Where a part of the card is on the page, which it must be. */
async function boxOf(part: Locator): Promise<Box> {
  const box = await part.boundingBox();
  if (box === null) {
    throw new Error("The part of the card should be on the page");
  }
  return { left: box.x, right: box.x + box.width, top: box.y, bottom: box.y + box.height };
}

/** Whether the part is wider inside than it shows: something of it is cut off. */
function isCutOff(part: Locator): Promise<boolean> {
  return part.evaluate((element) => element.scrollWidth > element.clientWidth);
}

/** The cards of the view, in the order of the dashboard. */
function cardsOf(page: Page): { pillWithChip: Locator; pill: Locator; round: Locator } {
  const cards = page.locator("timerify-card");
  return { pillWithChip: cards.nth(0), pill: cards.nth(1), round: cards.nth(2) };
}

test.describe("the cards with a Turn off button at their narrowest", () => {
  test.beforeEach(async ({ page, openDashboard, state, ws }) => {
    const { strict, loose } = state.timers;
    // The loose timer runs with no countdown, the strict one counts: both show the button.
    await ws.callService("timerify", "run", {}, { entity_id: loose.run_for });
    await ws.callService("number", "set_value", { value: 30 }, { entity_id: strict.run_for });
    await openDashboard(page, "sizes");
    // The login waits for the sidebar, which a phone hides: the page is narrowed after it, and
    // loaded again, as a phone loads it.
    await page.setViewportSize(PHONE);
    await page.reload({ waitUntil: "load" });
    await expect(page.locator("#ha-launch-screen")).toHaveCount(0);
    await expect(page.locator("timerify-card")).toHaveCount(3);
    for (const card of Object.values(cardsOf(page))) {
      await isReady(card);
    }
  });

  test("show a pill with its icon, its button and its chip side by side", async ({ page }) => {
    const russian = await stringsIn("ru");
    const { pillWithChip, pill } = cardsOf(page);

    for (const card of [pillWithChip, pill]) {
      const button = card.getByRole("button", { name: russian.card_turn_off, exact: true });
      await expect(button).toBeVisible();
      const outline = await boxOf(card.locator("ha-card"));
      const icon = await boxOf(card.locator(".icon"));
      const turnOff = await boxOf(button);

      expect(await isCutOff(card.locator(".content"))).toBe(false);
      expect(await isCutOff(button)).toBe(false);
      expect(icon.left).toBeGreaterThanOrEqual(outline.left);
      expect(turnOff.left).toBeGreaterThanOrEqual(icon.right);
      expect(turnOff.right).toBeLessThanOrEqual(outline.right);
    }

    const outline = await boxOf(pillWithChip.locator("ha-card"));
    const turnOff = await boxOf(pillWithChip.locator(".turn-off"));
    const chip = await boxOf(pillWithChip.locator(".chip"));
    expect(chip.left).toBeGreaterThanOrEqual(turnOff.right);
    expect(chip.right).toBeLessThanOrEqual(outline.right);
  });

  test("show a round tile with its button under its dial and inside it", async ({ page }) => {
    const russian = await stringsIn("ru");
    const { round } = cardsOf(page);
    const button = round.getByRole("button", { name: russian.card_turn_off, exact: true });
    await expect(button).toBeVisible();

    const outline = await boxOf(round.locator("ha-card"));
    const dial = await boxOf(round.locator(".dial"));
    const turnOff = await boxOf(button);

    expect(await isCutOff(round.locator(".content"))).toBe(false);
    expect(await isCutOff(button)).toBe(false);
    expect(turnOff.left).toBeGreaterThanOrEqual(outline.left);
    expect(turnOff.right).toBeLessThanOrEqual(outline.right);
    expect(turnOff.top).toBeGreaterThanOrEqual(dial.bottom);
    expect(turnOff.bottom).toBeLessThanOrEqual(outline.bottom);
  });
});
