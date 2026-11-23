# AlgoSignal

AlgoSignal is a modular Django monolith that scans Nifty 100 stocks for SMA-crossover
signals, ranks top performers, explains each company, and shows everything on interactive
charts.

> Signals are **research indicators, not trading recommendations**. This project does
> **not** place orders or execute trades.

## Quick Start (under 15 minutes)

### Windows PowerShell

1. Create and activate venv:
   - `python -m venv .venv`
   - `.\.venv\Scripts\Activate.ps1`
2. Install dependencies:
   - `pip install -r requirements/dev.txt`
3. Create env file:
   - `Copy-Item .env.example .env`
4. Run migrations:
   - `python manage.py migrate`
5. Create superuser:
   - `python manage.py createsuperuser`
6. Start server:
   - `python manage.py runserver`

### Linux/macOS

1. Create and activate venv:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
2. Install dependencies:
   - `pip install -r requirements/dev.txt`
3. Create env file:
   - `cp .env.example .env`
4. Run migrations:
   - `python manage.py migrate`
5. Create superuser:
   - `python manage.py createsuperuser`
6. Start server:
   - `python manage.py runserver`

## Apps

| App | Responsibility |
|---|---|
| `core` | Health check, market-hours logic |
| `companies` | Company universe, directory (S2) |
| `market_data` | Providers (yfinance), historical OHLCV, fundamentals |
| `fetcher` | Schedules, runs, locking, retry, circuit breaker |
| `indicators` | Pure indicator maths (SMA) + registry |
| `signals` | Crossover detection + idempotent persistence |
| `scanner` | Scan orchestration, scanner settings, Signals page |
| `analytics` | Returns windows, top performers, market overview, sector stats |
| `visualization` | Chart payload API + canvas chart workspace |
| `explorer` | Company search + company detail (tabs) |
| `dashboard` | Dashboard + settings composition |

## Verification

- Run tests: `pytest`
- Lint: `ruff check apps config`
- Format check: `ruff format --check .`
- Migration check: `python manage.py makemigrations --check --dry-run`
- Health check: open `/health/`
- Import constituents: `python manage.py import_constituents --index-code NIFTY100`
- Map instruments: `python manage.py map_instruments --exchange NSE`
- Fetch historical candles: `python manage.py fetch_historical --years 3`

## Notes

- Settings are split in `config/settings/`.
- `apps/` is added to `sys.path` in base settings so app modules are cleanly importable.
- Bootstrap 5.3, Bootstrap Icons and TradingView Lightweight Charts v5 are vendored in
  `static/vendor/` to avoid runtime CDN dependencies (Lightweight Charts is Apache-2.0;
  see `static/vendor/lightweight-charts/NOTICE.txt`).
- Chart SMA is computed on the unadjusted close; returns use adjusted close when
  available, else unadjusted with a visible note.
- Completed daily candles only are stored; live data is never persisted.