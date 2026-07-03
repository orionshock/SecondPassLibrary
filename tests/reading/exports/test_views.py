from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession
from reading.models import ReadingSession
from tests.reading.exports.helpers import (
    AllExportFixtureMixin,
    SelectedExportFixtureMixin,
    SingleBookExportFixtureMixin,
)
from tests.reading.exports.schema_assertions import (
    assert_valid_marginalia_export,
)
from tests.reading.utils import IsolatedUserdataMixin
from tests.utils.books import create_file_backed_book


User = get_user_model()


class ReadingExportApiTests(SingleBookExportFixtureMixin, IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.set_up_single_book_export_world()

    def test_export_requires_session_auth(self):
        r = self.client.get(self._book_url())
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_export_rejects_client_bearer_token(self):
        token = "spl_export_token"
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )

        r = self.client.post(
            self._book_url(),
            {"books": [{"book_id": str(self.book.id), "sessions": "all"}]},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_book_export_includes_only_request_user_sessions_for_book(self):
        self.client.force_login(self.user)
        r = cast(Any, self._post_book())
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        assert_valid_marginalia_export(r.data)
        self.assertEqual(r["Content-Type"], "application/json")
        self.assertEqual(
            r["Content-Disposition"],
            'attachment; filename="second-pass-marginalia.json"',
        )
        self.assertIn(b'\n  "type"', r.content)
        self.assertIn(b'\n  "books"', r.content)

        data = r.data
        self.assertEqual(data["type"], "SecondPassMarginaliaExport")
        self.assertEqual(data["schema_version"], "0.1.0")
        self.assertIn("profile", data)
        self.assertIn("generated_at", data)
        self.assertIn("generator", data)
        self.assertEqual(data["scope"]["type"], "selected")
        self.assertEqual(data["scope"]["books"][0]["session_filter"], "all")
        self.assertEqual(len(data["books"]), 1)

        book = data["books"][0]
        self.assertEqual(book["title"], "Export Book")
        self.assertTrue(book["source"].startswith("book:sha256:"))
        self.assertTrue(book["file_hash"].startswith("sha256:"))
        self.assertLess(list(book.keys()).index("source"), list(book.keys()).index("sessions"))
        self.assertLess(list(book.keys()).index("file_hash"), list(book.keys()).index("sessions"))
        sessions = book["sessions"]
        self.assertEqual([s["export_session_id"] for s in sessions], ["session-1", "session-2"])
        self.assertEqual({s["name"] for s in sessions}, {"First pass", "Second pass"})
        self.assertNotIn(str(self.other_user_session.id), str(data))
        self.assertNotIn(str(self.other_book_session.id), str(data))

    def test_session_export_includes_only_selected_session(self):
        self.client.force_login(self.user)
        r = cast(Any, self._post_book(sessions=[str(self.session1.id)]))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        assert_valid_marginalia_export(r.data)
        self.assertEqual(r["Content-Type"], "application/json")
        self.assertEqual(
            r["Content-Disposition"],
            'attachment; filename="second-pass-marginalia.json"',
        )

        sessions = r.data["books"][0]["sessions"]
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["export_session_id"], "session-1")
        self.assertEqual(sessions[0]["name"], "First pass")

    def test_session_export_filename_uses_generic_session_label_when_name_blank(self):
        self.client.force_login(self.user)
        blank_session = ReadingSession.objects.create(user=self.user, book=self.book)

        r = self._post_book(sessions=[str(blank_session.id)])
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(
            r["Content-Disposition"],
            'attachment; filename="second-pass-marginalia.json"',
        )
        self.assertNotIn(str(blank_session.id), r["Content-Disposition"])

    def test_cannot_export_another_users_session(self):
        self.client.force_login(self.user)
        r = self._post_book(sessions=[str(self.other_user_session.id)])
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_mismatched_book_session_route_returns_404(self):
        self.client.force_login(self.user)
        r = self._post_book(book=self.other_book, sessions=[str(self.session1.id)])
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_selected_export_includes_owned_hidden_book_sessions(self):
        reader = User.objects.create_user(username="reader", password="pw")
        hidden = create_file_backed_book(
            title="Hidden",
            epub_bytes=b"hidden-book",
            assign_public=False,
        ).book
        ReadingSession.objects.create(user=reader, book=hidden, name="Recovered hidden")

        self.client.force_login(reader)
        r = self.client.post(
            self._book_url(),
            {"books": [{"book_id": str(hidden.id), "sessions": "all"}]},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["books"][0]["title"], "Hidden")
        self.assertEqual(r.data["books"][0]["sessions"][0]["name"], "Recovered hidden")

    def test_old_book_and_session_export_routes_are_removed(self):
        self.client.force_login(self.user)
        self.assertEqual(
            self.client.get(f"/api/v1/reading/export/books/{self.book.id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(self._session_url(self.session1)).status_code,
            status.HTTP_404_NOT_FOUND,
        )


class AllMarginaliaExportApiTests(AllExportFixtureMixin, IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.set_up_all_export_world()

    def test_all_export_requires_session_auth(self):
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_all_export_rejects_client_bearer_token(self):
        token = "spl_all_export_token"
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )

        r = self.client.get(self._url(), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_all_export_download_header_and_scope(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.get(self._url()))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        assert_valid_marginalia_export(r.data)
        self.assertEqual(r["Content-Type"], "application/json")
        self.assertEqual(
            r["Content-Disposition"],
            'attachment; filename="second-pass-marginalia.json"',
        )
        self.assertIn(b'\n  "type"', r.content)
        self.assertEqual(r.data["scope"], {"type": "all"})

    def test_all_export_includes_current_user_visible_books_with_sessions(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.get(self._url()))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        books = r.data["books"]
        titles = [book["title"] for book in books]
        self.assertEqual(titles, ["Alpha Book", "Beta Book"])
        self.assertNotIn("No Session Book", titles)
        self.assertNotIn("Other User Book", titles)

        self.assertEqual(books[0]["sessions"][0]["export_session_id"], "session-1")
        self.assertEqual(books[1]["sessions"][0]["export_session_id"], "session-1")
        self.assertEqual(books[0]["sessions"][0]["annotations"][0]["body"][0]["value"], "alpha quote")
        self.assertNotIn(str(self.other_session.id), str(r.data))

    def test_all_export_includes_owned_hidden_book_sessions(self):
        hidden = create_file_backed_book(
            title="Hidden Owned",
            epub_bytes=b"hidden-owned-book",
            assign_public=False,
        ).book
        ReadingSession.objects.create(user=self.user, book=hidden, name="Hidden pass")

        self.client.force_login(self.user)
        r = cast(Any, self.client.get(self._url()))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        books = r.data["books"]
        by_title = {book["title"]: book for book in books}
        self.assertIn("Hidden Owned", by_title)
        self.assertEqual(by_title["Hidden Owned"]["sessions"][0]["name"], "Hidden pass")


class SelectedBookMarginaliaExportApiTests(SelectedExportFixtureMixin, IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.set_up_selected_export_world()

    def test_selected_book_export_includes_only_requested_sessions(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.post(
            self._url(),
            self._body({"book_id": str(self.book.id), "sessions": [str(self.session2.id)]}),
            format="json",
        ))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        assert_valid_marginalia_export(r.data)
        self.assertEqual(
            r["Content-Disposition"],
            'attachment; filename="second-pass-marginalia.json"',
        )
        self.assertEqual(
            r.data["scope"],
            {
                "type": "selected",
                "books": [{"book": r.data["books"][0]["source"], "session_filter": "selected"}],
            },
        )

        sessions = r.data["books"][0]["sessions"]
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["export_session_id"], "session-1")
        self.assertEqual(sessions[0]["name"], "Second")
        self.assertEqual(sessions[0]["annotations"][0]["motivation"], ["bookmarking"])
        self.assertNotIn("First", str(r.data))

    def test_selected_book_export_preserves_query_order(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.post(
            self._url(),
            self._body(
                {
                    "book_id": str(self.book.id),
                    "sessions": [str(self.session2.id), str(self.session1.id)],
                }
            ),
            format="json",
        ))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        names = [session["name"] for session in r.data["books"][0]["sessions"]]
        self.assertEqual(names, ["Second", "First"])

    def test_book_export_without_session_params_still_exports_all_sessions(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.post(
            self._url(),
            self._body({"book_id": str(self.book.id), "sessions": "all"}),
            format="json",
        ))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["scope"]["type"], "selected")
        self.assertEqual(r.data["scope"]["books"][0]["session_filter"], "all")
        names = {session["name"] for session in r.data["books"][0]["sessions"]}
        self.assertEqual(names, {"First", "Second"})

    def test_selected_export_supports_multiple_books(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.post(
            self._url(),
            self._body(
                {"book_id": str(self.book.id), "sessions": [str(self.session1.id)]},
                {"book_id": str(self.other_book.id), "sessions": "all"},
            ),
            format="json",
        ))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual([book["title"] for book in r.data["books"]], ["Selected Export", "Other Book"])
        self.assertEqual(r.data["scope"]["books"][0]["session_filter"], "selected")
        self.assertEqual(r.data["scope"]["books"][1]["session_filter"], "all")

    def test_selected_book_export_returns_404_for_invalid_session_id(self):
        self.client.force_login(self.user)
        r = self.client.post(
            self._url(),
            self._body({"book_id": str(self.book.id), "sessions": ["not-a-uuid"]}),
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_selected_book_export_returns_404_for_missing_session_id(self):
        self.client.force_login(self.user)
        r = self.client.post(
            self._url(),
            self._body({"book_id": str(self.book.id), "sessions": [str(uuid4())]}),
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_selected_book_export_returns_404_for_mismatched_book_session(self):
        self.client.force_login(self.user)
        r = self.client.post(
            self._url(),
            self._body({"book_id": str(self.book.id), "sessions": [str(self.other_book_session.id)]}),
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_selected_book_export_returns_404_for_another_users_session(self):
        self.client.force_login(self.user)
        r = self.client.post(
            self._url(),
            self._body({"book_id": str(self.book.id), "sessions": [str(self.other_user_session.id)]}),
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_selected_export_rejects_empty_selection(self):
        self.client.force_login(self.user)
        r = self.client.post(self._url(), {"books": []}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_selected_export_rejects_duplicate_books(self):
        self.client.force_login(self.user)
        r = self.client.post(
            self._url(),
            self._body(
                {"book_id": str(self.book.id), "sessions": "all"},
                {"book_id": str(self.book.id), "sessions": [str(self.session1.id)]},
            ),
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_selected_book_export_rejects_client_bearer_token(self):
        token = "spl_selected_export_token"
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )

        r = self.client.post(
            self._url(),
            self._body({"book_id": str(self.book.id), "sessions": [str(self.session1.id)]}),
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
