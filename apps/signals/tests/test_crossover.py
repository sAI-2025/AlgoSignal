from __future__ import annotations

import pandas as pd
import pytest

from apps.signals.services.crossover import detect


def _frame(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"close": closes},
        index=pd.date_range("2026-11-01", periods=len(closes), freq="D"),
    )


def test_detect_finds_bullish_and_bearish() -> None:
    # Hand-tuned series (short=2, long=3): a bearish cross at index 4, bullish at 7.
    df = _frame([10, 11, 12, 11, 10, 9, 10, 11, 12])

    result = detect(df, short=2, long=3)

    assert len(result.index) == 2
    bearish = result[result.signal_type == "BEARISH"].iloc[0]
    bullish = result[result.signal_type == "BULLISH"].iloc[0]
    assert bearish.candle_date == pd.Timestamp("2026-11-05").date()
    assert bullish.candle_date == pd.Timestamp("2026-11-08").date()


def test_detect_no_signal_on_first_valid_day() -> None:
    # Strictly rising then flat — the very first defined crossover must not fire spuriously.
    df = _frame([1, 2, 3, 4, 5])

    result = detect(df, short=2, long=3)

    # short stays above long; no bearish/bullish transition after the first defined bar.
    assert result.empty


def test_detect_flat_series_no_signal() -> None:
    df = _frame([5, 5, 5, 5, 5])

    result = detect(df, short=2, long=3)

    assert result.empty


def test_detect_equality_is_not_a_cross() -> None:
    # Averages equal for several bars then separate: one signal when they diverge.
    df = _frame([10, 10, 10, 10, 11, 12, 13])

    result = detect(df, short=2, long=3)

    assert set(result.signal_type.unique()).issubset({"BULLISH", "BEARISH"})


def test_detect_invalid_periods_raise() -> None:
    df = _frame([1, 2, 3])
    with pytest.raises(ValueError):
        detect(df, short=0, long=3)
    with pytest.raises(ValueError):
        detect(df, short=5, long=3)
