from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from apps.companies.models import Company
from apps.fetcher.services.jobs import constituents, daily_candles
from apps.fetcher.services.jobs.base import JobContext

IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 11, 20, 16, 30, tzinfo=IST)


def _ctx(**kwargs) -> JobContext:
    defaults = {"now": NOW, "universe_index": "NIFTY100"}
    defaults.update(kwargs)
    return JobContext(**defaults)


@pytest.mark.django_db
def test_daily_candles_empty_universe() -> None:
    result = daily_candles.run(_ctx())

    assert result.total_items == 0
    assert result.success_items == 0
    assert result.rows_written == 0


@pytest.mark.django_db
def test_daily_candles_counts_instruments(monkeypatch) -> None:
    company = Company.objects.create(company_name="Infosys", nse_code="INFY")
    from apps.market_data.models import Instrument

    Instrument.objects.create(
        company=company,
        exchange=Instrument.Exchange.NSE,
        tradingsymbol="INFY",
        provider_symbol="INFY.NS",
    )

    class _Saved:
        written_rows = 5
        skipped_incomplete_rows = 0

    monkeypatch.setattr(
        "apps.fetcher.services.jobs.daily_candles.backfill_company_history",
        lambda *a, **k: _Saved(),
    )

    result = daily_candles.run(_ctx())

    assert result.total_items == 1
    assert result.success_items == 1
    assert result.rows_written == 5


@pytest.mark.django_db
def test_constituents_job_import_error(monkeypatch) -> None:
    from apps.companies.services.importer import ImporterError

    def _boom(index_code):
        raise ImporterError("no urls configured")

    monkeypatch.setattr("apps.fetcher.services.jobs.constituents.run_constituent_import", _boom)

    result = constituents.run(_ctx())

    assert result.failed_items == 1
    assert result.errors[0]["error_code"] == "IMPORT_FAILED"
