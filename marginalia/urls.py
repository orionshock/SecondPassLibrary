from django.urls import path

from .annotations.views import SessionAnnotationBatchView, SessionAnnotationListView
from .detail_views import MarginaliaSessionDetailView
from .lifecycle_views import (
    MarginaliaBookActiveSessionView,
    MarginaliaBookOpenView,
    MarginaliaBookStartOverView,
    MarginaliaSessionCloseView,
    MarginaliaSessionProgressView,
)
from .views import (
    MarginaliaBookDetailView,
    MarginaliaBookListView,
    MarginaliaBookSessionListView,
    MarginaliaSessionListView,
)


app_name = "marginalia"

urlpatterns = [
    path("sessions/", MarginaliaSessionListView.as_view(), name="session-list"),
    path(
        "sessions/<uuid:session_id>/",
        MarginaliaSessionDetailView.as_view(),
        name="session-detail",
    ),
    path(
        "sessions/<uuid:session_id>/progress/",
        MarginaliaSessionProgressView.as_view(),
        name="session-progress",
    ),
    path(
        "sessions/<uuid:session_id>/close/",
        MarginaliaSessionCloseView.as_view(),
        name="session-close",
    ),
    path(
        "sessions/<uuid:session_id>/annotations/",
        SessionAnnotationListView.as_view(),
        name="session-annotation-list",
    ),
    path(
        "sessions/<uuid:session_id>/annotations/batch/",
        SessionAnnotationBatchView.as_view(),
        name="session-annotation-batch",
    ),
    path("books/", MarginaliaBookListView.as_view(), name="book-list"),
    path(
        "books/<uuid:book_id>/open/",
        MarginaliaBookOpenView.as_view(),
        name="book-open",
    ),
    path(
        "books/<uuid:book_id>/active-session/",
        MarginaliaBookActiveSessionView.as_view(),
        name="book-active-session",
    ),
    path(
        "books/<uuid:book_id>/start-over/",
        MarginaliaBookStartOverView.as_view(),
        name="book-start-over",
    ),
    path(
        "books/<uuid:book_id>/sessions/",
        MarginaliaBookSessionListView.as_view(),
        name="book-session-list",
    ),
    path(
        "books/<uuid:book_id>/",
        MarginaliaBookDetailView.as_view(),
        name="book-detail",
    ),
]
