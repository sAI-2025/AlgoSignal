from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from apps.indicators.rsi import rsi


def _frame(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"close": closes},
        index=pd.date_range("2026-11-01", periods=len(closes), freq="D"),
    )


def test_rsi_monotonic_up_is_100() -> None:
    # Strictly rising closes: only gains, average loss = 0 -> RSI = 100 after warmup.
    closes = list(range(1, 21))  # 1..20
    df = _frame(closes)
    result = rsi(df, window=14)
    # diff() makes index 0 NaN; ewm(min_periods=14) first valid at index 14.
    assert result.iloc[:14].isna().all()
    assert result.iloc[14:].eq(100.0).all()


def test_rsi_monotonic_down_is_0() -> None:
    closes = list(range(20, 0, -1))  # 20..1
    df = _frame(closes)
    result = rsi(df, window=14)
    assert result.iloc[:14].isna().all()
    assert result.iloc[14:].eq(0.0).all()


def test_rsi_stays_in_bounds() -> None:
    rng = np.random.default_rng(7)
    closes = (100 + np.cumsum(rng.normal(0, 2, 60))).tolist()
    df = pd.DataFrame(
        {"close": closes},
        index=pd.date_range("2026-11-01", periods=len(closes), freq="D"),
    )
    result = rsi(df, window=14)
    valid = result.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


def test_rsi_invalid_window_raises() -> None:
    df = _frame([1, 2, 3])
    with pytest.raises(ValueError):
        rsi(df, window=0)


def test_rsi_missing_column_raises() -> None:
    df = _frame([1, 2, 3])
    with pytest.raises(KeyError):
        rsi(df, window=2, column="volume")
