from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from accounts.models import UserProfile
from core.server_settings import set_advanced_library_groups_enabled
from library.models import (
    Author,
    BookAuthor,
    BookGroupAssignment,
    BookIdentifier,
    CatalogTag,
    LibraryGroup,
    LibraryGroupMembership,
    Series,
)
from shelves.models import Shelf, ShelfItem
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

        self.alpha = Author.objects.create(
            name="Alpha Author", sort_name="Alpha Author"
        )
        self.beta = Author.objects.create(name="Beta Author", sort_name="Beta Author")
        self.gamma = Author.objects.create(
            name="Gamma Author", sort_name="Gamma Author"
        )
        self.first_series = Series.objects.create(
            name="First Series", sort_name="First Series"
        )
        self.second_series = Series.objects.create(
            name="Second Series", sort_name="Second Series"
        )
        self.fantasy = CatalogTag.objects.create(
            name="Fantasy", normalized_name="fantasy", slug="fantasy"
        )
        self.mystery = CatalogTag.objects.create(
            name="Mystery", normalized_name="mystery", slug="mystery"
        )

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
        self.assertEqual(
            response_titles(response), ["Club Alpha", "Club Beta", "Shared Book"]
        )
        row = response.json()["results"][0]
        self.assertEqual([tag["name"] for tag in row["catalog_tags"]], ["Fantasy"])
        self.assertNotIn("tags", row)
        self.assertIn("file_format", row)
        for detail_field in (
            "description",
            "identifiers",
            "groups",
            "file",
            "download_url",
            "file_size",
            "checksum",
            "book_file",
            "storage_path",
            "source_filename",
        ):
            self.assertNotIn(detail_field, row)

    def test_group_author_ordering_uses_the_lowest_positioned_author_only(self):
        BookAuthor.objects.create(book=self.club_beta, author=self.alpha, position=1)

        response = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/books/",
            {"ordering": "author"},
        )

        self.assertEqual(
            response_titles(response),
            ["Club Alpha", "Shared Book", "Club Beta"],
        )

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

        search = self.client.get(
            f"/api/v1/library/groups/{self.hidden.id}/search",
            {"q": "book", "ordering": "created_at"},
        )
        self.assertEqual(search.status_code, 404)

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

    def test_group_books_q_matches_only_title_and_sort_title(self):
        self.club_alpha.sort_title = "Private Catalog Alias"
        self.club_alpha.save(update_fields=["sort_title", "updated_at"])

        title = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/books/", {"q": "club alpha"}
        )
        sort_title = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/books/", {"q": "catalog alias"}
        )

        self.assertEqual(response_titles(title), ["Club Alpha"])
        self.assertEqual(response_titles(sort_title), ["Club Alpha"])
        for term in (
            "beta author",
            "first series",
            "fantasy",
            "alpha house",
            "dresden file",
        ):
            with self.subTest(term=term):
                response = self.client.get(
                    f"/api/v1/library/groups/{self.club.id}/books/", {"q": term}
                )
                self.assertEqual(response_titles(response), [])

    def test_group_search_matches_global_broad_fields_within_group(self):
        self.club_alpha.subtitle = "Private subtitle"
        self.club_alpha.save(update_fields=["subtitle", "updated_at"])
        BookIdentifier.objects.create(
            book=self.club_alpha,
            scheme=BookIdentifier.SCHEME_OTHER,
            value="CLUB-IDENTIFIER-42",
            normalized_value="club-identifier-42",
        )
        cases = {
            "private subtitle": ["Club Alpha"],
            "beta author": ["Club Beta"],
            "first series": ["Club Alpha", "Club Beta"],
            "club-identifier-42": ["Club Alpha"],
            "fantasy": ["Club Alpha", "Shared Book"],
            "alpha house": ["Club Alpha"],
            "dresden file": ["Club Alpha"],
            "hidden dresden": [],
        }

        for term, expected in cases.items():
            with self.subTest(term=term):
                response = self.client.get(
                    f"/api/v1/library/groups/{self.club.id}/search", {"q": term}
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response_titles(response), expected)

    def test_group_search_blank_query_ordering_and_pagination_match_global_search(self):
        endpoint = f"/api/v1/library/groups/{self.club.id}/search"
        for query in ({}, {"q": ""}, {"q": "  "}):
            with self.subTest(query=query):
                response = self.client.get(endpoint, query)
                self.assertEqual(
                    response.json(),
                    {
                        "count": 0,
                        "next": None,
                        "previous": None,
                        "catalog_tags": [],
                        "results": [],
                    },
                )

        orderings = {
            "title": "Club Alpha",
            "-title": "Club Beta",
            "author": "Club Alpha",
            "-author": "Club Beta",
            "series": "Club Alpha",
            "-series": "Club Alpha",
        }
        for ordering, expected_first in orderings.items():
            with self.subTest(ordering=ordering):
                response = self.client.get(
                    endpoint,
                    {"q": "club", "ordering": ordering, "page_size": 1},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["count"], 2)
                self.assertEqual(response_titles(response), [expected_first])

        invalid = self.client.get(endpoint, {"q": "club", "ordering": "publisher"})
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("ordering", invalid.json())

    def test_group_books_exclude_shelf_composes_with_filters_order_and_pagination(self):
        shelf = Shelf.objects.create(
            name="Club shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.club,
            created_by=self.reader,
        )
        ShelfItem.objects.create(
            shelf=shelf,
            book=self.club_alpha,
            position=0,
            added_by=self.reader,
        )

        response = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/books/",
            {
                "exclude_shelf": str(shelf.id),
                "q": "club",
                "tag": self.mystery.slug,
                "author": str(self.beta.id),
                "series": str(self.first_series.id),
                "publisher": "Beta House",
                "ordering": "-title",
                "page": 1,
                "page_size": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Club Beta"])

    def test_group_books_exclude_shelf_validates_id_visibility_and_group_owner(self):
        club_shelf = Shelf.objects.create(
            name="Club shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.club,
            created_by=self.reader,
        )
        ShelfItem.objects.create(
            shelf=club_shelf,
            book=self.club_alpha,
            position=0,
            added_by=self.reader,
        )
        excluded = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/books/",
            {"exclude_shelf": str(club_shelf.id)},
        )
        self.assertEqual(excluded.status_code, 200)
        self.assertNotIn("Club Alpha", response_titles(excluded))

        family_shelf = Shelf.objects.create(
            name="Family shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.family,
            created_by=self.reader,
        )
        mismatch = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/books/",
            {"exclude_shelf": str(family_shelf.id)},
        )
        self.assertEqual(mismatch.status_code, 404)

        malformed = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/books/",
            {"exclude_shelf": "not-a-uuid"},
        )
        missing = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/books/",
            {"exclude_shelf": "00000000-0000-0000-0000-000000000001"},
        )
        hidden_shelf = Shelf.objects.create(
            name="Hidden shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.hidden,
            created_by=self.other,
        )
        hidden = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/books/",
            {"exclude_shelf": str(hidden_shelf.id)},
        )

        self.assertEqual(malformed.status_code, 400)
        self.assertIn("exclude_shelf", malformed.json())
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(hidden.status_code, 404)

    def test_group_search_exclude_shelf_requires_the_requested_group_owner(self):
        club_shelf = Shelf.objects.create(
            name="Club shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.club,
            created_by=self.reader,
        )
        ShelfItem.objects.create(
            shelf=club_shelf,
            book=self.club_alpha,
            position=0,
            added_by=self.reader,
        )
        endpoint = f"/api/v1/library/groups/{self.club.id}/search"

        excluded = self.client.get(
            endpoint,
            {"q": "club", "exclude_shelf": str(club_shelf.id)},
        )
        self.assertEqual(response_titles(excluded), ["Club Beta"])

        personal = Shelf.objects.create(
            name="Personal",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            created_by=self.reader,
        )
        mismatch = self.client.get(
            endpoint,
            {"q": "club", "exclude_shelf": str(personal.id)},
        )
        self.assertEqual(mismatch.status_code, 404)

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
        self.assertEqual(
            response_book_counts(response), {"Alpha Author": 2, "Beta Author": 1}
        )

    def test_group_series_include_only_group_series_and_count_group_books(self):
        response = self.client.get(f"/api/v1/library/groups/{self.club.id}/series/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_names(response), ["First Series", "Second Series"])
        self.assertEqual(
            response_book_counts(response), {"First Series": 2, "Second Series": 1}
        )

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
        alpha = next(
            row for row in authors.json()["results"] if row["name"] == "Alpha Author"
        )
        self.assertEqual(preview_titles(alpha), ["Club Alpha", "Shared Book"])
        self.assertNotIn("Family Gamma", preview_titles(alpha))
        for preview in alpha["preview_books"]:
            self.assertEqual(set(preview), {"id", "title", "cover_url"})

        self.assertEqual(series.status_code, 200)
        second = next(
            row for row in series.json()["results"] if row["name"] == "Second Series"
        )
        self.assertEqual(preview_titles(second), ["Shared Book"])
        self.assertNotIn("Family Gamma", preview_titles(second))

        self.assertEqual(tags.status_code, 200)
        self.assertNotIn("preview_books", tags.json()["results"][0])

    def test_group_author_and_series_previews_honor_the_bounded_limit(self):
        for endpoint in ("authors", "series"):
            with self.subTest(endpoint=endpoint):
                limited = self.client.get(
                    f"/api/v1/library/groups/{self.club.id}/{endpoint}/",
                    {"preview_limit": "1"},
                )
                self.assertEqual(limited.status_code, 200)
                self.assertTrue(
                    all(
                        len(row["preview_books"]) == 1
                        for row in limited.json()["results"]
                    )
                )

                disabled = self.client.get(
                    f"/api/v1/library/groups/{self.club.id}/{endpoint}/",
                    {"preview_limit": "0"},
                )
                self.assertEqual(disabled.status_code, 200)
                self.assertTrue(
                    all(
                        "preview_books" not in row for row in disabled.json()["results"]
                    )
                )

                invalid = self.client.get(
                    f"/api/v1/library/groups/{self.club.id}/{endpoint}/",
                    {"preview_limit": "25"},
                )
                self.assertEqual(invalid.status_code, 400)
                self.assertEqual(set(invalid.json()), {"preview_limit"})

    def test_group_tags_include_only_group_tags_and_count_group_books(self):
        response = self.client.get(f"/api/v1/library/groups/{self.club.id}/tags/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_names(response), ["Fantasy", "Mystery"])
        self.assertEqual(response_book_counts(response), {"Fantasy": 2, "Mystery": 1})
        for tag in response.json()["results"]:
            self.assertEqual(set(tag), {"id", "name", "slug", "book_count"})

    def test_group_tags_ignore_preview_only_params(self):
        response = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/tags/",
            {
                "include_preview_books": "true",
                "preview_limit": "invalid",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["results"])
        self.assertTrue(
            all("preview_books" not in row for row in response.json()["results"])
        )

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

    def test_group_author_and_series_share_normalized_search_and_exclude_id(self):
        self.beta.normalized_name = "pen name"
        self.beta.save(update_fields=["normalized_name", "updated_at"])
        self.second_series.normalized_name = "alternate saga"
        self.second_series.save(update_fields=["normalized_name", "updated_at"])

        authors = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/authors/",
            {"q": "  PEN   NAME ", "exclude_id": str(self.alpha.id)},
        )
        series = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/series/",
            {"q": "  ALTERNATE   SAGA ", "exclude_id": str(self.first_series.id)},
        )

        self.assertEqual(response_names(authors), ["Beta Author"])
        self.assertEqual(response_names(series), ["Second Series"])

    def test_group_tag_counts_use_the_complete_scoped_population(self):
        books = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/books/",
            {"page_size": 1},
        )
        tags = self.client.get(f"/api/v1/library/groups/{self.club.id}/tags/")

        self.assertEqual(len(books.json()["results"]), 1)
        self.assertEqual(response_book_counts(tags), {"Fantasy": 2, "Mystery": 1})

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
