from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .annotations.views import AnnotationViewSet
from .progress.views import ReadingProgressViewSet
from .sessions.views import (
    ActiveSessionView,
    CloseSessionView,
    OpenBookView,
    ReadingActivitySummaryView,
    ReadingSessionViewSet,
    RecentSessionsView,
    StartOverView,
)
from .exports.views import AllMarginaliaExportView
from .imports.views import (
    MarginaliaImportApplyView,
    MarginaliaImportPreviewView,
    MarginaliaImportUnmatchedView,
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
        "import/preview/",
        MarginaliaImportPreviewView.as_view(),
        name="import_marginalia_preview",
    ),
    path(
        "import/apply/",
        MarginaliaImportApplyView.as_view(),
        name="import_marginalia_apply",
    ),
    path(
        "import/unmatched/",
        MarginaliaImportUnmatchedView.as_view(),
        name="import_marginalia_unmatched",
    ),
    path(
        "sessions/recent/",
        RecentSessionsView.as_view(),
        name="sessions_recent",
    ),
    path(
        "books/activity-summary/",
        ReadingActivitySummaryView.as_view(),
        name="books_activity_summary",
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
