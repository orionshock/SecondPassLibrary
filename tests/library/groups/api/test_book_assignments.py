from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

from core import server_settings
from core.errors import ErrorCode
from accounts.models import UserProfile
from library.groups.services import (
    ensure_book_public_assignment,
    ensure_user_public_membership,
)
from library.models import Author, BookGroupAssignment, LibraryGroup, Series
from tests.library.groups.helpers import BaseLibraryGroupsAPITest
from tests.utils.books import create_file_backed_book
from tests.utils.responses import (
    assert_response,
    payload_dict,
    payload_list,
    response_data_dict,
)

User = get_user_model()


pytestmark = [pytest.mark.integration]


class LibraryGroupBooksAndCurationAPITest(BaseLibraryGroupsAPITest):
    def setUp(self):
        super().setUp()
        server_settings.set_advanced_library_groups_enabled(True)

        self.reader = User.objects.create_user(
            username="reader", email="reader@example.com", password="pw"
        )
        ensure_user_public_membership(user=self.reader)
        reader_profile, _ = UserProfile.objects.get_or_create(user=self.reader)
        reader_profile.role = UserProfile.ROLE_READER
        reader_profile.save(update_fields=["role", "updated_at"])

        self.curator = User.objects.create_user(
            username="curator", email="curator@example.com", password="pw"
        )
        ensure_user_public_membership(user=self.curator)
        curator_profile, _ = UserProfile.objects.get_or_create(user=self.curator)
        curator_profile.role = UserProfile.ROLE_READER
        curator_profile.save(update_fields=["role", "updated_at"])

        self.librarian = User.objects.create_user(
            username="librarian", email="librarian@example.com", password="pw"
        )
        ensure_user_public_membership(user=self.librarian)
        librarian_profile, _ = UserProfile.objects.get_or_create(user=self.librarian)
        librarian_profile.role = UserProfile.ROLE_LIBRARIAN
        librarian_profile.save(update_fields=["role", "updated_at"])

        self.group = LibraryGroup.objects.create(name="Group")
        self.create_membership(
            user=self.curator,
            group=self.group,
            is_curator=True,
        )

        self.other_group = LibraryGroup.objects.create(name="Other")

        self.visible_group = LibraryGroup.objects.create(name="VisibleGroup")
        self.create_membership(
            user=self.reader,
            group=self.visible_group,
        )

        self.book_public = create_file_backed_book(
            title="Public Book", assign_public=False
        ).book
        ensure_book_public_assignment(book=self.book_public, added_by=None)

        self.book_only_group = create_file_backed_book(
            title="OnlyGroup", assign_public=False
        ).book
        BookGroupAssignment.objects.create(
            book=self.book_only_group, group=self.group, added_by=self.librarian
        )

        self.book_inaccessible = create_file_backed_book(
            title="Inaccessible", assign_public=False
        ).book
        hidden = LibraryGroup.objects.create(name="Hidden")
        other = User.objects.create_user(
            username="other", email="other@example.com", password="pw"
        )
        ensure_user_public_membership(user=other)
        self.create_membership(
            user=other,
            group=hidden,
        )
        BookGroupAssignment.objects.create(
            book=self.book_inaccessible, group=hidden, added_by=self.librarian
        )

        BookGroupAssignment.objects.create(
            book=self.book_public, group=self.visible_group, added_by=self.librarian
        )
        BookGroupAssignment.objects.create(
            book=self.book_inaccessible,
            group=self.visible_group,
            added_by=self.librarian,
        )

    def test_reader_group_books_shows_books_in_groups_they_belong_to(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(
            self.client.get(f"/api/v1/library/groups/{self.visible_group.id}/books/"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        payload = response_data_dict(response)
        self.assertIn("count", payload)
        self.assertIn("results", payload)
        titles = {b["title"] for b in payload_list(payload, "results")}
        self.assertIn("Public Book", titles)
        self.assertIn("Inaccessible", titles)

    def test_librarian_group_books_sees_all_books_in_group(self):
        self.client.login(username="librarian", password="pw")
        response = assert_response(
            self.client.get(f"/api/v1/library/groups/{self.visible_group.id}/books/"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        payload = response_data_dict(response)
        titles = {b["title"] for b in payload_list(payload, "results")}
        self.assertIn("Public Book", titles)
        self.assertIn("Inaccessible", titles)

    def test_group_books_ordering_title_author_series_and_invalid(self):
        author_a = Author.objects.create(name="Ada Author")
        author_z = Author.objects.create(name="Zed Author")
        series_a = Series.objects.create(name="Alpha Series")
        series_z = Series.objects.create(name="Zulu Series")

        self.book_public.title = "Charlie"
        self.book_public.series = series_z
        self.book_public.series_index = 1
        self.book_public.save(update_fields=["title", "series", "series_index", "updated_at"])
        self.book_public.authors.set([author_z])

        self.book_inaccessible.title = "Bravo"
        self.book_inaccessible.series = series_a
        self.book_inaccessible.series_index = 2
        self.book_inaccessible.save(update_fields=["title", "series", "series_index", "updated_at"])
        self.book_inaccessible.authors.set([author_a])

        self.client.login(username="librarian", password="pw")

        expectations = {
            "title": ["Bravo", "Charlie"],
            "author": ["Bravo", "Charlie"],
            "series": ["Bravo", "Charlie"],
        }
        for ordering, expected_titles in expectations.items():
            response = assert_response(
                self.client.get(
                    f"/api/v1/library/groups/{self.visible_group.id}/books/?ordering={ordering}"
                ),
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, ordering)
            self.assertEqual(
                [row["title"] for row in payload_list(response_data_dict(response), "results")],
                expected_titles,
            )

        invalid = assert_response(
            self.client.get(
                f"/api/v1/library/groups/{self.visible_group.id}/books/?ordering=created_at"
            ),
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ordering", response_data_dict(invalid))

    def test_reader_cannot_add_or_remove_books(self):
        self.client.login(username="reader", password="pw")
        add = assert_response(
            self.client.post(
                f"/api/v1/library/groups/{self.group.id}/books/",
                data={"book": str(self.book_public.id)},
                format="json",
            ),
        )
        self.assertEqual(add.status_code, status.HTTP_404_NOT_FOUND)

        delete = assert_response(
            self.client.delete(
                f"/api/v1/library/groups/{self.group.id}/books/{self.book_only_group.id}/"
            ),
        )
        self.assertEqual(delete.status_code, status.HTTP_404_NOT_FOUND)

    def test_group_books_post_missing_book_returns_error_envelope(self):
        self.client.login(username="librarian", password="pw")
        response = assert_response(
            self.client.post(
                f"/api/v1/library/groups/{self.group.id}/books/", data={}, format="json"
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIsNotNone(response.data)
        payload = response_data_dict(response)
        self.assertIn("error", payload)
        self.assertEqual(
            payload_dict(payload, "error")["code"], ErrorCode.INVALID_REQUEST
        )

    def test_curator_can_add_visible_book_to_their_non_public_group(self):
        self.client.login(username="curator", password="pw")
        response = assert_response(
            self.client.post(
                f"/api/v1/library/groups/{self.group.id}/books/",
                data={"book": str(self.book_public.id)},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = response_data_dict(response)
        added_by = payload_dict(payload, "added_by")
        self.assertEqual(str(added_by["profile_id"]), str(self.curator.profile.id))
        self.assertEqual(added_by["username"], "curator")
        self.assertNotIsInstance(payload["added_by"], int)

    def test_curator_cannot_add_inaccessible_book_to_their_group(self):
        self.client.login(username="curator", password="pw")
        response = assert_response(
            self.client.post(
                f"/api/v1/library/groups/{self.group.id}/books/",
                data={"book": str(self.book_inaccessible.id)},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_curator_cannot_curate_public(self):
        self.client.login(username="curator", password="pw")
        response = assert_response(
            self.client.post(
                f"/api/v1/library/groups/{self.public.id}/books/",
                data={"book": str(self.book_public.id)},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
