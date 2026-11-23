"""Sector statistics helpers (ARCHITECTURE §12)."""

from __future__ import annotations

from apps.analytics.services.performance import ReturnsResult, compute_returns


def sector_stats_from_result(result: ReturnsResult) -> list[dict]:
    """Per-sector count and average return from an already-computed result."""
    buckets: dict[str, list[float]] = {}
    for row in result.rows:
        key = row.sector or "Unknown"
        buckets.setdefault(key, []).append(row.return_pct)

    stats = [
        {"sector": name, "count": len(values), "average_return": sum(values) / len(values)}
        for name, values in buckets.items()
    ]
    stats.sort(key=lambda item: item["average_return"], reverse=True)
    return stats


def sector_stats(period: str = "1M") -> list[dict]:
    """Return per-sector count and average return for *period*."""
    return sector_stats_from_result(compute_returns(period))
