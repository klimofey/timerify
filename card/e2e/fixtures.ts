// The fixtures of the end-to-end tests: the state `scripts.e2e.hass up` left, a connection
// to Home Assistant, a login that works with the frontend's service worker, and a reset of
// the fixture before every test.
import { readFile } from "node:fs/promises";
import { isDeepStrictEqual } from "node:util";
import { expect, test as base, type Page } from "@playwright/test";
import { STATE_FILE, type E2EState, type TimerEntities, type UserName } from "./constants";
import { hassWs, type HassWs } from "./ws";

export interface OpenDashboardOptions {
  /** Who logs in; the administrator by default. */
  user?: UserName;
  /**
   * Whether to reload the page once more when the frontend's service worker serves it, which
   * is what gets a card that Home Assistant loads with `add_extra_js_url` onto the page
   * (see `primeServiceWorker`). Pass `false` to stay on the first load the worker serves,
   * the page a user's very first visit ends on; it returns when the frontend has started
   * there, whether or not the card is on it. True by default.
   */
  reload?: boolean;
  /**
   * Whether the view has no card of Timerify yet, because the test adds one: the page is then
   * handed over once the card's element is defined, not once a card is shown. False by default.
   */
  emptyView?: boolean;
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
 * interval switched on, the dashboard saved as it was. Returns when Home Assistant shows it.
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
  const dashboardIsRestored = async () =>
    isDeepStrictEqual(await ws.dashboard(), state.dashboard_config);
  if (!(await dashboardIsRestored())) {
    await ws.saveDashboard(state.dashboard_config);
  }

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
        dashboard: await dashboardIsRestored(),
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
      dashboard: true,
    });
}

/**
 * How long the frontend may take to get its service worker in control on a first visit, in
 * milliseconds.
 */
const WORKER_WAIT = 40_000;

/**
 * Gets the frontend's service worker in control, and returns when the frontend has started on
 * the page the worker serves. A page of ours can then be reloaded for good.
 *
 * On the first visit the frontend registers the worker and reloads the page itself when the
 * worker takes control. That first load under the worker can lose the card: Home Assistant
 * 2026.10 starts the app and the modules added with `add_extra_js_url` (how Timerify loads
 * its card) as two independent `import()` calls, and the worker serves the large app file
 * after the small card module. The card defines its element first; the app then installs a
 * scoped custom element registry that knows nothing of it, so the dashboard shows "Custom
 * element doesn't exist: timerify-card" until the next load. Every load after it takes the
 * app file from the browser's cache, and shows the card. This is a frontend bug,
 * https://github.com/home-assistant/frontend/issues/53890, fixed by
 * https://github.com/home-assistant/frontend/pull/54444 in frontend 20261028.0 and later,
 * which Home Assistant 2026.11 is expected to carry. The investigation is in
 * docs/research/2026-10-31-card-first-load.md; the test that shows it is first-load.spec.ts.
 *
 * So: wait for the load the worker serves (a reload of our own would race the frontend's),
 * and for the frontend to have started on it. The frontend reloads when the worker takes
 * control, which is after the worker has precached the frontend: under two seconds on a quiet
 * machine, and measured at twenty on a busy one, so the wait is long, and never ends in a
 * reload of ours.
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
      { message: "the service worker should serve the page", timeout: WORKER_WAIT },
    )
    .toBe(true);
  await expect(page.locator("ha-sidebar")).toBeVisible();
}

function dashboardOpener(state: E2EState): OpenDashboard {
  return async (page, view, { user = "admin", reload = true, emptyView = false } = {}) => {
    const account = state.users[user];
    const path = `/${state.dashboard}/${view}`;
    await page.goto(path);
    await page.locator('input[name="username"]').fill(account.username);
    const password = page.locator('input[name="password"]');
    await password.fill(account.password);
    await password.press("Enter");
    await page.waitForURL((url) => url.pathname === path);
    await primeServiceWorker(page);
    if (!reload) {
      return;
    }
    await page.reload({ waitUntil: "load" });
    if (emptyView) {
      await expect
        .poll(() => page.evaluate(() => customElements.get("timerify-card") !== undefined), {
          message: "the card's element should be defined",
        })
        .toBe(true);
    } else {
      await expect(page.locator("timerify-card ha-card").first()).toBeVisible();
    }
    // The frontend's launch screen covers the whole page until it has faded out, and a press
    // made before that lands on it, not on the card: Playwright's own click waits for what it
    // presses to be reachable, a press at a point of the page (`press.ts`) does not.
    await expect(page.locator("#ha-launch-screen")).toHaveCount(0);
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
