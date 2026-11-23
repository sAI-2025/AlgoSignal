from django.urls import path

from apps.market_data.api import views

app_name = "market_data_api"

urlpatterns = [
    path("quote/<str:nse_code>/", views.live_quote, name="live_quote"),
    path("quotes/", views.live_quotes, name="live_quotes"),
    path("intraday/<str:nse_code>/", views.live_intraday, name="live_intraday"),
    path(
        "refresh-metrics/<str:nse_code>/",
        views.live_refresh_metrics,
        name="live_refresh_metrics",
    ),
]
