"""Convert stored ``TradingSignal`` rows into chart marker dicts (ARCHITECTURE §13.3).

Pure shaping: reads signals and emits the ``markers`` array of the chart payload. No
indicator maths happens here — the SMA values were already persisted at detection time.
"""

from __future__ import annotations

from datetime import date

from apps.signals.models import TradingSignal


def signals_to_markers(
    company_id: int,
    *,
    start: date | None = None,
    end: date | None = None,
    strategy: str = "SMA_CROSS",
) -> list[dict]:
    """Return marker objects for *company_id* within ``[start, end]`` (inclusive)."""
    qs = TradingSignal.objects.filter(company_id=company_id, strategy=strategy)
    if start is not None:
        qs = qs.filter(crossover_date__gte=start)
    if end is not None:
        qs = qs.filter(crossover_date__lte=end)

    return [
        {
            "time": signal.crossover_date.isoformat(),
            "type": signal.signal_type,
            "price": float(signal.close_price),
            "short_sma": float(signal.short_sma),
            "long_sma": float(signal.long_sma),
            "params": [signal.short_period, signal.long_period],
        }
        for signal in qs.order_by("crossover_date")
    ]
