from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.index, name="index"),
    path("app/", views.app_dashboard, name="app"),
    path("library/", views.library_browse, name="library"),
    path("library/books/<str:book_id>/", views.book_detail, name="book_detail"),
    path("imports/", views.imports, name="imports"),
    path("groups/", views.groups, name="groups"),
    path("groups/<str:group_id>/", views.group_detail, name="group_detail"),
]
