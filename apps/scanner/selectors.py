"""Read-only queries for the scanner app (ARCHITECTURE §3.1)."""

from __future__ import annotations

from apps.signals.models import TradingSignal


def stored_signals(
    *,
    signal_type: str | None = None,
    limit: int | None = None,
    short_period: int | None = None,
    long_period: int | None = None,
):
    qs = (
        TradingSignal.objects.select_related("company")
        .filter(strategy="SMA_CROSS")
        .order_by("-crossover_date", "company__nse_code")
    )
    if signal_type:
        qs = qs.filter(signal_type=signal_type)
    if short_period is not None:
        qs = qs.filter(short_period=short_period)
    if long_period is not None:
        qs = qs.filter(long_period=long_period)
    if limit is not None:
        qs = qs[:limit]
    return list(qs)
