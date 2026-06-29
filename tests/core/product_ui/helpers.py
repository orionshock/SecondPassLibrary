"""Shared helpers and base classes for product UI tests."""
from django.contrib.auth import get_user_model
from django.test import TestCase


User = get_user_model()


class ProductUiTestCase(TestCase):
    """Base test case with owner and user creation for product UI tests."""

    def setUp(self):
        self.bootstrap_owner = User.objects.create_superuser(
            username="bootstrap-owner",
            email="bootstrap-owner@example.com",
            password="pw",
        )
        self.user = User.objects.create_user(
            username="u", email="u@example.com", password="pw"
        )
