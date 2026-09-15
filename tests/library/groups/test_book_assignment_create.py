from __future__ import annotations

import json
from unittest.mock import patch

from library.groups.book_assignment_workflows import create_normal_book_assignment
from library.models import Book, BookGroupAssignment, LibraryGroupMembership
from library.queries import visible_books_for_user
from library.roles import is_curator
from tests.library.groups.book_assignment_helpers import (
    LibraryGroupBookAssignmentApiTestCase,
)


class LibraryGroupBookAssignmentCreateTests(
    LibraryGroupBookAssignmentApiTestCase
):
    def test_book_picker_filter_excludes_all_existing_group_assignments(self):
        self.assertTrue(self.client.login(username="curator", password="pw"))
        for index in range(3):
            assigned = Book.objects.create(title=f"Assigned {index}")
            BookGroupAssignment.objects.create(book=assigned, group=self.club)

        response = self.client.get(
            "/api/v1/library/books/",
            {"exclude_group": str(self.club.id), "page_size": 1},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["id"], str(self.source_book.id))
        self.assertNotEqual(response.json()["results"][0]["id"], str(self.club_book.id))

    def test_librarian_manager_and_owner_can_add_any_valid_book(self):
        for username, book in [
            ("librarian", self.hidden_book),
            ("manager", self.hidden_book),
            ("owner", self.extra_hidden_book),
        ]:
            with self.subTest(username=username):
                self.assertTrue(self.client.login(username=username, password="pw"))

                response = self.client.post(
                    self.group_books_url(),
                    json.dumps({"book_id": str(book.id)}),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 201)
                payload = response.json()
                self.assertEqual(payload["group_id"], str(self.club.id))
                self.assertEqual(payload["book_id"], str(book.id))
                self.assertTrue(
                    BookGroupAssignment.objects.filter(book=book, group=self.club).exists()
                )
                self.client.logout()

    def test_curator_can_add_only_currently_visible_books(self):
        self.assertTrue(self.client.login(username="curator", password="pw"))

        visible = self.client.post(
            self.group_books_url(),
            json.dumps({"book_id": str(self.source_book.id)}),
            content_type="application/json",
        )
        hidden = self.client.post(
            self.group_books_url(),
            json.dumps({"book_id": str(self.hidden_book.id)}),
            content_type="application/json",
        )

        self.assertEqual(visible.status_code, 201)
        self.assertEqual(hidden.status_code, 404)
        self.assertFalse(
            BookGroupAssignment.objects.filter(book=self.hidden_book, group=self.club).exists()
        )

    def test_curatorship_removed_before_workflow_rejects_assignment(self):
        self.assertTrue(self.client.login(username="curator", password="pw"))

        def revoke_then_assign(**kwargs):
            self.assertTrue(is_curator(self.curator, self.club))
            LibraryGroupMembership.objects.filter(
                user=self.curator,
                group=self.club,
            ).update(is_curator=False)
            return create_normal_book_assignment(**kwargs)

        with patch(
            "library.groups.book_assignment_views.create_normal_book_assignment",
            side_effect=revoke_then_assign,
        ):
            response = self.client.post(
                self.group_books_url(),
                json.dumps({"book_id": str(self.source_book.id)}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            LibraryGroupMembership.objects.filter(
                user=self.curator,
                group=self.club,
                is_curator=False,
            ).exists()
        )
        self.assertFalse(
            BookGroupAssignment.objects.filter(
                book=self.source_book,
                group=self.club,
            ).exists()
        )

    def test_book_visibility_lost_before_workflow_rejects_assignment(self):
        self.assertTrue(self.client.login(username="curator", password="pw"))

        def hide_then_assign(**kwargs):
            self.assertTrue(
                visible_books_for_user(self.curator, cached=False)
                .filter(pk=self.source_book.pk)
                .exists()
            )
            LibraryGroupMembership.objects.filter(
                user=self.curator,
                group=self.source,
            ).delete()
            return create_normal_book_assignment(**kwargs)

        with patch(
            "library.groups.book_assignment_views.create_normal_book_assignment",
            side_effect=hide_then_assign,
        ):
            response = self.client.post(
                self.group_books_url(),
                json.dumps({"book_id": str(self.source_book.id)}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            LibraryGroupMembership.objects.filter(
                user=self.curator,
                group=self.source,
            ).exists()
        )
        self.assertFalse(
            BookGroupAssignment.objects.filter(
                book=self.source_book,
                group=self.club,
            ).exists()
        )

    def test_reader_cannot_add_visible_book(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.post(
            self.group_books_url(),
            json.dumps({"book_id": str(self.club_book.id)}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_hidden_group_returns_404_before_payload_validation(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.post(
            self.group_books_url(self.hidden),
            json.dumps({"book_id": "not-a-uuid", "unknown": "field"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_post_requires_book_id_uuid_and_rejects_unknown_fields(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        missing = self.client.post(
            self.group_books_url(),
            json.dumps({}),
            content_type="application/json",
        )
        invalid = self.client.post(
            self.group_books_url(),
            json.dumps({"book_id": "not-a-uuid"}),
            content_type="application/json",
        )
        unknown = self.client.post(
            self.group_books_url(),
            json.dumps({"book_id": str(self.hidden_book.id), "title": "nope"}),
            content_type="application/json",
        )

        self.assertEqual(missing.status_code, 400)
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(unknown.status_code, 400)
        self.assertIn("book_id", missing.json())
        self.assertIn("book_id", invalid.json())
        self.assertIn("title", unknown.json())

    def test_post_unknown_book_id_returns_404(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.post(
            self.group_books_url(),
            json.dumps({"book_id": "00000000-0000-0000-0000-000000000001"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_post_creates_assignment_and_preserves_added_by(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        created = self.client.post(
            self.group_books_url(),
            json.dumps({"book_id": str(self.hidden_book.id)}),
            content_type="application/json",
        )
        self.client.logout()
        self.assertTrue(self.client.login(username="owner", password="pw"))
        existing = self.client.post(
            self.group_books_url(),
            json.dumps({"book_id": str(self.hidden_book.id)}),
            content_type="application/json",
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(existing.status_code, 201)
        self.assertEqual(set(created.json()), {"id", "group_id", "book_id"})
        self.assertNotIn("added_by", created.json())
        self.assertEqual(created.json()["id"], existing.json()["id"])
        assignment = BookGroupAssignment.objects.get(book=self.hidden_book, group=self.club)
        self.assertEqual(assignment.added_by, self.manager)
        self.assertEqual(
            BookGroupAssignment.objects.filter(book=self.hidden_book, group=self.club).count(),
            1,
        )
