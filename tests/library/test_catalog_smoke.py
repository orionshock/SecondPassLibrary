from __future__ import annotations


from rest_framework import status
from rest_framework.test import APITestCase


from tests.library.helpers import (
    create_reader_user,
)

class LibraryAPITest(APITestCase):
    def setUp(self):
        self.user = create_reader_user(username="testuser", password="testpass")
        self.client.login(username="testuser", password="testpass")

    def test_authenticated_access_books(self):
        response = self.client.get("/api/v1/library/books/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_authenticated_access_authors(self):
        response = self.client.get("/api/v1/library/authors/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
