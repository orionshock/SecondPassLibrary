from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from accounts.models import UserProfile
from core.server_settings import set_advanced_library_groups_enabled
from library.models import (
    Author,
    BookGroupAssignment,
    CatalogTag,
    LibraryGroup,
    LibraryGroupMembership,
    Series,
)
from tests.library.helpers import (
    create_catalog_book,
    response_book_counts,
    response_names,
    response_titles,
    set_user_role,
)


def preview_titles(row):
    return [book["title"] for book in row["preview_books"]]


class LibraryGroupBrowseTests(TestCase):
    def setUp(self):
        cache.clear()
        set_advanced_library_groups_enabled(True)
        User = get_user_model()
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.other = User.objects.create_user(username="other", password="pw")
        set_user_role(self.reader, UserProfile.ROLE_READER)
        set_user_role(self.other, UserProfile.ROLE_READER)

        self.club = LibraryGroup.objects.create(name="Club")
        self.family = LibraryGroup.objects.create(name="Family")
        self.hidden = LibraryGroup.objects.create(name="Hidden")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.club)
        LibraryGroupMembership.objects.create(user=self.reader, group=self.family)
        LibraryGroupMembership.objects.create(user=self.other, group=self.hidden)

        self.alpha = Author.objects.create(name="Alpha Author", sort_name="Alpha Author")
        self.beta = Author.objects.create(name="Beta Author", sort_name="Beta Author")
        self.gamma = Author.objects.create(name="Gamma Author", sort_name="Gamma Author")
        self.first_series = Series.objects.create(name="First Series", sort_name="First Series")
        self.second_series = Series.objects.create(name="Second Series", sort_name="Second Series")
        self.fantasy = CatalogTag.objects.create(name="Fantasy", normalized_name="fantasy", slug="fantasy")
        self.mystery = CatalogTag.objects.create(name="Mystery", normalized_name="mystery", slug="mystery")

        self.club_alpha = create_catalog_book(
            "Club Alpha",
            author=self.alpha,
            series=self.first_series,
            series_index="1.00",
            tag=self.fantasy,
            group=self.club,
            publisher="Alpha House",
            description="club dresden file",
        )
        self.club_beta = create_catalog_book(
            "Club Beta",
            author=self.beta,
            series=self.first_series,
            series_index="2.00",
            tag=self.mystery,
            group=self.club,
            publisher="Beta House",
        )
        self.family_gamma = create_catalog_book(
            "Family Gamma",
            author=self.gamma,
            series=self.second_series,
            series_index="1.00",
            tag=self.fantasy,
            group=self.family,
            publisher="Gamma House",
        )
        self.shared = create_catalog_book(
            "Shared Book",
            author=self.alpha,
            series=self.second_series,
            series_index="3.00",
            tag=self.fantasy,
            group=self.club,
            publisher="Shared House",
        )
        BookGroupAssignment.objects.create(book=self.shared, group=self.family)
        self.hidden_book = create_catalog_book(
            "Hidden Book",
            author=self.alpha,
            series=self.second_series,
            series_index="9.00",
            tag=self.mystery,
            group=self.hidden,
            publisher="Hidden House",
            description="hidden dresden file",
        )

        self.assertTrue(self.client.login(username="reader", password="pw"))

    def test_group_books_include_only_books_assigned_to_group(self):
        response = self.client.get(f"/api/v1/library/groups/{self.club.id}/books/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Club Alpha", "Club Beta", "Shared Book"])
        row = response.json()["results"][0]
        self.assertEqual([tag["name"] for tag in row["tags"]], ["Fantasy"])
        self.assertIn("file_format", row)
        for detail_field in ("catalog_tags", "file", "groups", "identifiers"):
            self.assertNotIn(detail_field, row)

    def test_group_books_exclude_books_visible_through_another_group(self):
        response = self.client.get(f"/api/v1/library/groups/{self.club.id}/books/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Family Gamma", response_titles(response))

    def test_inaccessible_group_returns_404(self):
        response = self.client.get(f"/api/v1/library/groups/{self.hidden.id}/books/")

        self.assertEqual(response.status_code, 404)

    def test_inaccessible_group_with_invalid_ordering_returns_404(self):
        endpoints = ["books", "authors", "series", "tags"]

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(
                    f"/api/v1/library/groups/{self.hidden.id}/{endpoint}/",
                    {"ordering": "created_at"},
                )
                self.assertEqual(response.status_code, 404)

    def test_group_books_q_filter_order_and_pagination_compose(self):
        response = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/books/",
            {
                "q": "club",
                "tag": self.fantasy.slug,
                "ordering": "-publisher",
                "page_size": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Club Alpha"])
        self.assertIsNone(response.json()["next"])

    def test_group_books_first_and_subsequent_pages_use_normal_envelope(self):
        url = f"/api/v1/library/groups/{self.club.id}/books/"

        first = self.client.get(url, {"page_size": 2})
        second = self.client.get(url, {"page_size": 2, "page": 2})

        self.assertEqual(response_titles(first), ["Club Alpha", "Club Beta"])
        self.assertIsNotNone(first.json()["next"])
        self.assertIsNone(first.json()["previous"])
        self.assertEqual(response_titles(second), ["Shared Book"])
        self.assertIsNone(second.json()["next"])
        self.assertIsNotNone(second.json()["previous"])

    def test_group_authors_include_only_group_authors_and_count_group_books(self):
        response = self.client.get(f"/api/v1/library/groups/{self.club.id}/authors/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_names(response), ["Alpha Author", "Beta Author"])
        self.assertEqual(response_book_counts(response), {"Alpha Author": 2, "Beta Author": 1})

    def test_group_series_include_only_group_series_and_count_group_books(self):
        response = self.client.get(f"/api/v1/library/groups/{self.club.id}/series/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_names(response), ["First Series", "Second Series"])
        self.assertEqual(response_book_counts(response), {"First Series": 2, "Second Series": 1})

    def test_group_author_and_series_preview_books_are_exact_group_scoped(self):
        authors = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/authors/",
            {"include_preview_books": "true"},
        )
        series = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/series/",
            {"include_preview_books": "true"},
        )
        tags = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/tags/",
            {"include_preview_books": "true"},
        )

        self.assertEqual(authors.status_code, 200)
        alpha = next(row for row in authors.json()["results"] if row["name"] == "Alpha Author")
        self.assertEqual(preview_titles(alpha), ["Club Alpha", "Shared Book"])
        self.assertNotIn("Family Gamma", preview_titles(alpha))
        for preview in alpha["preview_books"]:
            self.assertEqual(set(preview), {"id", "title", "cover_url"})

        self.assertEqual(series.status_code, 200)
        second = next(row for row in series.json()["results"] if row["name"] == "Second Series")
        self.assertEqual(preview_titles(second), ["Shared Book"])
        self.assertNotIn("Family Gamma", preview_titles(second))

        self.assertEqual(tags.status_code, 200)
        self.assertNotIn("preview_books", tags.json()["results"][0])

    def test_group_tags_include_only_group_tags_and_count_group_books(self):
        response = self.client.get(f"/api/v1/library/groups/{self.club.id}/tags/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_names(response), ["Fantasy", "Mystery"])
        self.assertEqual(response_book_counts(response), {"Fantasy": 2, "Mystery": 1})
        for tag in response.json()["results"]:
            self.assertEqual(set(tag), {"id", "name", "slug", "book_count"})

    def test_group_author_and_series_tag_filters_use_slug_without_duplicates(self):
        authors = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/authors/",
            {"tag": self.fantasy.slug},
        )
        series = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/series/",
            {"tag": self.fantasy.slug},
        )

        self.assertEqual(response_names(authors), ["Alpha Author"])
        self.assertEqual(response_book_counts(authors), {"Alpha Author": 2})
        self.assertEqual(response_names(series), ["First Series", "Second Series"])

    def test_invalid_ordering_returns_400_for_visible_group_axis_endpoints(self):
        endpoints = ["books", "authors", "series", "tags"]

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(
                    f"/api/v1/library/groups/{self.club.id}/{endpoint}/",
                    {"ordering": "created_at"},
                )
                self.assertEqual(response.status_code, 400)

    def test_group_axis_q_and_ordering_are_group_scoped(self):
        authors = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/authors/",
            {"q": "alpha", "ordering": "-book_count"},
        )
        series = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/series/",
            {"q": "second", "ordering": "-name"},
        )
        tags = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/tags/",
            {"q": "fantasy", "ordering": "-book_count"},
        )

        self.assertEqual(response_names(authors), ["Alpha Author"])
        self.assertEqual(response_book_counts(authors), {"Alpha Author": 2})
        self.assertEqual(response_names(series), ["Second Series"])
        self.assertEqual(response_book_counts(series), {"Second Series": 1})
        self.assertEqual(response_names(tags), ["Fantasy"])
        self.assertEqual(response_book_counts(tags), {"Fantasy": 2})
