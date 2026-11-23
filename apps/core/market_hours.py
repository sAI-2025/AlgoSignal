from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)
CANDLE_COMPLETE_TIME = time(16, 0)


@dataclass(frozen=True)
class MarketSession:
    state: str
    is_open: bool


def to_ist(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


def is_market_day(now: datetime) -> bool:
    return to_ist(now).weekday() < 5


def market_state(now: datetime) -> str:
    current = to_ist(now)
    if current.weekday() >= 5:
        return "CLOSED"
    if current.timetz().replace(tzinfo=None) < MARKET_OPEN:
        return "PRE_OPEN"
    if current.timetz().replace(tzinfo=None) <= MARKET_CLOSE:
        return "OPEN"
    return "CLOSED"


def current_session(now: datetime) -> MarketSession:
    state = market_state(now)
    return MarketSession(state=state, is_open=(state == "OPEN"))


def is_candle_complete(candle_date: date, now: datetime) -> bool:
    current = to_ist(now)
    if candle_date < current.date():
        return True
    if candle_date > current.date():
        return False
    return current.timetz().replace(tzinfo=None) >= CANDLE_COMPLETE_TIME
