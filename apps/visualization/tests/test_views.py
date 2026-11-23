from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.companies.models import Company
from apps.market_data.models import HistoricalPrice


@pytest.fixture
def user(db):
    return User.objects.create_user(username="chartuser", password="pw12345")


def _seed(company: Company, days: int = 40) -> None:
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
def test_chart_payload_api(client, user):
    Company.objects.create(company_name="Reliance", nse_code="RELIANCE")
    company = Company.objects.get(nse_code="RELIANCE")
    _seed(company)

    client.force_login(user)
    url = reverse("visualization:chart_payload", args=["RELIANCE"])
    response = client.get(url, {"tf": "3M", "sma": "7,30", "markers": "1"})

    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "RELIANCE"
    assert len(data["candles"]) == 40
    assert "sma_7" in data["indicators"]


@pytest.mark.django_db
def test_chart_payload_api_requires_auth(client):
    Company.objects.create(company_name="Reliance", nse_code="RELIANCE")
    url = reverse("visualization:chart_payload", args=["RELIANCE"])
    response = client.get(url)
    assert response.status_code == 302
    assert "/login" in response["Location"] or "login" in response["Location"]


@pytest.mark.django_db
def test_chart_payload_api_unknown_symbol(client, user):
    client.force_login(user)
    url = reverse("visualization:chart_payload", args=["NOPE"])
    response = client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_chart_payload_api_bad_sma(client, user):
    Company.objects.create(company_name="Reliance", nse_code="RELIANCE")
    client.force_login(user)
    url = reverse("visualization:chart_payload", args=["RELIANCE"])
    response = client.get(url, {"sma": "7,abc"})
    assert response.status_code == 422


@pytest.mark.django_db
def test_chart_payload_api_before_anchor(client, user):
    Company.objects.create(company_name="Reliance", nse_code="RELIANCE")
    company = Company.objects.get(nse_code="RELIANCE")
    _seed(company)

    client.force_login(user)
    url = reverse("visualization:chart_payload", args=["RELIANCE"])

    # Anchored earlier than the last candle → range ends at the anchor, not the latest.
    response = client.get(url, {"tf": "MAX", "before": "2026-01-10"})
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["to"] == "2026-01-10"
    assert all(c["time"] <= "2026-01-10" for c in data["candles"])


@pytest.mark.django_db
def test_chart_payload_api_bad_before(client, user):
    Company.objects.create(company_name="Reliance", nse_code="RELIANCE")
    client.force_login(user)
    url = reverse("visualization:chart_payload", args=["RELIANCE"])
    response = client.get(url, {"before": "not-a-date"})
    assert response.status_code == 422


@pytest.mark.django_db
def test_chart_workspace_page_renders(client, user):
    Company.objects.create(company_name="Reliance", nse_code="RELIANCE")
    client.force_login(user)
    url = reverse("visualization:workspace", args=["RELIANCE"])
    response = client.get(url)
    assert response.status_code == 200
    assert b"data-chart-workspace" in response.content
    assert b"RELIANCE" in response.content
    # Chart tools (V5–V9, V18) markup is present in the shell.
    for hook in (b'data-tool="pin"', b'data-tool="measure"', b'data-tool="range"'):
        assert hook in response.content
    assert b"data-custom-sma" in response.content
    assert b"data-pins-list" in response.content
    assert b'data-action="clear"' in response.content
    # S0 shell: theme toggle, sidebar toggle, market-status pill, user menu.
    assert b"data-theme-toggle" in response.content
    assert b"data-sidebar-toggle" in response.content
    assert b"IST" in response.content
    assert b'aria-labelledby="userMenu"' in response.content
