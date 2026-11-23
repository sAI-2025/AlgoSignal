// Overlay layer + coordinate helpers shared by the chart tools (V5–V7, V18).
// A single absolutely-positioned layer sits over the chart canvas; tools paint DOM
// nodes into it and re-position them when the chart pans/zooms. No data logic here.

class OverlayLayer {
  constructor(container) {
    this.container = container;
    this.el = document.createElement("div");
    this.el.className = "as-overlay-layer";
    container.appendChild(this.el);
  }

  clear() {
    this.el.replaceChildren();
  }

  add(node) {
    this.el.appendChild(node);
    return node;
  }

  destroy() {
    this.el.remove();
  }
}

// x pixel for a time value, or null if the bar is outside the current view.
function xForTime(chart, time) {
  if (time == null) {
    return null;
  }
  const scale = chart.timeScale();
  const x = scale.timeToCoordinate(time);
  return Number.isFinite(x) ? x : null;
}

// y pixel for a price on the price series, or null if not resolvable.
function yForPrice(series, price) {
  if (price == null) {
    return null;
  }
  const y = series.priceToCoordinate(price);
  return Number.isFinite(y) ? y : null;
}

// Inverse of xForTime: map a pixel back to the bar time under the cursor.
function timeForX(chart, x) {
  const time = chart.timeScale().coordinateToTime(x);
  return time ?? null;
}

function place(node, x, y) {
  node.style.left = `${Math.round(x)}px`;
  node.style.top = `${Math.round(y)}px`;
}

export { OverlayLayer, xForTime, yForPrice, timeForX, place };