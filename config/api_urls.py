"""REST API aggregator at ``/api/v1/`` (ARCHITECTURE §14).

Each app exposes its own thin API surface; this module aggregates them under a single
versioned base. Session auth + CSRF protect every endpoint; throttling is per-endpoint
(see ``apps.core.api.throttling`` and ``REST_FRAMEWORK`` settings).
"""

from django.urls import include, path

from apps.fetcher.api.views import coverage

urlpatterns = [
    path("companies/", include("apps.companies.api.urls")),
    path("analytics/", include("apps.analytics.api.urls")),
    path("scanner/", include("apps.scanner.api.urls")),
    path("explorer/", include("apps.explorer.api.urls")),
    path("dashboard/", include("apps.dashboard.api.urls")),
    path("fetcher/", include("apps.fetcher.api.urls")),
    path("live/", include("apps.market_data.api.urls")),
    path("charts/", include("apps.visualization.api.urls")),
    path("market-data/coverage/", coverage, name="market_data_coverage"),
]
