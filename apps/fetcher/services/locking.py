"""Provider circuit breaker and run-overlap guards (ARCHITECTURE §8.4).

Circuit-breaker state lives in the Django cache so it self-clears:

* ``provider:cooldown``         -- TTL 1800 s; set after too many consecutive rate limits.
* ``provider:rate_limit_streak`` -- consecutive rate-limited failures counter.

Run-overlap is guarded with a fresh-heartbeat ``FetchRun(status=RUNNING)`` check, which is
portable across SQLite and PostgreSQL (no ``select_for_update`` needed).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.fetcher.models import FetchRun

logger = logging.getLogger(__name__)

COOLDOWN_KEY = "provider:cooldown"
STREAK_KEY = "provider:rate_limit_streak"


def _now(now: datetime | None) -> datetime:
    return now or timezone.now()


def is_cooling_down(*, now: datetime | None = None, cache_backend=cache) -> bool:
    """Return True when the provider is in a post-circuit-breaker cool-down."""
    return cache_backend.get(COOLDOWN_KEY) is not None


def cooldown_remaining_seconds(*, now: datetime | None = None, cache_backend=cache) -> int:
    """Seconds left in the cool-down window, or 0 if not cooling down."""
    expiry = cache_backend.get(COOLDOWN_KEY)
    if expiry is None:
        return 0
    remaining = (expiry - _now(now)).total_seconds()
    return max(0, int(remaining))


def register_rate_limit(*, cache_backend=cache) -> int:
    """Increment the consecutive-rate-limit streak; trip the breaker at the threshold."""
    threshold = getattr(settings, "PROVIDER_CIRCUIT_THRESHOLD", 5)
    streak = int(cache_backend.get(STREAK_KEY, 0)) + 1
    if streak >= threshold:
        cooldown_seconds = getattr(settings, "PROVIDER_COOLDOWN_SECONDS", 1800)
        cache_backend.set(
            COOLDOWN_KEY,
            timezone.now() + timedelta(seconds=cooldown_seconds),
            cooldown_seconds,
        )
        logger.warning("Provider circuit breaker tripped after %s consecutive rate limits", streak)
    cache_backend.set(STREAK_KEY, streak, threshold * 60)
    return streak


def reset_rate_limit_streak(*, cache_backend=cache) -> None:
    """Clear the streak after a successful call (and therefore keep the breaker closed)."""
    cache_backend.delete(STREAK_KEY)


def has_active_run(
    job_type: str,
    *,
    now: datetime | None = None,
    heartbeat_timeout_min: int | None = None,
) -> bool:
    """True when a fresh ``RUNNING`` run for *job_type* already exists.

    Runs whose heartbeat is older than the timeout are considered stale, marked ``FAILED``
    and ignored so a stuck run cannot block the schedule forever.
    """
    current = _now(now)
    timeout = getattr(settings, "FETCH_HEARTBEAT_TIMEOUT_MIN", 15)
    if heartbeat_timeout_min is not None:
        timeout = heartbeat_timeout_min

    cutoff = current - timedelta(minutes=timeout)
    stale = FetchRun.objects.filter(
        job_type=job_type,
        status=FetchRun.Status.RUNNING,
    ).exclude(heartbeat_at__gt=cutoff)

    if stale.exists():
        stale.update(
            status=FetchRun.Status.FAILED,
            finished_at=current,
            message="Stale run (heartbeat timed out) — auto-failed",
        )

    return FetchRun.objects.filter(
        job_type=job_type,
        status=FetchRun.Status.RUNNING,
        heartbeat_at__gt=cutoff,
    ).exists()
