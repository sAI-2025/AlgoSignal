"""Serializers for the Dashboard API (S1 KPI summary)."""

from __future__ import annotations

from rest_framework import serializers


class CoverageSerializer(serializers.Serializer):
    companies = serializers.IntegerField()
    with_data = serializers.IntegerField()
    latest_candle = serializers.DateField(allow_null=True, required=False)
    earliest_candle = serializers.DateField(allow_null=True, required=False)


class BreadthSerializer(serializers.Serializer):
    advancers = serializers.IntegerField()
    decliners = serializers.IntegerField()
    unchanged = serializers.IntegerField()


class SectorStatSerializer(serializers.Serializer):
    sector = serializers.CharField()
    average_return = serializers.FloatField()
    count = serializers.IntegerField()


class SignalSummarySerializer(serializers.Serializer):
    nse_code = serializers.CharField()
    company_name = serializers.CharField()
    signal_type = serializers.CharField()
    crossover_date = serializers.DateField()
    close = serializers.FloatField()


class ReturnRowSerializer(serializers.Serializer):
    nse_code = serializers.CharField()
    company_name = serializers.CharField()
    return_pct = serializers.FloatField()


class DashboardSummarySerializer(serializers.Serializer):
    coverage = CoverageSerializer()
    breadth = BreadthSerializer()
    sectors = SectorStatSerializer(many=True)
    recent_signals = SignalSummarySerializer(many=True)
    top_gainers = ReturnRowSerializer(many=True)
    freshness_stale = serializers.BooleanField()
