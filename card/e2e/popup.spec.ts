// The pop-up in a real Home Assistant: the user runs the timer for a time, adds and takes off
// time and stops it, switches an interval of the schedule, cancels a pending command, and, if
// an administrator, goes to the timer's settings. Everything is read back from Home Assistant's
// own states, never from what the pop-up says.
// View "popup": the strict timer's pill, which has the interval, and the loose timer's, which
// has the fixture's pending command.
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import type { Locator, Page } from "@playwright/test";
import { REPO_ROOT } from "./constants";
import { expect, test } from "./fixtures";
import { tap } from "./press";
import { hassWs } from "./ws";

/** The browser's time zone, which the user's profile follows by default (the config's). */
const ZONE = "America/New_York";

const dayIn = (moment: number) =>
  new Intl.DateTimeFormat("en-CA", { timeZone: ZONE }).format(moment);

/**
 * A time as the card writes it at this moment: in the user's language and the browser's time
 * zone, with the short weekday when it falls on another day than today, which a command that
 * is due in ten hours does, and a countdown does in its last minutes before midnight.
 */
function clockText(language: string, hourCycle: "h12" | "h23", moment: number): string {
  const options: Intl.DateTimeFormatOptions = {
    timeZone: ZONE,
    hour: "numeric",
    minute: "2-digit",
    hourCycle,
  };
  if (dayIn(moment) !== dayIn(Date.now())) {
    options.weekday = "short";
  }
  return new Intl.DateTimeFormat(language, options).format(moment).replace(/\s+/g, " ");
}

/** The words of the card in Russian, read from the file the integration serves them from. */
async function russianStrings(): Promise<Record<string, string>> {
  const file = join(REPO_ROOT, "custom_components", "timerify", "translations", "ru.json");
  const translations = JSON.parse(await readFile(file, "utf8")) as {
    common: Record<string, string>;
  };
  return translations.common;
}

/** The cards of the view, in the order of the dashboard: the strict timer's, the loose one's. */
function cardsOf(page: Page): { strict: Locator; loose: Locator } {
  const cards = page.locator("timerify-card");
  return { strict: cards.nth(0), loose: cards.nth(1) };
}

/**
 * Taps the card, as a user does, and returns its pop-up once it is open. A card that has not
 * found its timer yet has no pop-up to open, so this waits for it first.
 */
async function openPopup(page: Page, card: Locator): Promise<Locator> {
  await expect(card.locator("timerify-card-popup")).toBeAttached();
  await tap(page, card);
  const dialog = card.locator("dialog");
  await expect(dialog).toBeVisible();
  return dialog;
}

const buttonOf = (dialog: Locator, name: string) =>
  dialog.getByRole("button", { name, exact: true });

test.describe("the pop-up in Home Assistant", () => {
  test.beforeEach(async ({ page, openDashboard }) => {
    await openDashboard(page, "popup");
    await expect(page.locator("timerify-card")).toHaveCount(2);
  });

  test("runs a preset, adds and takes off time, and stops", async ({ page, state, ws }) => {
    const { strict: entities } = state.timers;
    const dialog = await openPopup(page, cardsOf(page).strict);
    const minutesLeft = async () => (await ws.state(entities.run_for))?.state;

    await buttonOf(dialog, "45 min").click();
    await expect.poll(minutesLeft).toBe("45");
    await expect.poll(async () => (await ws.state(entities.target))?.state).toBe("on");
    // The pop-up shows the countdown it has started, to the end Timerify gave it, and is still
    // open. (The time left is the browser's clock against that end, which the test does not
    // pin: the clocks of the browser and of Home Assistant are not the test's business.)
    const end = Date.parse(String((await ws.state(entities.ends_at))?.state));
    expect(end, "Ends at should hold the end of the countdown").not.toBeNaN();
    await expect(dialog.getByText(/^\d+:\d\d$/)).toBeVisible();
    await expect(
      dialog.getByText(`until ${clockText("en", "h12", end)}`, { exact: true }),
    ).toBeVisible();

    await buttonOf(dialog, "Add 5 min").click();
    await expect.poll(minutesLeft).toBe("50");

    await buttonOf(dialog, "Take off 5 min").click();
    await expect.poll(minutesLeft).toBe("45");

    await buttonOf(dialog, "Stop").click();
    await expect.poll(minutesLeft).toBe("0");
    await expect.poll(async () => (await ws.state(entities.target))?.state).toBe("off");
    await expect(buttonOf(dialog, "Stop")).toBeDisabled();
    await expect(buttonOf(dialog, "Take off 5 min")).toBeDisabled();
    await expect(dialog).toBeVisible();
  });

  test("switches an interval off and on", async ({ page, state, ws }) => {
    const { switch: interval, start } = state.interval;
    const dialog = await openPopup(page, cardsOf(page).strict);
    const toggle = dialog.getByRole("switch");
    const switchState = async () => (await ws.state(interval))?.state;
    await expect(toggle).toContainText(start);
    await expect(toggle).toHaveAttribute("aria-checked", "true");

    await toggle.click();

    await expect.poll(switchState).toBe("off");
    await expect(toggle).toHaveAttribute("aria-checked", "false");
    await toggle.click();
    await expect.poll(switchState).toBe("on");
    await expect(toggle).toHaveAttribute("aria-checked", "true");
    await expect(dialog).toBeVisible();
  });

  test("cancels a pending command", async ({ page, state, ws }) => {
    const { loose: entities } = state.timers;
    const dialog = await openPopup(page, cardsOf(page).loose);
    const commands = await ws.state(entities.next_command);
    const due = Date.parse(String(commands?.state));
    expect(due, "Next command should hold the time of the fixture's command").not.toBeNaN();
    await expect(dialog.getByText("Pending commands", { exact: true })).toBeVisible();
    await expect(
      dialog.getByText(`On at ${clockText("en", "h12", due)}`, { exact: true }),
    ).toBeVisible();

    await buttonOf(dialog, "Cancel").click();

    await expect.poll(async () => (await ws.state(entities.next_command))?.state).toBe("unknown");
    // Nothing is pending any more: the section is gone, the pop-up is still open.
    await expect(dialog.getByText("Pending commands", { exact: true })).toHaveCount(0);
    await expect(dialog).toBeVisible();
  });

  test("an admin reaches the timer's settings", async ({ page, state }) => {
    const { strict: entities } = state.timers;
    const dialog = await openPopup(page, cardsOf(page).strict);

    await dialog.getByRole("link", { name: "Settings", exact: true }).click();

    await expect(page).toHaveURL(
      new RegExp(`/config/integrations/integration/timerify#config_entry=${entities.entry_id}$`),
    );
    // Home Assistant's own page of the integration, with the timer's row picked out.
    const row = page.locator(`ha-config-entry-row[data-entry-id="${entities.entry_id}"]`);
    await expect(row).toBeVisible();
    await expect(row).toHaveClass(/highlight/);
  });

  test("closes on the backdrop, but not when a press from inside ends there", async ({
    page,
  }) => {
    const dialog = await openPopup(page, cardsOf(page).strict);
    const title = await dialog.getByRole("heading", { level: 2 }).boundingBox();
    if (title === null) {
      throw new Error("The pop-up's title should be on the page");
    }
    // Selecting the title's text with a drag that ends on the backdrop, outside the dialog.
    await page.mouse.move(title.x + 4, title.y + title.height / 2);
    await page.mouse.down();
    await page.mouse.move(2, 2, { steps: 5 });
    await page.mouse.up();
    await expect(dialog).toBeVisible();

    // A click on the backdrop closes it.
    await page.mouse.click(2, 2);

    await expect(dialog).toBeHidden();
  });

  test.describe("in Russian", () => {
    test.use({ locale: "ru-RU" });

    test("speaks Russian", async ({ page, state, ws }) => {
      const ru = await russianStrings();
      const { strict: entities } = state.timers;
      await ws.callService("number", "set_value", { value: 45 }, { entity_id: entities.run_for });
      const end = Date.parse(String((await ws.state(entities.ends_at))?.state));
      expect(end, "Ends at should hold the end of the countdown").not.toBeNaN();

      const dialog = await openPopup(page, cardsOf(page).strict);

      await expect(page.locator("html")).toHaveAttribute("lang", "ru");
      await expect(buttonOf(dialog, ru.card_stop)).toBeVisible();
      // The preset as Russian writes 45 minutes: Intl's own, not an English word.
      const minutes = new Intl.NumberFormat("ru", {
        style: "unit",
        unit: "minute",
        unitDisplay: "short",
        useGrouping: false,
      }).format(45);
      await expect(buttonOf(dialog, minutes)).toBeVisible();
      // Russian counts a day of twenty-four hours.
      const until = ru.card_until.replace("{time}", clockText("ru", "h23", end));
      await expect(dialog.getByText(until, { exact: true })).toBeVisible();
    });
  });
});

test("a user who is not an admin sees no settings link and still runs the timer", async ({
  page,
  openDashboard,
  state,
  ws,
}) => {
  const viewer = await hassWs(state, "viewer");
  try {
    // The test would prove nothing for an administrator.
    expect((await viewer.currentUser()).is_admin).toBe(false);
  } finally {
    viewer.close();
  }
  await openDashboard(page, "popup", { user: "viewer" });
  await expect(page.locator("timerify-card")).toHaveCount(2);
  const dialog = await openPopup(page, cardsOf(page).strict);

  // The pop-up has its content, so that the missing link is the pop-up's choice.
  await expect(buttonOf(dialog, "30 min")).toBeVisible();
  await expect(dialog.getByRole("link")).toHaveCount(0);
  await buttonOf(dialog, "30 min").click();

  await expect
    .poll(async () => (await ws.state(state.timers.strict.run_for))?.state)
    .toBe("30");
});
