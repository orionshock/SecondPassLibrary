from __future__ import annotations

from django.test import SimpleTestCase
from rest_framework.authentication import SessionAuthentication

from library.api_access import LibraryBearerReadMixin
from library.urls import urlpatterns


class LibraryBearerRouteInventoryTests(SimpleTestCase):
    def test_every_library_route_has_an_explicit_bearer_category(self):
        readable = {
            "author-list",
            "author-detail",
            "book-list",
            "book-detail",
            "book-download",
            "group-list",
            "group-detail",
            "group-author-list",
            "group-book-list",
            "group-series-list",
            "group-tag-list",
            "series-list",
            "series-detail",
            "tag-list",
            "tag-detail",
        }
        mutation_only_with_boundary = {"group-book-assignment-detail"}
        session_only = {
            "book-cover",
            "group-membership-list",
            "group-membership-detail",
            "import-upload",
        }
        routes = {pattern.name: pattern.callback.view_class for pattern in urlpatterns}

        self.assertEqual(set(routes), readable | mutation_only_with_boundary | session_only)
        for name in readable | mutation_only_with_boundary:
            with self.subTest(route=name):
                self.assertTrue(issubclass(routes[name], LibraryBearerReadMixin))
        for name in session_only:
            with self.subTest(route=name):
                self.assertEqual(routes[name].authentication_classes, [SessionAuthentication])
