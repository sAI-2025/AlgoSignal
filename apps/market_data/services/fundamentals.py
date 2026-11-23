"""Fundamentals collection: fetch ``Ticker.info`` and upsert the latest snapshot.

Only the single latest ``CompanyMetrics`` row per company is kept (data tier T3,
ARCHITECTURE §6.1). This service is the *how*; scheduling/throttling policy and retry
policy live in the ``fetcher`` app.

The actual network call is injectable via ``fetch_fn`` so the job layer can wrap it with
``fetcher.services.retry.call_with_retry`` while this module keeps ownership of throttling,
mapping and persistence.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from django.utils import timezone

from apps.companies.models import Company
from apps.market_data.models import CompanyMetrics, Instrument
from apps.market_data.services.fundamentals_mapper import map_company_info
from apps.market_data.services.providers.base import ProviderError
from apps.market_data.services.providers.yfinance_provider import YFinanceProvider

logger = logging.getLogger(__name__)


@dataclass
class MetricsResult:
    company_id: int
    updated: bool = False
    missing_fields: list[str] = field(default_factory=list)


@dataclass
class BatchResult:
    total: int = 0
    success: int = 0
    failed: int = 0
    rows_written: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)


def resolve_provider_symbol(company: Company) -> str:
    """Return the provider symbol for *company*, preferring its mapped instrument."""
    instrument = (
        Instrument.objects.filter(company=company, exchange=Instrument.Exchange.NSE)
        .order_by("id")
        .first()
    )
    if instrument and instrument.provider_symbol:
        return instrument.provider_symbol
    return YFinanceProvider.to_provider_symbol(company.nse_code)


def _record_error(errors: list[dict[str, str]], symbol: str, exc: Exception) -> None:
    errors.append({"symbol": symbol, "error_code": type(exc).__name__, "message": str(exc)})


def _upsert_metrics(company: Company, raw: dict, *, source: str, now: datetime) -> MetricsResult:
    payload = map_company_info(raw)
    missing = sorted(name for name, value in payload.items() if value is None)
    CompanyMetrics.objects.update_or_create(
        company=company,
        defaults={
            **payload,
            "currency": "INR",
            "source": source,
            "fetched_at": now,
        },
    )
    return MetricsResult(company_id=company.id, updated=True, missing_fields=missing)


def fetch_and_store_metrics(
    company: Company,
    *,
    provider=None,
    now: datetime | None = None,
    fetch_fn: Callable[[Company], dict] | None = None,
) -> MetricsResult:
    """Fetch one company's info and upsert its ``CompanyMetrics`` snapshot."""
    provider = provider or YFinanceProvider()
    timestamp = now or timezone.now()

    if fetch_fn is None:
        symbol = resolve_provider_symbol(company)

        def fetch_fn(_company: Company) -> dict:  # noqa: F811 - local default
            return provider.get_company_info(symbol)

    raw = fetch_fn(company)
    return _upsert_metrics(company, raw, source=provider.name, now=timestamp)


def fetch_metrics_for_universe(
    *,
    batch_size: int = 10,
    throttle_seconds: float = 2.0,
    provider=None,
    now: datetime | None = None,
    fetch_fn: Callable[[Company], dict] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> BatchResult:
    """Refresh ``CompanyMetrics`` for all active companies, throttled and fault-tolerant.

    A single failing ticker is recorded in ``result.errors`` and never aborts the batch.
    """
    provider = provider or YFinanceProvider()
    timestamp = now or timezone.now()
    result = BatchResult()

    company_ids = list(
        Company.objects.filter(is_active=True).order_by("id").values_list("id", flat=True)
    )
    result.total = len(company_ids)
    companies = Company.objects.in_bulk(company_ids)

    for index, company_id in enumerate(company_ids, start=1):
        company = companies[company_id]
        try:
            metrics = fetch_and_store_metrics(
                company, provider=provider, now=timestamp, fetch_fn=fetch_fn
            )
        except ProviderError as exc:
            result.failed += 1
            _record_error(result.errors, company.nse_code, exc)
            logger.warning("Fundamentals fetch failed for %s: %s", company.nse_code, exc)
        else:
            result.success += 1
            result.rows_written += int(metrics.updated)

        if index < result.total and throttle_seconds > 0:
            sleep(max(0.0, throttle_seconds + random.uniform(-0.5, 0.5)))  # noqa: S311
        if index % max(1, batch_size) == 0 and index < result.total:
            sleep(10)

    return result
