"""Volume SMA: simple moving average of the volume column.

Pure pandas — no Django, DB or network imports. Returns a Series aligned to *df*'s index;
the first ``window - 1`` values are NaN. Used for the volume pane overlay (v1.1).
"""

from __future__ import annotations

import pandas as pd

from apps.indicators.registry import register


@register("volume_sma")
def volume_sma(df: pd.DataFrame, window: int, column: str = "volume") -> pd.Series:
    """Return the SMA of *column* (default ``volume``) over *window* bars."""
    if window <= 0:
        raise ValueError("window must be a positive integer")
    if column not in df.columns:
        raise KeyError(f"column {column!r} not in frame")
    return df[column].rolling(window=window, min_periods=window).mean()
