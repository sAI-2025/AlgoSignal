// Crosshair tooltip / info-panel plugin (ARCHITECTURE §13.4).
// Subscribes to crosshair moves and writes an OHLC + all active indicator readout
// into a target element. Uses requestAnimationFrame to avoid per-frame DOM thrash.
// Isolated so it can be removed without touching the chart core.

function attachCrosshairInfo(chart, { priceSeries, seriesMap, target, formatPrice }) {
  if (!target) {
    return () => {};
  }

  let frame = null;
  let lastParams = null;

  const paint = () => {
    frame = null;
    if (!lastParams || !lastParams.time || !lastParams.seriesData.size) {
      render(target, null, priceSeries, seriesMap, formatPrice);
      return;
    }
    render(target, lastParams, priceSeries, seriesMap, formatPrice);
  };

  const handler = (param) => {
    lastParams = param;
    if (frame === null) {
      frame = requestAnimationFrame(paint);
    }
  };

  chart.subscribeCrosshairMove(handler);
  return () => {
    chart.unsubscribeCrosshairMove(handler);
    if (frame !== null) {
      cancelAnimationFrame(frame);
    }
  };
}

function render(target, param, priceSeries, seriesMap, formatPrice) {
  const data = param ? param.seriesData.get(priceSeries) : null;
  if (!data) {
    target.innerHTML = '<span class="text-muted">Hover over the chart for OHLC + indicator values.</span>';
    return;
  }

  const indicatorCells = [];
  for (const [label, series] of seriesMap) {
    const point = param.seriesData.get(series);
    const value = point && Number.isFinite(point.value) ? formatPrice(point.value) : "—";
    indicatorCells.push(
      `<span class="as-tooltip-cell"><span class="as-tooltip-label">${escapeHtml(label)}</span> <span class="as-tooltip-value">${value}</span></span>`
    );
  }

  const parts = [`<strong>${escapeHtml(String(data.time))}</strong>`];
  if (typeof data.open === "number") {
    parts.push(`O ${formatPrice(data.open)}`);
    parts.push(`H ${formatPrice(data.high)}`);
    parts.push(`L ${formatPrice(data.low)}`);
    parts.push(`C ${formatPrice(data.close)}`);
  } else {
    parts.push(`Close ${formatPrice(data.value)}`);
  }
  if (indicatorCells.length) {
    parts.push(indicatorCells.join(" "));
  }

  target.innerHTML = parts.join(' <span class="text-muted">·</span> ');
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

export { attachCrosshairInfo };
