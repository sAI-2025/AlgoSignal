"""Return calculations for the six standard windows (ARCHITECTURE §12, PRD BR-08/BR-09).

A *read-only* analytics module: it never fetches from providers, only computes from stored
candles (``HistoricalPrice``). The current value is the latest completed (adjusted) close;
the historical value is the last close on or before the target date.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from apps.companies.models import Company
from apps.market_data.selectors import load_candles_dataframe

# period -> (relativedelta factory). 1D is special (previous session, handled by offset).
PERIODS: dict[str, relativedelta] = {
    "1W": relativedelta(days=7),
    "1M": relativedelta(months=1),
    "3M": relativedelta(months=3),
    "6M": relativedelta(months=6),
    "1Y": relativedelta(years=1),
}
STALE_DAYS = 5


@dataclass
class ReturnRow:
    company_id: int
    nse_code: str
    company_name: str
    sector: str | None
    industry: str | None
    period: str
    close: float
    return_pct: float
    basis: str  # "adjusted" | "unadjusted"


@dataclass
class ExcludedRow:
    nse_code: str
    company_name: str
    reason: str


@dataclass
class ReturnsResult:
    rows: list[ReturnRow] = field(default_factory=list)
    excluded: list[ExcludedRow] = field(default_factory=list)


def _target_date(latest: date, period: str) -> date | None:
    """Return the target historical date for *period*, or None for 1D (handled separately)."""
    delta = PERIODS.get(period)
    if delta is None:
        return None
    return latest - delta


def _pick_basis(frame, hist_position: int) -> tuple[str, str, str]:
    """Return (basis, current_column, historical_column)."""
    current_adj = frame["adj_close"].iloc[-1]
    hist_adj = frame["adj_close"].iloc[hist_position]
    if pd.notna(current_adj) and pd.notna(hist_adj):
        return "adjusted", "adj_close", "adj_close"
    return "unadjusted", "close", "close"


def _compute_company(
    company: Company, period: str, as_of_date: date
) -> tuple[ReturnRow | None, ExcludedRow | None]:
    frame = load_candles_dataframe(company.id)
    if frame.empty:
        return None, ExcludedRow(company.nse_code, company.company_name, "no price data")

    latest_date = frame.index.max().date()
    if (as_of_date - latest_date).days > STALE_DAYS:
        return None, ExcludedRow(
            company.nse_code, company.company_name, f"stale (last {latest_date})"
        )

    if period == "1D":
        if len(frame.index) < 2:
            return None, ExcludedRow(company.nse_code, company.company_name, "insufficient history")
        hist_position = len(frame.index) - 2
    else:
        target = _target_date(latest_date, period)
        if target is None:
            return None, ExcludedRow(company.nse_code, company.company_name, "unknown period")
        window = frame.loc[: pd.Timestamp(target)]  # last close on or before target
        if window.empty:
            return None, ExcludedRow(company.nse_code, company.company_name, "insufficient history")
        hist_position = len(window.index) - 1

    basis, current_col, hist_col = _pick_basis(frame, hist_position)
    current_value = float(frame[current_col].iloc[-1])
    historical_value = float(frame[hist_col].iloc[hist_position])
    if historical_value == 0:
        return None, ExcludedRow(company.nse_code, company.company_name, "zero historical price")

    return_pct = (current_value - historical_value) / historical_value * 100
    return (
        ReturnRow(
            company_id=company.id,
            nse_code=company.nse_code,
            company_name=company.company_name,
            sector=company.sector,
            industry=company.industry,
            period=period,
            close=current_value,
            return_pct=return_pct,
            basis=basis,
        ),
        None,
    )


def compute_returns(period: str, *, now: datetime | None = None) -> ReturnsResult:
    """Compute *period* returns across all active companies."""
    now = now or timezone.now()
    as_of_date = now.date()
    result = ReturnsResult()

    companies = Company.objects.filter(is_active=True).order_by("nse_code")
    for company in companies:
        row, excluded = _compute_company(company, period, as_of_date)
        if row is not None:
            result.rows.append(row)
        elif excluded is not None:
            result.excluded.append(excluded)
    return result


def company_returns(
    company: Company,
    periods: list[str] | None = None,
    *,
    now: datetime | None = None,
) -> list[ReturnRow | None]:
    """Return one row per period for a single company (``None`` where excluded).

    Used by the Company Detail returns strip (PRD S5b Overview tab).
    """
    now = now or timezone.now()
    as_of_date = now.date()
    periods = periods or ["1D", "1W", "1M", "3M", "6M", "1Y"]
    rows: list[ReturnRow | None] = []
    for period in periods:
        row, _excluded = _compute_company(company, period, as_of_date)
        rows.append(row)
    return rows


def top_performers_from_result(
    result: ReturnsResult,
    *,
    sector: str | None = None,
    industry: str | None = None,
    limit: int | None = 20,
    order: str = "desc",
) -> ReturnsResult:
    """Filter, sort and limit an already-computed :class:`ReturnsResult`."""
    rows = result.rows

    if sector:
        rows = [row for row in rows if row.sector == sector]
    if industry:
        rows = [row for row in rows if row.industry == industry]

    rows = sorted(rows, key=lambda row: row.return_pct, reverse=(order == "desc"))
    if limit is not None:
        rows = rows[:limit]

    return ReturnsResult(rows=rows, excluded=result.excluded)


def top_performers(
    period: str,
    *,
    sector: str | None = None,
    industry: str | None = None,
    limit: int | None = 20,
    order: str = "desc",
    now: datetime | None = None,
) -> ReturnsResult:
    """Filtered, sorted, limited return rows for the Top Performers screen."""
    result = compute_returns(period, now=now)
    return top_performers_from_result(
        result, sector=sector, industry=industry, limit=limit, order=order
    )


def best_median_worst(rows: list[ReturnRow]) -> dict[str, float | None]:
    if not rows:
        return {"best": None, "median": None, "worst": None}
    values = sorted(row.return_pct for row in rows)
    midpoint = len(values) // 2
    median = (
        values[midpoint] if len(values) % 2 == 1 else (values[midpoint - 1] + values[midpoint]) / 2
    )
    return {"best": values[-1], "median": median, "worst": values[0]}
