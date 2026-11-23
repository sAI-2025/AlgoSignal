from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.fetcher.models import FetchRun, FetchSchedule, JobType
from apps.fetcher.selectors import (
    all_schedules,
    heartbeat_age_seconds,
    recent_runs,
    scheduler_is_stale,
)
from apps.fetcher.services import locking
from apps.fetcher.services.scheduler import run_now
from apps.market_data.selectors import coverage_summary


@login_required
@require_http_methods(["GET", "POST"])
def market_data(request):
    message = None
    message_error = False

    if request.method == "POST":
        action = request.POST.get("action")
        schedule = _resolve_schedule(request)

        if not request.user.is_staff:
            message, message_error = "Only staff can change market-data settings.", True
        elif schedule is None:
            message, message_error = "Unknown schedule.", True
        elif action == "toggle":
            schedule.enabled = not schedule.enabled
            schedule.save(update_fields=["enabled", "updated_at"])
            state = "enabled" if schedule.enabled else "disabled"
            message = f"{schedule.get_job_type_display()} {state}."
        elif action == "interval":
            message, message_error = _update_interval(schedule, request.POST.get("interval_hours"))
        elif action == "run_now":
            try:
                run = run_now(schedule)
                message = (
                    f"{schedule.get_job_type_display()} finished: {run.status} "
                    f"({run.success_items}/{run.total_items} ok)."
                )
            except RuntimeError as exc:
                message, message_error = str(exc), True

        if message:
            return render_market_data(request, message=message, message_error=message_error)

    return render_market_data(request)


def _resolve_schedule(request) -> FetchSchedule | None:
    schedule_id = request.POST.get("schedule_id")
    if not schedule_id:
        return None
    return FetchSchedule.objects.filter(pk=schedule_id).first()


def _update_interval(schedule: FetchSchedule, raw: str | None) -> tuple[str, bool]:
    try:
        hours = int(raw or "")
    except (TypeError, ValueError):
        return "Interval must be a whole number of hours (1–168).", True
    if hours < 1 or hours > 168:
        return "Interval must be between 1 and 168 hours.", True
    if hours < 6 and schedule.job_type == JobType.FUNDAMENTALS:
        # soft warning only, still applied
        schedule.interval_hours = hours
        schedule.save(update_fields=["interval_hours", "updated_at"])
        return f"Interval set to {hours}h. Under 6h is not recommended for fundamentals.", False
    schedule.interval_hours = hours
    schedule.save(update_fields=["interval_hours", "updated_at"])
    return f"Interval set to {hours}h.", False


def render_market_data(request, *, message=None, message_error=False):
    job_filter = request.GET.get("job") or None
    status_filter = request.GET.get("status") or None
    context = {
        "schedules": all_schedules(),
        "runs": recent_runs(job_type=job_filter, status=status_filter, limit=50),
        "job_types": JobType.choices,
        "statuses": FetchRun.Status.choices,
        "job_filter": job_filter,
        "status_filter": status_filter,
        "coverage": coverage_summary(),
        "heartbeat_age": heartbeat_age_seconds(),
        "scheduler_stale": scheduler_is_stale(),
        "cooling_down": locking.is_cooling_down(),
        "cooldown_seconds": locking.cooldown_remaining_seconds(),
        "message": message,
        "message_error": message_error,
        "is_staff": request.user.is_staff,
    }
    return render(request, "fetcher/market_data.html", context)
