import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_endpoint_reports_ok() -> None:
    client = Client()

    response = client.get("/health/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["db"] == "ok"
    assert "scheduler_last_tick" in payload
