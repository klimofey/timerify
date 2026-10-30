// Runs `scripts.e2e.hass`, the Python side of the end-to-end tests, from the repository root:
// `npm --prefix card run e2e` starts in `card/`, where the module does not resolve.
import { spawn } from "node:child_process";
import { BASE_URL, REPO_ROOT, STATE_FILE } from "./constants";

export type HarnessCommand = "up" | "restart" | "down";

/**
 * Resolves when the command succeeded. It prints its progress, and on failure the log of
 * Home Assistant.
 */
export function runHarness(command: HarnessCommand): Promise<void> {
  const port = new URL(BASE_URL).port;
  const args = ["run", "python", "-m", "scripts.e2e.hass", command];
  args.push("--port", port, "--state", STATE_FILE);
  return new Promise((resolve, reject) => {
    const child = spawn("uv", args, { cwd: REPO_ROOT, stdio: "inherit" });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`uv ${args.join(" ")} exited with ${code}`));
      }
    });
  });
}
