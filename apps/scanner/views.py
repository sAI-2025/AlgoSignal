from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.scanner.models import ScannerSetting
from apps.scanner.selectors import stored_signals
from apps.scanner.services.params import ScannerParams
from apps.scanner.services.scanner import run


def _params_from_post(post) -> ScannerParams:
    return ScannerParams(
        short_period=int(post.get("short_period") or 7),
        long_period=int(post.get("long_period") or 30),
        lookback_days=int(post.get("lookback_days") or 10),
        max_stocks=int(post.get("max_stocks") or 25),
    )


def _serialize_rows(result) -> list[dict]:
    return [
        {
            "rank": index,
            "nse_code": row.nse_code,
            "company_name": row.company_name,
            "signal_type": row.signal_type,
            "crossover_date": row.crossover_date.isoformat(),
            "close": row.close,
            "short_sma": row.short_sma,
            "long_sma": row.long_sma,
        }
        for index, row in enumerate(result.rows, start=1)
    ]


@login_required
def signals_page(request):
    settings_obj = ScannerSetting.load()
    context = {
        "settings": settings_obj,
        "scan_result": None,
        "errors": {},
        "stored": stored_signals(limit=50),
    }

    if request.method == "POST":
        params = _params_from_post(request.POST)
        context["params"] = params
        context["errors"] = params.errors()
        if params.is_valid:
            context["scan_result"] = run(params)
        return render(request, "scanner/signals.html", context)

    context["params"] = ScannerParams(
        short_period=settings_obj.short_period,
        long_period=settings_obj.long_period,
        lookback_days=settings_obj.lookback_days,
        max_stocks=settings_obj.max_stocks,
    )
    return render(request, "scanner/signals.html", context)


@login_required
@require_http_methods(["POST"])
def scanner_run_api(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": {"code": "MALFORMED", "message": "Invalid JSON"}}, status=400)

    try:
        params = ScannerParams.from_mapping(payload)
    except (TypeError, ValueError) as exc:
        return JsonResponse(
            {"error": {"code": "VALIDATION_ERROR", "message": str(exc)}}, status=422
        )

    errors = params.errors()
    if errors:
        return JsonResponse(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid parameters",
                    "fields": errors,
                }
            },
            status=422,
        )

    result = run(params)
    return JsonResponse(
        {
            "rows": _serialize_rows(result),
            "counts": {"bullish": result.bullish_count, "bearish": result.bearish_count},
            "total_crossovers": result.total_crossovers,
            "skipped": result.skipped,
            "as_of": result.as_of.isoformat() if result.as_of else None,
        }
    )


@login_required
@require_http_methods(["GET", "PUT"])
def scanner_settings_api(request):
    settings_obj = ScannerSetting.load()
    if request.method == "GET":
        return JsonResponse(
            {
                "short_period": settings_obj.short_period,
                "long_period": settings_obj.long_period,
                "lookback_days": settings_obj.lookback_days,
                "max_stocks": settings_obj.max_stocks,
                "auto_run_on_open": settings_obj.auto_run_on_open,
            }
        )

    if not request.user.is_staff:
        return JsonResponse(
            {"error": {"code": "FORBIDDEN", "message": "Staff required"}}, status=403
        )

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": {"code": "MALFORMED", "message": "Invalid JSON"}}, status=400)

    params = ScannerParams.from_mapping(payload)
    errors = params.errors()
    if errors:
        return JsonResponse(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid parameters",
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
    return JsonResponse({"status": "saved"})


# Kept for potential staff-only triggering from the dashboard; not wired yet.
staff_only = user_passes_test(lambda user: user.is_staff)
