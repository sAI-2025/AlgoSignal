// Drawing tools (trendline, horizontal line) for the chart workspace.
// Drawings are anchored to (time, price) and re-positioned on zoom/pan via the overlay
// layer, so they stay attached to the bars they were drawn on. No persistence in v1.1
// — drawings live only for the chart session.

import { place } from "./overlay.js";

class DrawingTool {
  constructor(chart, priceSeries, overlay) {
    this.chart = chart;
    this.priceSeries = priceSeries;
    this.overlay = overlay;
    this.mode = null; // null | "trendline" | "horizontal"
    this.draft = null; // {id, type, pts:[{time,price}]} awaiting second point (trendline)
    this.drawings = []; // [{id, type, pts:[{time,price}]}]
    this.nextId = 1;
  }

  activate(mode) {
    this.mode = mode;
    this.draft = null;
  }

  deactivate() {
    this.mode = null;
    this.draft = null;
  }

  handleClick(chart, priceSeries, param) {
    if (!this.mode || !param || !param.point) {
      return false;
    }
    const time = param.time;
    const price = priceSeries.coordinateToPrice(param.point.y);
    if (!time || !Number.isFinite(price)) {
      return false;
    }
    const pt = { time, price };
    if (this.mode === "horizontal") {
      this.drawings.push({ id: this.nextId++, type: "horizontal", pts: [pt] });
      this.mode = null;
      return true;
    }
    if (this.mode === "trendline") {
      if (!this.draft) {
        this.draft = { id: this.nextId++, type: "trendline", pts: [pt] };
        // stay active awaiting the second point
      } else {
        this.draft.pts.push(pt);
        this.drawings.push(this.draft);
        this.draft = null;
        this.mode = null;
      }
      return true;
    }
    return false;
  }

  render() {
    const scale = this.chart.timeScale();
    const width = this.overlay.el.clientWidth || this.chart.options().width || 0;
    for (const drawing of this.drawings) {
      const p0 = drawing.pts[0];
      const x0 = scale.timeToCoordinate(p0.time);
      const y0 = this.priceSeries.priceToCoordinate(p0.price);
      if (x0 == null || y0 == null) {
        continue;
      }
      const node = document.createElement("div");
      node.style.position = "absolute";
      node.style.pointerEvents = "none";
      if (drawing.type === "horizontal") {
        node.style.left = "0";
        node.style.width = "100%";
        node.style.top = `${Math.round(y0)}px`;
        node.style.height = "1px";
        node.style.borderTop = "1px solid #0ea5e9";
      } else if (drawing.type === "trendline" && drawing.pts.length === 2) {
        const p1 = drawing.pts[1];
        const x1 = scale.timeToCoordinate(p1.time);
        const y1 = this.priceSeries.priceToCoordinate(p1.price);
        if (x1 == null || y1 == null) {
          continue;
        }
        const dx = x1 - x0;
        const dy = y1 - y0;
        const dist = Math.hypot(dx, dy);
        const angle = (Math.atan2(dy, dx) * 180) / Math.PI;
        node.style.left = `${Math.round(x0)}px`;
        node.style.top = `${Math.round(y0)}px`;
        node.style.width = `${Math.round(dist)}px`;
        node.style.height = "2px";
        node.style.background = "#0ea5e9";
        node.style.transformOrigin = "0 0";
        node.style.transform = `rotate(${angle}deg)`;
      }
      this.overlay.add(node);
    }
    // Draft preview (trendline awaiting second point): drawn from first point to the
    // last known crosshair position is omitted for simplicity; the first point shows as a dot.
    if (this.draft && this.draft.type === "trendline") {
      const p0 = this.draft.pts[0];
      const x0 = scale.timeToCoordinate(p0.time);
      const y0 = this.priceSeries.priceToCoordinate(p0.price);
      if (x0 != null && y0 != null) {
        const dot = document.createElement("div");
        dot.style.position = "absolute";
        dot.style.left = `${Math.round(x0 - 3)}px`;
        dot.style.top = `${Math.round(y0 - 3)}px`;
        dot.style.width = "6px";
        dot.style.height = "6px";
        dot.style.borderRadius = "50%";
        dot.style.background = "#0ea5e9";
        this.overlay.add(dot);
      }
    }
  }

  clear() {
    this.drawings = [];
    this.nextId = 1;
    this.draft = null;
    this.mode = null;
  }
}

export { DrawingTool };
