from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActiveSessionView,
    AnnotationViewSet,
    CloseSessionView,
    OpenBookView,
    ReadingProgressViewSet,
    ReadingSessionViewSet,
    StartOverView,
)

app_name = "reading"

router = DefaultRouter()
router.register(r"sessions", ReadingSessionViewSet, basename="readingsession")
router.register(r"annotations", AnnotationViewSet, basename="annotation")

urlpatterns = [
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
