from django.contrib.auth.models import User
from django.test import TestCase

from accounts.local_passwords import user_supports_local_password


class LocalPasswordCapabilityTest(TestCase):
    def test_normal_local_user_supports_local_password(self):
        user = User.objects.create_user(username="local-user", password="pw")
        self.assertTrue(user_supports_local_password(user))

    def test_unusable_password_user_does_not_support_local_password(self):
        user = User.objects.create_user(username="external-only-user")
        user.set_unusable_password()
        user.save(update_fields=["password"])
        self.assertFalse(user_supports_local_password(user))
