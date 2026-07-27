from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from reading.models import Annotation, ReadingSession
from tests.reading.annotations.helpers import bookmark_payload, highlight_payload
from tests.reading.api_test_base import ReadingAPITestBase
from tests.utils.responses import (
    assert_response,
    response_data_dict,
    response_data_list,
)


pytestmark = [pytest.mark.integration]


class ReadingAnnotationsSessionCrudTests(ReadingAPITestBase):
    def test_annotation_create_bookmark_returns_spl_native_shape(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        resp = assert_response(
            self.client.post(
                "/api/v1/reading/annotations/",
                data=bookmark_payload(session),
                format="json",
            ),
        )

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        payload = response_data_dict(resp)
        self.assertEqual(payload["kind"], "bookmark")
        self.assertEqual(payload["book"], str(self.book.id))
        self.assertEqual(
            payload["selector"], {"kind": "epub_cfi", "value": "epubcfi(/6/2)"}
        )
        self.assertEqual(payload["quote"], {})
        self.assertEqual(payload["highlight_text"], "")
        self.assertEqual(payload["highlight_color"], "")
        self.assertEqual(payload["comment_text"], "")
        self.assertFalse(payload["has_comment"])
        self.assertNotIn("motivation", payload)
        self.assertNotIn("target", payload)
        self.assertNotIn("body", payload)
        self.assertNotIn("profile_version", payload)

    def test_annotation_create_highlight_with_comment_returns_spl_native_shape(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        resp = assert_response(
            self.client.post(
                "/api/v1/reading/annotations/",
                data=highlight_payload(
                    session,
                    value="/6/6",
                    text="hello",
                    comment="note",
                    color="green",
                    quote={"exact": "hello", "prefix": "pre-", "suffix": "-suf"},
                ),
                format="json",
            ),
        )

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        payload = response_data_dict(resp)
        self.assertEqual(payload["kind"], "highlight")
        self.assertEqual(
            payload["selector"], {"kind": "epub_cfi", "value": "epubcfi(/6/6)"}
        )
        self.assertEqual(
            payload["quote"], {"exact": "hello", "prefix": "pre-", "suffix": "-suf"}
        )
        self.assertEqual(payload["highlight_text"], "hello")
        self.assertEqual(payload["highlight_color"], "green")
        self.assertEqual(payload["comment_text"], "note")
        self.assertTrue(payload["has_comment"])

        ann = Annotation.objects.get(pk=payload["id"])
        self.assertEqual(ann.quote_prefix, "pre-")
        self.assertEqual(ann.quote_suffix, "-suf")

    def test_annotation_list_detail_return_spl_native_shape(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        ann = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/2)",
            highlight_text="hello",
            highlight_color="yellow",
            comment_text="note",
        )

        listing = assert_response(
            self.client.get(f"/api/v1/reading/annotations/?session_id={session.id}")
        )
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        row = response_data_list(listing)[0]
        self.assertEqual(row["id"], str(ann.id))
        self.assertEqual(row["kind"], "highlight")
        self.assertNotIn("motivation", row)
        self.assertNotIn("target", row)
        self.assertNotIn("body", row)
        self.assertNotIn("profile_version", row)

        detail = assert_response(
            self.client.get(f"/api/v1/reading/annotations/{ann.id}/")
        )
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        payload = response_data_dict(detail)
        self.assertEqual(payload["id"], str(ann.id))
        self.assertEqual(payload["comment_text"], "note")

    def test_annotation_patch_comment_and_color_for_highlight(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        ann = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/2)",
            highlight_text="hello",
            highlight_color="yellow",
            comment_text="old",
        )

        resp = assert_response(
            self.client.patch(
                f"/api/v1/reading/annotations/{ann.id}/",
                data={"comment_text": "new", "highlight_color": "blue"},
                format="json",
            ),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ann.refresh_from_db()
        self.assertEqual(ann.comment_text, "new")
        self.assertEqual(ann.highlight_color, "blue")
        payload = response_data_dict(resp)
        self.assertEqual(payload["comment_text"], "new")
        self.assertEqual(payload["highlight_color"], "blue")
        self.assertTrue(payload["has_comment"])

    def test_annotation_patch_blank_comment_clears_note(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        ann = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/2)",
            highlight_text="hello",
            highlight_color="yellow",
            comment_text="old",
        )

        resp = assert_response(
            self.client.patch(
                f"/api/v1/reading/annotations/{ann.id}/",
                data={"comment_text": ""},
                format="json",
            ),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ann.refresh_from_db()
        self.assertEqual(ann.comment_text, "")
        self.assertFalse(response_data_dict(resp)["has_comment"])

    def test_annotation_patch_rejects_anchor_fields(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        ann = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/2)",
            highlight_text="hello",
            highlight_color="yellow",
            quote_prefix="pre-",
        )

        for field, value in (
            ("selector", {"kind": "epub_cfi", "value": "epubcfi(/6/4)"}),
            ("quote", {"exact": "hello", "prefix": "changed"}),
            ("highlight_text", "changed"),
            ("kind", "bookmark"),
            ("session", str(session.id)),
        ):
            resp = assert_response(
                self.client.patch(
                    f"/api/v1/reading/annotations/{ann.id}/",
                    data={field: value},
                    format="json",
                ),
            )
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, field)

        ann.refresh_from_db()
        self.assertEqual(ann.selector_value, "epubcfi(/6/2)")
        self.assertEqual(ann.quote_prefix, "pre-")
        self.assertEqual(ann.highlight_text, "hello")
        self.assertEqual(ann.anchor_kind, Annotation.ANCHOR_KIND_HIGHLIGHT)

    def test_patch_bookmark_rejects_comment_and_color_without_server_error(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        annotation = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            anchor_kind=Annotation.ANCHOR_KIND_BOOKMARK,
            book=self.book,
            selector_value="epubcfi(/6/2)",
        )

        for payload in ({"comment_text": "note"}, {"highlight_color": "yellow"}):
            resp = assert_response(
                self.client.patch(
                    f"/api/v1/reading/annotations/{annotation.id}/",
                    data=payload,
                    format="json",
                ),
            )
            self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, payload)

        annotation.refresh_from_db()
        self.assertEqual(annotation.comment_text, "")
        self.assertEqual(annotation.highlight_color, "")

    def test_annotations_list_filters_by_kind(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        a_bookmark = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            book=self.book,
            selector_value="epubcfi(/6/2)",
        )
        a_highlight = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/4)",
            highlight_text="hello",
            highlight_color="yellow",
        )
        a_comment = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_COMMENTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/6)",
            highlight_text="hello",
            comment_text="note",
        )

        expectations = {
            "bookmark": {str(a_bookmark.id)},
            "highlight": {str(a_highlight.id), str(a_comment.id)},
        }
        for kind, expected in expectations.items():
            response = assert_response(
                self.client.get(
                    f"/api/v1/reading/annotations/?session_id={session.id}&kind={kind}"
                ),
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, kind)
            self.assertEqual(
                {row["id"] for row in response_data_list(response)}, expected
            )

        multi = assert_response(
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&kind=highlight&kind=bookmark"
            ),
        )
        self.assertEqual(multi.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {row["id"] for row in response_data_list(multi)},
            {str(a_bookmark.id), str(a_highlight.id), str(a_comment.id)},
        )

        bad = assert_response(
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&kind=weird"
            ),
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        old_filter = assert_response(
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&motivation=highlighting"
            ),
        )
        self.assertEqual(old_filter.status_code, status.HTTP_400_BAD_REQUEST)

    def test_annotations_list_filters_by_repeated_disjoint_categories(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        bookmark = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            book=self.book,
            selector_value="epubcfi(/6/2)",
        )
        highlight = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/4)",
            highlight_text="plain highlight",
        )
        highlight_with_note = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_COMMENTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/6)",
            highlight_text="noted highlight",
            comment_text="reader note",
        )

        expectations = {
            "bookmark": {str(bookmark.id)},
            "highlight": {str(highlight.id)},
            "highlight_with_note": {str(highlight_with_note.id)},
        }
        for category, expected in expectations.items():
            response = assert_response(
                self.client.get(
                    f"/api/v1/reading/annotations/?session_id={session.id}&category={category}"
                )
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, category)
            self.assertEqual(
                {row["id"] for row in response_data_list(response)}, expected
            )

        combined = assert_response(
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}"
                "&category=bookmark&category=highlight_with_note"
            )
        )
        self.assertEqual(combined.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {row["id"] for row in response_data_list(combined)},
            {str(bookmark.id), str(highlight_with_note.id)},
        )
        self.assertNotIn(
            str(self.annotation2.id),
            {row["id"] for row in response_data_list(combined)},
        )

        invalid = assert_response(
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&category=note"
            )
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("category", response_data_dict(invalid))

    def test_annotations_list_ordering_created_and_modified(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        annotations = [
            Annotation.objects.create(
                session=session,
                motivation=Annotation.MOTIVATION_BOOKMARKING,
                book=self.book,
                selector_value=f"epubcfi(/6/{idx})",
            )
            for idx in (2, 4, 6)
        ]
        base = timezone.now()
        for idx, annotation in enumerate(annotations, start=1):
            Annotation.objects.filter(pk=annotation.pk).update(
                created_at=base + timedelta(seconds=idx),
                updated_at=base + timedelta(seconds={1: 10, 2: 30, 3: 20}[idx]),
            )

        expected = {
            "created": [str(a.id) for a in annotations],
            "-created": [str(a.id) for a in reversed(annotations)],
            "modified": [
                str(annotations[0].id),
                str(annotations[2].id),
                str(annotations[1].id),
            ],
            "-modified": [
                str(annotations[1].id),
                str(annotations[2].id),
                str(annotations[0].id),
            ],
        }
        for ordering, ids in expected.items():
            response = assert_response(
                self.client.get(
                    f"/api/v1/reading/annotations/?session_id={session.id}&ordering={ordering}"
                ),
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, ordering)
            self.assertEqual([row["id"] for row in response_data_list(response)], ids)

        bad = assert_response(
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&ordering=weird"
            ),
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_closed_session_rejects_progress_updates_and_annotation_create(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        session.is_active = False
        session.status = ReadingSession.STATUS_COMPLETED
        session.save(update_fields=["is_active", "status", "updated_at"])

        progress = assert_response(
            self.client.put(
                f"/api/v1/reading/sessions/{session.id}/progress/",
                data={"current_location": {"cfi": "/6/2"}},
                format="json",
            ),
        )
        self.assertEqual(progress.status_code, status.HTTP_400_BAD_REQUEST)

        ann = assert_response(
            self.client.post(
                "/api/v1/reading/annotations/",
                data=bookmark_payload(session),
                format="json",
            ),
        )
        self.assertEqual(ann.status_code, status.HTTP_400_BAD_REQUEST)
