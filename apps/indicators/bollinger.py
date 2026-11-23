"""Bollinger Bands: SMA middle band with upper/lower bands at +/- *num_std* standard deviations.

Pure pandas — no Django, DB or network imports. Returns a DataFrame with columns
``upper``, ``middle`` (SMA), ``lower``. Leading values are NaN until the rolling window
is defined. Backward-only, look-ahead-free.
"""

from __future__ import annotations

import pandas as pd

from apps.indicators.registry import register


@register("bollinger")
def bollinger(
    df: pd.DataFrame,
    window: int = 20,
    column: str = "close",
    num_std: float = 2.0,
) -> pd.DataFrame:
    """Return Bollinger Bands (upper, middle, lower) as a DataFrame aligned to *df*'s index."""
    if window <= 0:
        raise ValueError("window must be a positive integer")
    if column not in df.columns:
        raise KeyError(f"column {column!r} not in frame")
    typical = df[column]
    middle = typical.rolling(window=window, min_periods=window).mean()
    std = typical.rolling(window=window, min_periods=window).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    return pd.DataFrame({"upper": upper, "middle": middle, "lower": lower}, index=df.index)
