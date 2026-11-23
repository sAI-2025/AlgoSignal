"""Serializers for the Scanner API (S3 run/settings + stored signals)."""

from __future__ import annotations

from rest_framework import serializers


class ScannerParamsSerializer(serializers.Serializer):
    short_period = serializers.IntegerField(required=False, default=7, min_value=1)
    long_period = serializers.IntegerField(required=False, default=30, min_value=1)
    lookback_days = serializers.IntegerField(required=False, default=10, min_value=1)
    max_stocks = serializers.IntegerField(required=False, default=25, min_value=1)


class ScannerSettingsSerializer(serializers.Serializer):
    short_period = serializers.IntegerField()
    long_period = serializers.IntegerField()
    lookback_days = serializers.IntegerField()
    max_stocks = serializers.IntegerField()
    auto_run_on_open = serializers.BooleanField()


class SignalSerializer(serializers.Serializer):
    nse_code = serializers.CharField()
    company_name = serializers.CharField()
    signal_type = serializers.CharField()
    crossover_date = serializers.DateField()
    close = serializers.FloatField()
    short_sma = serializers.FloatField()
    long_sma = serializers.FloatField()
    params = serializers.ListField(child=serializers.IntegerField(), required=False)


class ScanResultSerializer(serializers.Serializer):
    rows = SignalSerializer(many=True)
    counts = serializers.DictField(child=serializers.IntegerField())
    total_crossovers = serializers.IntegerField()
    skipped = serializers.ListField(child=serializers.DictField())
    as_of = serializers.DateField(allow_null=True, required=False)
