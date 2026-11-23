"""CONSTITUENTS_SYNC job: re-import the index constituent CSV.

Delegates to ``companies.services.importer`` and maps its summary into a :class:`JobResult`.
This doubles as the import error log (ARCHITECTURE §8.2): row-level errors land in
``FetchRun.errors``.
"""

from __future__ import annotations

import logging

from apps.companies.services.importer import ImporterError, run_constituent_import
from apps.fetcher.services.jobs.base import JobContext, JobResult

logger = logging.getLogger(__name__)


def run(ctx: JobContext) -> JobResult:
    try:
        summary = run_constituent_import(index_code=ctx.universe_index)
    except ImporterError as exc:
        return JobResult(
            total_items=1,
            failed_items=1,
            errors=[{"symbol": "", "error_code": "IMPORT_FAILED", "message": str(exc)}],
            message=f"constituents sync failed: {exc}",
        )

    return JobResult(
        total_items=summary.total_rows,
        success_items=summary.processed_rows,
        failed_items=summary.skipped_rows,
        rows_written=summary.added_companies + summary.updated_companies,
        errors=summary.errors,
        message=(
            f"constituents: +{summary.added_companies} ~{summary.updated_companies} "
            f"skip={summary.skipped_rows} closed={summary.closed_memberships}"
        ),
    )
