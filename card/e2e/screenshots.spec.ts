// The pictures of the card for the documentation. They are not part of the gate: a countdown
// changes with every second, so these run on their own (`npm --prefix card run screenshots`)
// with the browser's clock fixed 15 minutes after the countdown began, which makes the card
// show the same time left and the same fill every time. The end time it shows is the
// server's, which is the time the run began plus 45 minutes, so a rerun changes the picture
// by that: do not run these to check anything. Run them when the card's look changes, look at
// the pictures (time left 30:00, the fill two thirds, every icon and state drawn), and commit
// them.
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";
import { REPO_ROOT, type TimerEntities } from "./constants";
import { expect, test } from "./fixtures";
import { mushroomBundle, serveMushroom } from "./mushroom";
import type { HassWs } from "./ws";

const MINUTE = 60_000;
const SCREENSHOTS = join(REPO_ROOT, "docs", "screenshots");
/**
 * Space around the cards in the picture, in pixels. The page's toolbar ends about nine pixels
 * above the first card, so a margin that is any larger shows the edge of it.
 */
const MARGIN = 6;

// Twice the pixels, so that the picture stays sharp on a high-resolution screen.
test.use({ colorScheme: "light", deviceScaleFactor: 2 });

/** Runs the timer for 45 minutes, and returns the moment its countdown began. */
async function startCountdown(ws: HassWs, timer: TimerEntities): Promise<number> {
  await ws.callService("number", "set_value", { value: 45 }, { entity_id: timer.run_for });
  const began = (await ws.state(timer.ends_at))?.attributes["started_at"];
  expect(typeof began, "Ends at should say when the countdown began").toBe("string");
  return Date.parse(String(began));
}

/** Saves the part of the page the two cards cover, with a margin, as the picture `name`. */
async function takePicture(page: Page, cards: Locator, name: string): Promise<void> {
  const boxes = await Promise.all((await cards.all()).map((card) => card.boundingBox()));
  const found = boxes.filter((box) => box !== null);
  expect(found).toHaveLength(2);
  const left = Math.min(...found.map((box) => box.x)) - MARGIN;
  const top = Math.min(...found.map((box) => box.y)) - MARGIN;
  const right = Math.max(...found.map((box) => box.x + box.width)) + MARGIN;
  const bottom = Math.max(...found.map((box) => box.y + box.height)) + MARGIN;
  await page.screenshot({
    path: join(SCREENSHOTS, name),
    clip: { x: left, y: top, width: right - left, height: bottom - top },
  });
}

/**
 * Waits until the pill picture is complete: what each card says (the countdown on the one, the
 * state of its target on the other) and, for each, the icon, which the frontend draws a moment
 * after the card.
 */
async function pillsAreDrawn(cards: Locator): Promise<void> {
  await expect(cards).toHaveCount(2);
  const [counting, idle] = [cards.nth(0), cards.nth(1)];
  await expect(counting.getByText("30:00", { exact: true })).toBeVisible();
  await expect(idle.getByText("Off", { exact: true })).toBeVisible();
  for (const card of [counting, idle]) {
    await expect(card.locator(".icon svg path[d]").first()).toBeAttached();
  }
}

/**
 * The same for the round tiles: the countdown is the centre of the one; the other has no time
 * to show, so its centre is its target's icon. Both have found their timer when their pop-up is
 * there, and the picture shows what they say then.
 */
async function roundsAreDrawn(cards: Locator): Promise<void> {
  await expect(cards).toHaveCount(2);
  const [counting, idle] = [cards.nth(0), cards.nth(1)];
  await expect(counting.locator(".time")).toHaveText("30:00");
  await expect(idle.getByText("Off", { exact: true })).toBeAttached();
  await expect(idle.locator(".centre .icon svg path[d]").first()).toBeAttached();
  for (const card of [counting, idle]) {
    await expect(card.locator("timerify-card-popup")).toBeAttached();
  }
}

test("pill", async ({ page, openDashboard, state, ws }) => {
  const began = await startCountdown(ws, state.timers.strict);
  await openDashboard(page, "screenshots");

  await page.clock.setFixedTime(began + 15 * MINUTE);

  const cards = page.locator("timerify-card");
  await pillsAreDrawn(cards);
  await takePicture(page, cards, "card-pill.png");
});
test("round", async ({ page, openDashboard, state, ws }) => {
  const began = await startCountdown(ws, state.timers.strict);
  await openDashboard(page, "round");

  await page.clock.setFixedTime(began + 15 * MINUTE);

  const cards = page.locator("timerify-card");
  await roundsAreDrawn(cards);
  await takePicture(page, cards, "card-round.png");
});

/**
 * Mushroom, the real release, as a resource of the dashboard: the way a user has it. The
 * resource is taken away again when the test is over, whatever came of it, so that the other
 * pictures, and the end-to-end tests, are taken without it.
 */
const withMushroom = test.extend<{ mushroomResource: void }>({
  mushroomResource: [
    async ({ ws }, use) => {
      const served = await serveMushroom(await mushroomBundle());
      const created = await ws.command<{ id: string }>("lovelace/resources/create", {
        res_type: "module",
        url: served.url,
      });
      try {
        await use();
      } finally {
        await ws.command("lovelace/resources/delete", { resource_id: created.id });
        await served.close();
      }
    },
    // Every test of this one is a test with Mushroom on the dashboard.
    { auto: true },
  ],
});

/** Waits until Mushroom is on the page, and the cards have taken its style. */
async function mushroomIsOn(page: Page, cards: Locator): Promise<void> {
  await expect
    .poll(() => page.evaluate(() => customElements.get("mushroom-entity-card") !== undefined), {
      message: "Mushroom should define its cards on the page",
    })
    .toBe(true);
  for (const card of await cards.all()) {
    await expect(card).toHaveAttribute("data-mushroom", "");
  }
}

withMushroom("pill in the Mushroom style", async ({ page, openDashboard, state, ws }) => {
  const began = await startCountdown(ws, state.timers.strict);
  await openDashboard(page, "mushroom-pill");

  await page.clock.setFixedTime(began + 15 * MINUTE);

  const cards = page.locator("timerify-card");
  await pillsAreDrawn(cards);
  await mushroomIsOn(page, cards);
  await takePicture(page, cards, "card-pill-mushroom.png");
});

withMushroom("round in the Mushroom style", async ({ page, openDashboard, state, ws }) => {
  const began = await startCountdown(ws, state.timers.strict);
  await openDashboard(page, "mushroom-round");

  await page.clock.setFixedTime(began + 15 * MINUTE);

  const cards = page.locator("timerify-card");
  await roundsAreDrawn(cards);
  await mushroomIsOn(page, cards);
  await takePicture(page, cards, "card-round-mushroom.png");
});
