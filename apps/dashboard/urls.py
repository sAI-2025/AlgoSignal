from django.urls import path

from apps.dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard, name="home"),
    path("settings/", views.settings, name="settings"),
    path("watchlist/", views.watchlist, name="watchlist"),
    path("alerts/", views.alerts, name="alerts"),
]
