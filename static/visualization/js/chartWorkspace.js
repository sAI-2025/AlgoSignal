// Chart workspace orchestrator (ARCHITECTURE §13.2 "State" + §13.4 toolbar).
// Wires the toolbar, state store, data adapter, chart core and tool plugins together.
// Vanilla ES module, no build step. Reads config from the host element's data-* attributes.

import {
  fetchPayload,
  fetchLiveQuote,
  toSeriesData,
  toVolumeData,
  toLineData,
  indicatorSeriesPoints,
  indicatorSeriesKeys,
} from "./dataAdapter.js";
import {
  createChart,
  addSmaSeries,
  attachMarkers,
  toChartMarkers,
  applyTheme,
  smaColor,
  indicatorColor,
  addLineSeries,
  currentTheme,
} from "./chartCore.js";
import { attachCrosshairInfo } from "./crosshairTooltip.js";
import { OverlayLayer } from "./overlay.js";
import { PinManager } from "./pins.js";
import { MeasureTool } from "./measure.js";
import { RangeSelectTool } from "./rangeSelect.js";
import { MarkerPopover } from "./markerPopover.js";
import { DrawingTool } from "./drawing.js";
import { attachKeyboard } from "./keyboard.js";

const SMA_WINDOWS = [7, 30];
const TIMEFRAMES = ["1D", "1W", "1M", "3M", "6M", "1Y", "3Y", "5Y", "MAX"];
const SERIES_TYPES = ["candlestick", "line", "area"];
// Drag this many bars past the left edge before lazy-history pulls an older window.
const OLDER_THRESHOLD = -2;
const RENDER_DEBOUNCE_MS = 200;

function debounce(fn, ms) {
  let timer = null;
  return (...args) => {
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(() => {
      timer = null;
      fn(...args);
    }, ms);
  };
}

function loadPrefs(symbol) {
  try {
    return JSON.parse(localStorage.getItem(`as.chart.${symbol}`) || "{}");
  } catch {
    return {};
  }
}

function savePrefs(symbol, prefs) {
  try {
    localStorage.setItem(`as.chart.${symbol}`, JSON.stringify(prefs));
  } catch {
    /* storage may be unavailable (private mode) — preferences are best-effort */
  }
}

class ChartWorkspace {
  constructor(root) {
    this.root = root;
    this.symbol = root.dataset.symbol;
    this.apiBase = root.dataset.apiBase || "/charts";
    this.container = root.querySelector("[data-chart-canvas]");
    this.infoTarget = root.querySelector("[data-chart-info]");
    this.tableBody = root.querySelector("[data-chart-table-body]");
    this.tableView = root.querySelector("[data-chart-table]");
    this.legend = root.querySelector("[data-chart-legend]");
    this.pinsList = root.querySelector("[data-pins-list]");
    this.customSmaInput = root.querySelector("[data-custom-sma]");

    const saved = loadPrefs(this.symbol);
    this.state = {
      symbol: this.symbol,
      tf: TIMEFRAMES.includes(saved.tf) ? saved.tf : "1Y",
      seriesType: SERIES_TYPES.includes(saved.seriesType) ? saved.seriesType : "candlestick",
      sma: Array.isArray(saved.sma) && saved.sma.length ? saved.sma : SMA_WINDOWS,
      markers: saved.markers !== false,
      liveOn: false,
      extraIndicators: Array.isArray(saved.extraIndicators) ? saved.extraIndicators : [],
      benchmark: saved.benchmark === true,
    };

    this.handle = null;
    this.smaHandles = new Map();
    this.extraIndicatorHandles = new Map();
    this.benchmarkHandle = null;
    this.markerHandle = null;
    this.detachInfo = null;
    this.liveTimer = null;
    this.liveQuote = null;

    // Tool state + overlays.
    this.tool = null;
    this.overlay = new OverlayLayer(this.container);
    this.candles = [];
    this.markers = [];
    this.loadingOlder = false;
    this.olderExhausted = false;
    this.subscribed = false;
    this.detachKeyboard = null;

    const formatPrice = (value) =>
      Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });

    this.pins = new PinManager(this.symbol, { listTarget: this.pinsList });
    this.pins.onChange = () => this.renderOverlays();
    this.pins.bindListRemove();

    this.measure = new MeasureTool({
      candles: [],
      formatPrice,
      onReadout: (text) => this.setInfo(text),
    });

    this.rangeTool = new RangeSelectTool(this.container, {
      candles: [],
      formatPrice,
      onStats: (text) => this.setInfo(text),
    });

    this.popover = new MarkerPopover(this.container);

    this.bindToolbar();
    this.bindKeyboard();
    this.render();
  }

  bindToolbar() {
    this.root.querySelectorAll("[data-tf]").forEach((btn) => {
      btn.addEventListener("click", () => this.setState({ tf: btn.dataset.tf }));
    });
    this.root.querySelectorAll("[data-series]").forEach((btn) => {
      btn.addEventListener("click", () => this.setState({ seriesType: btn.dataset.series }));
    });
    this.root.querySelectorAll("[data-sma-toggle]").forEach((input) => {
      input.addEventListener("change", () => this.recomputeSma());
    });
    this.root.querySelectorAll("[data-indicator]").forEach((btn) => {
      btn.addEventListener("click", () => this.toggleIndicator(btn));
    });
    const markersToggle = this.root.querySelector("[data-markers-toggle]");
    if (markersToggle) {
      markersToggle.addEventListener("change", () =>
        this.setState({ markers: markersToggle.checked }),
      );
    }
    const liveBtn = this.root.querySelector("[data-action='live']");
    if (liveBtn) {
      liveBtn.addEventListener("click", () => this.toggleLive());
    }
    this.root.querySelectorAll("[data-tool]").forEach((btn) => {
      btn.addEventListener("click", () => this.setTool(btn.dataset.tool));
    });
    if (this.customSmaInput) {
      const commit = () => this.recomputeSma();
      this.customSmaInput.addEventListener("change", commit);
      this.customSmaInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          commit();
          this.customSmaInput.blur();
        }
      });
    }
    const fullscreenBtn = this.root.querySelector("[data-action='fullscreen']");
    if (fullscreenBtn) {
      fullscreenBtn.addEventListener("click", () => this.toggleFullscreen());
    }
    const benchmarkBtn = this.root.querySelector("[data-action='benchmark']");
    if (benchmarkBtn) {
      benchmarkBtn.addEventListener("click", () => this.toggleBenchmark());
    }
    const pngBtn = this.root.querySelector("[data-action='png']");
    if (pngBtn) {
      pngBtn.addEventListener("click", () => this.exportPng());
    }
    const csvBtn = this.root.querySelector("[data-action='csv']");
    if (csvBtn) {
      csvBtn.addEventListener("click", () => this.exportCsv());
    }
    const tableToggle = this.root.querySelector("[data-action='table']");
    if (tableToggle) {
      tableToggle.addEventListener("click", () => this.toggleTable());
    }
    const clearBtn = this.root.querySelector("[data-action='clear']");
    if (clearBtn) {
      clearBtn.addEventListener("click", () => this.clearTools());
    }
  }

  bindKeyboard() {
    this.detachKeyboard = attachKeyboard({
      scrollBy: (n) => this.scrollBy(n),
      zoom: (factor) => this.zoom(factor),
      jump: (where) => this.jump(where),
      tool: (name) => this.setTool(name),
      toggle: (name) => this.toggle(name),
      clear: () => this.clearTools(),
    });
  }

  setState(patch) {
    Object.assign(this.state, patch);
    savePrefs(this.symbol, {
      tf: this.state.tf,
      seriesType: this.state.seriesType,
      sma: this.state.sma,
      markers: this.state.markers,
      extraIndicators: this.state.extraIndicators,
      benchmark: this.state.benchmark,
    });
    this.olderExhausted = false;
    this.syncToolbar();
    this._debouncedRender();
  }

  _debouncedRender = debounce(() => this.render(), RENDER_DEBOUNCE_MS);

  // SMA list = checked defaults ∪ any custom periods typed into the V9 input.
  recomputeSma() {
    const checked = [...this.root.querySelectorAll("[data-sma-toggle]:checked")].map((i) =>
      Number(i.value),
    );
    const custom = this.parseCustomSma();
    const sma = [...new Set([...checked, ...custom])].sort((a, b) => a - b);
    this.setState({ sma });
  }

  parseCustomSma() {
    if (!this.customSmaInput) {
      return [];
    }
    return this.customSmaInput.value
      .split(",")
      .map((token) => token.trim())
      .filter(Boolean)
      .map(Number)
      .filter((n) => Number.isInteger(n) && n > 0 && n <= 500);
  }

  toggleIndicator(btn) {
    const name = btn.dataset.indicator;
    const params = this.indicatorParams(btn);
    const next = [...this.state.extraIndicators];
    const idx = next.findIndex(
      (s) => s.name === name && JSON.stringify(s.params || {}) === JSON.stringify(params || {}),
    );
    if (idx >= 0) {
      next.splice(idx, 1);
      btn.classList.remove("active");
    } else {
      next.push({ name, params });
      btn.classList.add("active");
    }
    this.setState({ extraIndicators: next });
  }

  indicatorParams(btn) {
    const raw = btn.dataset.params;
    if (raw) {
      try {
        return JSON.parse(raw);
      } catch {}
    }
    const params = {};
    ["window", "fast", "slow", "signal", "numStd"].forEach((key) => {
      const v = btn.dataset[key];
      if (v !== undefined) {
        params[key] = Number(v);
      }
    });
    return params;
  }

  serializeIndicators() {
    return this.state.extraIndicators
      .map((spec) => {
        const vals = Object.values(spec.params || {}).join(":");
        return vals ? `${spec.name}:${vals}` : spec.name;
      })
      .join(",");
  }

  syncToolbar() {
    this.root.querySelectorAll("[data-tf]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tf === this.state.tf);
    });
    this.root.querySelectorAll("[data-series]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.series === this.state.seriesType);
    });
    this.root.querySelectorAll("[data-tool]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tool === this.tool);
    });
    const markersToggle = this.root.querySelector("[data-markers-toggle]");
    if (markersToggle) {
      markersToggle.checked = this.state.markers;
    }
    const benchmarkBtn = this.root.querySelector("[data-action='benchmark']");
    if (benchmarkBtn) {
      benchmarkBtn.classList.toggle("active", this.state.benchmark);
      benchmarkBtn.classList.toggle("btn-success", this.state.benchmark);
      benchmarkBtn.classList.toggle("btn-outline-secondary", !this.state.benchmark);
    }
  }

  setTool(name) {
    const next = this.tool === name ? null : name;
    this.tool = next;
    if (this.drawing) {
      if (next === "trendline" || next === "horizontal") {
        this.drawing.activate(next);
      } else {
        this.drawing.deactivate();
      }
    }

    if (next === "range") {
      this.setScrollEnabled(false);
      this.rangeTool.start();
    } else {
      this.setScrollEnabled(true);
      this.rangeTool.stop();
    }
    if (next !== "measure") {
      this.measure.reset();
    }
    this.popover.hide();
    this.syncToolbar();
    this.renderOverlays();
  }

  clearTools() {
    this.setTool(null);
    if (this.drawing) {
      this.drawing.clear();
    }
    this.measure.reset();
    this.rangeTool.reset();
    this.popover.hide();
    this.renderOverlays();
  }

  setScrollEnabled(enabled) {
    if (!this.handle) {
      return;
    }
    this.handle.chart.applyOptions({
      handleScroll: enabled,
      handleScale: enabled,
    });
  }

  async render() {
    const { tf, sma, markers, seriesType } = this.state;
    let payload;
    try {
      payload = await fetchPayload(this.symbol, {
        tf,
        sma,
        markers,
        ind: this.serializeIndicators(), benchmark: this.state.benchmark,
      });
    } catch (error) {
      this.showError(error);
      return;
    }
    if (!this.handle) {
      this.handle = createChart(this.container, { seriesType });
      this.ensureSubscriptions();
      this.drawing = new DrawingTool(this.handle.chart, this.handle.priceSeries, this.overlay);
    }
    this.candles = payload.candles;
    this.markers = payload.markers;
    this.measure.setCandles(payload.candles);
    this.rangeTool.setCandles(payload.candles);
    this.popover.setMarkers(payload.markers);
    this.rangeTool.attach(this.handle.chart);
    this.paint(payload, seriesType);
    this.paintTable(payload.candles);
    this.syncLegend(payload, sma);
    this.syncInfoPlugin();
    this.renderOverlays();
    this.syncLiveToolbar();
    if (this.state.liveOn && !this.liveTimer) {
      this.startLive();
    }
    if (!this.state.liveOn && this.liveTimer) {
      this.stopLive();
    }
  }

  ensureSubscriptions() {
    if (this.subscribed) {
      return;
    }
    this.subscribed = true;
    this.handle.chart.subscribeClick((param) => this.onChartClick(param));
    this.handle.chart.subscribeVisibleLogicalRangeChange((range) => {
      if (range) {
        this.maybeLoadOlder(range);
      }
      this.renderOverlays();
    });
  }

  onChartClick(param) {
    if (!param || !param.point) {
      return;
    }
    if (this.tool === "pin") {
      const price = this.handle.priceSeries.coordinateToPrice(param.point.y);
      if (param.time && Number.isFinite(price)) {
        this.pins.add(param.time, price);
        this.renderOverlays();
      }
      return;
    }
    if (this.tool === "measure") {
      if (this.measure.handleClick(this.handle.chart, this.handle.priceSeries, param)) {
        this.renderOverlays();
      }
      return;
    }
    if (this.tool === "range") {
      return;
    }
    if ((this.tool === "trendline" || this.tool === "horizontal") && this.drawing) {
      if (this.drawing.handleClick(this.handle.chart, this.handle.priceSeries, param)) {
        this.renderOverlays();
      }
      return;
    }
    // No tool active → a click opens the marker popover when it hits a signal.
    this.popover.handleClick(param);
  }

  maybeLoadOlder(range) {
    if (
      this.loadingOlder ||
      this.olderExhausted ||
      this.state.tf === "MAX" ||
      !this.candles.length ||
      range.from >= OLDER_THRESHOLD
    ) {
      return;
    }
    this.loadOlder();
  }

  async loadOlder() {
    if (this.loadingOlder) {
      return;
    }
    this.loadingOlder = true;
    const { tf, sma, markers, extraIndicators } = this.state;
    const oldest = this.candles[0].time;
    const oldCount = this.candles.length;
    const prevRange = this.handle?.chart.timeScale().getVisibleLogicalRange();
    try {
      const older = await fetchPayload(this.symbol, {
        tf,
        sma,
        markers,
        before: oldest,
        force: true,
        ind: this.serializeIndicators(), benchmark: this.state.benchmark,
      });
      const olderCandles = older.candles || [];
      if (!olderCandles.length || olderCandles[0].time >= oldest) {
        this.olderExhausted = true;
        return;
      }
      this.candles = this.mergeCandles(this.candles, olderCandles);
      this.markers = this.mergeMarkers(this.markers, older.markers);
      const indicators = {};
      const specs = [
        ...sma.map((period) => ({ name: "sma", params: { window: period } })),
        ...extraIndicators,
      ];
      specs.forEach((spec) => {
        Object.assign(indicators, indicatorSeriesPoints(spec, this.candles));
      });
      this.measure.setCandles(this.candles);
      this.rangeTool.setCandles(this.candles);
      this.popover.setMarkers(this.markers);
      this.paint({ candles: this.candles, indicators, markers: this.markers }, this.state.seriesType, {
        fit: false,
      });
      this.syncInfoPlugin();
      this.paintTable(this.candles);
      this.syncLegend({ markers: this.markers }, sma);
      // Prepending older bars shifts every logical index right; nudge the viewport so the
      // analyst keeps looking at the same candles after the older window loads in.
      const prepended = this.candles.length - oldCount;
      if (prevRange && prepended > 0) {
        this.handle.chart.timeScale().setVisibleLogicalRange({
          from: prevRange.from + prepended,
          to: prevRange.to + prepended,
        });
      }
      this.renderOverlays();
    } catch (error) {
      this.showError(error);
    } finally {
      this.loadingOlder = false;
    }
  }

  mergeCandles(current, older) {
    const byTime = new Map();
    older.forEach((c) => byTime.set(c.time, c));
    current.forEach((c) => byTime.set(c.time, c));
    return [...byTime.values()].sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
  }

  mergeMarkers(current, older) {
    const byKey = new Map();
    [...(older || []), ...(current || [])].forEach((m) => {
      byKey.set(`${m.time}|${m.type}`, m);
    });
    return [...byKey.values()].sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
  }

  paint(payload, seriesType, { fit = true } = {}) {
    const { chart, priceSeries, volumeSeries } = this.handle;
    volumeSeries.setData(toVolumeData(payload.candles));

    if (seriesType === "line" || seriesType === "area") {
      priceSeries.setData(
        toLineData(payload.candles.map((c) => ({ time: c.time, value: c.close }))),
      );
    } else {
      priceSeries.setData(toSeriesData(payload.candles));
    }

    // SMA overlays
    this.smaHandles.forEach((series) => chart.removeSeries(series));
    this.smaHandles.clear();
    this.state.sma.forEach((period, index) => {
      const points = (payload.indicators[`sma_${period}`] || []).map((p) => ({
        time: p.time,
        value: p.value,
      }));
      const series = addSmaSeries(chart, period, smaColor(index));
      series.setData(points);
      this.smaHandles.set(`sma_${period}`, series);
    });

    // Extra indicator overlays (EMA, RSI, MACD, Bollinger, volume SMA…)
    this.extraIndicatorHandles.forEach((series) => chart.removeSeries(series));
    this.extraIndicatorHandles.clear();
    this.state.extraIndicators.forEach((spec, index) => {
      const keys = indicatorSeriesKeys(spec);
      const pointsByKey = {};
      keys.forEach((key) => {
        pointsByKey[key] = (payload.indicators[key] || []).map((p) => ({
          time: p.time,
          value: p.value,
        }));
      });
      keys.forEach((key, k) => {
        const series = addLineSeries(chart, indicatorColor(index * 3 + k));
        series.setData(pointsByKey[key]);
        this.extraIndicatorHandles.set(key, series);
      });
    });

    // Benchmark overlay (compare mode): re-based index series.
    if (this.benchmarkHandle) {
      chart.removeSeries(this.benchmarkHandle);
      this.benchmarkHandle = null;
    }
    if (this.state.benchmark) {
      const points = (payload.indicators["benchmark"] || []).map((p) => ({
        time: p.time,
        value: p.value,
      }));
      if (points.length) {
        this.benchmarkHandle = addLineSeries(chart, "#0ea5e9");
        this.benchmarkHandle.setData(points);
      }
    }

    // Markers
    if (this.markerHandle) {
      this.markerHandle.detach();
      this.markerHandle = null;
    }
    if (this.state.markers && payload.markers.length) {
      this.markerHandle = attachMarkers(priceSeries, toChartMarkers(payload.markers));
    }

    if (fit) {
      chart.timeScale().fitContent();
    }
  }

  renderOverlays() {
    if (!this.handle) {
      return;
    }
    this.overlay.clear();
    this.pins.render(this.overlay, this.handle);
    this.measure.render(this.overlay, this.handle);
    if (this.tool === "range") {
      this.rangeTool.render(this.overlay);
    }
    if (this.drawing && (this.tool === "trendline" || this.tool === "horizontal")) {
      this.drawing.render();
    }
  }

  syncLegend(payload, sma) {
    if (!this.legend) {
      return;
    }
    const items = sma.map(
      (period, index) =>
        `<span><span class="swatch" style="background:${smaColor(index)}"></span>SMA ${period}</span>`,
    );
    this.state.extraIndicators.forEach((spec, index) => {
      const keys = indicatorSeriesKeys(spec);
      keys.forEach((key, k) => {
        items.push(
          `<span><span class="swatch" style="background:${indicatorColor(index * 3 + k)}"></span>${indicatorLabel(spec, key)}</span>`,
        );
      });
    });
    if (this.state.benchmark) {
      items.push(`<span><span class="swatch" style="background:#0ea5e9"></span>Benchmark (^NSEI)</span>`);
    }
    if (payload.markers && payload.markers.length) {
      items.push(`<span><span class="swatch" style="background:#16a34a"></span>Bullish</span>`);
      items.push(`<span><span class="swatch" style="background:#dc2626"></span>Bearish</span>`);
    }
    this.legend.innerHTML = items.join("");
  }

  syncInfoPlugin() {
    if (this.detachInfo) {
      this.detachInfo();
    }
    const seriesMap = new Map();
    this.smaHandles.forEach((series, label) => {
      seriesMap.set(label.replace("sma_", "SMA "), series);
    });
    this.state.extraIndicators.forEach((spec, index) => {
      const keys = indicatorSeriesKeys(spec);
      keys.forEach((key, k) => {
        const series = this.extraIndicatorHandles.get(key);
        if (series) {
          seriesMap.set(indicatorLabel(spec, key), series);
        }
      });
    });
    if (this.state.benchmark && this.benchmarkHandle) {
      seriesMap.set("Benchmark (^NSEI)", this.benchmarkHandle);
    }
    const formatPrice = (value) =>
      Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });
    this.detachInfo = attachCrosshairInfo(this.handle.chart, {
      priceSeries: this.handle.priceSeries,
      seriesMap,
      target: this.infoTarget,
      formatPrice,
    });

    // Visual crosshair line that follows the cursor across the chart pane.
    const crosshairEl = this.root.querySelector(".as-crosshair");
    if (crosshairEl) {
      const detachCrosshair = this.handle.chart.subscribeCrosshairMove((param) => {
        if (!param || !param.point) {
          crosshairEl.classList.remove("visible");
          return;
        }
        crosshairEl.style.left = `${Math.round(param.point.x)}px`;
        crosshairEl.classList.add("visible");
      });
      this.detachCrosshair = detachCrosshair;
    }
  }

  setInfo(text) {
    if (!this.infoTarget) {
      return;
    }
    this.infoTarget.innerHTML = text
      ? `<span class="as-tool-readout">${escapeHtml(text)}</span>`
      : '<span class="text-muted">Hover over the chart for OHLC + SMA values.</span>';
  }

  paintTable(candles) {
    if (!this.tableBody) {
      return;
    }
    this.tableBody.innerHTML = candles
      .slice()
      .reverse()
      .map(
        (c) =>
          `<tr><td>${c.time}</td><td class="text-end">${c.open}</td><td class="text-end">${c.high}</td>` +
          `<td class="text-end">${c.low}</td><td class="text-end">${c.close}</td>` +
          `<td class="text-end">${c.volume}</td></tr>`,
      )
      .join("");
  }

  toggleTable() {
    if (!this.tableView) {
      return;
    }
    this.tableView.classList.toggle("d-none");
  }

  // V12 Live mode: poll the live quote endpoint and update only the on-screen last bar.
  // Nothing is persisted; polling pauses when the tab is hidden or the market is closed.
  toggleLive() {
    this.setState({ liveOn: !this.state.liveOn });
  }

  // V14 Compare-with-index: overlay the benchmark (default ^NSEI) re-based to the
  // main symbol's first close so both series start at the same level. Re-fetches the
  // chart with ``benchmark=1`` so the server supplies the index series.
  toggleBenchmark() {
    this.setState({ benchmark: !this.state.benchmark });
  }

  startLive() {
    if (this.liveTimer || !this.handle) {
      return;
    }
    const intervalMs = Number(this.root.dataset.liveInterval || 30000);
    this.pollLive();
    this.liveTimer = setInterval(() => this.pollLive(), intervalMs);
  }

  stopLive() {
    if (this.liveTimer) {
      clearInterval(this.liveTimer);
      this.liveTimer = null;
    }
  }

  async pollLive() {
    if (!this.state.liveOn || !this.handle) {
      return;
    }
    try {
      const quote = await fetchLiveQuote(this.symbol);
      this.applyLiveQuote(quote);
    } catch (error) {
      // Fail silently on live polls — a stale last bar is better than breaking the chart.
      if (this.infoTarget) {
        this.infoTarget.innerHTML = `<span class="text-danger small">Live: ${escapeHtml(error.message)}</span>`;
      }
    }
  }

  applyLiveQuote(quote) {
    if (!this.handle || !this.candles.length) {
      return;
    }
    const { priceSeries } = this.handle;
    const lastCandle = this.candles[this.candles.length - 1];
    const quoteTime = new Date(quote.as_of).toISOString().slice(0, 10);
    const price = Number(quote.price);

    // Only update today's (last) bar; ignore quotes for other days.
    if (quoteTime !== lastCandle.time || !Number.isFinite(price)) {
      return;
    }

    const updated = {
      ...lastCandle,
      close: price,
      high: Math.max(lastCandle.high, price),
      low: Math.min(lastCandle.low, price),
    };
    this.candles[this.candles.length - 1] = updated;

    // series.update replaces/appends the bar at `time` — the on-screen last bar only.
    priceSeries.update({ time: updated.time, ...updated });

    this.liveQuote = quote;
    this.syncInfoPlugin();
    this.syncLiveToolbar();
    this.paintTable(this.candles);
  }

  syncLiveToolbar() {
    const btn = this.root.querySelector("[data-action='live']");
    const indicator = btn && btn.querySelector(".as-live-indicator");
    if (!btn || !indicator) {
      return;
    }
    if (this.state.liveOn) {
      btn.classList.add("active", "btn-success");
      btn.classList.remove("btn-outline-secondary");
      indicator.textContent = `● LIVE · ${this.liveQuote?.as_of.slice(11, 16) ?? ""} IST`;
    } else {
      btn.classList.remove("active", "btn-success");
      btn.classList.add("btn-outline-secondary");
      indicator.textContent = "● LIVE";
    }
  }

  scrollBy(bars) {
    if (!this.handle) {
      return;
    }
    const range = this.handle.chart.timeScale().getVisibleLogicalRange();
    if (!range) {
      return;
    }
    const span = range.to - range.from;
    const from = range.from + bars;
    this.handle.chart.timeScale().setVisibleLogicalRange({ from, to: from + span });
  }

  zoom(factor) {
    if (!this.handle) {
      return;
    }
    const range = this.handle.chart.timeScale().getVisibleLogicalRange();
    if (!range) {
      return;
    }
    const center = (range.from + range.to) / 2;
    const half = ((range.to - range.from) / 2) * factor;
    this.handle.chart.timeScale().setVisibleLogicalRange({ from: center - half, to: center + half });
  }

  jump(where) {
    if (!this.handle) {
      return;
    }
    if (where === "start") {
      this.handle.chart.timeScale().setVisibleLogicalRange({ from: -2, to: 22 });
    } else {
      this.handle.chart.timeScale().fitContent();
    }
  }

  toggle(name) {
    if (name === "markers") {
      this.setState({ markers: !this.state.markers });
    } else if (name === "table") {
      this.toggleTable();
    } else if (name === "fullscreen") {
      this.toggleFullscreen();
    }
  }

  toggleFullscreen() {
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      this.root.requestFullscreen?.();
    }
  }

  exportPng() {
    if (!this.handle) {
      return;
    }
    const canvas = this.handle.chart.takeScreenshot();
    canvas.toBlob((blob) => {
      if (!blob) {
        return;
      }
      downloadBlob(blob, `${this.symbol}-${this.state.tf}.png`);
    });
  }

  async exportCsv() {
    try {
      const payload = await fetchPayload(this.symbol, {
        tf: this.state.tf,
        sma: this.state.sma,
        markers: this.state.markers,
        force: true,
        ind: this.serializeIndicators(), benchmark: this.state.benchmark,
      });
      const header = "date,open,high,low,close,volume\n";
      const rows = payload.candles
        .map((c) => `${c.time},${c.open},${c.high},${c.low},${c.close},${c.volume}`)
        .join("\n");
      downloadBlob(new Blob([header + rows], { type: "text/csv" }), `${this.symbol}-${this.state.tf}.csv`);
    } catch (error) {
      this.showError(error);
    }
  }

  showError(error) {
    if (this.infoTarget) {
      this.infoTarget.innerHTML = `<span class="text-danger">${escapeHtml(error.message)}</span>`;
    }
  }

  destroy() {
    if (this.liveTimer) {
      clearInterval(this.liveTimer);
    }
    if (this.detachInfo) {
      this.detachInfo();
    }
    if (this.detachCrosshair) {
      this.detachCrosshair();
    }
    if (this.detachKeyboard) {
      this.detachKeyboard();
    }
    if (this.markerHandle) {
      this.markerHandle.detach();
    }
    if (this.handle) {
      this.handle.chart.remove();
      this.handle = null;
    }
    this.pins.destroy();
    this.overlay.destroy();
  }
}

function indicatorLabel(spec, key) {
  const { name, params = {} } = spec;
  const window = params.window;
  const base =
    { sma: "SMA", ema: "EMA", rsi: "RSI", volume_sma: "Vol SMA", macd: "MACD", bollinger: "Bollinger" }[name] ||
    name;
  if (name === "macd") {
    const part = { macd: "MACD", macd_signal: "Signal", macd_histogram: "Histogram" }[key];
    return part ? `${base} ${part}` : base;
  }
  if (name === "bollinger") {
    const part = {
      bollinger_upper: "Upper",
      bollinger_middle: "Middle",
      bollinger_lower: "Lower",
    }[key];
    return part ? `${base} ${part}` : base;
  }
  return window ? `${base} ${window}` : base;
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

// Auto-mount every [data-chart-workspace] on the page; theme changes re-apply live.
function mountAll() {
  const instances = [];
  document.querySelectorAll("[data-chart-workspace]").forEach((root) => {
    instances.push(new ChartWorkspace(root));
  });

  const themeObserver = new MutationObserver(() => {
    const theme = currentTheme();
    instances.forEach((ws) => {
      if (ws.handle) {
        applyTheme(ws.handle, theme);
      }
    });
  });
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-bs-theme"],
  });

  window.addEventListener("beforeunload", () => {
    themeObserver.disconnect();
    instances.forEach((ws) => ws.destroy());
  });

  document.addEventListener("visibilitychange", () => {
    const visible = document.visibilityState === "visible";
    instances.forEach((ws) => {
      if (visible && ws.state.liveOn && !ws.liveTimer) {
        ws.startLive();
      }
      if (!visible && ws.liveTimer) {
        ws.stopLive();
      }
    });
  });

  return instances;
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mountAll);
} else {
  mountAll();
}

export { ChartWorkspace, mountAll };