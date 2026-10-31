// The words of the card, for the tests that read what a page says.
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { REPO_ROOT } from "./constants";

/** The words of the card in a language, read from the file the integration serves them from. */
export async function stringsIn(language: "en" | "ru"): Promise<Record<string, string>> {
  const file = join(REPO_ROOT, "custom_components", "timerify", "translations", `${language}.json`);
  const translations = JSON.parse(await readFile(file, "utf8")) as {
    common: Record<string, string>;
  };
  return translations.common;
}
