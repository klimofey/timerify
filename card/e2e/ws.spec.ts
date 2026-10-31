// A test's connection to Home Assistant must fail loudly, with the reason, when Home Assistant
// is gone or silent: a call that never settles shows only as "Test timeout exceeded" a minute
// later, and a test of a restart has its first connection closed under it.
import { expect, test } from "./fixtures";
import { hassWs } from "./ws";

test("a command on a closed connection is rejected at once", async ({ state }) => {
  const ws = await hassWs(state);
  ws.close();

  await expect(ws.state(state.timers.strict.target)).rejects.toThrow(/WebSocket is closed/);
});

test("a command that Home Assistant does not answer is rejected after the time allowed", async ({
  state,
}) => {
  const ws = await hassWs(state, "admin", { callTimeout: 300 });
  try {
    // Home Assistant answers a ping with a pong, which is not the result of a command.
    await expect(ws.command("ping")).rejects.toThrow(/did not answer ping within 300 ms/);
    // The connection is still good for the commands it does answer.
    expect((await ws.currentUser()).is_admin).toBe(true);
  } finally {
    ws.close();
  }
});

test("the commands waiting when the connection closes are rejected", async ({ state }) => {
  const ws = await hassWs(state);
  const waiting = ws.command("ping");

  ws.close();

  await expect(waiting).rejects.toThrow(/WebSocket is closed/);
});
