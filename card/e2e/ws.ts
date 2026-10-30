// A test's own connection to Home Assistant's WebSocket API, with the long-lived token of
// one of the fixture's users: it sets a timer up, or looks at what the card did, the way a
// second device would. Node's own `WebSocket`, so there is nothing to install.
import type { E2EState, UserName } from "./constants";

/** The state of an entity as Home Assistant sends it. */
export interface HassState {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
  last_changed: string;
}

/** One view of a dashboard, as it is saved. */
export interface DashboardView {
  path: string;
  [field: string]: unknown;
}

export interface HassWs {
  callService(
    domain: string,
    service: string,
    data?: Record<string, unknown>,
    target?: { entity_id: string },
  ): Promise<unknown>;
  /** The state of the entity, or undefined when it has none. */
  state(entityId: string): Promise<HassState | undefined>;
  /** The saved configuration of a view of the fixture's dashboard. */
  config(dashboardView: string): Promise<DashboardView>;
  close(): void;
}

interface Pending {
  resolve(result: unknown): void;
  reject(error: Error): void;
}

/** Opens the connection and authenticates; resolves when Home Assistant accepted the token. */
function connect(baseUrl: string, token: string): Promise<WebSocket> {
  const url = new URL("/api/websocket", baseUrl);
  url.protocol = "ws:";
  const socket = new WebSocket(url);
  return new Promise((resolve, reject) => {
    socket.addEventListener("error", () => reject(new Error(`Cannot connect to ${url}`)));
    socket.addEventListener("close", () =>
      reject(new Error(`${url} closed before it accepted the token`)),
    );
    socket.addEventListener("message", function authenticate(event) {
      const message = JSON.parse(String(event.data)) as { type: string };
      if (message.type === "auth_required") {
        socket.send(JSON.stringify({ type: "auth", access_token: token }));
      } else if (message.type === "auth_ok") {
        socket.removeEventListener("message", authenticate);
        resolve(socket);
      } else {
        reject(new Error(`Home Assistant refused the token: ${JSON.stringify(message)}`));
      }
    });
  });
}

export async function hassWs(state: E2EState, user: UserName = "admin"): Promise<HassWs> {
  const socket = await connect(state.base_url, state.users[user].token);
  const pending = new Map<number, Pending>();
  let nextId = 1;

  socket.addEventListener("message", (event) => {
    const message = JSON.parse(String(event.data)) as {
      type: string;
      id: number;
      success: boolean;
      result: unknown;
      error: { message: string };
    };
    const waiting = pending.get(message.id);
    if (message.type !== "result" || waiting === undefined) {
      return;
    }
    pending.delete(message.id);
    if (message.success) {
      waiting.resolve(message.result);
    } else {
      waiting.reject(new Error(message.error.message));
    }
  });
  socket.addEventListener("close", () => {
    for (const waiting of pending.values()) {
      waiting.reject(new Error("The WebSocket closed"));
    }
    pending.clear();
  });

  const call = <T>(command: { type: string; [field: string]: unknown }): Promise<T> =>
    new Promise((resolve, reject) => {
      const id = nextId++;
      pending.set(id, { resolve: (result) => resolve(result as T), reject });
      socket.send(JSON.stringify({ id, ...command }));
    });

  return {
    callService: (domain, service, data = {}, target) =>
      call({ type: "call_service", domain, service, service_data: data, target }),
    state: async (entityId) =>
      (await call<HassState[]>({ type: "get_states" })).find((s) => s.entity_id === entityId),
    config: async (dashboardView) => {
      const config = await call<{ views: DashboardView[] }>({
        type: "lovelace/config",
        url_path: state.dashboard,
        force: true,
      });
      const found = config.views.find((view) => view.path === dashboardView);
      if (found === undefined) {
        throw new Error(`The dashboard ${state.dashboard} has no view ${dashboardView}`);
      }
      return found;
    },
    close: () => socket.close(),
  };
}
