from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from apps.companies.models import Company
from apps.market_data.models import CompanyMetrics, Instrument
from apps.market_data.services.fundamentals import (
    fetch_and_store_metrics,
    fetch_metrics_for_universe,
)
from apps.market_data.services.providers.base import ProviderNoData

FIXTURE = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "yf_info_reliance.json"


def _load_info() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class _StubProvider:
    name = "yfinance"

    def __init__(self, info: dict | None = None, fail_symbols: set[str] | None = None) -> None:
        self._info = info if info is not None else _load_info()
        self._fail = fail_symbols or set()

    def get_company_info(self, symbol: str) -> dict:
        if symbol in self._fail:
            raise ProviderNoData(f"{symbol}: no data")
        return self._info


@pytest.mark.django_db
def test_fetch_and_store_upserts_single_snapshot() -> None:
    company = Company.objects.create(company_name="Reliance", nse_code="RELIANCE")
    provider = _StubProvider()
    now = datetime(2026, 11, 22, 16, 30, tzinfo=ZoneInfo("Asia/Kolkata"))

    first = fetch_and_store_metrics(company, provider=provider, now=now)
    second = fetch_and_store_metrics(company, provider=provider, now=now)

    assert first.updated is True
    assert second.updated is True
    assert CompanyMetrics.objects.filter(company=company).count() == 1
    metrics = CompanyMetrics.objects.get(company=company)
    assert metrics.current_price is not None
    assert metrics.dividend_yield is not None


@pytest.mark.django_db
def test_fetch_metrics_for_universe_records_failures_and_continues() -> None:
    good = Company.objects.create(company_name="Reliance", nse_code="RELIANCE")
    bad = Company.objects.create(company_name="BadCo", nse_code="BADCO")
    Instrument.objects.create(
        company=bad,
        exchange=Instrument.Exchange.NSE,
        tradingsymbol="BADCO",
        provider_symbol="BADCO.NS",
    )
    provider = _StubProvider(fail_symbols={"BADCO.NS"})

    result = fetch_metrics_for_universe(
        provider=provider,
        sleep=lambda _s: None,
        now=datetime(2026, 11, 22, 16, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
    )

    assert result.total == 2
    assert result.success == 1
    assert result.failed == 1
    assert len(result.errors) == 1
    assert result.errors[0]["symbol"] == "BADCO"
    assert CompanyMetrics.objects.filter(company=good).exists()
    assert not CompanyMetrics.objects.filter(company=bad).exists()
