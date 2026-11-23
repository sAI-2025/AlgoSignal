from django.urls import path

from apps.scanner import views

app_name = "scanner"

urlpatterns = [
    path("", views.signals_page, name="signals"),
]
