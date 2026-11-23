from django.urls import path

from apps.scanner.api import views

app_name = "scanner_api"

urlpatterns = [
    path("run/", views.scanner_run, name="scanner_run"),
    path("settings/", views.scanner_settings, name="scanner_settings"),
    path("signals/", views.signals_list, name="signals_list"),
]
