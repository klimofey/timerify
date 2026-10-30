// The words of the card. They live in `translations/<language>.json` under `common`, where
// Home Assistant's backend serves them in the user's language; the English file is also built
// into the bundle, so that a key that does not exist fails the type check, and so that the
// words are there before the frontend has delivered any.
import { common } from "../../custom_components/timerify/translations/en.json";
import type { HomeAssistant } from "./hass";

export type StringKey = keyof typeof common;

type Blanks = Record<string, string | number>;

const CATEGORY = "common";
const INTEGRATION = "timerify";
const KEY_PREFIX = `component.${INTEGRATION}.${CATEGORY}.`;

function fill(text: string, blanks: Blanks | undefined): string {
  return text.replace(/\{(\w+)\}/g, (blank, name: string) => String(blanks?.[name] ?? blank));
}

/**
 * The text of `key`: in the language of `hass` once its strings have been loaded, in English
 * before that. `hass` is the one `lastLoaded` gives, or the card's own once the frontend has
 * handed it a new `localize`.
 */
export function t(
  hass: Pick<HomeAssistant, "localize"> | undefined,
  key: StringKey,
  blanks?: Blanks,
): string {
  return hass?.localize(KEY_PREFIX + key, blanks) || fill(common[key], blanks);
}

let language: string | undefined;
let loading: Promise<void> = Promise.resolve();
let loaded: HomeAssistant | undefined;
const listeners = new Set<() => void>();

/**
 * Loads the card's strings in the language of `hass`, once for each language: the frontend
 * delivers them to the cards as a new `localize` of `hass`. A load that fails leaves English
 * in place and is tried again by the next call.
 */
export function loadStrings(hass: HomeAssistant): Promise<void> {
  if (hass.language !== language) {
    language = hass.language;
    loading = fetchStrings(hass, hass.language);
  }
  return loading;
}

async function fetchStrings(hass: HomeAssistant, forLanguage: string): Promise<void> {
  let localize;
  try {
    localize = await hass.loadBackendTranslation(CATEGORY, INTEGRATION);
  } catch {
    if (language === forLanguage) {
      language = undefined;
    }
    return;
  }
  if (language !== forLanguage) {
    return;
  }
  // The `hass` that was asked is older than the strings, which reach it only as a new one.
  loaded = { ...hass, localize };
  listeners.forEach((listener) => listener());
}

/**
 * The `hass` the strings were last loaded with, whose `localize` holds them; for the words
 * that are needed where there is no `hass` of the card's own, such as the error of a config.
 */
export function lastLoaded(): HomeAssistant | undefined {
  return loaded;
}

/** Calls `listener` whenever strings have been loaded. */
export function onStringsLoaded(listener: () => void): void {
  listeners.add(listener);
}
