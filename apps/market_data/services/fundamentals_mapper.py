"""Pure mapping of a raw yfinance ``Ticker.info`` dict into ``CompanyMetrics`` fields.

No Django, DB or network imports here — this module is fully unit-testable against a
recorded fixture (see ``tests/fixtures/yf_info_reliance.json``).

Unit handling (ARCHITECTURE §4.3, PRD §8 "Rules"):
    * Percent-vs-fraction fields (``dividend_yield``, ``return_on_equity``,
      ``return_on_assets``, ``profit_margins``) are normalised to a **percentage**.
      yfinance has historically been inconsistent here: some versions return a fraction
      (``0.14`` meaning 14 %), others a percentage (``14.0``). We treat any value whose
      magnitude is ``<= 1.0`` as a fraction and multiply by 100; anything larger is
      assumed to already be a percentage. This is a documented heuristic — verify against
      a freshly recorded response before trusting production values.
    * ``debt_to_equity`` is a ratio and is **never** rescaled.
    * Money and ratio values become ``Decimal``; volumes become ``int``.
    * Missing / NaN / non-numeric input becomes ``None`` (never ``0``).
"""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Final

# yfinance info key -> CompanyMetrics field name.
_FIELD_MAP: Final[dict[str, str]] = {
    "currentPrice": "current_price",
    "previousClose": "previous_close",
    "open": "open_price",
    "dayHigh": "day_high",
    "dayLow": "day_low",
    "fiftyTwoWeekHigh": "fifty_two_week_high",
    "fiftyTwoWeekLow": "fifty_two_week_low",
    "volume": "volume",
    "averageVolume": "average_volume",
    "marketCap": "market_cap",
    "trailingPE": "trailing_pe",
    "forwardPE": "forward_pe",
    "trailingEps": "trailing_eps",
    "bookValue": "book_value",
    "priceToBook": "price_to_book",
    "dividendYield": "dividend_yield",
    "returnOnEquity": "return_on_equity",
    "returnOnAssets": "return_on_assets",
    "profitMargins": "profit_margins",
    "debtToEquity": "debt_to_equity",
    "totalRevenue": "total_revenue",
    "freeCashflow": "free_cashflow",
    "netIncomeToCommon": "net_income",
}

# Fields stored as whole-number share counts.
_VOLUME_FIELDS: Final[frozenset[str]] = frozenset({"volume", "average_volume"})

# Fields normalised from fraction -> percentage.
_PERCENT_FIELDS: Final[frozenset[str]] = frozenset(
    {"dividend_yield", "return_on_equity", "return_on_assets", "profit_margins"}
)

# Fields stored as money (2 dp) vs plain ratios (4 dp).
_MONEY_FIELDS: Final[frozenset[str]] = frozenset(
    {"market_cap", "total_revenue", "free_cashflow", "net_income"}
)

_MONEY_QUANT = Decimal("0.01")
_RATIO_QUANT = Decimal("0.0001")
_PERCENT_THRESHOLD = Decimal("1.0")


def _coerce_decimal(value: object) -> Decimal | None:
    """Return a finite ``Decimal`` for *value*, or ``None`` when missing/non-numeric."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not result.is_finite():
        return None
    return result


def map_company_info(raw: dict) -> dict[str, Decimal | int | None]:
    """Map a raw yfinance ``info`` dict to a ``CompanyMetrics`` field dict.

    The returned dict contains only known metric fields; unknown keys are ignored and
    missing fields are simply absent (the service treats absence as ``None``).
    """
    mapped: dict[str, Decimal | int | None] = {}

    for info_key, field_name in _FIELD_MAP.items():
        value = _coerce_decimal(raw.get(info_key))
        if value is None:
            mapped[field_name] = None
            continue

        if field_name in _VOLUME_FIELDS:
            mapped[field_name] = int(value)
            continue

        if field_name in _PERCENT_FIELDS:
            if abs(value) <= _PERCENT_THRESHOLD:
                value = value * Decimal("100")

        quant = _MONEY_QUANT if field_name in _MONEY_FIELDS else _RATIO_QUANT
        mapped[field_name] = value.quantize(quant)

    return mapped
