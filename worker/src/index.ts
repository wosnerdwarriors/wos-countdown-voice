export interface Player {
  id: string;
  name: string;
  marchMs: number;
}

export interface Rally {
  starterId: string;
  // UTC timestamp when the march phase begins (join phase ends).
  launchAt: number;
  rallyDurationMs: number;
  preDelayMs: number;
  arrivalAt: number;
}

export interface RoomState {
  players: Player[];
  rally: Rally | null;
  lastActiveAt: number;
}

type ClientMsg =
  | { type: "STATE_REQUEST"; roomId?: string }
  | { type: "PLAYER_ADD"; roomId?: string; payload: Player }
  | { type: "PLAYER_REMOVE"; roomId?: string; payload: string }
  | { type: "RALLY_START"; roomId?: string; payload: { starterId: string; launchAt?: number; rallyDurationMs?: number; preDelayMs?: number }; }
  | { type: "RALLY_END"; roomId?: string }
  | { type: "TIME_SYNC_REQUEST"; roomId?: string; payload: { t0: number } };


type ServerMsg = { type: "STATE"; payload: RoomState };
type TimeSyncResponse = { type: "TIME_SYNC_RESPONSE"; payload: { t0: number; t1: number; t2: number } };

const DEFAULT_STATE: RoomState = { players: [], rally: null, lastActiveAt: Date.now() };
const AUTO_DELETE_GRACE_MS = 5000;

function ceilToSecond(ts: number): number {
  return Math.ceil(ts / 1000) * 1000;
}

function jsonResponse(obj: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(obj), {
    ...init,
    headers: { "content-type": "application/json; charset=utf-8", ...(init.headers || {}) },
  });
}

export class RallyRoom {
  state: DurableObjectState;
  env: Env;
  sockets: Set<WebSocket>;
  data: RoomState | null;

  constructor(state: DurableObjectState, env: Env) {
    this.state = state;
    this.env = env;
    this.sockets = new Set();
    this.data = null;
  }

  async ensureLoaded() {
    if (this.data) return;
    const stored = await this.state.storage.get<RoomState>("state");
    const now = Date.now();
    const MAX_AGE_MS = 6 * 60 * 60 * 1000; // Expire rooms after 6 hours of inactivity.

    if (stored) {
      if (stored.rally && !Number.isFinite(stored.rally.arrivalAt)) {
        stored.rally = null;
      }
      // Reset stale rooms.
      if (!stored.lastActiveAt || now - stored.lastActiveAt > MAX_AGE_MS) {
        this.data = { ...DEFAULT_STATE, lastActiveAt: now };
        await this.persist();
      } else {
        this.data = stored;
      }
    } else {
      this.data = { ...DEFAULT_STATE, lastActiveAt: now };
      await this.persist();
    }
  }

  async persist() {
    if (!this.data) return;
    await this.state.storage.put("state", this.data);
  }

  broadcast() {
    if (!this.data) return;
    const msg: ServerMsg = { type: "STATE", payload: this.data };
    const text = JSON.stringify(msg);
    for (const ws of this.sockets) {
      try {
        ws.send(text);
      } catch {
        // Ignore dead sockets.
      }
    }
  }

  async maybeClearLanded() {
    if (!this.data?.rally) return;
    const arrivalAt = this.data.rally.arrivalAt;
    if (!Number.isFinite(arrivalAt)) return;
    if (arrivalAt <= Date.now()) {
      this.data.rally = null;
      await this.persist();
      await this.state.storage.deleteAlarm();
    }
  }

  async scheduleAutoCleanup(arrivalAt: number) {
    if (!Number.isFinite(arrivalAt)) return;
    const alarmAt = arrivalAt + AUTO_DELETE_GRACE_MS;
    await this.state.storage.setAlarm(alarmAt);
  }

  async handleMessage(ws: WebSocket, raw: string) {
    await this.ensureLoaded();
    if (!this.data) return;

    await this.maybeClearLanded();
    this.data.lastActiveAt = Date.now();

    let msg: ClientMsg;
    try {
      msg = JSON.parse(raw);
    } catch {
      return;
    }

    switch (msg.type) {
      case "STATE_REQUEST": {
        await this.maybeClearLanded();
        const reply: ServerMsg = { type: "STATE", payload: this.data };
        ws.send(JSON.stringify(reply));
        return;
      }
      case "PLAYER_ADD": {
        if (!msg.payload || !msg.payload.id) return;
        // Upsert by id.
        const idx = this.data.players.findIndex((p) => p.id === msg.payload.id);
        if (idx >= 0) this.data.players[idx] = msg.payload;
        else this.data.players.push(msg.payload);
        await this.persist();
        this.broadcast();
        return;
      }
      case "PLAYER_REMOVE": {
        const id = msg.payload;
        if (!id) return;
        this.data.players = this.data.players.filter((p) => p.id !== id);
        // End rally when the starter is removed.
        if (this.data.rally && this.data.rally.starterId === id) {
          this.data.rally = null;
          await this.state.storage.deleteAlarm();
        }
        await this.persist();
        this.broadcast();
        return;
      }
      case "RALLY_START": {
        const { starterId, launchAt, rallyDurationMs, preDelayMs } = msg.payload ?? {};

        if (!starterId) return;
        const starter = this.data.players.find((p) => p.id === starterId);
        if (!starter || !Number.isFinite(starter.marchMs)) return;

        const durationMs = Number(rallyDurationMs);
        const delayMs = Number(preDelayMs ?? 0);
        if (!Number.isFinite(durationMs) || durationMs < 0) return;
        if (!Number.isFinite(delayMs) || delayMs < 0) return;

        let computedLaunchAt = launchAt;

        if (typeof computedLaunchAt !== "number" || !Number.isFinite(computedLaunchAt)) {
          computedLaunchAt = Date.now() + delayMs + durationMs;
        }
        computedLaunchAt = ceilToSecond(computedLaunchAt);

        const arrivalAt = computedLaunchAt + starter.marchMs;
        this.data.rally = {
          starterId,
          launchAt: computedLaunchAt,
          rallyDurationMs: durationMs,
          preDelayMs: delayMs,
          arrivalAt,
        };

        await this.persist();
        await this.scheduleAutoCleanup(arrivalAt);
        this.broadcast();
        return;
      }
      case "RALLY_END": {
        this.data.rally = null;
        await this.persist();
        await this.state.storage.deleteAlarm();
        this.broadcast();
        return;
      }
      case "TIME_SYNC_REQUEST": {
        const t0 = msg.payload?.t0;
        if (typeof t0 !== "number" || !Number.isFinite(t0)) return;
        const t1 = Date.now();
        const t2 = Date.now();
        const reply: TimeSyncResponse = { type: "TIME_SYNC_RESPONSE", payload: { t0, t1, t2 } };
        ws.send(JSON.stringify(reply));
        return;
      }
    }
  }

  async fetch(request: Request): Promise<Response> {
    await this.ensureLoaded();
    await this.maybeClearLanded();

    // Debug: current room state.
    const url = new URL(request.url);
    if (url.pathname === "/state") {
      return jsonResponse({ ok: true, state: this.data });
    }

    if (request.headers.get("Upgrade") === "websocket") {
      const pair = new WebSocketPair();
      const client = pair[0];
      const server = pair[1];

      server.accept();
      this.sockets.add(server);

      // Send current state immediately.
      if (this.data) {
        server.send(JSON.stringify({ type: "STATE", payload: this.data } satisfies ServerMsg));
      }

      server.addEventListener("message", (evt) => {
        const text = typeof evt.data === "string" ? evt.data : "";
        this.handleMessage(server, text).catch((err) => {
          console.error("Failed to handle message", err);
        });
      });

      const cleanup = () => {
        try {
          this.sockets.delete(server);
          server.close();
        } catch {}
      };

      server.addEventListener("close", cleanup);
      server.addEventListener("error", cleanup);

      return new Response(null, { status: 101, webSocket: client });
    }

    return jsonResponse({ ok: true, hint: "Connect via WebSocket with Upgrade: websocket." });
  }

  async alarm() {
    await this.ensureLoaded();
    if (!this.data) return;
    const arrivalAt = this.data.rally?.arrivalAt;
    if (!Number.isFinite(arrivalAt)) return;
    if (arrivalAt <= Date.now()) {
      this.data.rally = null;
      await this.persist();
      this.broadcast();
    }
  }
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // Route WS + room state through the Durable Object.
    if (url.pathname === "/ws" || url.pathname === "/state") {
      const room = url.searchParams.get("instance_id") || url.searchParams.get("roomId") || "local";
      const id = env.ROOM.idFromName(room);
      const stub = env.ROOM.get(id);

      // Forward the request to the DO (keep the path).
      return stub.fetch(request);
    }

    // Serve static assets (built Vite app) from Workers Assets binding.
    return env.ASSETS.fetch(request);
  },
};
