"""Fetcher API views (S6 market data & fetch control)."""

from __future__ import annotations

from django.core.paginator import Paginator
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.api.permissions import IsStaff
from apps.core.api.throttling import (
    CoverageRateThrottle,
    FetcherBackfillRateThrottle,
    FetcherRunNowRateThrottle,
    FetcherSchedulesRateThrottle,
)
from apps.fetcher.api.serializers import (
    BackfillSerializer,
    CoverageSerializer,
    FetchRunSerializer,
    FetchScheduleSerializer,
    FetchScheduleUpdateSerializer,
)
from apps.fetcher.models import FetchRun, FetchSchedule
from apps.fetcher.selectors import (
    all_schedules,
    heartbeat_age_seconds,
    recent_runs,
    scheduler_is_stale,
)
from apps.fetcher.services import locking
from apps.fetcher.services.scheduler import run_now
from apps.market_data.models import Instrument
from apps.market_data.selectors import coverage_summary
from apps.market_data.services.historical_data import backfill_company_history


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([FetcherSchedulesRateThrottle])
def schedules_list(request):
    """List fetch schedules plus provider/scheduler status."""
    schedules = all_schedules()
    return Response(
        {
            "schedules": FetchScheduleSerializer(schedules, many=True).data,
            "provider": {
                "cooling_down": locking.is_cooling_down(),
                "cooldown_seconds": locking.cooldown_remaining_seconds(),
            },
            "scheduler": {
                "stale": scheduler_is_stale(),
                "heartbeat_age_seconds": heartbeat_age_seconds(),
            },
        }
    )


@api_view(["PUT"])
@permission_classes([IsStaff])
@throttle_classes([FetcherSchedulesRateThrottle])
def schedule_detail(request, schedule_id):
    """Update a fetch schedule (staff only)."""
    try:
        schedule = FetchSchedule.objects.get(pk=schedule_id)
    except FetchSchedule.DoesNotExist:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "Schedule not found."}}, status=404
        )

    serializer = FetchScheduleUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    updatable = [
        "enabled",
        "interval_hours",
        "only_market_days",
        "earliest_time_ist",
        "batch_size",
        "throttle_seconds",
    ]
    for field in updatable:
        if field in data:
            setattr(schedule, field, data[field])
    schedule.save()
    return Response(FetchScheduleSerializer(schedule).data)


@api_view(["POST"])
@permission_classes([IsStaff])
@throttle_classes([FetcherRunNowRateThrottle])
def schedule_run_now(request, schedule_id):
    """Run a schedule immediately (staff only)."""
    try:
        schedule = FetchSchedule.objects.get(pk=schedule_id)
    except FetchSchedule.DoesNotExist:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "Schedule not found."}}, status=404
        )
    try:
        run = run_now(schedule, trigger="MANUAL")
    except RuntimeError as exc:
        return Response({"error": {"code": "BUSY", "message": str(exc)}}, status=409)
    return Response(
        {
            "status": run.status,
            "success_items": run.success_items,
            "failed_items": run.failed_items,
            "rows_written": run.rows_written,
            "message": run.message,
        }
    )


@api_view(["POST"])
@permission_classes([IsStaff])
@throttle_classes([FetcherBackfillRateThrottle])
def backfill(request):
    """Backfill historical candles (staff only)."""
    serializer = BackfillSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    years = data["years"]
    symbol = (data.get("symbol") or "").strip().upper() or None
    start = data.get("start")
    end = data.get("end")

    instruments = Instrument.objects.select_related("company").filter(
        exchange=Instrument.Exchange.NSE
    )
    if symbol:
        instruments = instruments.filter(company__nse_code=symbol)

    total_written = 0
    total_skipped = 0
    per_symbol = []
    for instrument in instruments.order_by("company__nse_code"):
        result = backfill_company_history(instrument, years=years, start=start, end=end)
        total_written += result.written_rows
        total_skipped += result.skipped_incomplete_rows
        per_symbol.append(
            {
                "symbol": instrument.company.nse_code,
                "written": result.written_rows,
                "skipped_incomplete": result.skipped_incomplete_rows,
            }
        )

    return Response(
        {
            "years": years,
            "symbol": symbol,
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "total_written": total_written,
            "total_skipped": total_skipped,
            "per_symbol": per_symbol,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([])  # default user rate 120/min
def runs_list(request):
    """Fetch run history, optionally filtered by job type and status."""
    job_type = request.query_params.get("job") or None
    status = request.query_params.get("status") or None
    try:
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 50))
    except (TypeError, ValueError):
        page, page_size = 1, 50
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    runs = recent_runs(job_type=job_type, status=status)
    paginator = Paginator(runs, page_size)
    page_obj = paginator.get_page(page)

    return Response(
        {
            "results": FetchRunSerializer(page_obj.object_list, many=True).data,
            "pagination": {
                "page": page_obj.number,
                "page_size": page_size,
                "total": paginator.count,
                "num_pages": paginator.num_pages,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
            },
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([])  # default user rate 120/min
def run_detail(request, run_id):
    """Single fetch run detail."""
    try:
        run = FetchRun.objects.get(pk=run_id)
    except FetchRun.DoesNotExist:
        return Response({"error": {"code": "NOT_FOUND", "message": "Run not found."}}, status=404)
    return Response(FetchRunSerializer(run).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([CoverageRateThrottle])
def coverage(request):
    """Universe-wide candle coverage for the freshness chip."""
    return Response(CoverageSerializer(coverage_summary()).data)
