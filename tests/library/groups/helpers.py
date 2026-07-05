from __future__ import annotations

from rest_framework.test import APITestCase

from library.groups.public_group import get_public_group
from library.models import LibraryGroupMembership


class BaseLibraryGroupsAPITest(APITestCase):
    def setUp(self):
        super().setUp()
        self.public = get_public_group()

    def create_membership(
        self, *, user, group, is_curator=False
    ) -> LibraryGroupMembership:
        return LibraryGroupMembership.objects.create(
            user=user,
            group=group,
            is_curator=is_curator,
        )
