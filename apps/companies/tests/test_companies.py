from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.companies.models import Company
from apps.market_data.models import CompanyMetrics


@pytest.fixture
def user(db):
    return User.objects.create_user(username="companies", password="pw12345")


@pytest.mark.django_db
def test_list_companies_search_and_filter():
    from apps.companies.selectors import list_companies

    Company.objects.create(company_name="Reliance Industries", nse_code="RELIANCE", sector="Energy")
    Company.objects.create(company_name="Tata Motors", nse_code="TATAMOTORS", sector="Auto")

    assert [row["nse_code"] for row in list_companies(query="reliance")] == ["RELIANCE"]
    assert [row["nse_code"] for row in list_companies(sector="Auto")] == ["TATAMOTORS"]


@pytest.mark.django_db
def test_list_companies_enriches_metrics():
    from apps.companies.selectors import list_companies

    company = Company.objects.create(company_name="Reliance", nse_code="RELIANCE")
    CompanyMetrics.objects.create(
        company=company,
        current_price=2945,
        trailing_pe=25,
        market_cap=2400000,
        fetched_at="2026-11-20T10:00:00Z",
    )

    rows = list_companies()
    row = next(r for r in rows if r["nse_code"] == "RELIANCE")
    assert row["price"] == 2945.0
    assert row["trailing_pe"] == 25.0


@pytest.mark.django_db
def test_companies_page_renders(client, user):
    Company.objects.create(company_name="Reliance Industries", nse_code="RELIANCE", sector="Energy")
    client.force_login(user)
    response = client.get(reverse("companies:list"), {"q": "reliance"})
    assert response.status_code == 200
    assert b"Reliance Industries" in response.content


@pytest.mark.django_db
def test_refresh_metrics_returns_updated(client, user):
    company = Company.objects.create(
        company_name="Reliance Industries", nse_code="RELIANCE", sector="Energy"
    )
    CompanyMetrics.objects.create(
        company=company,
        current_price=2945,
        trailing_pe=25,
        market_cap=2400000,
        fetched_at="2026-11-20T10:00:00Z",
    )
    client.force_login(user)

    with patch(
        "apps.companies.api.views.fetch_and_store_metrics"
    ) as mock_fetch:
        mock_fetch.return_value = None
        response = client.post(reverse("companies_api:company_refresh_metrics", args=["RELIANCE"]))

    assert response.status_code == 200
    data = response.json()
    assert data["current_price"] == 2945.0
    assert data["trailing_pe"] == 25.0


@pytest.mark.django_db
def test_refresh_metrics_404_unknown(client, user):
    client.force_login(user)
    response = client.post(
        reverse("companies_api:company_refresh_metrics", args=["NOPE"])
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_refresh_metrics_502_provider_error(client, user):
    Company.objects.create(company_name="Reliance", nse_code="RELIANCE")
    client.force_login(user)

    with patch(
        "apps.companies.api.views.fetch_and_store_metrics"
    ) as mock_fetch:
        mock_fetch.side_effect = Exception("provider down")
        response = client.post(reverse("companies_api:company_refresh_metrics", args=["RELIANCE"]))

    assert response.status_code == 502
    data = response.json()
    assert data["error"]["code"] == "REFRESH_FAILED"
