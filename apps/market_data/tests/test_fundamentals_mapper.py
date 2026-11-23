from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from apps.market_data.services.fundamentals_mapper import map_company_info

FIXTURE = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "yf_info_reliance.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_map_company_info_maps_all_fields() -> None:
    payload = map_company_info(_load())

    assert payload["current_price"] == Decimal("2945.3500")
    assert payload["previous_close"] == Decimal("2921.4500")
    assert payload["fifty_two_week_high"] == Decimal("3217.0000")
    assert payload["volume"] == 6123456
    assert payload["average_volume"] == 5987654
    assert payload["trailing_pe"] == Decimal("24.8000")
    assert payload["market_cap"] == Decimal("1992000000000.00")


def test_percent_fields_normalised_from_fraction() -> None:
    payload = map_company_info(_load())

    assert payload["dividend_yield"] == Decimal("0.4200")
    assert payload["return_on_equity"] == Decimal("9.1400")
    assert payload["return_on_assets"] == Decimal("5.6800")
    assert payload["profit_margins"] == Decimal("7.1200")


def test_debt_to_equity_not_rescaled() -> None:
    payload = map_company_info(_load())

    # 0.47 is a ratio; must stay 0.47 and not become 47.
    assert payload["debt_to_equity"] == Decimal("0.4700")


def test_percent_field_already_in_percent_form_kept() -> None:
    payload = map_company_info({"dividendYield": 2.5, "profitMargins": 14.0})

    assert payload["dividend_yield"] == Decimal("2.5000")
    assert payload["profit_margins"] == Decimal("14.0000")


def test_missing_and_non_numeric_become_none() -> None:
    payload = map_company_info(
        {"currentPrice": None, "trailingPE": float("nan"), "marketCap": "n/a"}
    )

    assert payload["current_price"] is None
    assert payload["trailing_pe"] is None
    assert payload["market_cap"] is None


def test_unknown_keys_ignored() -> None:
    payload = map_company_info({"someUnknownKey": 123, "currentPrice": 100.0})

    assert "someunknownkey" not in payload
    assert payload["current_price"] == Decimal("100.0000")
