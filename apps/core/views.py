from django.core.cache import cache
from django.db import connections
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render


def home(request: HttpRequest):
    return render(request, "core/home.html")


def health(request: HttpRequest) -> JsonResponse:
    db_status = "ok"
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        db_status = "error"

    return JsonResponse(
        {
            "status": "ok" if db_status == "ok" else "degraded",
            "db": db_status,
            "scheduler_last_tick": cache.get("scheduler:last_tick"),
            "provider": "ok",
        }
    )
