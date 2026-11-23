from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.analytics.services.performance import (
    best_median_worst,
    compute_returns,
    top_performers_from_result,
)
from apps.analytics.services.sector_stats import sector_stats_from_result

PERIOD_CHOICES = ["1D", "1W", "1M", "3M", "6M", "1Y"]


@login_required
def top_performers_page(request):
    period = request.GET.get("period", "1M")
    if period not in PERIOD_CHOICES:
        period = "1M"
    order = "asc" if request.GET.get("order") == "asc" else "desc"
    sector = request.GET.get("sector") or None
    try:
        limit = int(request.GET.get("limit", 20))
    except (TypeError, ValueError):
        limit = 20

    # Compute the universe returns once and derive both the rows and sector stats from it.
    result = compute_returns(period)
    rows_result = top_performers_from_result(result, sector=sector, limit=limit, order=order)
    context = {
        "period": period,
        "period_choices": PERIOD_CHOICES,
        "order": order,
        "sector": sector,
        "limit": limit,
        "rows": rows_result.rows,
        "excluded": rows_result.excluded,
        "stats": best_median_worst(rows_result.rows),
        "sectors": sector_stats_from_result(result),
    }
    return render(request, "analytics/top_performers.html", context)
