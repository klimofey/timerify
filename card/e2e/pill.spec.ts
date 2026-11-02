// The pill in a real Home Assistant: it counts down a timer that was started somewhere else,
// opens its pop-up from a tap anywhere on it (its border too) but the chip, adds the chip's
// minutes without opening the pop-up, and carries on to the same end when Home Assistant
// restarts, and counts by Home Assistant's clock on a browser whose own is wrong. View "pill":
// one pill card on the strict timer, with a chip of 15. A pill whose double tap runs the timer
// is in the view "presses", and one with a Turn off button, on the loose timer, in "turn-off".
import type { Locator, Page } from "@playwright/test";
import { STRICT_NAME } from "./constants";
import { expect, test } from "./fixtures";
import { runHarness } from "./harness";
import { tabToButton } from "./focus";
import { doubleTap, tap, tapBorder } from "./press";
import { isReady } from "./ready";
import { hassWs } from "./ws";

const CHIP_MINUTES = 15;
/** The strict timer's default duration, which a run with no duration takes. */
const DEFAULT_MINUTES = "30";
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

/** The pill among the cards of a view that has another layout too. */
const pillOf = (page: Page) =>
  page.locator("timerify-card").filter({ has: page.locator("ha-card.pill") });

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

  test("leaves its content as it was when it has no Turn off button", async ({ page }) => {
    // The content of a card with the button is the container its form follows (sizes.spec.ts);
    // that of a card without it is no container, whatever page it is on.
    const content = pillOf(page).locator(".content");
    await expect(content).toBeVisible();
    expect(await content.evaluate((element) => getComputedStyle(element).containerType)).toBe(
      "normal",
    );
  });

  test("is not zoomed by a double tap, which Safari does unless the body says otherwise", async ({
    page,
  }) => {
    // Chromium has no double-tap zoom, so this reads what the browser makes of the rule that
    // keeps WebKit from it: panning and pinch-zoom stay, the double tap is the card's.
    const body = pillOf(page).locator(".body");
    await expect(body).toBeVisible();
    expect(await body.evaluate((element) => getComputedStyle(element).touchAction)).toBe(
      "manipulation",
    );
  });

  test("opens the pop-up from a tap anywhere on the pill but the chip", async ({ page }) => {
    const card = page.locator("timerify-card");
    const dialog = card.locator("dialog");
    await expect(dialog).toBeHidden();

    // The name and the icon let a press through to the button under them, which is why
    // Playwright's own click on them is refused (it finds the button in the way): tap where
    // a finger or a mouse would, at the middle of each.
    for (const part of [card.getByText(STRICT_NAME, { exact: true }), card.locator(".icon")]) {
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
    // The frontend announces on the window each change of its connection to Home Assistant,
    // which its own panels listen to. While it is cut off it goes on showing the last states,
    // so the countdown on the card proves nothing of the connection; this does.
    await page.evaluate(() => {
      const seen: string[] = [];
      (window as Window & { connectionStatuses?: string[] }).connectionStatuses = seen;
      window.addEventListener("connection-status", (event) =>
        seen.push((event as CustomEvent<string>).detail),
      );
    });

    await runHarness("restart");

    // The page saw the connection drop with Home Assistant, and is connected again.
    await expect
      .poll(
        async () => {
          const seen = await page.evaluate(
            () => (window as Window & { connectionStatuses?: string[] }).connectionStatuses ?? [],
          );
          return seen.includes("disconnected") && seen.at(-1) === "connected";
        },
        { message: "the page should have lost the connection and got it back", timeout: 120_000 },
      )
      .toBe(true);
    // The countdown is on the card, to the end Timerify kept.
    await expect(timeLeft).toBeVisible();
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

test.describe("the pill on a browser whose clock is wrong", () => {
  test("counts by Home Assistant's clock when the browser's is 5 minutes fast", async ({
    page,
    openDashboard,
    state,
    ws,
  }) => {
    await openDashboard(page, "pill");
    // Playwright's clock stays on for the pages that load next, and replaces what the frontend
    // asks of `performance` while it starts: so the page is opened first, as everywhere, and
    // loaded again on the wrong clock, where the card asks its first question.
    await page.clock.setSystemTime(Date.now() + 5 * MINUTE);
    await page.reload({ waitUntil: "load" });
    const card = page.locator("timerify-card");
    await expect(card.locator("ha-card")).toBeVisible();
    expect(await page.evaluate(() => Date.now())).toBeGreaterThan(Date.now() + 4 * MINUTE);

    const { strict } = state.timers;
    await ws.callService("number", "set_value", { value: 10 }, { entity_id: strict.run_for });

    // Ten minutes by Home Assistant's clock; the browser's would say five.
    await expect(card.getByText(/^(9:5\d|10:00)$/)).toBeVisible();
    const ends = (await ws.state(strict.ends_at))?.state ?? "";
    expect(Date.parse(ends), "Ends at should hold the end of the countdown").not.toBeNaN();
    await expectUntil(card, Date.parse(ends));
  });
});

test.describe("the pill with a double tap", () => {
  test.beforeEach(async ({ page, openDashboard }) => {
    await openDashboard(page, "presses");
    await expect(page.locator("timerify-card")).toHaveCount(2);
  });

  test("runs the timer on a double tap, and opens nothing", async ({ page, state, ws }) => {
    const { strict } = state.timers;
    const pill = pillOf(page);

    await doubleTap(page, pill);

    await expect.poll(async () => (await ws.state(strict.run_for))?.state).toBe(DEFAULT_MINUTES);
    await expect(pill.locator("dialog")).toBeHidden();
  });

  test("opens the pop-up on a single tap, and starts nothing", async ({ page, state, ws }) => {
    const { strict } = state.timers;
    const pill = pillOf(page);

    await tap(page, pill);

    await expect(pill.locator("dialog")).toBeVisible();
    expect((await ws.state(strict.run_for))?.state).toBe("0");
  });
});

test.describe("the pill with a Turn off button", () => {
  test.beforeEach(async ({ page, openDashboard }) => {
    await openDashboard(page, "turn-off");
    await expect(page.locator("timerify-card")).toHaveCount(2);
  });

  test("turns off a boiler that runs with no countdown", async ({ page, state, ws }) => {
    const { loose } = state.timers;
    const pill = pillOf(page);
    const turnOff = pill.getByRole("button", { name: "Turn off", exact: true });
    // Nothing runs, so there is nothing to turn off, once the card has found its timer.
    await isReady(pill);
    await expect(turnOff).toHaveCount(0);

    // Somewhere else the boiler is run with no duration: a loose timer turns its target on,
    // and nothing counts.
    await ws.callService("timerify", "run", {}, { entity_id: loose.run_for });
    await expect.poll(async () => (await ws.state(loose.target))?.state).toBe("on");
    expect((await ws.state(loose.ends_at))?.state).toBe("unknown");
    await expect(turnOff).toBeVisible();

    await turnOff.click();

    await expect.poll(async () => (await ws.state(loose.target))?.state).toBe("off");
    await expect(turnOff).toHaveCount(0);
    // A press on the button is not a tap of the card.
    await expect(pill.locator("dialog")).toBeHidden();
  });

  test("leaves the keyboard on the card when the button goes", async ({ page, state, ws }) => {
    const { loose } = state.timers;
    const pill = pillOf(page);
    const turnOff = pill.getByRole("button", { name: "Turn off", exact: true });
    await isReady(pill);
    await ws.callService("timerify", "run", {}, { entity_id: loose.run_for });
    await expect(turnOff).toBeVisible();

    await tabToButton(page, pill, turnOff);
    await page.keyboard.press("Enter");

    await expect.poll(async () => (await ws.state(loose.target))?.state).toBe("off");
    await expect(turnOff).toHaveCount(0);
    // The next Tab goes on from the card, not from the top of the dashboard.
    await expect(pill.locator(".body")).toBeFocused();
  });
});
