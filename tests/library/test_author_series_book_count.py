from __future__ import annotations

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.client_api import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession, UserProfile
from accounts.services import get_or_create_profile
from library.groups.services import (
    add_book_to_group,
    ensure_book_public_assignment,
    ensure_user_public_membership,
)
from library.models import Author, LibraryGroup, LibraryGroupMembership, Series
from library.groups.public_group import get_public_group
from tests.utils.books import create_file_backed_book
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.responses import (
    assert_response,
    response_data_dict,
    response_data_list,
)


class _AuthorSeriesBookCountBase(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.public = get_public_group()
        self.owner = User.objects.create_superuser(
            username="owner", password="pw", email="o@example.com"
        )
        ensure_user_public_membership(user=self.owner)

        self.manager = User.objects.create_user(
            username="manager", password="pw", email="m@example.com"
        )
        ensure_user_public_membership(user=self.manager)
        profile = get_or_create_profile(user=self.manager)
        profile.role = UserProfile.ROLE_MANAGER
        profile.save(update_fields=["role", "updated_at"])

        self.reader = User.objects.create_user(
            username="reader", password="pw", email="r@example.com"
        )
        ensure_user_public_membership(user=self.reader)

        self.hidden_group = LibraryGroup.objects.create(name="Hidden")
        other = User.objects.create_user(
            username="other", password="pw", email="other@example.com"
        )
        ensure_user_public_membership(user=other)
        # Only "other" can see hidden books.
        LibraryGroupMembership.objects.create(
            user=other,
            group=self.hidden_group,
        )

        self.author = Author.objects.create(name="Author A")
        self.series = Series.objects.create(name="Series S")

        self.book_public = create_file_backed_book(
            title="Public Book",
            assign_public=False,
            book_fields={"series": self.series},
        ).book
        self.book_public.authors.add(self.author)
        ensure_book_public_assignment(book=self.book_public, added_by=None)

        self.book_hidden = create_file_backed_book(
            title="Hidden Book",
            assign_public=False,
            book_fields={"series": self.series},
        ).book
        self.book_hidden.authors.add(self.author)
        add_book_to_group(
            actor=self.owner, book=self.book_hidden, group=self.hidden_group
        )


class AuthorSeriesBookCountSessionAuthTests(_AuthorSeriesBookCountBase):
    def test_reader_author_list_includes_visibility_scoped_book_count(self):
        self.client.login(username="reader", password="pw")
        resp = assert_response(self.client.get("/api/v1/library/authors/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = response_data_list(resp)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], str(self.author.id))
        self.assertEqual(results[0]["book_count"], 1)

    def test_manager_author_list_includes_all_visible_books_in_count(self):
        self.client.login(username="manager", password="pw")
        resp = assert_response(self.client.get("/api/v1/library/authors/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = response_data_list(resp)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["book_count"], 2)

    def test_author_list_ordering_by_name_and_book_count(self):
        other_author = Author.objects.create(name="Zed Author")
        other_book = create_file_backed_book(
            title="Other Public",
            assign_public=False,
        ).book
        other_book.authors.add(other_author)
        ensure_book_public_assignment(book=other_book, added_by=None)

        self.client.login(username="manager", password="pw")
        by_name = assert_response(
            self.client.get("/api/v1/library/authors/?ordering=name")
        )
        self.assertEqual(by_name.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row["name"] for row in response_data_list(by_name)],
            ["Author A", "Zed Author"],
        )

        by_count = assert_response(
            self.client.get("/api/v1/library/authors/?ordering=-book_count")
        )
        self.assertEqual(by_count.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [(row["name"], row["book_count"]) for row in response_data_list(by_count)],
            [("Author A", 2), ("Zed Author", 1)],
        )

    def test_author_list_invalid_ordering_returns_400(self):
        self.client.login(username="reader", password="pw")
        resp = assert_response(
            self.client.get("/api/v1/library/authors/?ordering=created_at")
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ordering", response_data_dict(resp))

    def test_reader_series_detail_includes_visibility_scoped_book_count(self):
        self.client.login(username="reader", password="pw")
        resp = assert_response(
            self.client.get(f"/api/v1/library/series/{self.series.id}/")
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = response_data_dict(resp)
        self.assertEqual(payload["id"], str(self.series.id))
        self.assertEqual(payload["book_count"], 1)

    def test_series_list_ordering_by_name_and_book_count(self):
        other_series = Series.objects.create(name="Zed Series")
        other_book = create_file_backed_book(
            title="Other Public",
            assign_public=False,
            book_fields={"series": other_series},
        ).book
        ensure_book_public_assignment(book=other_book, added_by=None)

        self.client.login(username="manager", password="pw")
        by_name = assert_response(
            self.client.get("/api/v1/library/series/?ordering=name")
        )
        self.assertEqual(by_name.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row["name"] for row in response_data_list(by_name)],
            ["Series S", "Zed Series"],
        )

        by_count = assert_response(
            self.client.get("/api/v1/library/series/?ordering=-book_count")
        )
        self.assertEqual(by_count.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [(row["name"], row["book_count"]) for row in response_data_list(by_count)],
            [("Series S", 2), ("Zed Series", 1)],
        )

    def test_series_list_invalid_ordering_returns_400(self):
        self.client.login(username="reader", password="pw")
        resp = assert_response(
            self.client.get("/api/v1/library/series/?ordering=updated_at")
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ordering", response_data_dict(resp))


class AuthorSeriesBookCountClientBearerTests(_AuthorSeriesBookCountBase):
    def setUp(self):
        super().setUp()
        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.reader,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
            last_seen_at=None,
            expires_at=None,
            revoked_at=None,
        )
        self._auth = f"Bearer {token}"

    def test_bearer_author_list_book_count_is_visibility_scoped(self):
        resp = assert_response(
            self.client.get("/api/v1/library/authors/", HTTP_AUTHORIZATION=self._auth)
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = response_data_list(resp)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["book_count"], 1)
