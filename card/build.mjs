// Bundles src/timerify-card.ts into the one ES module the integration serves.
//
//   node build.mjs           writes custom_components/timerify/frontend/timerify-card.js
//   node build.mjs --check   rebuilds in memory and exits 1 if the committed file differs
//
// The output depends on the sources and the pinned packages alone, so a rebuild on any
// machine gives the same bytes. Paths come from this file's location, not from the
// working directory.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";

const cardDirectory = fileURLToPath(new URL(".", import.meta.url));
const entryPoint = fileURLToPath(new URL("src/timerify-card.ts", import.meta.url));
const bundleFile = fileURLToPath(
  new URL("../custom_components/timerify/frontend/timerify-card.js", import.meta.url),
);

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
});
const [bundle] = outputFiles;
if (outputFiles.length !== 1 || bundle === undefined) {
  throw new Error(`Expected one output file, esbuild produced ${outputFiles.length}`);
}

if (process.argv.includes("--check")) {
  const committed = await readFile(bundleFile).catch(() => undefined);
  if (committed === undefined || !Buffer.from(bundle.contents).equals(committed)) {
    console.error(
      `${bundleFile} is not what the sources in card/ build to: run npm --prefix card run build`,
    );
    process.exitCode = 1;
  }
} else {
  await mkdir(dirname(bundleFile), { recursive: true });
  await writeFile(bundleFile, bundle.contents);
}
