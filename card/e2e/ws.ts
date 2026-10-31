// A test's own connection to Home Assistant's WebSocket API, with the long-lived token of
// one of the fixture's users: it sets a timer up, or looks at what the card did, the way a
// second device would. Node's own `WebSocket`, so there is nothing to install.
import type { DashboardConfig, DashboardView, E2EState, UserName } from "./constants";

/** The state of an entity as Home Assistant sends it. */
export interface HassState {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
  last_changed: string;
}

/** The user a connection belongs to, as `auth/current_user` tells it. */
export interface CurrentUser {
  id: string;
  name: string;
  is_admin: boolean;
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
  /** The saved configuration of the fixture's dashboard. */
  dashboard(): Promise<DashboardConfig>;
  /** Saves the configuration of the fixture's dashboard; only an administrator may. */
  saveDashboard(config: DashboardConfig): Promise<void>;
  /** The saved configuration of a view of the fixture's dashboard. */
  config(dashboardView: string): Promise<DashboardView>;
  /** The user whose token this connection has. */
  currentUser(): Promise<CurrentUser>;
  /**
   * Any command of the WebSocket API; resolves with its result. It rejects when the socket is
   * not open, and when Home Assistant has not answered within the options' `callTimeout`.
   */
  command<T = unknown>(type: string, fields?: Record<string, unknown>): Promise<T>;
  close(): void;
}

export interface HassWsOptions {
  /** How long a command may wait for its result, in milliseconds. */
  callTimeout?: number;
}

/** Home Assistant answers a command in milliseconds; a service call, once it has run. */
const CALL_TIMEOUT_MS = 15_000;
const CLOSED = "The WebSocket is closed";

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

export async function hassWs(
  state: E2EState,
  user: UserName = "admin",
  { callTimeout = CALL_TIMEOUT_MS }: HassWsOptions = {},
): Promise<HassWs> {
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
      waiting.reject(new Error(CLOSED));
    }
    pending.clear();
  });

  // A command sent on a socket that is not open would be dropped without a word, and the
  // close handler above has rejected only the commands that were waiting when it closed.
  const call = <T>(type: string, fields: Record<string, unknown> = {}): Promise<T> =>
    new Promise((resolve, reject) => {
      if (socket.readyState !== WebSocket.OPEN) {
        reject(new Error(`${CLOSED}: ${type} was not sent`));
        return;
      }
      const id = nextId++;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`Home Assistant did not answer ${type} within ${callTimeout} ms`));
      }, callTimeout);
      pending.set(id, {
        resolve: (result) => {
          clearTimeout(timer);
          resolve(result as T);
        },
        reject: (error) => {
          clearTimeout(timer);
          reject(error);
        },
      });
      socket.send(JSON.stringify({ id, type, ...fields }));
    });

  const dashboard = () =>
    call<DashboardConfig>("lovelace/config", { url_path: state.dashboard, force: true });

  return {
    callService: (domain, service, data = {}, target) =>
      call("call_service", { domain, service, service_data: data, target }),
    state: async (entityId) =>
      (await call<HassState[]>("get_states")).find((s) => s.entity_id === entityId),
    dashboard,
    saveDashboard: async (config) => {
      await call("lovelace/config/save", { url_path: state.dashboard, config });
    },
    config: async (dashboardView) => {
      const found = (await dashboard()).views.find((view) => view.path === dashboardView);
      if (found === undefined) {
        throw new Error(`The dashboard ${state.dashboard} has no view ${dashboardView}`);
      }
      return found;
    },
    currentUser: () => call<CurrentUser>("auth/current_user"),
    command: call,
    close: () => socket.close(),
  };
}
