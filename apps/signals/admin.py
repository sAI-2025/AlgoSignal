from django.contrib import admin

from apps.signals.models import TradingSignal


@admin.register(TradingSignal)
class TradingSignalAdmin(admin.ModelAdmin):
    list_display = (
        "crossover_date",
        "company",
        "signal_type",
        "short_period",
        "long_period",
        "close_price",
    )
    list_filter = ("signal_type", "strategy")
    search_fields = ("company__nse_code", "company__company_name")
    date_hierarchy = "crossover_date"
