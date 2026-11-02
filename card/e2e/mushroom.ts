// The real Mushroom, for the pictures of the documentation. A picture of the Mushroom style
// has to be taken with Mushroom on the page, so the screenshots load its release the way a user
// does: as a resource of the dashboard. The release is downloaded once, from GitHub, into a
// folder that git ignores, and checked against the hash written here; the end-to-end tests
// never come here, and need neither the network nor Mushroom.
//
// Mushroom is Apache-2.0 licensed, and is not part of this repository: the file is fetched for
// the run and left in the folder of the cache.
import { createHash } from "node:crypto";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import { join } from "node:path";
import { REPO_ROOT } from "./constants";

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

/** Mushroom served to the browser from this machine: where the dashboard finds it. */
export interface ServedMushroom {
  url: string;
  close(): Promise<void>;
}

/**
 * Serves the bytes on a port of this machine that nothing else uses, with the header that lets
 * a page of another origin, Home Assistant's, load them as a module.
 */
export async function serveMushroom(bytes: Buffer): Promise<ServedMushroom> {
  const server = createServer((request, response) => {
    if (request.url !== "/mushroom.js") {
      response.writeHead(404).end();
      return;
    }
    response
      .writeHead(200, {
        "content-type": "text/javascript; charset=utf-8",
        "access-control-allow-origin": "*",
        "cache-control": "no-store",
      })
      .end(bytes);
  });
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const { port } = server.address() as AddressInfo;
  return {
    url: `http://127.0.0.1:${port}/mushroom.js`,
    close: () =>
      new Promise<void>((resolve, reject) => {
        server.close((error) => (error ? reject(error) : resolve()));
        server.closeAllConnections();
      }),
  };
}
