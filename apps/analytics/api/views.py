"""Analytics API views (S4 top performers, S1 market overview, sectors)."""

from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.analytics.api.serializers import (
    MarketOverviewSerializer,
    ReturnRowSerializer,
    SectorStatSerializer,
    SectorStatsQuerySerializer,
    TopPerformersQuerySerializer,
)
from apps.analytics.services.market_overview import advancers_decliners
from apps.analytics.services.performance import top_performers
from apps.analytics.services.sector_stats import sector_stats
from apps.core.api.throttling import MarketOverviewRateThrottle, TopPerformersRateThrottle


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([TopPerformersRateThrottle])
def top_performers_api(request):
    """Returns ranking for a period, with optional sector/industry filter and ordering."""
    query = TopPerformersQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    data = query.validated_data

    result = top_performers(
        period=data["period"],
        sector=data.get("sector") or None,
        industry=data.get("industry") or None,
        limit=data["limit"],
        order=data["order"],
    )

    return Response(
        {
            "period": data["period"],
            "results": ReturnRowSerializer(result.rows, many=True).data,
            "excluded": [
                {"nse_code": row.nse_code, "company_name": row.company_name, "reason": row.reason}
                for row in result.excluded
            ],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([MarketOverviewRateThrottle])
def market_overview_api(request):
    """Advancers / decliners / unchanged from the last two completed closes."""
    counts = advancers_decliners()
    return Response(MarketOverviewSerializer(counts).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([MarketOverviewRateThrottle])
def sectors_api(request):
    """Per-sector average return and count for a period."""
    query = SectorStatsQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    stats = sector_stats(period=query.validated_data["period"])
    return Response(SectorStatSerializer(stats, many=True).data)
