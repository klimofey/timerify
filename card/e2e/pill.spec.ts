// The pill in a real Home Assistant: it counts down a timer that was started somewhere else,
// opens its pop-up from a tap anywhere on it (its border too) but the chip, adds the chip's
// minutes without opening the pop-up, and carries on to the same end when Home Assistant
// restarts.
// View "pill": one pill card on the strict timer, with a chip of 15.
import type { Locator } from "@playwright/test";
import { expect, test } from "./fixtures";
import { runHarness } from "./harness";
import { tapBorder } from "./press";
import { hassWs } from "./ws";

const NAME = "Smoke boiler";
const CHIP_MINUTES = 15;
const MINUTE = 60_000;
/** The browser's time zone, which the user's profile follows by default (the config's). */
const ZONE = "America/New_York";

const dayIn = (moment: number) =>
  new Intl.DateTimeFormat("en-CA", { timeZone: ZONE }).format(moment);

/**
 * What the pill says of the end of a countdown, written as the card writes it at this
 * moment: English, which counts twelve hours, and the short weekday when the end falls on
 * another day than today, which it does for the last minutes before midnight.
 */
function untilText(end: number): string {
  const options: Intl.DateTimeFormatOptions = {
    timeZone: ZONE,
    hour: "numeric",
    minute: "2-digit",
    hourCycle: "h12",
  };
  if (dayIn(end) !== dayIn(Date.now())) {
    options.weekday = "short";
  }
  return `until ${new Intl.DateTimeFormat("en", options).format(end).replace(/\s+/g, " ")}`;
}

/**
 * Waits for the card to say when the countdown ends. The text is worked out again at every
 * attempt, so a midnight that passes while the test waits does not leave it asking for the
 * words of the day before.
 */
async function expectUntil(card: Locator, end: number, timeout = 10_000): Promise<void> {
  await expect(async () => {
    await expect(card.getByText(untilText(end), { exact: true })).toBeVisible({ timeout: 1_000 });
  }).toPass({ timeout });
}

test.describe("the pill in Home Assistant", () => {
  test.beforeEach(async ({ page, openDashboard }) => {
    await openDashboard(page, "pill");
  });

  test("counts down a timer started elsewhere", async ({ page, state, ws }) => {
    const { strict } = state.timers;
    const card = page.locator("timerify-card");
    const timeLeft = card.getByText(/^\d+:\d\d$/);
    await expect(timeLeft).toHaveCount(0);

    await ws.callService("number", "set_value", { value: 3 }, { entity_id: strict.run_for });

    await expect(timeLeft).toHaveText(/^2:5\d$/);
    const ends = (await ws.state(strict.ends_at))?.state;
    expect(ends, "Ends at should hold the end of the countdown").toBeDefined();
    await expectUntil(card, Date.parse(ends ?? ""));
    // It goes on by itself, a second at a time: nothing but the clock changes.
    const seconds = async () => {
      const [minutes = 0, rest = 0] = ((await timeLeft.textContent()) ?? "").split(":").map(Number);
      return minutes * 60 + rest;
    };
    const first = await seconds();
    await expect.poll(seconds).toBeLessThan(first);
  });

  test("opens the pop-up from a tap anywhere on the pill but the chip", async ({ page }) => {
    const card = page.locator("timerify-card");
    const dialog = card.locator("dialog");
    await expect(dialog).toBeHidden();

    // The name and the icon let a press through to the button under them, which is why
    // Playwright's own click on them is refused (it finds the button in the way): tap where
    // a finger or a mouse would, at the middle of each.
    for (const part of [card.getByText(NAME, { exact: true }), card.locator(".icon")]) {
      const box = await part.boundingBox();
      if (box === null) {
        throw new Error("The part of the pill should be on the page");
      }
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
      await expect(dialog).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(dialog).toBeHidden();
    }
  });

  test("opens the pop-up from a tap on the border of the card", async ({ page }) => {
    await tapBorder(page, page.locator("timerify-card"));
  });

  test("adds the chip's minutes", async ({ page, state, ws }) => {
    const { strict } = state.timers;
    const card = page.locator("timerify-card");
    await ws.callService("number", "set_value", { value: 3 }, { entity_id: strict.run_for });
    await expect(card.getByText(/^2:5\d$/)).toBeVisible();

    await card.getByRole("button", { name: `Add ${CHIP_MINUTES} min` }).click();

    await expect.poll(async () => (await ws.state(strict.run_for))?.state).toBe("18");
    await expect(card.getByText(/^1[78]:\d\d$/)).toBeVisible();
    // The chip is not a tap of the card: the pop-up stays shut.
    await expect(card.locator("dialog")).toBeHidden();
  });

  test("keeps counting to the same end across a restart of Home Assistant", async ({
    page,
    state,
    ws,
  }) => {
    // A restart takes tens of seconds, and the countdown must outlast it.
    test.setTimeout(300_000);
    const { strict } = state.timers;
    const card = page.locator("timerify-card");
    const timeLeft = card.getByText(/^\d+:\d\d$/);
    await ws.callService("number", "set_value", { value: 10 }, { entity_id: strict.run_for });
    await expect(timeLeft).toBeVisible();
    const ends = (await ws.state(strict.ends_at))?.state ?? "";
    const end = Date.parse(ends);
    expect(end, "Ends at should hold the end of the countdown").not.toBeNaN();
    await expectUntil(card, end);

    await runHarness("restart");

    // The countdown is on the card again, to the end Timerify kept.
    await expect(timeLeft).toBeVisible({ timeout: 120_000 });
    await expectUntil(card, end);
    const afterwards = await hassWs(state);
    try {
      expect((await afterwards.state(strict.ends_at))?.state).toBe(ends);
      // And the page is connected to the restarted Home Assistant, not showing what it saw
      // before: when the end moves, the card follows.
      const timer = { entity_id: strict.run_for };
      await afterwards.callService("timerify", "add_time", { minutes: 1 }, timer);
      await expectUntil(card, end + MINUTE, 120_000);
    } finally {
      afterwards.close();
    }
    // Neither the card's own warning nor the dashboard's error card was left behind.
    await expect(card.locator('[role="alert"]')).toHaveCount(0);
    await expect(page.locator("hui-error-card")).toHaveCount(0);
  });
});
