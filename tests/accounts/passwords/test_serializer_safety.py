from __future__ import annotations

from typing import cast

from django.test import TestCase
from rest_framework import serializers

from accounts.users.serializers import ManagedUserSerializer


class UserSerializerDoesNotLeakPasswordsTests(TestCase):
    def test_managed_user_payload_never_contains_password_fields(self):
        serializer = cast(serializers.Serializer, ManagedUserSerializer())
        self.assertNotIn("password", serializer.fields)
        self.assertNotIn("temporary_password", serializer.fields)
