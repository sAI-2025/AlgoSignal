// api.js — shared fetch wrapper for the AlgoSignal browser layer (ARCHITECTURE §15).
// Handles CSRF (same-origin session auth), JSON request/response, the standard DRF
// error envelope, 429 retry-after, and 401/403 auth redirect to login.
// All functions return parsed JSON or throw an ApiError with {status, code, message, fields}.

const API_BASE = "/api/v1";

class ApiError extends Error {
  constructor(status, { code, message, fields } = {}) {
    super(message || `Request failed (${status})`);
    this.name = "ApiError";
    this.status = status;
    this.code = code || String(status);
    this.message = message || `Request failed (${status})`;
    this.fields = fields || {};
  }
}

function csrfToken() {
  const match = document.cookie.match(/(?:^|; )\s*csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

function jsonHeaders(extra = {}) {
  return Object.assign(
    { Accept: "application/json", "Content-Type": "application/json" },
    csrfToken() ? { "X-CSRFToken": csrfToken() } : {},
    extra,
  );
}

async function handleResponse(response) {
  if (response.ok) {
    const text = await response.text();
    return text ? JSON.parse(text) : null;
  }
  let body = {};
  try {
    body = JSON.parse(await response.text());
  } catch {}
  const envelope = body.error || {};
  if (response.status === 401 || response.status === 403) {
    // Session expired or insufficient privileges — send the user to login.
    const login = document.querySelector("[data-login-url]");
    if (login) {
      window.location.href = login.dataset.loginUrl;
    } else {
      window.location.href = "/login/?next=" + encodeURIComponent(window.location.pathname);
    }
  }
  throw new ApiError(response.status, {
    code: envelope.code,
    message: envelope.message,
    fields: envelope.fields || {},
  });
}

function buildQuery(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") {
      continue;
    }
    if (Array.isArray(value)) {
      value.forEach((v) => search.append(key, v));
    } else {
      search.append(key, String(value));
    }
  }
  return search.toString();
}

// GET a JSON resource.
export async function get(path, params = {}) {
  const url = `${API_BASE}${path}${buildQuery(params) ? "?" + buildQuery(params) : ""}`;
  const response = await fetch(url, {
    method: "GET",
    headers: jsonHeaders(),
    credentials: "same-origin",
  });
  return handleResponse(response);
}

// POST a JSON body.
export async function post(path, body = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: jsonHeaders(),
    credentials: "same-origin",
    body: JSON.stringify(body),
  });
  return handleResponse(response);
}

// PUT a JSON body.
export async function put(path, body = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: jsonHeaders(),
    credentials: "same-origin",
    body: JSON.stringify(body),
  });
  return handleResponse(response);
}

// Convenience wrappers for the endpoints the pages consume.
export const api = {
  dashboardSummary: () => get("/dashboard/summary/"),
  companies: (params) => get("/companies/", params),
  scannerRun: (params) => post("/scanner/run/", params),
  scannerSettings: () => get("/scanner/settings/"),
  topPerformers: (params) => get("/analytics/top-performers/", params),
  marketOverview: () => get("/analytics/market-overview/"),
  coverage: () => get("/market-data/coverage/"),
  schedules: () => get("/fetcher/schedules/"),
  runs: (params) => get("/fetcher/runs/", params),
  chartPayload: (symbol, params) => get(`/charts/${encodeURIComponent(symbol)}/`, params),
  liveQuote: (symbol) => get(`/live/quote/${encodeURIComponent(symbol)}/`),
  companyMetrics: (symbol) => get(`/companies/${encodeURIComponent(symbol)}/metrics/`),
  search: (q) => get("/search/", { q }),
};

export { ApiError };
