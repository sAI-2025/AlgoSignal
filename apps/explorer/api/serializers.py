"""Serializers for the Explorer API (S5a typeahead search)."""

from __future__ import annotations

from rest_framework import serializers


class SearchResultSerializer(serializers.Serializer):
    nse_code = serializers.CharField()
    company_name = serializers.CharField()
    sector = serializers.CharField(allow_null=True, required=False)
    bse_code = serializers.CharField(allow_null=True, required=False)


class SearchQuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True)
    sector = serializers.CharField(required=False, allow_blank=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=8)
