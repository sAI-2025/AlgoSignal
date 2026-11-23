from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
from django.db.models import Min
from django.utils import timezone

from apps.market_data.models import HistoricalPrice, Instrument
from apps.market_data.services.completeness import filter_completed_candles
from apps.market_data.services.providers.yfinance_provider import YFinanceProvider


@dataclass
class HistoricalSaveResult:
    written_rows: int = 0
    skipped_incomplete_rows: int = 0


def _to_decimal(value: object) -> Decimal | None:
    if value is None or pd.isna(value):
        return None
    return Decimal(str(value)).quantize(Decimal("0.0001"))


def store_historical_prices(
    company_id: int,
    frame: pd.DataFrame,
    *,
    source: str = "yfinance",
) -> HistoricalSaveResult:
    if frame.empty:
        return HistoricalSaveResult()

    completed_frame = filter_completed_candles(frame)
    skipped_incomplete = int(len(frame.index) - len(completed_frame.index))
    if completed_frame.empty:
        return HistoricalSaveResult(written_rows=0, skipped_incomplete_rows=skipped_incomplete)

    now = timezone.now()
    rows: list[HistoricalPrice] = []
    for index, row in completed_frame.iterrows():
        candle_date = pd.Timestamp(index).date()
        open_value = _to_decimal(row.get("open"))
        high_value = _to_decimal(row.get("high"))
        low_value = _to_decimal(row.get("low"))
        close_value = _to_decimal(row.get("close"))
        if any(v is None for v in (open_value, high_value, low_value, close_value)):
            continue

        rows.append(
            HistoricalPrice(
                company_id=company_id,
                candle_date=candle_date,
                open=open_value,
                high=high_value,
                low=low_value,
                close=close_value,
                adj_close=_to_decimal(row.get("adj_close")),
                volume=int(row.get("volume") or 0),
                source=source,
                updated_at=now,
            )
        )

    HistoricalPrice.objects.bulk_create(
        rows,
        update_conflicts=True,
        unique_fields=["company", "candle_date"],
        update_fields=[
            "open",
            "high",
            "low",
            "close",
            "adj_close",
            "volume",
            "source",
            "updated_at",
        ],
    )
    return HistoricalSaveResult(
        written_rows=len(rows),
        skipped_incomplete_rows=skipped_incomplete,
    )


def _infer_start_date(company_id: int, years: int) -> date:
    latest = (
        HistoricalPrice.objects.filter(company_id=company_id)
        .order_by("-candle_date")
        .values_list("candle_date", flat=True)
        .first()
    )
    if latest:
        return latest + timedelta(days=1)
    return timezone.localdate() - timedelta(days=365 * years)


def _resolve_start_date(
    instrument: Instrument, years: int, listing_date: date | None = None
) -> date:
    """Resolve the backfill start date.

    Priority:
      1. Explicit *listing_date* (e.g. from yfinance info).
      2. Earliest stored candle date + 1 day (incremental refresh).
      3. ``today - years`` (fresh backfill).
    """
    if listing_date is not None:
        return listing_date
    earliest = (
        HistoricalPrice.objects.filter(company_id=instrument.company_id)
        .aggregate(earliest=Min("candle_date"))["earliest"]
    )
    if earliest is not None:
        return earliest + timedelta(days=1)
    return timezone.localdate() - timedelta(days=365 * years)


def backfill_company_history(
    instrument: Instrument,
    *,
    years: int = 3,
    start: date | None = None,
    end: date | None = None,
    listing_date: date | None = None,
) -> HistoricalSaveResult:
    provider = YFinanceProvider()
    start_date = start or _resolve_start_date(instrument, years, listing_date)
    end_date = end or timezone.localdate()

    data = provider.get_daily_candles([instrument.provider_symbol], start_date, end_date)
    frame = data.get(instrument.provider_symbol, pd.DataFrame())
    return store_historical_prices(
        instrument.company_id,
        frame,
        source=provider.name,
    )
