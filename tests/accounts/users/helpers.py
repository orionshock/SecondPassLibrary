from __future__ import annotations

from django.contrib.auth import get_user_model

from accounts.models import UserProfile
from core import server_settings
from library.groups.public_group import get_public_group
from rest_framework.test import APITestCase


User = get_user_model()


class ManagedUsersApiTestMixin(APITestCase):
    def setUp(self):
        super().setUp()
        server_settings.clear_server_settings_cache()
        self.public = get_public_group()
        self.owner = User.objects.create_superuser(
            username="owner", email="owner@example.com", password="pw"
        )

        self.manager = User.objects.create_user(
            username="manager", email="manager@example.com", password="pw"
        )
        self._set_role(self.manager, UserProfile.ROLE_MANAGER)

        self.manager2 = User.objects.create_user(
            username="manager2", email="manager2@example.com", password="pw"
        )
        self._set_role(self.manager2, UserProfile.ROLE_MANAGER)

        self.librarian = User.objects.create_user(
            username="librarian", email="librarian@example.com", password="pw"
        )
        self._set_role(self.librarian, UserProfile.ROLE_LIBRARIAN)

        self.reader = User.objects.create_user(
            username="reader", email="reader@example.com", password="pw"
        )
        self._set_role(self.reader, UserProfile.ROLE_READER)

    def _set_role(self, user: User, role: str) -> None:
        user_profile, _ = UserProfile.objects.get_or_create(user=user)
        user_profile.role = role
        user_profile.save(update_fields=["role", "updated_at"])
