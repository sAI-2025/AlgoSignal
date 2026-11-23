from __future__ import annotations

from apps.scanner.services.params import ScannerParams


def test_defaults_are_valid() -> None:
    params = ScannerParams()

    assert params.is_valid
    assert params.errors() == {}


def test_short_must_be_positive() -> None:
    params = ScannerParams(short_period=0)

    assert "short_period" in params.errors()


def test_long_must_exceed_short() -> None:
    params = ScannerParams(short_period=7, long_period=5)

    assert params.errors()["long_period"] == "Long SMA must be greater than Short SMA."


def test_lookback_must_be_positive() -> None:
    assert "lookback_days" in ScannerParams(lookback_days=0).errors()


def test_max_stocks_must_be_positive() -> None:
    assert "max_stocks" in ScannerParams(max_stocks=0).errors()


def test_fetch_window_includes_buffer() -> None:
    params = ScannerParams(short_period=7, long_period=30, lookback_days=10)

    # long + lookback + buffer(10)
    assert params.fetch_window() == 50


def test_from_mapping() -> None:
    params = ScannerParams.from_mapping(
        {"short_period": "5", "long_period": "20", "lookback_days": "3", "max_stocks": "10"}
    )

    assert params.short_period == 5
    assert params.long_period == 20
    assert params.lookback_days == 3
    assert params.max_stocks == 10
