from django.urls import path

from apps.fetcher.api import views

app_name = "fetcher_api"

urlpatterns = [
    path("schedules/", views.schedules_list, name="schedules_list"),
    path("schedules/<int:schedule_id>/", views.schedule_detail, name="schedule_detail"),
    path(
        "schedules/<int:schedule_id>/run-now/",
        views.schedule_run_now,
        name="schedule_run_now",
    ),
    path("backfill/", views.backfill, name="backfill"),
    path("runs/", views.runs_list, name="runs_list"),
    path("runs/<int:run_id>/", views.run_detail, name="run_detail"),
    path("coverage/", views.coverage, name="coverage"),
]
