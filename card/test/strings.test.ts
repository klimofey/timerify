import { describe, expect, it, vi } from "vitest";
import { common as english } from "../../custom_components/timerify/translations/en.json";
import { common as russian } from "../../custom_components/timerify/translations/ru.json";
import { fakeHass } from "./fake-hass";

/** The strings module as a page that has just opened has it: nothing loaded yet. */
async function freshStrings() {
  vi.resetModules();
  return import("../src/strings");
}

describe("the strings of the card", () => {
  it("loads its strings in the user's language", async () => {
    const { lastLoaded, loadStrings, t } = await freshStrings();
    const hass = fakeHass({ language: "ru", stringsLoaded: false });

    await loadStrings(hass);

    expect(hass.translationLoads).toEqual([["common", "timerify"]]);
    expect(t(lastLoaded(), "card_close")).toBe(russian.card_close);
  });

  it("loads them once for a language, and again when the language changes", async () => {
    const { loadStrings } = await freshStrings();
    const englishPage = fakeHass();
    const russianPage = fakeHass({ language: "ru" });

    await loadStrings(englishPage);
    await loadStrings(englishPage.state("light.kitchen", "on"));
    expect(englishPage.translationLoads).toHaveLength(1);

    await loadStrings(russianPage);
    await loadStrings(russianPage);
    expect(russianPage.translationLoads).toHaveLength(1);
  });

  it("speaks English before any strings arrive", async () => {
    const { lastLoaded, t } = await freshStrings();

    expect(lastLoaded()).toBeUndefined();
    expect(t(undefined, "card_close")).toBe(english.card_close);
    expect(t(undefined, "card_entity_not_found", { entity: "number.boiler_run_for" })).toBe(
      "Entity not found: number.boiler_run_for",
    );
    expect(t(fakeHass({ language: "ru", stringsLoaded: false }), "card_close")).toBe(
      english.card_close,
    );
  });

  it("fills in the blanks of the user's language", async () => {
    const { t } = await freshStrings();

    expect(t(fakeHass({ language: "ru" }), "card_entity_not_found", { entity: "number.x" })).toBe(
      russian.card_entity_not_found.replace("{entity}", "number.x"),
    );
  });

  it("stays in English when the strings cannot be loaded, and tries again later", async () => {
    const { lastLoaded, loadStrings, t } = await freshStrings();
    const hass = fakeHass({ language: "ru", stringsLoaded: false });
    hass.rejectNextTranslations(new Error("connection lost"));

    await loadStrings(hass);
    expect(lastLoaded()).toBeUndefined();
    expect(t(lastLoaded(), "card_close")).toBe(english.card_close);

    await loadStrings(hass);
    expect(t(lastLoaded(), "card_close")).toBe(russian.card_close);
    expect(hass.translationLoads).toHaveLength(2);
  });

  it("tells whoever listens when strings have arrived", async () => {
    const { loadStrings, onStringsLoaded } = await freshStrings();
    const listener = vi.fn();
    onStringsLoaded(listener);

    await loadStrings(fakeHass({ language: "ru" }));

    expect(listener).toHaveBeenCalledOnce();
  });
});
