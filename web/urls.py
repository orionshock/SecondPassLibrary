from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.index, name="index"),
    path("app/", views.app_dashboard, name="app"),
    path("library/", views.library_browse, name="library"),
]

