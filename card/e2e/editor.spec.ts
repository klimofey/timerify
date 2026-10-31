// The visual editor and the card picker in a real Home Assistant: an administrator adds the
// card from the picker, changes its layout and presets in the form Home Assistant builds from
// the card's schema, and sees a mistake in the YAML as an error. What the form saved is read
// back from Home Assistant's own dashboard configuration.
// View "editor": it has no card, the tests add one.
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { REPO_ROOT, type E2EState, type TimerEntities } from "./constants";
import { expect, test } from "./fixtures";
import { tap } from "./press";

/** The words of the card in a language, read from the file the integration serves them from. */
async function stringsIn(language: "en" | "ru"): Promise<Record<string, string>> {
  const file = join(REPO_ROOT, "custom_components", "timerify", "translations", `${language}.json`);
  const translations = JSON.parse(await readFile(file, "utf8")) as {
    common: Record<string, string>;
  };
  return translations.common;
}

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

/** Goes into the dashboard's edit mode, as an administrator does, and asks for a new card. */
async function addCard(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Edit dashboard" }).click();
  await page.getByRole("button", { name: "Add card" }).click();
}

/** Looks for the card among the card types the picker offers. */
async function searchForCard(page: Page): Promise<void> {
  await page.getByRole("tab", { name: "By card" }).click();
  await page.getByPlaceholder("Search cards").fill("Timerify");
  await expect(page.locator("timerify-card")).toBeVisible();
}

/**
 * Picks the card in the picker with a press on its preview, which the picker covers with its
 * own layer, and returns once the editor is open.
 */
async function pickCard(page: Page, language: "en" | "ru" = "en"): Promise<void> {
  await tap(page, page.locator("timerify-card"));
  // The editor has its first field when Home Assistant has built the form from the schema.
  if (language === "en") {
    await expect(page.getByText("Timerify card configuration")).toBeVisible();
  } else {
    await expect(page.locator("hui-form-editor")).toBeVisible();
  }
  // The picker is gone, and with it its preview: the one card left is the editor's.
  await expect(page.getByPlaceholder("Search cards")).toHaveCount(0);
  await expect(page.locator("timerify-card")).toHaveCount(1);
}

/** Saves the card in the editor, which closes it; the card is then on the dashboard. */
async function saveCard(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Timerify card configuration")).toBeHidden();
}

/** The chip of a preset in the editor's form, by its label. */
const presetChip = (page: Page, label: string) =>
  page.getByRole("button", { name: `Remove ${label}` });

test.describe("the card in Home Assistant's editor", () => {
  test.beforeEach(async ({ page, openDashboard }) => {
    await openDashboard(page, "editor", { emptyView: true });
  });

  test("adds a card from the picker", async ({ page, state, ws }) => {
    const timer = firstTimer(state);
    const targetName = (await ws.state(timer.target))?.attributes["friendly_name"];
    expect(targetName, "Home Assistant should name the timer's target").toEqual(expect.any(String));
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

  test("falls back on the default presets when the last one is taken away", async ({
    page,
    ws,
  }) => {
    await addCard(page);
    await searchForCard(page);
    await pickCard(page);

    for (const label of DEFAULT_PRESET_LABELS) {
      await presetChip(page, label).click();
    }

    // The form stays: it said that an empty list stands for the defaults, and the card agrees.
    await expect(page.getByRole("button", { name: "Show code editor" })).toBeVisible();
    await expect(page.getByText(english["card_error_presets"])).toHaveCount(0);
    await saveCard(page);
    await expect.poll(async () => (await ws.config("editor")).cards).toHaveLength(1);
    await page.getByRole("button", { name: "Done" }).click();
    await tap(page, page.locator("timerify-card"));
    const dialog = page.locator("timerify-card dialog");
    await expect(dialog).toBeVisible();
    for (const label of DEFAULT_PRESET_LABELS) {
      await expect(dialog.getByRole("button", { name: label, exact: true })).toBeVisible();
    }
  });

  test("shows a bad YAML config as an error", async ({ page, state }) => {
    const timer = firstTimer(state);
    await addCard(page);
    await searchForCard(page);
    await pickCard(page);

    await page.getByRole("button", { name: "Show code editor" }).click();
    await page.locator(".cm-content").click();
    await page.keyboard.press("ControlOrMeta+A");
    await page.keyboard.insertText(
      ["type: custom:timerify-card", `entity: ${timer.run_for}`, "presets: [0]"].join("\n"),
    );

    // The message of the card itself: in the warning that the visual editor cannot be used,
    // and in the preview, which shows what the card would show on the dashboard.
    await expect(page.getByText(english["card_error_presets"])).toHaveCount(2);
    await expect(page.getByRole("button", { name: "Show visual editor" })).toBeDisabled();
  });

  test.describe("in Russian", () => {
    test.use({ locale: "ru-RU" });

    test("speaks Russian", async ({ page, state }) => {
      const ru = await stringsIn("ru");
      // Home Assistant's own words are Russian too, which the test does not spell: it finds the
      // controls it presses by what they are.
      await page.goto(`/${state.dashboard}/editor?edit=1`);
      await page.locator("hui-masonry-view ha-button").click();
      await page.locator('ha-tab-group-tab[panel="card"]').click();
      await page.locator("hui-card-picker ha-input-search input").fill("Timerify");
      await expect(page.locator("timerify-card")).toBeVisible();
      await pickCard(page, "ru");

      await expect(page.locator("html")).toHaveAttribute("lang", "ru");
      for (const field of ["entity", "layout", "name", "icon", "presets", "chip"]) {
        await expect(
          page.getByText(ru[`card_editor_${field}`], { exact: true }),
          field,
        ).toBeVisible();
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
      await expect(page.locator("ha-input-chip .label")).toHaveText(defaults);
      const list = new Intl.ListFormat("ru", { style: "long", type: "conjunction" });
      await expect(
        page.getByText(
          ru["card_editor_presets_helper"].replace("{presets}", list.format(defaults)),
        ),
      ).toBeVisible();
    });
  });
});
