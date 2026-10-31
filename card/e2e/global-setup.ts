import { runHarness } from "./harness";

/** Starts Home Assistant and builds the fixture; runs once, before the first test. */
export default async function globalSetup(): Promise<void> {
  await runHarness("up");
}
