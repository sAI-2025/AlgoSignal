"""Serializers for the Analytics API (S4 top performers, S1 market overview, sectors)."""

from __future__ import annotations

from rest_framework import serializers


class ReturnRowSerializer(serializers.Serializer):
    company_id = serializers.IntegerField()
    nse_code = serializers.CharField()
    company_name = serializers.CharField()
    sector = serializers.CharField(allow_null=True, required=False)
    industry = serializers.CharField(allow_null=True, required=False)
    period = serializers.CharField(required=False)
    close = serializers.FloatField()
    return_pct = serializers.FloatField()
    basis = serializers.CharField(required=False)


class TopPerformersQuerySerializer(serializers.Serializer):
    PERIOD_CHOICES = ["1D", "1W", "1M", "3M", "6M", "1Y"]
    period = serializers.ChoiceField(choices=PERIOD_CHOICES, required=False, default="1M")
    sector = serializers.CharField(required=False, allow_blank=True)
    industry = serializers.CharField(required=False, allow_blank=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=200, default=20)
    order = serializers.ChoiceField(choices=["asc", "desc"], required=False, default="desc")


class MarketOverviewSerializer(serializers.Serializer):
    advancers = serializers.IntegerField()
    decliners = serializers.IntegerField()
    unchanged = serializers.IntegerField()


class SectorStatsQuerySerializer(serializers.Serializer):
    period = serializers.ChoiceField(
        choices=["1D", "1W", "1M", "3M", "6M", "1Y"], required=False, default="1M"
    )


class SectorStatSerializer(serializers.Serializer):
    sector = serializers.CharField()
    average_return = serializers.FloatField()
    count = serializers.IntegerField()
