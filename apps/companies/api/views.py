"""Companies API views (S2). Thin HTTP layer delegating to selectors/services."""

from __future__ import annotations

from datetime import UTC, datetime

from django.core.paginator import Paginator
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.companies.api.serializers import (
    CompanyDetailSerializer,
    CompanyImportSerializer,
    CompanyListQuerySerializer,
    CompanyMetricsSerializer,
    CompanySerializer,
)
from apps.companies.models import Company
from apps.companies.selectors import list_companies, sectors
from apps.companies.services.importer import ImporterError, run_constituent_import
from apps.core.api.permissions import IsStaff
from apps.core.api.throttling import CompanyImportRateThrottle, SearchRateThrottle
from apps.market_data.models import Instrument
from apps.market_data.services.fundamentals import fetch_and_store_metrics
from apps.market_data.services.historical_data import backfill_company_history
from apps.market_data.services.providers.yfinance_provider import YFinanceProvider


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([SearchRateThrottle])
def company_list(request):
    """List companies with optional search/sector filter and ordering (paginated)."""
    query_serializer = CompanyListQuerySerializer(data=request.query_params)
    query_serializer.is_valid(raise_exception=True)
    data = query_serializer.validated_data

    rows = list_companies(
        query=data.get("q") or None,
        sector=data.get("sector") or None,
        ordering=data["ordering"],
        reverse=(data["dir"] == "desc"),
    )

    paginator = Paginator(rows, data["page_size"])
    page = paginator.get_page(data["page"])

    return Response(
        {
            "results": CompanySerializer(page.object_list, many=True).data,
            "pagination": {
                "page": page.number,
                "page_size": data["page_size"],
                "total": paginator.count,
                "num_pages": paginator.num_pages,
                "has_next": page.has_next(),
                "has_previous": page.has_previous(),
            },
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([SearchRateThrottle])
def company_detail(request, nse_code):
    """Single company detail."""
    company = Company.objects.filter(nse_code__iexact=nse_code).first()
    if company is None:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "Company not found."}},
            status=404,
        )
    metrics = getattr(company, "metrics", None)
    payload = CompanyDetailSerializer(
        {
            "nse_code": company.nse_code,
            "company_name": company.company_name,
            "bse_code": company.bse_code,
            "isin": company.isin,
            "sector": company.sector,
            "industry": company.industry,
            "description": company.description,
            "is_active": company.is_active,
            "price": float(metrics.current_price)
            if metrics and metrics.current_price is not None
            else None,
            "metrics_fetched_at": metrics.fetched_at if metrics else None,
        }
    ).data
    return Response(payload)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([SearchRateThrottle])
def company_metrics(request, nse_code):
    """Latest fundamentals snapshot for a company."""
    company = Company.objects.filter(nse_code__iexact=nse_code).first()
    if company is None:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "Company not found."}},
            status=404,
        )
    metrics = getattr(company, "metrics", None)
    if metrics is None:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "No fundamentals snapshot."}},
            status=404,
        )
    return Response(
        CompanyMetricsSerializer(
            {
                field.name: getattr(metrics, field.name)
                for field in metrics._meta.fields
                if field.name not in ("id", "company", "created_at", "updated_at")
            }
        ).data
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([SearchRateThrottle])
def company_refresh_metrics(request, nse_code):
    """Re-fetch fundamentals snapshot for a single company (refresh action)."""
    company = Company.objects.filter(nse_code__iexact=nse_code).first()
    if company is None:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "Company not found."}},
            status=404,
        )
    try:
        fetch_and_store_metrics(company)
    except Exception as exc:  # noqa: BLE001
        return Response(
            {"error": {"code": "REFRESH_FAILED", "message": str(exc)}},
            status=502,
        )
    metrics = getattr(company, "metrics", None)
    if metrics is None:
        return Response(
            {"error": {"code": "NOT_FOUND", "message": "No fundamentals snapshot."}},
            status=404,
        )
    return Response(
        CompanyMetricsSerializer(
            {
                field.name: getattr(metrics, field.name)
                for field in metrics._meta.fields
                if field.name not in ("id", "company", "created_at", "updated_at")
            }
        ).data
    )


@api_view(["POST"])
@permission_classes([IsStaff])
@throttle_classes([CompanyImportRateThrottle])
def company_import(request):
    """Run the constituent import (staff only)."""
    CompanyImportSerializer(data=request.data or {}).is_valid(raise_exception=True)
    index_code = str(request.data.get("index_code") or "^NSEI")
    try:
        summary = run_constituent_import(index_code)
    except ImporterError as exc:
        return Response({"error": {"code": "IMPORT_ERROR", "message": str(exc)}}, status=502)

    # Backfill 1 year of candles for companies missing instruments/data.
    total_written = 0
    provider = YFinanceProvider()
    for company in Company.objects.filter(is_active=True):
        instrument, _ = Instrument.objects.get_or_create(
            exchange=Instrument.Exchange.NSE,
            company=company,
            defaults={
                "tradingsymbol": company.nse_code.upper(),
                "provider_symbol": f"{company.nse_code.upper()}.NS",
                "instrument_type": "EQ",
            },
        )
        try:
            symbol = provider.to_provider_symbol(company.nse_code)
            info = provider.get_company_info(symbol)
            epoch_ms = info.get("firstTradeDateEpochUtc")
            listing_date = None
            if epoch_ms is not None:
                listing_date = datetime.fromtimestamp(
                    int(epoch_ms) / 1000, tz=UTC
                ).date()
            result = backfill_company_history(
                instrument, years=1, listing_date=listing_date
            )
            total_written += result.written_rows
        except Exception:  # noqa: BLE001
            pass

    summary_dict = {
        "index_code": summary.index_code,
        "source_url": summary.source_url,
        "source_sha256": summary.source_sha256,
        "total_rows": summary.total_rows,
        "processed_rows": summary.processed_rows,
        "added_companies": summary.added_companies,
        "updated_companies": summary.updated_companies,
        "skipped_rows": summary.skipped_rows,
        "closed_memberships": summary.closed_memberships,
        "skipped_unchanged": summary.skipped_unchanged,
        "errors": summary.errors,
        "candles_written": total_written,
    }
    return Response(summary_dict)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([SearchRateThrottle])
def company_sectors(request):
    """Distinct sector list for filter tiles."""
    return Response({"sectors": sectors()})
