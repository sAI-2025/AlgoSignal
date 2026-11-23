// stock-detail.js — refresh metrics handler for the Company Detail page.
// POSTs to /api/v1/companies/<symbol>/refresh-metrics/ and provides
// loading + toast feedback.

import { api } from "../js/api.js";

const TOAST_MS = 4000;

function $(sel, root = document) {
  return root.querySelector(sel);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

function showToast({ kind = "success", title, message }) {
  let container = document.querySelector(".as-toast-container");
  if (!container) {
    container = document.createElement("div");
    container.className = "as-toast-container";
    document.body.appendChild(container);
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

function setLoading(btn, loading) {
  const icon = btn.querySelector("i");
  const label = btn.querySelector("span");
  if (loading) {
    btn.classList.add("as-refresh-btn--loading");
    btn.disabled = true;
    if (icon) icon.style.display = "none";
    if (label) label.style.visibility = "hidden";
    const spinner = document.createElement("span");
    spinner.className = "as-spinner";
    spinner.setAttribute("aria-hidden", "true");
    btn.appendChild(spinner);
  } else {
    btn.classList.remove("as-refresh-btn--loading");
    btn.disabled = false;
    if (icon) icon.style.display = "";
    if (label) label.style.visibility = "";
    const spinner = btn.querySelector(".as-spinner");
    if (spinner) spinner.remove();
  }
}

function setMetricLoading(btn, loading) {
  if (loading) {
    btn.classList.add("as-metric-refresh--loading");
    btn.disabled = true;
    const icon = btn.querySelector("i");
    if (icon) icon.style.display = "none";
    const spinner = document.createElement("span");
    spinner.className = "as-spinner";
    spinner.setAttribute("aria-hidden", "true");
    btn.appendChild(spinner);
  } else {
    btn.classList.remove("as-metric-refresh--loading");
    btn.disabled = false;
    const icon = btn.querySelector("i");
    if (icon) icon.style.display = "";
    const spinner = btn.querySelector(".as-spinner");
    if (spinner) spinner.remove();
  }
}

export function initRefreshMetrics(btn) {
  const symbol = btn.dataset.symbol;
  if (!symbol) {
    return;
  }

  async function doRefresh() {
    try {
      await api.post(`/companies/${encodeURIComponent(symbol)}/refresh-metrics/`);
      showToast({
        kind: "success",
        title: "Metrics refreshed",
        message: `Fundamentals for ${symbol} updated from the provider.`,
      });
    } catch (error) {
      showToast({
        kind: "error",
        title: "Refresh failed",
        message: error.message || "Couldn't refresh metrics.",
      });
    }
  }

  btn.addEventListener("click", async () => {
    setLoading(btn, true);
    try {
      await doRefresh();
    } finally {
      setLoading(btn, false);
    }
  });

  // Per-metric refresh buttons inside metric cards.
  document.querySelectorAll('[data-action="refresh-metric"]').forEach((metricBtn) => {
    metricBtn.addEventListener("click", async () => {
      setMetricLoading(metricBtn, true);
      try {
        await doRefresh();
      } finally {
        setMetricLoading(metricBtn, false);
      }
    });
  });
}
