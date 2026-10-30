// The proof that the card's pop-up, a native <dialog> in the card's own shadow DOM, works in
// a real Home Assistant, which has dialogs of its own: it opens as a modal above the whole
// frontend, the page behind it takes no input, and Escape closes it. Everything else the
// pop-up will do rests on this. View "dialog": one pill card on the strict timer.
import type { Locator } from "@playwright/test";
import { expect, test } from "./fixtures";

const NAME = "Smoke boiler";

/**
 * Where the keyboard focus is, as seen through the shadow roots of the whole page: inside the
 * dialog, nowhere (on the document or on nothing), or somewhere in the page behind it.
 */
function focusedPlace(dialog: Locator): Promise<string> {
  return dialog.evaluate((element) => {
    let active: Element | null = document.activeElement;
    while (active?.shadowRoot?.activeElement) {
      active = active.shadowRoot.activeElement;
    }
    if (active === null || active === document.body || active === document.documentElement) {
      return "nowhere";
    }
    return element.contains(active) ? "the dialog" : `the page behind: <${active.localName}>`;
  });
}

/** Whether the element is the one that has the keyboard focus in its own tree. */
function hasFocus(element: Locator): Promise<boolean> {
  return element.evaluate((node) => {
    const root = node.getRootNode();
    return root instanceof ShadowRoot && root.activeElement === node;
  });
}

test.describe("the card's dialog in Home Assistant", () => {
  test.beforeEach(async ({ page, openDashboard }) => {
    await openDashboard(page, "dialog");
  });

  test("the card is on the dashboard", async ({ page }) => {
    await expect(page.locator("timerify-card").getByText(NAME)).toBeVisible();
  });

  test("a tap opens a modal dialog above Home Assistant", async ({ page }) => {
    const card = page.locator("timerify-card");
    const dialog = card.locator("dialog");
    await expect(dialog).toBeHidden();

    await card.getByRole("button", { name: NAME }).click();

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

    await card.getByRole("button", { name: NAME }).click();
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
    const body = card.getByRole("button", { name: NAME });
    await body.click();
    await expect(dialog).toBeVisible();

    await page.keyboard.press("Escape");

    await expect(dialog).toBeHidden();
    await expect(body).toBeFocused();
  });

  test("a keyboard user sees where the focus is", async ({ page }) => {
    const body = page.locator("timerify-card").getByRole("button", { name: NAME });
    // Tab through the page, as a keyboard user does, until it reaches the card.
    for (let presses = 1; !(await hasFocus(body)); presses++) {
      expect(presses, "presses of Tab before the card has the focus").toBeLessThanOrEqual(100);
      await page.keyboard.press("Tab");
    }

    const outline = await body.evaluate((node) => getComputedStyle(node).outlineStyle);
    expect(outline).not.toBe("none");
  });
});
