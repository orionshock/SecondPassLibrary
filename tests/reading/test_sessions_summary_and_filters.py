from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.client_api import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession
from library.group_services import (
    add_book_to_group,
    ensure_book_public_assignment,
    ensure_user_public_membership,
)
from library.models import LibraryGroup, LibraryGroupMembership
from reading.models import Annotation, ReadingProgress, ReadingSession
from tests.utils.books import create_file_backed_book


User = get_user_model()


def _results(resp: Response) -> list[dict[str, Any]]:
    payload = cast(dict[str, Any], resp.data)
    return cast(list[dict[str, Any]], payload.get("results") or [])


class ReadingSessionSummarySessionAuthTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(username="owner", password="pw", email="o@example.com")
        ensure_user_public_membership(user=self.owner)

        self.user = User.objects.create_user(username="u", password="pw", email="u@example.com")
        ensure_user_public_membership(user=self.user)
        self.client.login(username="u", password="pw")

        self.book = create_file_backed_book(title="Visible").book

        self.hidden_group = LibraryGroup.objects.create(name="Hidden")
        other = User.objects.create_user(username="other", password="pw", email="o@example.com")
        ensure_user_public_membership(user=other)
        LibraryGroupMembership.objects.create(user=other, group=self.hidden_group, role=LibraryGroupMembership.ROLE_READER)

        self.hidden_book = create_file_backed_book(title="Hidden", assign_public=False).book
        add_book_to_group(actor=self.owner, book=self.hidden_book, group=self.hidden_group)

        self.session_visible = ReadingSession.objects.create(user=self.user, book=self.book, name="S1")
        ReadingProgress.objects.create(session=self.session_visible, current_location={"cfi": "/6/2"}, progression=0.25)
        Annotation.objects.create(
            session=self.session_visible,
            book=self.book,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/2)",
            highlight_text="hi",
        )
        Annotation.objects.create(
            session=self.session_visible,
            book=self.book,
            motivation=Annotation.MOTIVATION_COMMENTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/4)",
            highlight_text="deleted",
            comment_text="deleted",
            is_deleted=True,
        )

        self.session_hidden = ReadingSession.objects.create(user=self.user, book=self.hidden_book, name="Secret")

    def test_list_includes_progression_annotation_count_and_compact_book(self):
        resp = cast(Response, self.client.get("/api/v1/reading/sessions/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = _results(resp)
        by_id = {r["id"]: r for r in results}

        visible = by_id[str(self.session_visible.id)]
        self.assertIn("progression", visible)
        self.assertEqual(visible["progression"], 0.25)
        self.assertEqual(visible["annotation_count"], 1)
        self.assertIn("book", visible)
        book = cast(dict[str, Any], visible["book"])
        self.assertEqual(book["id"], str(self.book.id))
        self.assertEqual(book["title"], "Visible")
        self.assertIsInstance(book["authors"], list)
        self.assertIn("cover_url", book)

    def test_list_does_not_leak_hidden_book_metadata(self):
        resp = cast(Response, self.client.get("/api/v1/reading/sessions/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = _results(resp)
        hidden = next(r for r in results if r["id"] == str(self.session_hidden.id))
        book = cast(dict[str, Any], hidden["book"])
        self.assertEqual(book["id"], str(self.hidden_book.id))
        self.assertEqual(book["title"], "")
        self.assertEqual(book["authors"], [])
        self.assertIsNone(book["series"])
        self.assertIsNone(book["cover_url"])

    def test_filters_book_status_is_active(self):
        self.session_visible.status = ReadingSession.STATUS_COMPLETED
        self.session_visible.is_active = False
        self.session_visible.save(update_fields=["status", "is_active", "updated_at"])

        r_book = cast(Response, self.client.get(f"/api/v1/reading/sessions/?book={self.book.id}"))
        self.assertEqual(r_book.status_code, 200)
        self.assertEqual({s["id"] for s in _results(r_book)}, {str(self.session_visible.id)})

        r_status = cast(Response, self.client.get("/api/v1/reading/sessions/?status=completed"))
        self.assertEqual(r_status.status_code, 200)
        self.assertIn(str(self.session_visible.id), {s["id"] for s in _results(r_status)})

        r_active = cast(Response, self.client.get("/api/v1/reading/sessions/?is_active=false"))
        self.assertEqual(r_active.status_code, 200)
        self.assertIn(str(self.session_visible.id), {s["id"] for s in _results(r_active)})

    def test_invalid_filters_return_400(self):
        bad_book = cast(Response, self.client.get("/api/v1/reading/sessions/?book=not-a-uuid"))
        self.assertEqual(bad_book.status_code, status.HTTP_400_BAD_REQUEST)

        bad_status = cast(Response, self.client.get("/api/v1/reading/sessions/?status=nope"))
        self.assertEqual(bad_status.status_code, status.HTTP_400_BAD_REQUEST)

        bad_active = cast(Response, self.client.get("/api/v1/reading/sessions/?is_active=maybe"))
        self.assertEqual(bad_active.status_code, status.HTTP_400_BAD_REQUEST)


class ReadingSessionSummaryBearerTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="pw", email="u@example.com")
        ensure_user_public_membership(user=self.user)

        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        self._auth = f"Bearer {token}"

        self.book = create_file_backed_book(title="Visible").book
        self.session = ReadingSession.objects.create(user=self.user, book=self.book)

    def test_bearer_list_includes_compact_book(self):
        resp = cast(Response, self.client.get("/api/v1/reading/sessions/", HTTP_AUTHORIZATION=self._auth))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = _results(resp)
        self.assertEqual(len(results), 1)
        s0 = results[0]
        self.assertIn("book", s0)
        book = cast(dict[str, Any], s0["book"])
        self.assertEqual(book["id"], str(self.book.id))
