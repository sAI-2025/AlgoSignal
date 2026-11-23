from django.urls import path

from apps.dashboard.api import views

app_name = "dashboard_api"

urlpatterns = [
    path("summary/", views.dashboard_summary_api, name="dashboard_summary"),
]
