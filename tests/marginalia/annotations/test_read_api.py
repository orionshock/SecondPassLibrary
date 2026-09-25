from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.client_sessions.services import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession
from library.models import Book
from marginalia.annotations.collection import annotation_collection
from marginalia.models import Annotation, ReadingSession


User = get_user_model()


class MarginaliaAnnotationReadAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.other = User.objects.create_user(username="other", password="testpass")
        self.book = Book.objects.create(title="Annotations Book")
        self.active = ReadingSession.objects.create(user=self.user, book=self.book)
        self.closed = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingSession.STATUS_CLOSED,
            closed_at=timezone.now(),
        )
        self.foreign = ReadingSession.objects.create(user=self.other, book=self.book)
        self.client.force_login(self.user)

    def url(self, session=None):
        target = session or self.active
        return f"/api/v1/marginalia/sessions/{target.id}/annotations/"

    def make_annotations(self, session=None):
        target = session or self.active
        highlight = Annotation.objects.create(
            session=target,
            client_id="highlight-1",
            kind=Annotation.KIND_HIGHLIGHT,
            location="epubcfi(/6/8!/4/2:7)",
            location_label="  Chapter 08 · 42%  ",
            highlight_text="Selected passage",
            quote_prefix="Before ",
            quote_suffix=" after.",
            highlight_color="green",
            comment_text="Optional note.",
        )
        bookmark = Annotation.objects.create(
            session=target,
            client_id="bookmark-1",
            kind=Annotation.KIND_BOOKMARK,
            location="epubcfi(/6/10!/4/2)",
            location_label="Chapter 09 · 47%",
        )
        return highlight, bookmark

    def test_active_and_closed_annotations_are_owner_readable_without_library_access(
        self,
    ):
        self.make_annotations(self.active)
        self.make_annotations(self.closed)

        active = self.client.get(self.url(self.active))
        closed = self.client.get(self.url(self.closed))

        self.assertEqual(active.status_code, status.HTTP_200_OK)
        self.assertEqual(closed.status_code, status.HTTP_200_OK)
        self.assertEqual(len(active.json()["annotations"]), 2)
        self.assertEqual(len(closed.json()["annotations"]), 2)

    def test_highlight_and_bookmark_use_distinct_canonical_shapes(self):
        highlight, bookmark = self.make_annotations()

        rows = {
            row["client_id"]: row
            for row in self.client.get(self.url()).json()["annotations"]
        }

        self.assertEqual(
            set(rows["highlight-1"]),
            {"id", "client_id", "kind", "location", "body", "created_at", "updated_at"},
        )
        self.assertEqual(
            rows["highlight-1"]["location"],
            {
                "location": highlight.location,
                "location_label": highlight.location_label,
            },
        )
        self.assertEqual(
            rows["highlight-1"]["body"],
            {
                "text": "Selected passage",
                "prefix": "Before ",
                "suffix": " after.",
                "color": "green",
                "note": "Optional note.",
            },
        )
        self.assertEqual(
            set(rows["bookmark-1"]),
            {"id", "client_id", "kind", "location", "created_at", "updated_at"},
        )
        self.assertEqual(rows["bookmark-1"]["id"], str(bookmark.id))

    def test_soft_deleted_annotations_are_omitted(self):
        self.make_annotations()
        Annotation.objects.create(
            session=self.active,
            client_id="deleted",
            kind=Annotation.KIND_BOOKMARK,
            location="epubcfi(/6/12)",
            is_deleted=True,
        )

        rows = self.client.get(self.url()).json()["annotations"]

        self.assertEqual(
            {row["client_id"] for row in rows}, {"highlight-1", "bookmark-1"}
        )

    def test_reading_order_uses_labels_then_deterministic_blank_label_fallback(self):
        created = timezone.now() - timedelta(days=1)
        fixtures = (
            ("blank-b", "", "epubcfi(/6/4)"),
            ("chapter-10", "Chapter 10 · 50%", "epubcfi(/6/10)"),
            ("blank-a", "", "epubcfi(/6/2)"),
            ("chapter-02", "Chapter 02 · 10%", "epubcfi(/6/8)"),
        )
        for client_id, label, location in fixtures:
            annotation = Annotation.objects.create(
                session=self.active,
                client_id=client_id,
                kind=Annotation.KIND_BOOKMARK,
                location=location,
                location_label=label,
            )
            Annotation.objects.filter(pk=annotation.pk).update(created_at=created)

        first = self.client.get(self.url()).json()["annotations"]
        second = self.client.get(self.url()).json()["annotations"]

        expected = ["chapter-02", "chapter-10", "blank-a", "blank-b"]
        self.assertEqual([row["client_id"] for row in first], expected)
        self.assertEqual([row["client_id"] for row in second], expected)

    def test_missing_and_foreign_sessions_do_not_leak(self):
        foreign = self.client.get(self.url(self.foreign))
        missing = self.client.get(
            "/api/v1/marginalia/sessions/"
            "00000000-0000-0000-0000-000000000000/annotations/"
        )

        self.assertEqual(foreign.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(foreign.json(), missing.json())

    def test_session_and_bearer_reads_match(self):
        self.make_annotations()
        expected = self.client.get(self.url()).json()
        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )

        response = APIClient().get(
            self.url(),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), expected)

    def test_get_and_reusable_assembler_are_bounded_and_read_only(self):
        highlight, _bookmark = self.make_annotations()
        before = (self.active.updated_at, highlight.updated_at)

        with self.assertNumQueries(2):
            session = ReadingSession.objects.get(pk=self.active.pk, user=self.user)
            payload = annotation_collection(session)
        response = self.client.get(self.url())
        self.active.refresh_from_db()
        highlight.refresh_from_db()

        self.assertEqual(len(payload["annotations"]), 2)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual((self.active.updated_at, highlight.updated_at), before)
