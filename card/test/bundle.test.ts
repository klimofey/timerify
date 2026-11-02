// @vitest-environment node
// esbuild cannot start in the page-like environment the other test files run in.
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { build, type Plugin } from "esbuild";
import { beforeAll, describe, expect, it } from "vitest";
import { bundleOptions } from "../build.mjs";

type Strings = Record<string, unknown>;

const entryPoint = fileURLToPath(new URL("../src/timerify-card.ts", import.meta.url));
const stringsFile = fileURLToPath(
  new URL("../../custom_components/timerify/translations/en.json", import.meta.url),
);

/** Makes the bundle read `file` where the card imports translations/en.json. */
function readStringsFrom(file: string): Plugin {
  return {
    name: "read-strings-from",
    setup(esbuild) {
      esbuild.onResolve({ filter: /translations[\\/]en\.json$/ }, () => ({ path: file }));
    },
  };
}

/**
 * The fingerprint of the bundle the build script's own options give when the strings of the
 * card are `strings`. The file is written outside the repository, under the name the card
 * imports.
 */
async function bundleWith(strings: Strings): Promise<string> {
  const directory = await mkdtemp(join(tmpdir(), "timerify-bundle-"));
  try {
    const file = join(directory, "translations", "en.json");
    await mkdir(dirname(file));
    await writeFile(file, JSON.stringify(strings));
    const options = bundleOptions(entryPoint);
    const { outputFiles } = await build({
      ...options,
      plugins: [readStringsFrom(file), ...(options.plugins ?? [])],
    });
    const [bundle] = outputFiles ?? [];
    if (outputFiles?.length !== 1 || bundle === undefined) {
      throw new Error(`Expected one output file, esbuild produced ${outputFiles?.length}`);
    }
    return createHash("sha256").update(bundle.contents).digest("hex");
  } finally {
    await rm(directory, { recursive: true });
  }
}

/** The same strings with every text longer, the way an edit of the wording does it. */
function reword(value: unknown): unknown {
  if (typeof value === "string") {
    return `${value} reworded`;
  }
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, text]) => [key, reword(text)]));
  }
  return value;
}

// The minifier names the identifiers of the bundle after the letters its sources use most, so
// each change below moves how often the letters occur: that is what a build that read the
// whole file would show.
const changesOutsideCommon: [string, (strings: Strings) => Strings][] = [
  [
    "a text outside common is reworded",
    ({ common, ...outside }) => ({ ...(reword(outside) as Strings), common }),
  ],
  [
    "a section outside common is added",
    (strings) => ({ ...strings, hints: { tip: "z".repeat(5000) } }),
  ],
  ["every section outside common is removed", ({ common }) => ({ common })],
];

describe("the bundle of the card", () => {
  let strings: Strings & { common: Strings };
  let fingerprint: string;

  beforeAll(async () => {
    strings = JSON.parse(await readFile(stringsFile, "utf8"));
    fingerprint = await bundleWith(strings);
  });

  it.each(changesOutsideCommon)("does not change when %s", async (_change, change) => {
    expect(await bundleWith(change(strings))).toBe(fingerprint);
  });

  it("changes when a text of common changes", async () => {
    const reworded = { ...strings, common: reword(strings.common) as Strings };

    expect(await bundleWith(reworded)).not.toBe(fingerprint);
  });
});
