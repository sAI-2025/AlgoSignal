from __future__ import annotations

from django.db import models
from django.db.models import Q


class ScannerSetting(models.Model):
    """Singleton scanner defaults (ARCHITECTURE ADR-12).

    Always accessed via :meth:`load`, which guarantees a single row with pk=1.
    """

    short_period = models.PositiveSmallIntegerField(default=7)
    long_period = models.PositiveSmallIntegerField(default=30)
    lookback_days = models.PositiveSmallIntegerField(default=10)
    max_stocks = models.PositiveSmallIntegerField(default=25)
    auto_run_on_open = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(short_period__gt=0), name="ck_scanner_short_positive"
            ),
            models.CheckConstraint(
                condition=Q(long_period__gt=models.F("short_period")),
                name="ck_scanner_long_gt_short",
            ),
            models.CheckConstraint(
                condition=Q(lookback_days__gt=0), name="ck_scanner_lookback_positive"
            ),
            models.CheckConstraint(
                condition=Q(max_stocks__gt=0), name="ck_scanner_max_stocks_positive"
            ),
        ]

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> ScannerSetting:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self) -> str:
        return f"Scanner defaults {self.short_period}/{self.long_period}"
