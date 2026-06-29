from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from library.group_services import (
    add_book_to_group,
    ensure_book_public_assignment,
    ensure_user_public_membership,
    get_public_group,
)
from library.models import BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from tests.utils.books import create_file_backed_book

User = get_user_model()


class LibraryGroupPreviewBooksAPITest(APITestCase):
    def setUp(self):
        self.public = get_public_group()

        self.reader = User.objects.create_user(username="reader", password="pw")
        ensure_user_public_membership(user=self.reader)
        profile, _ = UserProfile.objects.get_or_create(user=self.reader)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])

        self.manager = User.objects.create_user(username="manager", password="pw")
        ensure_user_public_membership(user=self.manager)
        profile, _ = UserProfile.objects.get_or_create(user=self.manager)
        profile.role = UserProfile.ROLE_MANAGER
        profile.save(update_fields=["role", "updated_at"])

        self.group = LibraryGroup.objects.create(name="Preview Group")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.group)

        self.other_group = LibraryGroup.objects.create(name="Other")
        self.hidden_group = LibraryGroup.objects.create(name="Hidden")

        self.other_visible_book = create_file_backed_book(title="Other Visible", assign_public=False).book
        ensure_book_public_assignment(book=self.other_visible_book, added_by=None)
        add_book_to_group(actor=self.manager, book=self.other_visible_book, group=self.other_group)

        self.hidden_book = create_file_backed_book(title="Hidden Book", assign_public=False).book
        add_book_to_group(actor=self.manager, book=self.hidden_book, group=self.hidden_group)

        self.group_books = []
        for index in range(7):
            book = create_file_backed_book(title=f"Group {index:02d}", assign_public=False).book
            self.group_books.append(book)
            BookGroupAssignment.objects.create(
                book=book,
                group=self.group,
                added_by=self.manager,
            )

        self.public_book = create_file_backed_book(title="Public Preview", assign_public=False).book
        ensure_book_public_assignment(book=self.public_book, added_by=None)

    def _results(self, response: Response) -> list[dict[str, Any]]:
        payload = cast(Mapping[str, Any], response.data)
        return cast(list[dict[str, Any]], payload["results"])

    def test_group_list_and_detail_preview_books_are_opt_in(self):
        self.client.login(username="reader", password="pw")

        list_default = cast(Response, self.client.get("/api/v1/library/groups/"))
        self.assertEqual(list_default.status_code, status.HTTP_200_OK)
        default_row = next(row for row in self._results(list_default) if row["id"] == str(self.group.id))
        self.assertNotIn("preview_books", default_row)

        detail_default = cast(
            Response,
            self.client.get(f"/api/v1/library/groups/{self.group.id}/"),
        )
        self.assertEqual(detail_default.status_code, status.HTTP_200_OK)
        self.assertNotIn("preview_books", cast(Mapping[str, Any], detail_default.data))

        list_preview = cast(
            Response,
            self.client.get("/api/v1/library/groups/?include_preview_books=true"),
        )
        self.assertEqual(list_preview.status_code, status.HTTP_200_OK)
        preview_row = next(row for row in self._results(list_preview) if row["id"] == str(self.group.id))
        self.assertIn("preview_books", preview_row)

        detail_preview = cast(
            Response,
            self.client.get(f"/api/v1/library/groups/{self.group.id}/?include_preview_books=true"),
        )
        self.assertEqual(detail_preview.status_code, status.HTTP_200_OK)
        self.assertIn("preview_books", cast(Mapping[str, Any], detail_preview.data))

    def test_group_preview_books_shape_cap_exact_assignments_and_visibility(self):
        self.client.login(username="reader", password="pw")
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/groups/{self.group.id}/?include_preview_books=true"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        previews = cast(list[dict[str, Any]], cast(Mapping[str, Any], response.data)["preview_books"])

        self.assertEqual(len(previews), 6)
        titles = [row["title"] for row in previews]
        self.assertLessEqual(set(titles), {book.title for book in self.group_books})
        self.assertNotIn("Other Visible", set(titles))
        self.assertNotIn("Hidden Book", set(titles))
        for row in previews:
            self.assertEqual(set(row.keys()), {"id", "title", "cover_url"})
            self.assertIsNone(row["cover_url"])
            self.assertNotIn("download_url", row)

    def test_public_group_preview_does_not_leak_hidden_books(self):
        self.client.login(username="reader", password="pw")
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/groups/{self.public.id}/?include_preview_books=true"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        previews = cast(list[dict[str, Any]], cast(Mapping[str, Any], response.data)["preview_books"])
        titles = {row["title"] for row in previews}
        self.assertIn("Public Preview", titles)
        self.assertNotIn("Hidden Book", titles)

    def test_broad_role_group_preview_includes_assigned_books(self):
        self.client.login(username="manager", password="pw")
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/groups/{self.hidden_group.id}/?include_preview_books=true"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        previews = cast(list[dict[str, Any]], cast(Mapping[str, Any], response.data)["preview_books"])
        self.assertEqual([row["title"] for row in previews], ["Hidden Book"])
