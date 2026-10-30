// The reset that every test starts with must undo whatever a test did to the fixture: a
// test that finds a timer left running, a command missing or an interval off cannot be
// trusted. The first test does all of that at once.
import { commandsOf, expect, resetFixture, test } from "./fixtures";
import { hassWs } from "./ws";

test("the reset puts back everything a test changed", async ({ state, ws }) => {
  const { strict, loose } = state.timers;
  const timer = (entities: { run_for: string }) => ({ entity_id: entities.run_for });
  const valueOf = async (entityId: string) => (await ws.state(entityId))?.state;

  // The strict timer runs and has a command, the loose one runs and has none left, and the
  // interval is off.
  await ws.callService("number", "set_value", { value: 5 }, timer(strict));
  await ws.callService("timerify", "add_command", { action: "off", delay: 3 }, timer(strict));
  await ws.callService("number", "set_value", { value: 7 }, timer(loose));
  for (const command of await commandsOf(ws, loose)) {
    await ws.callService("timerify", "cancel_command", { command_id: command.id }, timer(loose));
  }
  await ws.callService("switch", "turn_off", {}, { entity_id: state.interval.switch });
  await expect.poll(() => valueOf(strict.target)).toBe("on");
  await expect.poll(() => valueOf(state.interval.switch)).toBe("off");

  await resetFixture(state, ws);

  const actions = (await commandsOf(ws, loose)).map((command) => command.action);
  expect(actions).toEqual([state.command.action]);
  expect(await valueOf(strict.target)).toBe("off");
  expect(await valueOf(loose.target)).toBe("off");
  expect(await valueOf(state.interval.switch)).toBe("on");
});

test("a view of the dashboard can be read back", async ({ state, ws }) => {
  const view = await ws.config("dialog");

  expect(view["cards"]).toEqual([
    { type: "custom:timerify-card", entity: state.timers.strict.run_for, layout: "pill" },
  ]);
});

test("a user who is not an administrator gets to the dashboard too", async ({
  page,
  openDashboard,
  state,
}) => {
  await openDashboard(page, "dialog", { user: "viewer" });
  await expect(page.locator("timerify-card").getByText("Smoke boiler")).toBeVisible();

  const viewer = await hassWs(state, "viewer");
  try {
    expect((await viewer.state(state.timers.strict.target))?.state).toBe("off");
  } finally {
    viewer.close();
  }
});
