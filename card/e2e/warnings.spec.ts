// What the card says when it cannot work, in a real Home Assistant: a timer whose "Ends at"
// sensor is disabled in the registry has no countdown to read, and the card tells the user
// which sensor to enable instead of standing there dead.
// View "disabled": the pill of the timer whose "Ends at" sensor `scripts.e2e.hass` disabled.
// The sensor stays disabled for the whole run: enabling an entity makes Home Assistant reload
// its entry some time later, which would reach into the tests after this one. The other
// warnings (a user who may not see the timer, a disabled "Next command") are told by the unit
// tests, since no user of the fixture lacks permissions and the fixture's pop-ups are
// those of the other timers.
import { expect, test } from "./fixtures";
import { stringsIn } from "./strings";

test.describe("a timer whose Ends at sensor is disabled", () => {
  test.beforeEach(async ({ page, openDashboard, state, ws }) => {
    // The test would prove nothing for a sensor that has a state.
    expect(await ws.state(state.timers.disabled.ends_at)).toBeUndefined();
    await openDashboard(page, "disabled");
    await expect(page.locator("timerify-card")).toHaveCount(1);
  });

  test("tells the user which sensor to enable", async ({ page, state }) => {
    const english = await stringsIn("en");
    const { ends_at: sensor } = state.timers.disabled;

    const warning = page.locator("timerify-card").getByRole("alert");

    await expect(warning).toHaveText(english.card_ends_at_disabled.replace("{sensor}", sensor));
    // Nothing to press: the card is a warning, not a timer.
    await expect(page.locator("timerify-card dialog")).toHaveCount(0);
    await expect(page.locator("timerify-card").getByRole("button")).toHaveCount(0);
  });

  test.describe("in Russian", () => {
    test.use({ locale: "ru-RU" });

    test("tells it in Russian", async ({ page, state }) => {
      const russian = await stringsIn("ru");
      const { ends_at: sensor } = state.timers.disabled;

      const warning = page.locator("timerify-card").getByRole("alert");

      await expect(warning).toHaveText(russian.card_ends_at_disabled.replace("{sensor}", sensor));
    });
  });
});
