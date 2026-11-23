from django.db import models

from apps.companies.models import Company
from apps.core.models import TimeStampedModel


class Instrument(models.Model):
    class Exchange(models.TextChoices):
        NSE = "NSE", "NSE"
        BSE = "BSE", "BSE"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="instruments",
    )
    exchange = models.CharField(max_length=3, choices=Exchange.choices)
    tradingsymbol = models.CharField(max_length=30)
    provider_symbol = models.CharField(max_length=40)
    instrument_token = models.BigIntegerField(null=True, blank=True)
    instrument_type = models.CharField(max_length=20, default="EQ")
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["exchange", "tradingsymbol"],
                name="uq_market_data_instrument_exchange_symbol",
            )
        ]
        indexes = [models.Index(fields=["company", "exchange"])]

    def __str__(self) -> str:
        return f"{self.exchange}:{self.tradingsymbol}"


class HistoricalPrice(TimeStampedModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="historical_prices",
    )
    candle_date = models.DateField()
    open = models.DecimalField(max_digits=14, decimal_places=4)
    high = models.DecimalField(max_digits=14, decimal_places=4)
    low = models.DecimalField(max_digits=14, decimal_places=4)
    close = models.DecimalField(max_digits=14, decimal_places=4)
    adj_close = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    volume = models.BigIntegerField()
    source = models.CharField(max_length=20, default="yfinance")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "candle_date"],
                name="uq_historical_price_company_date",
            )
        ]
        indexes = [models.Index(fields=["company", "-candle_date"])]

    def __str__(self) -> str:
        return f"{self.company.nse_code} {self.candle_date}"


class CompanyMetrics(TimeStampedModel):
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="metrics",
    )
    # Price fields
    current_price = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    previous_close = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    open_price = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    day_high = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    day_low = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    fifty_two_week_high = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True
    )
    fifty_two_week_low = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    volume = models.BigIntegerField(null=True, blank=True)
    average_volume = models.BigIntegerField(null=True, blank=True)
    # Valuation
    market_cap = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    trailing_pe = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    forward_pe = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    trailing_eps = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    book_value = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    price_to_book = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    # Percent fields (stored as percentages, normalised by the mapper)
    dividend_yield = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    return_on_equity = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    return_on_assets = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    profit_margins = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    # Health
    debt_to_equity = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    total_revenue = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    free_cashflow = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    net_income = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    # Provenance
    currency = models.CharField(max_length=10, default="INR")
    source = models.CharField(max_length=20, default="yfinance")
    fetched_at = models.DateTimeField()

    class Meta:
        verbose_name_plural = "company metrics"

    def __str__(self) -> str:
        return f"Metrics for {self.company.nse_code}"
