// Chart core (ARCHITECTURE §13.2): create the Lightweight Charts instance, manage
// price/volume panes, SMA overlays, markers, and theme tokens read from CSS variables.
// No data fetching and no business rules — everything here is "how the chart looks".

const THEME_VARS = {
  light: {
    layout: { background: { color: "transparent" }, textColor: "#334155" },
    grid: { vertLines: { color: "rgba(51,65,85,0.08)" }, horzLines: { color: "rgba(51,65,85,0.08)" } },
  },
  dark: {
    layout: { background: { color: "transparent" }, textColor: "#cbd5e1" },
    grid: { vertLines: { color: "rgba(203,213,225,0.10)" }, horzLines: { color: "rgba(203,213,225,0.10)" } },
  },
};

const SMA_COLORS = ["#2563eb", "#f59e0b", "#8b5cf6", "#10b981", "#ef4444"];

function currentTheme() {
  return document.documentElement.getAttribute("data-bs-theme") === "dark" ? "dark" : "light";
}

function themeOptions(theme = currentTheme()) {
  return {
    ...THEME_VARS[theme],
    autoSize: true,
    localization: { locale: "en-IN" },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false, timeVisible: false, secondsVisible: false },
    crosshair: { mode: 0 },
  };
}

// Create the chart with a price series of the requested type and a volume histogram.
// Returns handles the workspace wires toolbars and tooltips to.
function createChart(container, { seriesType = "candlestick", theme } = {}) {
  const chart = LightweightCharts.createChart(container, themeOptions(theme));

  const priceSeries =
    seriesType === "line"
      ? chart.addSeries(LightweightCharts.LineSeries, { color: "#2563eb", lineWidth: 2 })
      : seriesType === "area"
        ? chart.addSeries(LightweightCharts.AreaSeries, {
            lineColor: "#2563eb",
            topColor: "rgba(37,99,235,0.4)",
            bottomColor: "rgba(37,99,235,0.02)",
          })
        : chart.addSeries(LightweightCharts.CandlestickSeries, {
            upColor: "#16a34a",
            downColor: "#dc2626",
            borderVisible: false,
            wickUpColor: "#16a34a",
            wickDownColor: "#dc2626",
          });

  const volumeSeries = chart.addSeries(LightweightCharts.HistogramSeries, {
    priceFormat: { type: "volume" },
    priceScaleId: "volume",
  });
  volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });

  return { chart, priceSeries, volumeSeries };
}

function addSmaSeries(chart, period, color) {
  return chart.addSeries(LightweightCharts.LineSeries, {
    color,
    lineWidth: 1,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  });
}

// v5 markers are a series primitive (createSeriesMarkers). Returns a handle whose
// setMarkers() updates the arrow overlay; call the handle's detach() on teardown.
function attachMarkers(series, markers) {
  if (typeof LightweightCharts.createSeriesMarkers !== "function") {
    return { setMarkers: () => {}, detach: () => {} };
  }
  return LightweightCharts.createSeriesMarkers(series, markers || []);
}

function toChartMarkers(markers) {
  return (markers || []).map((m) => ({
    time: m.time,
    position: m.type === "BULLISH" ? "belowBar" : "aboveBar",
    color: m.type === "BULLISH" ? "#16a34a" : "#dc2626",
    shape: m.type === "BULLISH" ? "arrowUp" : "arrowDown",
    text: m.type === "BULLISH" ? "Bullish" : "Bearish",
  }));
}

function applyTheme(handle, theme = currentTheme()) {
  handle.chart.applyOptions(themeOptions(theme));
}

function smaColor(index) {
  return SMA_COLORS[index % SMA_COLORS.length];
}

function addLineSeries(chart, color) {
  return chart.addSeries(LightweightCharts.LineSeries, {
    color,
    lineWidth: 1,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  });
}

const INDICATOR_COLORS = ["#06b6d4", "#84cc16", "#f97316", "#ec4899", "#6366f1"];
function indicatorColor(index) {
  return INDICATOR_COLORS[index % INDICATOR_COLORS.length];
}

export {
  createChart,
  addSmaSeries,
  addLineSeries,
  attachMarkers,
  toChartMarkers,
  applyTheme,
  smaColor,
  indicatorColor,
  currentTheme,
  THEME_VARS,
};