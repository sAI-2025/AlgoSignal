from datetime import date, datetime

from apps.core import market_hours


def test_market_open_during_session() -> None:
    now = datetime(2026, 11, 23, 10, 30, tzinfo=market_hours.IST)

    assert market_hours.market_state(now) == "OPEN"


def test_market_pre_open_before_session_start() -> None:
    now = datetime(2026, 11, 23, 8, 45, tzinfo=market_hours.IST)

    assert market_hours.market_state(now) == "PRE_OPEN"


def test_market_closed_on_weekend() -> None:
    now = datetime(2026, 11, 22, 10, 0, tzinfo=market_hours.IST)

    assert market_hours.market_state(now) == "CLOSED"


def test_candle_incomplete_before_buffer_time() -> None:
    now = datetime(2026, 11, 23, 15, 59, tzinfo=market_hours.IST)

    assert market_hours.is_candle_complete(date(2026, 11, 23), now) is False


def test_candle_complete_after_buffer_time() -> None:
    now = datetime(2026, 11, 23, 16, 1, tzinfo=market_hours.IST)

    assert market_hours.is_candle_complete(date(2026, 11, 23), now) is True
