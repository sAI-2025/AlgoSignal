"""Chart API views (V18 chart payload incl. lazy history ``before``)."""

from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.companies.models import Company
from apps.core.api.throttling import ChartRateThrottle
from apps.visualization.api.serializers import ChartPayloadQuerySerializer
from apps.visualization.services.chart_payload import (
    INDICATOR_PARAM_ORDER,
    build_chart_payload,
    parse_indicator_param,
    sma_periods_to_specs,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([ChartRateThrottle])
def chart_payload(request, nse_code):
    """Chart payload: candles + indicators + markers + meta, with ``before`` lazy history."""
    query = ChartPayloadQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    data = query.validated_data

    company = Company.objects.filter(nse_code__iexact=nse_code).first()
    if company is None:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "Company not found."}}, status=404
        )

    marker = str(data["markers"]).lower() in ("1", "true")
    try:
        sma_periods = [int(p) for p in str(data["sma"]).split(",") if p.strip()]
        indicator_specs = sma_periods_to_specs(sma_periods)
    except ValueError as exc:
        return Response(
            {
                "error": {
                    "code": "VALIDATION",
                    "message": str(exc) or "Invalid SMA period. Use comma-separated integers.",
                },
            },
            status=422,
        )
    raw_ind = str(data.get("ind") or "")
    tokens = [t.strip() for t in raw_ind.split(",") if t.strip()]
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if ":" not in token:
            i += 1
            continue
        name = token.split(":", 1)[0]
        if name not in INDICATOR_PARAM_ORDER:
            return Response(
                {"error": {"code": "VALIDATION", "message": f"Unknown indicator: {name!r}"}},
                status=422,
            )
        expected = INDICATOR_PARAM_ORDER[name]
        needed = len(expected)
        group = [token]
        j = i + 1
        while j < len(tokens) and ":" not in tokens[j] and len(group) - 1 < needed:
            group.append(tokens[j])
            j += 1
        full = ":".join(group)
        try:
            indicator_specs.append(parse_indicator_param(full))
        except ValueError as exc:
            return Response({"error": {"code": "VALIDATION", "message": str(exc)}}, status=422)
        i = j if j > i + 1 else i + 1
    benchmark = str(data.get("benchmark") or "") or None

    payload = build_chart_payload(
        company,
        tf=data["tf"],
        indicator_specs=indicator_specs or [("sma", {"window": 7}), ("sma", {"window": 30})],
        markers=marker,
        before=data.get("before"),
        benchmark=benchmark,
    )
    return Response(payload)
