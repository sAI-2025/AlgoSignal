"""Relative Strength Index (RSI): momentum oscillator, 0-100, Wilder's smoothing.

Pure pandas — no Django, DB or network imports. ``delta = close.diff()``; average gain /
average loss are smoothed with ``ewm(alpha=1/window, adjust=False, min_periods=window)``.
First ``window`` values are NaN (need ``window`` changes to seed the averages). No look-ahead.
"""

from __future__ import annotations

import pandas as pd

from apps.indicators.registry import register


@register("rsi")
def rsi(df: pd.DataFrame, window: int = 14, column: str = "close") -> pd.Series:
    """Return the RSI of *column* over *window* bars, aligned to *df*'s index."""
    if window <= 0:
        raise ValueError("window must be a positive integer")
    if column not in df.columns:
        raise KeyError(f"column {column!r} not in frame")
    delta = df[column].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
