from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import Q


class JobType(models.TextChoices):
    DAILY_CANDLES = "DAILY_CANDLES", "Daily candles"
    FUNDAMENTALS = "FUNDAMENTALS", "Fundamentals"
    CONSTITUENTS_SYNC = "CONSTITUENTS_SYNC", "Constituents sync"


class FetchSchedule(models.Model):
    job_type = models.CharField(max_length=20, choices=JobType.choices, unique=True)
    enabled = models.BooleanField(default=True)
    interval_hours = models.PositiveSmallIntegerField(default=24)
    only_market_days = models.BooleanField(default=True)
    earliest_time_ist = models.TimeField(null=True, blank=True)
    universe_index = models.CharField(max_length=30, default="NIFTY100")
    batch_size = models.PositiveSmallIntegerField(default=10)
    throttle_seconds = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("2.0"))
    last_started_at = models.DateTimeField(null=True, blank=True)
    last_finished_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=16, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(interval_hours__gte=1, interval_hours__lte=168),
                name="ck_fetch_schedule_interval_hours_range",
            ),
            models.CheckConstraint(
                condition=Q(batch_size__gt=0),
                name="ck_fetch_schedule_batch_size_positive",
            ),
            models.CheckConstraint(
                condition=Q(throttle_seconds__gte=Decimal("0")),
                name="ck_fetch_schedule_throttle_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.job_type} schedule"


class FetchRun(models.Model):
    class Trigger(models.TextChoices):
        CRON = "CRON", "Cron"
        MANUAL = "MANUAL", "Manual"
        CLI = "CLI", "CLI"

    class Status(models.TextChoices):
        RUNNING = "RUNNING", "Running"
        SUCCESS = "SUCCESS", "Success"
        PARTIAL = "PARTIAL", "Partial"
        FAILED = "FAILED", "Failed"

    job_type = models.CharField(max_length=20, choices=JobType.choices)
    schedule = models.ForeignKey(
        FetchSchedule,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="runs",
    )
    trigger = models.CharField(max_length=10, choices=Trigger.choices, default=Trigger.CRON)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    total_items = models.PositiveIntegerField(default=0)
    success_items = models.PositiveIntegerField(default=0)
    failed_items = models.PositiveIntegerField(default=0)
    rows_written = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    message = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["job_type", "-started_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.job_type} run @ {self.started_at:%Y-%m-%d %H:%M}"
