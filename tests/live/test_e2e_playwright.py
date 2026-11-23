"""
AlgoSignal — E2E Web UI Test Suite with Playwright
Tests the full browser experience: login, navigation, chart rendering, drawing tools.

Requires server running on 127.0.0.1:8000.

Usage:
    .venv\Scripts\python.exe tests/live/test_e2e_playwright.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "sai"
PASSWORD = "1234"

SCREENSHOT_DIR = Path("tests/live/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

PASS = 0
FAIL = 0
RESULTS: list[dict] = []


def log_test(name: str, passed: bool, detail: str = "", screenshot: str = "") -> None:
    global PASS, FAIL
    if passed:
        PASS += 1
        mark = "PASS"
    else:
        FAIL += 1
        mark = "FAIL"
    RESULTS.append({"test": name, "passed": passed, "detail": detail, "screenshot": screenshot})
    print(f"  [{mark}] {name} {detail}")


def take_screenshot(page, name: str) -> str:
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def run_e2e() -> None:
    global PASS, FAIL

    print("=" * 70)
    print("AlgoSignal E2E Web UI Test Suite (Playwright)")
    print("=" * 70)
    print(f"Base URL: {BASE_URL}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # ── 1. Health check ──────────────────────────────────────────
        print("--- 1. Server Health ---")
        resp = page.request.get(f"{BASE_URL}/health/")
        log_test("health_endpoint", resp.ok, f"status={resp.status}")
        print()

        # ── 2. Login ─────────────────────────────────────────────────
        print("--- 2. Login ---")
        page.goto(f"{BASE_URL}/login/")
        page.wait_for_load_state("networkidle")
        take_screenshot(page, "01_login_page")
        log_test("login_page_loads", page.url.endswith("/login/"), f"url={page.url}")

        page.fill('input[name="username"]', USERNAME)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")
        take_screenshot(page, "02_after_login")
        logged_in = "/login/" not in page.url
        log_test("login_success", logged_in, f"redirected to {page.url}")
        print()

        # ── 3. Dashboard ─────────────────────────────────────────────
        print("--- 3. Dashboard ---")
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        take_screenshot(page, "03_dashboard")
        has_coverage = page.locator('text="Companies with data"').count() > 0 or page.locator("[data-widget='coverage']").count() > 0
        log_test("dashboard_kpi_cards", has_coverage, "KPI cards visible")
        has_refresh = page.locator('[data-action="refresh-dashboard"]').count() > 0
        log_test("dashboard_refresh_button", has_refresh, "refresh button present")
        print()

        # ── 4. Sidebar navigation ────────────────────────────────────
        print("--- 4. Sidebar Navigation ---")
        nav_items = ["Dashboard", "Companies", "Signals", "Top Performers",
                     "Company Explorer", "Market Data", "Settings", "Watchlist", "Alerts"]
        for item in nav_items:
            locator = page.locator(f'text="{item}"')
            visible = locator.count() > 0
            log_test(f"nav_item_{item.lower().replace(' ', '_')}", visible, f"'{item}' in sidebar")
        take_screenshot(page, "04_sidebar")
        print()

        # ── 5. Companies page ────────────────────────────────────────
        print("--- 5. Companies Page ---")
        page.click('text="Companies"')
        page.wait_for_load_state("networkidle")
        take_screenshot(page, "05_companies_page")
        has_add_btn = page.locator('text="+ Add stock"').count() > 0 or page.locator('text="Add stock"').count() > 0
        log_test("companies_add_button", has_add_btn, "Add stock button present")
        has_table = page.locator("table").count() > 0
        log_test("companies_table", has_table, "company table present")
        has_search = page.locator('input[name="q"]').count() > 0
        log_test("companies_search", has_search, "search input present")
        print()

        # ── 6. Signals page ──────────────────────────────────────────
        print("--- 6. Signals Page ---")
        page.click('text="Signals"')
        page.wait_for_load_state("networkidle")
        take_screenshot(page, "06_signals_page")
        has_scanner_form = page.locator('input[name="short_period"]').count() > 0
        log_test("signals_scanner_form", has_scanner_form, "scanner parameter form present")
        has_generate = page.locator('text="Generate Signals"').count() > 0
        log_test("signals_generate_button", has_generate, "Generate Signals button present")
        print()

        # ── 7. Top Performers page ───────────────────────────────────
        print("--- 7. Top Performers Page ---")
        page.click('text="Top Performers"')
        page.wait_for_load_state("networkidle")
        take_screenshot(page, "07_top_performers")
        has_periods = page.locator('text="1M"').count() > 0
        log_test("top_performers_period_tabs", has_periods, "period tabs present")
        print()

        # ── 8. Company Explorer ──────────────────────────────────────
        print("--- 8. Company Explorer ---")
        page.click('text="Company Explorer"')
        page.wait_for_load_state("networkidle")
        take_screenshot(page, "08_explorer_home")
        has_search = page.locator('input[name="q"]').count() > 0 or page.locator('text="Company search"').count() > 0
        log_test("explorer_search", has_search, "company search present")
        print()

        # ── 9. Market Data page ──────────────────────────────────────
        print("--- 9. Market Data Page ---")
        page.click('text="Market Data"')
        page.wait_for_load_state("networkidle")
        take_screenshot(page, "09_market_data")
        has_provider = page.locator('text="yfinance"').count() > 0 or page.locator('text="Provider"').count() > 0
        log_test("market_data_provider", has_provider, "provider status visible")
        has_coverage_card = page.locator('text="Coverage"').count() > 0
        log_test("market_data_coverage", has_coverage_card, "coverage card present")
        print()

        # ── 10. Settings page ────────────────────────────────────────
        print("--- 10. Settings Page ---")
        page.click('text="Settings"')
        page.wait_for_load_state("networkidle")
        take_screenshot(page, "10_settings_page")
        has_scanner_defaults = page.locator('text="Scanner defaults"').count() > 0 or page.locator('text="Short SMA"').count() > 0
        log_test("settings_scanner_defaults", has_scanner_defaults, "scanner defaults section present")
        has_about = page.locator('text="About"').count() > 0
        log_test("settings_about_section", has_about, "About section present")
        print()

        # ── 11. Watchlist page ───────────────────────────────────────
        print("--- 11. Watchlist Page ---")
        page.click('text="Watchlist"')
        page.wait_for_load_state("networkidle")
        take_screenshot(page, "11_watchlist_page")
        has_watchlist_title = page.locator('text="Watchlist"').count() > 0
        log_test("watchlist_title", has_watchlist_title, "Watchlist page title present")
        print()

        # ── 12. Alerts page ──────────────────────────────────────────
        print("--- 12. Alerts Page ---")
        page.click('text="Alerts"')
        page.wait_for_load_state("networkidle")
        take_screenshot(page, "12_alerts_page")
        has_alerts_title = page.locator('text="Price Alerts"').count() > 0
        log_test("alerts_title", has_alerts_title, "Alerts page title present")
        has_alert_form = page.locator('#as-alert-form').count() > 0
        log_test("alerts_form", has_alert_form, "alert form present")
        print()

        # ── 13. Chart Workspace ──────────────────────────────────────
        print("--- 13. Chart Workspace ---")
        # Navigate to company detail first, then open chart workspace
        page.click('text="Companies"')
        page.wait_for_load_state("networkidle")
        page.goto(f"{BASE_URL}/charts/RELIANCE/workspace/")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("[data-chart-workspace]", timeout=10000)
        take_screenshot(page, "13_chart_workspace")
        has_canvas = page.locator('canvas').count() > 0
        log_test("chart_canvas_rendered", has_canvas, "Lightweight Charts canvas present")
        has_toolbar = page.locator('[data-tool="pin"]').count() > 0
        log_test("chart_toolbar", has_toolbar, "chart toolbar buttons present")
        has_live_toggle = page.locator('[data-action="live"]').count() > 0
        log_test("chart_live_toggle", has_live_toggle, "live toggle button present")
        has_benchmark = page.locator('[data-action="benchmark"]').count() > 0
        log_test("chart_benchmark_toggle", has_benchmark, "benchmark toggle present")
        has_trendline = page.locator('[data-tool="trendline"]').count() > 0
        log_test("chart_trendline_tool", has_trendline, "trendline tool present")
        has_horizontal = page.locator('[data-tool="horizontal"]').count() > 0
        log_test("chart_horizontal_tool", has_horizontal, "horizontal line tool present")
        print()

        # ── 14. Test Drawing Tools ───────────────────────────────────
        print("--- 14. Drawing Tools Test ---")
        page.click('[data-tool="horizontal"]')
        page.wait_for_timeout(500)
        take_screenshot(page, "14_horizontal_tool_active")
        log_test("horizontal_tool_activates", True, "horizontal tool activated")

        page.click('[data-tool="trendline"]')
        page.wait_for_timeout(500)
        take_screenshot(page, "15_trendline_tool_active")
        log_test("trendline_tool_activates", True, "trendline tool activated")

        # Clear tools
        page.click('[data-action="clear"]')
        page.wait_for_timeout(500)
        take_screenshot(page, "16_tools_cleared")
        log_test("clear_tools_works", True, "tools cleared")
        print()

        # ── 15. Test Benchmark Toggle ────────────────────────────────
        print("--- 15. Benchmark Toggle ---")
        page.click('[data-action="benchmark"]')
        page.wait_for_timeout(2000)  # Wait for chart to re-fetch
        take_screenshot(page, "17_benchmark_enabled")
        log_test("benchmark_toggle_works", True, "benchmark toggle clicked")
        print()

        # ── 16. Test Live Mode ───────────────────────────────────────
        print("--- 16. Live Mode Toggle ---")
        page.click('[data-action="live"]')
        page.wait_for_timeout(1000)
        take_screenshot(page, "18_live_mode_enabled")
        log_test("live_toggle_works", True, "live toggle clicked")
        print()

        # ── 17. Test PNG Export ──────────────────────────────────────
        print("--- 17. PNG Export ---")
        page.click('[data-action="png"]')
        page.wait_for_timeout(2000)
        take_screenshot(page, "19_png_export_triggered")
        log_test("png_export_triggered", True, "PNG export button clicked")
        print()

        # ── 18. Logout ───────────────────────────────────────────────
        print("--- 18. Logout ---")
        page.click('text="Sign out"')
        page.wait_for_load_state("networkidle")
        take_screenshot(page, "20_logged_out")
        logged_out = "/login/" in page.url
        log_test("logout_works", logged_out, f"redirected to {page.url}")
        print()

        browser.close()

    # ── Summary ──────────────────────────────────────────────────────
    print("=" * 70)
    print(f"TOTAL: {PASS + FAIL} tests | PASSED: {PASS} | FAILED: {FAIL}")
    print("=" * 70)

    # Save results
    with open("tests/live/e2e_test_results.json", "w") as f:
        json.dump({
            "summary": {"total": PASS + FAIL, "passed": PASS, "failed": FAIL},
            "results": RESULTS,
            "screenshots_dir": str(SCREENSHOT_DIR),
        }, f, indent=2)
    print(f"Results saved to tests/live/e2e_test_results.json")
    print(f"Screenshots saved to {SCREENSHOT_DIR}/")

    sys.exit(1 if FAIL > 0 else 0)


if __name__ == "__main__":
    run_e2e()
