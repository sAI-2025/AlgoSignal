from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.core.cache import cache

from apps.fetcher.models import FetchRun, FetchSchedule, JobType
from apps.fetcher.services import locking, scheduler
from apps.fetcher.services.jobs import constituents, daily_candles, fundamentals
from apps.fetcher.services.jobs.base import JobResult

IST = ZoneInfo("Asia/Kolkata")
FRIDAY_10 = datetime(2026, 11, 20, 10, 0, tzinfo=IST)  # a market day, before 16:15


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _stub_jobs(monkeypatch, result: JobResult | None = None) -> list:
    """Replace every job's run() with a stub and return the call list."""
    calls: list[JobType] = []
    payload = result or JobResult(total_items=1, success_items=1, rows_written=1, message="ok")

    def make(job_type):
        def _run(ctx):
            calls.append(job_type)
            return payload

        return _run

    monkeypatch.setattr(daily_candles, "run", make(JobType.DAILY_CANDLES))
    monkeypatch.setattr(fundamentals, "run", make(JobType.FUNDAMENTALS))
    monkeypatch.setattr(constituents, "run", make(JobType.CONSTITUENTS_SYNC))
    return calls


def _make_all_due() -> None:
    scheduler.ensure_default_schedules()
    FetchSchedule.objects.update(
        enabled=True,
        only_market_days=False,
        earliest_time_ist=None,
        next_run_at=None,
    )


# --- is_due gating -----------------------------------------------------------


def test_is_due_false_when_disabled() -> None:
    schedule = FetchSchedule(job_type=JobType.FUNDAMENTALS, enabled=False, next_run_at=None)
    assert scheduler.is_due(schedule, now=FRIDAY_10) is False


def test_is_due_false_before_next_run() -> None:
    schedule = FetchSchedule(
        job_type=JobType.FUNDAMENTALS, enabled=True, next_run_at=FRIDAY_10 + timedelta(hours=1)
    )
    assert scheduler.is_due(schedule, now=FRIDAY_10) is False


def test_is_due_true_when_next_run_passed() -> None:
    schedule = FetchSchedule(
        job_type=JobType.FUNDAMENTALS, enabled=True, next_run_at=FRIDAY_10 - timedelta(hours=1)
    )
    assert scheduler.is_due(schedule, now=FRIDAY_10) is True


def test_is_due_false_on_weekend() -> None:
    sunday = datetime(2026, 11, 22, 10, 0, tzinfo=IST)
    schedule = FetchSchedule(
        job_type=JobType.DAILY_CANDLES, enabled=True, next_run_at=None, only_market_days=True
    )
    assert scheduler.is_due(schedule, now=sunday) is False


def test_is_due_false_before_earliest_time() -> None:
    schedule = FetchSchedule(
        job_type=JobType.DAILY_CANDLES,
        enabled=True,
        next_run_at=None,
        only_market_days=False,
        earliest_time_ist=time(16, 15),
    )
    assert scheduler.is_due(schedule, now=FRIDAY_10) is False


# --- run_due_schedules -------------------------------------------------------


@pytest.mark.django_db
def test_runs_all_due_jobs_and_advances_next_run(monkeypatch) -> None:
    calls = _stub_jobs(monkeypatch)
    _make_all_due()

    runs = scheduler.run_due_schedules(now=FRIDAY_10, trigger="CLI")

    assert len(runs) == 3
    assert sorted(calls) == sorted(
        [JobType.DAILY_CANDLES, JobType.FUNDAMENTALS, JobType.CONSTITUENTS_SYNC]
    )
    for run in runs:
        assert run.status == FetchRun.Status.SUCCESS
    for schedule in FetchSchedule.objects.all():
        assert schedule.next_run_at is not None
        assert schedule.next_run_at > FRIDAY_10


@pytest.mark.django_db
def test_no_overlap_when_run_active(monkeypatch) -> None:
    calls = _stub_jobs(monkeypatch)
    _make_all_due()
    # A fresh RUNNING fundamentals run already exists.
    schedule = FetchSchedule.objects.get(job_type=JobType.FUNDAMENTALS)
    FetchRun.objects.create(
        job_type=JobType.FUNDAMENTALS,
        schedule=schedule,
        status=FetchRun.Status.RUNNING,
        started_at=FRIDAY_10,
        heartbeat_at=FRIDAY_10,
    )

    runs = scheduler.run_due_schedules(now=FRIDAY_10, trigger="CLI")

    job_types = {r.job_type for r in runs}
    assert JobType.FUNDAMENTALS not in job_types
    assert JobType.FUNDAMENTALS not in calls


@pytest.mark.django_db
def test_stale_running_run_is_failed_and_rerun(monkeypatch) -> None:
    calls = _stub_jobs(monkeypatch)
    _make_all_due()
    schedule = FetchSchedule.objects.get(job_type=JobType.FUNDAMENTALS)
    stale = FetchRun.objects.create(
        job_type=JobType.FUNDAMENTALS,
        schedule=schedule,
        status=FetchRun.Status.RUNNING,
        started_at=FRIDAY_10 - timedelta(hours=2),
        heartbeat_at=FRIDAY_10 - timedelta(hours=2),
    )

    scheduler.run_due_schedules(now=FRIDAY_10, trigger="CLI")

    stale.refresh_from_db()
    assert stale.status == FetchRun.Status.FAILED
    assert JobType.FUNDAMENTALS in calls


@pytest.mark.django_db
def test_cooling_down_records_partial_and_skips_job(monkeypatch, settings) -> None:
    calls = _stub_jobs(monkeypatch)
    _make_all_due()
    cache.set(
        locking.COOLDOWN_KEY,
        FRIDAY_10 + timedelta(minutes=20),
        settings.PROVIDER_COOLDOWN_SECONDS,
    )

    runs = scheduler.run_due_schedules(now=FRIDAY_10, trigger="CLI")

    assert calls == []  # no job actually ran
    assert len(runs) == 3
    for run in runs:
        assert run.status == FetchRun.Status.PARTIAL
        assert "cooling down" in run.message


@pytest.mark.django_db
def test_failed_job_marks_run_failed(monkeypatch) -> None:
    failed = JobResult(total_items=1, success_items=0, failed_items=1, message="boom")
    _stub_jobs(monkeypatch, result=failed)
    _make_all_due()

    runs = scheduler.run_due_schedules(now=FRIDAY_10, trigger="CLI")

    assert all(run.status == FetchRun.Status.FAILED for run in runs)
