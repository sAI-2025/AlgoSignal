from __future__ import annotations

import pandas as pd
import pytest

from apps.indicators.volume_sma import volume_sma


def _frame(volumes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"volume": volumes, "close": volumes},
        index=pd.date_range("2026-11-01", periods=len(volumes), freq="D"),
    )


def test_volume_sma3_hand_calculated() -> None:
    df = _frame([10, 20, 30, 40, 50])
    result = volume_sma(df, window=3)
    # rolling(window=3): first two NaN, then mean of 3 volumes.
    expected = [None, None, 20.0, 30.0, 40.0]
    assert result.isna().tolist() == [v is None for v in expected]
    assert result.dropna().tolist() == [v for v in expected if v is not None]


def test_volume_sma_default_column_is_volume() -> None:
    df = _frame([10, 20, 30, 40, 50])
    result = volume_sma(df, window=2)
    assert result.dropna().tolist() == pytest.approx([15.0, 25.0, 35.0, 45.0])


def test_volume_sma_invalid_window_raises() -> None:
    df = _frame([10, 20, 30])
    with pytest.raises(ValueError):
        volume_sma(df, window=0)


def test_volume_sma_missing_column_raises() -> None:
    df = _frame([10, 20, 30])
    with pytest.raises(KeyError):
        volume_sma(df, window=2, column="volume_missing")
