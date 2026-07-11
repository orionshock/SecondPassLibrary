from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from accounts.models import UserProfile
from core.server_settings import set_server_setting
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING
from library.models import LibraryGroup
from tests.library.helpers import set_user_role


class LibraryImportUploadApiTestCase(TestCase):
    url = "/api/v1/library/imports/"

    def setUp(self):
        super().setUp()
        cache.clear()
        User = get_user_model()
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.librarian = User.objects.create_user(username="librarian", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        set_user_role(self.reader, UserProfile.ROLE_READER)
        set_user_role(self.librarian, UserProfile.ROLE_LIBRARIAN)
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)
        self.public = LibraryGroup.objects.create(name="Common Room")
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(self.public.id),
            description="LibraryReWrite2607 Public/Common Room group id.",
        )

    def login_librarian(self) -> None:
        self.assertTrue(self.client.login(username="librarian", password="pw"))


def upload_file(name: str, data: bytes) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, data, content_type="application/octet-stream")
