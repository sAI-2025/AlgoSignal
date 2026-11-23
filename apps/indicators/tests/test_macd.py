from __future__ import annotations

import pandas as pd
import pytest

from apps.indicators.macd import macd


def _frame(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"close": closes},
        index=pd.date_range("2026-11-01", periods=len(closes), freq="D"),
    )


def test_macd_columns_and_warmup() -> None:
    df = _frame(list(range(1, 61)))  # 60 bars
    result = macd(df, fast=12, slow=26, signal=9)
    assert set(result.columns) == {"macd", "signal", "histogram"}
    # slow EMA needs 26 bars -> macd line first valid at index 25 (25 NaN values).
    assert result["macd"].iloc[:25].isna().all()
    assert result["macd"].iloc[25:].notna().all()


def test_macd_histogram_equals_macd_minus_signal() -> None:
    df = _frame(list(range(1, 61)))
    result = macd(df, fast=12, slow=26, signal=9)
    sub = result.dropna()
    hist = sub["histogram"]
    expected = sub["macd"] - sub["signal"]
    for got, exp in zip(hist.tolist(), expected.tolist(), strict=False):
        assert got == pytest.approx(exp)


def test_macd_invalid_params_raise() -> None:
    df = _frame(list(range(1, 61)))
    with pytest.raises(ValueError):
        macd(df, fast=0, slow=26, signal=9)
    with pytest.raises(ValueError):
        macd(df, fast=12, slow=0, signal=9)
    with pytest.raises(ValueError):
        macd(df, fast=12, slow=26, signal=0)


def test_macd_missing_column_raises() -> None:
    df = _frame([1, 2, 3])
    with pytest.raises(KeyError):
        macd(df, column="volume")
