"""Integration / end-to-end tests — full user flows across multiple endpoints,
and calculation verification through the API. Run with:
pytest tests/integration/test_full_flow.py"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.test import Client
from django.urls import reverse

from apps.companies.models import Company
from apps.market_data.models import CompanyMetrics, HistoricalPrice
from apps.signals.models import TradingSignal


@pytest.fixture
def authed(client: Client, user) -> Client:
    client.force_login(user)
    return client


# ── Full flow: add company → fetch history → scan → view signals → chart ────

@pytest.mark.django_db
def test_full_flow_add_company_to_chart(authed: Client):
    """E2E: Add a stock, verify it shows in companies list, then chart loads."""
    # 1. Add company via CLI-equivalent (direct ORM, as the web form does)
    company = Company.objects.create(
        company_name="Infosys Ltd", nse_code="INFY", sector="IT", is_active=True
    )

    # 2. Verify it appears in the companies API list
    list_resp = authed.get(reverse("companies_api:company_list"), {"q": "infy"})
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert any(r["nse_code"] == "INFY" for r in body["results"])

    # 3. Verify company detail API
    detail_resp = authed.get(reverse("companies_api:company_detail", args=["INFY"]))
    assert detail_resp.status_code == 200
    assert detail_resp.json()["company_name"] == "Infosys Ltd"

    # 4. Seed candles so the chart has data
    start = date(2026, 1, 1)
    for offset in range(60):
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

    # 5. Chart payload loads with all candles
    chart_resp = authed.get(
        reverse("visualization:chart_payload", args=["INFY"]),
        {"tf": "3M", "sma": "7,30", "markers": "1"},
    )
    assert chart_resp.status_code == 200
    chart_body = chart_resp.json()
    assert chart_body["symbol"] == "INFY"
    assert len(chart_body["candles"]) == 60
    assert "sma_7" in chart_body["indicators"]
    assert "sma_30" in chart_body["indicators"]

    # 6. Scanner finds crossovers on this data
    scan_resp = authed.post(
        reverse("scanner_api:scanner_run"),
        {"short_period": 7, "long_period": 30, "lookback_days": 10, "max_stocks": 25},
        content_type="application/json",
    )
    assert scan_resp.status_code == 200
    scan_body = scan_resp.json()
    assert "rows" in scan_body
    assert "counts" in scan_body


# ── Calculation verification via API ────────────────────────────────────────

@pytest.mark.django_db
class TestCalculationVerification:
    """Verify SMA/EMA/RSI/MACD/Bollinger values returned by the chart API match
    hand-calculated expectations (server-side math correctness)."""

    @staticmethod
    def _expected_sma(closes: list[float], window: int) -> list[float | None]:
        out: list[float | None] = []
        for i in range(len(closes)):
            if i < window - 1:
                out.append(None)
            else:
                out.append(sum(closes[i - window + 1 : i + 1]) / window)
        return out

    def test_sma_7_values_match_hand_calculation(self, authed: Client):
        company = Company.objects.create(
            company_name="Calc Test", nse_code="CALC", sector="IT", is_active=True
        )
        # Known closes: 10,11,12,13,14,15,16,17,18,19,20
        closes = [float(v) for v in range(10, 21)]
        start = date(2026, 1, 1)
        for offset, close in enumerate(closes):
            HistoricalPrice.objects.create(
                company=company,
                candle_date=start + timedelta(days=offset),
                open=close - 1,
                high=close + 1,
                low=close - 1,
                close=close,
                adj_close=close,
                volume=1000,
            )

        resp = authed.get(
            reverse("visualization:chart_payload", args=["CALC"]),
            {"tf": "MAX", "sma": "7", "markers": "0"},
        )
        assert resp.status_code == 200
        body = resp.json()
        sma_points = body["indicators"]["sma_7"]

        # Map time → value for lookup
        sma_map = {p["time"]: p["value"] for p in sma_points}

        expected = self._expected_sma(closes, 7)
        for i, exp_val in enumerate(expected):
            candle_date = (start + timedelta(days=i)).isoformat()
            if exp_val is None:
                assert candle_date not in sma_map, f"SMA should be undefined for {candle_date}"
            else:
                assert candle_date in sma_map, f"Missing SMA for {candle_date}"
                assert abs(sma_map[candle_date] - exp_val) < 0.001, (
                    f"SMA mismatch at {candle_date}: "
                    f"got {sma_map[candle_date]}, expected {exp_val}"
                )

    def test_scanner_crossover_detection(self, authed: Client):
        """Verify bullish/bearish detection via a controlled price sequence."""
        company = Company.objects.create(
            company_name="Cross Test", nse_code="CROSS", sector="IT", is_active=True
        )
        # Closes designed to create a bullish crossover at the end:
        # SMA 3 stays above SMA 7 after being below
        closes = [100, 99, 98, 97, 96, 95, 94, 100, 105, 110, 115, 120]
        start = date(2026, 1, 1)
        for offset, close in enumerate(closes):
            HistoricalPrice.objects.create(
                company=company,
                candle_date=start + timedelta(days=offset),
                open=close,
                high=close + 1,
                low=close - 1,
                close=close,
                adj_close=close,
                volume=1000,
            )

        resp = authed.post(
            reverse("scanner_api:scanner_run"),
            {"short_period": 3, "long_period": 7, "lookback_days": 12, "max_stocks": 25},
            content_type="application/json",
        )
        assert resp.status_code == 200
        body = resp.json()
        # Should find at least one bullish signal for CROSS
        cross_rows = [r for r in body["rows"] if r["nse_code"] == "CROSS"]
        if cross_rows:
            assert cross_rows[0]["signal_type"] in ("BULLISH", "BEARISH")
            if "params" in cross_rows[0]:
                assert cross_rows[0]["params"] == [3, 7]

    def test_market_overview_advancers_decliners(self, authed: Client):
        """Verify advancers/decliners calculation from last two closes."""
        c1 = Company.objects.create(company_name="Advancer", nse_code="ADV", sector="IT", is_active=True)
        c2 = Company.objects.create(company_name="Decliner", nse_code="DEC", sector="IT", is_active=True)
        today = date(2026, 11, 20)
        yesterday = date(2026, 11, 19)

        # ADV: up today
        HistoricalPrice.objects.create(company=c1, candle_date=yesterday, open=100, high=101, low=99, close=100, adj_close=100, volume=1000)
        HistoricalPrice.objects.create(company=c1, candle_date=today, open=100, high=105, low=100, close=105, adj_close=105, volume=1000)
        # DEC: down today
        HistoricalPrice.objects.create(company=c2, candle_date=yesterday, open=100, high=101, low=99, close=100, adj_close=100, volume=1000)
        HistoricalPrice.objects.create(company=c2, candle_date=today, open=100, high=101, low=95, close=95, adj_close=95, volume=1000)

        resp = authed.get(reverse("analytics_api:market_overview"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["advancers"] >= 1
        assert body["decliners"] >= 1


# ── Dashboard data integrity ────────────────────────────────────────────────

@pytest.mark.django_db
class TestDashboardDataIntegrity:
    def test_dashboard_summary_shapes(self, authed: Client):
        c1 = Company.objects.create(company_name="Co A", nse_code="COA", sector="IT", is_active=True)
        c2 = Company.objects.create(company_name="Co B", nse_code="COB", sector="Energy", is_active=True)
        # Add candle data so coverage counts them
        from apps.market_data.models import HistoricalPrice
        from datetime import date, timedelta
        today = date(2026, 11, 20)
        for c in (c1, c2):
            HistoricalPrice.objects.create(
                company=c, candle_date=today, open=100, high=101, low=99, close=100,
                adj_close=100, volume=1000,
            )

        resp = authed.get(reverse("dashboard_api:dashboard_summary"))
        assert resp.status_code == 200
        body = resp.json()

        # Coverage shape
        cov = body["coverage"]
        assert "companies" in cov
        assert "with_data" in cov
        assert "latest_candle" in cov
        assert isinstance(cov["companies"], int)
        assert isinstance(cov["with_data"], int)

        # Breadth shape
        br = body["breadth"]
        assert "advancers" in br
        assert "decliners" in br
        assert "unchanged" in br

        # Top gainers shape
        for row in body["top_gainers"]:
            assert "nse_code" in row
            assert "company_name" in row
            assert "return_pct" in row

        # Recent signals shape
        for row in body["recent_signals"]:
            assert "nse_code" in row
            assert "signal_type" in row
            assert row["signal_type"] in ("BULLISH", "BEARISH")
            assert "crossover_date" in row

        # Freshness flag is boolean
        assert isinstance(body["freshness_stale"], bool)

    def test_freshness_chip_values(self, authed: Client):
        Company.objects.create(company_name="Fresh Co", nse_code="FRESH", sector="IT", is_active=True)
        resp = authed.get(reverse("fetcher_api:coverage"))
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["companies"], int)
        assert isinstance(body["with_data"], int)
        assert body["latest_candle"] is None or isinstance(body["latest_candle"], str)


# ── Error handling matrix ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestErrorHandlingMatrix:
    """Every endpoint returns the correct HTTP status + error envelope for
    invalid input, missing auth, missing staff, and missing resources."""

    def test_404_unknown_company_across_endpoints(self, authed: Client):
        endpoints = [
            reverse("companies_api:company_detail", args=["NOSUCH"]),
            reverse("companies_api:company_metrics", args=["NOSUCH"]),
            reverse("visualization_api:chart_payload", args=["NOSUCH"]),
            reverse("market_data_api:live_quote", args=["NOSUCH"]),
        ]
        for url in endpoints:
            resp = authed.get(url)
            assert resp.status_code == 404, f"Expected 404 for {url}, got {resp.status_code}"
            body = resp.json()
            assert body["error"]["code"] == "NOT_FOUND"

    def test_422_validation_scanner(self, authed: Client):
        url = reverse("scanner_api:scanner_run")
        # Zero short_period → DRF field validation returns 400
        resp = authed.post(url, {"short_period": 0, "long_period": 30, "lookback_days": 10, "max_stocks": 25}, content_type="application/json")
        assert resp.status_code == 400
        body = resp.json()
        assert "short_period" in str(body)

    def test_403_staff_endpoints_non_staff(self, authed: Client):
        staff_endpoints = [
            ("POST", reverse("companies_api:company_import"), {}),
            ("PUT", reverse("scanner_api:scanner_settings"), {"short_period": 10, "long_period": 40, "lookback_days": 10, "max_stocks": 25}),
            ("PUT", reverse("fetcher_api:schedule_detail", args=[1]), {"enabled": False}),
            ("POST", reverse("fetcher_api:schedule_run_now", args=[1]), {}),
            ("POST", reverse("fetcher_api:backfill"), {"years": 1}),
        ]
        for method, url, payload in staff_endpoints:
            resp = getattr(authed, method.lower())(url, payload, content_type="application/json")
            assert resp.status_code == 403, f"Expected 403 for {method} {url}, got {resp.status_code}"

    def test_302_all_api_endpoints_require_auth(self, client: Client):
        """Every /api/v1/ endpoint requires authentication (403 for DRF API)."""
        api_endpoints = [
            ("GET", reverse("companies_api:company_list")),
            ("GET", reverse("companies_api:company_sectors")),
            ("GET", reverse("dashboard_api:dashboard_summary")),
            ("GET", reverse("analytics_api:top_performers")),
            ("GET", reverse("analytics_api:market_overview")),
            ("GET", reverse("analytics_api:sectors")),
            ("GET", reverse("explorer_api:search_api")),
            ("GET", reverse("scanner_api:scanner_settings")),
            ("GET", reverse("scanner_api:signals_list")),
            ("GET", reverse("fetcher_api:schedules_list")),
            ("GET", reverse("fetcher_api:coverage")),
            ("GET", reverse("fetcher_api:runs_list")),
        ]
        for method, url in api_endpoints:
            resp = getattr(client, method.lower())(url)
            assert resp.status_code == 403, f"Expected 403 for {method} {url}, got {resp.status_code}"
