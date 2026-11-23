from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.scanner.models import ScannerSetting


@pytest.fixture
def staff(db):
    return User.objects.create_user(username="staff", password="pw12345", is_staff=True)


@pytest.fixture
def regular(db):
    return User.objects.create_user(username="regular", password="pw12345")


@pytest.mark.django_db
def test_dashboard_renders(client, staff):
    client.force_login(staff)
    response = client.get(reverse("dashboard:home"))
    assert response.status_code == 200
    assert b"Dashboard" in response.content


@pytest.mark.django_db
def test_dashboard_requires_auth(client):
    response = client.get(reverse("dashboard:home"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_settings_get_renders(client, staff):
    client.force_login(staff)
    response = client.get(reverse("dashboard:settings"))
    assert response.status_code == 200
    assert b"Scanner defaults" in response.content


@pytest.mark.django_db
def test_settings_post_saves(client, staff):
    client.force_login(staff)
    response = client.post(
        reverse("dashboard:settings"),
        {
            "short_period": "5",
            "long_period": "20",
            "lookback_days": "15",
            "max_stocks": "30",
        },
    )
    assert response.status_code == 302
    setting = ScannerSetting.load()
    assert setting.short_period == 5
    assert setting.long_period == 20
    assert setting.lookback_days == 15
    assert setting.max_stocks == 30


@pytest.mark.django_db
def test_settings_post_non_staff_forbidden(client, regular):
    client.force_login(regular)
    response = client.post(
        reverse("dashboard:settings"),
        {"short_period": "5", "long_period": "20", "lookback_days": "15", "max_stocks": "30"},
    )
    # renders back with an error, defaults unchanged
    assert response.status_code == 200
    assert ScannerSetting.load().short_period == 7


@pytest.mark.django_db
def test_settings_post_invalid_long_not_greater(client, staff):
    client.force_login(staff)
    response = client.post(
        reverse("dashboard:settings"),
        {"short_period": "30", "long_period": "7", "lookback_days": "10", "max_stocks": "25"},
    )
    assert response.status_code == 200
    assert "long_period" in response.context["errors"]
