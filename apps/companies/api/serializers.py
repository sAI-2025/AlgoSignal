"""Serializers for the Companies API (S2).

All fields mirror the dicts returned by ``apps.companies.selectors`` so the views stay
thin and delegate to existing business logic.
"""

from __future__ import annotations

from rest_framework import serializers


class CompanySerializer(serializers.Serializer):
    nse_code = serializers.CharField()
    company_name = serializers.CharField()
    sector = serializers.CharField(allow_null=True, required=False)
    industry = serializers.CharField(allow_null=True, required=False)
    price = serializers.FloatField(allow_null=True, required=False)
    trailing_pe = serializers.FloatField(allow_null=True, required=False)
    market_cap = serializers.FloatField(allow_null=True, required=False)


class CompanyDetailSerializer(serializers.Serializer):
    nse_code = serializers.CharField()
    company_name = serializers.CharField()
    bse_code = serializers.CharField(allow_null=True, required=False)
    isin = serializers.CharField(allow_null=True, required=False)
    sector = serializers.CharField(allow_null=True, required=False)
    industry = serializers.CharField(allow_null=True, required=False)
    description = serializers.CharField(allow_null=True, required=False)
    is_active = serializers.BooleanField()
    price = serializers.FloatField(allow_null=True, required=False)
    metrics_fetched_at = serializers.DateTimeField(allow_null=True, required=False)


class CompanyMetricsSerializer(serializers.Serializer):
    current_price = serializers.FloatField(allow_null=True, required=False)
    previous_close = serializers.FloatField(allow_null=True, required=False)
    open_price = serializers.FloatField(allow_null=True, required=False)
    day_high = serializers.FloatField(allow_null=True, required=False)
    day_low = serializers.FloatField(allow_null=True, required=False)
    fifty_two_week_high = serializers.FloatField(allow_null=True, required=False)
    fifty_two_week_low = serializers.FloatField(allow_null=True, required=False)
    volume = serializers.IntegerField(allow_null=True, required=False)
    average_volume = serializers.IntegerField(allow_null=True, required=False)
    market_cap = serializers.FloatField(allow_null=True, required=False)
    trailing_pe = serializers.FloatField(allow_null=True, required=False)
    forward_pe = serializers.FloatField(allow_null=True, required=False)
    trailing_eps = serializers.FloatField(allow_null=True, required=False)
    book_value = serializers.FloatField(allow_null=True, required=False)
    price_to_book = serializers.FloatField(allow_null=True, required=False)
    dividend_yield = serializers.FloatField(allow_null=True, required=False)
    return_on_equity = serializers.FloatField(allow_null=True, required=False)
    return_on_assets = serializers.FloatField(allow_null=True, required=False)
    profit_margins = serializers.FloatField(allow_null=True, required=False)
    debt_to_equity = serializers.FloatField(allow_null=True, required=False)
    total_revenue = serializers.FloatField(allow_null=True, required=False)
    free_cashflow = serializers.FloatField(allow_null=True, required=False)
    net_income = serializers.FloatField(allow_null=True, required=False)
    currency = serializers.CharField(required=False)
    source = serializers.CharField(required=False)
    fetched_at = serializers.DateTimeField(allow_null=True, required=False)


class CompanyListQuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True)
    sector = serializers.CharField(required=False, allow_blank=True)
    ordering = serializers.ChoiceField(
        choices=["name", "symbol", "sector", "price", "pe", "market_cap"],
        required=False,
        default="name",
    )
    dir = serializers.ChoiceField(choices=["asc", "desc"], required=False, default="asc")
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=100, default=50)


class CompanyImportSerializer(serializers.Serializer):
    pass
