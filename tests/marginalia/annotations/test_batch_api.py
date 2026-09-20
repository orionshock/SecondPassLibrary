from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.client_sessions.services import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession
from library.models import (
    Book,
    BookGroupAssignment,
    LibraryGroup,
    LibraryGroupMembership,
)
from marginalia.annotations.serializers import BATCH_ANNOTATION_OPERATION_LIMIT
from marginalia.annotations.services import synchronize_annotations
from marginalia.exceptions import SessionClosedError
from marginalia.models import Annotation, ReadingSession


User = get_user_model()


def bookmark(client_id: str, cfi: str = "epubcfi(/6/2)") -> dict:
    return {
        "action": "upsert",
        "annotation": {
            "client_id": client_id,
            "kind": "bookmark",
            "location": {"cfi": cfi, "location_label": "Chapter 01 · 5%"},
        },
    }


def highlight(client_id: str, text: str = "Selected passage") -> dict:
    return {
        "action": "upsert",
        "annotation": {
            "client_id": client_id,
            "kind": "highlight",
            "location": {
                "cfi": "epubcfi(/6/8!/4/2:7)",
                "location_label": "  Chapter 08 · 42%  ",
            },
            "body": {
                "text": text,
                "prefix": "Before ",
                "suffix": " after.",
                "note": "Reader note.",
            },
        },
    }


class MarginaliaAnnotationBatchAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.other = User.objects.create_user(username="other", password="testpass")
        self.group = LibraryGroup.objects.create(name="Readers")
        LibraryGroupMembership.objects.create(user=self.user, group=self.group)
        self.book = Book.objects.create(title="Sync Book")
        BookGroupAssignment.objects.create(book=self.book, group=self.group)
        self.session = ReadingSession.objects.create(user=self.user, book=self.book)
        self.foreign = ReadingSession.objects.create(user=self.other, book=self.book)
        self.client.force_login(self.user)

    def url(self, session=None):
        target = session or self.session
        return f"/api/v1/marginalia/sessions/{target.id}/annotations/batch/"

    def post(self, operations, session=None):
        return self.client.post(
            self.url(session),
            {"operations": operations},
            format="json",
        )

    def test_multiple_kinds_create_atomically_and_identical_retry_is_stable(self):
        operations = [highlight("highlight-1"), bookmark("bookmark-1")]

        first = self.post(operations)
        timestamps = {
            row["client_id"]: row["updated_at"] for row in first.json()["annotations"]
        }
        second = self.post(operations)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(Annotation.objects.filter(session=self.session).count(), 2)
        self.assertEqual(
            next(
                row for row in first.json()["annotations"] if row["kind"] == "highlight"
            )["body"]["color"],
            "yellow",
        )
        self.assertEqual(
            {row["client_id"]: row["updated_at"] for row in second.json()["annotations"]},
            timestamps,
        )

    def test_upsert_updates_without_duplicates_and_restores_soft_deleted_rows(self):
        self.post([highlight("same")])
        updated = self.post([highlight("same", text="Replacement")])
        deleted = self.post([{"action": "delete", "client_id": "same"}])
        tombstone = Annotation.objects.get(session=self.session, client_id="same")
        deleted_at = tombstone.deleted_at
        repeated = self.post([{"action": "delete", "client_id": "same"}])
        tombstone.refresh_from_db()
        restored = self.post([highlight("same", text="Restored")])

        annotation = Annotation.objects.get(session=self.session, client_id="same")
        self.assertEqual(updated.json()["annotations"][0]["body"]["text"], "Replacement")
        self.assertEqual(deleted.json()["annotations"], [])
        self.assertEqual(repeated.json()["annotations"], [])
        self.assertIsNotNone(deleted_at)
        self.assertEqual(tombstone.deleted_at, deleted_at)
        self.assertEqual(restored.json()["annotations"][0]["body"]["text"], "Restored")
        self.assertFalse(annotation.is_deleted)
        self.assertIsNone(annotation.deleted_at)
        self.assertEqual(Annotation.objects.filter(session=self.session).count(), 1)

    def test_mixed_create_update_delete_returns_complete_authoritative_collection(self):
        self.post([highlight("update-me"), bookmark("delete-me")])

        response = self.post(
            [
                highlight("update-me", text="Updated"),
                {"action": "delete", "client_id": "delete-me"},
                bookmark("new-bookmark", "epubcfi(/6/12)"),
            ]
        )

        rows = {row["client_id"]: row for row in response.json()["annotations"]}
        self.assertEqual(set(rows), {"update-me", "new-bookmark"})
        self.assertEqual(rows["update-me"]["body"]["text"], "Updated")
        self.assertTrue(
            Annotation.objects.get(session=self.session, client_id="delete-me").is_deleted
        )
        self.assertIsNotNone(
            Annotation.objects.get(
                session=self.session, client_id="delete-me"
            ).deleted_at
        )

    def test_invalid_operation_rejects_the_complete_batch(self):
        invalid_batches = (
            [bookmark("valid"), {"action": "unsupported", "client_id": "bad"}],
            [bookmark("valid"), {"action": "delete"}],
            [bookmark("valid"), {"action": "delete", "client_id": "   "}],
            [bookmark("valid"), {"action": "delete", "client_id": "bad", "extra": 1}],
            [bookmark("duplicate"), bookmark("duplicate")],
        )
        for operations in invalid_batches:
            with self.subTest(operations=operations):
                response = self.post(operations)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertFalse(Annotation.objects.filter(session=self.session).exists())

    def test_unsupported_cfi_rejects_the_complete_batch(self):
        response = self.post([
            bookmark("valid"),
            bookmark("invalid", "epubcfi(/6/8!/4/3:2[bad^x])"),
        ])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cfi", str(response.data))
        self.assertFalse(Annotation.objects.filter(session=self.session).exists())

    def test_range_cfi_is_stored_unchanged(self):
        cfi = "epubcfi(/6/8[spine-item]!/4/2,/1:1,/4[section]/1:4)"
        response = self.post([bookmark("range", cfi)])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Annotation.objects.get(session=self.session).cfi, cfi)
        self.assertEqual(response.data["annotations"][0]["location"]["cfi"], cfi)

    def test_kind_specific_and_bounded_body_validation_is_strict(self):
        invalid_annotations = (
            {
                **bookmark("bookmark-body")["annotation"],
                "body": {"text": "Not allowed"},
            },
            {
                "client_id": "highlight-no-body",
                "kind": "highlight",
                "location": {"cfi": "epubcfi(/6/2)"},
            },
            highlight("too-long", text="x" * (64 * 1024 + 1))["annotation"],
            {
                **bookmark("unknown-field")["annotation"],
                "unknown": True,
            },
        )
        for annotation in invalid_annotations:
            with self.subTest(annotation=annotation.get("client_id")):
                response = self.post([{"action": "upsert", "annotation": annotation}])
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Annotation.objects.filter(session=self.session).exists())

    def test_closed_access_lost_and_foreign_sessions_reject_without_mutation(self):
        ReadingSession.objects.filter(pk=self.session.pk).update(
            status=ReadingSession.STATUS_CLOSED,
            closed_at=timezone.now(),
        )
        with self.assertRaises(SessionClosedError):
            synchronize_annotations(
                user=self.user,
                session_id=self.session.pk,
                operations=[
                    {
                        "action": "delete",
                        "client_id": "missing",
                    }
                ],
            )
        closed = self.post([bookmark("closed")])

        inaccessible_book = Book.objects.create(title="Hidden")
        inaccessible = ReadingSession.objects.create(
            user=self.user,
            book=inaccessible_book,
        )
        denied = self.post([bookmark("denied")], inaccessible)
        foreign = self.post([bookmark("foreign")], self.foreign)

        self.assertEqual(closed.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(foreign.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Annotation.objects.exists())

    def test_batch_limit_and_session_scope_are_enforced(self):
        too_many = [bookmark(f"bookmark-{index}") for index in range(BATCH_ANNOTATION_OPERATION_LIMIT + 1)]
        limited = self.post(too_many)

        other_book = Book.objects.create(title="Other")
        BookGroupAssignment.objects.create(book=other_book, group=self.group)
        other_session = ReadingSession.objects.create(user=self.user, book=other_book)
        Annotation.objects.create(
            session=other_session,
            client_id="same-id",
            kind=Annotation.KIND_BOOKMARK,
            cfi="epubcfi(/6/20)",
        )
        scoped = self.post([bookmark("same-id")])

        self.assertEqual(limited.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(scoped.status_code, status.HTTP_200_OK)
        self.assertEqual(Annotation.objects.filter(client_id="same-id").count(), 2)

    def test_bearer_authentication_can_synchronize(self):
        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )

        response = APIClient().post(
            self.url(),
            {"operations": [bookmark("bearer")]},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["annotations"][0]["client_id"], "bearer")
