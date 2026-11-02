import { describe, expect, it, vi } from "vitest";
import { common as english } from "../../custom_components/timerify/translations/en.json";
import { common as russian } from "../../custom_components/timerify/translations/ru.json";
import * as registered from "../src/editor";
import type { RegistryEntry } from "../src/hass";
import { TimerifyCard } from "../src/timerify-card";
import { NUMBER, fakeHass, localizeFor, type FakeHass } from "./fake-hass";

/**
 * The editor and the strings as a page that has just opened has them: nothing loaded yet. (The
 * card the page defined keeps the instances that were there when it was defined.)
 */
async function freshEditor() {
  vi.resetModules();
  const [editor, strings] = await Promise.all([import("../src/editor"), import("../src/strings")]);
  return { ...editor, ...strings };
}

const DEFAULT_PRESETS = [15, 30, 45, 60, 120];

type Words = Record<string, string>;

/** The six choices of a press, as the form offers them, in the words of `words`. */
const pressOptions = (words: Words) => [
  { value: "popup", label: words["card_editor_press_popup"] },
  { value: "run", label: words["card_editor_press_run"] },
  { value: "stop", label: words["card_editor_press_stop"] },
  { value: "run_or_stop", label: words["card_editor_press_run_or_stop"] },
  { value: "action", label: words["card_editor_press_action"] },
  { value: "none", label: words["card_editor_press_none"] },
];

/** The group of the form that holds the three presses, each followed by its action. */
const interactions = (words: Words) => ({
  name: "interactions",
  type: "expandable",
  flatten: true,
  icon: "mdi:gesture-tap",
  schema: ["tap", "double_tap", "hold"].flatMap((press) => [
    { name: press, selector: { select: { options: pressOptions(words) } } },
    { name: `${press}_action`, selector: { ui_action: { default_action: "more-info" } } },
  ]),
});

/** What Intl writes for a length of time, in a language, as the presets are labelled. */
function lengths(language: string) {
  const unit = (count: number, name: "hour" | "minute") =>
    new Intl.NumberFormat(language, {
      style: "unit",
      unit: name,
      unitDisplay: "short",
      useGrouping: false,
    }).format(count);
  return {
    presets: [
      unit(15, "minute"),
      unit(30, "minute"),
      unit(45, "minute"),
      unit(1, "hour"),
      unit(2, "hour"),
    ],
    listOf: (items: string[]) =>
      new Intl.ListFormat(language, { style: "long", type: "conjunction" }).format(items),
  };
}

/** A registry entry of Timerify's, as the frontend's `hass.entities` holds it. */
const timerifyEntry = (entity_id: string, translation_key: string): RegistryEntry => ({
  entity_id,
  platform: "timerify",
  translation_key,
});

/**
 * Entities that look like a timer to a careless filter, and sort before any timer of the
 * tests: a number of another integration with the same translation key, a number of
 * Timerify that is not the one a timer runs for, and one of its sensors.
 */
const LOOK_ALIKES: Record<string, RegistryEntry> = {
  "number.a_demo_run_for": {
    ...timerifyEntry("number.a_demo_run_for", "run_for"),
    platform: "demo",
  },
  "number.a_demo_volume": { entity_id: "number.a_demo_volume", platform: "demo" },
  "number.a_other_timerify": timerifyEntry("number.a_other_timerify", "other"),
  "sensor.a_ends_at": timerifyEntry("sensor.a_ends_at", "ends_at"),
};

/** A page whose registry has these "Run for" numbers of Timerify, besides the look-alikes. */
function pageWithTimers(...numbers: string[]): FakeHass {
  const entities: Record<string, RegistryEntry> = { ...LOOK_ALIKES };
  for (const number of numbers) {
    entities[number] = timerifyEntry(number, "run_for");
  }
  return fakeHass({ timers: [] }).with({ entities });
}

describe("the form of the visual editor", () => {
  it("offers Timerify's Run for numbers, a layout, a name, an icon, presets, a chip, the Turn off button, the Mushroom style and the presses", async () => {
    const { getConfigForm } = await freshEditor();

    const { schema } = await getConfigForm();

    expect(schema).toStrictEqual([
      {
        name: "entity",
        required: true,
        selector: { entity: { filter: { integration: "timerify", domain: "number" } } },
      },
      {
        name: "layout",
        selector: {
          select: {
            options: [
              { value: "pill", label: english.card_editor_layout_pill },
              { value: "round", label: english.card_editor_layout_round },
            ],
          },
        },
      },
      {
        name: "",
        type: "grid",
        schema: [
          { name: "name", selector: { text: {} } },
          { name: "icon", selector: { icon: {} } },
        ],
      },
      {
        name: "presets",
        selector: {
          select: {
            multiple: true,
            custom_value: true,
            options: DEFAULT_PRESETS.map((minutes, index) => ({
              value: String(minutes),
              label: lengths("en").presets[index],
            })),
          },
        },
      },
      // No unit of its own: its label says minutes.
      { name: "chip", selector: { number: { min: 1, max: 1440, mode: "box" } } },
      { name: "show_turn_off", selector: { boolean: {} } },
      { name: "mushroom", selector: { boolean: {} } },
      interactions(english),
    ]);
    expect(lengths("en").presets).toEqual(["15 min", "30 min", "45 min", "1 hr", "2 hr"]);
  });

  it("labels its fields and options in the user's language", async () => {
    const { getConfigForm, loadStrings } = await freshEditor();
    await loadStrings(fakeHass({ language: "ru" }));

    const form = await getConfigForm();

    const localize = localizeFor("ru");
    const labelled = [
      ...["entity", "layout", "name", "icon", "presets", "chip", "show_turn_off", "mushroom"],
      ...["interactions", "tap", "double_tap", "hold"],
      ...["tap_action", "double_tap_action", "hold_action"],
    ] as const;
    for (const field of labelled) {
      expect(form.computeLabel({ name: field }, localize), field).toBe(
        russian[`card_editor_${field}`],
      );
    }
    const russianLengths = lengths("ru");
    const [, layout, , presets, , , , group] = form.schema;
    expect(group).toStrictEqual(interactions(russian));
    expect(layout).toMatchObject({
      selector: {
        select: {
          options: [
            { value: "pill", label: russian.card_editor_layout_pill },
            { value: "round", label: russian.card_editor_layout_round },
          ],
        },
      },
    });
    expect(presets).toMatchObject({
      selector: {
        select: {
          options: DEFAULT_PRESETS.map((minutes, index) => ({
            value: String(minutes),
            label: russianLengths.presets[index],
          })),
        },
      },
    });
    expect(form.computeHelper({ name: "presets" }, localizeFor("ru"))).toBe(
      russian.card_editor_presets_helper.replace(
        "{presets}",
        russianLengths.listOf(russianLengths.presets),
      ),
    );
    // Not a word of the English file is glued to a number.
    expect(form.computeHelper({ name: "presets" }, localizeFor("ru"))).not.toMatch(/\b(min|hr)\b/);
  });

  it("words the presses as Home Assistant's own editor does", async () => {
    const { getConfigForm, loadStrings } = await freshEditor();
    await loadStrings(fakeHass());

    const form = await getConfigForm();

    const localize = localizeFor("en");
    expect(
      Object.fromEntries(
        ["interactions", "tap", "double_tap", "hold"].map((name) => [
          name,
          form.computeLabel({ name }, localize),
        ]),
      ),
    ).toEqual({
      interactions: "Interactions",
      tap: "Tap behavior",
      double_tap: "Double tap behavior",
      hold: "Hold behavior",
    });
    expect(english.card_editor_press_none).toBe("Nothing");
  });

  it("speaks English until a card has loaded the user's language", async () => {
    const { getConfigForm, lastLoaded } = await freshEditor();
    expect(lastLoaded()).toBeUndefined();

    const form = await getConfigForm();

    expect(form.computeHelper({ name: "presets" }, localizeFor("en"))).toBe(
      english.card_editor_presets_helper.replace(
        "{presets}",
        lengths("en").listOf(lengths("en").presets),
      ),
    );
    expect(form.computeHelper({ name: "presets" }, localizeFor("en"))).toBe(
      "Leave empty for 15 min, 30 min, 45 min, 1 hr, and 2 hr",
    );
    // The label is the frontend's `localize` of the page; before the strings reach it, it says
    // nothing, and the editor falls back on its own words.
    expect(form.computeLabel({ name: "entity" }, fakeHass({ stringsLoaded: false }).localize)).toBe(
      "",
    );
  });

  it("words the presets helper in the editor's language before any card has loaded", async () => {
    const { getConfigForm, lastLoaded } = await freshEditor();
    expect(lastLoaded()).toBeUndefined();

    const form = await getConfigForm();

    const russianLengths = lengths("ru");
    expect(form.computeHelper({ name: "presets" }, localizeFor("ru"))).toBe(
      russian.card_editor_presets_helper.replace(
        "{presets}",
        russianLengths.listOf(russianLengths.presets),
      ),
    );
  });

  it("says which presses use a Home Assistant action in the editor's language before any card has loaded", async () => {
    const { getConfigForm, lastLoaded } = await freshEditor();
    expect(lastLoaded()).toBeUndefined();

    const form = await getConfigForm();

    for (const field of ["tap_action", "double_tap_action", "hold_action"]) {
      expect(form.computeHelper({ name: field }, localizeFor("ru")), field).toBe(
        russian.card_editor_action_helper,
      );
    }
  });

  it("words the helpers in the language of the editor, whatever the last card loaded", async () => {
    const { getConfigForm, loadStrings } = await freshEditor();
    await loadStrings(fakeHass({ language: "ru" }));

    const form = await getConfigForm();

    const englishLengths = lengths("en");
    expect(form.computeHelper({ name: "presets" }, localizeFor("en"))).toBe(
      english.card_editor_presets_helper.replace(
        "{presets}",
        englishLengths.listOf(englishLengths.presets),
      ),
    );
    expect(form.computeHelper({ name: "hold_action" }, localizeFor("en"))).toBe(
      english.card_editor_action_helper,
    );
    // The names of the options are all the form can take from the card: they stay in the
    // language of the last card, which is not the editor's here.
    const [, layout] = form.schema;
    expect(layout).toMatchObject({
      selector: { select: { options: [{ label: russian.card_editor_layout_pill }, {}] } },
    });
  });

  it("words the helpers in English until the editor's strings have reached the frontend", async () => {
    const { getConfigForm, loadStrings } = await freshEditor();
    await loadStrings(fakeHass({ language: "ru" }));
    const form = await getConfigForm();
    const unlocalized = fakeHass({ stringsLoaded: false }).localize;

    const englishLengths = lengths("en");
    expect(form.computeHelper({ name: "presets" }, unlocalized)).toBe(
      english.card_editor_presets_helper.replace(
        "{presets}",
        englishLengths.listOf(englishLengths.presets),
      ),
    );
    expect(form.computeHelper({ name: "tap_action" }, unlocalized)).toBe(
      english.card_editor_action_helper,
    );
  });

  it("explains the presets, and which presses use a Home Assistant action", async () => {
    const { getConfigForm } = await freshEditor();

    const form = await getConfigForm();

    for (const field of ["tap_action", "double_tap_action", "hold_action"]) {
      expect(form.computeHelper({ name: field }, localizeFor("en")), field).toBe(
        english.card_editor_action_helper,
      );
    }
    for (const field of [
      ...["entity", "layout", "name", "icon", "chip", "show_turn_off"],
      ...["interactions", "tap", ""],
    ]) {
      expect(form.computeHelper({ name: field }, localizeFor("en")), field).toBeUndefined();
    }
  });

  it("says in the user's language which presses use a Home Assistant action", async () => {
    const { getConfigForm, loadStrings } = await freshEditor();
    await loadStrings(fakeHass({ language: "ru" }));

    const form = await getConfigForm();

    expect(form.computeHelper({ name: "hold_action" }, localizeFor("ru"))).toBe(
      russian.card_editor_action_helper,
    );
  });

  it("refuses a config of the wrong kind, as the card does", async () => {
    const { getConfigForm } = await freshEditor();
    const { assertConfig } = await getConfigForm();
    const wrongKind = [
      [{ entity: 5 }, english.card_error_entity],
      [{ entity: NUMBER, layout: 1 }, english.card_error_layout],
      [{ entity: NUMBER, presets: "15" }, english.card_error_presets],
      [{ entity: NUMBER, presets: [{}] }, english.card_error_presets],
      [{ entity: NUMBER, presets: [15, null] }, english.card_error_presets],
      [{ entity: NUMBER, chip: true }, english.card_error_chip],
      [{ entity: NUMBER, show_turn_off: "yes" }, english.card_error_show_turn_off],
      [{ entity: NUMBER, show_turn_off: 1 }, english.card_error_show_turn_off],
      [{ entity: NUMBER, mushroom: "yes" }, english.card_error_mushroom],
      [{ entity: NUMBER, mushroom: 1 }, english.card_error_mushroom],
      [{ entity: NUMBER, tap: 5 }, english.card_error_press],
      [{ entity: NUMBER, hold: ["run"] }, english.card_error_press],
      [{ entity: NUMBER, hold_action: "more-info" }, english.card_error_action],
      [{ entity: NUMBER, tap_action: [{ action: "more-info" }] }, english.card_error_action],
    ] as const;

    for (const [config, message] of wrongKind) {
      expect(() => assertConfig(config), JSON.stringify(config)).toThrow(message);
      expect(() => new TimerifyCard().setConfig(config), JSON.stringify(config)).toThrow(message);
    }
    expect(() =>
      assertConfig({
        type: "custom:timerify-card",
        entity: NUMBER,
        layout: "round",
        presets: ["15", "30", 20],
        chip: 10,
        show_turn_off: true,
        mushroom: true,
        tap: "action",
        tap_action: { action: "more-info" },
        double_tap: "run",
        hold: "none",
      }),
    ).not.toThrow();
  });

  it("keeps the user in the form when a value is wrong, and leaves it to the card to say so", async () => {
    const { getConfigForm } = await freshEditor();
    const { assertConfig } = await getConfigForm();
    // What a user can type into the form: a preset of 0 or 1.5 or text, a chip out of range, and
    // what a hand-written config may hold: a layout the card does not have, no timer yet.
    const mistakes = [
      [{ entity: NUMBER, presets: ["15", "0"] }, english.card_error_presets],
      [{ entity: NUMBER, presets: ["1.5"] }, english.card_error_presets],
      [{ entity: NUMBER, presets: ["abc"] }, english.card_error_presets],
      [{ entity: NUMBER, chip: 1441 }, english.card_error_chip],
      [{ entity: NUMBER, chip: 0 }, english.card_error_chip],
      [{ entity: NUMBER, layout: "square" }, english.card_error_layout],
      [{ entity: NUMBER, tap: "toggle" }, english.card_error_press],
      [{ entity: NUMBER, hold: "" }, english.card_error_press],
      [{ entity: "sensor.boiler_ends_at" }, english.card_error_entity],
      [{ entity: "" }, english.card_error_entity],
      [{}, english.card_error_entity],
    ] as const;

    for (const [config, message] of mistakes) {
      expect(() => assertConfig(config), JSON.stringify(config)).not.toThrow();
      expect(() => new TimerifyCard().setConfig(config), JSON.stringify(config)).toThrow(message);
    }
  });

  it("lets the user take the last preset away, as the helper says", async () => {
    const { getConfigForm } = await freshEditor();
    const { assertConfig } = await getConfigForm();
    const config = { entity: NUMBER, presets: [] };

    // The form is not left, and the card takes the empty list for the defaults.
    expect(() => assertConfig(config)).not.toThrow();
    expect(() => new TimerifyCard().setConfig(config)).not.toThrow();
  });
});

describe("the card in the card picker", () => {
  it("picks the first unused timer for a new card, with the default presets", async () => {
    const { getStubConfig } = await freshEditor();
    const hass = pageWithTimers("number.c_run_for", "number.b_run_for", "number.a_run_for");

    const unused = getStubConfig(
      hass,
      [...Object.keys(LOOK_ALIKES), "number.b_run_for", "number.a_run_for"],
      ["number.c_run_for"],
    );
    const onlyUsed = getStubConfig(
      hass,
      [],
      [...Object.keys(LOOK_ALIKES), "number.c_run_for", "number.b_run_for"],
    );

    expect(unused).toStrictEqual({
      entity: "number.a_run_for",
      layout: "pill",
      // As the editor writes them: strings.
      presets: ["15", "30", "45", "60", "120"],
    });
    expect(onlyUsed.entity).toBe("number.b_run_for");
  });

  it("takes any timer of Timerify when the dashboard offers none", async () => {
    const { getStubConfig } = await freshEditor();
    const hass = pageWithTimers("number.c_run_for", "number.b_run_for");

    // The picker leaves out entities that are unavailable, so these lists can be empty
    // although the timers exist.
    expect(getStubConfig(hass, [], []).entity).toBe("number.b_run_for");
    expect(getStubConfig(hass, Object.keys(LOOK_ALIKES), []).entity).toBe("number.b_run_for");
  });

  it("asks for a timer when there is none", async () => {
    const { getStubConfig } = await freshEditor();
    const hass = pageWithTimers();

    const stub = getStubConfig(hass, Object.keys(LOOK_ALIKES), Object.keys(LOOK_ALIKES));

    expect(stub.entity).toBe("");
    expect(() => new TimerifyCard().setConfig(stub)).toThrow(english.card_error_entity);
  });

  it("starts loading the user's language, and does not wait for it", async () => {
    const { getStubConfig, lastLoaded } = await freshEditor();
    const hass = fakeHass({ language: "ru", stringsLoaded: false });

    getStubConfig(hass, [NUMBER], []);

    expect(hass.translationLoads).toEqual([["common", "timerify"]]);
    expect(lastLoaded()).toBeUndefined();
    await vi.waitFor(() => expect(lastLoaded()).toBeDefined());
  });

  it("is what Home Assistant finds on the card's class", async () => {
    const card = customElements.get("timerify-card") as typeof TimerifyCard | undefined;

    expect(card?.getConfigForm).toBe(registered.getConfigForm);
    expect(card?.getStubConfig).toBe(registered.getStubConfig);
  });
});

// Last in the file: Mushroom's cards stay defined once the first of these defines a stand-in for
// one of them, so the scenario in which Mushroom is missing comes first.
describe("the Mushroom style field of the form", () => {
  it("says Mushroom was not found, in the language of the editor, while its cards are not defined", async () => {
    const { getConfigForm } = await freshEditor();
    const form = await getConfigForm();

    expect(form.computeHelper({ name: "mushroom" }, localizeFor("en"))).toBe(
      english.card_editor_mushroom_missing,
    );
    expect(form.computeHelper({ name: "mushroom" }, localizeFor("ru"))).toBe(
      russian.card_editor_mushroom_missing,
    );
    // Before the page's strings have reached the form, it says it in English.
    const unlocalized = fakeHass({ stringsLoaded: false }).localize;
    expect(form.computeHelper({ name: "mushroom" }, unlocalized)).toBe(
      english.card_editor_mushroom_missing,
    );
  });

  it("says nothing once Mushroom's cards are defined", async () => {
    const { getConfigForm } = await freshEditor();
    const form = await getConfigForm();

    customElements.define("mushroom-entity-card", class extends HTMLElement {});

    expect(form.computeHelper({ name: "mushroom" }, localizeFor("en"))).toBeUndefined();
  });
});
