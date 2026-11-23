from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.dashboard.services.summary import dashboard_summary
from apps.scanner.models import ScannerSetting
from apps.scanner.services.params import ScannerParams


@login_required
def dashboard(request):
    context = {"summary": dashboard_summary()}
    return render(request, "dashboard/dashboard.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def settings(request):
    settings_obj = ScannerSetting.load()
    errors: dict[str, str] = {}

    if request.method == "POST":
        params = ScannerParams(
            short_period=int(request.POST.get("short_period") or settings_obj.short_period),
            long_period=int(request.POST.get("long_period") or settings_obj.long_period),
            lookback_days=int(request.POST.get("lookback_days") or settings_obj.lookback_days),
            max_stocks=int(request.POST.get("max_stocks") or settings_obj.max_stocks),
        )
        errors = params.errors()
        if not errors and request.user.is_staff:
            settings_obj.short_period = params.short_period
            settings_obj.long_period = params.long_period
            settings_obj.lookback_days = params.lookback_days
            settings_obj.max_stocks = params.max_stocks
            settings_obj.auto_run_on_open = request.POST.get("auto_run_on_open") == "on"
            settings_obj.save()
            return redirect(reverse("dashboard:settings"))
        if not errors and not request.user.is_staff:
            errors["form"] = "Only staff can change settings."

    context = {
        "settings": settings_obj,
        "errors": errors,
        "is_staff": request.user.is_staff,
    }
    return render(request, "dashboard/settings.html", context)


@login_required
def watchlist(request):
    """Watchlist page (UI-only; the starred symbols live in localStorage)."""
    return render(request, "dashboard/watchlist.html")


@login_required
def alerts(request):
    """Alerts page (UI-only; alerts live in localStorage, no backend/notifications)."""
    return render(request, "dashboard/alerts.html")
