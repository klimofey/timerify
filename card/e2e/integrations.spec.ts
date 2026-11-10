// Where a user finds Timerify in the settings of a real Home Assistant: on the Integrations
// tab, which leads to the page of the integration, where a timer is configured and its
// schedule intervals are added. That tab lists devices, hubs and services and no helpers,
// so the type in Timerify's manifest decides whether it is there at all.
// View "popup": any view does; the tests only need an administrator who is logged in.
import type { APIRequestContext } from "@playwright/test";
import type { E2EState, TimerEntities } from "./constants";
import { expect, test } from "./fixtures";
import type { HassWs } from "./ws";

const INTEGRATION_PAGE = "/config/integrations/integration/timerify";
const INTERVAL_FLOW = "/api/config/config_entries/subentries/flow";

/** A step of a flow, as Home Assistant's HTTP API answers it. */
interface FlowStep {
  type: string;
  flow_id: string;
  title?: string;
}

/** A schedule interval of a timer, as `config_entries/subentries/list` lists it. */
interface Subentry {
  subentry_id: string;
  title: string;
}

/**
 * Adds a schedule interval to the timer with the calls the form of the page makes, at the
 * time of the fixture's own interval, which is never open in a run. Returns the title
 * Timerify gave it.
 */
async function addInterval(
  request: APIRequestContext,
  state: E2EState,
  timer: TimerEntities,
): Promise<string> {
  const headers = { Authorization: `Bearer ${state.users.admin.token}` };
  const post = async (path: string, data: Record<string, unknown>): Promise<FlowStep> => {
    const response = await request.post(path, { headers, data });
    expect(response.ok(), `${path} should answer`).toBe(true);
    return (await response.json()) as FlowStep;
  };
  const form = await post(INTERVAL_FLOW, { handler: [timer.entry_id, "interval"] });
  expect(form.type).toBe("form");
  const { weekday, start, end } = state.interval;
  const created = await post(`${INTERVAL_FLOW}/${form.flow_id}`, {
    days: "weekdays",
    weekdays: [weekday],
    start: `${start}:00`,
    end: `${end}:00`,
  });
  expect(created.type).toBe("create_entry");
  expect(created.title).toBeTruthy();
  return created.title as string;
}

/** Removes the schedule intervals of the timer that have the title. */
async function removeIntervals(ws: HassWs, timer: TimerEntities, title: string): Promise<void> {
  const entry = { entry_id: timer.entry_id };
  const intervals = await ws.command<Subentry[]>("config_entries/subentries/list", entry);
  for (const interval of intervals.filter((found) => found.title === title)) {
    const subentry = { ...entry, subentry_id: interval.subentry_id };
    await ws.command("config_entries/subentries/delete", subentry);
  }
}

test.describe("Timerify in the settings", () => {
  test.beforeEach(async ({ page, openDashboard }) => {
    await openDashboard(page, "popup");
  });

  test("an admin finds Timerify on the Integrations tab and opens its timers", async ({
    page,
    state,
  }) => {
    await page.goto("/config/integrations/dashboard");

    const card = page.locator("ha-integration-card").filter({ hasText: "Timerify" });
    await expect(card).toBeVisible();
    await card.locator(`a[href="${INTEGRATION_PAGE}"]`).first().click();

    await expect(page).toHaveURL(new RegExp(`${INTEGRATION_PAGE}$`));
    // Home Assistant's own page of the integration, with a row for each timer.
    const { strict, loose } = state.timers;
    for (const entities of [strict, loose]) {
      await expect(
        page.locator(`ha-config-entry-row[data-entry-id="${entities.entry_id}"]`),
      ).toBeVisible();
    }
  });

  test("the page of the integration shows a new schedule interval without a reload", async ({
    page,
    request,
    state,
    ws,
  }) => {
    const { loose } = state.timers;
    await page.goto(INTEGRATION_PAGE);
    const timer = page.locator(`ha-config-entry-row[data-entry-id="${loose.entry_id}"]`);
    const intervals = timer.locator("ha-config-sub-entry-row");
    await expect(timer).toBeVisible();
    await expect(intervals).toHaveCount(0);

    const title = await addInterval(request, state, loose);
    try {
      await expect(intervals.filter({ hasText: title })).toBeVisible();
    } finally {
      await removeIntervals(ws, loose, title);
    }
    await expect(intervals).toHaveCount(0);
  });
});
