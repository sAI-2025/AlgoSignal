from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from apps.companies.models import Company
from apps.market_data.models import HistoricalPrice, Instrument
from apps.market_data.services.historical_data import (
    _resolve_start_date,
    store_historical_prices,
)


@pytest.mark.django_db
def test_store_historical_prices_upserts_without_duplicates() -> None:
    company = Company.objects.create(company_name="Infosys", nse_code="INFY")

    frame = pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "adj_close": [101.0, 102.0],
            "volume": [1000, 1200],
        },
        index=pd.to_datetime(["2026-11-20", "2026-11-21"]),
    )

    first = store_historical_prices(company.id, frame)
    second = store_historical_prices(company.id, frame)

    assert first.written_rows == 2
    assert second.written_rows == 2
    assert HistoricalPrice.objects.filter(company=company).count() == 2


@pytest.mark.django_db
def test_store_historical_prices_drops_incomplete_candle(monkeypatch: pytest.MonkeyPatch) -> None:
    company = Company.objects.create(company_name="TCS", nse_code="TCS")

    frame = pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "adj_close": [101.0, 102.0],
            "volume": [1000, 1200],
        },
        index=pd.to_datetime(["2026-11-22", "2026-11-23"]),
    )

    from zoneinfo import ZoneInfo

    monkeypatch.setattr(
        "apps.market_data.services.historical_data.timezone.now",
        lambda: datetime(2026, 11, 23, 15, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
    )

    result = store_historical_prices(company.id, frame)

    assert result.written_rows == 1
    assert result.skipped_incomplete_rows == 1
    assert HistoricalPrice.objects.filter(company=company, candle_date="2026-11-22").exists()
    assert not HistoricalPrice.objects.filter(company=company, candle_date="2026-11-23").exists()


@pytest.mark.django_db
def test_resolve_start_date_uses_listing_date() -> None:
    company = Company.objects.create(company_name="NewCo", nse_code="NEWCO")
    instrument = Instrument.objects.create(
        company=company,
        exchange=Instrument.Exchange.NSE,
        tradingsymbol="NEWCO",
        provider_symbol="NEWCO.NS",
    )
    listing_date = date(2026, 1, 15)
    start = _resolve_start_date(instrument, years=1, listing_date=listing_date)
    assert start == listing_date


@pytest.mark.django_db
def test_resolve_start_date_falls_back_to_earliest_candle() -> None:
    company = Company.objects.create(company_name="OldCo", nse_code="OLDCO")
    instrument = Instrument.objects.create(
        company=company,
        exchange=Instrument.Exchange.NSE,
        tradingsymbol="OLDCO",
        provider_symbol="OLDCO.NS",
    )
    HistoricalPrice.objects.create(
        company=company,
        candle_date=date(2026, 2, 1),
        open=100, high=101, low=99, close=100, volume=1000,
    )
    start = _resolve_start_date(instrument, years=1)
    assert start == date(2026, 2, 2)


@pytest.mark.django_db
def test_resolve_start_date_falls_back_to_today_minus_years() -> None:
    from django.utils import timezone

    company = Company.objects.create(company_name="NoDataCo", nse_code="NODATA")
    instrument = Instrument.objects.create(
        company=company,
        exchange=Instrument.Exchange.NSE,
        tradingsymbol="NODATA",
        provider_symbol="NODATA.NS",
    )
    start = _resolve_start_date(instrument, years=1)
    expected = timezone.localdate() - timedelta(days=365)
    assert start == expected
