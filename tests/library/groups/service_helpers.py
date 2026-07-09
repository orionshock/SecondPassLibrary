from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from library.groups.services import configure_public_group
from library.models import Book


class LibraryGroupServiceTestCase(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.actor = User.objects.create_user(username="actor", password="pw")
        self.user = User.objects.create_user(username="reader", password="pw")
        self.book = Book.objects.create(title="Service Book")
        self.public = configure_public_group(name="Common Room", description="Shared")
