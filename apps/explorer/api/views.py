"""Explorer API views (S5a typeahead search)."""

from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.api.throttling import SearchRateThrottle
from apps.explorer.api.serializers import SearchQuerySerializer, SearchResultSerializer
from apps.explorer.services.search import search_companies, sectors


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([SearchRateThrottle])
def search_api(request):
    """Typeahead company search by name or NSE code."""
    query = SearchQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    data = query.validated_data

    results = search_companies(
        data.get("q") or "", limit=data["limit"], sector=data.get("sector") or None
    )
    return Response(
        {
            "results": SearchResultSerializer(results, many=True).data,
            "sectors": sectors(),
        }
    )
