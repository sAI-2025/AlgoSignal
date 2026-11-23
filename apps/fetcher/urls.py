from __future__ import annotations

from django.urls import path

from apps.fetcher import views

app_name = "fetcher"

urlpatterns = [
    path("", views.market_data, name="market_data"),
]
