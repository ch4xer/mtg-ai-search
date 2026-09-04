const TOKEN_KEY = "mtg-access-token";
const REFRESH_KEY = "mtg-refresh-token";
let refreshRequest = null;

export class ApiError extends Error {
  constructor(message, status, payload = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access, refresh) {
  localStorage.setItem(TOKEN_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

async function refreshAccessToken() {
  if (refreshRequest) return refreshRequest;
  const refresh = getRefreshToken();
  if (!refresh) return null;
  refreshRequest = (async () => {
    try {
      const res = await fetch("/api/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!res.ok) return null;
      const data = await res.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      return data.access_token;
    } catch {
      return null;
    }
  })().finally(() => {
    refreshRequest = null;
  });
  return refreshRequest;
}

export async function apiFetch(url, options = {}) {
  const token = getAccessToken();
  const headers = { ...options.headers };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  let body = options.body;
  if (body && typeof body === "object" && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }

  let res = await fetch(url, { ...options, body, headers });

  if (res.status === 401 && token) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers["Authorization"] = `Bearer ${newToken}`;
      res = await fetch(url, { ...options, body, headers });
    }
  }

  return res;
}

export async function apiJson(url, options = {}, fallbackMessage = "Request failed") {
  const response = await apiFetch(url, options);
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(payload?.detail || fallbackMessage, response.status, payload);
  }
  return payload;
}
