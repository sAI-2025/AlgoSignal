from __future__ import annotations

import pandas as pd
import pytest

from apps.indicators.ema import ema


def _frame(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"close": closes},
        index=pd.date_range("2026-11-01", periods=len(closes), freq="D"),
    )


def test_ema2_hand_calculated() -> None:
    df = _frame([1, 2, 3, 4, 5])
    result = ema(df, window=2)
    # ewm(span=2, adjust=False) -> alpha = 2/3; min_periods=2 -> index 0 is NaN.
    # y[1] = 2/3*2 + 1/3*1 = 5/3
    # y[2] = 2/3*3 + 1/3*(5/3) = 23/9
    # y[3] = 2/3*4 + 1/3*(23/9) = 95/27
    # y[4] = 2/3*5 + 1/3*(95/27) = 365/81
    expected = [None, 5 / 3, 23 / 9, 95 / 27, 365 / 81]
    assert result.isna().tolist() == [v is None for v in expected]
    got = result.dropna().tolist()
    exp = [v for v in expected if v is not None]
    for got_v, exp_v in zip(got, exp, strict=False):
        assert got_v == pytest.approx(exp_v)


def test_ema_constant_series_equals_constant() -> None:
    df = _frame([7.0, 7.0, 7.0, 7.0, 7.0])
    result = ema(df, window=3)
    assert result.dropna().tolist() == pytest.approx([7.0, 7.0, 7.0])


def test_ema_invalid_window_raises() -> None:
    df = _frame([1, 2, 3])
    with pytest.raises(ValueError):
        ema(df, window=0)


def test_ema_missing_column_raises() -> None:
    df = _frame([1, 2, 3])
    with pytest.raises(KeyError):
        ema(df, window=2, column="volume")
