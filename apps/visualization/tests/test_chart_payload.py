from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.companies.models import Company
from apps.market_data.models import HistoricalPrice
from apps.signals.models import TradingSignal
from apps.visualization.services.chart_payload import (
    build_chart_payload,
    parse_sma_periods,
)
from apps.visualization.services.markers import signals_to_markers
from apps.visualization.services.timeframes import resolve_range


def _company_with_candles(
    code: str = "RELIANCE", days: int = 40, *, start: date = date(2026, 1, 1)
) -> Company:
    company = Company.objects.create(company_name=code, nse_code=code)
    for offset in range(days):
        close = 100.0 + offset
        HistoricalPrice.objects.create(
            company=company,
            candle_date=start + timedelta(days=offset),
            open=close - 1,
            high=close + 2,
            low=close - 2,
            close=close,
            adj_close=close,
            volume=1000 + offset,
        )
    return company


def test_resolve_range_known_and_max() -> None:
    end = date(2026, 6, 1)
    start, out_end = resolve_range("1Y", end)
    assert out_end == end
    assert start == date(2025, 6, 1)

    start_max, _ = resolve_range("MAX", end)
    assert start_max is None


def test_resolve_range_unknown_raises() -> None:
    with pytest.raises(ValueError):
        resolve_range("7Y", date(2026, 1, 1))


def test_parse_sma_periods() -> None:
    assert parse_sma_periods(None) == [7, 30]
    assert parse_sma_periods("7,30") == [7, 30]
    assert parse_sma_periods(" 5 , 5 , 20 ") == [5, 20]
    with pytest.raises(ValueError):
        parse_sma_periods("7,abc")
    with pytest.raises(ValueError):
        parse_sma_periods("0")


@pytest.mark.django_db
def test_build_chart_payload_shape() -> None:
    company = _company_with_candles()

    payload = build_chart_payload(
        company,
        tf="3M",
        indicator_specs=[("sma", {"window": 7}), ("sma", {"window": 30})],
        markers=True,
    )

    assert payload["symbol"] == "RELIANCE"
    assert payload["tf"] == "3M"
    assert payload["basis"] == "unadjusted"
    assert len(payload["candles"]) == 40
    first = payload["candles"][0]
    assert set(first) == {"time", "open", "high", "low", "close", "volume"}
    # SMA(7) is NaN for the first 6 bars → 34 points remain.
    assert len(payload["indicators"]["sma_7"]) == 40 - 6
    assert len(payload["indicators"]["sma_30"]) == 40 - 29
    meta = payload["meta"]
    assert meta["count"] == 40
    assert meta["complete_only"] is True


@pytest.mark.django_db
def test_build_chart_payload_markers_toggle() -> None:
    company = _company_with_candles()
    TradingSignal.objects.create(
        company=company,
        signal_type=TradingSignal.SignalType.BULLISH,
        short_period=7,
        long_period=30,
        short_sma=100,
        long_sma=99,
        close_price=101,
        crossover_date=date(2026, 1, 20),
    )

    with_markers = build_chart_payload(company, tf="MAX", markers=True)
    without = build_chart_payload(company, tf="MAX", markers=False)

    assert len(with_markers["markers"]) == 1
    marker = with_markers["markers"][0]
    assert marker["type"] == "BULLISH"
    assert marker["params"] == [7, 30]
    assert without["markers"] == []


@pytest.mark.django_db
def test_build_chart_payload_empty_company() -> None:
    company = Company.objects.create(company_name="Empty", nse_code="EMPTY")

    payload = build_chart_payload(company, tf="1Y")

    assert payload["candles"] == []
    assert payload["meta"]["count"] == 0
    assert payload["meta"]["last_candle_date"] is None


@pytest.mark.django_db
def test_signals_to_markers_range_filter() -> None:
    company = _company_with_candles()
    TradingSignal.objects.create(
        company=company,
        signal_type=TradingSignal.SignalType.BEARISH,
        short_period=7,
        long_period=30,
        short_sma=100,
        long_sma=99,
        close_price=101,
        crossover_date=date(2026, 1, 10),
    )
    TradingSignal.objects.create(
        company=company,
        signal_type=TradingSignal.SignalType.BULLISH,
        short_period=7,
        long_period=30,
        short_sma=100,
        long_sma=99,
        close_price=101,
        crossover_date=date(2026, 2, 10),
    )

    markers = signals_to_markers(company.id, start=date(2026, 2, 1), end=date(2026, 2, 28))

    assert [m["type"] for m in markers] == ["BULLISH"]
