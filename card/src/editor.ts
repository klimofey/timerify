// The card's visual editor, and the card's first appearance in the card picker.
//
// The editor is the frontend's own form. The card gives Home Assistant a schema of selectors
// (`getConfigForm`, the documented way for a custom card to have an editor); the frontend draws
// the fields, keeps the card's config in step with them, and asks `assertConfig` whether the
// card can work with what they hold. Nothing here renders anything.
import { DEFAULT_PRESETS, MAX_MINUTES, assertShape } from "./config";
import { formatMinutes } from "./format";
import type { HomeAssistant, Localize } from "./hass";
import { lastLoaded, loadStrings, localizeName, t, type StringKey } from "./strings";

/** The word each field is labelled with. */
const LABELS = {
  entity: "card_editor_entity",
  layout: "card_editor_layout",
  name: "card_editor_name",
  icon: "card_editor_icon",
  presets: "card_editor_presets",
  chip: "card_editor_chip",
} as const satisfies Record<string, StringKey>;

interface Option {
  value: string;
  label: string;
}

/** A field of the form: the part of the frontend's `ha-form` schema that the card uses. */
interface SelectorField {
  name: keyof typeof LABELS;
  required?: boolean;
  selector:
    | { entity: { filter: { integration: string; domain: string } } }
    | { select: { options: Option[]; multiple?: boolean; custom_value?: boolean } }
    | { text: Record<string, never> }
    | { icon: Record<string, never> }
    | { number: { min: number; max: number; mode: "box" } };
}

/** Fields side by side. The frontend names a grid with the empty string. */
interface GridField {
  name: "";
  type: "grid";
  schema: SelectorField[];
}

/** What `getConfigForm` hands Home Assistant; the frontend's `LovelaceConfigForm`. */
export interface LovelaceConfigForm {
  schema: (SelectorField | GridField)[];
  /** Throws, with a message for the user, when the form cannot show the config at all. */
  assertConfig(config: unknown): void;
  computeLabel(field: { name: string }, localize: Localize): string;
  computeHelper(field: { name: string }): string | undefined;
}

const isLabelled = (name: string): name is keyof typeof LABELS => Object.hasOwn(LABELS, name);

const ENGLISH = { locale: { language: "en" } };

/**
 * What the editor's own words are said in: the language of the last strings a card loaded, and
 * English before any card has. `getConfigForm` is given no `hass`, and the form that Home
 * Assistant builds is given no way to translate the labels of a select's options, so these
 * come from the card.
 */
function speaking(): { locale: { language: string } } {
  return lastLoaded() ?? ENGLISH;
}

/** The default presets, in words: "15 min, 30 min, 45 min, 1 hr, and 2 hr" in English. */
function defaultPresetsText(): string {
  const language = speaking();
  return new Intl.ListFormat(language.locale.language, {
    style: "long",
    type: "conjunction",
  }).format(DEFAULT_PRESETS.map((minutes) => formatMinutes(language, minutes)));
}

/**
 * The form of the visual editor. Home Assistant awaits it when the user opens the editor, and
 * builds the form from it once.
 */
export async function getConfigForm(): Promise<LovelaceConfigForm> {
  const words = lastLoaded();
  return {
    schema: [
      {
        name: "entity",
        required: true,
        // Timerify has one kind of number: the one a timer runs for.
        selector: { entity: { filter: { integration: "timerify", domain: "number" } } },
      },
      {
        name: "layout",
        selector: {
          select: {
            options: [
              { value: "pill", label: t(words, "card_editor_layout_pill") },
              { value: "round", label: t(words, "card_editor_layout_round") },
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
            // The form writes what it is given as text, and so does a preset the user types.
            options: DEFAULT_PRESETS.map((minutes) => ({
              value: String(minutes),
              label: formatMinutes(speaking(), minutes),
            })),
          },
        },
      },
      // The label says that these are minutes, so the field has no unit of its own.
      { name: "chip", selector: { number: { min: 1, max: MAX_MINUTES, mode: "box" } } },
    ],
    // Only the shape: a value that is wrong stays in the form, and the card's own check of
    // it (`setConfig`, which the preview runs) tells the user what it should be.
    assertConfig: assertShape,
    computeLabel: ({ name }, localize) =>
      isLabelled(name) ? localize(localizeName(LABELS[name])) : "",
    computeHelper: ({ name }) =>
      name === "presets"
        ? t(lastLoaded(), "card_editor_presets_helper", { presets: defaultPresetsText() })
        : undefined,
  };
}

/** The config of a card that has just been picked. */
export interface StubConfig {
  entity: string;
  layout: "pill";
  presets: string[];
}

/**
 * The config a new card starts with, when the user picks it in the card picker: the first
 * timer of Timerify, with its layout and presets written out so that the editor shows them.
 * `entities` are the entities the dashboard does not use yet and `entitiesFallback` those it
 * does (the picker leaves out the ones that are unavailable); when neither has a timer, any
 * timer of Timerify will do, and a home without one gets no entity, which the card asks the
 * user for. The words of the editor are on their way once this has been asked.
 */
export function getStubConfig(
  hass: HomeAssistant,
  entities: string[],
  entitiesFallback: string[],
): StubConfig {
  void loadStrings(hass);
  const isRunForNumber = (entityId: string) => {
    const entry = hass.entities[entityId];
    return entry?.platform === "timerify" && entry.translation_key === "run_for";
  };
  const firstTimer = (entityIds: string[]) => entityIds.filter(isRunForNumber).sort()[0];
  return {
    entity:
      firstTimer(entities) ??
      firstTimer(entitiesFallback) ??
      firstTimer(Object.keys(hass.entities)) ??
      "",
    layout: "pill",
    presets: DEFAULT_PRESETS.map(String),
  };
}
