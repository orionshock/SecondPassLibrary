from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from library.group_services import ensure_book_public_assignment, ensure_user_public_membership, get_public_group
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership


User = get_user_model()


class LibraryGroupVisibilityAPITest(APITestCase):
    def setUp(self):
        self.public = get_public_group()

        self.reader = User.objects.create_user(username="reader", email="reader@example.com", password="pw")
        ensure_user_public_membership(user=self.reader)
        reader_profile, _ = UserProfile.objects.get_or_create(user=self.reader)
        reader_profile.role = UserProfile.ROLE_READER
        reader_profile.save(update_fields=["role", "updated_at"])

        self.manager = User.objects.create_user(username="manager", email="manager@example.com", password="pw")
        ensure_user_public_membership(user=self.manager)
        manager_profile, _ = UserProfile.objects.get_or_create(user=self.manager)
        manager_profile.role = UserProfile.ROLE_MANAGER
        manager_profile.save(update_fields=["role", "updated_at"])

        self.listed = LibraryGroup.objects.create(name="Listed", slug="listed", discoverability=LibraryGroup.DISCOVERABILITY_LISTED)
        self.unlisted = LibraryGroup.objects.create(
            name="Unlisted",
            slug="unlisted",
            discoverability=LibraryGroup.DISCOVERABILITY_UNLISTED,
        )
        self.unlisted_member = LibraryGroup.objects.create(
            name="UnlistedMember",
            slug="unlisted-member",
            discoverability=LibraryGroup.DISCOVERABILITY_UNLISTED,
        )
        LibraryGroupMembership.objects.create(
            user=self.reader,
            group=self.unlisted_member,
            role=LibraryGroupMembership.ROLE_READER,
        )

    def test_reader_sees_public_and_listed_and_member_unlisted(self):
        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.get("/api/v1/library/groups/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = cast(list[dict[str, Any]], response.data)
        slugs = {g["slug"] for g in data}
        self.assertIn("public", slugs)
        self.assertIn("listed", slugs)
        self.assertIn("unlisted-member", slugs)
        self.assertNotIn("unlisted", slugs)

        public = next(g for g in data if g["slug"] == "public")
        self.assertTrue(public["is_public_group"])

    def test_reader_cannot_view_unlisted_group_they_are_not_member_of(self):
        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.get(f"/api/v1/library/groups/{self.unlisted.id}/"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_manager_sees_all_groups(self):
        self.client.login(username="manager", password="pw")
        response = cast(Response, self.client.get("/api/v1/library/groups/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = cast(list[dict[str, Any]], response.data)
        slugs = {g["slug"] for g in data}
        self.assertTrue({"public", "listed", "unlisted", "unlisted-member"}.issubset(slugs))


class LibraryGroupBooksAndCurationAPITest(APITestCase):
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

        self.group = LibraryGroup.objects.create(name="Group", slug="group", discoverability=LibraryGroup.DISCOVERABILITY_UNLISTED)
        LibraryGroupMembership.objects.create(user=self.curator, group=self.group, role=LibraryGroupMembership.ROLE_CURATOR)
        LibraryGroupMembership.objects.create(user=self.reader, group=self.group, role=LibraryGroupMembership.ROLE_READER)

        self.listed_group = LibraryGroup.objects.create(
            name="Listed",
            slug="listed",
            discoverability=LibraryGroup.DISCOVERABILITY_LISTED,
        )

        self.book_public = Book.objects.create(title="Public Book")
        ensure_book_public_assignment(book=self.book_public, added_by=None)

        self.book_only_group = Book.objects.create(title="Only Group")
        BookGroupAssignment.objects.create(book=self.book_only_group, group=self.group, added_by=self.librarian)

        self.book_inaccessible = Book.objects.create(title="Inaccessible")
        hidden = LibraryGroup.objects.create(name="Hidden", slug="hidden", discoverability=LibraryGroup.DISCOVERABILITY_UNLISTED)
        other = User.objects.create_user(username="other", email="other@example.com", password="pw")
        ensure_user_public_membership(user=other)
        LibraryGroupMembership.objects.create(user=other, group=hidden, role=LibraryGroupMembership.ROLE_READER)
        BookGroupAssignment.objects.create(book=self.book_inaccessible, group=hidden, added_by=self.librarian)

        # Assign both books to a listed group the reader can see but does not necessarily have access to.
        BookGroupAssignment.objects.create(book=self.book_public, group=self.listed_group, added_by=self.librarian)
        BookGroupAssignment.objects.create(book=self.book_inaccessible, group=self.listed_group, added_by=self.librarian)

    def test_reader_group_books_filters_inaccessible_books(self):
        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.get(f"/api/v1/library/groups/{self.listed_group.id}/books/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = {b["title"] for b in cast(list[dict[str, Any]], response.data)}
        self.assertIn("Public Book", titles)
        self.assertNotIn("Inaccessible", titles)

    def test_librarian_group_books_sees_all_books_in_group(self):
        self.client.login(username="librarian", password="pw")
        response = cast(Response, self.client.get(f"/api/v1/library/groups/{self.listed_group.id}/books/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = {b["title"] for b in cast(list[dict[str, Any]], response.data)}
        self.assertIn("Public Book", titles)
        self.assertIn("Inaccessible", titles)

    def test_reader_cannot_add_or_remove_books(self):
        self.client.login(username="reader", password="pw")
        add = cast(Response, self.client.post(f"/api/v1/library/groups/{self.group.id}/books/", data={"book": str(self.book_public.id)}, format="json"))
        self.assertEqual(add.status_code, status.HTTP_403_FORBIDDEN)

        delete = cast(Response, self.client.delete(f"/api/v1/library/groups/{self.group.id}/books/{self.book_only_group.id}/"))
        self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_curator_can_add_visible_book_to_their_non_public_group(self):
        self.client.login(username="curator", password="pw")
        response = cast(Response, self.client.post(f"/api/v1/library/groups/{self.group.id}/books/", data={"book": str(self.book_public.id)}, format="json"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_curator_cannot_add_inaccessible_book(self):
        self.client.login(username="curator", password="pw")
        response = cast(Response, self.client.post(f"/api/v1/library/groups/{self.group.id}/books/", data={"book": str(self.book_inaccessible.id)}, format="json"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_curator_cannot_add_or_remove_books_in_public(self):
        self.client.login(username="curator", password="pw")
        add = cast(Response, self.client.post(f"/api/v1/library/groups/{self.public.id}/books/", data={"book": str(self.book_public.id)}, format="json"))
        self.assertEqual(add.status_code, status.HTTP_403_FORBIDDEN)

        delete = cast(Response, self.client.delete(f"/api/v1/library/groups/{self.public.id}/books/{self.book_public.id}/"))
        self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_curator_can_remove_book_from_their_group(self):
        self.client.login(username="curator", password="pw")
        response = cast(Response, self.client.delete(f"/api/v1/library/groups/{self.group.id}/books/{self.book_only_group.id}/"))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_librarian_can_add_and_remove_broadly_and_last_removal_falls_back_to_public(self):
        book = Book.objects.create(title="Temp")
        BookGroupAssignment.objects.create(book=book, group=self.group, added_by=self.librarian)

        self.client.login(username="librarian", password="pw")
        removed = cast(Response, self.client.delete(f"/api/v1/library/groups/{self.group.id}/books/{book.id}/"))
        self.assertEqual(removed.status_code, status.HTTP_204_NO_CONTENT)

        slugs = set(BookGroupAssignment.objects.filter(book=book).values_list("group__slug", flat=True))
        self.assertEqual(slugs, {"public"})


class LibraryGroupPresentationPatchAPITest(APITestCase):
    def setUp(self):
        self.public = get_public_group()

        self.manager = User.objects.create_user(username="manager", email="manager@example.com", password="pw")
        ensure_user_public_membership(user=self.manager)
        manager_profile, _ = UserProfile.objects.get_or_create(user=self.manager)
        manager_profile.role = UserProfile.ROLE_MANAGER
        manager_profile.save(update_fields=["role", "updated_at"])

        self.librarian = User.objects.create_user(username="librarian", email="librarian@example.com", password="pw")
        ensure_user_public_membership(user=self.librarian)
        librarian_profile, _ = UserProfile.objects.get_or_create(user=self.librarian)
        librarian_profile.role = UserProfile.ROLE_LIBRARIAN
        librarian_profile.save(update_fields=["role", "updated_at"])

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

        self.group = LibraryGroup.objects.create(
            name="Group",
            slug="group",
            discoverability=LibraryGroup.DISCOVERABILITY_UNLISTED,
            description="before",
        )
        self.other_group = LibraryGroup.objects.create(
            name="Other",
            slug="other",
            discoverability=LibraryGroup.DISCOVERABILITY_UNLISTED,
        )
        LibraryGroupMembership.objects.create(
            user=self.curator, group=self.group, role=LibraryGroupMembership.ROLE_CURATOR
        )

        self.book_in_group = Book.objects.create(title="InGroup")
        BookGroupAssignment.objects.create(book=self.book_in_group, group=self.group, added_by=self.librarian)

    def test_librarian_can_patch_public_description(self):
        self.client.login(username="librarian", password="pw")
        response = cast(Response, self.client.patch(f"/api/v1/library/groups/{self.public.id}/", data={"description": "x"}, format="json"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.public.refresh_from_db()
        self.assertEqual(self.public.description, "x")

    def test_librarian_cannot_patch_public_discoverability(self):
        self.client.login(username="librarian", password="pw")
        response = cast(Response, self.client.patch(f"/api/v1/library/groups/{self.public.id}/", data={"discoverability": LibraryGroup.DISCOVERABILITY_UNLISTED}, format="json"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.public.refresh_from_db()
        self.assertEqual(self.public.discoverability, LibraryGroup.DISCOVERABILITY_LISTED)

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

    def test_librarian_can_patch_non_public_description_and_discoverability(self):
        self.client.login(username="librarian", password="pw")
        response = cast(Response, self.client.patch(f"/api/v1/library/groups/{self.group.id}/", data={"description": "after", "discoverability": LibraryGroup.DISCOVERABILITY_LISTED}, format="json"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.group.refresh_from_db()
        self.assertEqual(self.group.description, "after")
        self.assertEqual(self.group.discoverability, LibraryGroup.DISCOVERABILITY_LISTED)

    def test_curator_can_patch_description_and_discoverability_for_their_group_only(self):
        self.client.login(username="curator", password="pw")
        ok = cast(Response, self.client.patch(f"/api/v1/library/groups/{self.group.id}/", data={"description": "c", "discoverability": LibraryGroup.DISCOVERABILITY_LISTED}, format="json"))
        self.assertEqual(ok.status_code, status.HTTP_200_OK)

        denied = cast(Response, self.client.patch(f"/api/v1/library/groups/{self.other_group.id}/", data={"description": "c"}, format="json"))
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)

    def test_attempts_to_patch_name_or_slug_are_rejected(self):
        self.client.login(username="manager", password="pw")
        response = cast(Response, self.client.patch(f"/api/v1/library/groups/{self.group.id}/", data={"name": "NEW"}, format="json"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.group.refresh_from_db()
        self.assertEqual(self.group.name, "Group")

        response2 = cast(Response, self.client.patch(f"/api/v1/library/groups/{self.group.id}/", data={"slug": "new-slug"}, format="json"))
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        self.group.refresh_from_db()
        self.assertEqual(self.group.slug, "group")

    def test_discoverability_update_does_not_grant_book_access(self):
        book = Book.objects.create(title="HiddenBook")
        hidden_group = LibraryGroup.objects.create(name="Hidden", slug="hidden", discoverability=LibraryGroup.DISCOVERABILITY_UNLISTED)
        other = User.objects.create_user(username="other", email="other@example.com", password="pw")
        ensure_user_public_membership(user=other)
        LibraryGroupMembership.objects.create(user=other, group=hidden_group, role=LibraryGroupMembership.ROLE_READER)
        BookGroupAssignment.objects.create(book=book, group=hidden_group, added_by=self.librarian)

        # Make the hidden group listed (so it's visible) but do not grant membership to reader.
        self.client.login(username="librarian", password="pw")
        patched = cast(Response, self.client.patch(f"/api/v1/library/groups/{hidden_group.id}/", data={"discoverability": LibraryGroup.DISCOVERABILITY_LISTED}, format="json"))
        self.assertEqual(patched.status_code, status.HTTP_200_OK)

        # Reader can now see the group (listed), but still cannot see the book in the group's books listing.
        self.client.logout()
        self.client.login(username="reader", password="pw")
        listing = cast(Response, self.client.get("/api/v1/library/groups/"))
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        slugs = {g["slug"] for g in cast(list[dict[str, Any]], listing.data)}
        self.assertIn("hidden", slugs)

        books = cast(Response, self.client.get(f"/api/v1/library/groups/{hidden_group.id}/books/"))
        self.assertEqual(books.status_code, status.HTTP_200_OK)
        titles = {b["title"] for b in cast(list[dict[str, Any]], books.data)}
        self.assertNotIn("HiddenBook", titles)
