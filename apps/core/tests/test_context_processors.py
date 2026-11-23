from datetime import datetime
from unittest.mock import patch

from django.utils import timezone

from apps.core.context_processors import market_status


def test_market_status_wires_session_and_time():
    fake_session = type("Session", (), {"state": "OPEN", "is_open": True})()
    mocked_now = datetime(2026, 11, 23, 10, 0, tzinfo=timezone.UTC)
    mocked_local = datetime(2026, 11, 23, 15, 30)
    with (
        patch("apps.core.context_processors.current_session", return_value=fake_session),
        patch("apps.core.context_processors.timezone.now", return_value=mocked_now),
        patch("apps.core.context_processors.to_ist", return_value=mocked_local),
    ):
        context = market_status(None)

    assert context["market_state"] == "OPEN"
    assert context["market_open"] is True
    assert context["market_time_ist"] == "15:30"
