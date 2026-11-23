from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from apps.analytics.services.market_overview import advancers_decliners
from apps.analytics.services.performance import compute_returns, top_performers
from apps.companies.models import Company
from apps.market_data.models import HistoricalPrice

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 1, 31, 16, 0, tzinfo=IST)


def _company(
    code: str,
    closes: list[float],
    *,
    start: date = date(2026, 1, 1),
    sector: str | None = None,
    adjusted: bool = True,
) -> Company:
    company = Company.objects.create(company_name=code, nse_code=code, sector=sector)
    for offset, close in enumerate(closes):
        HistoricalPrice.objects.create(
            company=company,
            candle_date=start + timedelta(days=offset),
            open=close,
            high=close,
            low=close,
            close=close,
            adj_close=close if adjusted else None,
            volume=1000,
        )
    return company


def _rising_series(days: int = 30) -> list[float]:
    return [100.0 + i for i in range(days)]


@pytest.mark.django_db
def test_return_1d() -> None:
    _company("AAA", _rising_series())

    result = compute_returns("1D", now=AS_OF)

    row = next(row for row in result.rows if row.nse_code == "AAA")
    assert row.return_pct == pytest.approx((129 - 128) / 128 * 100)
    assert row.basis == "adjusted"


@pytest.mark.django_db
def test_return_1w() -> None:
    _company("AAA", _rising_series())

    result = compute_returns("1W", now=AS_OF)

    row = next(row for row in result.rows if row.nse_code == "AAA")
    # latest 2026-01-30 close=129; 7 days back 2026-01-23 close=122
    assert row.return_pct == pytest.approx((129 - 122) / 122 * 100)


@pytest.mark.django_db
def test_unadjusted_basis_when_no_adj_close() -> None:
    _company("BBB", [100.0, 110.0], adjusted=False)

    result = compute_returns("1D", now=datetime(2026, 1, 3, 16, 0, tzinfo=IST))

    row = next(row for row in result.rows if row.nse_code == "BBB")
    assert row.basis == "unadjusted"
    assert row.return_pct == pytest.approx(10.0)


@pytest.mark.django_db
def test_insufficient_history_excluded() -> None:
    _company("CCC", [100.0, 101.0, 102.0])

    result = compute_returns("1Y", now=datetime(2026, 1, 4, 16, 0, tzinfo=IST))

    assert result.rows == []
    assert any(
        ex.nse_code == "CCC" and ex.reason == "insufficient history" for ex in result.excluded
    )


@pytest.mark.django_db
def test_stale_company_excluded() -> None:
    _company("DDD", _rising_series(), start=date(2026, 1, 1))

    # as_of far after the last candle (2026-01-30) → stale
    result = compute_returns("1D", now=datetime(2026, 2, 15, 16, 0, tzinfo=IST))

    assert any(ex.nse_code == "DDD" and ex.reason.startswith("stale") for ex in result.excluded)


@pytest.mark.django_db
def test_top_performers_order_and_limit() -> None:
    _company("AAA", _rising_series())  # +0.78% 1D
    _company("BBB", [100.0, 120.0], start=date(2026, 1, 29))  # +20% 1D
    _company("CCC", [100.0, 90.0], start=date(2026, 1, 29))  # -10% 1D

    result = top_performers("1D", limit=2, order="desc", now=AS_OF)

    assert [row.nse_code for row in result.rows] == ["BBB", "AAA"]


@pytest.mark.django_db
def test_sector_filter() -> None:
    _company("AAA", [100.0, 110.0], start=date(2026, 1, 29), sector="IT")
    _company("BBB", [100.0, 120.0], start=date(2026, 1, 29), sector="Auto")

    result = top_performers("1D", sector="IT", now=AS_OF)

    assert [row.nse_code for row in result.rows] == ["AAA"]


@pytest.mark.django_db
def test_advancers_decliners() -> None:
    _company("UP", [100.0, 110.0], start=date(2026, 1, 29))
    _company("DOWN", [100.0, 90.0], start=date(2026, 1, 29))
    _company("FLAT", [100.0, 100.0], start=date(2026, 1, 29))

    counts = advancers_decliners()

    assert counts["advancers"] == 1
    assert counts["decliners"] == 1
    assert counts["unchanged"] == 1


@pytest.mark.django_db
def test_missing_adj_close_falls_back_to_unadjusted() -> None:
    company = _company("AAA", _rising_series(), start=date(2026, 1, 20))
    # Drop adjusted close only on the latest candle; earlier candles keep it.
    latest = HistoricalPrice.objects.filter(company=company).order_by("-candle_date").first()
    latest.adj_close = None
    latest.save(update_fields=["adj_close"])

    result = compute_returns("1D", now=AS_OF)

    row = next(row for row in result.rows if row.nse_code == "AAA")
    assert row.basis == "unadjusted"
    assert row.return_pct == row.return_pct  # not NaN


@pytest.mark.django_db
def test_industry_filter() -> None:
    tech = Company.objects.create(company_name="Tech Co", nse_code="TECH", industry="Technology")
    auto = Company.objects.create(company_name="Auto Co", nse_code="AUTO", industry="Automobile")
    for company in (tech, auto):
        for offset, close in enumerate([100.0, 110.0]):
            HistoricalPrice.objects.create(
                company=company,
                candle_date=date(2026, 1, 29) + timedelta(days=offset),
                open=close,
                high=close,
                low=close,
                close=close,
                adj_close=close,
                volume=1000,
            )

    result = top_performers("1D", industry="Technology", now=AS_OF)

    assert [row.nse_code for row in result.rows] == ["TECH"]
