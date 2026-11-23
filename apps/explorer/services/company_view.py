"""Compose the Company Detail page context (ARCHITECTURE §4.10, PRD S5b).

A *composition* helper: it reads from lower apps' selectors/services and shapes one dict
for the template. It owns no business rules — returns come from ``analytics``, signals
from ``signals``, coverage from ``market_data`` — and writes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.analytics.services.performance import ReturnRow, company_returns
from apps.companies.models import Company
from apps.market_data.selectors import company_coverage
from apps.signals.selectors import signals_for_company

DETAIL_PERIODS = ["1D", "1W", "1M", "3M", "6M", "1Y"]

# The 8 key metric tiles on the Overview tab (PRD S5b).
KEY_METRIC_FIELDS: list[tuple[str, str, str]] = [
    ("Market cap", "market_cap", "money"),
    ("P/E (trailing)", "trailing_pe", "ratio"),
    ("Revenue", "total_revenue", "money"),
    ("Net profit", "net_income", "money"),
    ("Return on equity", "return_on_equity", "percent"),
    ("Debt / Equity", "debt_to_equity", "ratio"),
    ("Dividend yield", "dividend_yield", "percent"),
    ("52-week high", "fifty_two_week_high", "money"),
]

# Metric groups for the Fundamentals tab (PRD §8 grouping). Each entry is
# (label, attribute name, formatter kind).
FUNDAMENTAL_GROUPS: dict[str, list[tuple[str, str, str]]] = {
    "Valuation": [
        ("Market cap", "market_cap", "money"),
        ("Trailing P/E", "trailing_pe", "ratio"),
        ("Forward P/E", "forward_pe", "ratio"),
        ("Price / Book", "price_to_book", "ratio"),
        ("Trailing EPS", "trailing_eps", "money"),
        ("Book value", "book_value", "money"),
    ],
    "Profitability": [
        ("Return on equity", "return_on_equity", "percent"),
        ("Return on assets", "return_on_assets", "percent"),
        ("Profit margin", "profit_margins", "percent"),
        ("Dividend yield", "dividend_yield", "percent"),
    ],
    "Financial health": [
        ("Debt / Equity", "debt_to_equity", "ratio"),
        ("Total revenue", "total_revenue", "money"),
        ("Net income", "net_income", "money"),
        ("Free cashflow", "free_cashflow", "money"),
    ],
    "Trading": [
        ("Current price", "current_price", "money"),
        ("Previous close", "previous_close", "money"),
        ("Open", "open_price", "money"),
        ("Day high", "day_high", "money"),
        ("Day low", "day_low", "money"),
        ("Volume", "volume", "int"),
        ("Average volume", "average_volume", "int"),
        ("52-week high", "fifty_two_week_high", "money"),
        ("52-week low", "fifty_two_week_low", "money"),
    ],
}


@dataclass
class CompanyDetail:
    company: Company
    metrics: object | None
    returns: list[ReturnRow | None]
    returns_strip: list[dict]
    key_metrics: list[dict]
    signals: list
    coverage: dict
    fundamentals: dict[str, list[dict]]
    latest_close: float | None


def _format_value(value, kind: str) -> str | None:
    if value is None:
        return None
    if kind == "percent":
        return f"{float(value):.2f}%"
    if kind == "int":
        return f"{int(value):,}"
    if kind == "ratio":
        return f"{float(value):.2f}"
    return f"{float(value):,.2f}"


def _metric_dict(metrics, label: str, attr: str, kind: str) -> dict:
    raw = getattr(metrics, attr, None) if metrics is not None else None
    return {
        "label": label,
        "value": _format_value(raw, kind),
        "raw": float(raw) if raw is not None else None,
        "kind": kind,
    }


def build_company_detail(company: Company, *, now=None) -> CompanyDetail:
    """Assemble everything the Company Detail page needs for *company*."""
    metrics = getattr(company, "metrics", None)
    returns = company_returns(company, DETAIL_PERIODS, now=now)
    signals = signals_for_company(company.id)
    coverage = company_coverage(company.id)

    returns_strip = [
        {
            "period": period,
            "return_pct": row.return_pct if row is not None else None,
            "basis": row.basis if row is not None else None,
        }
        for period, row in zip(DETAIL_PERIODS, returns, strict=False)
    ]

    key_metrics = [
        _metric_dict(metrics, label, attr, kind) for label, attr, kind in KEY_METRIC_FIELDS
    ]

    fundamentals: dict[str, list[dict]] = {}
    for group, fields in FUNDAMENTAL_GROUPS.items():
        fundamentals[group] = [
            _metric_dict(metrics, label, attr, kind) for label, attr, kind in fields
        ]

    latest_close = None
    if metrics is not None and metrics.current_price is not None:
        latest_close = float(metrics.current_price)

    return CompanyDetail(
        company=company,
        metrics=metrics,
        returns=returns,
        returns_strip=returns_strip,
        key_metrics=key_metrics,
        signals=signals,
        coverage=coverage,
        fundamentals=fundamentals,
        latest_close=latest_close,
    )
