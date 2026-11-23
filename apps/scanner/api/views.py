"""Scanner API views (S3 run/settings + stored signals)."""

from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.api.throttling import ScannerRunRateThrottle, ScannerSettingsRateThrottle
from apps.scanner.api.serializers import (
    ScannerParamsSerializer,
    ScannerSettingsSerializer,
    ScanResultSerializer,
    SignalSerializer,
)
from apps.scanner.models import ScannerSetting
from apps.scanner.services.params import ScannerParams
from apps.scanner.services.scanner import run


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([ScannerRunRateThrottle])
def scanner_run(request):
    """Run the SMA crossover scan and persist signals (idempotent)."""
    serializer = ScannerParamsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    params = ScannerParams(
        short_period=data["short_period"],
        long_period=data["long_period"],
        lookback_days=data["lookback_days"],
        max_stocks=data["max_stocks"],
    )
    errors = params.errors()
    if errors:
        return Response(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid scanner parameters.",
                    "fields": errors,
                }
            },
            status=422,
        )

    result = run(params)
    return Response(
        ScanResultSerializer(
            {
                "rows": result.rows,
                "counts": {"bullish": result.bullish_count, "bearish": result.bearish_count},
                "total_crossovers": result.total_crossovers,
                "skipped": result.skipped,
                "as_of": result.as_of,
            }
        ).data
    )


@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
@throttle_classes([ScannerSettingsRateThrottle])
def scanner_settings(request):
    """GET scanner defaults; PUT (staff) updates them."""
    settings_obj = ScannerSetting.load()

    if request.method == "GET":
        return Response(
            ScannerSettingsSerializer(
                {
                    "short_period": settings_obj.short_period,
                    "long_period": settings_obj.long_period,
                    "lookback_days": settings_obj.lookback_days,
                    "max_stocks": settings_obj.max_stocks,
                    "auto_run_on_open": settings_obj.auto_run_on_open,
                }
            ).data
        )

    if not request.user.is_staff:
        return Response({"error": {"code": "FORBIDDEN", "message": "Staff required."}}, status=403)

    serializer = ScannerParamsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    params = ScannerParams(
        short_period=data["short_period"],
        long_period=data["long_period"],
        lookback_days=data["lookback_days"],
        max_stocks=data["max_stocks"],
    )
    errors = params.errors()
    if errors:
        return Response(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid scanner parameters.",
                    "fields": errors,
                }
            },
            status=422,
        )

    settings_obj.short_period = params.short_period
    settings_obj.long_period = params.long_period
    settings_obj.lookback_days = params.lookback_days
    settings_obj.max_stocks = params.max_stocks
    settings_obj.save()
    return Response({"status": "saved"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([])  # default user rate 120/min
def signals_list(request):
    """Stored signals, optionally filtered by type, date range, company."""
    signal_type = request.query_params.get("type") or None
    from_date = request.query_params.get("from") or None
    to_date = request.query_params.get("to") or None
    company = request.query_params.get("company") or None
    try:
        limit = int(request.query_params.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 500))

    qs_filters = {"strategy": "SMA_CROSS"}
    if signal_type:
        qs_filters["signal_type"] = signal_type
    if from_date:
        qs_filters["crossover_date__gte"] = from_date
    if to_date:
        qs_filters["crossover_date__lte"] = to_date
    if company:
        qs_filters["company__nse_code__iexact"] = company

    from apps.signals.models import TradingSignal

    rows = (
        TradingSignal.objects.filter(**qs_filters)
        .select_related("company")
        .order_by("-crossover_date", "company__nse_code")[:limit]
    )

    return Response(
        SignalSerializer(
            [
                {
                    "nse_code": row.company.nse_code,
                    "company_name": row.company.company_name,
                    "signal_type": row.signal_type,
                    "crossover_date": row.crossover_date,
                    "close": float(row.close_price),
                    "short_sma": float(row.short_sma),
                    "long_sma": float(row.long_sma),
                    "params": [row.short_period, row.long_period],
                }
                for row in rows
            ],
            many=True,
        ).data
    )
