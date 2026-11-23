from __future__ import annotations

import pandas as pd
import pytest

from apps.indicators.sma import sma


def _frame(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"close": closes},
        index=pd.date_range("2026-11-01", periods=len(closes), freq="D"),
    )


def test_sma3_hand_calculated() -> None:
    df = _frame([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    result = sma(df, window=3)

    # First two are NaN (undefined until a full window exists), then the mean of 3 closes.
    expected = [None, None, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
    assert result.isna().tolist() == [value is None for value in expected]
    assert result.dropna().tolist() == [value for value in expected if value is not None]


def test_sma7_first_six_are_nan() -> None:
    df = _frame(list(range(1, 11)))

    result = sma(df, window=7)

    assert result.iloc[:6].isna().all()
    # SMA7 on 1..10: last value is mean of 4..10 = 7.0
    assert result.iloc[-1] == pytest.approx(7.0)


def test_sma_uses_close_by_default() -> None:
    df = pd.DataFrame(
        {"open": [10, 20, 30], "close": [1, 2, 3]},
        index=pd.date_range("2026-11-01", periods=3, freq="D"),
    )

    result = sma(df, window=2)

    assert result.dropna().tolist() == [1.5, 2.5]


def test_sma_custom_column() -> None:
    df = pd.DataFrame(
        {"high": [10, 20, 30, 40]},
        index=pd.date_range("2026-11-01", periods=4, freq="D"),
    )

    result = sma(df, window=2, column="high")

    assert result.dropna().tolist() == [15.0, 25.0, 35.0]


def test_sma_invalid_window_raises() -> None:
    df = _frame([1, 2, 3])
    with pytest.raises(ValueError):
        sma(df, window=0)


def test_sma_missing_column_raises() -> None:
    df = _frame([1, 2, 3])
    with pytest.raises(KeyError):
        sma(df, window=2, column="volume")
