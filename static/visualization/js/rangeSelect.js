// Range-select tool (PRD V6): drag a band across the chart to summarise the candles in
// that window — close-to-close change, high/low, average volume, up-day count. While the
// tool is active the workspace disables chart scroll/scale so the drag selects instead of
// panning. Stats are computed from the loaded candles; the band is a pure overlay.

class RangeSelectTool {
  constructor(container, { candles, formatPrice, onStats } = {}) {
    this.container = container;
    this.candles = candles || [];
    this.formatPrice = formatPrice || ((v) => String(v));
    this.onStats = onStats || (() => {});
    this.active = false;
    this.dragStartX = null;
    this.dragEndX = null;
    this._onDown = this._onDown.bind(this);
    this._onMove = this._onMove.bind(this);
    this._onUp = this._onUp.bind(this);
  }

  setCandles(candles) {
    this.candles = candles || [];
  }

  start() {
    if (this.active) {
      return;
    }
    this.active = true;
    this.container.addEventListener("pointerdown", this._onDown);
    this.container.addEventListener("pointermove", this._onMove);
    window.addEventListener("pointerup", this._onUp);
  }

  stop() {
    this.active = false;
    this.container.removeEventListener("pointerdown", this._onDown);
    this.container.removeEventListener("pointermove", this._onMove);
    window.removeEventListener("pointerup", this._onUp);
    this.dragStartX = null;
    this.dragEndX = null;
    this.onStats("");
  }

  reset() {
    this.dragStartX = null;
    this.dragEndX = null;
    this.onStats("");
  }

  _localX(event) {
    const rect = this.container.getBoundingClientRect();
    return event.clientX - rect.left;
  }

  _onDown(event) {
    this.dragStartX = this._localX(event);
    this.dragEndX = this.dragStartX;
  }

  _onMove(event) {
    if (this.dragStartX == null) {
      return;
    }
    this.dragEndX = this._localX(event);
  }

  _onUp() {
    if (this.dragStartX == null || this.dragEndX == null) {
      return;
    }
    const x1 = Math.min(this.dragStartX, this.dragEndX);
    const x2 = Math.max(this.dragStartX, this.dragEndX);
    this.dragStartX = null;
    this.dragEndX = null;
    this._commit(x1, x2);
  }

  _commit(x1, x2) {
    if (!this._chart || x2 - x1 < 4) {
      this.onStats("");
      return;
    }
    const t1 = this._chart.timeScale().coordinateToTime(x1);
    const t2 = this._chart.timeScale().coordinateToTime(x2);
    if (t1 == null || t2 == null) {
      this.onStats("");
      return;
    }
    const lo = t1 < t2 ? t1 : t2;
    const hi = t1 < t2 ? t2 : t1;
    const inRange = this.candles.filter((c) => c.time >= lo && c.time <= hi);
    this.onStats(this._summarise(inRange));
  }

  _summarise(candles) {
    if (!candles.length) {
      return "";
    }
    const first = candles[0];
    const last = candles[candles.length - 1];
    const delta = last.close - first.close;
    const pct = first.close === 0 ? 0 : (delta / first.close) * 100;
    const sign = delta >= 0 ? "+" : "";
    let high = -Infinity;
    let low = Infinity;
    let volSum = 0;
    let upDays = 0;
    for (const c of candles) {
      if (c.high > high) high = c.high;
      if (c.low < low) low = c.low;
      volSum += c.volume;
      if (c.close > c.open) upDays += 1;
    }
    const avgVol = Math.round(volSum / candles.length);
    return (
      `${candles.length} bars · ${sign}${pct.toFixed(2)}% (${sign}${this.formatPrice(delta)}) · ` +
      `H ${this.formatPrice(high)} · L ${this.formatPrice(low)} · ` +
      `avg vol ${avgVol.toLocaleString("en-IN")} · ${upDays} up day${upDays === 1 ? "" : "s"}`
    );
  }

  // Called by the workspace with the current chart handle so the tool can convert pixels.
  attach(chart) {
    this._chart = chart;
  }

  // Render the committed band (kept between _onUp and the next drag) as an overlay.
  render(layer) {
    if (!layer || this.dragStartX == null || this.dragEndX == null) {
      return;
    }
    const x1 = Math.min(this.dragStartX, this.dragEndX);
    const x2 = Math.max(this.dragStartX, this.dragEndX);
    const band = document.createElement("span");
    band.className = "as-range-band";
    band.style.left = `${Math.round(x1)}px`;
    band.style.width = `${Math.round(x2 - x1)}px`;
    band.style.top = "0";
    band.style.bottom = "0";
    layer.add(band);
  }
}

export { RangeSelectTool };