from django.contrib import admin

from apps.market_data.models import CompanyMetrics, HistoricalPrice, Instrument


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "exchange",
        "tradingsymbol",
        "provider_symbol",
        "instrument_type",
        "last_updated",
    )
    search_fields = (
        "company__nse_code",
        "company__company_name",
        "tradingsymbol",
        "provider_symbol",
    )
    list_filter = ("exchange", "instrument_type")


@admin.register(HistoricalPrice)
class HistoricalPriceAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "candle_date",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
        "source",
    )
    search_fields = (
        "company__nse_code",
        "company__company_name",
    )
    list_filter = ("source",)
    date_hierarchy = "candle_date"


@admin.register(CompanyMetrics)
class CompanyMetricsAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "current_price",
        "trailing_pe",
        "market_cap",
        "source",
        "fetched_at",
    )
    search_fields = (
        "company__nse_code",
        "company__company_name",
    )
    list_filter = ("source",)
    readonly_fields = ("fetched_at",)
