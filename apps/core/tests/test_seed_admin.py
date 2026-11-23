from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command


@pytest.mark.django_db
def test_seed_admin_creates_superuser():
    call_command("seed_admin", "--username", "sai", "--password", "strongpw1")

    user = get_user_model().objects.get(username="sai")
    assert user.is_superuser is True
    assert user.is_staff is True
    assert user.check_password("strongpw1")


@pytest.mark.django_db
def test_seed_admin_is_idempotent_and_rotates_password():
    call_command("seed_admin", "--username", "sai", "--password", "firstpw1")
    call_command("seed_admin", "--username", "sai", "--password", "secondpw2")

    users = get_user_model().objects.filter(username="sai")
    assert users.count() == 1
    user = users.get()
    assert user.check_password("secondpw2")
    assert not user.check_password("firstpw1")


@pytest.mark.django_db
def test_seed_admin_no_staff_creates_regular_user():
    call_command("seed_admin", "--username", "reader", "--password", "strongpw1", "--no-staff")

    user = get_user_model().objects.get(username="reader")
    assert user.is_staff is False
    assert user.is_superuser is False
