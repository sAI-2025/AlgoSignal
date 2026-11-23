from __future__ import annotations

import pandas as pd
import pytest

from apps.indicators.bollinger import bollinger


def _frame(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"close": closes},
        index=pd.date_range("2026-11-01", periods=len(closes), freq="D"),
    )


def test_bollinger_columns_and_warmup() -> None:
    df = _frame(list(range(1, 41)))  # 40 bars
    result = bollinger(df, window=20, num_std=2)
    assert set(result.columns) == {"upper", "middle", "lower"}
    assert result.iloc[:19].isna().all().all()  # rolling(window=20): first 19 NaN
    assert result.iloc[19:].notna().all().all()


def test_bollinger_bands_are_symmetric_around_middle() -> None:
    df = _frame(list(range(1, 41)))
    result = bollinger(df, window=20, num_std=2)
    sub = result.dropna()
    half_width = sub["upper"] - sub["middle"]
    for got, exp in zip(half_width.tolist(), (sub["middle"] - sub["lower"]).tolist(), strict=False):
        assert got == pytest.approx(exp)


def test_bollinger_invalid_window_raises() -> None:
    df = _frame([1, 2, 3])
    with pytest.raises(ValueError):
        bollinger(df, window=0)


def test_bollinger_missing_column_raises() -> None:
    df = _frame([1, 2, 3])
    with pytest.raises(KeyError):
        bollinger(df, column="volume")
