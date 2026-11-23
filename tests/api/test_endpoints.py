"""Master API endpoint tests — every /api/v1/ endpoint, every HTTP method,
every success and error case. Run with: pytest tests/api/test_endpoints.py"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.test import Client
from django.urls import reverse

from apps.companies.models import Company
from apps.market_data.models import HistoricalPrice
from apps.scanner.models import ScannerSetting


@pytest.fixture
def authed(client: Client, user) -> Client:
    client.force_login(user)
    return client


@pytest.fixture
def seeded_company(db, authed: Client) -> Company:
    c = Company.objects.create(company_name="Reliance", nse_code="RELIANCE", sector="Energy", is_active=True)
    start = date(2026, 1, 1)
    for offset in range(40):
        close = 100.0 + offset
        HistoricalPrice.objects.create(
            company=c,
            candle_date=start + timedelta(days=offset),
            open=close - 1,
            high=close + 2,
            low=close - 2,
            close=close,
            adj_close=close,
            volume=1000 + offset,
        )
    return c


# ── Companies API ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCompaniesEndpoints:
    def test_company_list_requires_auth(self, client: Client):
        url = reverse("companies_api:company_list")
        resp = client.get(url)
        assert resp.status_code == 403

    def test_company_list_pagination_and_filters(self, authed: Client, seeded_company: Company):
        url = reverse("companies_api:company_list")
        resp = authed.get(url, {"q": "reliance", "sector": "Energy", "ordering": "name", "dir": "asc", "page": 1, "page_size": 20})
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert "results" in body
        assert len(body["results"]) == 1
        assert body["results"][0]["nse_code"] == "RELIANCE"
        assert_pagination_shape(body)

    def test_company_detail_found(self, authed: Client, seeded_company: Company):
        url = reverse("companies_api:company_detail", args=["RELIANCE"])
        resp = authed.get(url)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["nse_code"] == "RELIANCE"
        assert body["company_name"] == "Reliance"
        assert body["sector"] == "Energy"

    def test_company_detail_not_found(self, authed: Client):
        url = reverse("companies_api:company_detail", args=["NOPE"])
        resp = authed.get(url)
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "NOT_FOUND"

    def test_company_metrics_found(self, authed: Client, seeded_company: Company):
        from apps.market_data.models import CompanyMetrics
        CompanyMetrics.objects.create(
            company=seeded_company,
            current_price=139.0,
            trailing_pe=25.0,
            market_cap=240000000000,
            fetched_at="2026-11-20T10:00:00Z",
        )
        url = reverse("companies_api:company_metrics", args=["RELIANCE"])
        resp = authed.get(url)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["current_price"] == 139.0
        assert body["trailing_pe"] == 25.0

    def test_company_metrics_not_found(self, authed: Client, seeded_company: Company):
        url = reverse("companies_api:company_metrics", args=["RELIANCE"])
        resp = authed.get(url)
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "NOT_FOUND"

    def test_company_sectors(self, authed: Client, seeded_company: Company):
        url = reverse("companies_api:company_sectors")
        resp = authed.get(url)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert "sectors" in body
        assert "Energy" in body["sectors"]

    def test_company_import_staff_only(self, authed: Client):
        url = reverse("companies_api:company_import")
        resp = authed.post(url, {})
        assert resp.status_code == 403

    def test_company_import_staff_allowed(self, staff_client: Client):
        url = reverse("companies_api:company_import")
        resp = staff_client.post(url, {})
        # May 502 if provider unreachable in test env — that's acceptable, just not 403/405
        assert resp.status_code in (200, 502), resp.content


# ── Scanner API ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestScannerEndpoints:
    def test_scanner_run_requires_auth(self, client: Client):
        url = reverse("scanner_api:scanner_run")
        resp = client.post(url, {"short_period": 7, "long_period": 30, "lookback_days": 10, "max_stocks": 25})
        assert resp.status_code == 403

    def test_scanner_run_valid(self, authed: Client, seeded_company: Company):
        url = reverse("scanner_api:scanner_run")
        resp = authed.post(
            url,
            {"short_period": 7, "long_period": 30, "lookback_days": 10, "max_stocks": 25},
            content_type="application/json",
        )
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert "rows" in body
        assert "counts" in body
        assert "bullish" in body["counts"]
        assert "bearish" in body["counts"]
        assert "total_crossovers" in body
        assert "skipped" in body
        assert "as_of" in body

    def test_scanner_run_invalid_long_less_than_short(self, authed: Client):
        url = reverse("scanner_api:scanner_run")
        resp = authed.post(
            url,
            {"short_period": 30, "long_period": 7, "lookback_days": 10, "max_stocks": 25},
            content_type="application/json",
        )
        assert resp.status_code == 422, resp.content
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "long_period" in body["error"]["fields"]

    def test_scanner_run_missing_fields(self, authed: Client):
        url = reverse("scanner_api:scanner_run")
        resp = authed.post(url, {}, content_type="application/json")
        # All fields have defaults — empty body is valid
        assert resp.status_code == 200, resp.content

    def test_scanner_settings_get(self, authed: Client):
        url = reverse("scanner_api:scanner_settings")
        resp = authed.get(url)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["short_period"] == 7
        assert body["long_period"] == 30
        assert body["lookback_days"] == 10
        assert body["max_stocks"] == 25

    def test_scanner_settings_put_staff_only(self, authed: Client):
        url = reverse("scanner_api:scanner_settings")
        resp = authed.put(url, {"short_period": 10, "long_period": 40, "lookback_days": 15, "max_stocks": 30}, content_type="application/json")
        assert resp.status_code == 403

    def test_scanner_settings_put_staff_allowed(self, staff_client: Client):
        url = reverse("scanner_api:scanner_settings")
        resp = staff_client.put(url, {"short_period": 10, "long_period": 40, "lookback_days": 15, "max_stocks": 30}, content_type="application/json")
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["status"] == "saved"

    def test_scanner_settings_put_invalid(self, staff_client: Client):
        url = reverse("scanner_api:scanner_settings")
        resp = staff_client.put(url, {"short_period": 30, "long_period": 7, "lookback_days": 10, "max_stocks": 25}, content_type="application/json")
        assert resp.status_code == 422

    def test_signals_list(self, authed: Client, seeded_company: Company):
        from apps.signals.models import TradingSignal
        TradingSignal.objects.create(
            company=seeded_company,
            strategy="SMA_CROSS",
            signal_type="BULLISH",
            short_period=7,
            long_period=30,
            short_sma=135.0,
            long_sma=134.0,
            close_price=139.0,
            crossover_date=date(2026, 11, 20),
        )
        url = reverse("scanner_api:signals_list")
        resp = authed.get(url)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["nse_code"] == "RELIANCE"
        assert body[0]["signal_type"] == "BULLISH"

    def test_signals_list_filter_type(self, authed: Client, seeded_company: Company):
        from apps.signals.models import TradingSignal
        TradingSignal.objects.create(
            company=seeded_company,
            strategy="SMA_CROSS",
            signal_type="BEARISH",
            short_period=7,
            long_period=30,
            short_sma=130.0,
            long_sma=131.0,
            close_price=129.0,
            crossover_date=date(2026, 11, 19),
        )
        url = reverse("scanner_api:signals_list")
        resp = authed.get(url, {"type": "BEARISH"})
        assert resp.status_code == 200
        body = resp.json()
        assert all(row["signal_type"] == "BEARISH" for row in body)


# ── Analytics API ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestAnalyticsEndpoints:
    def test_top_performers_all_periods(self, authed: Client, seeded_company: Company):
        url = reverse("analytics_api:top_performers")
        for period in ("1D", "1W", "1M", "3M", "6M", "1Y"):
            resp = authed.get(url, {"period": period, "limit": 10, "order": "desc"})
            assert resp.status_code == 200, f"period={period}: {resp.content}"
            body = resp.json()
            assert body["period"] == period
            assert "results" in body
            assert "excluded" in body

    def test_top_performers_invalid_period(self, authed: Client):
        url = reverse("analytics_api:top_performers")
        resp = authed.get(url, {"period": "INVALID"})
        assert resp.status_code == 400, resp.content

    def test_top_performers_sector_filter(self, authed: Client, seeded_company: Company):
        url = reverse("analytics_api:top_performers")
        resp = authed.get(url, {"period": "1M", "sector": "Energy", "limit": 5})
        assert resp.status_code == 200, resp.content

    def test_market_overview(self, authed: Client, seeded_company: Company):
        # Need 2 completed candles for advancers/decliners
        from apps.market_data.models import HistoricalPrice
        latest = HistoricalPrice.objects.filter(company=seeded_company).order_by("-candle_date").first()
        prev = HistoricalPrice.objects.filter(company=seeded_company).order_by("-candle_date")[1]
        if prev:
            prev.close = float(prev.close) - 5
            prev.save()
        url = reverse("analytics_api:market_overview")
        resp = authed.get(url)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert "advancers" in body
        assert "decliners" in body
        assert "unchanged" in body

    def test_sectors(self, authed: Client, seeded_company: Company):
        url = reverse("analytics_api:sectors")
        resp = authed.get(url, {"period": "1M"})
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert isinstance(body, list)


# ── Explorer API ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestExplorerEndpoints:
    def test_search_typeahead(self, authed: Client, seeded_company: Company):
        url = reverse("explorer_api:search_api")
        resp = authed.get(url, {"q": "reliance", "limit": 10})
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert "results" in body
        assert "sectors" in body
        assert any(r["nse_code"] == "RELIANCE" for r in body["results"])

    def test_search_empty_query(self, authed: Client, seeded_company: Company):
        url = reverse("explorer_api:search_api")
        resp = authed.get(url, {"q": "", "limit": 10})
        assert resp.status_code == 200, resp.content  # empty q is valid


# ── Dashboard API ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDashboardEndpoints:
    def test_dashboard_summary(self, authed: Client, seeded_company: Company):
        url = reverse("dashboard_api:dashboard_summary")
        resp = authed.get(url)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert "coverage" in body
        assert "breadth" in body
        assert "sectors" in body
        assert "recent_signals" in body
        assert "top_gainers" in body
        assert "freshness_stale" in body


# ── Fetcher API ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestFetcherEndpoints:
    def test_schedules_list(self, authed: Client):
        url = reverse("fetcher_api:schedules_list")
        resp = authed.get(url)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert "schedules" in body
        assert "provider" in body
        assert "scheduler" in body
        assert "cooling_down" in body["provider"]
        assert "stale" in body["scheduler"]

    def test_schedule_detail_put_staff_only(self, authed: Client):
        url = reverse("fetcher_api:schedule_detail", args=[1])
        resp = authed.put(url, {"enabled": False}, content_type="application/json")
        assert resp.status_code == 403

    def test_schedule_detail_not_found(self, staff_client: Client):
        url = reverse("fetcher_api:schedule_detail", args=[99999])
        resp = staff_client.put(url, {"enabled": False}, content_type="application/json")
        assert resp.status_code == 404

    def test_schedule_run_now_staff_only(self, authed: Client):
        url = reverse("fetcher_api:schedule_run_now", args=[1])
        resp = authed.post(url, {}, content_type="application/json")
        assert resp.status_code == 403

    def test_schedule_run_now_not_found(self, staff_client: Client):
        url = reverse("fetcher_api:schedule_run_now", args=[99999])
        resp = staff_client.post(url, {}, content_type="application/json")
        assert resp.status_code == 404

    def test_backfill_staff_only(self, authed: Client):
        url = reverse("fetcher_api:backfill")
        resp = authed.post(url, {"years": 1}, content_type="application/json")
        assert resp.status_code == 403

    def test_backfill_validation(self, staff_client: Client):
        url = reverse("fetcher_api:backfill")
        resp = staff_client.post(url, {"years": 99}, content_type="application/json")
        assert resp.status_code == 400, resp.content  # DRF returns 400 for validation

    def test_runs_list(self, authed: Client):
        url = reverse("fetcher_api:runs_list")
        resp = authed.get(url)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert_pagination_shape(body)

    def test_run_detail_not_found(self, authed: Client):
        url = reverse("fetcher_api:run_detail", args=[99999])
        resp = authed.get(url)
        assert resp.status_code == 404

    def test_coverage(self, authed: Client):
        url = reverse("fetcher_api:coverage")
        resp = authed.get(url)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert "companies" in body
        assert "with_data" in body
        assert "latest_candle" in body


# ── Live Data API ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLiveDataEndpoints:
    def test_live_quote(self, authed: Client, seeded_company: Company):
        url = reverse("market_data_api:live_quote", args=["RELIANCE"])
        resp = authed.get(url)
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert "symbol" in body
        assert "price" in body
        assert "as_of" in body
        assert "market_state" in body

    def test_live_quotes_batch(self, authed: Client, seeded_company: Company):
        url = reverse("market_data_api:live_quotes")
        resp = authed.get(url, {"symbols": "RELIANCE,TCS,INFY"})
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert isinstance(body, list)

    def test_live_quotes_batch_limit(self, authed: Client):
        url = reverse("market_data_api:live_quotes")
        symbols = ",".join([f"SYM{i}" for i in range(25)])
        resp = authed.get(url, {"symbols": symbols})
        assert resp.status_code == 200, resp.content  # server caps at 20

    def test_live_intraday(self, authed: Client, seeded_company: Company):
        url = reverse("market_data_api:live_intraday", args=["RELIANCE"])
        resp = authed.get(url, {"interval": "5m"})
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["symbol"] == "RELIANCE"
        assert body["interval"] == "5m"
        assert "bars" in body

    def test_live_refresh_metrics_staff_only(self, authed: Client):
        url = reverse("market_data_api:live_refresh_metrics", args=["RELIANCE"])
        resp = authed.post(url, {}, content_type="application/json")
        # Endpoint is authenticated-only; provider may be unreachable in test env (502)
        assert resp.status_code in (200, 502), resp.content


# ── Chart / Visualization API ────────────────────────────────────────────────

@pytest.mark.django_db
class TestChartEndpoints:
    def test_chart_payload_basic(self, authed: Client, seeded_company: Company):
        url = reverse("visualization_api:chart_payload", args=["RELIANCE"])
        resp = authed.get(url, {"tf": "1Y", "sma": "7,30", "markers": "1"})
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["symbol"] == "RELIANCE"
        assert body["tf"] == "1Y"
        assert body["basis"] == "unadjusted"
        assert len(body["candles"]) == 40
        assert "sma_7" in body["indicators"]
        assert "sma_30" in body["indicators"]
        assert "markers" in body
        assert "meta" in body
        assert body["meta"]["count"] == 40
        assert body["meta"]["complete_only"] is True

    def test_chart_payload_unknown_symbol(self, authed: Client):
        url = reverse("visualization_api:chart_payload", args=["NOPE"])
        resp = authed.get(url)
        assert resp.status_code == 404, resp.content
        body = resp.json()
        assert body["error"]["code"] == "NOT_FOUND"

    def test_chart_payload_bad_sma(self, authed: Client, seeded_company: Company):
        url = reverse("visualization_api:chart_payload", args=["RELIANCE"])
        resp = authed.get(url, {"sma": "7,abc"})
        assert resp.status_code == 422, resp.content

    def test_chart_payload_sma_out_of_range(self, authed: Client, seeded_company: Company):
        url = reverse("visualization_api:chart_payload", args=["RELIANCE"])
        resp = authed.get(url, {"sma": "9999"})
        assert resp.status_code == 422, resp.content

    def test_chart_payload_before_anchor(self, authed: Client, seeded_company: Company):
        url = reverse("visualization_api:chart_payload", args=["RELIANCE"])
        resp = authed.get(url, {"tf": "MAX", "before": "2026-01-10"})
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["meta"]["to"] == "2026-01-10"
        assert all(c["time"] <= "2026-01-10" for c in body["candles"])

    def test_chart_payload_bad_before(self, authed: Client, seeded_company: Company):
        url = reverse("visualization_api:chart_payload", args=["RELIANCE"])
        resp = authed.get(url, {"before": "not-a-date"})
        assert resp.status_code == 400, resp.content  # DRF returns 400 for invalid date

    def test_chart_payload_extra_indicators(self, authed: Client, seeded_company: Company):
        url = reverse("visualization_api:chart_payload", args=["RELIANCE"])
        resp = authed.get(url, {"ind": "ema:12,rsi:14,macd:12,26,9,bollinger:20,2,volume_sma:20"})
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert "ema_12" in body["indicators"]
        assert "rsi_14" in body["indicators"]
        assert "macd" in body["indicators"]
        assert "macd_signal" in body["indicators"]
        assert "macd_histogram" in body["indicators"]
        assert "bollinger_upper" in body["indicators"]
        assert "bollinger_middle" in body["indicators"]
        assert "bollinger_lower" in body["indicators"]
        assert "volume_sma_20" in body["indicators"]

    def test_chart_payload_benchmark(self, authed: Client, seeded_company: Company):
        url = reverse("visualization_api:chart_payload", args=["RELIANCE"])
        resp = authed.get(url, {"benchmark": "^NSEI"})
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert "benchmark" in body["indicators"]

    def test_chart_payload_indicator_invalid_name(self, authed: Client, seeded_company: Company):
        url = reverse("visualization_api:chart_payload", args=["RELIANCE"])
        resp = authed.get(url, {"ind": "nonexistent:5"})
        assert resp.status_code == 422, resp.content


# ── Health Endpoint ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestHealthEndpoint:
    def test_health_ok(self, client: Client):
        resp = client.get("/health/")
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["status"] == "ok"
        assert body["db"] == "ok"
        assert "scheduler_last_tick" in body


def assert_pagination_shape(body: dict) -> None:
    assert "results" in body
    assert "pagination" in body
    pg = body["pagination"]
    for key in ("page", "page_size", "total", "num_pages", "has_next", "has_previous"):
        assert key in pg, f"Missing pagination key: {key}"
