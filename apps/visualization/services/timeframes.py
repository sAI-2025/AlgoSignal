"""Timeframe → date-range mapping for the chart workspace (ARCHITECTURE §13.3).

A timeframe maps the *end* date (usually the last stored candle) to a *start* date. ``MAX``
means "all available history" and therefore has no start bound.
"""

from __future__ import annotations

from datetime import date

from dateutil.relativedelta import relativedelta

# tf -> relativedelta offset subtracted from the end date. ``MAX`` -> None (no start).
TIMEFRAMES: dict[str, relativedelta | None] = {
    "1D": relativedelta(days=1),
    "1W": relativedelta(weeks=1),
    "1M": relativedelta(months=1),
    "3M": relativedelta(months=3),
    "6M": relativedelta(months=6),
    "1Y": relativedelta(years=1),
    "3Y": relativedelta(years=3),
    "5Y": relativedelta(years=5),
    "MAX": None,
}

DEFAULT_TF = "1Y"


def resolve_range(tf: str, end: date) -> tuple[date | None, date]:
    """Return ``(start, end)`` for timeframe *tf* anchored at *end*.

    ``start`` is ``None`` for ``MAX``. Raises ``ValueError`` for an unknown timeframe.
    """
    if tf not in TIMEFRAMES:
        raise ValueError(f"Unknown timeframe: {tf!r}")
    delta = TIMEFRAMES[tf]
    start = end - delta if delta is not None else None
    return start, end
