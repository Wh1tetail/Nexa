/** Server-Sent Events client for live notifications.
 *  Uses fetch streaming (not EventSource) so the access token travels in the
 *  Authorization header instead of the URL. */
import { http, tokenStore } from "@/services/http";
import type { Notification } from "@/types/api";

const STREAM_URL = (import.meta.env.VITE_API_URL ?? "") + "/api/v1/notifications/stream";

type Status = "connecting" | "live" | "offline";
let status: Status = "offline";
const listeners = new Set<() => void>();

export const realtimeStatus = {
  get: () => status,
  subscribe(fn: () => void) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
};

function setStatus(s: Status) {
  if (s !== status) {
    status = s;
    listeners.forEach((fn) => fn());
  }
}

interface Options {
  onNotification: (n: Notification) => void;
  signal: AbortSignal;
}

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve) => {
    const t = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(t);
      resolve();
    });
  });

/** Ensures a valid access token: an authenticated axios call triggers the
 *  refresh interceptor (or the session-expired handler). */
async function refreshToken(): Promise<boolean> {
  try {
    await http.get("/auth/me");
    return !!tokenStore.access;
  } catch {
    return false;
  }
}

/** The server sends a ping every 15 s; silence for longer means a dead
 *  connection (e.g. a proxy kept the socket open after a backend restart). */
const WATCHDOG_MS = 40_000;

/** Set when the server reported that this session was revoked
 *  (logout elsewhere, password change, deactivation). Read by AuthContext
 *  to show an accurate message. */
let revokedAt = 0;
export const wasRecentlyRevoked = () => Date.now() - revokedAt < 10_000;

type StreamEnd = "closed" | "revoked";

async function readStream(res: Response, opts: Options, kill: () => void): Promise<StreamEnd> {
  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  let lastSeen = Date.now();
  const watchdog = setInterval(() => {
    if (Date.now() - lastSeen > WATCHDOG_MS) kill();
  }, 5_000);
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) return "closed";
      lastSeen = Date.now();
      buffer += value;
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        let event = "message";
        const data: string[] = [];
        for (const line of frame.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data.push(line.slice(5).trim());
        }
        if (event === "ready") setStatus("live");
        else if (event === "notification") opts.onNotification(JSON.parse(data.join("\n")) as Notification);
        else if (event === "expired") return "closed"; // token expired: reconnect with a fresh one
        else if (event === "revoked") return "revoked";
      }
    }
  } finally {
    clearInterval(watchdog);
    reader.cancel().catch(() => undefined);
  }
}

/** Keeps a stream open until `signal` aborts; reconnects with backoff. */
export async function runNotificationStream(opts: Options): Promise<void> {
  let attempt = 0;
  while (!opts.signal.aborted) {
    setStatus("connecting");
    // per-connection controller: aborted by the page (outer signal) or by the watchdog
    const conn = new AbortController();
    const onAbort = () => conn.abort();
    opts.signal.addEventListener("abort", onAbort);
    try {
      let token = tokenStore.access;
      if (!token && !(await refreshToken())) break;
      token = tokenStore.access;
      const res = await fetch(STREAM_URL, {
        headers: { Authorization: `Bearer ${token}`, Accept: "text/event-stream" },
        signal: conn.signal,
        cache: "no-store",
      });
      if (res.status === 401) {
        if (!(await refreshToken())) break; // session is over
        continue;
      }
      if (!res.ok || !res.body) throw new Error(`stream ${res.status}`);
      attempt = 0;
      const end = await readStream(res, opts, () => conn.abort());
      if (end === "revoked") {
        revokedAt = Date.now();
        // Still valid here (e.g. this tab changed the password and holds new tokens)?
        // Then reconnect at once; otherwise the session-expired handler signs the user out.
        if (!(await refreshToken())) break;
        attempt = 0;
        continue;
      }
    } catch {
      if (opts.signal.aborted) break;
    } finally {
      opts.signal.removeEventListener("abort", onAbort);
    }
    if (opts.signal.aborted) break;
    setStatus("offline");
    // fast reconnect after a normal end (token expiry), backoff on errors
    const delay = attempt === 0 ? 500 : Math.min(30_000, 1000 * 2 ** attempt);
    attempt += 1;
    await sleep(delay, opts.signal);
  }
  setStatus("offline");
}
