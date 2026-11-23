"""Dashboard summary composition (ARCHITECTURE §4.10, PRD S1).

Reads from lower apps' selectors/services and shapes one dict for the dashboard page.
Owns no models and no business rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from apps.analytics.services.market_overview import advancers_decliners
from apps.analytics.services.performance import compute_returns, top_performers_from_result
from apps.analytics.services.sector_stats import sector_stats_from_result
from apps.market_data.selectors import coverage_summary
from apps.scanner.selectors import stored_signals


@dataclass
class DashboardSummary:
    coverage: dict
    breadth: dict
    sectors: list[dict] = field(default_factory=list)
    recent_signals: list = field(default_factory=list)
    top_gainers: list = field(default_factory=list)
    freshness_stale: bool = False


def dashboard_summary() -> DashboardSummary:
    coverage = coverage_summary()
    breadth = advancers_decliners()
    # Compute the universe 1D returns once and derive both sectors and top gainers from it.
    result = compute_returns("1D")
    sectors = sector_stats_from_result(result)
    gainers = top_performers_from_result(result, limit=5)
    recent = stored_signals(limit=8)

    return DashboardSummary(
        coverage=coverage,
        breadth=breadth,
        sectors=sectors,
        recent_signals=recent,
        top_gainers=gainers.rows,
        freshness_stale=False,
    )
