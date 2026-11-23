"""Idempotent persistence of crossover rows into ``TradingSignal``."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from apps.signals.models import TradingSignal

_QUANT = Decimal("0.0001")


@dataclass
class SaveResult:
    inserted: int = 0
    skipped: int = 0


def _to_decimal(value: object) -> Decimal:
    return Decimal(str(value)).quantize(_QUANT)


def save(
    company,
    *,
    strategy: str,
    short: int,
    long: int,
    rows: pd.DataFrame,
) -> SaveResult:
    """Persist *rows* for *company*, skipping any that already exist (unique key)."""
    if rows.empty:
        return SaveResult()

    objects = [
        TradingSignal(
            company=company,
            strategy=strategy,
            signal_type=row.signal_type,
            short_period=short,
            long_period=long,
            short_sma=_to_decimal(row.short_sma),
            long_sma=_to_decimal(row.long_sma),
            close_price=_to_decimal(row.close),
            crossover_date=row.candle_date,
        )
        for row in rows.itertuples(index=False)
    ]

    before = TradingSignal.objects.filter(company=company, strategy=strategy).count()
    TradingSignal.objects.bulk_create(objects, ignore_conflicts=True)
    after = TradingSignal.objects.filter(company=company, strategy=strategy).count()

    inserted = after - before
    return SaveResult(inserted=inserted, skipped=len(objects) - inserted)
