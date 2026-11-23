"""Assemble the chart workspace payload (ARCHITECTURE §13.3).

One JSON object with candles + indicator series + signal markers + meta. Reads only:
candles from ``market_data`` selectors, indicator maths from the ``indicators`` registry,
markers from stored ``signals``. No writes, no provider calls.

SMA is computed on the **unadjusted close** to match the indicator contract (ARCHITECTURE
§10, PRD "SMA uses Close"), so ``basis`` is reported as ``"unadjusted"``.

Indicator specs are ``(name, params)`` tuples looked up in the ``indicators`` registry, so
adding an indicator (EMA, RSI, MACD, Bollinger, volume SMA) needs no caller change beyond
passing its spec.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from django.utils import timezone

from apps.companies.models import Company
from apps.indicators.registry import get_indicator
from apps.market_data.selectors import (
    company_last_candle_date,
    load_benchmark_candles,
    load_candles_range,
)
from apps.visualization.services.markers import signals_to_markers
from apps.visualization.services.timeframes import DEFAULT_TF, resolve_range

MAX_BARS = 5000
BENCHMARK_DEFAULT = "^NSEI"

# Positional → named parameter order for indicators whose params are passed positionally
# in the ``ind=name:p1:p2`` query form. Adding an indicator: register its function, then
# add its param order here.
INDICATOR_PARAM_ORDER: dict[str, list[str]] = {
    "sma": ["window"],
    "ema": ["window"],
    "rsi": ["window"],
    "macd": ["fast", "slow", "signal"],
    "bollinger": ["window", "num_std"],
    "volume_sma": ["window"],
}


def _coerce_number(text: str):
    """Convert a query param token to int, then float, else string."""
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def parse_indicator_param(value: str) -> tuple[str, dict]:
    """Parse a single ``ind=name:p1:p2`` token into ``(name, params)``.

    Positional params are mapped to named params via :data:`INDICATOR_PARAM_ORDER`.
    """
    parts = value.split(":")
    name = parts[0]
    if name not in INDICATOR_PARAM_ORDER:
        raise ValueError(f"Unknown indicator: {name!r}")
    raw_params = parts[1:]
    expected = INDICATOR_PARAM_ORDER[name]
    if len(raw_params) > len(expected):
        raise ValueError(
            f"Indicator {name!r} takes {len(expected)} param(s), got {len(raw_params)}"
        )
    params = {key: _coerce_number(tok) for key, tok in zip(expected, raw_params, strict=False)}
    return name, params


def _series_points(values) -> list[dict]:
    return [
        {"time": index.date().isoformat(), "value": round(float(value), 4)}
        for index, value in values.items()
        if not pd.isna(value)
    ]


def _indicator_series(frame, specs: list[tuple[str, dict]]) -> dict[str, list[dict]]:
    """Build ``{series_key: points}`` for every ``(name, params)`` spec."""
    series: dict[str, list[dict]] = {}
    seen: set[tuple[str, frozenset]] = set()
    for name, params in specs:
        marker = (name, frozenset(params.items()))
        if marker in seen:
            continue
        seen.add(marker)
        result = get_indicator(name)(frame, **params)
        if isinstance(result, pd.DataFrame):
            for col in result.columns:
                key = col if col == name else f"{name}_{col}"
                series[key] = _series_points(result[col])
        else:  # Series
            window = params.get("window")
            key = f"{name}_{window}" if window is not None else name
            series[key] = _series_points(result)
    return series


def _default_specs() -> list[tuple[str, dict]]:
    return [("sma", {"window": 7}), ("sma", {"window": 30})]


def _benchmark_series(frame, benchmark_symbol: str, start: date, end: date) -> list[dict]:
    """Rebase the benchmark index to the main symbol's first close so both series
    start at the same level and diverge by relative performance (compare mode)."""
    bench = load_benchmark_candles(benchmark_symbol, start, end)
    if bench.empty or frame.empty:
        return []
    main_first_close = float(frame["close"].iloc[0])
    bench_first = bench["close"].dropna()
    if bench_first.empty:
        return []
    bench_first_close = float(bench_first.iloc[0])
    ratio = main_first_close / bench_first_close
    bench_map = {
        index.date().isoformat(): float(value) * ratio
        for index, value in bench["close"].items()
        if not pd.isna(value)
    }
    points: list[dict] = []
    for index, _row in frame.iterrows():
        key = index.date().isoformat()
        if key in bench_map:
            points.append({"time": key, "value": round(bench_map[key], 4)})
    return points


def build_chart_payload(
    company: Company,
    *,
    tf: str = DEFAULT_TF,
    indicator_specs: list[tuple[str, dict]] | None = None,
    markers: bool = True,
    before: date | None = None,
    benchmark: str | None = None,
) -> dict:
    """Return the chart payload dict for *company*.

    ``tf`` is a timeframe key (1D…MAX); ``indicator_specs`` are ``(name, params)`` tuples
    resolved through the indicators registry; ``markers`` toggles signal markers; ``before``
    anchors the range end (defaults to the company's last stored candle); ``benchmark`` is an
    index symbol (e.g. ``^NSEI``) to overlay as a re-based comparison series.
    """
    if indicator_specs is None:
        indicator_specs = _default_specs()
    end = before or company_last_candle_date(company.id)

    if end is None:
        indicators: dict[str, list[dict]] = {
            f"sma_{p['window']}": [] for _, p in indicator_specs if "window" in p
        }
        if benchmark:
            indicators["benchmark"] = []
        return {
            "symbol": company.nse_code,
            "tf": tf,
            "basis": "unadjusted",
            "candles": [],
            "indicators": indicators,
            "markers": [],
            "meta": {
                "from": None,
                "to": None,
                "count": 0,
                "last_candle_date": None,
                "complete_only": True,
                "generated_at": timezone.now().isoformat(),
            },
        }

    start, end = resolve_range(tf, end)
    frame = load_candles_range(company.id, start=start, end=end, limit=MAX_BARS)

    indicators = _indicator_series(frame, indicator_specs)
    if benchmark:
        indicators["benchmark"] = _benchmark_series(frame, benchmark, start, end)

    return {
        "symbol": company.nse_code,
        "tf": tf,
        "basis": "unadjusted",
        "candles": _candles(frame),
        "indicators": indicators,
        "markers": signals_to_markers(company.id, start=start, end=end) if markers else [],
        "meta": {
            "from": start.isoformat() if start else None,
            "to": end.isoformat(),
            "count": len(frame),
            "last_candle_date": end.isoformat(),
            "complete_only": True,
            "generated_at": timezone.now().isoformat(),
        },
    }


def _candles(frame) -> list[dict]:
    rows: list[dict] = []
    for index, row in frame.iterrows():
        rows.append(
            {
                "time": index.date().isoformat(),
                "open": round(float(row["open"]), 4),
                "high": round(float(row["high"]), 4),
                "low": round(float(row["low"]), 4),
                "close": round(float(row["close"]), 4),
                "volume": int(row["volume"]) if row["volume"] is not None else 0,
            }
        )
    return rows


def parse_sma_periods(raw: str | None) -> list[int]:
    """Parse a ``sma=7,30`` query value into a validated, de-duplicated list of periods."""
    if not raw:
        return [7, 30]
    periods: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            period = int(token)
        except ValueError as exc:
            raise ValueError(f"Invalid SMA period: {token!r}") from exc
        if period <= 0 or period > 500:
            raise ValueError(f"SMA period out of range (1..500): {period}")
        if period not in periods:
            periods.append(period)
    return periods or [7, 30]


def sma_periods_to_specs(periods: list[int]) -> list[tuple[str, dict]]:
    """Convert a list of SMA periods into ``("sma", {"window": n})`` specs."""
    specs = []
    for p in periods:
        if p <= 0 or p > 500:
            raise ValueError(f"SMA period out of range (1..500): {p}")
        specs.append(("sma", {"window": p}))
    return specs
