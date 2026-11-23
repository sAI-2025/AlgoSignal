# AlgoSignal — Dashboard & Chart UX Enhancement Plan

**Plan file:** `.kilo/plans/1795381214750-dashboard-chart-ux-plan.md`
**Target:** `C:\Users\chskc\Desktop\AlgoSignal`
**Status:** Ready for implementation

---

## Current State Assessment

| Feature | Status | Notes |
|---------|--------|-------|
| Dashboard refresh button | Exists (`data-action="refresh-dashboard"`) | Calls `initDashboard()` but no loading spinner, no toast feedback |
| Add Stock form | Exists | Basic validation (symbol + name only); no financial metrics section |
| Chart "1Y" timeframe | Exists | `resolve_range("1Y", end)` returns `end - 1 year` |
| Indicator buttons (RSI, MACD, Bollinger, Vol SMA) | Exists in chart template | Already wired to `toggleIndicator()` |
| Crosshair tooltip | Exists (`attachCrosshairInfo`) | Shows OHLC + SMA only, not RSI/MACD/Bollinger values |
| Lightweight Charts rendering | Exists | `createChart()` with candlestick/line/area series |
| CompanyMetrics model | Exists | Has all 8 required financial metric fields |
| Auto-backfill on add | Exists (just fixed) | `backfill_company_history(instrument, years=1)` called on add |

---

## Guiding Principles

- **Karpathy Guidelines:** Minimum code, surgical changes, goal-driven verification, simplicity first
- **Frontend Design:** Distinctive identity, no templated Bootstrap defaults, deliberate palette/type choices, restraint — one signature element max

---

## Task Plan

### Task 1: Dashboard Refresh with Loading State

**Goal:** Clicking "Refresh" shows a spinner, disables the button, fetches latest data, shows toast on success/error, re-enables button.

**Files to change:**
- `static/js/pages/dashboard.js` — add `refreshDashboard()` with loading state + toast
- `templates/dashboard/dashboard.html` — add toast container, spinner markup, disable button during refresh
- `static/css/algosignal.css` — add `.as-spinner`, `.as-toast` styles

**Verification:**
- Clicking refresh shows spinner overlay on button
- Button is `disabled` during fetch, re-enabled after
- Toast appears on success ("Dashboard refreshed") or error ("Couldn't refresh dashboard")
- KPI cards update with fresh data

**Decision:** Auto-fetch on page load remains; manual refresh is API-only (no full page reload).

---

### Task 2: Add Stock Form — Financial Metrics Section

**Goal:** When user enters an NSE symbol and tabs out / blurs, auto-fetch financial metrics from yfinance, show spinner while loading, display metrics in a structured section below the form.

**Metrics to display:** Market Cap, P/E (Trailing), Revenue, Net Profit, ROE, Debt/Equity, Dividend Yield, 52-Week High.

**Files to change:**
- `templates/companies/add_company.html` — add metrics section (hidden by default), spinner, metric cards
- `static/js/pages/add-company.js` (new) — fetch metrics on symbol blur, populate section
- `apps/companies/views.py` — add `GET /api/v1/companies/metrics/<nse_code>/` endpoint or reuse existing
- `static/css/algosignal.css` — metric card styles, spinner animation

**Decision:** Auto-fetch on `blur` of the symbol field (not on every keystroke). Show spinner in the metrics section during fetch. If fetch fails, show muted "Metrics unavailable" message.

**Validation additions (Task 4):**
- NSE symbol: uppercase, 1-20 chars, alphanumeric + hyphen only
- Company name: required, 2-200 chars
- Sector: optional, from predefined list (Energy, Financial Services, IT, Auto, Pharma, FMCG, Metals, Chemicals, Cement, Power, Telecom, Realty, Consumer Durables, Media, Textiles)

---

### Task 3: Chart Crosshair Tooltip — All Active Indicators

**Goal:** Hovering over a chart point shows a pointer-based tooltip with OHLC + value of every active indicator (SMA, EMA, RSI, MACD, Bollinger, Volume SMA, Benchmark).

**Files to change:**
- `static/visualization/js/crosshairTooltip.js` — extend `render()` to iterate all series handles, not just SMA
- `static/visualization/js/chartWorkspace.js` — pass all indicator series handles to `syncInfoPlugin()`
- `static/css/algosignal.css` — tooltip styling (distinctive, not Bootstrap-default)

**Decision:** Enhance existing `attachCrosshairInfo` rather than replace. Add a visual crosshair (vertical line + highlight) that follows cursor.

---

### Task 4: Strict Validation for Add Stock Metadata

**Goal:** Prevent invalid data entry at the form level and API level.

**Files to change:**
- `apps/companies/views.py` — add server-side validation for symbol format, name length, sector from allowed list
- `templates/companies/add_company.html` — client-side pattern attribute on inputs, inline validation messages
- `apps/companies/selectors.py` — optional: add `validate_company_data()` helper

**Validation rules:**
- `nse_code`: required, `^[A-Z][A-Z0-9-]{0,19}$`, must not already exist (unless updating)
- `name`: required, 2-200 chars
- `sector`: optional, must be from allowed list if provided
- `industry`: optional, 2-150 chars

---

### Task 5: Performance Optimization — Chart Rendering

**Goal:** Smooth rendering for large datasets, debounce rapid timeframe/indicator changes.

**Files to change:**
- `static/js/pages/dashboard.js` — debounce `initDashboard()` refresh calls (300ms)
- `static/visualization/js/chartWorkspace.js` — debounce `setState()` calls that trigger re-render (200ms)
- `static/visualization/js/dataAdapter.js` — cache hit ratio already good; add `force` bypass only on explicit user action

**Decision:** No Web Workers needed (datasets < 5000 bars). Debounce is sufficient.

---

### Task 6: Chart Toolbar Usability Redesign

**Goal:** Reorganize the crowded chart toolbar into logical, collapsible groups so tools are discoverable.

**Files to change:**
- `templates/visualization/_chart_workspace.html` — regroup buttons into collapsible sections (Timeframe, Series, Indicators, Tools, Export)
- `static/css/algosignal.css` — accordion/collapse styles, group styling

**Decision:** Use native `<details>/<summary>` for collapsible groups (no JS dependency, accessible by default).

---

### Task 7: Interface Smoothness — Button & Interactive Element Styling

**Goal:** Distinctive button states, hover effects, focus rings, disabled states — not Bootstrap defaults.

**Files to change:**
- `static/css/algosignal.css` — button styles, focus-visible rings, active states, disabled opacity

**Decision:** One signature element: a subtle gradient accent on primary buttons + consistent focus-visible ring.

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| yfinance rate limits on auto-fetch | Cache metrics per symbol for 24h; show stale data rather than blocking |
| Crosshair tooltip flicker on rapid moves | `requestAnimationFrame` already used; keep it |
| Toolbar redesign breaks keyboard shortcuts | Preserve `data-tool`, `data-tf`, `data-indicator` attributes |
| Metrics fetch fails silently | Show muted fallback, don't block form submission |

---

## Validation Checklist (Definition of Done)

- [ ] Dashboard refresh shows spinner + toast, button disabled during fetch
- [ ] Add Stock symbol blur auto-fetches metrics with spinner
- [ ] Add Stock form rejects invalid symbols (lowercase, special chars, too long)
- [ ] Chart crosshair shows RSI/MACD/Bollinger values when those indicators are active
- [ ] Chart "1Y" fetches exactly 1 year of data back from last candle
- [ ] Chart toolbar is organized into collapsible groups
- [ ] All 263 existing pytest tests still pass
- [ ] `ruff check` passes with no new issues
- [ ] Dark theme works for all new UI elements

---

## Open Questions (for user confirmation)

1. **Auto-fetch metrics on Add Stock:** Should metrics fetch happen on symbol `blur` (recommended) or only on form submit?
2. **Crosshair style:** Should the crosshair be a full vertical line across all panes, or just a tooltip bubble near the cursor? (Recommended: full vertical line + tooltip bubble)
3. **Sector list:** Should sectors be a free-text field or a `<select>` with predefined options? (Recommended: predefined `<select>` with "Other" option)

---

## Implementation Order

1. Task 1 (Dashboard refresh) — quick win, isolated
2. Task 4 (Validation) — foundation for Task 2
3. Task 2 (Add Stock metrics) — depends on Task 4
4. Task 3 (Crosshair tooltip) — chart UX improvement
5. Task 5 (Performance) — debouncing, caching
6. Task 6 (Toolbar redesign) — template restructure
7. Task 7 (Button styling) — final polish

---

## Notes

- The `backfill_company_history` fix from the previous session (MultiIndex column flattening in `yfinance_provider.py`) must remain in place for Task 2's auto-fetch to work.
- No new Django models needed; `CompanyMetrics` already has all required fields.
- No new API endpoints strictly needed; existing `company_metrics` view can serve the Add Stock fetch.