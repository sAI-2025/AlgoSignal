// Data adapter for the chart workspace (ARCHITECTURE §13.2).
// Fetches the chart payload, normalises numbers, caches by (symbol, tf, sma), and
// exposes an onUpdate hook. No DOM or chart-library access — pure data plumbing.

const cache = new Map();

// Cache key for a payload request. Callers can force a refresh to bypass the cache.
function stableKey(symbol, tf, sma, markers, ind, before, benchmark) {
  return `${symbol}|${tf}|${sma.join(",")}|${markers ? 1 : 0}|${ind}|${before || ""}|${benchmark ? 1 : 0}`;
}

async function fetchPayload(
  symbol,
  {
    tf = "1Y",
    sma = [7, 30],
    markers = true,
    ind = "",
    benchmark = false,
    before = null,
    force = false,
  } = {},
) {
  const key = stableKey(symbol, tf, sma, markers, ind, before, benchmark);
  if (!force && cache.has(key)) {
    return cache.get(key);
  }

  const params = new URLSearchParams({
    tf,
    sma: sma.join(","),
    markers: markers ? "1" : "0",
  });
  if (ind) {
    params.set("ind", ind);
  }
  if (benchmark) {
    params.set("benchmark", "1");
  }
  if (before) {
    params.set("before", before);
  }
  const response = await fetch(`/api/v1/charts/${encodeURIComponent(symbol)}/?${params.toString()}`, {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail?.error?.message || `Chart request failed (${response.status})`);
  }
  const payload = await response.json();
  cache.set(key, payload);
  return payload;
}

// Fetch a single live quote (never persisted, cached 30 s by the server).
async function fetchLiveQuote(symbol) {
  const response = await fetch(`/api/v1/live/quote/${encodeURIComponent(symbol)}/`, {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail?.error?.message || `Live quote request failed (${response.status})`);
  }
  return response.json();
}

// Convert a candle payload into the arrays Lightweight Charts expects.
function toSeriesData(candles) {
  return candles.map((c) => ({
    time: c.time,
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
  }));
}

function toVolumeData(candles) {
  return candles.map((c) => ({
    time: c.time,
    value: c.volume,
    color: c.close >= c.open ? "rgba(22,163,74,0.4)" : "rgba(220,38,38,0.4)",
  }));
}

function toLineData(points) {
  return points.map((p) => ({ time: p.time, value: p.value }));
}

// Client-side SMA over a candle array, matching the backend's rolling mean with
// min_periods=window (the first ``period - 1`` bars have no value and are skipped).
// Used only to keep SMA continuity across lazy-history merges; the initial load still
// uses the server-computed indicators.
function smaPoints(period, candles) {
  const out = [];
  let sum = 0;
  for (let i = 0; i < candles.length; i += 1) {
    sum += candles[i].close;
    if (i >= period) {
      sum -= candles[i - period].close;
    }
    if (i >= period - 1) {
      out.push({ time: candles[i].time, value: sum / period });
    }
  }
  return out;
}

// Unmasked recursive EMA (seed = first close, alpha = 2/(period+1)), indexed by candle.
function unmaskedEma(candles, period) {
  const alpha = 2 / (period + 1);
  const out = [];
  let prev = candles[0].close;
  out[0] = prev;
  for (let i = 1; i < candles.length; i += 1) {
    prev = alpha * candles[i].close + (1 - alpha) * prev;
    out[i] = prev;
  }
  return out;
}

// EMA valid from index period-1 onwards, mirroring ewm(span=period, adjust=False).
function emaPoints(period, candles) {
  const raw = unmaskedEma(candles, period);
  const out = [];
  for (let i = period - 1; i < candles.length; i += 1) {
    out.push({ time: candles[i].time, value: raw[i] });
  }
  return out;
}

// RSI (Wilder's smoothing, alpha = 1/period), valid from index period onwards.
function rsiPoints(period, candles) {
  const alpha = 1 / period;
  const out = [];
  let avgGain = 0;
  let avgLoss = 0;
  let prevClose = candles[0].close;
  for (let i = 1; i < candles.length; i += 1) {
    const delta = candles[i].close - prevClose;
    prevClose = candles[i].close;
    const gain = delta > 0 ? delta : 0;
    const loss = delta < 0 ? -delta : 0;
    avgGain = alpha * gain + (1 - alpha) * avgGain;
    avgLoss = alpha * loss + (1 - alpha) * avgLoss;
    if (i >= period) {
      const rs = avgLoss === 0 ? Infinity : avgGain / avgLoss;
      out.push({ time: candles[i].time, value: 100 - 100 / (1 + rs) });
    }
  }
  return out;
}

// Volume SMA, valid from index period-1 onwards.
function volumeSmaPoints(period, candles) {
  const out = [];
  let sum = 0;
  for (let i = 0; i < candles.length; i += 1) {
    sum += candles[i].volume ?? 0;
    if (i >= period) {
      sum -= candles[i - period].volume ?? 0;
    }
    if (i >= period - 1) {
      out.push({ time: candles[i].time, value: sum / period });
    }
  }
  return out;
}

function isNaN(value) {
  return Number.isNaN(value);
}

// MACD: macd line + signal EMA + histogram, both EMAs min_periods=slow (server parity).
function macdPoints(candles, { fast = 12, slow = 26, signal = 9 } = {}) {
  const n = candles.length;
  const fastEma = unmaskedEma(candles, fast);
  const slowEma = unmaskedEma(candles, slow);
  const macd = Array(n).fill(NaN);
  for (let i = slow - 1; i < n; i += 1) {
    macd[i] = fastEma[i] - slowEma[i];
  }
  const alpha = 2 / (signal + 1);
  const signalOut = Array(n).fill(NaN);
  let sigPrev = NaN;
  let seen = 0;
  for (let i = slow - 1; i < n; i += 1) {
    if (isNaN(macd[i])) {
      continue;
    }
    seen += 1;
    sigPrev = seen === 1 ? macd[i] : alpha * macd[i] + (1 - alpha) * sigPrev;
    if (seen >= signal) {
      signalOut[i] = sigPrev;
    }
  }
  const macdPts = [];
  const signalPts = [];
  const histPts = [];
  for (let i = slow - 1; i < n; i += 1) {
    if (!isNaN(macd[i])) {
      macdPts.push({ time: candles[i].time, value: macd[i] });
    }
    if (!isNaN(signalOut[i])) {
      signalPts.push({ time: candles[i].time, value: signalOut[i] });
    }
    if (!isNaN(macd[i]) && !isNaN(signalOut[i])) {
      histPts.push({ time: candles[i].time, value: macd[i] - signalOut[i] });
    }
  }
  return { macd: macdPts, signal: signalPts, histogram: histPts };
}

// Bollinger Bands: rolling mean +- numStd * rolling sample std, valid from index window-1.
function bollingerPoints(candles, { window = 20, numStd = 2 } = {}) {
  const n = candles.length;
  const middle = Array(n).fill(NaN);
  const stdDev = Array(n).fill(NaN);
  for (let i = window - 1; i < n; i += 1) {
    const windowCloses = [];
    for (let j = i - window + 1; j <= i; j += 1) {
      windowCloses.push(candles[j].close);
    }
    const mean = windowCloses.reduce((a, b) => a + b, 0) / window;
    const variance =
      windowCloses.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(window - 1, 1);
    middle[i] = mean;
    stdDev[i] = Math.sqrt(variance);
  }
  const upperPts = [];
  const middlePts = [];
  const lowerPts = [];
  for (let i = window - 1; i < n; i += 1) {
    if (isNaN(middle[i])) {
      continue;
    }
    upperPts.push({ time: candles[i].time, value: middle[i] + numStd * stdDev[i] });
    middlePts.push({ time: candles[i].time, value: middle[i] });
    lowerPts.push({ time: candles[i].time, value: middle[i] - numStd * stdDev[i] });
  }
  return { upper: upperPts, middle: middlePts, lower: lowerPts };
}

// Indicator spec -> list of series keys emitted by that spec (mirrors the server's naming).
function indicatorSeriesKeys(spec) {
  const { name, params = {} } = spec;
  if (name === "macd") {
    return ["macd", "macd_signal", "macd_histogram"];
  }
  if (name === "bollinger") {
    return ["bollinger_upper", "bollinger_middle", "bollinger_lower"];
  }
  const window = params.window;
  return window ? [`${name}_${window}`] : [name];
}

// Indicator spec -> {seriesKey: points}, mirroring the server's key naming so lazy-history
// merges stay consistent with the initial server payload.
function indicatorSeriesPoints(spec, candles) {
  const { name, params = {} } = spec;
  if (name === "sma") {
    return { [`sma_${params.window}`]: smaPoints(params.window, candles) };
  }
  if (name === "ema") {
    return { [`ema_${params.window}`]: emaPoints(params.window, candles) };
  }
  if (name === "rsi") {
    return { [`rsi_${params.window}`]: rsiPoints(params.window, candles) };
  }
  if (name === "volume_sma") {
    return { [`volume_sma_${params.window}`]: volumeSmaPoints(params.window, candles) };
  }
  if (name === "macd") {
    const parts = macdPoints(candles, params);
    return {
      macd: parts.macd,
      macd_signal: parts.signal,
      macd_histogram: parts.histogram,
    };
  }
  if (name === "bollinger") {
    const parts = bollingerPoints(candles, params);
    return {
      bollinger_upper: parts.upper,
      bollinger_middle: parts.middle,
      bollinger_lower: parts.lower,
    };
  }
  return {};
}

function invalidate() {
  cache.clear();
}

export {
  fetchPayload,
  fetchLiveQuote,
  toSeriesData,
  toVolumeData,
  toLineData,
  smaPoints,
  emaPoints,
  rsiPoints,
  macdPoints,
  bollingerPoints,
  volumeSmaPoints,
  indicatorSeriesPoints,
  indicatorSeriesKeys,
  invalidate,
};