// dashboard.js — hydrates the dashboard KPI cards and widgets from
// GET /api/v1/dashboard/summary/ (ARCHITECTURE §14). Runs after the server-rendered
// shell paints, so the page is usable before JS loads and refreshes from the API on demand.

import { api } from "../js/api.js";

const DASHBOARD_KEY = "as.dashboard";
const TOAST_MS = 4000;

function $(sel, root = document) {
  return root.querySelector(sel);
}

function fmtPct(value) {
  if (value == null) {
    return "—";
  }
  const sign = value >= 0 ? "▲ +" : "▼ −";
  return `${sign}${Math.abs(Number(value)).toFixed(2)}%`;
}

function money(value) {
  if (value == null) {
    return "—";
  }
  return Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function showToast({ kind = "success", title, message }) {
  const container = document.querySelector(".as-toast-container");
  if (!container) {
    const el = document.createElement("div");
    el.className = "as-toast-container";
    document.body.appendChild(el);
    return showToast({ kind, title, message });
  }
  const toast = document.createElement("div");
  toast.className = `as-toast ${kind}`;
  const iconHtml = kind === "success"
    ? '<svg class="as-toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
    : '<svg class="as-toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><circle cx="12" cy="12" r="10"/><path d="M12 9v4l4 2"/><path d="M12 17h.01"/></svg>';
  toast.innerHTML = `
    ${iconHtml}
    <div class="as-toast-body"><div style="font-weight:600">${escapeHtml(title)}</div><div style="font-size:0.75rem;color:var(--as-muted);margin-top:0.125rem">${escapeHtml(message || "")}</div></div>
    <button class="as-toast-close" aria-label="Dismiss">&times;</button>
  `;
  toast.querySelector(".as-toast-close").addEventListener("click", () => toast.remove());
  container.appendChild(toast);
  setTimeout(() => toast.remove(), TOAST_MS);
}

async function fetchSummary() {
  return await api.dashboardSummary();
}

function renderCoverage(summary) {
  const el = $("[data-widget='coverage']");
  if (!el || !summary.coverage) {
    return;
  }
  const c = summary.coverage;
  const withData = el.querySelector("[data-field='with_data']");
  const total = el.querySelector("[data-field='companies']");
  const latest = el.querySelector("[data-field='latest_candle']");
  if (withData) {
    withData.textContent = c.with_data ?? "—";
  }
  if (total) {
    total.textContent = c.companies ?? "—";
  }
  if (latest) {
    latest.textContent = c.latest_candle ?? "—";
  }
}

function renderBreadth(summary) {
  const el = $("[data-widget='breadth']");
  if (!el || !summary.breadth) {
    return;
  }
  const b = summary.breadth;
  for (const field of ["advancers", "decliners", "unchanged"]) {
    const node = el.querySelector(`[data-field='${field}']`);
    if (node) {
      node.textContent = b[field] ?? "—";
      node.className = `h4 mb-0 ${field === "advancers" ? "text-success" : field === "decliners" ? "text-danger" : "text-muted"}`;
    }
  }
}

function renderTopGainers(summary) {
  const el = $("[data-widget='top_gainers']");
  if (!el || !summary.top_gainers) {
    return;
  }
  const tbody = el.querySelector("tbody");
  if (!tbody) {
    return;
  }
  tbody.innerHTML = "";
  if (!summary.top_gainers.length) {
    tbody.innerHTML =
      '<tr><td colspan="2" class="text-muted small">No gainers to show yet.</td></tr>';
    return;
  }
  for (const row of summary.top_gainers) {
    const tr = document.createElement("tr");
    const sign = row.return_pct >= 0 ? "text-success" : "text-danger";
    const arrow = row.return_pct >= 0 ? "▲ +" : "▼ −";
    tr.innerHTML = `
      <td><a href="/explorer/${encodeURIComponent(row.nse_code)}/" class="text-decoration-none">${escapeHtml(row.nse_code)}</a></td>
      <td class="text-end ${sign}">${arrow}${Math.abs(Number(row.return_pct)).toFixed(2)}%</td>
    `;
    tbody.appendChild(tr);
  }
}

function renderRecentSignals(summary) {
  const el = $("[data-widget='recent_signals']");
  if (!el || !summary.recent_signals) {
    return;
  }
  const tbody = el.querySelector("tbody");
  if (!tbody) {
    return;
  }
  tbody.innerHTML = "";
  if (!summary.recent_signals.length) {
    tbody.innerHTML =
      '<tr><td colspan="4" class="text-muted small">No signals stored yet. Run the scanner from the Signals page.</td></tr>';
    return;
  }
  for (const signal of summary.recent_signals) {
    const tr = document.createElement("tr");
    const cls = signal.signal_type === "BULLISH" ? "text-success" : "text-danger";
    const arrow = signal.signal_type === "BULLISH" ? "▲" : "▼";
    tr.innerHTML = `
      <td>${escapeHtml(signal.crossover_date)}</td>
      <td><a href="/explorer/${encodeURIComponent(signal.company.nse_code)}/" class="text-decoration-none">${escapeHtml(signal.company.nse_code)}</a></td>
      <td><span class="${cls}">${arrow}</span> ${escapeHtml(signal.signal_type)}</td>
      <td class="text-end as-num">${money(signal.close_price)}</td>
    `;
    tbody.appendChild(tr);
  }
}

function renderSectors(summary) {
  const el = $("[data-widget='sectors']");
  if (!el || !summary.sectors) {
    return;
  }
  const container = el.querySelector(".d-flex.flex-wrap");
  if (!container) {
    return;
  }
  container.innerHTML = "";
  if (!summary.sectors.length) {
    container.innerHTML = '<p class="text-muted small mb-0">No sector data yet.</p>';
    return;
  }
  for (const item of summary.sectors) {
    const badge = document.createElement("span");
    badge.className = `badge rounded-pill ${item.average_return >= 0 ? "bg-success" : "bg-danger"}`;
    badge.textContent = `${escapeHtml(item.sector)}: ${Number(item.average_return).toFixed(2)}%`;
    container.appendChild(badge);
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

export async function initDashboard() {
  const root = $("[data-api-url='/api/v1/dashboard/summary/']");
  if (!root) {
    return;
  }
  try {
    const summary = await fetchSummary();
    renderCoverage(summary);
    renderBreadth(summary);
    renderTopGainers(summary);
    renderRecentSignals(summary);
    renderSectors(summary);
    root.dataset.apiLoaded = "1";
  } catch (error) {
    const banner = $("[data-widget='error']");
    if (banner) {
      banner.textContent = `Couldn't load dashboard: ${error.message}`;
      banner.classList.remove("d-none");
    }
  }
}

export async function refreshDashboard() {
  const btn = document.querySelector("[data-action='refresh-dashboard']");
  if (!btn) {
    return;
  }
  if (btn.classList.contains("refreshing")) {
    return;
  }
  btn.classList.add("refreshing");
  btn.insertAdjacentHTML("beforeend", '<span class="as-spinner" aria-hidden="true"></span>');
  try {
    const summary = await api.dashboardSummary();
    renderCoverage(summary);
    renderBreadth(summary);
    renderTopGainers(summary);
    renderRecentSignals(summary);
    renderSectors(summary);
    showToast({ kind: "success", title: "Dashboard refreshed", message: "Market data updated from the latest stored candles." });
  } catch (error) {
    showToast({ kind: "error", title: "Refresh failed", message: error.message || "Couldn't refresh dashboard data." });
  } finally {
    btn.classList.remove("refreshing");
    const spinner = btn.querySelector(".as-spinner");
    if (spinner) {
      spinner.remove();
    }
  }
}
