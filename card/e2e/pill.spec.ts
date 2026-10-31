// The pill in a real Home Assistant: it counts down a timer that was started somewhere else,
// adds the chip's minutes without opening the pop-up, and carries on to the same end when
// Home Assistant restarts. View "pill": one pill card on the strict timer, with a chip of 15.
import { expect, test } from "./fixtures";
import { runHarness } from "./harness";
import { hassWs } from "./ws";

const CHIP_MINUTES = 15;
const MINUTE = 60_000;

/**
 * The clock time the user's profile shows for a moment: the browser's time zone
 * (America/New_York, the config's) and English, which counts twelve hours.
 */
function clockTime(moment: number): string {
  return new Intl.DateTimeFormat("en", {
    timeZone: "America/New_York",
    hour: "numeric",
    minute: "2-digit",
    hourCycle: "h12",
  })
    .format(moment)
    .replace(/\s+/g, " ");
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
    await expect(
      card.getByText(`until ${clockTime(Date.parse(ends ?? ""))}`, { exact: true }),
    ).toBeVisible();
    // It goes on by itself, a second at a time: nothing but the clock changes.
    const seconds = async () => {
      const [minutes = 0, rest = 0] = ((await timeLeft.textContent()) ?? "").split(":").map(Number);
      return minutes * 60 + rest;
    };
    const first = await seconds();
    await expect.poll(seconds).toBeLessThan(first);
  });

  test("adds the chip's minutes", async ({ page, state, ws }) => {
    const { strict } = state.timers;
    const card = page.locator("timerify-card");
    await ws.callService("number", "set_value", { value: 3 }, { entity_id: strict.run_for });
    await expect(card.getByText(/^2:5\d$/)).toBeVisible();

    // The whole pill is a button too, and its name holds the chip's: ask for the chip's alone.
    const chip = card.getByRole("button", { name: `Add ${CHIP_MINUTES} min`, exact: true });
    await chip.click();

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
    expect(Date.parse(ends), "Ends at should hold the end of the countdown").not.toBeNaN();
    const until = card.getByText(`until ${clockTime(Date.parse(ends))}`, { exact: true });
    await expect(until).toBeVisible();

    await runHarness("restart");

    // The countdown is on the card again, to the end Timerify kept.
    await expect(timeLeft).toBeVisible({ timeout: 120_000 });
    await expect(until).toBeVisible();
    const afterwards = await hassWs(state);
    try {
      expect((await afterwards.state(strict.ends_at))?.state).toBe(ends);
      // And the page is connected to the restarted Home Assistant, not showing what it saw
      // before: when the end moves, the card follows.
      const timer = { entity_id: strict.run_for };
      await afterwards.callService("timerify", "add_time", { minutes: 1 }, timer);
      await expect(
        card.getByText(`until ${clockTime(Date.parse(ends) + MINUTE)}`, { exact: true }),
      ).toBeVisible({ timeout: 120_000 });
    } finally {
      afterwards.close();
    }
    // Neither the card's own warning nor the dashboard's error card was left behind.
    await expect(card.locator('[role="alert"]')).toHaveCount(0);
    await expect(page.locator("hui-error-card")).toHaveCount(0);
  });
});
