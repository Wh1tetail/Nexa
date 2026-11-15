import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

import type { ApiErrorBody, TokenPair } from "@/types/api";

const API_BASE = (import.meta.env.VITE_API_URL ?? "") + "/api/v1";
const ACCESS_KEY = "nexa.access";
const REFRESH_KEY = "nexa.refresh";

// Access token lives in memory (+ sessionStorage for reloads); refresh token in localStorage.
export const tokenStore = {
  get access() {
    try {
      return sessionStorage.getItem(ACCESS_KEY);
    } catch {
      return null;
    }
  },
  get refresh() {
    try {
      return localStorage.getItem(REFRESH_KEY);
    } catch {
      return null;
    }
  },
  set(tokens: TokenPair) {
    try {
      sessionStorage.setItem(ACCESS_KEY, tokens.access_token);
      localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
    } catch {
      /* storage unavailable */
    }
  },
  clear() {
    try {
      sessionStorage.removeItem(ACCESS_KEY);
      localStorage.removeItem(REFRESH_KEY);
    } catch {
      /* ignore */
    }
  },
};

export const http = axios.create({ baseURL: API_BASE, timeout: 30000 });

/** Interface language sent with every request: the server answers (errors,
 *  CSV, texts) in it. Read from storage at start so even the very first
 *  requests carry it; kept current by I18nProvider. */
let requestLanguage = (() => {
  try {
    return localStorage.getItem("nexa.locale") || "ru";
  } catch {
    return "ru";
  }
})();

/** Administrator pages that manage a teacher's groups and lessons set the
 *  teacher here; the server reads it from X-Teacher-Id (ignored for others). */
let actingTeacherId: number | null = null;
export function setActingTeacher(id: number | null) {
  actingTeacherId = id;
}

http.interceptors.request.use((config) => {
  const token = tokenStore.access;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  config.headers["Accept-Language"] = requestLanguage;
  if (actingTeacherId !== null) config.headers["X-Teacher-Id"] = String(actingTeacherId);
  return config;
});

let refreshing: Promise<string | null> | null = null;
let onSessionExpired: (() => void) | null = null;

export function setSessionExpiredHandler(fn: () => void) {
  onSessionExpired = fn;
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = tokenStore.refresh;
  if (!refresh) return null;
  try {
    const { data } = await axios.post<TokenPair>(`${API_BASE}/auth/refresh`, { refresh_token: refresh });
    tokenStore.set(data);
    return data.access_token;
  } catch {
    return null;
  }
}

http.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    const url = original?.url ?? "";
    if (
      error.response?.status === 401 &&
      original &&
      !original._retry &&
      !url.includes("/auth/login") &&
      !url.includes("/auth/refresh")
    ) {
      original._retry = true;
      refreshing ??= refreshAccessToken().finally(() => {
        refreshing = null;
      });
      const token = await refreshing;
      if (token) {
        original.headers.Authorization = `Bearer ${token}`;
        return http(original);
      }
      tokenStore.clear();
      onSessionExpired?.();
    }
    return Promise.reject(error);
  },
);

/** Human-readable message from any API error. */
/** Set by I18nProvider so messages created outside React follow the interface language. */
const fallbackText = { generic: "Что-то пошло не так", offline: "Нет соединения с сервером" };
export function setHttpMessages(m: { generic: string; offline: string; lang: string }) {
  fallbackText.generic = m.generic;
  fallbackText.offline = m.offline;
  requestLanguage = m.lang;
}

export function errorMessage(err: unknown, fallback = fallbackText.generic): string {
  if (axios.isAxiosError(err)) {
    const body = err.response?.data as ApiErrorBody | undefined;
    if (body && typeof body.detail === "string") return body.detail;
    if (!err.response) return fallbackText.offline;
  }
  return fallback;
}

export function apiUrl(path: string) {
  return `${API_BASE}${path}`;
}
