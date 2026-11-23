"""Endpoint-scoped throttle classes (ARCHITECTURE §14 rate table)."""

from __future__ import annotations

from rest_framework.throttling import UserRateThrottle


class ChartRateThrottle(UserRateThrottle):
    rate = "120/min"


class LiveQuoteRateThrottle(UserRateThrottle):
    rate = "60/min"


class LiveIntradayRateThrottle(UserRateThrottle):
    rate = "30/min"


class ScannerRunRateThrottle(UserRateThrottle):
    rate = "10/min"


class ScannerSettingsRateThrottle(UserRateThrottle):
    rate = "30/min"


class TopPerformersRateThrottle(UserRateThrottle):
    rate = "60/min"


class MarketOverviewRateThrottle(UserRateThrottle):
    rate = "60/min"


class SearchRateThrottle(UserRateThrottle):
    rate = "120/min"


class FetcherSchedulesRateThrottle(UserRateThrottle):
    rate = "30/min"


class FetcherRunNowRateThrottle(UserRateThrottle):
    rate = "6/hour"


class FetcherBackfillRateThrottle(UserRateThrottle):
    rate = "6/hour"


class CoverageRateThrottle(UserRateThrottle):
    rate = "30/min"


class RefreshMetricsRateThrottle(UserRateThrottle):
    rate = "1/min"


class CompanyImportRateThrottle(UserRateThrottle):
    rate = "6/hour"
