// Price-level pins (PRD V5). A pin marks a (time, price) point the analyst wants to
// remember. Persisted per symbol in localStorage, painted as overlay dots that re-project
// on every view change. Pins never touch the chart library's data.

import { place, xForTime, yForPrice } from "./overlay.js";

const STORAGE_PREFIX = "as.pins.";

function loadPins(symbol) {
  try {
    const raw = JSON.parse(localStorage.getItem(`${STORAGE_PREFIX}${symbol}`) || "[]");
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

function savePins(symbol, pins) {
  try {
    localStorage.setItem(`${STORAGE_PREFIX}${symbol}`, JSON.stringify(pins));
  } catch {
    /* storage may be unavailable — pins are best-effort */
  }
}

class PinManager {
  constructor(symbol, { listTarget } = {}) {
    this.symbol = symbol;
    this.listTarget = listTarget;
    this.pins = loadPins(symbol);
    this.nodes = new Map();
    this.onChange = null;
  }

  list() {
    return this.pins.slice();
  }

  add(time, price) {
    const pin = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      time,
      price,
    };
    this.pins.push(pin);
    savePins(this.symbol, this.pins);
    this.emit();
    return pin;
  }

  remove(id) {
    this.pins = this.pins.filter((p) => p.id !== id);
    savePins(this.symbol, this.pins);
    this.emit();
  }

  clear() {
    this.pins = [];
    savePins(this.symbol, this.pins);
    this.emit();
  }

  emit() {
    if (this.onChange) {
      this.onChange(this.pins.slice());
    }
    this.renderList();
  }

  // Re-project every pin dot onto the layer. Called on view change and after render.
  render(layer, handle) {
    if (!layer) {
      return;
    }
    const { chart, priceSeries } = handle;
    const wanted = new Set(this.pins.map((p) => p.id));

    for (const [id, node] of this.nodes) {
      if (!wanted.has(id)) {
        node.remove();
        this.nodes.delete(id);
      }
    }

    for (const pin of this.pins) {
      let node = this.nodes.get(pin.id);
      if (!node) {
        node = document.createElement("span");
        node.className = "as-pin-dot";
        node.title = `Pinned ${pin.time} @ ${pin.price}`;
        layer.add(node);
        this.nodes.set(pin.id, node);
      }
      const x = xForTime(chart, pin.time);
      const y = yForPrice(priceSeries, pin.price);
      if (x == null || y == null) {
        node.style.display = "none";
        continue;
      }
      node.style.display = "block";
      place(node, x, y);
    }
  }

  renderList() {
    if (!this.listTarget) {
      return;
    }
    if (!this.pins.length) {
      this.listTarget.innerHTML = '<span class="text-muted small">No pinned levels.</span>';
      return;
    }
    this.listTarget.innerHTML = this.pins
      .map(
        (p) =>
          `<span class="as-pin-chip">${escapeHtml(p.time)} · ${p.price}` +
          `<button type="button" class="btn-close btn-close-sm ms-1" data-pin-remove="${escapeHtml(p.id)}"` +
          ` aria-label="Remove pin"></button></span>`,
      )
      .join("");
  }

  bindListRemove() {
    if (!this.listTarget) {
      return;
    }
    this.listTarget.addEventListener("click", (event) => {
      const btn = event.target.closest("[data-pin-remove]");
      if (btn) {
        this.remove(btn.dataset.pinRemove);
      }
    });
  }

  destroy() {
    this.nodes.clear();
  }
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export { PinManager };