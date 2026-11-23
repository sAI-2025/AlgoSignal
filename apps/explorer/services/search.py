"""Company search for the Explorer (ARCHITECTURE §4.10, PRD S5a).

A *selector*: read-only, asks the companies table. Returns lightweight dicts so callers
(views, JSON API) can serialise without touching model internals.
"""

from __future__ import annotations

from django.db.models import Q

from apps.companies.models import Company

SEARCH_FIELDS = ("company_name", "nse_code")


def search_companies(query: str, *, limit: int = 8, sector: str | None = None) -> list[dict]:
    """Return up to *limit* active companies matching *query* (name or NSE code).

    An empty query returns the first companies alphabetically. ``sector`` optionally
    narrows the result set. Each row is a plain dict ready for JSON.
    """
    qs = Company.objects.filter(is_active=True)
    if sector:
        qs = qs.filter(sector=sector)

    term = (query or "").strip()
    if term:
        condition = Q()
        for field in SEARCH_FIELDS:
            condition |= Q(**{f"{field}__icontains": term})
        qs = qs.filter(condition)

    qs = qs.order_by("company_name")[:limit]
    return [
        {
            "nse_code": company.nse_code,
            "company_name": company.company_name,
            "sector": company.sector,
            "bse_code": company.bse_code,
        }
        for company in qs
    ]


def sectors(*, limit: int | None = None) -> list[str]:
    """Distinct, non-empty sectors for the Explorer sector tiles."""
    qs = (
        Company.objects.filter(is_active=True, sector__isnull=False)
        .exclude(sector="")
        .values_list("sector", flat=True)
        .distinct()
        .order_by("sector")
    )
    return list(qs[:limit]) if limit else list(qs)
