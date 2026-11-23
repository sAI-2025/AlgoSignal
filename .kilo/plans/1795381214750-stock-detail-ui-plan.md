# AlgoSignal — Stock Detail UI Enhancement Plan

**Plan file:** `.kilo/plans/1795381214750-stock-detail-ui-plan.md`
**Target:** `C:\Users\chskc\Desktop\AlgoSignal`
**Status:** Ready for implementation

---

## Decisions Resolved

| Decision | Resolution | Rationale |
|----------|-----------|-----------|
| Listing date source | Try yfinance `info.firstTradeDateEpochUtc` → fallback to earliest `HistoricalPrice.candle_date` → fallback to `today - years` | No model change needed (karpathy: simplicity first). Fixture lacks `firstTradeDateEpochUtc`, so fallback chain is essential. |
| Refresh scope | Metrics only (`CompanyMetrics`) | Keeps scope tight; chart candles already have their own refresh path via backfill. |
| Null/empty metric display | Show "Not available" with per-metric refresh action | Better than bare "—"; gives user a clear path to retry. |
| Detail page URL | Keep `/explorer/<nse_code>/` | Page already exists with all tabs; no new routing needed. |
| Refresh mechanism | New `POST /api/v1/companies/<nse_code>/refresh-metrics/` endpoint | Separate from read-only metrics GET; follows DRF pattern used elsewhere. |

---

## Current State (Explorer Detail Page)

**URL:** `/explorer/<nse_code>/` (`apps/explorer/views.py:company_detail`)
**Tabs:** overview, chart, fundamentals, signals, history
**Service:** `apps/explorer/services/company_view.py:build_company_detail`
**Metric fields (8 required):** Market Cap, P/E (Trailing), Revenue, Net Profit, ROE, Debt/Equity, Dividend Yield, 52-week High — all in `CompanyMetrics` model, all nullable
**Null display:** `"—"` in `_tab_overview.html:9` and `_tab_fundamentals.html:20`
**Refresh:** None exists on detail page
**Backfill:** `backfill_company_history(instrument, years=1)` — fixed lookback, no listing date awareness

---

## Task Plan

### Task 1: Dynamic Listing Date Detection in Backfill

**Goal:** When backfilling a company with < 1 year of data, start from the listing date instead of `today - 1 year`.

**Files to change:**
- `apps/market_data/services/historical_data.py`
  - Modify `backfill_company_history()` to accept an optional `listing_date` param
  - Add `_resolve_start_date(instrument, years, listing_date)` helper:
    1. If `listing_date` provided → start = `listing_date`
    2. Else if candles exist → start = `earliest_candle_date + 1 day` (incremental)
    3. Else → start = `today - 365 * years` (current fallback)
- `apps/companies/views.py` (`add_company`)
  - After creating Instrument, attempt to read `firstTradeDateEpochUtc` from yfinance info; store it (temporarily in a variable, pass to backfill)
  - Pass detected listing date to `backfill_company_history()`
- `apps/companies/api/views.py` (`company_import`)
  - Same: detect listing date per company during import backfill loop

**Verification:**
- `backfill_company_history` uses listing date when available
- `_resolve_start_date` falls back correctly through all 3 tiers
- No model migration needed (no `listing_date` field on Company)

### Task 2: Refresh Metrics API Endpoint

**Goal:** A POST endpoint that re-fetches `CompanyMetrics` for a single company and returns the updated snapshot.

**Files to change:**
- `apps/companies/api/views.py`
  - Add `company_refresh_metrics(request, nse_code)` view
  - `@api_view(["POST"])`, `@permission_classes([IsAuthenticated])`, throttle class
  - Calls `fetch_and_store_metrics(company)` from `apps.market_data.services.fundamentals`
  - Returns `CompanyMetricsSerializer` data or 404/502 on provider error
- `apps/companies/api/urls.py`
  - Add `path("<str:nse_code>/refresh-metrics/", views.company_refresh_metrics, name="company_refresh_metrics")`

**Verification:**
- POST returns 200 with updated metrics on success
- POST returns 404 if company not found
- POST returns 502 if provider fails
- Throttling applied (prevents yfinance rate-limit abuse)

### Task 3: Refresh Button + Loading States on Detail Page

**Goal:** Every stock detail page tab has a functional refresh button with visual feedback.

**Files to change:**
- `templates/explorer/company_detail.html`
  - Add refresh button in the header action area (next to "Open chart workspace")
  - Button: `data-action="refresh-metrics"`, shows spinner during refresh
- `static/css/algosignal.css`
  - `.as-refresh-btn--loading` state (opacity, spinner)
  - `.as-metric--loading` skeleton style for metric cards
  - `.as-metric--stale` / `.as-metric--fresh` color indicators
- `static/js/pages/stock-detail.js` (new)
  - `refreshMetrics(symbol)` — POST to `/api/v1/companies/<nse_code>/refresh-metrics/`
  - Per-metric-group loading skeleton during fetch
  - Toast on success/error (reuse existing toast pattern from dashboard)
  - Re-render metrics section after successful fetch (or full page reload as fallback)

**Verification:**
- Refresh button visible on all tabs (header is shared)
- Clicking shows spinner on button, disables it during fetch
- Toast appears on success ("Metrics refreshed") or error ("Refresh failed")
- Button re-enabled after fetch completes

### Task 4: Financial Metrics Overview Redesign

**Goal:** Modernize metric card layout, handle loading/error/empty states, show "Not available" with per-metric refresh.

**Files to change:**
- `templates/explorer/_tab_overview.html`
  - Replace simple cards with redesigned metric cards:
    - Category badge (Valuation, Profitability, Financial Health, Trading)
    - Value + change indicator (where applicable)
    - "Not available" state with mini refresh icon
    - Skeletons during loading
- `templates/explorer/_tab_fundamentals.html`
  - Same redesign applied to table rows: "Not available" instead of "—"
  - Per-row refresh icon for null values
- `static/css/algosignal.css`
  - `.as-metric-card` — distinct card styling with category color accents
  - `.as-metric-value` — typography hierarchy
  - `.as-metric--empty` — muted "Not available" styling
  - `.as-metric--refreshing` — spinner overlay on individual metric
  - `.as-skeleton` — pulse animation for loading state
  - Category color palette (4–6 named hex values derived from existing `--as-*` vars)

**Verification:**
- All 8 required metrics render as cards on overview
- Null values show "Not available" not "—"
- Loading skeleton shows during refresh
- Category badges use distinctive colors, not Bootstrap defaults
- No templated Bootstrap card defaults remain

### Task 5: Validation & Tests

**Goal:** Ensure no regressions and new behavior is tested.

**Files to change:**
- `apps/companies/tests/test_companies.py` — add test for `company_refresh_metrics` endpoint (200, 404, 502)
- `apps/explorer/tests/test_explorer.py` — add test for detail page with null metrics (shows "Not available")
- `apps/market_data/tests/test_historical_data.py` — add test for `_resolve_start_date` with listing date

**Verification:**
- `pytest` — 263+ tests pass
- `ruff check apps config` — clean

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| yfinance rate limits on per-company refresh | Throttle the new endpoint; show 502 gracefully; user can retry |
| `firstTradeDateEpochUtc` missing from yfinance info (per fixture) | Fallback chain handles it: earliest candle → today-years |
| Refresh button triggers full page reload vs partial update | AJAX preferred; full reload fallback is acceptable per karpathy (simplicity) |
| Multiple rapid refresh clicks | Button disabled during fetch; toast prevents duplicate state confusion |

---

## Validation Checklist (Definition of Done)

- [ ] Backfill uses listing date when available (3-tier fallback verified)
- [ ] `POST /api/v1/companies/<nse_code>/refresh-metrics/` returns 200/404/502 correctly
- [ ] Detail page refresh button shows spinner + toast, disables during fetch
- [ ] Null metrics show "Not available" with mini refresh icon (not "—")
- [ ] Overview cards have category badges, not plain Bootstrap defaults
- [ ] Loading skeletons appear during metrics refresh
- [ ] All 263 existing pytest tests still pass
- [ ] `ruff check apps config` clean
- [ ] Dark theme works for all new UI elements (CSS vars used consistently)

---

## Implementation Order

1. Task 1 (Dynamic listing date in backfill)
2. Task 2 (Refresh metrics API endpoint)
3. Task 3 (Refresh button + loading states on detail page)
4. Task 4 (Metrics overview redesign)
5. Task 5 (Tests + final verification)

---

## Open Questions

None — all three core design decisions resolved with user input.
