"""Shared helpers and base classes for product UI tests."""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from core.server_settings import clear_server_settings_cache
from tests.testenv.filesystem import IsolatedMediaRootMixin


User = get_user_model()


class ProductUiTestCase(IsolatedMediaRootMixin, TestCase):
    """Base test case with owner and user creation for product UI tests."""

    def setUp(self):
        cache.clear()
        clear_server_settings_cache()
        self.bootstrap_owner = User.objects.create_superuser(
            username="bootstrap-owner",
            email="bootstrap-owner@example.com",
            password="pw",
        )
        self.user = User.objects.create_user(
            username="u", email="u@example.com", password="pw"
        )
