from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.index, name="index"),
    path("setup/", views.setup, name="setup"),
    path(
        "client-api/authorize/",
        views.client_api_authorize,
        name="client_api_authorize",
    ),
]
