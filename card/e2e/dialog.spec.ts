// The proof that the card's pop-up, a native <dialog> in the card's own shadow DOM, works in
// a real Home Assistant, which has dialogs of its own: it opens as a modal above the whole
// frontend, the page behind it takes no input, and Escape closes it. Everything else the
// pop-up will do rests on this. View "dialog": one pill card on the strict timer.
import { STRICT_NAME } from "./constants";
import { expect, test } from "./fixtures";
import { focusedPlace, hasFocus } from "./focus";

/** What `transparent` computes to: the probe's answer when the theme has no primary colour. */
const NO_COLOR = "rgba(0, 0, 0, 0)";

test.describe("the card's dialog in Home Assistant", () => {
  test.beforeEach(async ({ page, openDashboard }) => {
    await openDashboard(page, "dialog");
  });

  test("the card is on the dashboard", async ({ page }) => {
    await expect(page.locator("timerify-card").getByText(STRICT_NAME)).toBeVisible();
  });

  test("a tap opens a modal dialog above Home Assistant", async ({ page }) => {
    const card = page.locator("timerify-card");
    const dialog = card.locator("dialog");
    await expect(dialog).toBeHidden();

    await card.getByRole("button", { name: STRICT_NAME }).click();

    await expect(dialog).toBeVisible();
    const isModal = (node: HTMLDialogElement) => node.open && node.matches(":modal");
    expect(await dialog.evaluate(isModal)).toBe(true);
    // Playwright clicks only what nothing else covers: the frontend's header, sidebar and
    // overlays are all below the dialog.
    await dialog.getByRole("button", { name: "Close" }).click();
    await expect(dialog).toBeHidden();
  });

  test("the page behind the dialog takes no input", async ({ page }) => {
    const card = page.locator("timerify-card");
    const dialog = card.locator("dialog");
    const sidebar = page.locator("ha-sidebar").getByRole("link").first();
    // The sidebar can be clicked as long as the dialog is closed.
    await sidebar.click({ trial: true });

    await card.getByRole("button", { name: STRICT_NAME }).click();
    await expect(dialog).toBeVisible();

    for (let presses = 1; presses <= 6; presses++) {
      await page.keyboard.press("Tab");
      const place = await focusedPlace(dialog);
      expect(place, `focus after ${presses} presses of Tab`).not.toMatch(/^the page behind/);
    }
    const click = sidebar.click({ trial: true, timeout: 2_000 });
    await expect(click).rejects.toThrow(/intercepts pointer events/);
  });

  test("Escape closes it and gives focus back to the card", async ({ page }) => {
    const card = page.locator("timerify-card");
    const dialog = card.locator("dialog");
    const body = card.getByRole("button", { name: STRICT_NAME });
    await body.click();
    await expect(dialog).toBeVisible();

    await page.keyboard.press("Escape");

    await expect(dialog).toBeHidden();
    await expect(body).toBeFocused();
  });

  test("a keyboard user sees where the focus is", async ({ page }) => {
    const body = page.locator("timerify-card").getByRole("button", { name: STRICT_NAME });
    // Tab through the page, as a keyboard user does, until it reaches the card.
    for (let presses = 1; !(await hasFocus(body)); presses++) {
      expect(presses, "presses of Tab before the card has the focus").toBeLessThanOrEqual(100);
      await page.keyboard.press("Tab");
    }

    // The card's own ring, not the browser's default one: `.body:focus-visible` in the card
    // draws 2px, solid, in the theme's primary colour.
    const outline = await body.evaluate((node, none) => {
      const style = getComputedStyle(node);
      // The theme's colour as the browser computes it, taken from a probe in the same tree.
      const probe = document.createElement("span");
      probe.style.color = `var(--primary-color, ${none})`;
      node.parentNode?.append(probe);
      const primary = getComputedStyle(probe).color;
      probe.remove();
      return {
        style: style.outlineStyle,
        width: style.outlineWidth,
        color: style.outlineColor,
        primary,
      };
    }, NO_COLOR);
    expect(outline.primary, "the theme should define --primary-color").not.toBe(NO_COLOR);
    expect(outline).toMatchObject({ style: "solid", width: "2px", color: outline.primary });
  });
});
