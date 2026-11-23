"""Shared pytest fixtures for the AlgoSignal test suite.

Provides authenticated clients, seeded companies/candles/metrics/signals,
and helper assertions used across all API, page, and integration tests.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.core.cache import cache

from apps.companies.models import Company
from apps.market_data.models import CompanyMetrics, HistoricalPrice, Instrument
from apps.scanner.models import ScannerSetting
from apps.signals.models import TradingSignal


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear cache between tests to prevent throttling state leakage."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client() -> Client:
    """Unauthenticated Django test client."""
    return Client()


@pytest.fixture
def user(db) -> User:
    """Standard non-staff user (tester credentials)."""
    return User.objects.create_user(username="tester", password="1234")


@pytest.fixture
def staff_user(db) -> User:
    """Staff user for admin/trigger endpoints."""
    return User.objects.create_user(username="admin", password="1234", is_staff=True, is_superuser=True)


@pytest.fixture
def authed_client(client: Client, user: User) -> Client:
    """Authenticated client as standard user."""
    client.force_login(user)
    return client


@pytest.fixture
def staff_client(client: Client, staff_user: User) -> Client:
    """Authenticated client as staff user."""
    client.force_login(staff_user)
    return client


@pytest.fixture
def seed_company(db) -> Company:
    """Create a single active company."""
    return Company.objects.create(
        company_name="Reliance Industries Ltd",
        nse_code="RELIANCE",
        sector="Energy",
        industry="Oil & Gas",
        is_active=True,
    )


@pytest.fixture
def seed_companies(db) -> list[Company]:
    """Create 5 companies across 3 sectors."""
    codes = [
        ("RELIANCE", "Reliance Industries Ltd", "Energy", "Oil & Gas"),
        ("TCS", "Tata Consultancy Services", "IT", "Software"),
        ("INFY", "Infosys Ltd", "IT", "Software"),
        ("HDFCBANK", "HDFC Bank Ltd", "Financial Services", "Banking"),
        ("ITC", "ITC Ltd", "FMCG", "Cigarettes"),
    ]
    return [
        Company.objects.create(company_name=name, nse_code=code, sector=sector, industry=industry, is_active=True)
        for code, name, sector, industry in codes
    ]


@pytest.fixture
def seed_candles(db, seed_company: Company) -> None:
    """Seed 40 daily candles for RELIANCE (ascending closes)."""
    start = date(2026, 1, 1)
    for offset in range(40):
        close = 100.0 + offset
        HistoricalPrice.objects.create(
            company=seed_company,
            candle_date=start + timedelta(days=offset),
            open=close - 1,
            high=close + 2,
            low=close - 2,
            close=close,
            adj_close=close,
            volume=1000 + offset,
        )


@pytest.fixture
def seed_metrics(db, seed_company: Company) -> CompanyMetrics:
    """Seed fundamentals snapshot for RELIANCE."""
    return CompanyMetrics.objects.create(
        company=seed_company,
        current_price=139.0,
        previous_close=138.0,
        open_price=138.5,
        day_high=140.0,
        day_low=137.5,
        fifty_two_week_high=150.0,
        fifty_two_week_low=120.0,
        volume=5000000,
        average_volume=4500000,
        market_cap=240000000000,
        trailing_pe=25.0,
        forward_pe=22.0,
        trailing_eps=5.56,
        book_value=50.0,
        price_to_book=2.78,
        dividend_yield=0.5,
        return_on_equity=15.0,
        return_on_assets=8.0,
        profit_margins=12.0,
        debt_to_equity=0.4,
        total_revenue=1000000000000,
        free_cashflow=80000000000,
        net_income=120000000000,
        currency="INR",
        source="yfinance",
    )


@pytest.fixture
def seed_instrument(db, seed_company: Company) -> Instrument:
    """Seed an instrument mapping for RELIANCE."""
    return Instrument.objects.create(
        company=seed_company,
        exchange=Instrument.Exchange.NSE,
        tradingsymbol="RELIANCE",
        provider_symbol="RELIANCE.NS",
        instrument_type="EQ",
    )


@pytest.fixture
def seed_signal(db, seed_company: Company) -> TradingSignal:
    """Seed a stored bullish crossover signal."""
    return TradingSignal.objects.create(
        company=seed_company,
        strategy="SMA_CROSS",
        signal_type="BULLISH",
        short_period=7,
        long_period=30,
        short_sma=135.0,
        long_sma=134.0,
        close_price=139.0,
        crossover_date=date(2026, 11, 20),
    )


@pytest.fixture
def seed_scanner_setting(db) -> ScannerSetting:
    """Seed default scanner settings."""
    return ScannerSetting.load()


def assert_api_error(response, expected_status: int, expected_code: str | None = None) -> dict:
    """Assert a DRF error-envelope response and return the parsed body."""
    assert response.status_code == expected_status
    body = response.json()
    assert "error" in body, f"Expected error envelope, got: {body}"
    if expected_code is not None:
        assert body["error"]["code"] == expected_code, f"Expected code {expected_code}, got: {body}"
    return body


def assert_pagination_shape(body: dict) -> None:
    """Assert the standard paginated response shape."""
    assert "results" in body
    assert "pagination" in body
    pg = body["pagination"]
    for key in ("page", "page_size", "total", "num_pages", "has_next", "has_previous"):
        assert key in pg, f"Missing pagination key: {key}"


def require_auth(client: Client, method: str, url: str, **kwargs) -> None:
    """Assert an endpoint redirects to login when unauthenticated."""
    resp = getattr(client, method.lower())(url, **kwargs)
    assert resp.status_code == 302, f"Expected 302 redirect for unauthenticated {method} {url}, got {resp.status_code}"
    assert "login" in resp["Location"].lower()

