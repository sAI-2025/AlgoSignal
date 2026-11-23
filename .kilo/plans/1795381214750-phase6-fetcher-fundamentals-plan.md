# Phase 6 — Fetcher App & Fundamentals (implementation plan)

## 1. Goal

Build the `fetcher` app (schedules, runs, locking, retry, `run_scheduler` tick) and add
fundamentals collection to `market_data` (`CompanyMetrics` + `fundamentals` service +
yfinance `get_company_info`). This is the "WHEN/which batch" layer plus the daily
`Ticker.info` snapshot pipeline, per ARCHITECTURE §4.4, §6.3, §7, §8 and PRD §6 S6 / §8.

Signals remain research-only. No live order execution. Provider-specific code stays in
`market_data`; `fetcher` only orchestrates.

## 2. Assumptions (resolved, not re-asked)

- **"Next phase" = Phase 6.** Phases 1–4 are complete; Phase 5 (Historical OHLCV) code is
  present but the working tree is broken. This plan therefore starts with a **Phase 5
  finalization** step, then Phase 6.
- **Scope is backend + Django admin only.** The S6 "Market Data" HTML page, the
  `/api/v1/fetcher/*` REST endpoints, and live quotes/intraday are **out of scope** for this
  phase (see §12). They belong to later composition/API phases; admin is the verification
  surface now.
- **Django 6.1.3 / pandas 3.1.1 / yfinance 1.8.0** (already pinned). `CheckConstraint(...,
  condition=...)` is valid (Django ≥ 5.1).
- **SQLite now, PostgreSQL-portable.** No raw SQL, no SQLite-only features; ORM only; JSONField
  only for `FetchRun.errors` (small log).
- Default schedules are created idempotently at the start of `run_scheduler`
  (`ensure_default_schedules()`), not via a data migration, so a fresh DB works immediately.

## 3. Step 0 — Phase 5 finalization (prerequisite, must be green first)

These are real breakages in the current working tree; fix before any Phase 6 work:

1. `apps/companies/services/importer.py:1` — `wfrom __future__ import annotations` →
   `from __future__ import annotations` (stray `w` = SyntaxError; blocks all imports/tests).
2. `apps/market_data/tests/test_historical_data.py:53-57` — block is over-indented after the
   DataFrame literal; dedent the `from zoneinfo import ZoneInfo` + `monkeypatch.setattr(...)`
   block to function-body level (4 spaces).
3. Run the full gate and confirm green before continuing:
   `ruff check .` · `ruff format --check .` · `pytest` · `python manage.py makemigrations --check --dry-run`.

Do **not** proceed to §4 until this gate is clean.

## 4. Deliverables — file tree (NEW / CHANGED)

```
apps/market_data/
  services/providers/base.py                      CHANGED  add ProviderError taxonomy
  services/providers/yfinance_provider.py         CHANGED  implement get_company_info + error wrapping
  services/fundamentals_mapper.py                 NEW      pure unit-normalising mapper
  services/fundamentals.py                        NEW      fetch + upsert latest CompanyMetrics
  models.py                                       CHANGED  add CompanyMetrics
  migrations/0003_companymetrics.py               NEW
  admin.py                                        CHANGED  register CompanyMetrics
  tests/test_fundamentals_mapper.py               NEW
  tests/test_fundamentals_service.py              NEW
apps/fetcher/                                     NEW app
  __init__.py  apps.py  admin.py  models.py  views.py  urls.py
  migrations/__init__.py  migrations/0001_initial.py
  services/__init__.py
  services/retry.py                               NEW
  services/locking.py                             NEW
  services/scheduler.py                           NEW
  services/jobs/__init__.py                       NEW
  services/jobs/daily_candles.py                  NEW
  services/jobs/fundamentals.py                   NEW
  services/jobs/constituents.py                   NEW
  management/__init__.py
  management/commands/__init__.py
  management/commands/run_scheduler.py            NEW
  tests/__init__.py
  tests/test_models.py                            NEW
  tests/test_retry.py                             NEW
  tests/test_scheduler.py                         NEW
  tests/test_jobs.py                              NEW
config/settings/base.py                           CHANGED  add fetcher app + provider reliability settings
config/settings/test.py                           CHANGED  (only if cache override needed for cooldown tests)
tests/fixtures/yf_info_reliance.json              NEW      recorded Ticker.info sample
```

## 5. Task order

### 5.1 Provider error taxonomy — `services/providers/base.py` (CHANGED)

Add (subclass a common base, keep existing `Quote`, `ProviderHealth`, Protocol):

```python
class ProviderError(Exception): ...
class ProviderRateLimited(ProviderError): ...   # HTTP 429
class ProviderNoData(ProviderError): ...         # empty frame / delisted
class ProviderTransient(ProviderError): ...      # timeouts, 5xx
class ProviderFatal(ProviderError): ...          # auth/config
```

### 5.2 yfinance provider — `services/providers/yfinance_provider.py` (CHANGED)

- Implement `get_company_info(self, symbol: str) -> dict` returning the raw
  `yf.Ticker(symbol).info` mapping. Set a request timeout where the API allows; wrap
  exceptions:
  - ratelimit/429-ish → `ProviderRateLimited`
  - empty/`{}` → `ProviderNoData`
  - timeouts/connection/5xx → `ProviderTransient`
  - auth/config → `ProviderFatal`
- Keep `get_daily_candles` as-is (do not regress Phase 5). Leave `get_live_quote` /
  `get_intraday` as `NotImplementedError` (later phase).
- No retries inside the provider (retry lives in `fetcher.services.retry`).

### 5.3 Fundamentals mapper — `services/fundamentals_mapper.py` (NEW, pure)

`map_company_info(raw: dict) -> dict[str, Decimal | int | None]`

- Map the 22 PRD §8 keys → `CompanyMetrics` field names:
  `currentPrice→current_price`, `previousClose→previous_close`, `open→open_price`,
  `dayHigh→day_high`, `dayLow→day_low`, `fiftyTwoWeekHigh→fifty_two_week_high`,
  `fiftyTwoWeekLow→fifty_two_week_low`, `volume→volume`, `averageVolume→average_volume`,
  `marketCap→market_cap`, `trailingPE→trailing_pe`, `forwardPE→forward_pe`,
  `trailingEps→trailing_eps`, `bookValue→book_value`, `priceToBook→price_to_book`,
  `dividendYield→dividend_yield`, `returnOnEquity→return_on_equity`,
  `returnOnAssets→return_on_assets`, `profitMargins→profit_margins`,
  `debtToEquity→debt_to_equity`, `totalRevenue→total_revenue`, `freeCashflow→free_cashflow`,
  `netIncomeToCommon→net_income`.
- **Unit normalisation (the critical part):**
  - Percent-vs-fraction fields (`dividend_yield`, `return_on_equity`, `return_on_assets`,
    `profit_margins`): if `abs(value) <= 1.0` treat as a fraction and ×100; else assume already
    a percent. Record the rule in a docstring + test against the fixture.
  - `debt_to_equity`: keep as ratio (no ×100).
  - Money/ratios → `Decimal` (quantize money to 2 dp, ratios to 4 dp); volumes → `int`.
  - Missing/NaN/None → `None` (never 0).
- No Django/DB imports — pure, unit-testable.

### 5.4 CompanyMetrics model — `services/../models.py` (CHANGED)

`CompanyMetrics(TimeStampedModel)`:
- `company = OneToOneField(Company, on_delete=CASCADE, related_name="metrics")`
- Nullable `DecimalField`s: `current_price, previous_close, open_price, day_high, day_low,
  fifty_two_week_high, fifty_two_week_low` (max_digits=14, dp=4);
  `average_volume, volume` → `BigIntegerField(null=True)`;
  `market_cap, total_revenue, free_cashflow, net_income` (max_digits=20, dp=2);
  `trailing_pe, forward_pe, price_to_book, debt_to_equity` (max_digits=12, dp=4);
  `trailing_eps, book_value` (max_digits=14, dp=4);
  `dividend_yield, return_on_equity, return_on_assets, profit_margins`
  (max_digits=8, dp=4, stored as **percent**).
- Plus `currency = CharField(10, default="INR")`, `source = CharField(20, default="yfinance")`,
  `fetched_at = DateTimeField()`.
- Migration `0003_companymetrics.py`. Register in `admin.py` (read-only list display + search).

### 5.5 Fundamentals service — `services/fundamentals.py` (NEW)

- `fetch_and_store_metrics(company, *, provider=None, now=None) -> MetricsResult`
  - resolve provider symbol via the company's `Instrument` (NSE), fall back to
    `YFinanceProvider.to_provider_symbol(company.nse_code)`;
  - call `provider.get_company_info(symbol)` (wrapped by retry at the job layer, not here);
  - `payload = map_company_info(raw)`; `CompanyMetrics.objects.update_or_create(company=company,
    defaults={**payload, "source": provider.name, "fetched_at": now or timezone.now(),
    "currency": "INR"})`;
  - return `MetricsResult(company_id, updated: bool, missing_fields: list[str])`.
- `fetch_metrics_for_universe(*, batch_size, throttle, provider=None, now=None) -> BatchResult`
  - iterate active companies; **throttle** `throttle_seconds` + jitter ±0.5s between tickers,
    pause 10s after each batch of `batch_size` (default 10);
  - per-company failures captured as `{symbol, error_code, message}` and **do not abort** the
    batch; `BatchResult(total, success, failed, errors)`.
- Logging only (`logger.info/warning/error`), never `print`.

### 5.6 `fetcher` app scaffold (NEW)

- `apps.py` → `FetcherConfig(name="apps.fetcher")`; add `"apps.fetcher.apps.FetcherConfig"`
  to `INSTALLED_APPS` (after `market_data`).
- `models.py`:

**`FetchSchedule`** — `job_type` (choices `DAILY_CANDLES`/`FUNDAMENTALS`/`CONSTITUENTS_SYNC`,
**unique**), `enabled=Bool(True)`, `interval_hours=PositiveSmallInt(24)`,
`only_market_days=Bool(True)`, `earliest_time_ist=TimeField(null)`, `universe_index=Char(30,
default settings.INDEX_UNIVERSE)`, `batch_size=PositiveSmallInt(10)`,
`throttle_seconds=DecimalField(max_digits=6, dp=2, default=Decimal("2.0"))`,
`last_started_at`, `last_finished_at`, `next_run_at` (null), `last_status=Char(16, blank)`,
`updated_at=auto_now`. `CheckConstraint`s (use `condition=`): `interval_hours BETWEEN 1 AND 168`,
`batch_size > 0`, `throttle_seconds >= 1.0` (per PRD §11 for fundamentals; keep general ≥ 0 with a
stricter check noted, or set default 2.0 and validate in the form/serializer later).

**`FetchRun`** — `job_type` (same choices), `schedule=ForeignKey(FetchSchedule, null,
on_delete=SET_NULL, related_name="runs")`, `trigger` (`CRON`/`MANUAL`/`CLI`),
`status` (`RUNNING`/`SUCCESS`/`PARTIAL`/`FAILED`), `started_at`, `finished_at`, `heartbeat_at`,
`total_items`, `success_items`, `failed_items` (PositiveInt default 0), `rows_written`
(PositiveInt default 0), `errors=JSONField(default=list, blank=True)`, `message=Char(500, blank)`.
Indexes: `(job_type, -started_at)`, `(status)`.

- `admin.py` register both (schedules list with next_run/last_status; runs read-only with errors).
- `migrations/0001_initial.py`.

### 5.7 `fetcher/services/retry.py` (NEW)

`call_with_retry(func, *, retries=3, transient_delays=(5,15,45), rate_limit_delays=(30,60,120),
sleep=time.sleep, now=...) -> result`
- classify `ProviderTransient` → transient schedule; `ProviderRateLimited` → rate-limit schedule
  and increment the circuit-breaker streak; `ProviderNoData` → record, **no retry**;
  `ProviderFatal` → re-raise. Re-raise the last error after exhausting retries.
- `sleep`/`now` injectable so tests run instantly (no real delays).

### 5.8 `fetcher/services/locking.py` (NEW)

- `is_cooling_down(*, now, cache) -> bool` — reads cache key `provider:cooldown` (TTL 1800s).
- `register_rate_limit(*, cache)` — increments `provider:rate_limit_streak`; at 5, set
  `provider:cooldown` (1800s). `reset_rate_limit_streak(cache)` on a successful call.
- `has_active_run(job_type, *, now, heartbeat_timeout=15min) -> bool` — True if an
  `FetchRun(status=RUNNING, heartbeat_at > now-heartbeat_timeout)` exists. Stale RUNNING runs
  (older than timeout) are marked `FAILED` and ignored.
- `acquire(job_type, ...)`/`release(...)` wrap the above inside `transaction.atomic()` (portable;
  no `select_for_update` required on SQLite — guard with the RUNNING+heartbeat check).

### 5.9 `fetcher/services/scheduler.py` (NEW)

- `ensure_default_schedules()` — `get_or_create` the three `FetchSchedule` rows with the
  defaults from §8.2 (DAILY_CANDLES 24h/market-days/16:15 IST; FUNDAMENTALS 12h/any-day;
  CONSTITUENTS_SYNC 168h/any-day). Idempotent.
- `is_due(schedule, *, now) -> bool` — `enabled and next_run_at <= now and (not
  only_market_days or is_market_day(now)) and (earliest_time_ist is None or
  now_ist.time() >= earliest_time_ist)` (reuse `apps.core.market_hours`).
- `run_due_schedules(*, now=None, trigger="CRON") -> list[FetchRun]`:
  `ensure_default_schedules()` → for each enabled schedule: if `is_due` and not
  `has_active_run` and not `is_cooling_down` → open `FetchRun(RUNNING)` under
  `acquire`, dispatch to the job, finalize status/counts/errors, advance
  `next_run_at = now + interval_hours`, set `last_status`.
- `_dispatch(job_type, run)` maps to the job callables in §5.10; `run.heartbeat_at` refreshed
  per batch.

### 5.10 `fetcher/services/jobs/*` (NEW)

- `daily_candles.run(ctx)` — reuse `market_data.services.historical_data.backfill_company_history`
  (incremental; Phase 5). Counts rows → `FetchRun`.
- `fundamentals.run(ctx)` — call `market_data.services.fundamentals.fetch_metrics_for_universe`
  through `retry.call_with_retry`; update heartbeat per batch; classify PARTIAL when
  `failed>0 and success>0`.
- `constituents.run(ctx)` — call `companies.services.importer.run_constituent_import`; map its
  summary into counts + `errors` (this doubles as the import error log per §8.2).
- Each job returns a small `JobResult(total, success, failed, rows_written, errors, message)`.

### 5.11 `run_scheduler` command (NEW)

`python manage.py run_scheduler [--once] [--dry-run]`
- calls `scheduler.run_due_schedules()`; prints a one-line JSON summary (like
  `import_constituents`). Default single tick (cron invokes every ~10 min). No long-running loop.

### 5.12 Settings — `config/settings/base.py` (CHANGED)

- add `"apps.fetcher.apps.FetcherConfig"` to `INSTALLED_APPS`.
- add (with sane env-overridable defaults):
  `PROVIDER_MAX_RETRIES=3`, `PROVIDER_TRANSIENT_DELAYS=(5,15,45)`,
  `PROVIDER_RATE_LIMIT_DELAYS=(30,60,120)`, `PROVIDER_CIRCUIT_THRESHOLD=5`,
  `PROVIDER_COOLDOWN_SECONDS=1800`, `FETCH_HEARTBEAT_TIMEOUT_MIN=15`,
  `FETCH_SCHEDULER_DEFAULT_INTERVAL_HOURS` mapping optional. Reuse existing
  `PROVIDER_THROTTLE_SECONDS`.
- `.env.example`: document every new key (no secrets).

## 6. Data flow

```
cron (OS) ──▶ manage.py run_scheduler ──▶ scheduler.run_due_schedules
   └─ ensure_default_schedules → is_due? → acquire lock → FetchRun(RUNNING)
        └─ _dispatch(job_type)
             ├─ DAILY_CANDLES  → historical_data.backfill_company_history (market_data)
             ├─ FUNDAMENTALS   → retry.call_with_retry(→ fundamentals.fetch_metrics_for_universe
             │                     → yfinance.get_company_info → fundamentals_mapper → CompanyMetrics upsert)
             └─ CONSTITUENTS_SYNC → companies.importer.run_constituent_import
        └─ finalize FetchRun(SUCCESS/PARTIAL/FAILED) + next_run_at
```

Dependency direction preserved: `fetcher → market_data → companies → core`; `fetcher` holds no
provider code.

## 7. Key decisions

- **DTO isolation:** jobs call `market_data` service functions only; provider selection/creation
  stays inside `market_data` (jobs may pass `provider=` for tests).
- **Locking on SQLite:** RUNNING-run + fresh-heartbeat check (portable); documented as the
  SQLite-safe path, with `select_for_update` left for a later PostgreSQL hardening pass.
- **Circuit breaker state in cache** (`provider:cooldown`, `provider:rate_limit_streak`), not DB,
  so it self-clears; acceptable with LocMem per ARCHITECTURE §9 caveat.
- **Default schedules seeded in `run_scheduler`**, not a data migration, so first tick on a fresh
  DB self-heals.

## 8. Tests (offline; no live network)

- `tests/fixtures/yf_info_reliance.json` — representative recorded `Ticker.info` payload
  (include at least one fraction-form percent field, e.g. `dividendYield: 0.0042`,
  `returnOnEquity: 0.14`, and `debtToEquity: 2.1` as a ratio) so normalisation is proven.
- `test_fundamentals_mapper.py` — fixture → expected dict; percent×100 rule; missing→None;
  money Decimal quantize; `debt_to_equity` unchanged.
- `test_fundamentals_service.py` — `monkeypatch` `YFinanceProvider.get_company_info` to return
  the fixture; assert `CompanyMetrics` upserted once, second call updates not duplicates;
  failing ticker recorded, batch continues.
- `test_retry.py` — inject `sleep` no-op; transient retried 3×; rate-limit schedule; NoData not
  retried; circuit breaker trips at 5 (via `locking`).
- `test_models.py` — schedule `CheckConstraint`s reject `interval_hours=0/169`; unique job_type;
  run defaults.
- `test_scheduler.py` (freezegun) — `is_due` gating (not due before `next_run_at`, market-day
  gate, earliest-time gate); no overlap when a RUNNING run is fresh; stale RUNNING → FAILED and
  re-runnable; `next_run_at` advances by interval; cooling-down skips with PARTIAL/"cooling down".

## 9. Out of scope (explicit)

- S6 "Market Data" HTML page, `/api/v1/fetcher/*` REST endpoints (later composition/API phase).
- Live quotes/intraday, `kite_client` implementation (later).
- Celery/Redis (only when ARCHITECTURE §20 criteria met).
- `earliest_time_ist` UI editing beyond admin.

## 10. Validation plan (must all pass before handoff)

```
ruff check .
ruff format --check .
pytest -q
python manage.py makemigrations --check --dry-run
python manage.py migrate            # apply 0003 + fetcher 0001 on a scratch DB
python manage.py run_scheduler --dry-run   # seeds defaults, prints summary, writes no data
```
Manual smoke: Django admin → FetchSchedule (3 rows), FetchRun empty until a real
`run_scheduler`/`run-now`; CompanyMetrics absent until a fundamentals job runs.

## 11. Risks & mitigations

- **yfinance schema/units drift** → mapper isolated + fixture test; note "verify against a fresh
  `Ticker.info`" before trusting production values.
- **Rate limits** → throttle + retry/backoff + circuit breaker mandatory (ARCHITECTURE §7.2).
- **SQLite single-writer** → short transactions, single `run_scheduler` tick, heartbeat guard.
- **LocMem cache per worker** → acceptable for v1 (documented); swap to Redis when scaling.

## 12. Definition of Done

- [ ] Step 0 fixes applied; full gate green on the pre-existing suite.
- [ ] `fetcher` app + `CompanyMetrics` migrated; `makemigrations --check` clean.
- [ ] `run_scheduler` seeds default schedules and executes due jobs without overlap.
- [ ] Fundamentals mapper normalises units per fixture; service upserts one snapshot/company.
- [ ] Retry/backoff + circuit breaker behave per §5.7–5.8 and are unit-tested.
- [ ] `ruff`, `pytest`, `makemigrations --check` all green; no `print` in app code.