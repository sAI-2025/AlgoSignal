// Marker popover (PRD V8): clicking a signal marker opens a small panel with the crossover
// details — direction, date, close, the two SMA values and the period pair. Dismissed by
// clicking empty space or pressing Escape (wired by the workspace).

class MarkerPopover {
  constructor(container) {
    this.container = container;
    this.markers = [];
    this.el = document.createElement("div");
    this.el.className = "as-marker-popover d-none";
    this.container.appendChild(this.el);
  }

  setMarkers(markers) {
    this.markers = markers || [];
  }

  hide() {
    this.el.classList.add("d-none");
  }

  // Feed a chart click. Returns true when a marker was matched and shown.
  handleClick(param) {
    if (!param || !param.time || !this.markers.length) {
      this.hide();
      return false;
    }
    const marker = this._nearest(param.time);
    if (!marker) {
      this.hide();
      return false;
    }
    this._render(marker, param.point);
    return true;
  }

  _nearest(time) {
    const exact = this.markers.filter((m) => m.time === time);
    if (exact.length) {
      return exact[0];
    }
    // Fall back to the closest marker time so near-misses on dense bars still resolve.
    let best = null;
    let bestDist = Infinity;
    for (const m of this.markers) {
      const d = timeDistance(m.time, time);
      if (d < bestDist) {
        bestDist = d;
        best = m;
      }
    }
    return bestDist <= 3 * 86400 ? best : null;
  }

  _render(marker, point) {
    const bullish = marker.type === "BULLISH";
    const dir = bullish ? "Bullish crossover" : "Bearish crossover";
    const color = bullish ? "#16a34a" : "#dc2626";
    const params = Array.isArray(marker.params) ? marker.params.join(" / ") : "";
    this.el.innerHTML =
      `<div class="as-marker-popover-title" style="color:${color}">${dir}</div>` +
      `<div class="small"><strong>${escapeHtml(marker.time)}</strong></div>` +
      `<div class="small">Close ${formatNumber(marker.price)}</div>` +
      `<div class="small">SMA ${formatNumber(marker.short_sma)} / ${formatNumber(marker.long_sma)}` +
      (params ? ` <span class="text-muted">(${escapeHtml(params)})</span>` : "") +
      `</div>`;
    this.el.classList.remove("d-none");
    this._position(point);
  }

  _position(point) {
    const rect = this.container.getBoundingClientRect();
    const x = point ? point.x : rect.width / 2;
    const y = point ? point.y : 40;
    const clampedX = Math.min(Math.max(8, x + 12), Math.max(8, rect.width - 180));
    this.el.style.left = `${Math.round(clampedX)}px`;
    this.el.style.top = `${Math.round(Math.min(Math.max(8, y), rect.height - 120))}px`;
  }
}

// Rough calendar-distance between two ISO date strings, in seconds (best-effort).
function timeDistance(a, b) {
  const ta = Date.parse(a);
  const tb = Date.parse(b);
  if (Number.isNaN(ta) || Number.isNaN(tb)) {
    return Infinity;
  }
  return Math.abs(tb - ta) / 1000;
}

function formatNumber(value) {
  return Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

export { MarkerPopover };