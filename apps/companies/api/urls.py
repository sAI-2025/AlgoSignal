from django.urls import path

from apps.companies.api import views

app_name = "companies_api"

urlpatterns = [
    path("", views.company_list, name="company_list"),
    path("sectors/", views.company_sectors, name="company_sectors"),
    path("import/", views.company_import, name="company_import"),
    path("<str:nse_code>/", views.company_detail, name="company_detail"),
    path("<str:nse_code>/metrics/", views.company_metrics, name="company_metrics"),
    path(
        "<str:nse_code>/refresh-metrics/",
        views.company_refresh_metrics,
        name="company_refresh_metrics",
    ),
]
