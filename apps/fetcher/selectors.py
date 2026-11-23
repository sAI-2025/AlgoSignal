"""Read-only queries for the Market Data page (ARCHITECTURE §3.1, PRD S6).

A *selector*: asks schedules, runs and the scheduler heartbeat. No business logic, no writes.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.core.cache import cache
from django.utils import timezone

from apps.fetcher.models import FetchRun, FetchSchedule

HEARTBEAT_KEY = "scheduler:last_tick"
# The scheduler tick runs every ~10 min; warn when the heartbeat is older than 3× that.
STALE_AFTER = timedelta(minutes=30)


def all_schedules() -> list[FetchSchedule]:
    return list(FetchSchedule.objects.order_by("job_type"))


def recent_runs(
    *,
    job_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[FetchRun]:
    qs = FetchRun.objects.select_related("schedule").order_by("-started_at")
    if job_type:
        qs = qs.filter(job_type=job_type)
    if status:
        qs = qs.filter(status=status)
    return list(qs[:limit])


def scheduler_heartbeat() -> datetime | None:
    return cache.get(HEARTBEAT_KEY)


def heartbeat_age_seconds(*, now: datetime | None = None) -> int | None:
    """Seconds since the last scheduler tick, or ``None`` if it never ran."""
    heartbeat = scheduler_heartbeat()
    if heartbeat is None:
        return None
    return max(0, int(((_now(now)) - heartbeat).total_seconds()))


def scheduler_is_stale(*, now: datetime | None = None) -> bool:
    """True when no tick has been recorded recently enough (or never)."""
    age = heartbeat_age_seconds(now=now)
    return age is None or age > STALE_AFTER.total_seconds()


def _now(now: datetime | None) -> datetime:
    return now or timezone.now()
