from __future__ import annotations

from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from apps.companies.models import Company
from apps.visualization.services.chart_payload import (
    build_chart_payload,
    parse_indicator_param,
    parse_sma_periods,
    sma_periods_to_specs,
)


def _parse_before(raw: str | None) -> date | None:
    """Parse an ISO ``before=YYYY-MM-DD`` anchor for lazy history; ``None`` means latest."""
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid before date: {raw!r}") from exc


@login_required
def chart_workspace(request, nse_code: str):
    """Render the full-screen chart workspace shell for *nse_code*."""
    company = get_object_or_404(Company, nse_code=nse_code.upper())
    context = {
        "company": company,
        "timeframes": ["1D", "1W", "1M", "3M", "6M", "1Y", "3Y", "5Y", "MAX"],
        "sma_options": [7, 30],
    }
    return render(request, "visualization/chart_workspace.html", context)


@login_required
def chart_payload_api(request, nse_code: str):
    company = get_object_or_404(Company, nse_code=nse_code.upper())
    tf = request.GET.get("tf", "1Y")
    markers = request.GET.get("markers", "1") not in ("0", "false", "")

    try:
        sma_periods = parse_sma_periods(request.GET.get("sma"))
    except ValueError as exc:
        return JsonResponse({"error": {"code": "VALIDATION", "message": str(exc)}}, status=422)

    try:
        indicator_specs = sma_periods_to_specs(sma_periods)
        for raw in request.GET.getlist("ind"):
            try:
                indicator_specs.append(parse_indicator_param(raw))
            except ValueError as exc:
                return JsonResponse(
                    {"error": {"code": "VALIDATION", "message": str(exc)}}, status=422
                )
    except ValueError as exc:
        return JsonResponse({"error": {"code": "VALIDATION", "message": str(exc)}}, status=422)

    try:
        before = _parse_before(request.GET.get("before"))
    except ValueError as exc:
        return JsonResponse({"error": {"code": "VALIDATION", "message": str(exc)}}, status=422)

    benchmark = request.GET.get("benchmark") or None

    try:
        payload = build_chart_payload(
            company,
            tf=tf,
            indicator_specs=indicator_specs,
            markers=markers,
            before=before,
            benchmark=benchmark,
        )
    except ValueError as exc:
        return JsonResponse({"error": {"code": "VALIDATION", "message": str(exc)}}, status=422)

    return JsonResponse(payload)
