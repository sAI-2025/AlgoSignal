from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.fetcher.models import FetchRun, FetchSchedule, JobType


@pytest.mark.django_db
def test_job_type_is_unique() -> None:
    FetchSchedule.objects.create(job_type=JobType.FUNDAMENTALS)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FetchSchedule.objects.create(job_type=JobType.FUNDAMENTALS)


@pytest.mark.django_db
def test_interval_hours_check_constraint() -> None:
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FetchSchedule.objects.create(job_type=JobType.DAILY_CANDLES, interval_hours=0)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FetchSchedule.objects.create(job_type=JobType.DAILY_CANDLES, interval_hours=169)


@pytest.mark.django_db
def test_batch_size_check_constraint() -> None:
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FetchSchedule.objects.create(job_type=JobType.FUNDAMENTALS, batch_size=0)


@pytest.mark.django_db
def test_throttle_non_negative_constraint() -> None:
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FetchSchedule.objects.create(
                job_type=JobType.FUNDAMENTALS, throttle_seconds=Decimal("-1.0")
            )


@pytest.mark.django_db
def test_valid_schedule_creates() -> None:
    schedule = FetchSchedule.objects.create(job_type=JobType.FUNDAMENTALS, interval_hours=12)
    assert schedule.pk is not None
    assert schedule.throttle_seconds == Decimal("2.0")


@pytest.mark.django_db
def test_fetch_run_defaults() -> None:
    from django.utils import timezone

    run = FetchRun.objects.create(job_type=JobType.FUNDAMENTALS, started_at=timezone.now())
    assert run.status == FetchRun.Status.RUNNING
    assert run.errors == []
    assert run.total_items == 0
