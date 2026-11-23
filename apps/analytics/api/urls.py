from django.urls import path

from apps.analytics.api import views

app_name = "analytics_api"

urlpatterns = [
    path("top-performers/", views.top_performers_api, name="top_performers"),
    path("market-overview/", views.market_overview_api, name="market_overview"),
    path("sectors/", views.sectors_api, name="sectors"),
]
