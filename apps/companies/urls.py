from django.urls import path

from apps.companies import views

app_name = "companies"

urlpatterns = [
    path("", views.companies_page, name="list"),
    path("add/", views.add_company, name="add"),
]
