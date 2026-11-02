// The card's visual editor, and the card's first appearance in the card picker.
//
// The editor is the frontend's own form. The card gives Home Assistant a schema of selectors
// (`getConfigForm`, the documented way for a custom card to have an editor); the frontend draws
// the fields, keeps the card's config in step with them, and asks `assertConfig` whether the
// form can show what they hold; whether the card can work with it is the card's own `setConfig`.
// Nothing here renders anything.
import {
  DEFAULT_PRESETS,
  MAX_MINUTES,
  PRESS_CHOICES,
  assertShape,
  type PressChoice,
} from "./config";
import { formatMinutes } from "./format";
import type { HomeAssistant, Localize } from "./hass";
import { mushroomIsDefined } from "./mushroom";
import { lastLoaded, loadStrings, localizeName, t, type StringKey } from "./strings";

/** The word each field is labelled with. */
const LABELS = {
  entity: "card_editor_entity",
  layout: "card_editor_layout",
  name: "card_editor_name",
  icon: "card_editor_icon",
  presets: "card_editor_presets",
  chip: "card_editor_chip",
  show_turn_off: "card_editor_show_turn_off",
  mushroom: "card_editor_mushroom",
  interactions: "card_editor_interactions",
  tap: "card_editor_tap",
  double_tap: "card_editor_double_tap",
  hold: "card_editor_hold",
  tap_action: "card_editor_tap_action",
  double_tap_action: "card_editor_double_tap_action",
  hold_action: "card_editor_hold_action",
} as const satisfies Record<string, StringKey>;

/** The word each choice of a press is offered with. */
const PRESS_LABELS = {
  popup: "card_editor_press_popup",
  run: "card_editor_press_run",
  stop: "card_editor_press_stop",
  run_or_stop: "card_editor_press_run_or_stop",
  action: "card_editor_press_action",
  none: "card_editor_press_none",
} as const satisfies Record<PressChoice, StringKey>;

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
    | { number: { min: number; max: number; mode: "box" } }
    | { boolean: Record<string, never> }
    | { ui_action: { default_action: "more-info" } };
}

/** Fields side by side. The frontend names a grid with the empty string. */
interface GridField {
  name: "";
  type: "grid";
  schema: SelectorField[];
}

/**
 * A group the user opens to see its fields. Its fields are the card's own keys, not keys of
 * the group (`flatten`), and its title is the label of its name.
 */
interface ExpandableField {
  name: "interactions";
  type: "expandable";
  flatten: true;
  icon: string;
  schema: SelectorField[];
}

/** What `getConfigForm` hands Home Assistant; the frontend's `LovelaceConfigForm`. */
export interface LovelaceConfigForm {
  schema: (SelectorField | GridField | ExpandableField)[];
  /** Throws, with a message for the user, when the form cannot show the config at all. */
  assertConfig(config: unknown): void;
  computeLabel(field: { name: string }, localize: Localize): string;
  computeHelper(field: { name: string }, localize: Localize): string | undefined;
}

const isLabelled = (name: string): name is keyof typeof LABELS => Object.hasOwn(LABELS, name);

/** Whether the field is the Home Assistant action of a press. */
const isActionField = (name: string): boolean => name.endsWith("_action");

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
  const pressOptions = PRESS_CHOICES.map((choice) => ({
    value: choice,
    label: t(words, PRESS_LABELS[choice]),
  }));
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
      { name: "show_turn_off", selector: { boolean: {} } },
      { name: "mushroom", selector: { boolean: {} } },
      {
        name: "interactions",
        type: "expandable",
        flatten: true,
        icon: "mdi:gesture-tap",
        // Each press is followed by its action, which it uses when it is set to one. The
        // selector of an action cannot offer the pop-up or Timerify's own actions, so the
        // press is chosen first. An action that is not set is Home Assistant's default for
        // it, the more-info dialog of the entity.
        schema: [
          { name: "tap", selector: { select: { options: pressOptions } } },
          { name: "tap_action", selector: { ui_action: { default_action: "more-info" } } },
          { name: "double_tap", selector: { select: { options: pressOptions } } },
          { name: "double_tap_action", selector: { ui_action: { default_action: "more-info" } } },
          { name: "hold", selector: { select: { options: pressOptions } } },
          { name: "hold_action", selector: { ui_action: { default_action: "more-info" } } },
        ],
      },
    ],
    // Only the shape: a value that is wrong stays in the form, and the card's own check of
    // it (`setConfig`, which the preview runs) tells the user what it should be.
    assertConfig: assertShape,
    computeLabel: ({ name }, localize) =>
      isLabelled(name) ? localize(localizeName(LABELS[name])) : "",
    computeHelper: ({ name }, localize) => {
      if (name === "presets") {
        return t(lastLoaded(), "card_editor_presets_helper", { presets: defaultPresetsText() });
      }
      if (name === "mushroom") {
        // The one helper that is made with the `localize` the frontend gives, in English when it
        // does not have the card's strings yet.
        return mushroomIsDefined() ? undefined : t({ localize }, "card_editor_mushroom_missing");
      }
      return isActionField(name) ? t(lastLoaded(), "card_editor_action_helper") : undefined;
    },
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
