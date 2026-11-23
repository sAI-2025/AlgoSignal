# AlgoSignal — Comprehensive Automated Testing Strategy

**Project:** AlgoSignal — Nifty Stock SMA-Crossover Scanner  
**Test Engineer:** Senior Automation Test Engineer (10+ years)  
**Date:** 2026-11-23  
**Environment:** Local Django dev server (`127.0.0.1:8000`), Django 6.1.3, DRF, Python 3.13.5

---

## 1. Test Scope & Coverage Areas

| Area | Coverage | Tools |
|------|----------|-------|
| **API Endpoint Testing** | All 22+ `/api/v1/` endpoints, status codes, schema, auth, validation, error envelopes | `requests`, `pytest` |
| **Data Integrity & Logic** | SMA/EMA/RSI/MACD/Bollinger calculations, scanner crossover detection, advancers/decliners | `pytest` + hand-calculated expected values |
| **Database Validation** | CRUD persistence, ORM consistency, seeded data integrity | Django test DB + `pytest` |
| **Environment Coverage** | Local dev (`localhost:8000`) + staging/prod readiness checks | `requests` + config validation |
| **End-to-End Workflows** | Add company → fetch history → scan → view signals → chart | Playwright (browser) |
| **Web UI Testing** | Page rendering, chart rendering, buttons, forms, navigation | Playwright + screenshots |

---

## 2. API Endpoint Inventory

### Public (no auth)
| # | Method | Endpoint | Expected Status |
|---|--------|----------|-----------------|
| 1 | GET | `/health/` | 200 |

### Authenticated (all `/api/v1/` endpoints require login)
| # | Method | Endpoint | Auth | Expected Status |
|---|--------|----------|------|-----------------|
| 2 | GET | `/api/v1/companies/` | user | 200 |
| 3 | GET | `/api/v1/companies/sectors/` | user | 200 |
| 4 | GET | `/api/v1/companies/<code>/` | user | 200 |
| 5 | GET | `/api/v1/companies/<code>/metrics/` | user | 200 / 404 |
| 6 | POST | `/api/v1/companies/import/` | staff | 200 / 502 |
| 7 | POST | `/api/v1/scanner/run/` | user | 200 |
| 8 | GET | `/api/v1/scanner/settings/` | user | 200 |
| 9 | PUT | `/api/v1/scanner/settings/` | staff | 200 |
| 10 | GET | `/api/v1/scanner/signals/` | user | 200 |
| 11 | GET | `/api/v1/analytics/top-performers/` | user | 200 |
| 12 | GET | `/api/v1/analytics/market-overview/` | user | 200 |
| 13 | GET | `/api/v1/analytics/sectors/` | user | 200 |
| 14 | GET | `/api/v1/explorer/search/` | user | 200 |
| 15 | GET | `/api/v1/dashboard/summary/` | user | 200 |
| 16 | GET | `/api/v1/fetcher/schedules/` | user | 200 |
| 17 | PUT | `/api/v1/fetcher/schedules/<id>/` | staff | 200 |
| 18 | POST | `/api/v1/fetcher/schedules/<id>/run-now/` | staff | 200 / 409 |
| 19 | POST | `/api/v1/fetcher/backfill/` | staff | 200 / 400 |
| 20 | GET | `/api/v1/fetcher/runs/` | user | 200 |
| 21 | GET | `/api/v1/fetcher/runs/<id>/` | user | 200 / 404 |
| 22 | GET | `/api/v1/fetcher/coverage/` | user | 200 |
| 23 | GET | `/api/v1/live/quote/<code>/` | user | 200 / 404 |
| 24 | GET | `/api/v1/live/quotes/` | user | 200 |
| 25 | GET | `/api/v1/live/intraday/<code>/` | user | 200 |
| 26 | POST | `/api/v1/live/refresh-metrics/<code>/` | user | 200 / 429 / 502 |
| 27 | GET | `/api/v1/charts/<code>/` | user | 200 |
| 28 | GET | `/api/v1/market-data/coverage/` | user | 200 |

### Auth failures (expected 403)
| # | Method | Endpoint |
|---|--------|----------|
| A1 | GET | Any `/api/v1/` endpoint without auth |
| A2 | POST | `/api/v1/scanner/run/` without staff |

### Validation failures (expected 400/422)
| # | Method | Endpoint | Invalid Input |
|---|--------|----------|---------------|
| V1 | GET | `/api/v1/charts/<code>/` | `sma=7,abc` |
| V2 | GET | `/api/v1/charts/<code>/` | `sma=9999` |
| V3 | GET | `/api/v1/charts/<code>/` | `before=not-a-date` |
| V4 | POST | `/api/v1/scanner/run/` | `short_period=0` |
| V5 | POST | `/api/v1/analytics/top-performers/` | `period=INVALID` |
| V6 | POST | `/api/v1/fetcher/backfill/` | `years=99` |

---

## 3. Test Environment Strategy

| Environment | URL | Purpose | Auth |
|-------------|-----|---------|------|
| **Local Dev** | `http://127.0.0.1:8000` | Primary test target, full API coverage | Django session |
| **Staging** | `https://staging.algosignal.local` | Pre-production validation | Same |
| **Production** | `https://api.algosignal.com` | Smoke test only (read-only GET) | Same |

**CI/CD Integration:** Tests run on every push to `main` branch using GitHub Actions or Azure Pipelines.

---

## 4. Test Tools & Stack

| Purpose | Tool | Version | Why |
|---------|------|---------|-----|
| API testing | Python `requests` | 2.34.2 | Lightweight, no build step |
| E2E browser testing | Playwright | latest | Screenshots, DOM inspection, chart canvas verification |
| Unit/integration | pytest | 9.2.0 | Django integration, fast |
| Linting | ruff | latest | Code quality |
| Screenshot capture | Playwright | latest | Visual regression, chart rendering proof |

---

## 5. Step-by-Step Test Execution Plan

### Phase 1: Prerequisites
1. Start Django dev server on port 8000
2. Create test user (`user: sai`, `PWD: 1234`) and staff user
3. Seed test data (companies, candles, metrics, signals)
4. Verify server is running via `/health/`

### Phase 2: API Endpoint Tests
For each endpoint:
1. Send unauthenticated request → expect 403
2. Send authenticated request as non-staff → expect 200 (or 403 for staff-only)
3. Send invalid input → expect 400/422 with error envelope
4. Validate response JSON schema
5. Log results + capture any error details

### Phase 3: Data Integrity & Logic
1. Seed known price sequence → verify SMA values match hand calculation
2. Seed crossover pattern → verify scanner detects BULLISH/BEARISH correctly
3. Verify advancers/decliners match last-two-close comparison
4. Verify coverage counts match seeded companies/candles

### Phase 4: Database Validation
1. Add company via API → verify DB row exists
2. Fetch company detail → verify matches stored data
3. Update scanner settings → verify persisted
4. Run backfill → verify FetchRun created

### Phase 5: E2E Web UI (Playwright)
1. Navigate to login page → login as `sai`
2. Verify dashboard loads with KPI cards
3. Navigate to Companies page → verify table renders
4. Navigate to Chart Workspace → verify Lightweight Charts canvas renders
5. Test drawing tools (trendline, horizontal line)
6. Test benchmark toggle
7. Test live mode toggle
8. Take screenshots at each step

---

## 6. Expected Results & Pass/Fail Criteria

| Check | Pass Condition |
|-------|---------------|
| Health endpoint | Returns 200, `{"status":"ok","db":"ok"}` |
| API auth | Unauthenticated → 403 with error envelope |
| API success | Authenticated → 200 with valid JSON |
| Validation | Invalid input → 400/422 with `{"error":{"code","message"}}` |
| Staff-only | Non-staff → 403 |
| Chart render | Canvas element present, data series visible |
| SMA calc | Server values match hand calculation within 0.001 |
| Crossover | Bullish/Bearish signals detected correctly |
| DB persistence | Created/updated records retrievable via API |

---

## 7. Known Issues / Technical Debt

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Shared throttle bucket across all custom throttle classes | Tests may interfere | Clear cache between tests |
| DRF returns 403 (not 302) for unauthenticated API | Tests must expect 403 | Update test assertions |
| `live_refresh_metrics` not staff-only | Authenticated users can trigger | Document as known behavior |
| Two `/coverage/` endpoints (duplicate) | Confusing API surface | Document both |
| `chartWorkspace.js` `apiBase` unused | Chart always hits `/api/v1/charts/` | Document as dead config |
