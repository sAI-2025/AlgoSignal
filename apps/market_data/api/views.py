"""Live data API views (PRD FR-14, ARCHITECTURE §9)."""

from __future__ import annotations

from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.api.throttling import LiveIntradayRateThrottle, LiveQuoteRateThrottle
from apps.market_data.api.serializers import (
    IntradayQuerySerializer,
    LiveQuoteSerializer,
    LiveQuotesQuerySerializer,
    RefreshMetricsSerializer,
)
from apps.market_data.services.live_quotes import (
    get_intraday,
    get_live_quote,
    get_live_quotes,
    refresh_metrics,
)
from apps.market_data.services.providers.base import ProviderNoData

REFRESH_METRICS_TTL = 60


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([LiveQuoteRateThrottle])
def live_quote(request, nse_code):
    """Single live quote (cached 30 s, never persisted)."""
    try:
        payload = get_live_quote(nse_code)
    except ProviderNoData:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "Company not found."}}, status=404
        )
    return Response(LiveQuoteSerializer(payload).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([LiveQuoteRateThrottle])
def live_quotes(request):
    """Batch live quotes (≤ 20 symbols)."""
    query = LiveQuotesQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    raw = query.validated_data.get("symbols") or ""
    symbols = [s.strip() for s in raw.split(",") if s.strip()][:20]
    payloads = get_live_quotes(symbols)
    return Response(LiveQuoteSerializer(payloads, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([LiveIntradayRateThrottle])
def live_intraday(request, nse_code):
    """Intraday bars for the on-screen last bar (Live mode)."""
    query = IntradayQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    records = get_intraday(nse_code, interval=query.validated_data["interval"])
    return Response(
        {
            "symbol": nse_code,
            "interval": query.validated_data["interval"],
            "bars": records,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([])  # per-symbol 1/min enforced below
def live_refresh_metrics(request, nse_code):
    """Live-fetch fresh fundamentals and upsert the snapshot (1 request/min/symbol)."""
    RefreshMetricsSerializer(data=request.data or {}).is_valid(raise_exception=True)
    lock_key = f"live:refresh-metrics:{nse_code.upper()}"
    if cache.get(lock_key) is not None:
        return Response(
            {
                "error": {
                    "code": "THROTTLED",
                    "message": "Wait before refreshing this symbol again.",
                }
            },
            status=429,
        )
    cache.set(lock_key, "1", REFRESH_METRICS_TTL)
    try:
        result = refresh_metrics(nse_code)
    except Exception as exc:  # noqa: BLE001 - surface provider errors cleanly
        return Response({"error": {"code": "PROVIDER_ERROR", "message": str(exc)}}, status=502)
    return Response(result)
