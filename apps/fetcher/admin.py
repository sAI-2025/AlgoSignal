from django.contrib import admin

from apps.fetcher.models import FetchRun, FetchSchedule


@admin.register(FetchSchedule)
class FetchScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "job_type",
        "enabled",
        "interval_hours",
        "only_market_days",
        "earliest_time_ist",
        "next_run_at",
        "last_status",
        "updated_at",
    )
    list_filter = ("enabled", "only_market_days", "job_type")
    list_editable = ("enabled", "interval_hours")
    readonly_fields = (
        "last_started_at",
        "last_finished_at",
        "next_run_at",
        "last_status",
        "updated_at",
    )


@admin.register(FetchRun)
class FetchRunAdmin(admin.ModelAdmin):
    list_display = (
        "started_at",
        "job_type",
        "trigger",
        "status",
        "total_items",
        "success_items",
        "failed_items",
        "rows_written",
    )
    list_filter = ("job_type", "status", "trigger")
    readonly_fields = (
        "job_type",
        "schedule",
        "trigger",
        "status",
        "started_at",
        "finished_at",
        "heartbeat_at",
        "total_items",
        "success_items",
        "failed_items",
        "rows_written",
        "errors",
        "message",
    )
