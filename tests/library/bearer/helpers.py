from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession
from core.server_settings import set_advanced_library_groups_enabled
from tests.library.helpers import LibraryCatalogApiFixtureMixin


class LibraryBearerApiTestCase(LibraryCatalogApiFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        set_advanced_library_groups_enabled(True)
        self.token = "spl_library_bearer_test"
        UserClientSession.objects.create(
            user=self.reader,
            name="Reader client",
            client_type="reader",
            token_hash=hash_client_secret(self.token),
        )
        self.bearer = APIClient()

    def bearer_get(self, path, data=None):
        return self.bearer.get(
            path,
            data or {},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    def use_manager_bearer(self):
        UserClientSession.objects.filter(token_hash=hash_client_secret(self.token)).update(
            user=self.manager
        )
