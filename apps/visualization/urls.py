from django.urls import path

from apps.visualization import views

app_name = "visualization"

urlpatterns = [
    path("<str:nse_code>/workspace/", views.chart_workspace, name="workspace"),
    path("<str:nse_code>/", views.chart_payload_api, name="chart_payload"),
]
