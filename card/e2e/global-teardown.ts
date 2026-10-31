import { runHarness } from "./harness";

/** Stops Home Assistant; runs once, after the last test. */
export default async function globalTeardown(): Promise<void> {
  await runHarness("down");
}
