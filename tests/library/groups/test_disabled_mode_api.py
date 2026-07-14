from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession, UserProfile
from core.server_settings import (
    set_advanced_library_groups_enabled,
    set_server_setting,
)
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING
from library.models import (
    Book,
    BookCatalogTag,
    BookGroupAssignment,
    CatalogTag,
    LibraryGroup,
    LibraryGroupMembership,
)
from tests.library.helpers import set_user_role


class AdvancedLibraryGroupsApiModeTests(TestCase):
    def setUp(self):
        cache.clear()
        set_advanced_library_groups_enabled(False)
        User = get_user_model()
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.librarian = User.objects.create_user(username="librarian", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        self.target = User.objects.create_user(username="target", password="pw")
        self.candidate = User.objects.create_user(username="candidate", password="pw")
        set_user_role(self.reader, UserProfile.ROLE_READER)
        set_user_role(self.librarian, UserProfile.ROLE_LIBRARIAN)
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)
        set_user_role(self.target, UserProfile.ROLE_READER)
        set_user_role(self.candidate, UserProfile.ROLE_READER)

        self.public = LibraryGroup.objects.create(
            name="Common Room", description="Simple mode"
        )
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(self.public.id),
            description="Public/Common Room group id.",
        )
        self.custom = LibraryGroup.objects.create(name="Club", description="Hidden")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.public)
        LibraryGroupMembership.objects.create(user=self.target, group=self.custom)
        LibraryGroupMembership.objects.create(user=self.candidate, group=self.public)

        self.public_book = Book.objects.create(title="Public Book")
        self.custom_book = Book.objects.create(title="Custom Book")
        self.candidate_book = Book.objects.create(title="Candidate Book")
        BookGroupAssignment.objects.create(book=self.public_book, group=self.public)
        BookGroupAssignment.objects.create(book=self.public_book, group=self.custom)
        BookGroupAssignment.objects.create(book=self.custom_book, group=self.custom)
        BookGroupAssignment.objects.create(book=self.candidate_book, group=self.public)

    def _json(self, data):
        return json.dumps(data)

    def test_disabled_mode_hides_custom_group_api_surfaces_without_rewriting_data(self):
        self.client.login(username="manager", password="pw")
        group_url = f"/api/v1/library/groups/{self.custom.id}/"
        books_url = f"{group_url}books/"
        memberships_url = f"{group_url}memberships/"

        list_response = self.client.get(
            "/api/v1/library/groups/?include_preview_books=true"
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            [row["id"] for row in list_response.json()["results"]],
            [str(self.public.id)],
        )
        self.assertIn("preview_books", list_response.json()["results"][0])

        blocked_requests = [
            self.client.get(group_url),
            self.client.get(f"{group_url}?include_preview_books=true"),
            self.client.patch(
                group_url,
                self._json({"description": "No"}),
                content_type="application/json",
            ),
            self.client.delete(group_url),
            self.client.get(books_url),
            self.client.post(
                books_url,
                self._json({"book_id": str(self.candidate_book.id)}),
                content_type="application/json",
            ),
            self.client.delete(f"{books_url}{self.custom_book.id}/"),
            self.client.get(memberships_url),
            self.client.post(
                memberships_url,
                self._json({"user_id": str(self.candidate.profile.id)}),
                content_type="application/json",
            ),
            self.client.patch(
                f"{memberships_url}{self.target.profile.id}/",
                self._json({"is_curator": True}),
                content_type="application/json",
            ),
            self.client.delete(f"{memberships_url}{self.target.profile.id}/"),
            self.client.get(f"{group_url}authors/"),
            self.client.get(f"{group_url}series/"),
            self.client.get(f"{group_url}tags/"),
        ]
        for response in blocked_requests:
            with self.subTest(path=response.request["PATH_INFO"]):
                self.assertEqual(response.status_code, 404)

        create = self.client.post(
            "/api/v1/library/groups/",
            self._json({"name": "Blocked"}),
            content_type="application/json",
        )
        self.assertEqual(create.status_code, 404)
        self.custom.refresh_from_db()
        self.assertEqual(self.custom.description, "Hidden")
        self.assertTrue(
            BookGroupAssignment.objects.filter(
                group=self.custom, book=self.custom_book
            ).exists()
        )
        self.assertTrue(
            LibraryGroupMembership.objects.filter(
                group=self.custom, user=self.target
            ).exists()
        )

    def test_disabled_mode_retains_public_simple_mode_operations(self):
        public_url = f"/api/v1/library/groups/{self.public.id}/"
        books_url = f"{public_url}books/"
        memberships_url = f"{public_url}memberships/"

        self.client.login(username="librarian", password="pw")
        detail = self.client.get(f"{public_url}?include_preview_books=true")
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.json()["is_public_group"])
        self.assertIn("preview_books", detail.json())
        patch = self.client.patch(
            public_url,
            self._json({"description": "Updated simple mode"}),
            content_type="application/json",
        )
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(patch.json()["description"], "Updated simple mode")
        for axis in ("authors", "series", "tags"):
            self.assertEqual(self.client.get(f"{public_url}{axis}/").status_code, 200)
        self.assertEqual(self.client.get(books_url).status_code, 200)
        added = self.client.post(
            books_url,
            self._json({"book_id": str(self.custom_book.id)}),
            content_type="application/json",
        )
        self.assertEqual(added.status_code, 201)
        removed = self.client.delete(f"{books_url}{self.public_book.id}/")
        self.assertEqual(removed.status_code, 204)

        self.client.logout()
        self.client.login(username="manager", password="pw")
        self.assertEqual(self.client.get(memberships_url).status_code, 200)
        created = self.client.post(
            memberships_url,
            self._json({"user_id": str(self.target.profile.id)}),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201)
        member_url = f"{memberships_url}{self.target.profile.id}/"
        patched = self.client.patch(
            member_url,
            self._json({"is_curator": False}),
            content_type="application/json",
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(self.client.delete(member_url).status_code, 204)
        self.assertEqual(self.client.delete(public_url).status_code, 400)

    def test_disabled_mode_bearer_reads_public_tags_but_custom_group_is_404(self):
        public_tag = CatalogTag.objects.create(
            name="Public Tag", normalized_name="public tag", slug="public-tag"
        )
        custom_tag = CatalogTag.objects.create(
            name="Custom Tag", normalized_name="custom tag", slug="custom-tag"
        )
        BookCatalogTag.objects.create(book=self.public_book, catalog_tag=public_tag)
        BookCatalogTag.objects.create(book=self.custom_book, catalog_tag=custom_tag)
        token = "spl_disabled_group_tag_test"
        UserClientSession.objects.create(
            user=self.reader,
            name="Reader client",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        bearer_client = APIClient()

        public_response = bearer_client.get(
            f"/api/v1/library/groups/{self.public.id}/tags/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        custom_response = bearer_client.get(
            f"/api/v1/library/groups/{self.custom.id}/tags/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(public_response.status_code, 200)
        self.assertEqual(
            [row["slug"] for row in public_response.json()["results"]],
            ["public-tag"],
        )
        self.assertEqual(custom_response.status_code, 404)

    def test_enabled_mode_keeps_custom_group_api_behavior(self):
        set_advanced_library_groups_enabled(True)
        self.client.login(username="manager", password="pw")
        group_url = f"/api/v1/library/groups/{self.custom.id}/"
        books_url = f"{group_url}books/"
        memberships_url = f"{group_url}memberships/"

        listed = self.client.get("/api/v1/library/groups/?include_preview_books=true")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(
            {row["id"] for row in listed.json()["results"]},
            {str(self.public.id), str(self.custom.id)},
        )
        self.assertEqual(
            self.client.get(f"{group_url}?include_preview_books=true").status_code,
            200,
        )
        patched = self.client.patch(
            group_url,
            self._json({"description": "Enabled"}),
            content_type="application/json",
        )
        self.assertEqual(patched.status_code, 200)
        for axis in ("authors", "series", "tags"):
            self.assertEqual(self.client.get(f"{group_url}{axis}/").status_code, 200)

        self.assertEqual(self.client.get(books_url).status_code, 200)
        self.assertEqual(
            self.client.post(
                books_url,
                self._json({"book_id": str(self.candidate_book.id)}),
                content_type="application/json",
            ).status_code,
            201,
        )
        self.assertEqual(
            self.client.delete(f"{books_url}{self.candidate_book.id}/").status_code,
            204,
        )

        self.assertEqual(self.client.get(memberships_url).status_code, 200)
        self.assertEqual(
            self.client.post(
                memberships_url,
                self._json({"user_id": str(self.candidate.profile.id)}),
                content_type="application/json",
            ).status_code,
            201,
        )
        candidate_membership_url = f"{memberships_url}{self.candidate.profile.id}/"
        self.assertEqual(
            self.client.patch(
                candidate_membership_url,
                self._json({"is_curator": True}),
                content_type="application/json",
            ).status_code,
            200,
        )
        self.assertEqual(self.client.delete(candidate_membership_url).status_code, 204)

        created = self.client.post(
            "/api/v1/library/groups/",
            self._json({"name": "Created while enabled"}),
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(
            self.client.delete(
                f"/api/v1/library/groups/{created.json()['id']}/"
            ).status_code,
            204,
        )
