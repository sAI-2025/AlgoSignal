from __future__ import annotations

from django.db import models

from apps.companies.models import Company


class TradingSignal(models.Model):
    class SignalType(models.TextChoices):
        BULLISH = "BULLISH", "Bullish"
        BEARISH = "BEARISH", "Bearish"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="signals",
    )
    strategy = models.CharField(max_length=30, default="SMA_CROSS")
    signal_type = models.CharField(max_length=10, choices=SignalType.choices)
    short_period = models.PositiveSmallIntegerField()
    long_period = models.PositiveSmallIntegerField()
    short_sma = models.DecimalField(max_digits=14, decimal_places=4)
    long_sma = models.DecimalField(max_digits=14, decimal_places=4)
    close_price = models.DecimalField(max_digits=14, decimal_places=4)
    crossover_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-crossover_date", "company__nse_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "strategy", "short_period", "long_period", "crossover_date"],
                name="uq_trading_signal_unique_key",
            )
        ]
        indexes = [
            models.Index(fields=["-crossover_date"]),
            models.Index(fields=["signal_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.company.nse_code} {self.signal_type} {self.crossover_date}"
