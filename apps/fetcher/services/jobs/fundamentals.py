"""FUNDAMENTALS job: refresh ``CompanyMetrics`` for active companies.

Delegates the fetch to ``market_data.services.fundamentals`` (which owns throttling, mapping
and persistence) and injects a retry-wrapped provider call so transient/rate-limited failures
back off per policy. Consecutive rate limits trip the circuit breaker via ``locking``.
"""

from __future__ import annotations

import logging

from django.conf import settings

from apps.companies.models import Company
from apps.fetcher.services.jobs.base import JobContext, JobResult
from apps.fetcher.services.locking import register_rate_limit, reset_rate_limit_streak
from apps.fetcher.services.retry import call_with_retry
from apps.market_data.services.fundamentals import (
    fetch_metrics_for_universe,
    resolve_provider_symbol,
)
from apps.market_data.services.providers.base import ProviderRateLimited
from apps.market_data.services.providers.yfinance_provider import YFinanceProvider

logger = logging.getLogger(__name__)


def run(ctx: JobContext) -> JobResult:
    provider = ctx.provider or YFinanceProvider()

    def fetch_fn(company: Company) -> dict:
        symbol = resolve_provider_symbol(company)
        try:
            info = call_with_retry(
                lambda: provider.get_company_info(symbol),
                retries=getattr(settings, "PROVIDER_MAX_RETRIES", 3),
                transient_delays=getattr(settings, "PROVIDER_TRANSIENT_DELAYS", (5, 15, 45)),
                rate_limit_delays=getattr(settings, "PROVIDER_RATE_LIMIT_DELAYS", (30, 60, 120)),
            )
        except ProviderRateLimited:
            register_rate_limit()
            raise
        else:
            reset_rate_limit_streak()
            return info

    batch = fetch_metrics_for_universe(
        batch_size=ctx.batch_size,
        throttle_seconds=ctx.throttle_seconds,
        provider=provider,
        now=ctx.now,
        fetch_fn=fetch_fn,
    )

    return JobResult(
        total_items=batch.total,
        success_items=batch.success,
        failed_items=batch.failed,
        rows_written=batch.rows_written,
        errors=batch.errors,
        message=f"fundamentals: {batch.success}/{batch.total} ok",
    )
