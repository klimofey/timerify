// When a card of a test may be pressed.
import { expect, type Locator } from "@playwright/test";

/**
 * Returns when the card has found its timer: it then says what the target is doing ("Off",
 * "On", the time left), which it cannot before, and its status is blank. Until then a press
 * on the card, or a button that should be on it, comes too early.
 */
export async function isReady(card: Locator): Promise<void> {
  await expect(card.locator(".status")).not.toBeEmpty();
}
