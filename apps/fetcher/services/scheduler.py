"""Scheduler: decide which fetch jobs are due and run them exactly once each tick.

The OS cron / Task Scheduler runs ``manage.py run_scheduler`` roughly every 10 minutes.
This module reads the ``FetchSchedule`` rows from the DB (not the crontab) and runs any job
whose ``next_run_at`` has passed, subject to market-day / earliest-time gates and the
no-overlap lock (ARCHITECTURE §8.1).
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.market_hours import is_market_day, to_ist
from apps.fetcher.models import FetchRun, FetchSchedule, JobType
from apps.fetcher.services import locking
from apps.fetcher.services.jobs import constituents, daily_candles, fundamentals
from apps.fetcher.services.jobs.base import JobContext, JobResult

logger = logging.getLogger(__name__)

# job_type -> job module (each exposes ``run(ctx) -> JobResult``)
_JOBS = {
    JobType.DAILY_CANDLES: daily_candles,
    JobType.FUNDAMENTALS: fundamentals,
    JobType.CONSTITUENTS_SYNC: constituents,
}

_DEFAULT_SCHEDULES = {
    JobType.DAILY_CANDLES: {
        "interval_hours": 24,
        "only_market_days": True,
        "earliest_time_ist": time(16, 15),
        "batch_size": 10,
        "throttle_seconds": 3.0,
    },
    JobType.FUNDAMENTALS: {
        "interval_hours": 12,
        "only_market_days": False,
        "earliest_time_ist": None,
        "batch_size": 10,
        "throttle_seconds": 2.0,
    },
    JobType.CONSTITUENTS_SYNC: {
        "interval_hours": 168,
        "only_market_days": False,
        "earliest_time_ist": None,
        "batch_size": 10,
        "throttle_seconds": 2.0,
    },
}


def ensure_default_schedules() -> None:
    """Create the three default schedules if missing (idempotent)."""
    index_code = settings.INDEX_UNIVERSE
    for job_type, defaults in _DEFAULT_SCHEDULES.items():
        FetchSchedule.objects.get_or_create(
            job_type=job_type,
            defaults={"universe_index": index_code, **defaults},
        )


def is_due(schedule: FetchSchedule, *, now: datetime) -> bool:
    """Return True when *schedule* should run at *now*."""
    if not schedule.enabled:
        return False
    if schedule.next_run_at is not None and schedule.next_run_at > now:
        return False
    if schedule.only_market_days and not is_market_day(now):
        return False
    if schedule.earliest_time_ist is not None:
        if to_ist(now).time() < schedule.earliest_time_ist:
            return False
    return True


def _final_status(result: JobResult) -> str:
    if result.failed_items == 0:
        return FetchRun.Status.SUCCESS
    if result.success_items > 0 or result.rows_written > 0:
        return FetchRun.Status.PARTIAL
    return FetchRun.Status.FAILED


@transaction.atomic
def _claim(schedule: FetchSchedule, *, now: datetime, trigger: str) -> FetchRun:
    """Create a RUNNING FetchRun and advance bookkeeping. Caller guarantees no active run."""
    run = FetchRun.objects.create(
        job_type=schedule.job_type,
        schedule=schedule,
        trigger=trigger,
        status=FetchRun.Status.RUNNING,
        started_at=now,
        heartbeat_at=now,
    )
    schedule.last_started_at = now
    schedule.save(update_fields=["last_started_at"])
    return run


def _finalize(run: FetchRun, schedule: FetchSchedule, result: JobResult, *, now: datetime) -> None:
    status = _final_status(result)
    run.status = status
    run.finished_at = now
    run.total_items = result.total_items
    run.success_items = result.success_items
    run.failed_items = result.failed_items
    run.rows_written = result.rows_written
    run.errors = result.errors
    run.message = result.message[:500]
    run.save()

    schedule.next_run_at = now + timedelta(hours=schedule.interval_hours)
    schedule.last_finished_at = now
    schedule.last_status = status
    schedule.save(update_fields=["next_run_at", "last_finished_at", "last_status", "updated_at"])


def _run_one(schedule: FetchSchedule, *, now: datetime, trigger: str) -> FetchRun:
    job = _JOBS[schedule.job_type]
    ctx = JobContext(
        now=now,
        batch_size=schedule.batch_size,
        throttle_seconds=float(schedule.throttle_seconds),
        universe_index=schedule.universe_index,
    )
    run = _claim(schedule, now=now, trigger=trigger)
    try:
        result = job.run(ctx)
    except Exception as exc:  # noqa: BLE001 - record a failed run, never crash the tick
        logger.exception("Job %s raised", schedule.job_type)
        result = JobResult(
            total_items=0,
            failed_items=1,
            errors=[{"symbol": "", "error_code": type(exc).__name__, "message": str(exc)}],
            message=f"job error: {exc}",
        )
    _finalize(run, schedule, result, now=now)
    return run


def run_now(
    schedule: FetchSchedule,
    *,
    now: datetime | None = None,
    trigger: str = "MANUAL",
) -> FetchRun:
    """Run one schedule immediately, bypassing the due-gate.

    Respects the active-run lock and the provider cool-down; raises ``RuntimeError`` with a
    user-facing message when either would prevent the run. Used by the Market Data page's
    "Run now" control (PRD S6).
    """
    now = now or timezone.now()
    if locking.has_active_run(schedule.job_type, now=now):
        raise RuntimeError(f"A {schedule.get_job_type_display()} run is already active.")
    if locking.is_cooling_down(now=now):
        raise RuntimeError("Provider is cooling down after rate limits; try again shortly.")
    return _run_one(schedule, now=now, trigger=trigger)


def run_due_schedules(*, now: datetime | None = None, trigger: str = "CRON") -> list[FetchRun]:
    """Run every due schedule once. Returns the list of FetchRun rows created."""
    now = now or timezone.now()
    ensure_default_schedules()

    runs: list[FetchRun] = []
    schedules = FetchSchedule.objects.filter(enabled=True).order_by("job_type")
    for schedule in schedules:
        if not is_due(schedule, now=now):
            continue
        if locking.has_active_run(schedule.job_type, now=now):
            logger.info("Skipping %s: a run is already active", schedule.job_type)
            continue
        if locking.is_cooling_down(now=now):
            runs.append(
                _record_cooldown(schedule, now=now, trigger=trigger),
            )
            continue
        runs.append(_run_one(schedule, now=now, trigger=trigger))
    return runs


def _record_cooldown(schedule: FetchSchedule, *, now: datetime, trigger: str) -> FetchRun:
    """Record a PARTIAL run noting the provider is cooling down, and advance next_run_at."""
    remaining = locking.cooldown_remaining_seconds(now=now)
    run = FetchRun.objects.create(
        job_type=schedule.job_type,
        schedule=schedule,
        trigger=trigger,
        status=FetchRun.Status.PARTIAL,
        started_at=now,
        finished_at=now,
        heartbeat_at=now,
        message=f"skipped: provider cooling down ({remaining}s left)",
    )
    schedule.next_run_at = now + timedelta(hours=schedule.interval_hours)
    schedule.last_finished_at = now
    schedule.last_status = FetchRun.Status.PARTIAL
    schedule.save(update_fields=["next_run_at", "last_finished_at", "last_status", "updated_at"])
    return run
