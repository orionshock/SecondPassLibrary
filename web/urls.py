from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.index, name="index"),
    path("app/", views.app_dashboard, name="app"),

    # Canonical reading session routes (sessions-first).
    path("reading/export/", views.reading_export, name="reading_export"),
    path("reading/import/", views.reading_import, name="reading_import"),
    path("reading/sessions/", views.reading_sessions, name="reading_sessions"),
    path(
        "reading/sessions/books/<str:book_id>/<str:session_id>/",
        views.reading_session_marginalia,
        name="reading_session_marginalia",
    ),
    path(
        "reading/sessions/books/<str:book_id>/",
        views.reading_book_sessions_canonical,
        name="reading_book_sessions_canonical",
    ),

    path("server/", views.server_settings, name="server_settings"),
    path("profile/", views.profile, name="profile"),
    path("profile/password/", views.profile_password, name="profile_password"),
    path("client-api/authorize/", views.client_api_authorize, name="client_api_authorize"),
    path("library/", views.library_browse, name="library"),
    path("library/books/<str:book_id>/", views.book_detail, name="book_detail"),
    path("library/books/<str:book_id>/edit/", views.book_edit, name="book_edit"),
    path("imports/", views.imports, name="imports"),
    path("groups/", views.groups, name="groups"),
    path("groups/new/", views.group_new, name="group_new"),
    path("groups/<str:group_id>/", views.group_detail, name="group_detail"),
    path("groups/<str:group_id>/edit/", views.group_edit, name="group_edit"),
    path("users/", views.users, name="users"),
    path("users/new/", views.user_new, name="user_new"),
    path("users/<str:user_id>/edit/", views.user_edit, name="user_edit"),
    path("shelves/", views.shelves, name="shelves"),
    path("shelves/new/", views.shelf_new, name="shelf_new"),
    path("shelves/<str:shelf_id>/", views.shelf_detail, name="shelf_detail"),
    path("shelves/<str:shelf_id>/edit/", views.shelf_edit, name="shelf_edit"),
]
