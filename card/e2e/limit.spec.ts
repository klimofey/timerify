// A device left on under a limit in a real Home Assistant: the card says the time the device
// is turned off at the latest, not a time left, and time added to it gives an ordinary
// countdown. The limit is made by Timerify, from a switch that someone turns on, and read back
// from Home Assistant's own states: what the card says is compared with the end Timerify gave.
// View "limit": the pill and the round tile of the loose timer that has a limit of two hours.
import type { Locator, Page } from "@playwright/test";
import { clockText } from "./clock";
import type { TimerEntities } from "./constants";
import { expect, test } from "./fixtures";
import { tap } from "./press";
import { isReady } from "./ready";
import { stringsIn } from "./strings";
import type { HassState, HassWs } from "./ws";

const english = await stringsIn("en");

const SECOND = 1000;
const MINUTE = 60 * SECOND;
/** The limit of the fixture's timer, `LIMIT_MINUTES` of `scripts.e2e.hass`. */
const LIMIT_MINUTES = 120;

/** The pill and the round tile of the view, which show the same timer. */
function cardsOf(page: Page): { pill: Locator; round: Locator } {
  const cards = page.locator("timerify-card");
  return {
    pill: cards.filter({ has: page.locator("ha-card.pill") }),
    round: cards.filter({ has: page.locator("ha-card.round") }),
  };
}

/** What the card says of a limit that turns the device off at `end`. */
const latestText = (end: number) =>
  english.card_until_latest.replace("{time}", clockText("en", "h12", end));
/** What the card says of a countdown that ends at `end`. */
const untilText = (end: number) =>
  english.card_until.replace("{time}", clockText("en", "h12", end));

/** The moment "Ends at" holds, in milliseconds; the test fails if it holds none. */
async function endOf(ws: HassWs, timer: TimerEntities): Promise<number> {
  const end = Date.parse(String((await ws.state(timer.ends_at))?.state));
  expect(end, "Ends at should hold a moment").not.toBeNaN();
  return end;
}

/**
 * Someone turns the device on by hand, somewhere else, and Timerify gives it a limit:
 * returns when "Ends at" says so, with the moment of the limit.
 */
async function leaveOn(ws: HassWs, timer: TimerEntities): Promise<number> {
  await ws.callService("switch", "turn_on", {}, { entity_id: timer.target });
  const limitOf = async (): Promise<unknown> => (await ws.state(timer.ends_at))?.attributes["limit"];
  await expect.poll(limitOf, { message: "Ends at should say it is a limit" }).toBe(true);
  return endOf(ws, timer);
}

const attributesOf = async (ws: HassWs, entityId: string): Promise<HassState["attributes"]> =>
  (await ws.state(entityId))?.attributes ?? {};

test.describe("a device left on under a limit", () => {
  test.beforeEach(async ({ page, openDashboard }) => {
    await openDashboard(page, "limit");
    await expect(page.locator("timerify-card")).toHaveCount(2);
  });

  test("the pill says the time the device is turned off at the latest", async ({
    page,
    state,
    ws,
  }) => {
    const { limited } = state.timers;
    const { pill } = cardsOf(page);
    await isReady(pill);

    const limit = await leaveOn(ws, limited);

    // The limit is the whole limit from the moment the device was seen on. Both moments are
    // the server's, so the clock of the host, which may be seconds apart, is not in it; the
    // margin is the time Timerify takes to hear of the device.
    const seenOn = Date.parse(String((await ws.state(limited.target))?.last_changed));
    expect(Math.abs(limit - seenOn - LIMIT_MINUTES * MINUTE)).toBeLessThan(2 * SECOND);
    await expect(pill.getByText(latestText(limit), { exact: true })).toBeVisible();
    // Nobody chose a time, so there is none left to show or to count, and Run for says 0.
    await expect(pill.getByText(/^\d+:\d\d$/)).toHaveCount(0);
    await expect(pill.getByText(/^until /)).toHaveCount(0);
    expect((await ws.state(limited.run_for))?.state).toBe("0");
  });

  test("the round tile shows the icon and a full ring, and says the limit to a screen reader", async ({
    page,
    state,
    ws,
  }) => {
    const { limited } = state.timers;
    const { round } = cardsOf(page);
    await isReady(round);

    const limit = await leaveOn(ws, limited);

    const button = round.getByRole("button", { name: new RegExp(`${latestText(limit)}$`) });
    await expect(button).toBeVisible();
    await expect(round.locator(".centre .icon")).toBeVisible();
    await expect(round.locator(".time")).toHaveCount(0);
    await expect(round.locator("circle.progress")).toHaveAttribute("stroke-dashoffset", "0");
  });

  test("the pop-up says the limit, and time added to it gives an ordinary countdown", async ({
    page,
    state,
    ws,
  }) => {
    const { limited } = state.timers;
    const { pill } = cardsOf(page);
    await isReady(pill);
    const limit = await leaveOn(ws, limited);
    await expect(pill.getByText(latestText(limit), { exact: true })).toBeVisible();

    await tap(page, pill);
    const dialog = pill.locator("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText(latestText(limit), { exact: true })).toBeVisible();
    await dialog.getByRole("button", { name: "Add 5 min", exact: true }).click();

    // Timerify adds the time to the limit, and the result is a countdown that someone chose.
    await expect
      .poll(async () => (await attributesOf(ws, limited.ends_at))["limit"])
      .toBe(false);
    const end = await endOf(ws, limited);
    expect(end).toBe(limit + 5 * MINUTE);
    // The pop-up is part of the card, so the pill's own words are told from it by their place.
    await expect(pill.locator(".status").getByText(untilText(end), { exact: true })).toBeVisible();
    await expect(dialog.getByText(untilText(end), { exact: true })).toBeVisible();
    await expect(dialog.getByText(/^\d+:\d\d(:\d\d)?$/)).toBeVisible();
    await expect(pill.getByText(/at the latest/)).toHaveCount(0);
    expect(Number((await ws.state(limited.run_for))?.state)).toBeGreaterThan(LIMIT_MINUTES);
  });

  test("stops with the pop-up's Stop, and the device turns off", async ({ page, state, ws }) => {
    const { limited } = state.timers;
    const { pill } = cardsOf(page);
    await isReady(pill);
    const limit = await leaveOn(ws, limited);
    await tap(page, pill);
    const dialog = pill.locator("dialog");
    await expect(dialog.getByText(latestText(limit), { exact: true })).toBeVisible();

    await dialog.getByRole("button", { name: "Stop", exact: true }).click();

    await expect.poll(async () => (await ws.state(limited.target))?.state).toBe("off");
    expect((await ws.state(limited.ends_at))?.state).toBe("unknown");
    await expect(dialog.getByText(/at the latest/)).toHaveCount(0);
    await expect(pill.getByText(/at the latest/)).toHaveCount(0);
  });

  test("a device turned off by hand ends the limit", async ({ page, state, ws }) => {
    const { limited } = state.timers;
    const { pill } = cardsOf(page);
    await isReady(pill);
    const limit = await leaveOn(ws, limited);
    await expect(pill.getByText(latestText(limit), { exact: true })).toBeVisible();

    await ws.callService("switch", "turn_off", {}, { entity_id: limited.target });

    await expect.poll(async () => (await ws.state(limited.ends_at))?.state).toBe("unknown");
    await expect(pill.getByText(/at the latest/)).toHaveCount(0);
  });
});
