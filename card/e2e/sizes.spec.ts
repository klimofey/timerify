// The cards with a Turn off button at their narrowest, and at their widest: a narrow card shows
// the button as its icon alone, a wide one shows its words, and the card has room for what it
// shows at the fewest columns it declares (`min_columns`, which `getGridOptions` pins). View
// "sizes": a sections view of one section, whose cards ask for one column, which is less than
// they declare, so Home Assistant gives each the fewest columns it declares; the test narrows
// the page to the narrowest phone, 320 px, and reads it in Russian, the longer language, whose
// words need the most room. View "wide": cards of 12 columns, and one pill on each side of the
// width where the words begin. View "dials": the round tile without the button, whose dial is
// measured at three widths of the page.
import type { Locator, Page } from "@playwright/test";
import { TIME_FROM, expectDialsToFit, expectTimeFromTheWidth, showDials } from "./dials";
import { expect, test } from "./fixtures";
import { tabToButton } from "./focus";
import { isReady } from "./ready";
import {
  PHONE,
  TARGET,
  boxOf,
  fitsInRing,
  isCutOff,
  isInside,
  reloadAtWidth,
  runBothTimers,
} from "./sizing";
import { stringsIn } from "./strings";

/** The space the pill leaves at its right: its padding and the border of the card. */
const PILL_EDGE = 13;

test.describe("the cards with a Turn off button at their narrowest", () => {
  test.use({ locale: "ru-RU" });

  /** The cards of the view, in the order of the dashboard. */
  function cardsOf(page: Page): { pillWithChip: Locator; pill: Locator; round: Locator } {
    const cards = page.locator("timerify-card");
    return { pillWithChip: cards.nth(0), pill: cards.nth(1), round: cards.nth(2) };
  }

  test.beforeEach(async ({ page, openDashboard, state, ws }) => {
    await runBothTimers(ws, state);
    await openDashboard(page, "sizes");
    // The login waits for the sidebar, which a phone hides: the page is narrowed after it, and
    // loaded again, as a phone loads it.
    await reloadAtWidth(page, PHONE);
    await expect(page.locator("timerify-card")).toHaveCount(3);
    for (const card of Object.values(cardsOf(page))) {
      await isReady(card);
    }
  });

  test("show a pill with its icon, the button as an icon alone, and its chip side by side", async ({
    page,
  }) => {
    const russian = await stringsIn("ru");
    const { pillWithChip, pill } = cardsOf(page);

    for (const card of [pillWithChip, pill]) {
      // Named by its words for assistive technology, and shown as the power icon.
      const button = card.getByRole("button", { name: russian.card_turn_off, exact: true });
      await expect(button).toBeVisible();
      await expect(button).toHaveAttribute("title", russian.card_turn_off);
      await expect(card.locator(".turn-off-icon")).toBeVisible();
      await expect(card.locator(".turn-off-label")).toBeHidden();
      const outline = await boxOf(card.locator("ha-card"));
      const icon = await boxOf(card.locator(".icon"));
      const turnOff = await boxOf(button);

      expect(await isCutOff(card.locator(".content"))).toBe(false);
      expect(turnOff.width).toBeGreaterThanOrEqual(TARGET);
      expect(turnOff.height).toBeGreaterThanOrEqual(TARGET);
      expect(icon.left).toBeGreaterThanOrEqual(outline.left);
      expect(turnOff.left).toBeGreaterThanOrEqual(icon.right);
    }

    const outline = await boxOf(pill.locator("ha-card"));
    expect((await boxOf(pill.locator(".turn-off"))).right).toBeLessThanOrEqual(
      outline.right - PILL_EDGE,
    );
    const withChip = await boxOf(pillWithChip.locator("ha-card"));
    const turnOff = await boxOf(pillWithChip.locator(".turn-off"));
    const chip = await boxOf(pillWithChip.locator(".chip"));
    expect(chip.left).toBeGreaterThanOrEqual(turnOff.right);
    expect(chip.right).toBeLessThanOrEqual(withChip.right - PILL_EDGE);
  });

  test("show a round tile with the button as an icon alone under its dial, inside it", async ({
    page,
  }) => {
    const russian = await stringsIn("ru");
    const { round } = cardsOf(page);
    const button = round.getByRole("button", { name: russian.card_turn_off, exact: true });
    await expect(button).toBeVisible();
    await expect(round.locator(".turn-off-label")).toBeHidden();

    const outline = await boxOf(round.locator("ha-card"));
    const dial = await boxOf(round.locator(".dial"));
    const turnOff = await boxOf(button);

    // The dial has shrunk to the room this phone leaves it, and its time is inside its ring.
    expect(isInside(dial, outline)).toBe(true);
    expect(await fitsInRing(round.locator(".dial"), round.locator(".time"))).toBe(true);
    // The button is as big as a finger needs, and inside the tile.
    expect(turnOff.width).toBeGreaterThanOrEqual(TARGET);
    expect(turnOff.height).toBeGreaterThanOrEqual(TARGET);
    // The card's own padding, 8 px, is left on each side.
    expect(turnOff.left).toBeGreaterThanOrEqual(outline.left + 8);
    expect(turnOff.right).toBeLessThanOrEqual(outline.right - 8);
    expect(turnOff.top).toBeGreaterThanOrEqual(dial.bottom);
    expect(turnOff.bottom).toBeLessThanOrEqual(outline.bottom);
  });

  test("show where the keyboard is on the icon button, and leave it on the card when it goes", async ({
    page,
    state,
    ws,
  }) => {
    const russian = await stringsIn("ru");
    const { pill } = cardsOf(page);
    const button = pill.getByRole("button", { name: russian.card_turn_off, exact: true });

    await tabToButton(page, pill, button);
    const ring = await button.evaluate((element) => {
      const style = getComputedStyle(element);
      return { style: style.outlineStyle, width: style.outlineWidth };
    });
    expect(ring).toEqual({ style: "solid", width: "2px" });

    await page.keyboard.press("Enter");

    await expect
      .poll(async () => (await ws.state(state.timers.loose.target))?.state)
      .toBe("off");
    await expect(button).toHaveCount(0);
    await expect(pill.locator(".body")).toBeFocused();
  });
});

// The dial of the round tile is 80 px where the tile has room for it, and follows the tile where
// it has less: 2 columns on any screen, 3 on a narrow phone. Where the dial is too small for
// the time to be read it shows the icon instead. View "dials" (see dials.ts): the first three
// of its six tiles are in the Home Assistant look.
test.describe("the round tile's dial at every size the tile allows", () => {
  test.beforeEach(async ({ page, openDashboard, state, ws }) => {
    await showDials(page, openDashboard, ws, state);
  });

  test("holds the time, or the icon where the time cannot be read, inside its ring", async ({
    page,
  }) => {
    await expectDialsToFit(page, { first: 0, mushroom: false });
  });

  test(`shows the time from a dial of ${TIME_FROM} px, and the icon below it`, async ({ page }) => {
    await expectTimeFromTheWidth(page.locator("timerify-card").first());
  });
});

// The width where the words begin was computed from the Russian word, the longer of the two, so
// the Russian run is the one that tests it; the English run is cheap, and tests the same width
// with more room for the name.
const LANGUAGES = [
  { language: "en", locale: "en-US" },
  { language: "ru", locale: "ru-RU" },
] as const;

for (const { language, locale } of LANGUAGES) {
  test.describe(`the cards with a Turn off button, wide, in ${language}`, () => {
    test.use({ locale });

    test.beforeEach(async ({ page, openDashboard, state, ws }) => {
      await runBothTimers(ws, state);
      await openDashboard(page, "wide");
      await expect(page.locator("timerify-card")).toHaveCount(5);
    });

    /** The cards of the view, in the order of the dashboard. */
    function cardsOf(page: Page): Locator[] {
      const cards = page.locator("timerify-card");
      return [0, 1, 2, 3, 4].map((index) => cards.nth(index));
    }

    test("show the words of the button, and not its icon, where there is room for them", async ({
      page,
    }) => {
      const word = (await stringsIn(language)).card_turn_off;
      const [pill, pillWithChip, round, , wider] = cardsOf(page);

      for (const card of [pill, pillWithChip, round, wider]) {
        await isReady(card);
        const button = card.getByRole("button", { name: word, exact: true });
        await expect(button).toBeVisible();
        await expect(card.locator(".turn-off-label")).toHaveText(word);
        await expect(card.locator(".turn-off-icon")).toBeHidden();
        expect(await isCutOff(card.locator(".content"))).toBe(false);
      }
    });

    test("show the icon of the button in a card of 6 columns, and its words in one of 7", async ({
      page,
    }) => {
      const [, , , narrow, wider] = cardsOf(page);
      await isReady(narrow);
      await isReady(wider);

      await expect(narrow.locator(".turn-off-icon")).toBeVisible();
      await expect(narrow.locator(".turn-off-label")).toBeHidden();
      await expect(wider.locator(".turn-off-label")).toBeVisible();
      await expect(wider.locator(".turn-off-icon")).toBeHidden();
      // The name keeps room beside the words, which is what the width they begin at is for: in
      // Russian the word is the longest, and the name has just what the threshold leaves it.
      expect((await boxOf(wider.locator(".name"))).width).toBeGreaterThanOrEqual(80);
    });

    test("leave the keyboard on the card when the button with its words goes", async ({
      page,
      state,
      ws,
    }) => {
      const word = (await stringsIn(language)).card_turn_off;
      const [pill] = cardsOf(page);
      await isReady(pill);
      const button = pill.getByRole("button", { name: word, exact: true });

      await tabToButton(page, pill, button);
      await page.keyboard.press("Enter");

      await expect
        .poll(async () => (await ws.state(state.timers.loose.target))?.state)
        .toBe("off");
      await expect(button).toHaveCount(0);
      await expect(pill.locator(".body")).toBeFocused();
    });
  });
}
