"""Context processors shared by every page shell (ARCHITECTURE §4.1)."""

from __future__ import annotations

from django.utils import timezone

from apps.core.market_hours import current_session, to_ist


def market_status(request) -> dict:
    """Inject ``market_state`` / ``market_open`` / ``market_time_ist`` into every template."""
    now = timezone.now()
    session = current_session(now)
    local = to_ist(now)
    return {
        "market_state": session.state,
        "market_open": session.is_open,
        "market_time_ist": local.strftime("%H:%M"),
    }
