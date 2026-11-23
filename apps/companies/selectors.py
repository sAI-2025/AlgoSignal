"""Read-only queries for the Companies directory (ARCHITECTURE §4.10, PRD S2).

A *selector*: asks the companies table with optional search, sector filter and ordering.
Rows are enriched with the latest ``CompanyMetrics`` snapshot when present.
"""

from __future__ import annotations

from django.db.models import Q

from apps.companies.models import Company

SORT_FIELDS = {
    "name": "company_name",
    "symbol": "nse_code",
    "sector": "sector",
    "price": "metrics__current_price",
    "pe": "metrics__trailing_pe",
    "market_cap": "metrics__market_cap",
}


def list_companies(
    *,
    query: str | None = None,
    sector: str | None = None,
    ordering: str = "name",
    reverse: bool = False,
) -> list[dict]:
    """Return company rows for the directory, optionally filtered and sorted."""
    qs = Company.objects.filter(is_active=True).select_related("metrics")

    term = (query or "").strip()
    if term:
        qs = qs.filter(Q(company_name__icontains=term) | Q(nse_code__icontains=term))
    if sector:
        qs = qs.filter(sector=sector)

    sort_field = SORT_FIELDS.get(ordering, "company_name")
    qs = qs.order_by(("-" if reverse else "") + sort_field, "nse_code")

    rows = []
    for company in qs:
        metrics = getattr(company, "metrics", None)
        rows.append(
            {
                "nse_code": company.nse_code,
                "company_name": company.company_name,
                "sector": company.sector,
                "industry": company.industry,
                "price": float(metrics.current_price)
                if metrics and metrics.current_price
                else None,
                "trailing_pe": float(metrics.trailing_pe)
                if metrics and metrics.trailing_pe
                else None,
                "market_cap": float(metrics.market_cap) if metrics and metrics.market_cap else None,
            }
        )
    return rows


def sectors(*, limit: int | None = None) -> list[str]:
    qs = (
        Company.objects.filter(is_active=True, sector__isnull=False)
        .exclude(sector="")
        .values_list("sector", flat=True)
        .distinct()
        .order_by("sector")
    )
    return list(qs[:limit]) if limit else list(qs)
