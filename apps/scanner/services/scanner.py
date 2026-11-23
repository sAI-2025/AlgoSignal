"""Scan orchestration: candles → SMAs → crossovers → lookback → rank → persist.

This is the head chef (ARCHITECTURE §1). It coordinates the indicators, signals and
market_data apps but owns no maths of its own beyond the pipeline glue (ARCHITECTURE §4.7).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime

from django.utils import timezone

from apps.companies.models import Company
from apps.indicators.registry import get_indicator
from apps.market_data.selectors import load_candles_dataframe
from apps.market_data.services.completeness import filter_completed_candles
from apps.scanner.services.params import ScannerParams
from apps.signals.services.crossover import detect
from apps.signals.services.persistence import save

logger = logging.getLogger(__name__)


@dataclass
class ScanRow:
    company_id: int
    nse_code: str
    company_name: str
    sector: str | None
    signal_type: str
    crossover_date: date
    close: float
    short_sma: float
    long_sma: float
    strength: float


@dataclass
class ScanResult:
    rows: list[ScanRow] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    total_crossovers: int = 0
    bullish_count: int = 0
    bearish_count: int = 0
    as_of: date | None = None
    params: ScannerParams | None = None


def _process_company(
    company: Company, params: ScannerParams, now: datetime
) -> tuple[ScanRow | None, dict | None]:
    """Compute one company's latest eligible crossover, persisting it when present.

    Returns ``(row, skip)`` — exactly one is non-None.
    """
    frame = load_candles_dataframe(company.id, limit=params.fetch_window())
    if frame.empty:
        return None, {"nse_code": company.nse_code, "reason": "no price data"}

    frame = filter_completed_candles(frame, now=now)
    if len(frame.index) < params.long_period + 1:
        return None, {"nse_code": company.nse_code, "reason": "insufficient history"}

    crossovers = detect(frame, params.short_period, params.long_period)
    if crossovers.empty:
        return None, None

    # Keep only crossovers inside the lookback window (last `lookback_days` bars).
    last_index = len(frame.index) - 1
    earliest_index = max(0, last_index - params.lookback_days + 1)
    eligible_dates = set(frame.index[earliest_index : last_index + 1].date)
    eligible = crossovers[crossovers["candle_date"].isin(eligible_dates)]
    if eligible.empty:
        return None, None

    # Idempotent persistence of all eligible crossovers in the window.
    save(
        company,
        strategy="SMA_CROSS",
        short=params.short_period,
        long=params.long_period,
        rows=eligible,
    )

    latest = eligible.sort_values("candle_date").iloc[-1]
    close = float(latest["close"])
    short_sma = float(latest["short_sma"])
    long_sma = float(latest["long_sma"])
    strength = abs(short_sma - long_sma) / close if close else 0.0

    row = ScanRow(
        company_id=company.id,
        nse_code=company.nse_code,
        company_name=company.company_name,
        sector=company.sector,
        signal_type=latest["signal_type"],
        crossover_date=latest["candle_date"],
        close=close,
        short_sma=short_sma,
        long_sma=long_sma,
        strength=strength,
    )
    return row, None


def run(params: ScannerParams, *, as_of: datetime | None = None) -> ScanResult:
    """Execute the scan pipeline and persist signals (idempotent)."""
    if not params.is_valid:
        raise ValueError(f"Invalid scanner params: {params.errors()}")

    # Fail fast if the SMA indicator is somehow unavailable.
    get_indicator("sma")

    now = as_of or timezone.now()
    result = ScanResult(as_of=now.date(), params=params)

    companies = Company.objects.filter(is_active=True).order_by("nse_code")
    for company in companies:
        row, skip = _process_company(company, params, now)
        if skip is not None:
            result.skipped.append(skip)
        if row is None:
            continue

        result.rows.append(row)
        if row.signal_type == "BULLISH":
            result.bullish_count += 1
        else:
            result.bearish_count += 1

    result.total_crossovers = len(result.rows)

    # Rank + limit to Max Stocks (one row per company already).
    from apps.scanner.services.ranking import apply_max_stocks, rank_rows

    ranked = rank_rows(result.rows)
    result.rows = apply_max_stocks(ranked, params.max_stocks)
    return result
