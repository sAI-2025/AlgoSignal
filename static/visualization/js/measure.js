// Measure tool (PRD V7): two clicks drop a ruler. Shows price delta, percent move and
// the number of bars between the two anchors. Pure overlay + readout; it never mutates
// chart data. Bars are counted from the loaded candle times.

import { place, timeForX, xForTime, yForPrice } from "./overlay.js";

class MeasureTool {
  constructor({ candles, formatPrice, onReadout } = {}) {
    this.candles = candles || [];
    this.formatPrice = formatPrice || ((v) => String(v));
    this.onReadout = onReadout || (() => {});
    this.anchor = null;
    this.result = null;
  }

  setCandles(candles) {
    this.candles = candles || [];
  }

  reset() {
    this.anchor = null;
    this.result = null;
    this.onReadout("");
  }

  // Feed a chart click. Returns true when the click was consumed by the tool.
  handleClick(chart, series, param) {
    const price = this._priceAt(series, param);
    if (price == null) {
      return false;
    }
    const time = param.time ?? timeForX(chart, param.point.x);
    if (time == null) {
      return false;
    }

    if (!this.anchor) {
      this.anchor = { time, price };
      this.result = null;
      this.onReadout("Click a second point to measure.");
      return true;
    }

    const a = this.anchor;
    this.result = { a, b: { time, price } };
    this.anchor = null;
    this.onReadout(this._summarise(this.result));
    return true;
  }

  _priceAt(series, param) {
    if (param.point && Number.isFinite(param.point.y)) {
      const price = series.coordinateToPrice(param.point.y);
      if (Number.isFinite(price)) {
        return price;
      }
    }
    return null;
  }

  _summarise({ a, b }) {
    const delta = b.price - a.price;
    const pct = a.price === 0 ? 0 : (delta / a.price) * 100;
    const bars = this._barsBetween(a.time, b.time);
    const sign = delta >= 0 ? "+" : "";
    const barsText = bars == null ? "" : ` · ${bars} bar${bars === 1 ? "" : "s"}`;
    return (
      `${this.formatPrice(a.price)} → ${this.formatPrice(b.price)} · ` +
      `${sign}${this.formatPrice(delta)} (${sign}${pct.toFixed(2)}%)${barsText}`
    );
  }

  // Number of candles strictly between the two anchor times; null if either is unknown.
  _barsBetween(t1, t2) {
    const times = this.candles.map((c) => c.time);
    const i1 = times.indexOf(t1);
    const i2 = times.indexOf(t2);
    if (i1 === -1 || i2 === -1) {
      return null;
    }
    return Math.abs(i2 - i1);
  }

  render(layer, handle) {
    if (!layer || !this.result) {
      return;
    }
    const { chart, priceSeries } = handle;
    const { a, b } = this.result;
    const x1 = xForTime(chart, a.time);
    const x2 = xForTime(chart, b.time);
    const y1 = yForPrice(priceSeries, a.price);
    const y2 = yForPrice(priceSeries, b.price);
    if (x1 == null || x2 == null || y1 == null || y2 == null) {
      return;
    }

    const left = Math.min(x1, x2);
    const width = Math.abs(x2 - x1);
    const box = document.createElement("span");
    box.className = "as-measure-box";
    box.style.left = `${Math.round(left)}px`;
    box.style.top = `${Math.round(Math.min(y1, y2))}px`;
    box.style.width = `${Math.round(width)}px`;
    box.style.height = `${Math.round(Math.abs(y2 - y1))}px`;
    layer.add(box);

    for (const [x, y] of [
      [x1, y1],
      [x2, y2],
    ]) {
      const dot = document.createElement("span");
      dot.className = "as-measure-dot";
      place(dot, x, y);
      layer.add(dot);
    }
  }
}

export { MeasureTool };