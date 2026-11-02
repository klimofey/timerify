// @ts-check
// Bundles src/timerify-card.ts into the one ES module the integration serves.
//
//   node build.mjs           writes custom_components/timerify/frontend/timerify-card.js
//   node build.mjs --check   rebuilds in memory and exits 1 if the committed file differs
//
// The output depends on the sources, the pinned packages and `common` of
// translations/en.json alone, so a rebuild on any machine gives the same bytes. Paths come
// from this file's location, not from the working directory.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";

const cardDirectory = fileURLToPath(new URL(".", import.meta.url));
const entryPoint = fileURLToPath(new URL("src/timerify-card.ts", import.meta.url));
const bundleFile = fileURLToPath(
  new URL("../custom_components/timerify/frontend/timerify-card.js", import.meta.url),
);

/**
 * Gives the bundle `common` of translations/en.json and nothing else. esbuild would bundle the
 * whole file and drop what is not imported, but it names the identifiers of the bundle after
 * the letters its sources use most, and it counts the letters of the whole file. So a text
 * changed outside `common`, which the card never shows, would rename identifiers.
 *
 * The file is matched by its name, not by the path the card imports it from: the bundle test
 * points that import at a copy named translations/en.json, and the copy has to be cut down the
 * same way. Any module of that name is cut to `common`.
 * @returns {import("esbuild").Plugin}
 */
function commonStringsOnly() {
  return {
    name: "common-strings-only",
    setup(esbuild) {
      const stringsFile = { filter: /translations[\\/]en\.json$/, namespace: "file" };
      esbuild.onLoad(stringsFile, async ({ path }) => {
        const { common } = JSON.parse(await readFile(path, "utf8"));
        if (common === null || typeof common !== "object") {
          throw new Error(`${path} has no "common" section for the card`);
        }
        return { contents: `export const common = ${JSON.stringify(common)};`, loader: "js" };
      });
    },
  };
}

/**
 * Bundles `entryPoint` with the options of the script.
 * @param {string} entryPoint the module to bundle
 * @param {import("esbuild").Plugin[]} [extraPlugins] plugins that run before the script's own
 * @returns {Promise<Uint8Array>} the bytes of the one file esbuild produces
 */
export async function buildBundle(entryPoint, extraPlugins = []) {
  const { outputFiles } = await build({
    absWorkingDir: cardDirectory,
    entryPoints: [entryPoint],
    bundle: true,
    format: "esm",
    target: "es2022",
    minify: true,
    legalComments: "eof",
    charset: "utf8",
    sourcemap: false,
    write: false,
    plugins: [...extraPlugins, commonStringsOnly()],
  });
  const [bundle] = outputFiles;
  if (outputFiles.length !== 1 || bundle === undefined) {
    throw new Error(`Expected one output file, esbuild produced ${outputFiles.length}`);
  }
  return bundle.contents;
}

async function main() {
  const bundle = await buildBundle(entryPoint);

  if (process.argv.includes("--check")) {
    const committed = await readFile(bundleFile).catch(() => undefined);
    if (committed === undefined || !Buffer.from(bundle).equals(committed)) {
      console.error(
        `${bundleFile} is not what the sources in card/ build to: run npm --prefix card run build`,
      );
      process.exitCode = 1;
    }
  } else {
    await mkdir(dirname(bundleFile), { recursive: true });
    await writeFile(bundleFile, bundle);
  }
}

// Imported by the bundle test, which must not write or check the committed file.
if (import.meta.main) {
  await main();
}
