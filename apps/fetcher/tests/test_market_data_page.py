from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from apps.fetcher.models import FetchRun, FetchSchedule, JobType
from apps.fetcher.selectors import heartbeat_age_seconds, scheduler_is_stale
from apps.fetcher.services.jobs.base import JobResult


@pytest.fixture
def staff(db):
    return User.objects.create_user(username="ops", password="pw12345", is_staff=True)


@pytest.fixture
def regular(db):
    return User.objects.create_user(username="viewer", password="pw12345")


@pytest.fixture
def schedule(db):
    return FetchSchedule.objects.create(job_type=JobType.DAILY_CANDLES, enabled=True)


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_market_data_renders(client, staff, schedule):
    client.force_login(staff)
    response = client.get(reverse("fetcher:market_data"))
    assert response.status_code == 200
    assert b"Schedules" in response.content
    assert b"Daily candles" in response.content


@pytest.mark.django_db
def test_market_data_requires_auth(client):
    response = client.get(reverse("fetcher:market_data"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_toggle_enabled(client, staff, schedule):
    client.force_login(staff)
    response = client.post(
        reverse("fetcher:market_data"),
        {"action": "toggle", "schedule_id": schedule.id},
    )
    assert response.status_code == 200
    schedule.refresh_from_db()
    assert schedule.enabled is False


@pytest.mark.django_db
def test_interval_validation(client, staff, schedule):
    client.force_login(staff)
    bad = client.post(
        reverse("fetcher:market_data"),
        {"action": "interval", "schedule_id": schedule.id, "interval_hours": "999"},
    )
    assert b"between 1 and 168" in bad.content
    schedule.refresh_from_db()
    assert schedule.interval_hours == 24  # unchanged default

    ok = client.post(
        reverse("fetcher:market_data"),
        {"action": "interval", "schedule_id": schedule.id, "interval_hours": "6"},
    )
    schedule.refresh_from_db()
    assert schedule.interval_hours == 6
    assert ok.status_code == 200


@pytest.mark.django_db
def test_run_now_creates_run(client, staff, schedule, monkeypatch):
    from apps.fetcher.services import scheduler as scheduler_module

    monkeypatch.setitem(
        scheduler_module._JOBS,
        JobType.DAILY_CANDLES,
        type(
            "Stub", (), {"run": staticmethod(lambda ctx: JobResult(total_items=2, success_items=2))}
        ),
    )

    client.force_login(staff)
    response = client.post(
        reverse("fetcher:market_data"),
        {"action": "run_now", "schedule_id": schedule.id},
    )
    assert response.status_code == 200
    run = FetchRun.objects.latest("started_at")
    assert run.trigger == FetchRun.Trigger.MANUAL
    assert run.status == FetchRun.Status.SUCCESS


@pytest.mark.django_db
def test_toggle_requires_staff(client, regular, schedule):
    client.force_login(regular)
    response = client.post(
        reverse("fetcher:market_data"),
        {"action": "toggle", "schedule_id": schedule.id},
    )
    assert b"Only staff can change market-data settings" in response.content
    schedule.refresh_from_db()
    assert schedule.enabled is True  # unchanged


@pytest.mark.django_db
def test_interval_requires_staff(client, regular, schedule):
    client.force_login(regular)
    response = client.post(
        reverse("fetcher:market_data"),
        {"action": "interval", "schedule_id": schedule.id, "interval_hours": "6"},
    )
    assert b"Only staff can change market-data settings" in response.content
    schedule.refresh_from_db()
    assert schedule.interval_hours == 24  # unchanged


@pytest.mark.django_db
def test_run_now_non_staff_blocked(client, regular, schedule):
    client.force_login(regular)
    response = client.post(
        reverse("fetcher:market_data"),
        {"action": "run_now", "schedule_id": schedule.id},
    )
    assert b"Only staff can change market-data settings" in response.content
    assert not FetchRun.objects.exists()


@pytest.mark.django_db
def test_scheduler_is_stale_when_never_run():
    assert scheduler_is_stale() is True
    assert heartbeat_age_seconds() is None


@pytest.mark.django_db
def test_scheduler_heartbeat_fresh():
    cache.set("scheduler:last_tick", timezone.now(), 3600)
    assert scheduler_is_stale() is False
    assert heartbeat_age_seconds() is not None
    assert heartbeat_age_seconds() < 5
