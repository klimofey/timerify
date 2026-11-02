// The visual editor and the card picker in a real Home Assistant: an administrator adds the
// card from the picker, changes its layout and presets in the form Home Assistant builds from
// the card's schema, and sees a mistake in the YAML as an error. What the form saved is read
// back from Home Assistant's own dashboard configuration.
// View "editor": it has no card, the tests add one.
import type { Page } from "@playwright/test";
import type { E2EState, TimerEntities } from "./constants";
import { expect, test } from "./fixtures";
import { tap } from "./press";
import { stringsIn } from "./strings";

const english = await stringsIn("en");

/** The preset chips of a new card, as the editor labels them. */
const DEFAULT_PRESET_LABELS = ["15 min", "30 min", "45 min", "1 hr", "2 hr"];
const DEFAULT_PRESETS = ["15", "30", "45", "60", "120"];

/** The timer a new card starts with: the first one by the entity id of its number. */
function firstTimer(state: E2EState): TimerEntities {
  const [first] = Object.values(state.timers).sort((a, b) => (a.run_for < b.run_for ? -1 : 1));
  if (first === undefined) {
    throw new Error("The fixture should have timers");
  }
  return first;
}

/**
 * A word of Home Assistant's own, in the language of the page, as the frontend itself looks it
 * up: the test finds the controls it presses by the names a user reads on them, and spells no
 * language of its own. A page that has just loaded has no words until the frontend has fetched
 * its translations, so the lookup waits for the word to be there.
 */
async function frontendWord(page: Page, key: string): Promise<string> {
  const lookup = () =>
    page.evaluate((wanted) => {
      const app = document.querySelector("home-assistant") as unknown as {
        hass?: { localize(key: string): string };
      } | null;
      return app?.hass?.localize(wanted) ?? "";
    }, key);
  await expect.poll(lookup, { message: `the frontend's word for ${key}` }).not.toBe("");
  return lookup();
}

const ADD_CARD = "ui.panel.lovelace.editor.edit_card.add";
const BY_CARD = "ui.panel.lovelace.editor.cardpicker.by_card";
const SEARCH_CARDS = "ui.panel.lovelace.editor.edit_card.search_cards";

/** Goes into the dashboard's edit mode, as an administrator does. */
async function startEditing(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Edit dashboard" }).click();
}

/** Asks for a new card, in the edit mode. */
async function addCard(page: Page): Promise<void> {
  await page.getByRole("button", { name: await frontendWord(page, ADD_CARD) }).click();
}

/** Looks for the card among the card types the picker offers. */
async function searchForCard(page: Page): Promise<void> {
  await page.getByRole("tab", { name: await frontendWord(page, BY_CARD) }).click();
  await page.getByPlaceholder(await frontendWord(page, SEARCH_CARDS)).fill("Timerify");
  await expect(page.locator("timerify-card")).toBeVisible();
}

/**
 * Picks the card in the picker with a press on its preview, which the picker covers with its
 * own layer, and returns once the editor is open: when Home Assistant has built the form from
 * the schema, its first field is there.
 */
async function pickCard(page: Page, words: Record<string, string> = english): Promise<void> {
  await tap(page, page.locator("timerify-card"));
  await expect(page.getByText(words["card_editor_entity"], { exact: true })).toBeVisible();
  // The picker is gone, and with it its preview: the one card left is the editor's.
  await expect(page.getByPlaceholder(await frontendWord(page, SEARCH_CARDS))).toHaveCount(0);
  await expect(page.locator("timerify-card")).toHaveCount(1);
}

/** Saves the card in the editor, which closes it; the card is then on the dashboard. */
async function saveCard(page: Page): Promise<void> {
  const save = page.getByRole("button", { name: "Save" });
  await save.click();
  await expect(save).toBeHidden();
}

/** The chip of a preset in the editor's form, by what it says. */
const presetChip = (page: Page, label: string) =>
  page.getByRole("button", { name: label, exact: true });

/** The choices of a press, as the editor words them. */
const PRESS_CHOICES = [
  "card_editor_press_popup",
  "card_editor_press_run",
  "card_editor_press_stop",
  "card_editor_press_run_or_stop",
  "card_editor_press_action",
  "card_editor_press_none",
] as const;

/**
 * The drop-down of what a press does, by its label: an empty one shows its label in its place.
 */
const behaviour = (page: Page, label: string, words: Record<string, string> = english) =>
  page.getByText(words[label], { exact: true });

/** A choice in the drop-down that is open. */
const menuChoice = (page: Page, key: string, words: Record<string, string> = english) =>
  page.getByRole("menuitem", { name: words[key], exact: true });

/**
 * A yes-or-no field of the form, found by the words beside it: the switch has no name of its
 * own, its label is the text of the field it sits in. (Playwright's click on the switch is
 * refused: the switch's own thumb is in the way.)
 */
const yesNoField = (page: Page, label: string) =>
  page.locator("ha-formfield").filter({ hasText: label });

/** The button that takes the chip of a preset away. */
const removeChip = (page: Page, label: string) =>
  page.getByRole("button", { name: `Remove ${label}` });

test.describe("the card in Home Assistant's editor", () => {
  test.beforeEach(async ({ page, openDashboard }) => {
    await openDashboard(page, "editor", { emptyView: true });
  });

  test("adds a card from the picker", async ({ page, state, ws }) => {
    const timer = firstTimer(state);
    const targetName = (await ws.state(timer.target))?.attributes["friendly_name"];
    expect(targetName, "Home Assistant should name the timer's target").toEqual(expect.any(String));
    await startEditing(page);
    await addCard(page);

    await searchForCard(page);

    // The picker shows the card as it would be: the first timer, in the pill.
    const preview = page.locator("timerify-card");
    await expect(preview.locator("ha-card.pill .name")).toHaveText(String(targetName));

    await pickCard(page);

    // The editor starts with the defaults, which it shows, so that adding a preset does not
    // lose the others unseen.
    for (const label of DEFAULT_PRESET_LABELS) {
      await expect(presetChip(page, label)).toBeVisible();
    }
    await expect(page.getByText(english["card_editor_presets"])).toBeVisible();
    await saveCard(page);
    await expect(page.locator("timerify-card ha-card.pill .name")).toHaveText(String(targetName));
    await expect
      .poll(async () => (await ws.config("editor")).cards)
      .toEqual([
        {
          type: "custom:timerify-card",
          entity: timer.run_for,
          layout: "pill",
          presets: DEFAULT_PRESETS,
        },
      ]);
  });

  test("changes the layout and the presets in the visual editor", async ({ page, state, ws }) => {
    const timer = firstTimer(state);
    await startEditing(page);
    await addCard(page);
    await searchForCard(page);
    await pickCard(page);
    const card = page.locator("timerify-card");
    await expect(card.locator("ha-card.pill")).toBeVisible();

    await page.getByRole("radio", { name: english["card_editor_layout_round"] }).click();

    await expect(card.locator("ha-card.round")).toBeVisible();
    await expect(card.locator("ha-card.pill")).toHaveCount(0);

    // A preset the list does not offer is typed in, and kept after the five it started with.
    await page.getByRole("button", { name: english["card_editor_presets"] }).click();
    await page.getByPlaceholder("Search | Add custom item").fill("20");
    await page.getByText("Add custom item").click();
    await expect(presetChip(page, "20")).toBeVisible();
    await saveCard(page);

    await expect
      .poll(async () => (await ws.config("editor")).cards)
      .toEqual([
        {
          type: "custom:timerify-card",
          entity: timer.run_for,
          layout: "round",
          presets: [...DEFAULT_PRESETS, "20"],
        },
      ]);
    await expect(page.locator("timerify-card ha-card.round")).toBeVisible();
  });

  test("sets what a tap does in the Interactions group", async ({ page, state, ws }) => {
    const timer = firstTimer(state);
    await startEditing(page);
    await addCard(page);
    await searchForCard(page);
    await pickCard(page);

    // The group is shut until the user opens it.
    const group = page.getByText(english["card_editor_interactions"], { exact: true });
    await expect(group).toBeVisible();
    await expect(behaviour(page, "card_editor_tap")).toBeHidden();
    await group.click();
    for (const press of ["card_editor_tap", "card_editor_double_tap", "card_editor_hold"]) {
      await expect(behaviour(page, press), press).toBeVisible();
    }

    await behaviour(page, "card_editor_tap").click();
    for (const choice of PRESS_CHOICES) {
      await expect(menuChoice(page, choice), choice).toBeVisible();
    }
    await menuChoice(page, "card_editor_press_run").click();
    await saveCard(page);

    await expect
      .poll(async () => (await ws.config("editor")).cards)
      .toEqual([
        {
          type: "custom:timerify-card",
          entity: timer.run_for,
          layout: "pill",
          presets: DEFAULT_PRESETS,
          tap: "run",
        },
      ]);
  });

  test("turns the Turn off button on in the form", async ({ page, state, ws }) => {
    const timer = firstTimer(state);
    await startEditing(page);
    await addCard(page);
    await searchForCard(page);
    await pickCard(page);

    // A press on the words beside the switch turns it, as a press on the switch does.
    await yesNoField(page, english["card_editor_show_turn_off"]).getByRole("paragraph").click();
    await saveCard(page);

    await expect
      .poll(async () => (await ws.config("editor")).cards)
      .toEqual([
        {
          type: "custom:timerify-card",
          entity: timer.run_for,
          layout: "pill",
          presets: DEFAULT_PRESETS,
          show_turn_off: true,
        },
      ]);
  });

  test("turns the Mushroom style on in the form, and says that Mushroom was not found", async ({
    page,
    state,
    ws,
  }) => {
    const timer = firstTimer(state);
    await startEditing(page);
    await addCard(page);
    await searchForCard(page);
    await pickCard(page);

    // This page has no Mushroom: the note is under the field, whatever the field says.
    await expect(page.getByText(english["card_editor_mushroom_missing"])).toBeVisible();
    // A press on the words beside the switch turns it, as a press on the switch does. The note
    // under them is another paragraph of the field.
    await yesNoField(page, english["card_editor_mushroom"]).locator("p.primary").click();
    await saveCard(page);

    await expect
      .poll(async () => (await ws.config("editor")).cards)
      .toEqual([
        {
          type: "custom:timerify-card",
          entity: timer.run_for,
          layout: "pill",
          presets: DEFAULT_PRESETS,
          mushroom: true,
        },
      ]);
  });

  test("does not say that Mushroom was not found when its cards are on the page", async ({
    page,
  }) => {
    await page.evaluate(() =>
      customElements.define("mushroom-entity-card", class extends HTMLElement {}),
    );
    await startEditing(page);
    await addCard(page);
    await searchForCard(page);
    await pickCard(page);

    await expect(yesNoField(page, english["card_editor_mushroom"])).toBeVisible();
    await expect(page.getByText(english["card_editor_mushroom_missing"])).toHaveCount(0);
  });

  test("falls back on the default presets when the last one is taken away", async ({
    page,
    state,
    ws,
  }) => {
    const timer = firstTimer(state);
    await startEditing(page);
    await addCard(page);
    await searchForCard(page);
    await pickCard(page);

    for (const label of DEFAULT_PRESET_LABELS) {
      await removeChip(page, label).click();
    }

    // The form stays: it said that an empty list stands for the defaults, and the card agrees.
    await expect(page.getByRole("button", { name: "Show code editor" })).toBeVisible();
    await expect(page.getByText(english["card_error_presets"])).toHaveCount(0);
    await saveCard(page);
    await expect
      .poll(async () => (await ws.config("editor")).cards)
      .toEqual([
        { type: "custom:timerify-card", entity: timer.run_for, layout: "pill", presets: [] },
      ]);
    await page.getByRole("button", { name: "Done" }).click();
    await tap(page, page.locator("timerify-card"));
    const dialog = page.locator("timerify-card dialog");
    await expect(dialog).toBeVisible();
    for (const label of DEFAULT_PRESET_LABELS) {
      await expect(dialog.getByRole("button", { name: label, exact: true })).toBeVisible();
    }
  });

  test("keeps the form when a preset typed is not minutes, and shows the card's error", async ({
    page,
  }) => {
    await startEditing(page);
    await addCard(page);
    await searchForCard(page);
    await pickCard(page);

    await page.getByRole("button", { name: english["card_editor_presets"] }).click();
    await page.getByPlaceholder("Search | Add custom item").fill("0");
    await page.getByText("Add custom item").click();

    // The user is not thrown out of the form: the preview says what is wrong, as the card
    // would on the dashboard, and the preset can be taken away from where it was added.
    await expect(presetChip(page, "0")).toBeVisible();
    await expect(page.getByRole("button", { name: "Show code editor" })).toBeVisible();
    await expect(page.getByText(english["card_error_presets"])).toBeVisible();
    await removeChip(page, "0").click();
    await expect(page.getByText(english["card_error_presets"])).toHaveCount(0);
    await expect(page.locator("timerify-card ha-card.pill")).toBeVisible();
  });

  /** Replaces the YAML of the card in the editor's code editor. */
  async function writeYaml(page: Page, lines: string[]): Promise<void> {
    await page.getByRole("button", { name: "Show code editor" }).click();
    await page.locator(".cm-content").click();
    await page.keyboard.press("ControlOrMeta+A");
    await page.keyboard.insertText(lines.join("\n"));
  }

  test("shows a bad YAML config as an error", async ({ page, state }) => {
    const timer = firstTimer(state);
    await startEditing(page);
    await addCard(page);
    await searchForCard(page);
    await pickCard(page);

    await writeYaml(page, [
      "type: custom:timerify-card",
      `entity: ${timer.run_for}`,
      "presets: [0]",
    ]);

    // The card's own message, in the preview, which shows what the card would show on the
    // dashboard. The form could show this config, so it is still there to put it right.
    await expect(page.getByText(english["card_error_presets"])).toBeVisible();
    await page.getByRole("button", { name: "Show visual editor" }).click();
    await expect(removeChip(page, "0")).toBeVisible();
  });

  test("tells a config the form cannot show from one it can", async ({ page, state }) => {
    const timer = firstTimer(state);
    await startEditing(page);
    await addCard(page);
    await searchForCard(page);
    await pickCard(page);

    await writeYaml(page, [
      "type: custom:timerify-card",
      `entity: ${timer.run_for}`,
      "presets: 15",
    ]);

    // The same message twice: in the warning that the visual editor cannot be used for this,
    // and in the preview.
    await expect(page.getByText(english["card_error_presets"])).toHaveCount(2);
    await expect(page.getByRole("button", { name: "Show visual editor" })).toBeDisabled();
  });

  test.describe("in Russian", () => {
    test.use({ locale: "ru-RU" });

    test("speaks Russian", async ({ page, state }) => {
      const ru = await stringsIn("ru");
      // Home Assistant's own words are Russian too, which the test does not spell: it reads
      // them from the frontend, and enters the edit mode by the address.
      await page.goto(`/${state.dashboard}/editor?edit=1`);
      await addCard(page);
      await searchForCard(page);
      await pickCard(page, ru);

      await expect(page.locator("html")).toHaveAttribute("lang", "ru");
      await expect(yesNoField(page, ru["card_editor_show_turn_off"])).toBeVisible();
      const fields = ["entity", "layout", "name", "icon", "presets", "chip", "interactions"];
      for (const field of fields) {
        await expect(
          page.getByText(ru[`card_editor_${field}`], { exact: true }),
          field,
        ).toBeVisible();
      }
      await page.getByText(ru["card_editor_interactions"], { exact: true }).click();
      for (const press of ["card_editor_tap", "card_editor_double_tap", "card_editor_hold"]) {
        await expect(behaviour(page, press, ru), press).toBeVisible();
      }
      await behaviour(page, "card_editor_tap", ru).click();
      for (const choice of PRESS_CHOICES) {
        await expect(menuChoice(page, choice, ru), choice).toBeVisible();
      }
      for (const layout of ["pill", "round"]) {
        await expect(
          page.getByRole("radio", { name: ru[`card_editor_layout_${layout}`] }),
          layout,
        ).toBeVisible();
      }
      // The presets as Russian writes them: Intl's own, not an English word.
      const unit = (count: number, name: "hour" | "minute") =>
        new Intl.NumberFormat("ru", {
          style: "unit",
          unit: name,
          unitDisplay: "short",
          useGrouping: false,
        }).format(count);
      const defaults = [
        unit(15, "minute"),
        unit(30, "minute"),
        unit(45, "minute"),
        unit(1, "hour"),
        unit(2, "hour"),
      ];
      for (const label of defaults) {
        await expect(presetChip(page, label)).toBeVisible();
      }
      const list = new Intl.ListFormat("ru", { style: "long", type: "conjunction" });
      await expect(
        page.getByText(
          ru["card_editor_presets_helper"].replace("{presets}", list.format(defaults)),
        ),
      ).toBeVisible();
    });
  });
});
