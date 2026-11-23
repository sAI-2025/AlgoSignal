from __future__ import annotations

import pandas as pd
import pytest

from apps.indicators.registry import available, get_indicator, register


def test_registry_returns_sma() -> None:
    indicator = get_indicator("sma")
    df = pd.DataFrame(
        {"close": [1.0, 2.0, 3.0]},
        index=pd.date_range("2026-11-01", periods=3, freq="D"),
    )

    result = indicator(df, window=2)

    assert result.dropna().tolist() == [1.5, 2.5]


def test_registry_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_indicator("does_not_exist")


def test_registry_available_lists_sma() -> None:
    assert "sma" in available()


def test_registry_available_lists_all_v11_indicators() -> None:
    names = set(available())
    for name in ("ema", "rsi", "macd", "bollinger", "volume_sma"):
        assert name in names, f"{name!r} not registered"


def test_registry_custom_registration() -> None:
    @register("double")
    def _double(df, column="close"):
        return df[column] * 2

    assert get_indicator("double") is _double
