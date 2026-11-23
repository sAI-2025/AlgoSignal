"""
AlgoSignal — Data Integrity & Database Validation Test Suite (v2)
Tests calculation accuracy, scanner crossover detection, and database persistence
against the live server.

Requires server running on 127.0.0.1:8000 with seeded test data.

Usage:
    .venv\Scripts\python.exe tests/live/test_data_integrity.py
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

REQUEST_DELAY = 0.5

PASS = 0
FAIL = 0
RESULTS: list[dict] = []


def log_test(name: str, passed: bool, detail: str = "") -> None:
    global PASS, FAIL
    if passed:
        PASS += 1
        mark = "PASS"
    else:
        FAIL += 1
        mark = "FAIL"
    RESULTS.append({"test": name, "passed": passed, "detail": detail})
    print(f"  [{mark}] {name} {detail}")


def check(name: str, condition: bool, detail: str = "") -> None:
    log_test(name, condition, detail)


def extract_csrf_token(html: str) -> str | None:
    match = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', html)
    return match.group(1) if match else None


def main() -> None:
    print("=" * 70)
    print("AlgoSignal Data Integrity & Database Validation Suite (v2)")
    print("=" * 70)
    print(f"Base URL: {BASE_URL}")
    print()

    sess = requests.Session()

    # Login
    sess.get(f"{BASE_URL}/login/", timeout=15)
    csrf_token = extract_csrf_token(sess.cookies.get_dict() and "" or "")
    login_page = sess.get(f"{BASE_URL}/login/", timeout=15)
    csrf_token = extract_csrf_token(login_page.text)

    login_data = {"username": USERNAME, "password": PASSWORD, "next": "/"}
    if csrf_token:
        login_data["csrfmiddlewaretoken"] = csrf_token
    sess.post(f"{BASE_URL}/login/", data=login_data,
              headers={"Referer": f"{BASE_URL}/login/"}, timeout=15)

    csrf_cookie = sess.cookies.get("csrftoken")
    if csrf_cookie:
        sess.headers.update({"X-CSRFToken": csrf_cookie})

    time.sleep(REQUEST_DELAY)

    # ── 1. SMA Calculation Verification ──────────────────────────────
    print("--- 1. SMA Calculation Verification ---")
    resp = sess.get(f"{BASE_URL}/api/v1/charts/RELIANCE/",
                    params={"tf": "1Y", "sma": "7", "markers": "0"}, timeout=15)
    check("chart_reliance_sma7_returns_200", resp.status_code == 200,
          f"status={resp.status_code}")
    if resp.status_code == 200:
        body = resp.json()
        candles = body.get("candles", [])
        indicators = body.get("indicators", {})
        sma_7 = indicators.get("sma_7", [])
        check("chart_has_candles", len(candles) > 0, f"{len(candles)} candles")
        check("chart_has_sma_7", "sma_7" in indicators, "sma_7 indicator present")
        check("sma_7_has_points", len(sma_7) > 0, f"{len(sma_7)} SMA points")

        if sma_7:
            valid_points = [p for p in sma_7 if p.get("value") is not None]
            check("sma_7_valid_points", len(valid_points) > 0,
                  f"{len(valid_points)} valid SMA points")
            closes = [c["close"] for c in candles]
            if closes and valid_points:
                min_close, max_close = min(closes), max(closes)
                sma_values = [p["value"] for p in valid_points]
                sma_in_range = all(min_close - 50 <= v <= max_close + 50 for v in sma_values)
                check("sma_7_within_price_range", sma_in_range,
                      f"SMA values within [{min_close}, {max_close}]")
    time.sleep(REQUEST_DELAY)
    print()

    # ── 2. Scanner Crossover Detection ───────────────────────────────
    print("--- 2. Scanner Crossover Detection ---")
    resp = sess.post(f"{BASE_URL}/api/v1/scanner/run/", json={
        "short_period": 7, "long_period": 30, "lookback_days": 10, "max_stocks": 25
    }, timeout=15)
    check("scanner_run_200", resp.status_code == 200, f"status={resp.status_code}")
    if resp.status_code == 200:
        body = resp.json()
        check("scanner_has_rows", "rows" in body, "rows key present")
        check("scanner_has_counts", "counts" in body, "counts key present")
        check("scanner_has_total", "total_crossovers" in body, "total_crossovers present")
        check("scanner_has_as_of", "as_of" in body, "as_of present")
        if "counts" in body:
            counts = body["counts"]
            check("scanner_counts_has_bullish", "bullish" in counts,
                  f"bullish={counts.get('bullish')}")
            check("scanner_counts_has_bearish", "bearish" in counts,
                  f"bearish={counts.get('bearish')}")
        if "rows" in body and body["rows"]:
            row = body["rows"][0]
            check("scanner_row_has_nse_code", "nse_code" in row, f"row={row}")
            check("scanner_row_has_signal_type", "signal_type" in row,
                  f"signal_type={row.get('signal_type')}")
    time.sleep(REQUEST_DELAY)
    print()

    # ── 3. Market Overview Advancers/Decliners ───────────────────────
    print("--- 3. Market Overview (Advancers/Decliners) ---")
    resp = sess.get(f"{BASE_URL}/api/v1/analytics/market-overview/", timeout=15)
    check("market_overview_200", resp.status_code == 200, f"status={resp.status_code}")
    if resp.status_code == 200:
        body = resp.json()
        check("overview_has_advancers", "advancers" in body,
              f"advancers={body.get('advancers')}")
        check("overview_has_decliners", "decliners" in body,
              f"decliners={body.get('decliners')}")
        check("overview_has_unchanged", "unchanged" in body,
              f"unchanged={body.get('unchanged')}")
        total = body.get("advancers", 0) + body.get("decliners", 0) + body.get("unchanged", 0)
        check("overview_total_non_negative", total >= 0, f"total={total}")
    time.sleep(REQUEST_DELAY)
    print()

    # ── 4. Dashboard Summary Data Integrity ──────────────────────────
    print("--- 4. Dashboard Summary Data Integrity ---")
    resp = sess.get(f"{BASE_URL}/api/v1/dashboard/summary/", timeout=15)
    check("dashboard_summary_200", resp.status_code == 200, f"status={resp.status_code}")
    if resp.status_code == 200:
        body = resp.json()
        check("dashboard_has_coverage", "coverage" in body, "coverage present")
        check("dashboard_has_breadth", "breadth" in body, "breadth present")
        check("dashboard_has_sectors", "sectors" in body, "sectors present")
        check("dashboard_has_recent_signals", "recent_signals" in body, "recent_signals present")
        check("dashboard_has_top_gainers", "top_gainers" in body, "top_gainers present")
        check("dashboard_has_freshness_stale", "freshness_stale" in body,
              f"freshness_stale={body.get('freshness_stale')}")
        if "coverage" in body:
            cov = body["coverage"]
            check("coverage_has_companies", "companies" in cov, f"companies={cov.get('companies')}")
            check("coverage_has_with_data", "with_data" in cov, f"with_data={cov.get('with_data')}")
        if "breadth" in body:
            br = body["breadth"]
            check("breadth_has_advancers", "advancers" in br, f"advancers={br.get('advancers')}")
            check("breadth_has_decliners", "decliners" in br, f"decliners={br.get('decliners')}")
            check("breadth_has_unchanged", "unchanged" in br, f"unchanged={br.get('unchanged')}")
    time.sleep(REQUEST_DELAY)
    print()

    # ── 5. Coverage Consistency ──────────────────────────────────────
    print("--- 5. Coverage Consistency (dual endpoints) ---")
    resp1 = sess.get(f"{BASE_URL}/api/v1/fetcher/coverage/", timeout=15)
    resp2 = sess.get(f"{BASE_URL}/api/v1/market-data/coverage/", timeout=15)
    check("coverage_endpoint1_200", resp1.status_code == 200, f"status={resp1.status_code}")
    check("coverage_endpoint2_200", resp2.status_code == 200, f"status={resp2.status_code}")
    if resp1.status_code == 200 and resp2.status_code == 200:
        b1, b2 = resp1.json(), resp2.json()
        check("coverage_consistent_companies",
              b1.get("companies") == b2.get("companies"),
              f"endpoint1={b1.get('companies')}, endpoint2={b2.get('companies')}")
        check("coverage_consistent_with_data",
              b1.get("with_data") == b2.get("with_data"),
              f"endpoint1={b1.get('with_data')}, endpoint2={b2.get('with_data')}")
    time.sleep(REQUEST_DELAY)
    print()

    # ── 6. Chart Indicator Consistency ───────────────────────────────
    print("--- 6. Chart Indicator Consistency ---")
    resp = sess.get(f"{BASE_URL}/api/v1/charts/RELIANCE/",
                    params={"ind": "ema:12,rsi:14,macd:12,26,9,bollinger:20,2,volume_sma:20"},
                    timeout=15)
    check("chart_extra_indicators_200", resp.status_code == 200, f"status={resp.status_code}")
    if resp.status_code == 200:
        body = resp.json()
        indicators = body.get("indicators", {})
        expected_keys = ["ema_12", "rsi_14", "macd", "macd_signal", "macd_histogram",
                         "bollinger_upper", "bollinger_middle", "bollinger_lower", "volume_sma_20"]
        for key in expected_keys:
            check(f"chart_indicator_{key}", key in indicators,
                  f"{key} present" if key in indicators else f"{key} MISSING")
    time.sleep(REQUEST_DELAY)
    print()

    # ── 7. Benchmark Overlay ─────────────────────────────────────────
    print("--- 7. Benchmark Overlay ---")
    resp = sess.get(f"{BASE_URL}/api/v1/charts/RELIANCE/",
                    params={"benchmark": "^NSEI"}, timeout=15)
    check("chart_benchmark_200", resp.status_code == 200, f"status={resp.status_code}")
    if resp.status_code == 200:
        body = resp.json()
        indicators = body.get("indicators", {})
        check("chart_has_benchmark", "benchmark" in indicators, "benchmark present")
    time.sleep(REQUEST_DELAY)
    print()

    # ── 8. Live Quote Data Integrity ─────────────────────────────────
    print("--- 8. Live Quote Data Integrity ---")
    resp = sess.get(f"{BASE_URL}/api/v1/live/quote/RELIANCE/", timeout=15)
    check("live_quote_200", resp.status_code == 200, f"status={resp.status_code}")
    if resp.status_code == 200:
        body = resp.json()
        check("live_quote_has_symbol", "symbol" in body, f"symbol={body.get('symbol')}")
        check("live_quote_has_price", "price" in body, f"price={body.get('price')}")
        check("live_quote_has_as_of", "as_of" in body, "as_of present")
        check("live_quote_has_market_state", "market_state" in body,
              f"market_state={body.get('market_state')}")
    time.sleep(REQUEST_DELAY)
    print()

    # ── 9. Intraday Data Integrity ───────────────────────────────────
    print("--- 9. Intraday Data Integrity ---")
    resp = sess.get(f"{BASE_URL}/api/v1/live/intraday/RELIANCE/",
                    params={"interval": "5m"}, timeout=15)
    check("live_intraday_200", resp.status_code == 200, f"status={resp.status_code}")
    if resp.status_code == 200:
        body = resp.json()
        check("intraday_has_symbol", body.get("symbol") == "RELIANCE", f"symbol={body.get('symbol')}")
        check("intraday_has_interval", body.get("interval") == "5m", f"interval={body.get('interval')}")
        check("intraday_has_bars", "bars" in body, f"{len(body.get('bars', []))} bars")
    time.sleep(REQUEST_DELAY)
    print()

    # ── Summary ──────────────────────────────────────────────────────
    print("=" * 70)
    print(f"TOTAL: {PASS + FAIL} tests | PASSED: {PASS} | FAILED: {FAIL}")
    print("=" * 70)

    with open("tests/live/data_integrity_results.json", "w") as f:
        json.dump({
            "summary": {"total": PASS + FAIL, "passed": PASS, "failed": FAIL},
            "results": RESULTS,
        }, f, indent=2)
    print("Results saved to tests/live/data_integrity_results.json")

    sys.exit(1 if FAIL > 0 else 0)


if __name__ == "__main__":
    main()
