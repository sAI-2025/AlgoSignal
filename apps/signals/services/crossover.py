"""Pure SMA crossover detection.

No Django, DB or network imports (ARCHITECTURE §5 rule 3). Input must be a DataFrame
sorted ascending by date with lower-case columns; output is a DataFrame with one row per
crossover: ``[candle_date, signal_type, short_sma, long_sma, close]``.

Rules (ARCHITECTURE §11.2, PRD BR-04):
    * Bullish: previous short SMA ≤ previous long SMA **and** current short > current long.
    * Bearish: previous short SMA ≥ previous long SMA **and** current short < current long.
    * Both SMAs must be defined on both bars (no signal on the first valid day).
    * SMAs are rounded to 6 dp before comparison to avoid float noise.
"""

from __future__ import annotations

import pandas as pd

from apps.indicators.sma import sma

OUTPUT_COLUMNS = ["candle_date", "signal_type", "short_sma", "long_sma", "close"]


def detect(df: pd.DataFrame, short: int, long: int) -> pd.DataFrame:
    """Return crossover rows for the given SMA periods."""
    if short <= 0 or long <= short:
        raise ValueError("require 0 < short < long")

    short_sma = sma(df, short).round(6)
    long_sma = sma(df, long).round(6)
    diff = short_sma - long_sma
    prev = diff.shift(1)  # backward-looking only
    valid = diff.notna() & prev.notna()

    bullish = valid & (prev <= 0) & (diff > 0)
    bearish = valid & (prev >= 0) & (diff < 0)

    closes = df["close"]
    dates = df.index
    rows: list[dict] = []
    for position in range(len(df)):
        if bullish.iloc[position]:
            signal_type = "BULLISH"
        elif bearish.iloc[position]:
            signal_type = "BEARISH"
        else:
            continue
        rows.append(
            {
                "candle_date": pd.Timestamp(dates[position]).date(),
                "signal_type": signal_type,
                "short_sma": float(short_sma.iloc[position]),
                "long_sma": float(long_sma.iloc[position]),
                "close": float(closes.iloc[position]),
            }
        )

    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
