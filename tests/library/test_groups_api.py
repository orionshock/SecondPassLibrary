from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from library.group_services import (
    ensure_book_public_assignment,
    ensure_user_public_membership,
    get_public_group,
)
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from core.errors import ErrorCode


User = get_user_model()


class LibraryGroupVisibilityAPITest(APITestCase):
    def setUp(self):
        self.public = get_public_group()

        self.reader = User.objects.create_user(
            username="reader", email="reader@example.com", password="pw"
        )
        ensure_user_public_membership(user=self.reader)
        reader_profile, _ = UserProfile.objects.get_or_create(user=self.reader)
        reader_profile.role = UserProfile.ROLE_READER
        reader_profile.save(update_fields=["role", "updated_at"])

        self.manager = User.objects.create_user(
            username="manager", email="manager@example.com", password="pw"
        )
        ensure_user_public_membership(user=self.manager)
        manager_profile, _ = UserProfile.objects.get_or_create(user=self.manager)
        manager_profile.role = UserProfile.ROLE_MANAGER
        manager_profile.save(update_fields=["role", "updated_at"])

        self.member_group = LibraryGroup.objects.create(name="MemberGroup", slug="member-group")
        self.other_group = LibraryGroup.objects.create(name="OtherGroup", slug="other-group")
        LibraryGroupMembership.objects.create(
            user=self.reader,
            group=self.member_group,
            role=LibraryGroupMembership.ROLE_READER,
        )

    def test_reader_sees_public_and_member_groups_only(self):
        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.get("/api/v1/library/groups/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        payload = cast(Mapping[str, Any], response.data)
        data = cast(list[dict[str, Any]], payload["results"])
        slugs = {g["slug"] for g in data}
        self.assertIn("public", slugs)
        self.assertIn("member-group", slugs)
        self.assertNotIn("other-group", slugs)

        public = next(g for g in data if g["slug"] == "public")
        self.assertTrue(public["is_public_group"])

    def test_reader_cannot_view_non_member_non_public_group(self):
        self.client.login(username="reader", password="pw")
        response = cast(
            Response, self.client.get(f"/api/v1/library/groups/{self.other_group.id}/")
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_manager_sees_all_groups(self):
        self.client.login(username="manager", password="pw")
        response = cast(Response, self.client.get("/api/v1/library/groups/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        payload = cast(Mapping[str, Any], response.data)
        data = cast(list[dict[str, Any]], payload["results"])
        slugs = {g["slug"] for g in data}
        self.assertTrue({"public", "member-group", "other-group"}.issubset(slugs))


class LibraryGroupBooksAndCurationAPITest(APITestCase):
    def setUp(self):
        self.public = get_public_group()

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

        self.group = LibraryGroup.objects.create(name="Group", slug="group")
        LibraryGroupMembership.objects.create(
            user=self.curator, group=self.group, role=LibraryGroupMembership.ROLE_CURATOR
        )

        self.other_group = LibraryGroup.objects.create(name="Other", slug="other")

        self.visible_group = LibraryGroup.objects.create(name="VisibleGroup", slug="visible-group")
        LibraryGroupMembership.objects.create(
            user=self.reader, group=self.visible_group, role=LibraryGroupMembership.ROLE_READER
        )

        self.book_public = Book.objects.create(title="Public Book")
        ensure_book_public_assignment(book=self.book_public, added_by=None)

        self.book_only_group = Book.objects.create(title="OnlyGroup")
        BookGroupAssignment.objects.create(
            book=self.book_only_group, group=self.group, added_by=self.librarian
        )

        self.book_inaccessible = Book.objects.create(title="Inaccessible")
        hidden = LibraryGroup.objects.create(name="Hidden", slug="hidden")
        other = User.objects.create_user(username="other", email="other@example.com", password="pw")
        ensure_user_public_membership(user=other)
        LibraryGroupMembership.objects.create(
            user=other, group=hidden, role=LibraryGroupMembership.ROLE_READER
        )
        BookGroupAssignment.objects.create(book=self.book_inaccessible, group=hidden, added_by=self.librarian)

        BookGroupAssignment.objects.create(book=self.book_public, group=self.visible_group, added_by=self.librarian)
        BookGroupAssignment.objects.create(book=self.book_inaccessible, group=self.visible_group, added_by=self.librarian)

    def test_reader_group_books_shows_books_in_groups_they_belong_to(self):
        self.client.login(username="reader", password="pw")
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/groups/{self.visible_group.id}/books/"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        payload = cast(Mapping[str, Any], response.data)
        self.assertIn("count", payload)
        self.assertIn("results", payload)
        titles = {b["title"] for b in cast(list[dict[str, Any]], payload["results"])}
        self.assertIn("Public Book", titles)
        self.assertIn("Inaccessible", titles)

    def test_librarian_group_books_sees_all_books_in_group(self):
        self.client.login(username="librarian", password="pw")
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/groups/{self.visible_group.id}/books/"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        payload = cast(Mapping[str, Any], response.data)
        titles = {b["title"] for b in cast(list[dict[str, Any]], payload["results"])}
        self.assertIn("Public Book", titles)
        self.assertIn("Inaccessible", titles)

    def test_reader_cannot_add_or_remove_books(self):
        self.client.login(username="reader", password="pw")
        add = cast(
            Response,
            self.client.post(
                f"/api/v1/library/groups/{self.group.id}/books/",
                data={"book": str(self.book_public.id)},
                format="json",
            ),
        )
        self.assertEqual(add.status_code, status.HTTP_404_NOT_FOUND)

        delete = cast(
            Response,
            self.client.delete(
                f"/api/v1/library/groups/{self.group.id}/books/{self.book_only_group.id}/"
            ),
        )
        self.assertEqual(delete.status_code, status.HTTP_404_NOT_FOUND)

    def test_group_books_post_missing_book_returns_error_envelope(self):
        self.client.login(username="librarian", password="pw")
        response = cast(
            Response,
            self.client.post(f"/api/v1/library/groups/{self.group.id}/books/", data={}, format="json"),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIsNotNone(response.data)
        payload = cast(dict[str, Any], response.data)
        self.assertIn("error", payload)
        self.assertEqual(cast(dict[str, Any], payload["error"])["code"], ErrorCode.INVALID_REQUEST)

    def test_curator_can_add_visible_book_to_their_non_public_group(self):
        self.client.login(username="curator", password="pw")
        response = cast(
            Response,
            self.client.post(
                f"/api/v1/library/groups/{self.group.id}/books/",
                data={"book": str(self.book_public.id)},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_curator_cannot_add_inaccessible_book_to_their_group(self):
        self.client.login(username="curator", password="pw")
        response = cast(
            Response,
            self.client.post(
                f"/api/v1/library/groups/{self.group.id}/books/",
                data={"book": str(self.book_inaccessible.id)},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_curator_cannot_curate_public(self):
        self.client.login(username="curator", password="pw")
        response = cast(
            Response,
            self.client.post(
                f"/api/v1/library/groups/{self.public.id}/books/",
                data={"book": str(self.book_public.id)},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class LibraryGroupPresentationPatchAPITest(APITestCase):
    def setUp(self):
        self.public = get_public_group()

        self.reader = User.objects.create_user(username="reader", email="reader@example.com", password="pw")
        ensure_user_public_membership(user=self.reader)
        reader_profile, _ = UserProfile.objects.get_or_create(user=self.reader)
        reader_profile.role = UserProfile.ROLE_READER
        reader_profile.save(update_fields=["role", "updated_at"])

        self.curator = User.objects.create_user(username="curator", email="curator@example.com", password="pw")
        ensure_user_public_membership(user=self.curator)
        curator_profile, _ = UserProfile.objects.get_or_create(user=self.curator)
        curator_profile.role = UserProfile.ROLE_READER
        curator_profile.save(update_fields=["role", "updated_at"])

        self.librarian = User.objects.create_user(username="librarian", email="librarian@example.com", password="pw")
        ensure_user_public_membership(user=self.librarian)
        librarian_profile, _ = UserProfile.objects.get_or_create(user=self.librarian)
        librarian_profile.role = UserProfile.ROLE_LIBRARIAN
        librarian_profile.save(update_fields=["role", "updated_at"])

        self.manager = User.objects.create_user(username="manager", email="manager@example.com", password="pw")
        ensure_user_public_membership(user=self.manager)
        manager_profile, _ = UserProfile.objects.get_or_create(user=self.manager)
        manager_profile.role = UserProfile.ROLE_MANAGER
        manager_profile.save(update_fields=["role", "updated_at"])

        self.group = LibraryGroup.objects.create(name="Group", slug="group", description="before")
        LibraryGroupMembership.objects.create(user=self.curator, group=self.group, role=LibraryGroupMembership.ROLE_CURATOR)

        self.other_group = LibraryGroup.objects.create(name="Other", slug="other", description="before")

    def test_reader_cannot_patch_group(self):
        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.patch(f"/api/v1/library/groups/{self.group.id}/", data={"description": "after"}, format="json"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_manager_can_patch_public_description(self):
        self.client.login(username="manager", password="pw")
        response = cast(Response, self.client.patch(f"/api/v1/library/groups/{self.public.id}/", data={"description": "m"}, format="json"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_reader_cannot_patch_public_description(self):
        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.patch(f"/api/v1/library/groups/{self.public.id}/", data={"description": "no"}, format="json"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_curator_cannot_patch_public_description(self):
        self.client.login(username="curator", password="pw")
        response = cast(Response, self.client.patch(f"/api/v1/library/groups/{self.public.id}/", data={"description": "no"}, format="json"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_librarian_can_patch_non_public_description(self):
        self.client.login(username="librarian", password="pw")
        response = cast(Response, self.client.patch(f"/api/v1/library/groups/{self.group.id}/", data={"description": "after"}, format="json"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.group.refresh_from_db()
        self.assertEqual(self.group.description, "after")

    def test_curator_can_patch_description_for_their_group_only(self):
        self.client.login(username="curator", password="pw")
        ok = cast(Response, self.client.patch(f"/api/v1/library/groups/{self.group.id}/", data={"description": "c"}, format="json"))
        self.assertEqual(ok.status_code, status.HTTP_200_OK)

        denied = cast(Response, self.client.patch(f"/api/v1/library/groups/{self.other_group.id}/", data={"description": "c"}, format="json"))
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)

    def test_attempts_to_patch_name_or_slug_are_rejected(self):
        self.client.login(username="manager", password="pw")
        response = cast(Response, self.client.patch(f"/api/v1/library/groups/{self.group.id}/", data={"name": "NEW"}, format="json"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIsNotNone(response.data)
        payload = cast(dict[str, Any], response.data)
        self.assertIn("error", payload)
        self.assertEqual(cast(dict[str, Any], payload["error"])["code"], ErrorCode.GROUP_IDENTITY_IMMUTABLE)
        self.group.refresh_from_db()
        self.assertEqual(self.group.name, "Group")

        response2 = cast(Response, self.client.patch(f"/api/v1/library/groups/{self.group.id}/", data={"slug": "new-slug"}, format="json"))
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIsNotNone(response2.data)
        payload2 = cast(dict[str, Any], response2.data)
        self.assertIn("error", payload2)
        self.assertEqual(cast(dict[str, Any], payload2["error"])["code"], ErrorCode.GROUP_IDENTITY_IMMUTABLE)
        self.group.refresh_from_db()
        self.assertEqual(self.group.slug, "group")

    def test_discoverability_patch_is_rejected(self):
        self.client.login(username="librarian", password="pw")
        response = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/groups/{self.group.id}/",
                data={"discoverability": "listed"},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIsNotNone(response.data)
        payload = cast(dict[str, Any], response.data)
        self.assertEqual(cast(dict[str, Any], payload["error"])["code"], ErrorCode.UNSAFE_FIELD)
