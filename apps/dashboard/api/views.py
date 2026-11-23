"""Dashboard API views (S1 KPI summary + freshness chip)."""

from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.api.throttling import MarketOverviewRateThrottle
from apps.dashboard.api.serializers import DashboardSummarySerializer
from apps.dashboard.services.summary import dashboard_summary


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([MarketOverviewRateThrottle])
def dashboard_summary_api(request):
    """KPI counts, breadth, sectors, recent signals and top gainers for the dashboard."""
    summary = dashboard_summary()
    return Response(
        DashboardSummarySerializer(
            {
                "coverage": summary.coverage,
                "breadth": summary.breadth,
                "sectors": summary.sectors,
                "recent_signals": [
                    {
                        "nse_code": row.company.nse_code,
                        "company_name": row.company.company_name,
                        "signal_type": row.signal_type,
                        "crossover_date": row.crossover_date,
                        "close": float(row.close_price),
                    }
                    for row in summary.recent_signals
                ],
                "top_gainers": [
                    {
                        "nse_code": row.nse_code,
                        "company_name": row.company_name,
                        "return_pct": row.return_pct,
                    }
                    for row in summary.top_gainers
                ],
                "freshness_stale": summary.freshness_stale,
            }
        ).data
    )
