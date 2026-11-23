"""Read-only queries over stored market data (ARCHITECTURE §3.1: selectors *ask*)."""

from __future__ import annotations

from datetime import date

import pandas as pd
from django.db.models import Count, Max, Min

from apps.market_data.models import HistoricalPrice, Instrument

DATA_COLUMNS = ["open", "high", "low", "close", "adj_close", "volume"]


def load_candles_dataframe(company_id: int, *, limit: int | None = None) -> pd.DataFrame:
    """Return a company's candles as a DataFrame indexed ascending by ``candle_date``.

    Columns are lower-case OHLCV + ``adj_close`` to match the indicator contract
    (ARCHITECTURE §10). Rows are ordered oldest → newest.
    """
    qs = HistoricalPrice.objects.filter(company_id=company_id).order_by("-candle_date")
    if limit is not None:
        qs = qs[:limit]

    return _records_to_frame(qs)


def load_candles_range(
    company_id: int,
    *,
    start: date | None = None,
    end: date | None = None,
    limit: int = 5000,
) -> pd.DataFrame:
    """Return candles within ``[start, end]`` (inclusive), oldest → newest, capped at *limit*."""
    qs = HistoricalPrice.objects.filter(company_id=company_id)
    if start is not None:
        qs = qs.filter(candle_date__gte=start)
    if end is not None:
        qs = qs.filter(candle_date__lte=end)
    qs = qs.order_by("-candle_date")[:limit]
    return _records_to_frame(qs)


def _records_to_frame(qs) -> pd.DataFrame:
    records = [
        {
            "candle_date": price.candle_date,
            "open": float(price.open),
            "high": float(price.high),
            "low": float(price.low),
            "close": float(price.close),
            "adj_close": float(price.adj_close) if price.adj_close is not None else None,
            "volume": price.volume,
        }
        for price in qs
    ]
    records.reverse()

    if not records:
        return pd.DataFrame(columns=["candle_date", *DATA_COLUMNS])

    frame = pd.DataFrame(records).set_index("candle_date")
    frame.index = pd.to_datetime(frame.index)
    return frame[DATA_COLUMNS]


def latest_candle_date() -> date | None:
    return HistoricalPrice.objects.aggregate(latest=Max("candle_date"))["latest"]


def company_last_candle_date(company_id: int) -> date | None:
    return HistoricalPrice.objects.filter(company_id=company_id).aggregate(
        latest=Max("candle_date")
    )["latest"]


def company_candles(company_id: int):
    """Return a company's candles newest-first (unpaginated queryset for views)."""
    return HistoricalPrice.objects.filter(company_id=company_id).order_by("-candle_date")


def coverage_summary() -> dict:
    """Universe-wide candle coverage for the Market Data / dashboard freshness chip."""
    total_companies = Instrument.objects.filter(exchange=Instrument.Exchange.NSE).count()
    with_data = HistoricalPrice.objects.values("company_id").distinct().count()
    latest = latest_candle_date()
    earliest = HistoricalPrice.objects.aggregate(earliest=Min("candle_date"))["earliest"]
    return {
        "companies": total_companies,
        "with_data": with_data,
        "latest_candle": latest,
        "earliest_candle": earliest,
    }


def company_coverage(company_id: int) -> dict:
    agg = HistoricalPrice.objects.filter(company_id=company_id).aggregate(
        count=Count("id"), first=Min("candle_date"), last=Max("candle_date")
    )
    return {
        "count": agg["count"],
        "first": agg["first"],
        "last": agg["last"],
    }


def load_benchmark_candles(symbol: str, start: date, end: date) -> pd.DataFrame:
    """Fetch benchmark/index candles from the provider (not stored), indexed by date.

    The benchmark lives outside the stored universe (e.g. ``^NSEI``), so it is read
    straight from the provider rather than from ``HistoricalPrice``.
    """
    from apps.market_data.services.providers.yfinance_provider import YFinanceProvider

    provider = YFinanceProvider()
    frames = provider.get_daily_candles([symbol], start, end)
    frame = frames.get(symbol, pd.DataFrame())
    if frame.empty:
        return pd.DataFrame(columns=DATA_COLUMNS)
    return frame[["open", "high", "low", "close", "volume"]]
