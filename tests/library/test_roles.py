from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from accounts.models import UserProfile
from accounts.roles import is_librarian, is_manager, is_owner
from core.server_settings import set_server_setting
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING
from library.models import LibraryGroup, LibraryGroupMembership
from library.roles import is_curator
from tests.library.helpers import set_user_role


class LibraryReWrite2607RolePrimitiveTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.curator = User.objects.create_user(username="curator", password="pw")
        self.librarian = User.objects.create_user(username="librarian", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        for user in [self.reader, self.curator]:
            set_user_role(user, UserProfile.ROLE_READER)
        set_user_role(self.librarian, UserProfile.ROLE_LIBRARIAN)
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)

        self.public = LibraryGroup.objects.create(name="Common Room")
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(self.public.id),
            description="LibraryReWrite2607 Public/Common Room group id.",
        )
        self.club = LibraryGroup.objects.create(name="Club")
        self.other_group = LibraryGroup.objects.create(name="Other")
        LibraryGroupMembership.objects.create(user=self.curator, group=self.club, is_curator=True)

    def test_owner_implies_manager_librarian_and_curator(self):
        self.assertTrue(is_owner(self.owner))
        self.assertTrue(is_manager(self.owner))
        self.assertTrue(is_librarian(self.owner))
        self.assertTrue(is_curator(self.owner, self.club))

    def test_manager_implies_librarian_and_curator(self):
        self.assertFalse(is_owner(self.manager))
        self.assertTrue(is_manager(self.manager))
        self.assertTrue(is_librarian(self.manager))
        self.assertTrue(is_curator(self.manager, self.club))

    def test_librarian_implies_curator_but_not_manager_or_owner(self):
        self.assertFalse(is_owner(self.librarian))
        self.assertFalse(is_manager(self.librarian))
        self.assertTrue(is_librarian(self.librarian))
        self.assertTrue(is_curator(self.librarian, self.club))

    def test_group_curator_does_not_imply_librarian_manager_or_owner(self):
        self.assertFalse(is_owner(self.curator))
        self.assertFalse(is_manager(self.curator))
        self.assertFalse(is_librarian(self.curator))
        self.assertTrue(is_curator(self.curator, self.club))

    def test_curator_is_group_specific(self):
        self.assertTrue(is_curator(self.curator, self.club))
        self.assertFalse(is_curator(self.curator, self.other_group))

    def test_public_membership_alone_does_not_make_curator(self):
        LibraryGroupMembership.objects.create(user=self.reader, group=self.public)

        self.assertFalse(is_curator(self.reader, self.public))
