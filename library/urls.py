from django.urls import path

from library.catalog.axis_views import (
    AuthorDetailView,
    AuthorListView,
    CatalogTagDetailView,
    CatalogTagListView,
    SeriesDetailView,
    SeriesListView,
)
from library.catalog.views import BookDetailView, BookListView
from library.catalog.identifier_views import BookIdentifierDetailView, BookIdentifierListCreateView
from library.groups.book_assignment_views import (
    GroupBookAssignmentDetailView,
    GroupBookAssignmentListView,
)
from library.groups.browse_views import (
    GroupAuthorListView,
    GroupCatalogTagListView,
    GroupSeriesListView,
)
from library.groups.membership_views import (
    LibraryGroupMembershipDetailView,
    LibraryGroupMembershipListView,
)
from library.groups.views import LibraryGroupDetailView, LibraryGroupListView
from library.imports.views import ImportUploadView


app_name = "library"

urlpatterns = [
    path("authors/", AuthorListView.as_view(), name="author-list"),
    path("authors/<uuid:axis_id>/", AuthorDetailView.as_view(), name="author-detail"),
    path("books/", BookListView.as_view(), name="book-list"),
    path("books/<uuid:book_id>/", BookDetailView.as_view(), name="book-detail"),
    path(
        "books/<uuid:book_id>/identifiers/",
        BookIdentifierListCreateView.as_view(),
        name="book-identifier-list",
    ),
    path(
        "books/<uuid:book_id>/identifiers/<uuid:identifier_id>/",
        BookIdentifierDetailView.as_view(),
        name="book-identifier-detail",
    ),
    path("groups/", LibraryGroupListView.as_view(), name="group-list"),
    path("groups/<uuid:group_id>/", LibraryGroupDetailView.as_view(), name="group-detail"),
    path("groups/<uuid:group_id>/authors/", GroupAuthorListView.as_view(), name="group-author-list"),
    path(
        "groups/<uuid:group_id>/books/",
        GroupBookAssignmentListView.as_view(),
        name="group-book-list",
    ),
    path(
        "groups/<uuid:group_id>/books/<uuid:book_id>/",
        GroupBookAssignmentDetailView.as_view(),
        name="group-book-assignment-detail",
    ),
    path(
        "groups/<uuid:group_id>/memberships/",
        LibraryGroupMembershipListView.as_view(),
        name="group-membership-list",
    ),
    path(
        "groups/<uuid:group_id>/memberships/<uuid:user_id>/",
        LibraryGroupMembershipDetailView.as_view(),
        name="group-membership-detail",
    ),
    path("groups/<uuid:group_id>/series/", GroupSeriesListView.as_view(), name="group-series-list"),
    path("groups/<uuid:group_id>/tags/", GroupCatalogTagListView.as_view(), name="group-tag-list"),
    path("imports/", ImportUploadView.as_view(), name="import-upload"),
    path("series/", SeriesListView.as_view(), name="series-list"),
    path("series/<uuid:axis_id>/", SeriesDetailView.as_view(), name="series-detail"),
    path("tags/", CatalogTagListView.as_view(), name="tag-list"),
    path("tags/<uuid:axis_id>/", CatalogTagDetailView.as_view(), name="tag-detail"),
]
