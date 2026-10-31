// What a user sees on the very first visit. The frontend registers its service worker and
// reloads the page when the worker takes control; on Home Assistant 2026.10 the card is
// missing from that first load under the worker (home-assistant/frontend#53890). The
// investigation is in docs/research/2026-10-31-card-first-load.md. Every other file of tests
// reloads once more to get past it: see `primeServiceWorker` in fixtures.ts.
import { expect, test } from "./fixtures";

test("the card is defined and shown on the first load the service worker serves", async ({
  page,
  openDashboard,
}) => {
  await openDashboard(page, "dialog", { reload: false });
  // Everything above this line must hold on every Home Assistant: a failure there is a
  // failure. The user has logged in, the worker serves the page and the frontend has
  // started on it, and the card's module has run, which is what makes the next line a
  // statement about the registry it defined its element on and not about the module.
  await expect
    .poll(
      () =>
        page.evaluate(() => window.customCards?.some((entry) => entry.type === "timerify-card")),
      { message: "the card's module should have run" },
    )
    .toBe(true);

  // From here the test is expected to fail, and only here: the module has run, yet the
  // element is not defined on the registry the frontend uses. When the harness runs a Home
  // Assistant whose frontend has pull request #54444 (20261028.0 or later, which 2026.11 is
  // expected to carry), this passes, and Playwright reports that it was expected to fail:
  // remove this line then, and the reload in the opener with it.
  test.fail(
    true,
    "Known frontend defect home-assistant/frontend#53890, fixed by pull request #54444 in " +
      "frontend 20261028.0 and later, which Home Assistant 2026.11 is expected to carry: a " +
      "module added with add_extra_js_url can run before the frontend installs its scoped " +
      "custom element registry, and the definition is lost.",
  );
  const defined = await page.evaluate(() => customElements.get("timerify-card") !== undefined);
  expect(defined, "timerify-card should be defined on the registry the frontend uses").toBe(true);
  await expect(page.locator("timerify-card ha-card").first()).toBeVisible();
});
