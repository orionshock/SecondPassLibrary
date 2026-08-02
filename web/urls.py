from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("setup/", views.setup, name="setup"),
]
