from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

from accounts.models import UserProfile
from core import server_settings
from core.errors import ErrorCode
from library.groups.services import ensure_user_public_membership
from library.models import BookGroupAssignment, LibraryGroup
from library.groups.public_group import get_public_group
from tests.library.groups.helpers import BaseLibraryGroupsAPITest
from tests.utils.books import create_file_backed_book
from tests.utils.responses import (
    assert_response,
    payload_dict,
    response_data_dict,
)

User = get_user_model()


pytestmark = [pytest.mark.integration]


class LibraryGroupAdvancedFeatureGateAPITest(BaseLibraryGroupsAPITest):
    def setUp(self):
        super().setUp()
        self.public = get_public_group()
        server_settings.set_advanced_library_groups_enabled(False)

        self.manager = User.objects.create_user(username="manager", password="pw")
        ensure_user_public_membership(user=self.manager)
        profile, _ = UserProfile.objects.get_or_create(user=self.manager)
        profile.role = UserProfile.ROLE_MANAGER
        profile.save(update_fields=["role", "updated_at"])

        self.librarian = User.objects.create_user(username="librarian", password="pw")
        ensure_user_public_membership(user=self.librarian)
        profile, _ = UserProfile.objects.get_or_create(user=self.librarian)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        self.group = LibraryGroup.objects.create(name="Group", description="before")
        self.book = create_file_backed_book(title="Book", assign_public=False).book

    def assert_advanced_groups_disabled(self, response) -> None:
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIsNotNone(response.data)
        payload = response_data_dict(response)
        self.assertEqual(
            payload_dict(payload, "error")["code"],
            ErrorCode.ADVANCED_GROUPS_DISABLED,
        )

    def test_group_create_is_blocked_when_advanced_groups_disabled(self):
        self.client.login(username="manager", password="pw")

        response = assert_response(
            self.client.post(
                "/api/v1/library/groups/",
                data={"name": "Blocked"},
                format="json",
            ),
        )

        self.assert_advanced_groups_disabled(response)

    def test_group_description_patch_is_blocked_when_advanced_groups_disabled(self):
        self.client.login(username="manager", password="pw")

        response = assert_response(
            self.client.patch(
                f"/api/v1/library/groups/{self.group.id}/",
                data={"description": "after"},
                format="json",
            ),
        )

        self.assert_advanced_groups_disabled(response)

    def test_non_public_group_book_mutation_is_blocked_when_advanced_groups_disabled(
        self,
    ):
        self.client.login(username="librarian", password="pw")

        add = assert_response(
            self.client.post(
                f"/api/v1/library/groups/{self.group.id}/books/",
                data={"book": str(self.book.id)},
                format="json",
            ),
        )

        self.assert_advanced_groups_disabled(add)

    def test_public_group_book_mutation_still_works_when_advanced_groups_disabled(self):
        self.client.login(username="librarian", password="pw")

        response = assert_response(
            self.client.post(
                f"/api/v1/library/groups/{self.public.id}/books/",
                data={"book": str(self.book.id)},
                format="json",
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            BookGroupAssignment.objects.filter(
                book=self.book, group=self.public
            ).exists()
        )
