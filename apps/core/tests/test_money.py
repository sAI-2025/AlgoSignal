from __future__ import annotations

import pytest

from apps.core import money


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2945.35", "₹ 2,945.35"),
        ("0", "₹ 0.00"),
        (None, money.EM_DASH),
        ("-1234.5", "₹ -1,234.50"),
    ],
)
def test_format_price(value, expected):
    assert money.format_price(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("6123456", "61,23,456"),
        ("2945", "2,945"),
        ("0", "0"),
        (None, money.EM_DASH),
    ],
)
def test_format_number(value, expected):
    assert money.format_number(value, 0) == expected


def test_format_number_decimals():
    assert money.format_number("6123456.75", 2) == "61,23,456.75"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("17200000000000", "₹ 17.2 L Cr"),  # 1.72e13
        ("84500000000", "₹ 8,450 Cr"),  # 8.45e10
        ("1234567890", "₹ 123.5 Cr"),  # 1.23e9 / 1e7 = 123.456789 → 123.5
        ("7500000", "₹ 75 L"),  # 75 lakh
        ("1234567", "₹ 12.3 L"),  # 12.34567 L → 12.3
        ("500000", "₹ 5 L"),
        ("8450", "₹ 8,450"),
        (None, money.EM_DASH),
        ("-84500000000", "₹ -8,450 Cr"),
    ],
)
def test_format_crore(value, expected):
    assert money.format_crore(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2.41", "▲ +2.41 %"),
        ("-1.08", "▼ −1.08 %"),
        ("0", "0.00 %"),
        (None, money.EM_DASH),
    ],
)
def test_format_percent(value, expected):
    assert money.format_percent(value) == expected


def test_format_percent_no_arrow():
    assert money.format_percent("2.41", arrow=False) == "+2.41 %"
    assert money.format_percent("-1.08", arrow=False) == "−1.08 %"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("24.8", "24.80"),
        ("0", "0.00"),
        (None, money.EM_DASH),
    ],
)
def test_format_ratio(value, expected):
    assert money.format_ratio(value) == expected
