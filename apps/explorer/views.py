from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from apps.companies.models import Company
from apps.explorer.services.company_view import DETAIL_PERIODS, build_company_detail
from apps.explorer.services.search import search_companies, sectors
from apps.market_data.selectors import company_candles

TABS = ["overview", "chart", "fundamentals", "signals", "history"]


@login_required
def explorer_home(request):
    query = request.GET.get("q", "").strip()
    sector = request.GET.get("sector") or None
    results = search_companies(query, limit=50, sector=sector) if (query or sector) else []
    context = {
        "query": query,
        "sector": sector,
        "results": results,
        "sectors": sectors(),
    }
    return render(request, "explorer/explorer_home.html", context)


@login_required
def search_api(request):
    query = request.GET.get("q", "")
    sector = request.GET.get("sector") or None
    return JsonResponse({"results": search_companies(query, limit=8, sector=sector)})


@login_required
def company_detail(request, nse_code: str):
    company = get_object_or_404(Company, nse_code=nse_code.upper())
    tab = request.GET.get("tab", "overview")
    if tab not in TABS:
        tab = "overview"

    detail = build_company_detail(company)
    context = {
        "detail": detail,
        "company": company,
        "tab": tab,
        "tabs": TABS,
        "periods": DETAIL_PERIODS,
        "price_history": None,
        "pagination": None,
    }

    if tab == "history":
        paginator = Paginator(company_candles(company.id), 25)
        page_number = request.GET.get("page", 1)
        page = paginator.get_page(page_number)
        context["price_history"] = page.object_list
        context["pagination"] = page

    return render(request, "explorer/company_detail.html", context)
