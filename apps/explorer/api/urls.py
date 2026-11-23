from django.urls import path

from apps.explorer.api import views

app_name = "explorer_api"

urlpatterns = [
    path("search/", views.search_api, name="search_api"),
]
