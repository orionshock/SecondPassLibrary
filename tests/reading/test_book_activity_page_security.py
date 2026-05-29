from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.response import Response
from rest_framework.test import APIClient

from library.group_services import ensure_book_public_assignment, ensure_user_public_membership
from library.models import Book
from reading.models import Annotation, ReadingSession
from tests.utils.books import create_file_backed_book


User = get_user_model()


class BookActivityPageSecurityTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="u1", password="pass1", email="u1@example.com"
        )
        self.user2 = User.objects.create_user(
            username="u2", password="pass2", email="u2@example.com"
        )
        ensure_user_public_membership(user=self.user1)
        ensure_user_public_membership(user=self.user2)

        self.book = create_file_backed_book(title="Book 1", assign_public=False).book
        ensure_book_public_assignment(book=self.book, added_by=None)

        self.session1 = ReadingSession.objects.create(user=self.user1, book=self.book)
        self.session2 = ReadingSession.objects.create(user=self.user2, book=self.book)
        Annotation.objects.create(
            session=self.session2,
            book=self.book,
            motivation=Annotation.MOTIVATION_COMMENTING,
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/2)",
            comment_text="secret",
        )

    def test_annotations_list_for_book_is_scoped_to_request_user(self):
        client = APIClient()
        self.assertTrue(client.login(username="u1", password="pass1"))

        resp = cast(
            Response,
            client.get(f"/api/v1/reading/annotations/?book_id={self.book.id}"),
        )
        self.assertEqual(resp.status_code, 200)
        data = cast(dict[str, Any], resp.data)
        results = cast(list[dict[str, Any]], data.get("results") or [])
        # user2's annotation should not appear to user1.
        self.assertEqual(results, [])
