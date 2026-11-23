"""Presentation formatters for money, ratios and percentages (PRD §5.6).

Pure, dependency-free helpers so every screen formats numbers the same way. Missing
values render as an em dash — never ``0`` (PRD §5.6). Prices use Indian digit grouping
(1,00,00,000) with a ₹ prefix; large amounts collapse to Lakh / Crore / Lakh-Crore.

    >>> format_price("2945.35")
    '₹ 2,945.35'
    >>> format_crore(Decimal("1.72e13"))
    '₹ 17.2 L Cr'
    >>> format_percent(-1.08)
    '▼ −1.08 %'
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

EM_DASH = "—"
RUPEE = "₹"
UP_TRIANGLE = "▲"
DOWN_TRIANGLE = "▼"
MINUS = "−"  # true minus sign (U+2212)

CRORE = Decimal("10000000")  # 1,00,00,000
LAKH_CRORE = Decimal("1000000000000")  # 1,00,000 Cr
LAKH = Decimal("100000")  # 1,00,000


def to_decimal(value: object) -> Decimal | None:
    """Best-effort conversion to ``Decimal``; ``None`` for missing/unparseable input."""
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _group_int(digits: str) -> str:
    """Group an integer string in the Indian system (last 3, then 2s)."""
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join([*groups, tail])


def _group_decimal(value: Decimal, decimals: int) -> str:
    """Fixed-point string for *value* with Indian grouping and *decimals* places."""
    quant = value.quantize(Decimal(1).scaleb(-decimals))
    sign = "-" if quant < 0 else ""
    text = f"{abs(quant):.{decimals}f}"
    integer, _, frac = text.partition(".")
    grouped = _group_int(integer)
    return f"{sign}{grouped}" + (f".{frac}" if decimals else "")


def _group_decimal_str(text: str) -> str:
    """Indian-group the integer part of a decimal string (``"8450.0"`` → ``"8,450"``)."""
    integer, _, frac = text.partition(".")
    return _group_int(integer) + ("." + frac if frac else "")


def _trim(value: Decimal, places: int = 1) -> str:
    """Quantize then drop trailing zeros/point (``8450.0`` → ``"8450"``, ``17.20`` → ``"17.2"``)."""
    quant = value.quantize(Decimal(1).scaleb(-places))
    text = f"{quant:.{places}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _trim(value: Decimal, places: int = 1) -> str:
    """Quantize then drop trailing zeros/point (``8450.0`` → ``"8450"``, ``17.20`` → ``"17.2"``)."""
    quant = value.quantize(Decimal(1).scaleb(-places))
    text = f"{quant:.{places}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def format_price(value: object) -> str:
    """₹ + Indian-grouped, 2 decimals. ``None`` → em dash."""
    number = to_decimal(value)
    if number is None:
        return EM_DASH
    return f"{RUPEE} {_group_decimal(number, 2)}"


def format_number(value: object, decimals: int = 0) -> str:
    """Indian-grouped number without a currency symbol (e.g. volume)."""
    number = to_decimal(value)
    if number is None:
        return EM_DASH
    return _group_decimal(number, decimals)


def format_crore(value: object) -> str:
    """Large rupee amount scaled to Lakh-Crore / Crore / Lakh (PRD §5.6)."""
    number = to_decimal(value)
    if number is None:
        return EM_DASH
    sign = "-" if number < 0 else ""
    magnitude = abs(number)
    if magnitude >= LAKH_CRORE:
        return f"{RUPEE} {sign}{_group_decimal_str(_trim(magnitude / LAKH_CRORE))} L Cr"
    if magnitude >= CRORE:
        return f"{RUPEE} {sign}{_group_decimal_str(_trim(magnitude / CRORE))} Cr"
    if magnitude >= LAKH:
        return f"{RUPEE} {sign}{_group_decimal_str(_trim(magnitude / LAKH))} L"
    return f"{RUPEE} {sign}{_group_decimal(magnitude, 0)}"


def format_percent(value: object, *, arrow: bool = True) -> str:
    """Signed percentage with 2 decimals; optional ▲/▼ arrow (PRD §5.6)."""
    number = to_decimal(value)
    if number is None:
        return EM_DASH
    sign = "+" if number > 0 else (MINUS if number < 0 else "")
    text = f"{abs(number):.2f}"
    prefix = ""
    if arrow and number != 0:
        prefix = f"{UP_TRIANGLE} " if number > 0 else f"{DOWN_TRIANGLE} "
    return f"{prefix}{sign}{text} %"


def format_ratio(value: object) -> str:
    """Plain ratio (P/E, P/B, D/E) with 2 decimals; ``None`` → em dash."""
    number = to_decimal(value)
    if number is None:
        return EM_DASH
    return f"{number:.2f}"
