from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.bootstrap import (
    SetupAlreadyComplete,
    create_first_owner,
    has_active_owner,
)
from accounts.models import UserProfile
from core import server_settings
from library.group_services import get_public_group
from library.models import LibraryGroupMembership


User = get_user_model()


class FirstOwnerBootstrapServiceTests(TestCase):
    def test_active_superuser_is_owner_capable(self):
        self.assertFalse(has_active_owner())
        User.objects.create_superuser(
            username="owner", email="owner@example.com", password="pw"
        )
        self.assertTrue(has_active_owner())

    def test_inactive_superuser_does_not_block_setup(self):
        User.objects.create_superuser(
            username="disabled-owner",
            email="disabled-owner@example.com",
            password="pw",
            is_active=False,
        )
        self.assertFalse(has_active_owner())

    def test_create_first_owner_creates_local_owner_profile_and_public_membership(self):
        owner = create_first_owner(
            username="owner",
            password="Correct-Horse-Battery-47",
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
        )

        owner.refresh_from_db()
        profile = UserProfile.objects.get(user=owner)
        public = get_public_group()

        self.assertTrue(owner.is_active)
        self.assertTrue(owner.is_staff)
        self.assertTrue(owner.is_superuser)
        self.assertTrue(owner.check_password("Correct-Horse-Battery-47"))
        self.assertEqual(owner.first_name, "Ada")
        self.assertEqual(owner.last_name, "Lovelace")
        self.assertEqual(owner.email, "ada@example.com")
        self.assertEqual(profile.role, UserProfile.ROLE_MANAGER)
        self.assertFalse(profile.must_change_password)
        self.assertEqual(server_settings.get_server_name(), "Second Pass Library")
        self.assertEqual(server_settings.get_server_description(), "")
        self.assertFalse(server_settings.get_advanced_library_groups_enabled())
        self.assertEqual(public.name, "Common Room")
        self.assertEqual(
            public.description,
            "Main Public Library Room for everyone",
        )
        self.assertTrue(
            LibraryGroupMembership.objects.filter(
                user=owner,
                group=public,
                role=LibraryGroupMembership.ROLE_READER,
            ).exists()
        )

    def test_create_first_owner_accepts_blank_email(self):
        owner = create_first_owner(
            username="owner",
            password="Correct-Horse-Battery-47",
        )
        self.assertEqual(owner.email, "")

    def test_create_first_owner_saves_configured_server_and_public_space(self):
        create_first_owner(
            username="owner",
            password="Correct-Horse-Battery-47",
            server_name="Family Library",
            server_description="Shared at home.",
            public_group_name="Reading Room",
            public_group_description="Books for everyone.",
            advanced_library_groups_enabled=True,
        )

        public = get_public_group()
        self.assertEqual(server_settings.get_server_name(), "Family Library")
        self.assertEqual(
            server_settings.get_server_description(),
            "Shared at home.",
        )
        self.assertTrue(server_settings.get_advanced_library_groups_enabled())
        self.assertEqual(public.name, "Reading Room")
        self.assertEqual(public.description, "Books for everyone.")

    def test_second_create_is_rejected(self):
        create_first_owner(
            username="owner",
            password="Correct-Horse-Battery-47",
        )

        with self.assertRaises(SetupAlreadyComplete):
            create_first_owner(
                username="owner-two",
                password="Another-Correct-Password-48",
            )

        self.assertEqual(User.objects.filter(is_superuser=True).count(), 1)
