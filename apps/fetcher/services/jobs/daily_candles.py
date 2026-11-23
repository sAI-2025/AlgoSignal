"""DAILY_CANDLES job: incremental daily OHLCV update from stored history.

Delegates to ``market_data`` (Phase 5). Only completed candles are written; the fetch
window is inferred incrementally from the last stored bar per company.
"""

from __future__ import annotations

import logging

from apps.fetcher.services.jobs.base import JobContext, JobResult
from apps.market_data.models import Instrument
from apps.market_data.services.historical_data import backfill_company_history

logger = logging.getLogger(__name__)


def run(ctx: JobContext) -> JobResult:
    result = JobResult()

    instruments = Instrument.objects.select_related("company").filter(
        exchange=Instrument.Exchange.NSE,
        company__is_active=True,
    )

    for instrument in instruments.order_by("company__nse_code"):
        result.total_items += 1
        try:
            saved = backfill_company_history(instrument, end=ctx.now.date())
        except Exception as exc:  # noqa: BLE001 - a single ticker must never abort the batch
            result.failed_items += 1
            result.errors.append(
                {
                    "symbol": instrument.company.nse_code,
                    "error_code": type(exc).__name__,
                    "message": str(exc),
                }
            )
            logger.warning("Daily candles failed for %s: %s", instrument.company.nse_code, exc)
            continue

        result.success_items += 1
        result.rows_written += saved.written_rows

    result.message = f"daily candles: {result.success_items}/{result.total_items} ok"
    return result
