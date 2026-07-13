from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from accounts.models import UserProfile
from core.server_settings import (
    set_advanced_library_groups_enabled,
    set_server_setting,
)
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING
from library.models import LibraryGroup, LibraryGroupMembership
from tests.library.helpers import set_user_role


class LibraryGroupMutationApiTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        set_advanced_library_groups_enabled(True)
        User = get_user_model()
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.librarian = User.objects.create_user(username="librarian", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        set_user_role(self.reader, UserProfile.ROLE_READER)
        set_user_role(self.librarian, UserProfile.ROLE_LIBRARIAN)
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)

        self.public = LibraryGroup.objects.create(name="Common Room", description="Shared")
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(self.public.id),
            description="Public/Common Room group id.",
        )
        self.club = LibraryGroup.objects.create(name="Club", description="Readers")
        self.hidden = LibraryGroup.objects.create(name="Hidden", description="Private")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.public)
        LibraryGroupMembership.objects.create(user=self.reader, group=self.club)


def json_body(data: dict) -> str:
    return json.dumps(data)
