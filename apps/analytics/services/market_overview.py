"""Market breadth and sector aggregates (ARCHITECTURE §12, PRD S1 market overview)."""

from __future__ import annotations

from dataclasses import dataclass, field

from apps.analytics.services.performance import compute_returns
from apps.companies.models import Company
from apps.market_data.selectors import load_candles_dataframe


@dataclass
class MarketOverview:
    advancers: int = 0
    decliners: int = 0
    unchanged: int = 0
    sectors: list[dict] = field(default_factory=list)


def advancers_decliners() -> dict[str, int]:
    """Count advancers/decliners/unchanged from each company's last two completed closes."""
    counts = {"advancers": 0, "decliners": 0, "unchanged": 0}
    for company in Company.objects.filter(is_active=True).only("id"):
        frame = load_candles_dataframe(company.id, limit=2)
        if len(frame.index) < 2:
            continue
        previous = float(frame["close"].iloc[-2])
        latest = float(frame["close"].iloc[-1])
        if latest > previous:
            counts["advancers"] += 1
        elif latest < previous:
            counts["decliners"] += 1
        else:
            counts["unchanged"] += 1
    return counts


def sector_average_returns(period: str = "1D") -> list[dict]:
    """Average return per sector for *period*, sorted by average desc."""
    result = compute_returns(period)
    buckets: dict[str, list[float]] = {}
    for row in result.rows:
        key = row.sector or "Unknown"
        buckets.setdefault(key, []).append(row.return_pct)

    sectors = [
        {"sector": name, "average_return": sum(values) / len(values), "count": len(values)}
        for name, values in buckets.items()
    ]
    sectors.sort(key=lambda item: item["average_return"], reverse=True)
    return sectors


def market_overview() -> MarketOverview:
    overview = MarketOverview(**advancers_decliners())
    overview.sectors = sector_average_returns("1D")
    return overview
