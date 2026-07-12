from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserProfile
from tests.testenv.filesystem import IsolatedMediaRootMixin


User = get_user_model()


class SeedDevUsersCommandTestCase(IsolatedMediaRootMixin, TestCase):
    def create_setup_owner(self, username: str = "setup-owner"):
        owner = User.objects.create_superuser(
            username=username,
            password="private-password",
            email=f"{username}@example.test",
        )
        profile = UserProfile.objects.get(user=owner)
        profile.role = UserProfile.ROLE_MANAGER
        profile.save(update_fields=["role", "updated_at"])
        return owner
