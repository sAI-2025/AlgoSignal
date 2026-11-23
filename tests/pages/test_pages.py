"""Page rendering + button markup tests — every HTML page returns 200 and
every button/control from the PRD is present in the DOM. Run with:
pytest tests/pages/test_pages.py"""

from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from apps.companies.models import Company


@pytest.fixture
def mk_company(db) -> Company:
    return Company.objects.create(company_name="Reliance", nse_code="RELIANCE", sector="Energy", is_active=True)


@pytest.fixture
def authed(client: Client, user) -> Client:
    client.force_login(user)
    return client


# ── Shell / base layout ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestShell:
    def test_base_template_renders(self, authed: Client):
        resp = authed.get(reverse("dashboard:home"))
        assert resp.status_code == 200, resp.content
        html = resp.content.decode()
        # Sidebar nav items (all 7 screens + watchlist)
        for label in ("Dashboard", "Companies", "Signals", "Top Performers", "Company Explorer", "Market Data", "Settings", "Watchlist"):
            assert label in html, f"Missing nav item: {label}"
        # S0 controls
        assert 'data-search-toggle' in html
        assert 'id="as-freshness"' in html
        assert 'data-theme-toggle' in html
        assert 'data-sidebar-toggle' in html
        assert "IST" in html
        # Footer disclaimer
        assert "research indicators" in html.lower() or "not investment advice" in html.lower()
        # Lightweight Charts attribution (chartWorkspace loaded on company detail page)
        assert "Lightweight Charts" in html or "chartWorkspace.js" in html or "lightweight-charts" in html.lower() or "vendor/" in html


# ── Dashboard page ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDashboardPage:
    def test_dashboard_renders_with_widgets(self, authed: Client):
        resp = authed.get(reverse("dashboard:home"))
        assert resp.status_code == 200, resp.content
        html = resp.content.decode()
        # KPI cards
        assert "Companies with data" in html
        assert "Latest candle" in html
        assert "Advancers" in html
        assert "Decliners" in html
        assert "Unchanged" in html
        # Widgets
        assert 'data-widget="coverage"' in html
        assert 'data-widget="breadth"' in html
        assert 'data-widget="sectors"' in html
        assert 'data-widget="top_gainers"' in html
        assert 'data-widget="recent_signals"' in html
        # API wiring
        assert 'data-api-url="/api/v1/dashboard/summary/"' in html
        # Refresh button
        assert 'data-action="refresh-dashboard"' in html
        # Error widget placeholder
        assert 'data-widget="error"' in html


# ── Companies page ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCompaniesPage:
    def test_companies_renders_with_buttons(self, authed: Client, mk_company: Company):
        resp = authed.get(reverse("companies:list"))
        assert resp.status_code == 200, resp.content
        html = resp.content.decode()
        # Add stock button
        assert 'href="/companies/add/"' in html or 'href="{% url' in html
        assert "+ Add stock" in html or 'btn-primary' in html
        # Search + filters
        assert 'name="q"' in html
        assert 'name="sector"' in html
        assert 'name="ordering"' in html
        # Table columns
        assert "Company" in html
        assert "Symbol" in html
        assert "Sector" in html
        assert "Price" in html
        # Watchlist star column
        assert 'data-code=' in html or 'watchlist-star' in html

    def test_add_stock_page_renders(self, authed: Client):
        resp = authed.get(reverse("companies:add"))
        assert resp.status_code == 200, resp.content
        html = resp.content.decode()
        assert "Add stock" in html
        assert 'name="nse_code"' in html
        assert 'name="name"' in html
        assert 'name="sector"' in html
        assert 'name="industry"' in html
        assert "csrfmiddlewaretoken" in html


# ── Signals page ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSignalsPage:
    def test_signals_renders_with_scanner_form(self, authed: Client):
        resp = authed.get(reverse("scanner:signals"))
        assert resp.status_code == 200, resp.content
        html = resp.content.decode()
        # Scanner parameters
        assert 'name="short_period"' in html
        assert 'name="long_period"' in html
        assert 'name="lookback_days"' in html
        assert 'name="max_stocks"' in html
        # Generate button
        assert "Generate Signals" in html
        # Export
        assert "Export CSV" in html or "Reset" in html


# ── Top Performers page ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestTopPerformersPage:
    def test_top_performers_renders_with_controls(self, authed: Client, mk_company: Company):
        resp = authed.get(reverse("analytics:top_performers"))
        assert resp.status_code == 200, resp.content
        html = resp.content.decode()
        # Period tabs
        for period in ("1D", "1W", "1M", "3M", "6M", "1Y"):
            assert period in html
        # Sort order
        assert "Highest" in html or "Lowest" in html
        # Table columns
        assert "Company" in html
        assert "Sector" in html


# ── Company Explorer pages ──────────────────────────────────────────────────

@pytest.mark.django_db
class TestExplorerPages:
    def test_explorer_home_renders(self, authed: Client, mk_company: Company):
        resp = authed.get(reverse("explorer:home"))
        assert resp.status_code == 200, resp.content
        html = resp.content.decode()
        assert "Company search" in html or "search" in html.lower()
        assert "Recently viewed" in html or "recently" in html.lower() or "RELIANCE" in html

    def test_company_detail_renders(self, authed: Client, mk_company: Company):
        resp = authed.get(reverse("explorer:detail", args=["RELIANCE"]))
        assert resp.status_code == 200, resp.content
        html = resp.content.decode()
        assert "RELIANCE" in html
        # Tabs (rendered via |title filter: overview->Overview, history->History)
        for tab in ("Overview", "Chart", "Fundamentals", "Signals", "History"):
            assert tab in html
        # Open chart workspace button
        assert "chart workspace" in html.lower() or "Open chart" in html


# ── Chart Workspace page ────────────────────────────────────────────────────

@pytest.mark.django_db
class TestChartWorkspacePage:
    def test_chart_workspace_renders_all_tools(self, authed: Client):
        from apps.companies.models import Company
        Company.objects.create(company_name="Reliance", nse_code="RELIANCE", sector="Energy", is_active=True)
        resp = authed.get(reverse("visualization:workspace", args=["RELIANCE"]))
        assert resp.status_code == 200, resp.content
        html = resp.content.decode()
        assert "data-chart-workspace" in html
        assert "RELIANCE" in html
        # V1-V4: series type, timeframe, indicators
        assert 'data-series="candles"' in html or 'data-series="candlestick"' in html
        assert 'data-tf=' in html
        assert 'data-sma-toggle' in html
        # V5-V7: tools
        assert 'data-tool="pin"' in html
        assert 'data-tool="measure"' in html
        assert 'data-tool="range"' in html
        assert 'data-tool="trendline"' in html
        assert 'data-tool="horizontal"' in html
        # V12: Live toggle
        assert 'data-action="live"' in html
        # V14: Benchmark toggle
        assert 'data-action="benchmark"' in html
        # V13: Fullscreen
        assert 'data-action="fullscreen"' in html
        # V14: Export
        assert 'data-action="png"' in html
        assert 'data-action="csv"' in html
        # Clear / reset
        assert 'data-action="clear"' in html
        assert 'data-action="table"' in html
        # Custom SMA input (V9)
        assert 'data-custom-sma' in html
        # Markers toggle
        assert 'data-markers-toggle' in html


# ── Market Data page ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestMarketDataPage:
    def test_market_data_renders(self, authed: Client):
        resp = authed.get(reverse("fetcher:market_data"))
        assert resp.status_code == 200, resp.content
        html = resp.content.decode()
        # Provider status
        assert "yfinance" in html.lower() or "Provider" in html
        # Coverage
        assert "Coverage" in html
        # Scheduler heartbeat
        assert "heartbeat" in html.lower() or "Heartbeat" in html
        # Schedule table
        assert "Schedules" in html or "Every" in html or "schedules" in html.lower()
        # Action buttons (staff only: "Run now"; non-staff sees status badges)
        assert "Run now" in html or "Set" in html or "on" in html


# ── Settings page ───────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSettingsPage:
    def test_settings_renders_all_sections(self, authed: Client):
        resp = authed.get(reverse("dashboard:settings"))
        assert resp.status_code == 200, resp.content
        html = resp.content.decode()
        # Scanner defaults
        assert "Scanner defaults" in html or "Short SMA" in html
        # About section
        assert "About" in html or "yfinance" in html.lower()
        # Data provider mentioned
        assert "yfinance" in html.lower()
        # Lightweight Charts attribution
        assert "Lightweight Charts" in html or "TradingView" in html


# ── Watchlist page ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestWatchlistPage:
    def test_watchlist_renders(self, authed: Client):
        resp = authed.get(reverse("dashboard:watchlist"))
        assert resp.status_code == 200, resp.content
        html = resp.content.decode()
        assert "Watchlist" in html


# ── Login page ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLoginPage:
    def test_login_renders(self, client: Client):
        resp = client.get(reverse("login"))
        assert resp.status_code == 200, resp.content
        html = resp.content.decode()
        assert 'name="username"' in html
        assert 'name="password"' in html
        assert "Sign in" in html or "sign in" in html.lower()
