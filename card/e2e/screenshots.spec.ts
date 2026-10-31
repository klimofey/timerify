// The pictures of the card for the documentation. They are not part of the gate: a countdown
// changes with every second, so these run on their own (`npm --prefix card run screenshots`)
// with the browser's clock fixed 15 minutes after the countdown began, which makes the card
// show the same time left and the same fill every time. The end time it shows is the
// server's, which is the time the run began plus 45 minutes. Run them when the card's look
// changes, look at the pictures, and commit them.
import { join } from "node:path";
import { REPO_ROOT } from "./constants";
import { expect, test } from "./fixtures";

const MINUTE = 60_000;
const SCREENSHOTS = join(REPO_ROOT, "docs", "screenshots");
/** Space around the cards in the picture, in pixels. */
const MARGIN = 12;

// Twice the pixels, so that the picture stays sharp on a high-resolution screen.
test.use({ colorScheme: "light", deviceScaleFactor: 2 });

test("pill", async ({ page, openDashboard, state, ws }) => {
  const { strict } = state.timers;
  await ws.callService("number", "set_value", { value: 45 }, { entity_id: strict.run_for });
  const began = (await ws.state(strict.ends_at))?.attributes["started_at"];
  expect(typeof began, "Ends at should say when the countdown began").toBe("string");
  await openDashboard(page, "screenshots");

  await page.clock.setFixedTime(Date.parse(String(began)) + 15 * MINUTE);

  const cards = page.locator("timerify-card");
  await expect(cards).toHaveCount(2);
  await expect(cards.first().getByText("30:00", { exact: true })).toBeVisible();
  const boxes = await Promise.all((await cards.all()).map((card) => card.boundingBox()));
  const found = boxes.filter((box) => box !== null);
  expect(found).toHaveLength(2);
  const left = Math.min(...found.map((box) => box.x)) - MARGIN;
  const top = Math.min(...found.map((box) => box.y)) - MARGIN;
  const right = Math.max(...found.map((box) => box.x + box.width)) + MARGIN;
  const bottom = Math.max(...found.map((box) => box.y + box.height)) + MARGIN;
  await page.screenshot({
    path: join(SCREENSHOTS, "card-pill.png"),
    clip: { x: left, y: top, width: right - left, height: bottom - top },
  });
});
