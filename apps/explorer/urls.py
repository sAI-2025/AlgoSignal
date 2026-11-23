from django.urls import path

from apps.explorer import views

app_name = "explorer"

urlpatterns = [
    path("", views.explorer_home, name="home"),
    path("search/", views.search_api, name="search_api"),
    path("<str:nse_code>/", views.company_detail, name="detail"),
]
