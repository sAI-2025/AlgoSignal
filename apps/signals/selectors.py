"""Read-only queries for stored signals (ARCHITECTURE §3.1: selectors *ask*)."""

from __future__ import annotations

from apps.signals.models import TradingSignal


def recent_signals(*, limit: int = 8, signal_type: str | None = None):
    qs = TradingSignal.objects.select_related("company").order_by(
        "-crossover_date", "company__nse_code"
    )
    if signal_type:
        qs = qs.filter(signal_type=signal_type)
    return list(qs[:limit])


def signals_for_company(company_id: int, *, signal_type: str | None = None):
    qs = (
        TradingSignal.objects.filter(company_id=company_id)
        .select_related("company")
        .order_by("-crossover_date")
    )
    if signal_type:
        qs = qs.filter(signal_type=signal_type)
    return list(qs)


def signal_type_counts(*, strategy: str = "SMA_CROSS") -> dict[str, int]:
    from django.db.models import Count

    rows = (
        TradingSignal.objects.filter(strategy=strategy)
        .values("signal_type")
        .annotate(count=Count("id"))
    )
    counts = {row["signal_type"]: row["count"] for row in rows}
    return {
        "bullish": counts.get("BULLISH", 0),
        "bearish": counts.get("BEARISH", 0),
    }
