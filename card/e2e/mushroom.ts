// The real Mushroom, for the pictures of the documentation. A picture of the Mushroom style
// has to be taken with Mushroom on the page, so the screenshots load its release the way a user
// does who installs it by hand: the file is in the `www` folder of Home Assistant, which serves
// it at `/local`, and the dashboard has it as a resource. The release is downloaded once, from
// GitHub, into a folder that git ignores, and checked against the hash written here; the
// end-to-end tests never come here, and need neither the network nor Mushroom.
//
// Mushroom is Apache-2.0 licensed, and is not part of this repository: the file is fetched for
// the run and left in the folder of the cache.
//
// The tests that measure a card in the Mushroom style use a stand-in instead, `loadMushroom`:
// all the card looks for is one of Mushroom's cards being defined.
import { createHash } from "node:crypto";
import { mkdir, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { Page } from "@playwright/test";
import { LOCAL_DIR, REPO_ROOT } from "./constants";

/** The release that the pictures are taken with, and the hash of its `mushroom.js`. */
export const MUSHROOM_VERSION = "5.2.3";
export const MUSHROOM_SHA256 = "631668268e474d5357e0f17f161322499ea5c93a910431477e112653d7aa456b";

const RELEASE_URL = `https://github.com/piitaya/lovelace-mushroom/releases/download/v${MUSHROOM_VERSION}/mushroom.js`;
const CACHE_DIR = join(REPO_ROOT, "card", "e2e", ".mushroom");
const CACHE_FILE = join(CACHE_DIR, `mushroom-${MUSHROOM_VERSION}.js`);

const sha256 = (bytes: Buffer): string => createHash("sha256").update(bytes).digest("hex");

async function cached(): Promise<Buffer | undefined> {
  try {
    const bytes = await readFile(CACHE_FILE);
    return sha256(bytes) === MUSHROOM_SHA256 ? bytes : undefined;
  } catch {
    return undefined;
  }
}

/**
 * The bytes of the pinned release of Mushroom: from the cache when it holds them, else from
 * GitHub, which is then written to the cache. A download that does not have the pinned hash is
 * an error, and nothing of it is kept.
 */
export async function mushroomBundle(): Promise<Buffer> {
  const known = await cached();
  if (known !== undefined) {
    return known;
  }
  const response = await fetch(RELEASE_URL);
  if (!response.ok) {
    throw new Error(`GitHub answered ${response.status} for ${RELEASE_URL}`);
  }
  const bytes = Buffer.from(await response.arrayBuffer());
  const got = sha256(bytes);
  if (got !== MUSHROOM_SHA256) {
    throw new Error(
      `${RELEASE_URL} has the hash ${got}, not the ${MUSHROOM_SHA256} that this test is pinned to`,
    );
  }
  await mkdir(CACHE_DIR, { recursive: true });
  // Written whole or not at all, so that a run that stops half way leaves no broken file.
  const partial = `${CACHE_FILE}.partial`;
  await writeFile(partial, bytes);
  await rename(partial, CACHE_FILE);
  return bytes;
}

/** What Mushroom does on a page: its cards become known to the browser, after ours did. */
export const loadMushroom = (page: Page) =>
  page.evaluate(() => customElements.define("mushroom-entity-card", class extends HTMLElement {}));

/** Mushroom in the folder that Home Assistant serves: where the dashboard finds it. */
export interface InstalledMushroom {
  /** The address of the file on Home Assistant's own origin, as a dashboard's resource has it. */
  url: string;
  remove(): Promise<void>;
}

/**
 * Puts the bytes into the `www` folder of the Home Assistant of this run, the way a user
 * installs Mushroom by hand. The file is named by the release, so that nothing else of the
 * folder is in its way. Home Assistant serves `/local` only when the folder was there as it
 * started, which `scripts.e2e.hass up` takes care of; a folder that is not there is an
 * error that says so, not a resource that quietly fails to load.
 */
export async function installMushroom(bytes: Buffer): Promise<InstalledMushroom> {
  const folder = await stat(LOCAL_DIR).catch(() => undefined);
  if (!folder?.isDirectory()) {
    throw new Error(
      `${LOCAL_DIR} is not there, so this Home Assistant does not serve /local; ` +
        "`scripts.e2e.hass up` makes it, so start the run again",
    );
  }
  const name = `mushroom-${MUSHROOM_VERSION}.js`;
  const file = join(LOCAL_DIR, name);
  await writeFile(file, bytes);
  return { url: `/local/${name}`, remove: () => rm(file, { force: true }) };
}
