from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.companies.models import Company
from apps.market_data.models import CompanyMetrics, HistoricalPrice
from apps.signals.models import TradingSignal


@pytest.fixture
def user(db):
    return User.objects.create_user(username="explorer", password="pw12345")


def _seed_candles(company: Company, days: int = 40) -> None:
    start = date(2026, 1, 1)
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


@pytest.mark.django_db
def test_search_companies_by_name_and_code():
    Company.objects.create(company_name="Reliance Industries", nse_code="RELIANCE")
    Company.objects.create(company_name="Tata Motors", nse_code="TATAMOTORS")

    from apps.explorer.services.search import search_companies

    by_name = search_companies("reliance")
    by_code = search_companies("TATA")
    assert [row["nse_code"] for row in by_name] == ["RELIANCE"]
    assert [row["nse_code"] for row in by_code] == ["TATAMOTORS"]


@pytest.mark.django_db
def test_search_api_returns_json(client, user):
    Company.objects.create(company_name="Reliance Industries", nse_code="RELIANCE")
    client.force_login(user)
    response = client.get(reverse("explorer:search_api"), {"q": "reliance"})
    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["nse_code"] == "RELIANCE"


@pytest.mark.django_db
def test_explorer_home_renders(client, user):
    client.force_login(user)
    response = client.get(reverse("explorer:home"))
    assert response.status_code == 200
    assert b"Company Explorer" in response.content


@pytest.mark.django_db
def test_company_detail_overview(client, user):
    company = Company.objects.create(
        company_name="Reliance Industries", nse_code="RELIANCE", sector="Energy"
    )
    _seed_candles(company)
    CompanyMetrics.objects.create(
        company=company,
        current_price=2945,
        trailing_pe=25,
        market_cap=2400000,
        fetched_at="2026-11-20T10:00:00Z",
    )
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

    client.force_login(user)
    response = client.get(reverse("explorer:detail", args=["RELIANCE"]), {"tab": "overview"})
    assert response.status_code == 200
    content = response.content
    assert b"RELIANCE" in content
    assert b"BULLISH" in content


@pytest.mark.django_db
def test_company_detail_history_tab_paginates(client, user):
    company = Company.objects.create(company_name="Reliance Industries", nse_code="RELIANCE")
    _seed_candles(company, days=60)
    client.force_login(user)
    response = client.get(reverse("explorer:detail", args=["RELIANCE"]), {"tab": "history"})
    assert response.status_code == 200
    assert response.context["pagination"].paginator.count == 60
    assert len(response.context["price_history"]) == 25


@pytest.mark.django_db
def test_company_detail_unknown_404(client, user):
    client.force_login(user)
    response = client.get(reverse("explorer:detail", args=["NOPE"]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_company_detail_shows_not_available_for_null_metrics(client, user):
    company = Company.objects.create(
        company_name="NoMetrics", nse_code="NOMETRICS", sector="Energy"
    )
    _seed_candles(company)
    client.force_login(user)
    response = client.get(reverse("explorer:detail", args=["NOMETRICS"]), {"tab": "overview"})
    assert response.status_code == 200
    content = response.content.decode()
    assert "Not available" in content
    # Metric values should not use bare em-dash; check the metric card area specifically
    assert "as-metric-value--empty" in content


@pytest.mark.django_db
def test_company_returns_strip_service():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    company = Company.objects.create(company_name="Reliance Industries", nse_code="RELIANCE")
    _seed_candles(company)  # last candle 2026-02-09

    from apps.explorer.services.company_view import build_company_detail

    now = datetime(2026, 2, 10, 16, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    detail = build_company_detail(company, now=now)
    assert [item["period"] for item in detail.returns_strip] == [
        "1D",
        "1W",
        "1M",
        "3M",
        "6M",
        "1Y",
    ]
    assert detail.returns_strip[0]["return_pct"] is not None
