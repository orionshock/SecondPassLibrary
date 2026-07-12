from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from accounts.models import UserProfile
from core.server_settings import set_server_setting
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING
from library.models import LibraryGroup, LibraryGroupMembership
from tests.library.helpers import set_user_role


def json_body(data: dict) -> str:
    return json.dumps(data)


class LibraryGroupMembershipApiTestCase(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.target = User.objects.create_user(
            username="target",
            password="pw",
            first_name="Target",
            last_name="User",
        )
        self.other = User.objects.create_user(username="other", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        for user in [self.reader, self.target, self.other]:
            set_user_role(user, UserProfile.ROLE_READER)
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)

        self.public = LibraryGroup.objects.create(name="Common Room")
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(self.public.id),
            description="Public/Common Room group id.",
        )
        self.club = LibraryGroup.objects.create(name="Club")
        self.hidden = LibraryGroup.objects.create(name="Hidden")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.club)
        LibraryGroupMembership.objects.create(user=self.target, group=self.club)
        LibraryGroupMembership.objects.create(user=self.other, group=self.hidden)

    def membership_list_url(self, group=None) -> str:
        group = group or self.club
        return f"/api/v1/library/groups/{group.id}/memberships/"

    def membership_detail_url(self, *, group=None, user=None) -> str:
        group = group or self.club
        user = user or self.target
        return f"/api/v1/library/groups/{group.id}/memberships/{user.profile.id}/"
