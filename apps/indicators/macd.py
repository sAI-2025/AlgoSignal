"""MACD (Moving Average Convergence Divergence): trend-following momentum indicator.

Pure pandas — no Django, DB or network imports. Returns a DataFrame with columns
``macd`` (fast EMA − slow EMA), ``signal`` (EMA of the MACD line) and ``histogram``
(macd − signal). Leading values are NaN until the slow EMA is defined. Backward-only,
look-ahead-free.
"""

from __future__ import annotations

import pandas as pd

from apps.indicators.registry import register


@register("macd")
def macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    column: str = "close",
) -> pd.DataFrame:
    """Return MACD / signal / histogram as a DataFrame aligned to *df*'s index."""
    if fast <= 0 or slow <= 0 or signal <= 0:
        raise ValueError("fast, slow and signal must be positive integers")
    if column not in df.columns:
        raise KeyError(f"column {column!r} not in frame")
    ema_fast = df[column].ewm(span=fast, adjust=False, min_periods=slow).mean()
    ema_slow = df[column].ewm(span=slow, adjust=False, min_periods=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "histogram": histogram},
        index=df.index,
    )
