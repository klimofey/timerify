// The fixtures of the end-to-end tests: the state `scripts.e2e.hass up` left, a connection
// to Home Assistant, a login that works with the frontend's service worker, and a reset of
// the fixture before every test.
import { readFile } from "node:fs/promises";
import { expect, test as base, type Page } from "@playwright/test";
import { STATE_FILE, type E2EState, type TimerEntities, type UserName } from "./constants";
import { hassWs, type HassWs } from "./ws";

export interface OpenDashboardOptions {
  /** Who logs in; the administrator by default. */
  user?: UserName;
}

/** Logs in at the login page, as a user does, and shows the view of the fixture's dashboard. */
export type OpenDashboard = (
  page: Page,
  view: string,
  options?: OpenDashboardOptions,
) => Promise<void>;

/** A pending command, as the `commands` attribute of a "Next command" sensor lists it. */
export interface CommandRow {
  id: string;
  action: string;
}

/** The pending commands of a timer, in the order its "Next command" sensor lists them. */
export async function commandsOf(ws: HassWs, timer: TimerEntities): Promise<CommandRow[]> {
  const commands = (await ws.state(timer.next_command))?.attributes["commands"];
  return Array.isArray(commands) ? (commands as CommandRow[]) : [];
}

/**
 * Puts the fixture back as `scripts.e2e.hass up` made it, whatever the last test did: both
 * numbers stopped, every command cancelled and the fixture's command added again, the
 * interval switched on. Returns when Home Assistant shows it.
 */
export async function resetFixture(state: E2EState, ws: HassWs): Promise<void> {
  const { strict, loose } = state.timers;
  const timer = (entities: TimerEntities) => ({ entity_id: entities.run_for });
  for (const entities of [strict, loose]) {
    await ws.callService("number", "set_value", { value: 0 }, timer(entities));
    for (const command of await commandsOf(ws, entities)) {
      const data = { command_id: command.id };
      await ws.callService("timerify", "cancel_command", data, timer(entities));
    }
  }
  await ws.callService("timerify", "add_command", state.command, timer(loose));
  await ws.callService("switch", "turn_on", {}, { entity_id: state.interval.switch });

  const valueOf = async (entityId: string) => (await ws.state(entityId))?.state;
  await expect
    .poll(
      async () => ({
        strict: Number(await valueOf(strict.run_for)),
        strictTarget: await valueOf(strict.target),
        strictCommands: (await commandsOf(ws, strict)).length,
        loose: Number(await valueOf(loose.run_for)),
        looseTarget: await valueOf(loose.target),
        looseCommands: (await commandsOf(ws, loose)).length,
        interval: await valueOf(state.interval.switch),
      }),
      { message: "Home Assistant should show the fixture, restored" },
    )
    .toEqual({
      strict: 0,
      strictTarget: "off",
      strictCommands: 0,
      loose: 0,
      looseTarget: "off",
      looseCommands: 1,
      interval: "on",
    });
}

/**
 * Gets the frontend's service worker in control, with its cache filled, and returns when the
 * page can be reloaded for good.
 *
 * On the first visit the frontend registers the worker and reloads the page itself when the
 * worker takes control. That first load under the worker has a cold cache, and a card module
 * can then run before the frontend is ready for it: the card is not defined, and the
 * dashboard shows a configuration error. Every load after it has the cache filled and shows
 * the card. So: wait for the load the worker serves (a reload of our own would race the
 * frontend's), and for the frontend to have started on it.
 */
async function primeServiceWorker(page: Page): Promise<void> {
  const servedByWorker = () =>
    page.evaluate(() =>
      performance
        .getEntriesByType("navigation")
        .some((entry) => (entry as PerformanceNavigationTiming).workerStart > 0),
    );
  await expect
    .poll(
      // The frontend's own reload can destroy the page this asks: that is "not yet".
      () => servedByWorker().catch(() => false),
      { message: "the service worker should serve the page" },
    )
    .toBe(true);
  await expect(page.locator("ha-sidebar")).toBeVisible();
}

function dashboardOpener(state: E2EState): OpenDashboard {
  return async (page, view, { user = "admin" } = {}) => {
    const account = state.users[user];
    const path = `/${state.dashboard}/${view}`;
    await page.goto(path);
    await page.locator('input[name="username"]').fill(account.username);
    const password = page.locator('input[name="password"]');
    await password.fill(account.password);
    await password.press("Enter");
    await page.waitForURL((url) => url.pathname === path);
    await primeServiceWorker(page);
    await page.reload({ waitUntil: "load" });
    await expect(page.locator("timerify-card ha-card").first()).toBeVisible();
  };
}

export const test = base.extend<
  { ws: HassWs; openDashboard: OpenDashboard; freshFixture: void },
  { state: E2EState }
>({
  state: [
    async ({}, use) => {
      await use(JSON.parse(await readFile(STATE_FILE, "utf8")) as E2EState);
    },
    { scope: "worker" },
  ],
  ws: async ({ state }, use) => {
    const ws = await hassWs(state);
    await use(ws);
    ws.close();
  },
  openDashboard: async ({ state }, use) => {
    await use(dashboardOpener(state));
  },
  // Automatic: every test starts from the fixture, and creates its own starting point from it.
  freshFixture: [
    async ({ state, ws }, use) => {
      await resetFixture(state, ws);
      await use();
    },
    { auto: true },
  ],
});

export { expect };
