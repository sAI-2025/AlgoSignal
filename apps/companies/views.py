from __future__ import annotations

import re
from datetime import UTC, date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.companies.models import Company
from apps.companies.selectors import list_companies, sectors
from apps.market_data.models import Instrument
from apps.market_data.services.historical_data import backfill_company_history
from apps.market_data.services.providers.yfinance_provider import YFinanceProvider

ALLOWED_SECTORS = {
    "Energy", "Financial Services", "Information Technology", "Automobile",
    "Pharmaceuticals", "FMCG", "Metals & Mining", "Chemicals", "Cement & Cement Products",
    "Power", "Telecom", "Realty", "Consumer Durables", "Media & Entertainment",
    "Textiles", "Other",
}
SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9-]{0,19}$")


def validate_add_company(nse_code, name, sector, industry):
    """Return a dict of field -> error message for invalid Add Stock input."""
    errors = {}
    if not nse_code:
        errors["nse_code"] = "Symbol is required."
    elif not SYMBOL_RE.match(nse_code):
        errors["nse_code"] = "Use an uppercase NSE symbol (letters, digits, hyphens; max 20 chars)."
    elif Company.objects.filter(nse_code__iexact=nse_code).exists():
        errors["nse_code"] = f"{nse_code} is already added."
    if not name:
        errors["name"] = "Company name is required."
    elif len(name) < 2:
        errors["name"] = "Company name must be at least 2 characters."
    elif len(name) > 200:
        errors["name"] = "Company name must be at most 200 characters."
    if sector and sector not in ALLOWED_SECTORS:
        errors["sector"] = "Choose a sector from the list, or 'Other'."
    if industry and len(industry) > 150:
        errors["industry"] = "Industry must be at most 150 characters."
    return errors


def _detect_listing_date(nse_code: str) -> date | None:
    """Detect listing date from yfinance info.

    Tries ``firstTradeDateEpochUtc`` from ``Ticker.info``. Returns ``None`` when the
    provider is unavailable or the field is absent, so the caller can fall back to
    earliest candle or today-years.
    """
    provider = YFinanceProvider()
    symbol = provider.to_provider_symbol(nse_code)
    try:
        info = provider.get_company_info(symbol)
    except Exception:  # noqa: BLE001
        return None
    epoch_ms = info.get("firstTradeDateEpochUtc")
    if epoch_ms is None:
        return None
    try:
        return datetime.fromtimestamp(int(epoch_ms) / 1000, tz=UTC).date()
    except (ValueError, OSError, OverflowError):  # noqa: BLE001
        return None


@login_required
def companies_page(request):
    query = request.GET.get("q", "").strip()
    sector = request.GET.get("sector") or None
    ordering = request.GET.get("ordering", "name")
    reverse = request.GET.get("dir") == "desc"

    rows = list_companies(query=query, sector=sector, ordering=ordering, reverse=reverse)
    paginator = Paginator(rows, 50)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "query": query,
        "sector": sector,
        "ordering": ordering,
        "reverse": reverse,
        "sectors": sectors(),
        "companies": page.object_list,
        "pagination": page,
        "total": paginator.count,
    }
    return render(request, "companies/companies.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def add_company(request):
    """Add a single company/stock via the web UI."""
    if request.method == "POST":
        nse_code = (request.POST.get("nse_code") or "").strip().upper()
        name = (request.POST.get("name") or "").strip()
        sector = (request.POST.get("sector") or "").strip() or None
        industry = (request.POST.get("industry") or "").strip() or None

        errors = validate_add_company(nse_code, name, sector, industry)

        if not errors:
            company, _ = Company.objects.update_or_create(
                nse_code=nse_code,
                defaults={
                    "company_name": name,
                    "sector": sector,
                    "industry": industry,
                    "is_active": True,
                },
            )
            # Ensure an Instrument exists (yfinance symbol mapping) and backfill from
            # the listing date (not a fixed 1-year lookback) so charts render immediately.
            instrument, _ = Instrument.objects.get_or_create(
                exchange=Instrument.Exchange.NSE,
                company=company,
                defaults={
                    "tradingsymbol": nse_code,
                    "provider_symbol": f"{nse_code}.NS",
                    "instrument_type": "EQ",
                },
            )
            listing_date = _detect_listing_date(nse_code)
            try:
                result = backfill_company_history(
                    instrument, years=1, listing_date=listing_date
                )
                messages.success(
                    request,
                    f"Added {nse_code} — {name} ({result.written_rows} candles)",
                )
            except Exception as exc:  # noqa: BLE001
                messages.warning(
                    request,
                    f"Added {nse_code} — {name} (data fetch failed: {exc})",
                )
            return redirect(reverse("companies:list"))

        context = {
            "errors": errors,
            "form_data": request.POST,
            "allowed_sectors": sorted(ALLOWED_SECTORS),
        }
        return render(request, "companies/add_company.html", context)

    context = {"allowed_sectors": sorted(ALLOWED_SECTORS)}
    return render(request, "companies/add_company.html", context)
