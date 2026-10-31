import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { common as english } from "../../custom_components/timerify/translations/en.json";
import { common as russian } from "../../custom_components/timerify/translations/ru.json";
import { ConfigError, DEFAULT_PRESETS, parseConfig } from "../src/config";
import { NUMBER, START, fakeHass } from "./fake-hass";
import { mountCard } from "./mount";

/** The error `parseConfig` raises for this config; the scenario fails if it accepts it. */
function refusal(raw: unknown): ConfigError {
  try {
    parseConfig(raw);
  } catch (error) {
    if (error instanceof ConfigError) {
      return error;
    }
    throw error;
  }
  throw new Error(`The config ${JSON.stringify(raw)} was accepted`);
}

describe("the config of the card", () => {
  it("refuses a config without a Run for number", () => {
    for (const raw of [{}, { entity: "switch.boiler" }, { entity: 5 }, null, undefined]) {
      expect(refusal(raw).key).toBe("card_error_entity");
    }
  });

  it("says what is wrong in English before any strings are loaded", () => {
    expect(refusal({}).message).toBe(english.card_error_entity);
  });

  it("defaults to the pill layout and the default presets", () => {
    expect(parseConfig({ entity: NUMBER })).toStrictEqual({
      entity: NUMBER,
      layout: "pill",
      presets: [15, 30, 45, 60, 120],
    });
    expect([...DEFAULT_PRESETS]).toEqual([15, 30, 45, 60, 120]);
  });

  it("takes the round layout, and refuses any other", () => {
    expect(parseConfig({ entity: NUMBER, layout: "round" }).layout).toBe("round");
    expect(refusal({ entity: NUMBER, layout: "square" }).key).toBe("card_error_layout");
  });

  it("keeps the name and the icon it is given", () => {
    expect(parseConfig({ entity: NUMBER, name: "Water", icon: "mdi:water-boiler" })).toMatchObject({
      name: "Water",
      icon: "mdi:water-boiler",
    });
  });

  it("refuses presets that are not whole minutes from 1 to 1440", () => {
    for (const presets of [[], [0], [1.5], ["x"], ["1.5"], [1441], [15, 0], 15, "15"]) {
      expect(refusal({ entity: NUMBER, presets }).key, JSON.stringify(presets)).toBe(
        "card_error_presets",
      );
    }
    expect(parseConfig({ entity: NUMBER, presets: [1, 1440] }).presets).toEqual([1, 1440]);
  });

  it("takes presets as the visual editor writes them", () => {
    expect(parseConfig({ entity: NUMBER, presets: ["15", "30", 15] }).presets).toEqual([15, 30]);
  });

  it("keeps presets in the order they are given", () => {
    expect(parseConfig({ entity: NUMBER, presets: [60, 5, 30] }).presets).toEqual([60, 5, 30]);
  });

  it("has no quick chip unless it is given", () => {
    expect(parseConfig({ entity: NUMBER })).not.toHaveProperty("chip");
    expect(parseConfig({ entity: NUMBER, chip: undefined })).not.toHaveProperty("chip");
  });

  it("takes a quick chip of whole minutes, as the visual editor writes it", () => {
    expect(parseConfig({ entity: NUMBER, chip: 15 }).chip).toBe(15);
    expect(parseConfig({ entity: NUMBER, chip: "15" }).chip).toBe(15);
    expect(parseConfig({ entity: NUMBER, chip: 1 }).chip).toBe(1);
    expect(parseConfig({ entity: NUMBER, chip: 1440 }).chip).toBe(1440);
  });

  it("refuses a quick chip that is not whole minutes from 1 to 1440", () => {
    for (const chip of [0, -5, 1441, 1.5, "1.5", "x", "", null, [15], true]) {
      expect(refusal({ entity: NUMBER, chip }).key, JSON.stringify(chip)).toBe("card_error_chip");
    }
  });

  it("ignores what Home Assistant adds to a card", () => {
    const raw = {
      type: "custom:timerify-card",
      entity: NUMBER,
      grid_options: { columns: 6 },
      visibility: [{ condition: "screen", media_query: "(min-width: 600px)" }],
    };
    expect(parseConfig(raw)).toStrictEqual({
      entity: NUMBER,
      layout: "pill",
      presets: [15, 30, 45, 60, 120],
    });
  });
});

describe("the errors of a card on a page that is not in English", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(START);
  });

  afterEach(() => {
    document.body.replaceChildren();
    vi.useRealTimers();
  });

  it("speaks the language a card already loaded in its config errors", async () => {
    const russianPage = fakeHass({ language: "ru", stringsLoaded: false });
    await mountCard(russianPage);

    const second = document.createElement("timerify-card");
    expect(() => second.setConfig({ entity: NUMBER, presets: [0] })).toThrow(
      russian.card_error_presets,
    );
  });

  it("words the error of a quick chip in that language too", async () => {
    await mountCard(fakeHass({ language: "ru", stringsLoaded: false }));

    expect(refusal({ entity: NUMBER, chip: 1441 }).message).toBe(russian.card_error_chip);
  });
});
