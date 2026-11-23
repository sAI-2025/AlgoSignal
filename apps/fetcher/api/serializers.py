"""Serializers for the Fetcher API (S6 market data & fetch control)."""

from __future__ import annotations

from rest_framework import serializers


class FetchScheduleSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    job_type = serializers.CharField()
    enabled = serializers.BooleanField()
    interval_hours = serializers.IntegerField()
    only_market_days = serializers.BooleanField()
    earliest_time_ist = serializers.TimeField(allow_null=True, required=False)
    universe_index = serializers.CharField()
    batch_size = serializers.IntegerField()
    throttle_seconds = serializers.FloatField()
    last_started_at = serializers.DateTimeField(allow_null=True, required=False)
    last_finished_at = serializers.DateTimeField(allow_null=True, required=False)
    next_run_at = serializers.DateTimeField(allow_null=True, required=False)
    last_status = serializers.CharField(allow_null=True, required=False)
    updated_at = serializers.DateTimeField(allow_null=True, required=False)


class FetchScheduleUpdateSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(required=False)
    interval_hours = serializers.IntegerField(required=False, min_value=1, max_value=168)
    only_market_days = serializers.BooleanField(required=False)
    earliest_time_ist = serializers.TimeField(required=False, allow_null=True)
    batch_size = serializers.IntegerField(required=False, min_value=1)
    throttle_seconds = serializers.FloatField(required=False, min_value=0)


class FetchRunSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    job_type = serializers.CharField()
    trigger = serializers.CharField()
    status = serializers.CharField()
    started_at = serializers.DateTimeField()
    finished_at = serializers.DateTimeField(allow_null=True, required=False)
    heartbeat_at = serializers.DateTimeField(allow_null=True, required=False)
    total_items = serializers.IntegerField()
    success_items = serializers.IntegerField()
    failed_items = serializers.IntegerField()
    rows_written = serializers.IntegerField()
    errors = serializers.ListField(child=serializers.DictField(), required=False)
    message = serializers.CharField(required=False)


class CoverageSerializer(serializers.Serializer):
    companies = serializers.IntegerField()
    with_data = serializers.IntegerField()
    latest_candle = serializers.DateField(allow_null=True, required=False)
    earliest_candle = serializers.DateField(allow_null=True, required=False)


class BackfillSerializer(serializers.Serializer):
    years = serializers.IntegerField(required=False, min_value=1, max_value=10, default=3)
    symbol = serializers.CharField(required=False, allow_blank=True)
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
