// How the tests press a card as a user does: with the mouse, at a point of the page, not through
// Playwright's own click, which refuses a point that something else covers (the card's content
// lets presses through to the body under it, so every part of it is "covered").
import { expect, type Locator, type Page } from "@playwright/test";

interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

async function boxOf(locator: Locator): Promise<Box> {
  const box = await locator.boundingBox();
  if (box === null) {
    throw new Error("The card should be on the page");
  }
  return box;
}

/** Taps the middle of the card with the mouse: down and up at once, not a hold. */
export async function tap(page: Page, card: Locator): Promise<void> {
  const box = await boxOf(card);
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
}

/**
 * Presses the middle of the card with the mouse and lets go once the card says that letting
 * go will act (`data-held`, which is what the user sees after half a second), as a user
 * does. There is no fixed wait: the assertion waits for the card, on the browser's own clock:
 * a test that holds must not install a fake one (`page.clock.install` would freeze the hold's
 * timer, so that `data-held` never came).
 */
export async function hold(page: Page, card: Locator): Promise<void> {
  const box = await boxOf(card);
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await expect(card).toHaveAttribute("data-held", "");
  await page.mouse.up();
  await expect(card).not.toHaveAttribute("data-held");
}

/**
 * Taps the border of the card, half a pixel inside its right edge and then its bottom edge,
 * and expects the pop-up each time: the border is part of the card, and a press on it is a
 * tap. (The left and top edges would open it without the body reaching over the border, since
 * the browser takes a point for the pixel right of it and below it.)
 */
export async function tapBorder(page: Page, card: Locator): Promise<void> {
  const dialog = card.locator("dialog");
  await expect(dialog).toBeHidden();
  const box = await boxOf(card.locator("ha-card"));
  const edges = {
    right: { x: box.x + box.width - 0.5, y: box.y + box.height / 2 },
    bottom: { x: box.x + box.width / 2, y: box.y + box.height - 0.5 },
  };
  for (const [edge, point] of Object.entries(edges)) {
    await page.mouse.click(point.x, point.y);
    await expect(dialog, `a tap on the ${edge} border`).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
  }
}
