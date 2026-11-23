"""Serializers for the Live Data API (PRD FR-14, ARCHITECTURE §9)."""

from __future__ import annotations

from rest_framework import serializers


class LiveQuoteSerializer(serializers.Serializer):
    symbol = serializers.CharField()
    price = serializers.FloatField()
    change = serializers.FloatField(allow_null=True, required=False)
    change_pct = serializers.FloatField(allow_null=True, required=False)
    as_of = serializers.DateTimeField(allow_null=True, required=False)
    market_state = serializers.CharField(required=False)
    source = serializers.CharField(required=False)
    delayed_hint = serializers.CharField(allow_null=True, required=False)


class LiveQuotesQuerySerializer(serializers.Serializer):
    symbols = serializers.CharField(required=False, default="")


class IntradayQuerySerializer(serializers.Serializer):
    interval = serializers.ChoiceField(choices=["1m", "5m", "15m"], required=False, default="5m")


class RefreshMetricsSerializer(serializers.Serializer):
    pass
