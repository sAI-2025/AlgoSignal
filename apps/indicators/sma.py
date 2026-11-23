"""Simple Moving Average (SMA): the mean of the last *N* closes.

Pure pandas — no Django, DB or network imports (ARCHITECTURE §5 rule 3). The first
``window - 1`` values are NaN by design because a full window is required.
"""

from __future__ import annotations

import pandas as pd

from apps.indicators.registry import register


@register("sma")
def sma(df: pd.DataFrame, window: int, column: str = "close") -> pd.Series:
    """Return the SMA of *column* over *window* bars, aligned to *df*'s index."""
    if window <= 0:
        raise ValueError("window must be a positive integer")
    if column not in df.columns:
        raise KeyError(f"column {column!r} not in frame")
    return df[column].rolling(window=window, min_periods=window).mean()
