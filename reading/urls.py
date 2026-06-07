from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActiveSessionView,
    AnnotationViewSet,
    CloseSessionView,
    OpenBookView,
    ReadingProgressViewSet,
    ReadingSessionViewSet,
    RecentSessionsView,
    StartOverView,
)
from .export_views import (
    AllMarginaliaExportView,
    BookMarginaliaExportView,
    SessionMarginaliaExportView,
)

app_name = "reading"

router = DefaultRouter()
router.register(r"sessions", ReadingSessionViewSet, basename="readingsession")
router.register(r"annotations", AnnotationViewSet, basename="annotation")

urlpatterns = [
    path(
        "export/",
        AllMarginaliaExportView.as_view(),
        name="export_all_marginalia",
    ),
    path(
        "export/books/<uuid:book_id>/",
        BookMarginaliaExportView.as_view(),
        name="export_book_marginalia",
    ),
    path(
        "export/books/<uuid:book_id>/<uuid:session_id>/",
        SessionMarginaliaExportView.as_view(),
        name="export_session_marginalia",
    ),
    path(
        "sessions/recent/",
        RecentSessionsView.as_view(),
        name="sessions_recent",
    ),
    path("", include(router.urls)),
    path(
        "books/<uuid:book_id>/active-session/",
        ActiveSessionView.as_view(),
        name="active_session",
    ),
    path(
        "books/<uuid:book_id>/start-over/", StartOverView.as_view(), name="start_over"
    ),
    path(
        "books/<uuid:book_id>/open/",
        OpenBookView.as_view(),
        name="open_book",
    ),
    path(
        "sessions/<uuid:session_id>/progress/",
        ReadingProgressViewSet.as_view(
            {"get": "retrieve", "put": "update", "patch": "partial_update"}
        ),
        name="session_progress",
    ),
    path(
        "sessions/<uuid:session_id>/close/",
        CloseSessionView.as_view(),
        name="session_close",
    ),
]
