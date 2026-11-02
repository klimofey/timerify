// The Mushroom style in a real Home Assistant, without Mushroom: a card that asks for the style
// takes it once Mushroom's cards are defined on the page, and the page here defines a stand-in
// for one of them, which is all the card looks for. (The pictures of the documentation are
// taken with the real Mushroom: screenshots.spec.ts.) What the tests measure is the card's own
// size: the look Mushroom gives it, the look a theme's variables change, and that the Turn off
// button still fits at the narrowest and the widest the card is made.
// Views "mushroom-pill" and "mushroom-round": the two layouts with the option on; "mushroom-sizes"
// and "mushroom-wide": the cards of the views "sizes" and "wide", with the option on.
import type { Locator, Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { isReady } from "./ready";
import { PHONE, TARGET, boxOf, isCutOff, runBothTimers } from "./sizing";
import { stringsIn } from "./strings";

/** What Mushroom does on a page: its cards become known to the browser, after ours did. */
const loadMushroom = (page: Page) =>
  page.evaluate(() => customElements.define("mushroom-entity-card", class extends HTMLElement {}));

/** What a theme says in Mushroom's variables: larger spacing and icon, and another colour. */
const THEME = `:root {
  --mush-spacing: 20px;
  --mush-icon-size: 48px;
  --mush-rgb-state-entity: 255, 0, 0;
}`;

/** The sizes of a card's parts, as the browser computes them. */
interface Look {
  card: { height: string; borderRadius: string };
  content: { paddingLeft: string; paddingRight: string; gap: string };
  icon: { width: string; height: string; borderRadius: string };
  name: { fontSize: string; fontWeight: string; lineHeight: string; letterSpacing: string };
}

function lookOf(card: Locator): Promise<Look> {
  return card.evaluate((element) => {
    const parts = element.shadowRoot;
    const style = (selector: string) => {
      const part = parts?.querySelector(selector);
      if (!part) {
        throw new Error(`The card has no ${selector}`);
      }
      return getComputedStyle(part);
    };
    const card = style("ha-card");
    const content = style(".content");
    const icon = style(".icon");
    const name = style(".name");
    return {
      card: { height: card.height, borderRadius: card.borderRadius },
      content: {
        paddingLeft: content.paddingLeft,
        paddingRight: content.paddingRight,
        gap: content.columnGap,
      },
      icon: { width: icon.width, height: icon.height, borderRadius: icon.borderRadius },
      name: {
        fontSize: name.fontSize,
        fontWeight: name.fontWeight,
        lineHeight: name.lineHeight,
        letterSpacing: name.letterSpacing,
      },
    };
  });
}

/** The colour of the pill's fill, which shows the share of the countdown that has gone. */
function fillColour(card: Locator): Promise<string> {
  return card.locator(".fill").evaluate((fill) => getComputedStyle(fill).backgroundColor);
}

/** The card as it is in the Home Assistant look, which is what a card has without Mushroom. */
const HOME_ASSISTANT_PILL: Look = {
  card: { height: "56px", borderRadius: "28px" },
  content: { paddingLeft: "8px", paddingRight: "12px", gap: "12px" },
  icon: { width: "40px", height: "40px", borderRadius: "0px" },
  name: { fontSize: "14px", fontWeight: "500", lineHeight: "22.4px", letterSpacing: "normal" },
};
/** The amber of Home Assistant's default theme for what is on: `--state-active-color`. */
const HOME_ASSISTANT_FILL = "rgb(255, 193, 7)";

/** The card as Mushroom's own cards are, with the sizes Mushroom has when no theme sets them. */
const MUSHROOM_PILL: Look = {
  card: { height: "56px", borderRadius: "12px" },
  content: { paddingLeft: "10px", paddingRight: "10px", gap: "10px" },
  icon: { width: "36px", height: "36px", borderRadius: "50%" },
  name: { fontSize: "14px", fontWeight: "500", lineHeight: "20px", letterSpacing: "0.1px" },
};
/** Mushroom's blue, the colour of what is on: `--mush-rgb-state-entity` when no theme sets it. */
const MUSHROOM_FILL = "rgb(33, 150, 243)";

test.describe("the pill that asks for the Mushroom style", () => {
  test.beforeEach(async ({ page, openDashboard }) => {
    await openDashboard(page, "mushroom-pill");
    await expect(page.locator("timerify-card")).toHaveCount(2);
    for (const card of await page.locator("timerify-card").all()) {
      await isReady(card);
    }
  });

  test("keeps the Home Assistant look while Mushroom is not on the page", async ({ page }) => {
    for (const card of await page.locator("timerify-card").all()) {
      await expect(card).not.toHaveAttribute("data-mushroom", "");
      expect(await lookOf(card)).toEqual(HOME_ASSISTANT_PILL);
      expect(await fillColour(card)).toBe(HOME_ASSISTANT_FILL);
    }
  });

  test("takes Mushroom's look when Mushroom's cards are defined, without a reload", async ({
    page,
  }) => {
    await loadMushroom(page);

    for (const card of await page.locator("timerify-card").all()) {
      await expect(card).toHaveAttribute("data-mushroom", "");
      // The card's own transitions (the frontend gives it a fraction of a second to change
      // its shape) are over when it has this look.
      await expect.poll(() => lookOf(card)).toEqual(MUSHROOM_PILL);
      // The countdown's fill has Mushroom's colour of what is on.
      expect(await fillColour(card)).toBe(MUSHROOM_FILL);
    }
    // The chip has Mushroom's height.
    const chip = page.locator("timerify-card").first().locator(".chip");
    expect((await boxOf(chip)).height).toBe(36);
  });

  test("follows what a theme says in Mushroom's variables", async ({ page }) => {
    await loadMushroom(page);
    const card = page.locator("timerify-card").first();
    await expect(card).toHaveAttribute("data-mushroom", "");

    // A theme sets its variables on the page, as Home Assistant does with the ones of a theme.
    await page.addStyleTag({ content: THEME });

    await expect.poll(() => lookOf(card)).toMatchObject({
      // The card is as high as its icon and the spacing around it make it.
      card: { height: "88px" },
      content: { paddingLeft: "20px", paddingRight: "20px", gap: "20px" },
      icon: { width: "48px", height: "48px" },
    });
    expect(await fillColour(card)).toBe("rgb(255, 0, 0)");
  });
});

// A card of the view "pill", which is written without the option.
test("a card that does not ask for the style stays as it is, whatever Mushroom and the theme say", async ({
  page,
  openDashboard,
}) => {
  await openDashboard(page, "pill");
  const card = page.locator("timerify-card");
  await expect(card).toHaveCount(1);
  await isReady(card);

  await loadMushroom(page);
  await page.addStyleTag({ content: THEME });

  await expect(card).not.toHaveAttribute("data-mushroom", "");
  expect(await lookOf(card)).toEqual(HOME_ASSISTANT_PILL);
  expect(await fillColour(card)).toBe(HOME_ASSISTANT_FILL);
});

test.describe("the round tile that asks for the Mushroom style", () => {
  test.beforeEach(async ({ page, openDashboard }) => {
    await openDashboard(page, "mushroom-round");
    await expect(page.locator("timerify-card")).toHaveCount(2);
    for (const card of await page.locator("timerify-card").all()) {
      await isReady(card);
    }
  });

  test("keeps its size, and takes Mushroom's spacing and icon", async ({ page }) => {
    const cards = page.locator("timerify-card");
    const before = await boxOf(cards.first().locator("ha-card"));
    expect(before.height).toBe(120);

    await loadMushroom(page);

    for (const card of await cards.all()) {
      await expect(card).toHaveAttribute("data-mushroom", "");
      // As high as the grid row it is placed in: the name, the dial and the spacing fit it exactly.
      await expect.poll(() => lookOf(card)).toMatchObject({
        card: { height: "120px" },
        content: { paddingLeft: "10px", paddingRight: "10px" },
        icon: { width: "36px", height: "36px", borderRadius: "50%" },
        name: { fontSize: "14px", lineHeight: "20px" },
      });
    }
  });
});

// The Turn off button of the Mushroom style is Mushroom's control, 42 px high: it has to fit
// where the Home Assistant look's button, 40 px, did. The narrow cards are in Russian on the
// narrowest phone, as in sizes.spec.ts.
test.describe("the cards with a Turn off button at their narrowest, in the Mushroom style", () => {
  test.use({ locale: "ru-RU" });

  test.beforeEach(async ({ page, openDashboard, state, ws }) => {
    await runBothTimers(ws, state);
    await openDashboard(page, "mushroom-sizes");
    await page.setViewportSize(PHONE);
    await page.reload({ waitUntil: "load" });
    await expect(page.locator("#ha-launch-screen")).toHaveCount(0);
    await expect(page.locator("timerify-card")).toHaveCount(3);
    await loadMushroom(page);
    for (const card of await page.locator("timerify-card").all()) {
      await isReady(card);
      await expect(card).toHaveAttribute("data-mushroom", "");
    }
  });

  test("show a pill with its icon, the button as Mushroom's control, and its chip side by side", async ({
    page,
  }) => {
    const russian = await stringsIn("ru");
    const [pillWithChip, pill] = await page.locator("timerify-card").all();
    if (pillWithChip === undefined || pill === undefined) {
      throw new Error("The view should have two pills");
    }

    for (const card of [pillWithChip, pill]) {
      const button = card.getByRole("button", { name: russian.card_turn_off, exact: true });
      await expect(button).toBeVisible();
      await expect(card.locator(".turn-off-icon")).toBeVisible();
      await expect(card.locator(".turn-off-label")).toBeHidden();
      const outline = await boxOf(card.locator("ha-card"));
      const icon = await boxOf(card.locator(".icon"));
      const turnOff = await boxOf(button);

      expect(await isCutOff(card.locator(".content"))).toBe(false);
      // Mushroom's control: square, 42 px, and so a target for a finger.
      expect(turnOff.width).toBe(42);
      expect(turnOff.height).toBe(42);
      expect(turnOff.width).toBeGreaterThanOrEqual(TARGET);
      expect(icon.left).toBeGreaterThanOrEqual(outline.left);
      expect(turnOff.left).toBeGreaterThanOrEqual(icon.right);
      // The card's spacing, 10 px, and its border are left at the right.
      expect(turnOff.right).toBeLessThanOrEqual(outline.right - 11);
    }
    const withChip = await boxOf(pillWithChip.locator("ha-card"));
    const turnOff = await boxOf(pillWithChip.locator(".turn-off"));
    const chip = await boxOf(pillWithChip.locator(".chip"));
    expect(chip.left).toBeGreaterThanOrEqual(turnOff.right);
    expect(chip.right).toBeLessThanOrEqual(withChip.right - 11);
  });

  test("show a round tile with the button as Mushroom's control under its dial, inside it", async ({
    page,
  }) => {
    const russian = await stringsIn("ru");
    const round = page.locator("timerify-card").nth(2);
    const button = round.getByRole("button", { name: russian.card_turn_off, exact: true });
    await expect(button).toBeVisible();
    await expect(round.locator(".turn-off-label")).toBeHidden();

    const outline = await boxOf(round.locator("ha-card"));
    const dial = await boxOf(round.locator(".dial"));
    const turnOff = await boxOf(button);

    expect(turnOff.width).toBe(42);
    expect(turnOff.height).toBe(42);
    // The card's spacing, 10 px, is left on each side.
    expect(turnOff.left).toBeGreaterThanOrEqual(outline.left + 10);
    expect(turnOff.right).toBeLessThanOrEqual(outline.right - 10);
    expect(turnOff.top).toBeGreaterThanOrEqual(dial.bottom);
    expect(turnOff.bottom).toBeLessThanOrEqual(outline.bottom);
  });
});

const LANGUAGES = [
  { language: "en", locale: "en-US" },
  { language: "ru", locale: "ru-RU" },
] as const;

for (const { language, locale } of LANGUAGES) {
  test.describe(`the cards with a Turn off button, wide, in the Mushroom style, in ${language}`, () => {
    test.use({ locale });

    test.beforeEach(async ({ page, openDashboard, state, ws }) => {
      await runBothTimers(ws, state);
      await openDashboard(page, "mushroom-wide");
      await expect(page.locator("timerify-card")).toHaveCount(5);
      await loadMushroom(page);
      for (const card of await page.locator("timerify-card").all()) {
        await isReady(card);
        await expect(card).toHaveAttribute("data-mushroom", "");
      }
    });

    test("show the words of the button where there is room for them, and its icon in 6 columns", async ({
      page,
    }) => {
      const word = (await stringsIn(language)).card_turn_off;
      const [pill, pillWithChip, round, narrow, wider] = await page.locator("timerify-card").all();
      if (
        pill === undefined ||
        pillWithChip === undefined ||
        round === undefined ||
        narrow === undefined ||
        wider === undefined
      ) {
        throw new Error("The view should have five cards");
      }

      for (const card of [pill, pillWithChip, round, wider]) {
        const button = card.getByRole("button", { name: word, exact: true });
        await expect(button).toBeVisible();
        await expect(card.locator(".turn-off-label")).toHaveText(word);
        await expect(card.locator(".turn-off-icon")).toBeHidden();
        expect(await isCutOff(card.locator(".content"))).toBe(false);
        expect((await boxOf(button)).height).toBe(42);
      }
      await expect(narrow.locator(".turn-off-icon")).toBeVisible();
      await expect(narrow.locator(".turn-off-label")).toBeHidden();
      // The name keeps the room beside the words that the width they begin at is for.
      expect((await boxOf(wider.locator(".name"))).width).toBeGreaterThanOrEqual(80);
    });
  });
}
