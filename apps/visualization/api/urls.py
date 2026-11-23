from django.urls import path

from apps.visualization.api import views

app_name = "visualization_api"

urlpatterns = [
    path("<str:nse_code>/", views.chart_payload, name="chart_payload"),
]
