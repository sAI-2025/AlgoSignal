"""Exponential Moving Average (EMA): recursively-weighted mean of the last *N* closes.

Pure pandas — no Django, DB or network imports (ARCHITECTURE §5 rule 3). Uses the standard
recursive form ``ewm(span=window, adjust=False)`` with ``min_periods=window`` so the first
``window - 1`` values are NaN (undefined until a full window exists), matching the SMA
contract of backward-only, look-ahead-free maths.
"""

from __future__ import annotations

import pandas as pd

from apps.indicators.registry import register


@register("ema")
def ema(df: pd.DataFrame, window: int, column: str = "close") -> pd.Series:
    """Return the EMA of *column* over *window* bars, aligned to *df*'s index."""
    if window <= 0:
        raise ValueError("window must be a positive integer")
    if column not in df.columns:
        raise KeyError(f"column {column!r} not in frame")
    return df[column].ewm(span=window, adjust=False, min_periods=window).mean()
