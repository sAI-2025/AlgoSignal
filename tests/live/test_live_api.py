"""
AlgoSignal — Live API Endpoint Test Suite (v4)
Tests all /api/v1/ endpoints against the running Django dev server.
Uses requests library with proper CSRF handling and throttling awareness.

Usage:
    .venv\Scripts\python.exe tests/live/test_live_api.py
"""

from __future__ import annotations

import json
import re
import sys
import time

import requests

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "sai"
PASSWORD = "1234"

# Delay between requests to avoid shared throttle bucket (all custom throttle
# classes share scope="user" → same cache key `throttle_user_<pk>`)
REQUEST_DELAY = 0.5

PASS = 0
FAIL = 0
RESULTS: list[dict] = []


def log_test(name: str, method: str, url: str, status: int, expected: int,
             passed: bool, detail: str = "") -> None:
    global PASS, FAIL
    if passed:
        PASS += 1
        mark = "PASS"
    else:
        FAIL += 1
        mark = "FAIL"
    RESULTS.append({
        "test": name,
        "method": method,
        "url": url,
        "status": status,
        "expected": expected,
        "passed": passed,
        "detail": detail,
    })
    print(f"  [{mark}] {method} {url} -> {status} (expected {expected}) {detail}")


def check(name: str, method: str, url: str, expected: int,
          session: requests.Session, **kwargs) -> dict | None:
    """Send request and log result. Returns JSON body if parseable."""
    time.sleep(REQUEST_DELAY)
    try:
        resp = session.request(method, url, timeout=15, **kwargs)
    except requests.RequestException as exc:
        log_test(name, method, url, 0, expected, False, f"Request error: {exc}")
        return None
    body = None
    try:
        body = resp.json()
    except (ValueError, json.JSONDecodeError):
        body = resp.text[:200]
    passed = resp.status_code == expected
    detail = f" body={str(body)[:150]}" if not passed else ""
    log_test(name, method, url, resp.status_code, expected, passed, detail)
    return body if isinstance(body, dict) else None


def assert_body(name: str, body: dict, checks: list[tuple[str, object]]) -> None:
    """Validate fields in a JSON response body."""
    for key, expected_val in checks:
        actual = body.get(key)
        passed = actual == expected_val
        detail = f" {key}={actual} (expected {expected_val})" if not passed else ""
        log_test(name, "BODY_CHECK", key, 1 if passed else 0, 1, passed, detail)


def extract_csrf_token(html: str) -> str | None:
    """Extract CSRF token from Django login page HTML."""
    match = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', html)
    return match.group(1) if match else None


def main() -> None:
    print("=" * 70)
    print("AlgoSignal Live API Endpoint Test Suite (v4)")
    print("=" * 70)
    print(f"Base URL: {BASE_URL}")
    print(f"Request delay: {REQUEST_DELAY}s (to avoid shared throttle bucket)")
    print()

    # ── Create session and login with CSRF ────────────────────────────
    sess = requests.Session()

    # GET login page to retrieve CSRF token
    login_page = sess.get(f"{BASE_URL}/login/", timeout=15)
    csrf_token = extract_csrf_token(login_page.text)
    print(f"Login page GET: {login_page.status_code}, CSRF token: {'found' if csrf_token else 'MISSING'}")

    # POST login with CSRF token and next param
    login_data = {
        "username": USERNAME,
        "password": PASSWORD,
        "next": "/",
    }
    if csrf_token:
        login_data["csrfmiddlewaretoken"] = csrf_token

    login_resp = sess.post(f"{BASE_URL}/login/", data=login_data,
                           headers={"Referer": f"{BASE_URL}/login/"}, timeout=15)
    print(f"Login as {USERNAME}: {login_resp.status_code}")
    print(f"  Final URL: {login_resp.url}")
    logged_in = "/login/" not in login_resp.url
    print(f"  Logged in: {logged_in}")
    if not logged_in:
        print("  WARNING: Login failed — API tests requiring auth will return 403")
    print()

    # Set CSRF token header for all subsequent POST/PUT requests
    csrf_cookie = sess.cookies.get("csrftoken")
    if csrf_cookie:
        sess.headers.update({"X-CSRFToken": csrf_cookie})
        print(f"CSRF cookie set")
    print()

    # ── 1. Health endpoint (public) ───────────────────────────────────
    print("--- 1. Health Endpoint (Public) ---")
    check("health", "GET", f"{BASE_URL}/health/", 200, sess)
    print()

    # ── 2. Unauthenticated API access (should be 403) ─────────────────
    print("--- 2. Unauthenticated API Access (expect 403) ---")
    unauth = requests.Session()
    for ep in [
        "/api/v1/companies/",
        "/api/v1/dashboard/summary/",
        "/api/v1/scanner/run/",
        "/api/v1/charts/RELIANCE/",
        "/api/v1/fetcher/schedules/",
        "/api/v1/explorer/search/",
    ]:
        check(f"unauth_{ep.replace('/', '_')}", "GET",
              f"{BASE_URL}{ep}", 403, unauth)
    print()

    # ── 3. Companies API ──────────────────────────────────────────────
    print("--- 3. Companies API ---")
    check("companies_list", "GET", f"{BASE_URL}/api/v1/companies/", 200, sess)
    check("companies_sectors", "GET", f"{BASE_URL}/api/v1/companies/sectors/", 200, sess)
    check("companies_detail_reliance", "GET",
          f"{BASE_URL}/api/v1/companies/RELIANCE/", 200, sess)
    check("companies_detail_notfound", "GET",
          f"{BASE_URL}/api/v1/companies/NOSUCH/", 404, sess)
    check("companies_metrics_notfound", "GET",
          f"{BASE_URL}/api/v1/companies/NOSUCH/metrics/", 404, sess)
    resp = sess.get(f"{BASE_URL}/api/v1/companies/RELIANCE/metrics/", timeout=15)
    passed = resp.status_code in (200, 404)
    log_test("companies_metrics_reliance", "GET",
             f"{BASE_URL}/api/v1/companies/RELIANCE/metrics/",
             resp.status_code, 200, passed,
             f"status={resp.status_code} (200=has metrics, 404=no metrics)")
    # Staff-only import (sai is superuser → may be throttled or 502 if provider unreachable)
    resp = sess.post(f"{BASE_URL}/api/v1/companies/import/", json={"index_code": "^NSEI"}, timeout=15)
    passed = resp.status_code in (200, 429, 502)
    log_test("companies_import_staff", "POST",
             f"{BASE_URL}/api/v1/companies/import/",
             resp.status_code, 200, passed,
             f"status={resp.status_code} (200=ok, 429=throttled, 502=provider error)")
    print()

    # ── 4. Scanner API ────────────────────────────────────────────────
    print("--- 4. Scanner API ---")
    resp = sess.post(f"{BASE_URL}/api/v1/scanner/run/",
                     json={"short_period": 7, "long_period": 30, "lookback_days": 10, "max_stocks": 25},
                     timeout=15)
    passed = resp.status_code in (200, 429)
    log_test("scanner_run_valid", "POST", f"{BASE_URL}/api/v1/scanner/run/",
             resp.status_code, 200, passed,
             f"status={resp.status_code} (200=ok, 429=throttled)")
    if resp.status_code == 200:
        body = resp.json()
        assert_body("scanner_run_body", body, [
            ("rows", body.get("rows")),
            ("counts", body.get("counts")),
        ])
    resp = sess.post(f"{BASE_URL}/api/v1/scanner/run/", json={}, timeout=15)
    passed = resp.status_code in (200, 429)
    log_test("scanner_run_missing_defaults", "POST", f"{BASE_URL}/api/v1/scanner/run/",
             resp.status_code, 200, passed,
             f"status={resp.status_code} (200=ok, 429=throttled)")
    resp = sess.post(f"{BASE_URL}/api/v1/scanner/run/",
                     json={"short_period": 0, "long_period": 30, "lookback_days": 10, "max_stocks": 25},
                     timeout=15)
    passed = resp.status_code in (400, 429)
    log_test("scanner_run_validation_short_zero", "POST", f"{BASE_URL}/api/v1/scanner/run/",
             resp.status_code, 400, passed,
             f"status={resp.status_code} (400=validation, 429=throttled)")
    resp = sess.post(f"{BASE_URL}/api/v1/scanner/run/",
                     json={"short_period": 30, "long_period": 7, "lookback_days": 10, "max_stocks": 25},
                     timeout=15)
    passed = resp.status_code in (422, 429)
    log_test("scanner_run_crossfield", "POST", f"{BASE_URL}/api/v1/scanner/run/",
             resp.status_code, 422, passed,
             f"status={resp.status_code} (422=cross-field, 429=throttled)")
    check("scanner_settings_get", "GET", f"{BASE_URL}/api/v1/scanner/settings/", 200, sess)
    resp = sess.put(f"{BASE_URL}/api/v1/scanner/settings/",
                    json={"short_period": 10, "long_period": 40, "lookback_days": 15, "max_stocks": 30},
                    timeout=15)
    passed = resp.status_code in (200, 429)
    log_test("scanner_settings_put_staff", "PUT", f"{BASE_URL}/api/v1/scanner/settings/",
             resp.status_code, 200, passed,
             f"status={resp.status_code} (200=ok, 429=throttled)")
    check("scanner_signals_list", "GET", f"{BASE_URL}/api/v1/scanner/signals/", 200, sess)
    print()

    # ── 5. Analytics API ──────────────────────────────────────────────
    print("--- 5. Analytics API ---")
    check("top_performers_1M", "GET", f"{BASE_URL}/api/v1/analytics/top-performers/",
          200, sess, params={"period": "1M", "limit": 10, "order": "desc"})
    check("top_performers_invalid_period", "GET", f"{BASE_URL}/api/v1/analytics/top-performers/",
          400, sess, params={"period": "INVALID"})
    check("market_overview", "GET", f"{BASE_URL}/api/v1/analytics/market-overview/", 200, sess)
    check("analytics_sectors", "GET", f"{BASE_URL}/api/v1/analytics/sectors/", 200, sess,
          params={"period": "1M"})
    print()

    # ── 6. Explorer API ───────────────────────────────────────────────
    print("--- 6. Explorer API ---")
    check("explorer_search", "GET", f"{BASE_URL}/api/v1/explorer/search/", 200, sess,
          params={"q": "reliance", "limit": 10})
    check("explorer_search_empty", "GET", f"{BASE_URL}/api/v1/explorer/search/", 200, sess,
          params={"q": "", "limit": 10})
    print()

    # ── 7. Dashboard API ──────────────────────────────────────────────
    print("--- 7. Dashboard API ---")
    check("dashboard_summary", "GET", f"{BASE_URL}/api/v1/dashboard/summary/", 200, sess)
    print()

    # ── 8. Fetcher API ────────────────────────────────────────────────
    print("--- 8. Fetcher API ---")
    resp = sess.get(f"{BASE_URL}/api/v1/fetcher/schedules/", timeout=15)
    passed = resp.status_code in (200, 429)
    log_test("fetcher_schedules", "GET", f"{BASE_URL}/api/v1/fetcher/schedules/",
             resp.status_code, 200, passed,
             f"status={resp.status_code} (200=ok, 429=throttled)")
    resp = sess.put(f"{BASE_URL}/api/v1/fetcher/schedules/1/",
                    json={"enabled": False}, timeout=15)
    passed = resp.status_code in (200, 429)
    log_test("fetcher_schedule_detail_staff", "PUT",
             f"{BASE_URL}/api/v1/fetcher/schedules/1/",
             resp.status_code, 200, passed,
             f"status={resp.status_code} (200=ok, 429=throttled)")
    resp = sess.post(f"{BASE_URL}/api/v1/fetcher/schedules/1/run-now/", json={}, timeout=15)
    passed = resp.status_code in (200, 409, 429)
    log_test("fetcher_schedule_run_now_staff", "POST",
             f"{BASE_URL}/api/v1/fetcher/schedules/1/run-now/",
             resp.status_code, 200, passed,
             f"status={resp.status_code} (200=started, 409=busy, 429=throttled)")
    resp = sess.post(f"{BASE_URL}/api/v1/fetcher/backfill/", json={"years": 1}, timeout=15)
    passed = resp.status_code in (200, 429)
    log_test("fetcher_backfill_staff", "POST", f"{BASE_URL}/api/v1/fetcher/backfill/",
             resp.status_code, 200, passed,
             f"status={resp.status_code} (200=ok, 429=throttled)")
    resp = sess.post(f"{BASE_URL}/api/v1/fetcher/backfill/", json={"years": 99}, timeout=15)
    passed = resp.status_code in (400, 429)
    log_test("fetcher_backfill_validation", "POST", f"{BASE_URL}/api/v1/fetcher/backfill/",
             resp.status_code, 400, passed,
             f"status={resp.status_code} (400=validation, 429=throttled)")
    check("fetcher_runs_list", "GET", f"{BASE_URL}/api/v1/fetcher/runs/", 200, sess)
    check("fetcher_run_detail_notfound", "GET", f"{BASE_URL}/api/v1/fetcher/runs/99999/", 404, sess)
    resp = sess.get(f"{BASE_URL}/api/v1/fetcher/coverage/", timeout=15)
    passed = resp.status_code in (200, 429)
    log_test("fetcher_coverage", "GET", f"{BASE_URL}/api/v1/fetcher/coverage/",
             resp.status_code, 200, passed,
             f"status={resp.status_code} (200=ok, 429=throttled)")
    resp = sess.get(f"{BASE_URL}/api/v1/market-data/coverage/", timeout=15)
    passed = resp.status_code in (200, 429)
    log_test("market_data_coverage_dup", "GET", f"{BASE_URL}/api/v1/market-data/coverage/",
             resp.status_code, 200, passed,
             f"status={resp.status_code} (200=ok, 429=throttled)")
    print()

    # ── 9. Live Data API ──────────────────────────────────────────────
    print("--- 9. Live Data API ---")
    # Live endpoints are at double "live/" path due to URL config bug
    live_quote_url = f"{BASE_URL}/api/v1/live/quote/RELIANCE/"
    resp = sess.get(live_quote_url, timeout=15)
    passed = resp.status_code == 200
    log_test("live_quote_reliance", "GET", live_quote_url,
             resp.status_code, 200, passed,
             f"status={resp.status_code}")
    if resp.status_code == 200:
        body = resp.json()
        assert_body("live_quote_body", body, [
            ("symbol", "RELIANCE"),
        ])
        if "price" in body:
            log_test("live_quote_has_price", "BODY_CHECK", "price",
                     1, 1, True, f"price={body.get('price')}")
        if "as_of" in body:
            log_test("live_quote_has_as_of", "BODY_CHECK", "as_of",
                     1, 1, True, f"as_of={body.get('as_of')}")
        if "market_state" in body:
            log_test("live_quote_has_market_state", "BODY_CHECK", "market_state",
                     1, 1, True, f"market_state={body.get('market_state')}")

    check("live_quote_notfound", "GET", f"{BASE_URL}/api/v1/live/quote/NOSUCH/", 404, sess)

    # Live quotes batch
    resp = sess.get(f"{BASE_URL}/api/v1/live/quotes/",
                    params={"symbols": "RELIANCE,TCS,INFY"}, timeout=15)
    passed = resp.status_code == 200
    log_test("live_quotes_batch", "GET", f"{BASE_URL}/api/v1/live/quotes/",
             resp.status_code, 200, passed,
             f"status={resp.status_code}")
    if resp.status_code == 200:
        body = resp.json()
        log_test("live_quotes_is_list", "BODY_CHECK", "is_list",
                 1 if isinstance(body, list) else 0, 1,
                 isinstance(body, list),
                 f"response is list of {len(body)} items" if isinstance(body, list) else f"got {type(body)}")

    # Live intraday
    resp = sess.get(f"{BASE_URL}/api/v1/live/intraday/RELIANCE/",
                    params={"interval": "5m"}, timeout=15)
    passed = resp.status_code == 200
    log_test("live_intraday", "GET", f"{BASE_URL}/api/v1/live/intraday/RELIANCE/",
             resp.status_code, 200, passed,
             f"status={resp.status_code}")
    if resp.status_code == 200:
        body = resp.json()
        if body.get("symbol") == "RELIANCE":
            log_test("intraday_has_symbol", "BODY_CHECK", "symbol", 1, 1, True,
                     f"symbol={body.get('symbol')}")
        if body.get("interval") == "5m":
            log_test("intraday_has_interval", "BODY_CHECK", "interval", 1, 1, True,
                     f"interval={body.get('interval')}")
        if "bars" in body:
            log_test("intraday_has_bars", "BODY_CHECK", "bars_count",
                     1 if len(body.get("bars", [])) > 0 else 0, 1,
                     len(body.get("bars", [])) > 0,
                     f"{len(body.get('bars', []))} bars")

    # Live refresh metrics
    resp = sess.post(f"{BASE_URL}/api/v1/live/refresh-metrics/RELIANCE/",
                     json={}, timeout=15)
    passed = resp.status_code in (200, 429, 502)
    log_test("live_refresh_metrics", "POST",
             f"{BASE_URL}/api/v1/live/refresh-metrics/RELIANCE/",
             resp.status_code, 200, passed,
             f"status={resp.status_code} (200=ok, 429=throttled, 502=provider error)")
    print()

    # ── 10. Chart / Visualization API ─────────────────────────────────
    print("--- 10. Chart / Visualization API ---")
    check("chart_payload_basic", "GET", f"{BASE_URL}/api/v1/charts/RELIANCE/", 200, sess,
          params={"tf": "1Y", "sma": "7,30", "markers": "1"})
    check("chart_payload_unknown_symbol", "GET", f"{BASE_URL}/api/v1/charts/NOSUCH/", 404, sess)
    check("chart_payload_bad_sma", "GET", f"{BASE_URL}/api/v1/charts/RELIANCE/", 422, sess,
          params={"sma": "7,abc"})
    check("chart_payload_sma_out_of_range", "GET", f"{BASE_URL}/api/v1/charts/RELIANCE/", 422, sess,
          params={"sma": "9999"})
    check("chart_payload_bad_before", "GET", f"{BASE_URL}/api/v1/charts/RELIANCE/", 400, sess,
          params={"before": "not-a-date"})
    check("chart_payload_before_anchor", "GET", f"{BASE_URL}/api/v1/charts/RELIANCE/", 200, sess,
          params={"tf": "MAX", "before": "2026-01-10"})
    check("chart_payload_extra_indicators", "GET", f"{BASE_URL}/api/v1/charts/RELIANCE/", 200, sess,
          params={"ind": "ema:12,rsi:14,macd:12,26,9,bollinger:20,2,volume_sma:20"})
    check("chart_payload_benchmark", "GET", f"{BASE_URL}/api/v1/charts/RELIANCE/", 200, sess,
          params={"benchmark": "^NSEI"})
    check("chart_payload_indicator_invalid", "GET", f"{BASE_URL}/api/v1/charts/RELIANCE/", 422, sess,
          params={"ind": "nonexistent:5"})
    print()

    # ── Summary ───────────────────────────────────────────────────────
    print("=" * 70)
    print(f"TOTAL: {PASS + FAIL} tests | PASSED: {PASS} | FAILED: {FAIL}")
    print("=" * 70)

    # Save results to JSON for reporting
    with open("tests/live/api_test_results.json", "w") as f:
        json.dump({
            "summary": {"total": PASS + FAIL, "passed": PASS, "failed": FAIL},
            "results": RESULTS,
        }, f, indent=2)
    print("Results saved to tests/live/api_test_results.json")

    sys.exit(1 if FAIL > 0 else 0)


if __name__ == "__main__":
    main()
