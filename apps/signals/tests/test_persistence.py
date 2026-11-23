from __future__ import annotations

import pandas as pd
import pytest

from apps.companies.models import Company
from apps.signals.models import TradingSignal
from apps.signals.services.persistence import save


def _rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "candle_date": [pd.Timestamp("2026-11-08").date()],
            "signal_type": ["BULLISH"],
            "short_sma": [11.5],
            "long_sma": [11.0],
            "close": [11.0],
        }
    )


@pytest.mark.django_db
def test_save_inserts_then_skips_duplicates() -> None:
    company = Company.objects.create(company_name="Infosys", nse_code="INFY")

    first = save(company, strategy="SMA_CROSS", short=2, long=3, rows=_rows())
    second = save(company, strategy="SMA_CROSS", short=2, long=3, rows=_rows())

    assert first.inserted == 1
    assert first.skipped == 0
    assert second.inserted == 0
    assert second.skipped == 1
    assert TradingSignal.objects.filter(company=company).count() == 1


@pytest.mark.django_db
def test_save_empty_rows() -> None:
    company = Company.objects.create(company_name="TCS", nse_code="TCS")

    result = save(company, strategy="SMA_CROSS", short=7, long=30, rows=pd.DataFrame())

    assert result.inserted == 0
    assert result.skipped == 0


@pytest.mark.django_db
def test_different_periods_are_distinct_signals() -> None:
    company = Company.objects.create(company_name="ITC", nse_code="ITC")

    save(company, strategy="SMA_CROSS", short=2, long=3, rows=_rows())
    save(company, strategy="SMA_CROSS", short=5, long=10, rows=_rows())

    assert TradingSignal.objects.filter(company=company).count() == 2
