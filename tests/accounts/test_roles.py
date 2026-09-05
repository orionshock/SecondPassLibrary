from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from accounts.models import UserProfile
from accounts.roles import (
    RoleRank,
    effective_role_rank,
    is_librarian,
    is_manager,
    is_owner,
)


class AccountRoleRankTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.librarian = User.objects.create_user(username="librarian", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        self.no_profile = User.objects.create_user(username="no-profile", password="pw")
        self.inactive = User.objects.create_user(username="inactive", password="pw", is_active=False)
        self.librarian.profile.role = UserProfile.ROLE_LIBRARIAN
        self.librarian.profile.save(update_fields=["role", "updated_at"])
        self.manager.profile.role = UserProfile.ROLE_MANAGER
        self.manager.profile.save(update_fields=["role", "updated_at"])
        self.inactive.profile.role = UserProfile.ROLE_MANAGER
        self.inactive.profile.save(update_fields=["role", "updated_at"])
        self.no_profile.profile.delete()
        self.no_profile.refresh_from_db()

    def test_effective_role_rank_maps_account_and_fallback_states(self):
        cases = [
            (None, RoleRank.READER),
            (AnonymousUser(), RoleRank.READER),
            (self.inactive, RoleRank.READER),
            (self.no_profile, RoleRank.READER),
            (self.reader, RoleRank.READER),
            (self.librarian, RoleRank.LIBRARIAN),
            (self.manager, RoleRank.MANAGER),
            (self.owner, RoleRank.OWNER),
        ]

        for user, rank in cases:
            with self.subTest(user=getattr(user, "username", None)):
                self.assertEqual(effective_role_rank(user), rank)

    def test_role_inheritance_uses_rank_comparisons(self):
        expectations = [
            (self.owner, True, True, True),
            (self.manager, False, True, True),
            (self.librarian, False, False, True),
            (self.reader, False, False, False),
        ]

        for user, owner, manager, librarian in expectations:
            with self.subTest(user=user.username):
                self.assertEqual(is_owner(user), owner)
                self.assertEqual(is_manager(user), manager)
                self.assertEqual(is_librarian(user), librarian)
