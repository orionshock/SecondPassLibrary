from __future__ import annotations

from typing import cast

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from core import server_settings
from core.errors import ErrorCode
from library.groups.services import ensure_user_public_membership
from library.groups.public_group import get_public_group
from library.models import LibraryGroup, LibraryGroupMembership


User = get_user_model()


pytestmark = [pytest.mark.integration]


class LibraryGroupMembershipFeatureGateAPITest(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="manager", email="manager@example.com", password="pw"
        )
        ensure_user_public_membership(user=self.manager)
        manager_profile, _ = UserProfile.objects.get_or_create(user=self.manager)
        manager_profile.role = UserProfile.ROLE_MANAGER
        manager_profile.save(update_fields=["role", "updated_at"])

        self.reader = User.objects.create_user(
            username="reader", email="reader@example.com", password="pw"
        )
        ensure_user_public_membership(user=self.reader)
        reader_profile, _ = UserProfile.objects.get_or_create(user=self.reader)
        reader_profile.role = UserProfile.ROLE_READER
        reader_profile.save(update_fields=["role", "updated_at"])

        self.group = LibraryGroup.objects.create(name="Group")
        self.membership = LibraryGroupMembership.objects.create(
            user=self.reader,
            group=self.group,
        )

    def assert_advanced_groups_disabled(self, response: Response) -> None:
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        payload = cast(dict, response.data)
        self.assertEqual(
            cast(dict, payload["error"])["code"],
            ErrorCode.ADVANCED_GROUPS_DISABLED,
        )

    def test_membership_add_is_blocked_when_advanced_groups_disabled(self):
        self.client.login(username="manager", password="pw")

        response = cast(
            Response,
            self.client.post(
                f"/api/v1/library/groups/{self.group.id}/memberships/",
                data={"profile_id": self.reader.profile.id},
                format="json",
            ),
        )

        self.assert_advanced_groups_disabled(response)

    def test_membership_curator_update_is_blocked_when_advanced_groups_disabled(self):
        self.client.login(username="manager", password="pw")

        response = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/groups/{self.group.id}/memberships/{self.membership.id}/",
                data={"is_curator": True},
                format="json",
            ),
        )

        self.assert_advanced_groups_disabled(response)

    def test_membership_remove_is_blocked_when_advanced_groups_disabled(self):
        self.client.login(username="manager", password="pw")

        response = cast(
            Response,
            self.client.delete(
                f"/api/v1/library/groups/{self.group.id}/memberships/{self.membership.id}/",
            ),
        )

        self.assert_advanced_groups_disabled(response)


class LibraryGroupMembershipManagementAPITest(APITestCase):
    def setUp(self):
        server_settings.set_advanced_library_groups_enabled(True)
        self.public = get_public_group()

        self.owner = User.objects.create_superuser(
            username="owner", email="owner@example.com", password="pw"
        )
        ensure_user_public_membership(user=self.owner)
        owner_profile, _ = UserProfile.objects.get_or_create(user=self.owner)
        owner_profile.role = UserProfile.ROLE_MANAGER
        owner_profile.save(update_fields=["role", "updated_at"])

        self.manager = User.objects.create_user(
            username="manager", email="manager@example.com", password="pw"
        )
        ensure_user_public_membership(user=self.manager)
        manager_profile, _ = UserProfile.objects.get_or_create(user=self.manager)
        manager_profile.role = UserProfile.ROLE_MANAGER
        manager_profile.save(update_fields=["role", "updated_at"])

        self.librarian = User.objects.create_user(
            username="librarian", email="librarian@example.com", password="pw"
        )
        ensure_user_public_membership(user=self.librarian)
        librarian_profile, _ = UserProfile.objects.get_or_create(user=self.librarian)
        librarian_profile.role = UserProfile.ROLE_LIBRARIAN
        librarian_profile.save(update_fields=["role", "updated_at"])

        self.reader = User.objects.create_user(
            username="reader", email="reader@example.com", password="pw"
        )
        ensure_user_public_membership(user=self.reader)
        reader_profile, _ = UserProfile.objects.get_or_create(user=self.reader)
        reader_profile.role = UserProfile.ROLE_READER
        reader_profile.save(update_fields=["role", "updated_at"])

        self.group = LibraryGroup.objects.create(
            name="Group"
        )

    def test_manager_and_owner_can_list_memberships(self):
        LibraryGroupMembership.objects.create(user=self.reader, group=self.group)
        self.client.login(username="manager", password="pw")
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/groups/{self.group.id}/memberships/"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = cast(dict, response.data)
        first = cast(list[dict], payload["results"])[0]
        self.assertIn("user", first)
        self.assertNotIn("user_id", first)
        self.assertEqual(first["user"]["profile_id"], str(self.reader.profile.id))
        self.assertEqual(first["user"]["username"], "reader")
        self.assertEqual(first["user"]["email"], "reader@example.com")
        self.assertIn("first_name", first["user"])
        self.assertIn("last_name", first["user"])
        self.assertNotIn("is_owner", first["user"])

        self.client.logout()
        self.client.login(username="owner", password="pw")
        response2 = cast(
            Response,
            self.client.get(f"/api/v1/library/groups/{self.group.id}/memberships/"),
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

    def test_librarian_can_list_memberships(self):
        self.client.login(username="librarian", password="pw")
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/groups/{self.group.id}/memberships/"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_member_reader_cannot_list_memberships_for_non_public_group(self):
        self.client.login(username="reader", password="pw")
        response2 = cast(
            Response,
            self.client.get(f"/api/v1/library/groups/{self.group.id}/memberships/"),
        )
        self.assertEqual(response2.status_code, status.HTTP_404_NOT_FOUND)

    def test_group_member_can_list_memberships_for_their_group(self):
        LibraryGroupMembership.objects.create(
            user=self.reader, group=self.group
        )
        self.client.login(username="reader", password="pw")
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/groups/{self.group.id}/memberships/"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_membership_defaults_to_non_curator(self):
        membership = LibraryGroupMembership.objects.create(user=self.reader, group=self.group)
        self.assertFalse(membership.is_curator)

    def test_direct_public_curator_creation_is_rejected(self):
        with self.assertRaises(DjangoValidationError):
            LibraryGroupMembership.objects.create(
                user=self.reader,
                group=self.public,
                is_curator=True,
            )

    def test_authenticated_user_can_list_public_memberships(self):
        self.client.login(username="reader", password="pw")
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/groups/{self.public.id}/memberships/"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_manager_can_add_reader_and_curator_memberships_non_public(self):
        self.client.login(username="manager", password="pw")
        add_reader = cast(
            Response,
            self.client.post(
                f"/api/v1/library/groups/{self.group.id}/memberships/",
                data={"profile_id": self.reader.profile.id},
                format="json",
            ),
        )
        self.assertEqual(add_reader.status_code, status.HTTP_201_CREATED)
        add_reader_data = cast(dict, add_reader.data)
        self.assertFalse(add_reader_data["is_curator"])
        self.assertEqual(add_reader_data["user"]["profile_id"], str(self.reader.profile.id))
        self.assertNotIn("is_owner", add_reader_data["user"])
        self.assertNotIn("user_id", add_reader_data)
        self.assertNotIn("role", add_reader_data)

        add_curator = cast(
            Response,
            self.client.post(
                f"/api/v1/library/groups/{self.group.id}/memberships/",
                data={"profile_id": self.reader.profile.id, "is_curator": True},
                format="json",
            ),
        )
        self.assertEqual(add_curator.status_code, status.HTTP_201_CREATED)
        add_curator_data = cast(dict, add_curator.data)
        self.assertTrue(add_curator_data["is_curator"])
        self.assertEqual(add_curator_data["user"]["profile_id"], str(self.reader.profile.id))
        membership = LibraryGroupMembership.objects.get(user=self.reader, group=self.group)
        self.assertTrue(membership.is_curator)

    def test_broad_role_users_may_be_curators_on_non_public_groups(self):
        for user in (self.owner, self.manager, self.librarian):
            with self.subTest(username=user.username):
                self.client.logout()
                self.client.login(username="owner", password="pw")
                response = cast(
                    Response,
                    self.client.post(
                        f"/api/v1/library/groups/{self.group.id}/memberships/",
                        data={"profile_id": user.profile.id, "is_curator": True},
                        format="json",
                    ),
                )
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                membership = LibraryGroupMembership.objects.get(user=user, group=self.group)
                self.assertTrue(membership.is_curator)

    def test_reader_librarian_and_curator_cannot_mutate_memberships(self):
        curator_user = User.objects.create_user(
            username="curator", email="curator@example.com", password="pw"
        )
        ensure_user_public_membership(user=curator_user)
        curator_profile, _ = UserProfile.objects.get_or_create(user=curator_user)
        curator_profile.role = UserProfile.ROLE_READER
        curator_profile.save(update_fields=["role", "updated_at"])

        membership = LibraryGroupMembership.objects.create(
            user=self.reader, group=self.group
        )
        LibraryGroupMembership.objects.create(
            user=curator_user, group=self.group, is_curator=True
        )

        for username in ("reader", "librarian", "curator"):
            self.client.logout()
            self.client.login(username=username, password="pw")

            create = cast(
                Response,
                self.client.post(
                    f"/api/v1/library/groups/{self.group.id}/memberships/",
                    data={"profile_id": self.manager.profile.id},
                    format="json",
                ),
            )
            self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)

            patch = cast(
                Response,
                self.client.patch(
                    f"/api/v1/library/groups/{self.group.id}/memberships/{membership.id}/",
                    data={"is_curator": True},
                    format="json",
                ),
            )
            self.assertEqual(patch.status_code, status.HTTP_403_FORBIDDEN)

            delete = cast(
                Response,
                self.client.delete(
                    f"/api/v1/library/groups/{self.group.id}/memberships/{membership.id}/",
                ),
            )
            self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_duplicate_add_is_idempotent_and_updates_curator_status(self):
        self.client.login(username="manager", password="pw")
        first = cast(
            Response,
            self.client.post(
                f"/api/v1/library/groups/{self.group.id}/memberships/",
                data={"profile_id": self.reader.profile.id},
                format="json",
            ),
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = cast(
            Response,
            self.client.post(
                f"/api/v1/library/groups/{self.group.id}/memberships/",
                data={"profile_id": self.reader.profile.id, "is_curator": True},
                format="json",
            ),
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(LibraryGroupMembership.objects.filter(user=self.reader, group=self.group).count(), 1)
        membership = LibraryGroupMembership.objects.get(user=self.reader, group=self.group)
        self.assertTrue(membership.is_curator)

    def test_manager_cannot_add_curator_membership_to_public(self):
        self.client.login(username="manager", password="pw")
        response = cast(
            Response,
            self.client.post(
                f"/api/v1/library/groups/{self.public.id}/memberships/",
                data={"profile_id": self.reader.profile.id, "is_curator": True},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.reader.refresh_from_db()
        public_membership = LibraryGroupMembership.objects.get(user=self.reader, group=self.public)
        self.assertFalse(public_membership.is_curator)

    def test_manager_can_remove_public_membership_if_another_group_remains(self):
        other = LibraryGroup.objects.create(name="Other")
        LibraryGroupMembership.objects.create(user=self.reader, group=other)

        self.client.login(username="manager", password="pw")
        membership = LibraryGroupMembership.objects.get(user=self.reader, group=self.public)
        response = cast(
            Response,
            self.client.delete(
                f"/api/v1/library/groups/{self.public.id}/memberships/{membership.id}/"
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(LibraryGroupMembership.objects.filter(pk=membership.id).exists())
        self.assertTrue(LibraryGroupMembership.objects.filter(user=self.reader, group=other).exists())

    def test_removing_users_final_membership_restores_public(self):
        # Remove the only (Public) membership; invariant should restore it.
        self.client.login(username="manager", password="pw")
        membership = LibraryGroupMembership.objects.get(user=self.reader, group=self.public)
        response = cast(
            Response,
            self.client.delete(
                f"/api/v1/library/groups/{self.public.id}/memberships/{membership.id}/"
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(LibraryGroupMembership.objects.filter(user=self.reader).exists())
        restored = LibraryGroupMembership.objects.get(user=self.reader, group=self.public)
        self.assertFalse(restored.is_curator)

    def test_manager_can_update_and_remove_non_public_membership(self):
        self.client.login(username="manager", password="pw")
        membership = LibraryGroupMembership.objects.create(
            user=self.reader, group=self.group
        )

        patched = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/groups/{self.group.id}/memberships/{membership.id}/",
                data={"is_curator": True},
                format="json",
            ),
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        patched_data = cast(dict, patched.data)
        self.assertIn("user", patched_data)
        self.assertEqual(patched_data["user"]["profile_id"], str(self.reader.profile.id))
        self.assertNotIn("is_owner", patched_data["user"])
        self.assertNotIn("user_id", patched_data)
        membership.refresh_from_db()
        self.assertTrue(membership.is_curator)

        deleted = cast(
            Response,
            self.client.delete(
                f"/api/v1/library/groups/{self.group.id}/memberships/{membership.id}/"
            ),
        )
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(LibraryGroupMembership.objects.filter(pk=membership.id).exists())

    def test_public_curator_update_is_rejected(self):
        self.client.login(username="manager", password="pw")
        membership = LibraryGroupMembership.objects.get(user=self.reader, group=self.public)
        response = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/groups/{self.public.id}/memberships/{membership.id}/",
                data={"is_curator": True},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        membership.refresh_from_db()
        self.assertFalse(membership.is_curator)

    def test_legacy_integer_user_field_is_rejected(self):
        self.client.login(username="manager", password="pw")
        response = cast(
            Response,
            self.client.post(
                f"/api/v1/library/groups/{self.group.id}/memberships/",
                data={"user": self.reader.pk},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_legacy_role_field_is_rejected(self):
        self.client.login(username="manager", password="pw")
        response = cast(
            Response,
            self.client.post(
                f"/api/v1/library/groups/{self.group.id}/memberships/",
                data={"profile_id": self.reader.profile.id, "role": "curator"},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
