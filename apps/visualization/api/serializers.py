"""Query validation for the Chart API."""

from __future__ import annotations

from rest_framework import serializers


class ChartPayloadQuerySerializer(serializers.Serializer):
    tf = serializers.ChoiceField(
        choices=["1D", "1W", "1M", "3M", "6M", "1Y", "3Y", "5Y", "MAX"],
        required=False,
        default="1Y",
    )
    sma = serializers.CharField(required=False, default="7,30")
    ind = serializers.CharField(required=False, default="")
    benchmark = serializers.CharField(required=False, default="")
    markers = serializers.ChoiceField(
        choices=["0", "1", "true", "false"], required=False, default="1"
    )
    before = serializers.DateField(required=False)
