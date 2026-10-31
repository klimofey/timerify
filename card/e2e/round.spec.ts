// The round card in a real Home Assistant: a tap opens its pop-up, and a long press starts the
// timer with no duration, or stops it when it runs, without opening the pop-up. View "round":
// the strict timer's round card, then the loose timer's.
import type { Locator, Page } from "@playwright/test";
import { STRICT_NAME } from "./constants";
import { expect, test } from "./fixtures";
import { hold, tap, tapBorder } from "./press";

/** The strict timer's default duration, which a bare run takes (Task 4's fixture). */
const DEFAULT_MINUTES = "30";

/** The cards of the view, in the order of the dashboard: the strict timer's, the loose one's. */
function cardsOf(page: Page): { strict: Locator; loose: Locator } {
  const cards = page.locator("timerify-card");
  return { strict: cards.nth(0), loose: cards.nth(1) };
}

/**
 * Returns when the card has found its timer: until then it is a card of a timer that is not
 * there, and a long press on it does nothing.
 */
async function isReady(card: Locator): Promise<void> {
  await expect(card.locator("timerify-card-popup")).toBeAttached();
}

test.describe("the round card in Home Assistant", () => {
  test.beforeEach(async ({ page, openDashboard }) => {
    await openDashboard(page, "round");
    const { strict, loose } = cardsOf(page);
    await expect(page.locator("timerify-card")).toHaveCount(2);
    await expect(strict.locator(".name")).toHaveText(STRICT_NAME);
    await isReady(strict);
    await isReady(loose);
  });

  test("opens the pop-up on a tap, also on the border of the card", async ({ page, state, ws }) => {
    const { strict } = cardsOf(page);
    const dialog = strict.locator("dialog");

    await tap(page, strict);

    await expect(dialog).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await tapBorder(page, strict);
    // A tap starts nothing.
    expect((await ws.state(state.timers.strict.run_for))?.state).toBe("0");
  });

  test("holding starts the default duration on a strict timer", async ({ page, state, ws }) => {
    const { strict: entities } = state.timers;
    const { strict } = cardsOf(page);

    await hold(page, strict);

    await expect.poll(async () => (await ws.state(entities.run_for))?.state).toBe(DEFAULT_MINUTES);
    await expect.poll(async () => (await ws.state(entities.target))?.state).toBe("on");
    await expect(strict.locator(".time")).toBeVisible();
    await expect(strict.locator("dialog")).toBeHidden();
  });

  test("holding again stops it", async ({ page, state, ws }) => {
    const { strict: entities } = state.timers;
    const { strict } = cardsOf(page);
    await hold(page, strict);
    await expect.poll(async () => (await ws.state(entities.run_for))?.state).toBe(DEFAULT_MINUTES);
    // The card shows the countdown: it is what the second hold stops.
    await expect(strict.locator(".time")).toBeVisible();

    await hold(page, strict);

    await expect.poll(async () => (await ws.state(entities.run_for))?.state).toBe("0");
    await expect.poll(async () => (await ws.state(entities.target))?.state).toBe("off");
    await expect(strict.locator(".time")).toHaveCount(0);
    await expect(strict.locator("dialog")).toBeHidden();
  });

  test("holding runs a loose timer without a countdown", async ({ page, state, ws }) => {
    const { loose: entities } = state.timers;
    const { loose } = cardsOf(page);

    await hold(page, loose);

    await expect.poll(async () => (await ws.state(entities.target))?.state).toBe("on");
    expect((await ws.state(entities.ends_at))?.state).toBe("unknown");
    // The ring is full, and there is no time to count: the icon is in its centre.
    await expect(loose.locator("circle.progress")).toHaveAttribute("stroke-dashoffset", "0");
    await expect(loose.locator(".time")).toHaveCount(0);
    await expect(loose.locator("dialog")).toBeHidden();
  });

  test("holding stops a loose timer that runs without a countdown", async ({
    page,
    state,
    ws,
  }) => {
    const { loose: entities } = state.timers;
    const { loose } = cardsOf(page);
    await hold(page, loose);
    await expect.poll(async () => (await ws.state(entities.target))?.state).toBe("on");
    // The card shows it runs, the ring full: it is what the second hold stops.
    const ring = loose.locator("circle.progress");
    await expect(ring).toHaveAttribute("stroke-dashoffset", "0");

    await hold(page, loose);

    await expect.poll(async () => (await ws.state(entities.target))?.state).toBe("off");
    expect((await ws.state(entities.ends_at))?.state).toBe("unknown");
    // The ring is empty again, and nothing opened.
    await expect(ring).not.toHaveAttribute("stroke-dashoffset", "0");
    await expect(loose.locator("dialog")).toBeHidden();
  });
});
