from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from apps.companies.models import Company
from apps.market_data.models import HistoricalPrice
from apps.scanner.services.params import ScannerParams
from apps.scanner.services.scanner import run
from apps.signals.models import TradingSignal

IST = ZoneInfo("Asia/Kolkata")
AS_OF = datetime(2026, 11, 10, 16, 0, tzinfo=IST)
START = date(2026, 11, 1)


def _company_with_closes(code: str, closes: list[float], *, start: date = START) -> Company:
    company = Company.objects.create(company_name=code, nse_code=code)
    for offset, close in enumerate(closes):
        HistoricalPrice.objects.create(
            company=company,
            candle_date=start + timedelta(days=offset),
            open=close,
            high=close,
            low=close,
            close=close,
            adj_close=close,
            volume=1000,
        )
    return company


@pytest.mark.django_db
def test_scan_detects_and_persists_crossovers() -> None:
    # Hand-tuned series (short=2/long=3): bearish cross at 11-05, bullish cross at 11-08.
    company = _company_with_closes("INFY", [10, 11, 12, 11, 10, 9, 10, 11, 12])

    params = ScannerParams(short_period=2, long_period=3, lookback_days=10, max_stocks=25)
    result = run(params, as_of=AS_OF)

    # One result row per company (its latest crossover).
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.nse_code == "INFY"
    assert row.signal_type == "BULLISH"
    assert row.crossover_date == date(2026, 11, 8)
    # Both eligible crossovers in the lookback window are persisted.
    assert TradingSignal.objects.filter(company=company).count() == 2


@pytest.mark.django_db
def test_scan_ranks_by_date_desc_then_strength() -> None:
    # Two companies with crossovers on different dates.
    _company_with_closes("AAA", [10, 11, 12, 11, 10, 9, 10, 11, 12])  # bullish 11-08
    _company_with_closes("BBB", [10, 9, 8, 9, 10, 11, 10, 9, 8], start=date(2026, 11, 3))
    # bearish crossover on 11-09 for BBB

    params = ScannerParams(short_period=2, long_period=3, lookback_days=10, max_stocks=25)
    result = run(params, as_of=AS_OF)

    dates = [row.crossover_date for row in result.rows]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.django_db
def test_scan_lookback_excludes_old_crossovers() -> None:
    # Crossover at 11-08 but lookback=1 means only the last bar (11-09) is eligible.
    _company_with_closes("OLD", [10, 11, 12, 11, 10, 9, 10, 11, 12])

    params = ScannerParams(short_period=2, long_period=3, lookback_days=1, max_stocks=25)
    result = run(params, as_of=AS_OF)

    assert result.rows == []


@pytest.mark.django_db
def test_scan_max_stocks_limits_companies() -> None:
    for code in ("AAA", "BBB", "CCC"):
        _company_with_closes(code, [10, 11, 12, 11, 10, 9, 10, 11, 12])

    params = ScannerParams(short_period=2, long_period=3, lookback_days=10, max_stocks=2)
    result = run(params, as_of=AS_OF)

    assert len(result.rows) == 2


@pytest.mark.django_db
def test_scan_is_idempotent_for_signals() -> None:
    _company_with_closes("INFY", [10, 11, 12, 11, 10, 9, 10, 11, 12])

    params = ScannerParams(short_period=2, long_period=3, lookback_days=10, max_stocks=25)
    run(params, as_of=AS_OF)
    run(params, as_of=AS_OF)

    # Two eligible crossovers, persisted once each despite running the scan twice.
    assert TradingSignal.objects.count() == 2


@pytest.mark.django_db
def test_scan_records_insufficient_history() -> None:
    _company_with_closes("SHORT", [10, 11, 12])  # only 3 bars, need > long(3) => 4+

    params = ScannerParams(short_period=2, long_period=3, lookback_days=10, max_stocks=25)
    result = run(params, as_of=AS_OF)

    assert result.rows == []
    reasons = {skip["nse_code"]: skip["reason"] for skip in result.skipped}
    assert reasons.get("SHORT") == "insufficient history"


@pytest.mark.django_db
def test_invalid_params_raise() -> None:
    with pytest.raises(ValueError):
        run(ScannerParams(short_period=7, long_period=5))
