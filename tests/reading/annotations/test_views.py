from datetime import timedelta
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from accounts.models import UserProfile
from library.group_services import ensure_user_public_membership
from library.models import BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from reading.models import Annotation, ReadingSession
from tests.reading.api_test_base import ReadingAPITestBase, ReadingClientBearerAPITestBase
from tests.utils.books import create_file_backed_book
from tests.utils.responses import response_data_dict, response_data_list


User = get_user_model()


def bookmark_payload(session: ReadingSession, value: str = "epubcfi(/6/2)") -> dict[str, Any]:
    return {
        "session": str(session.id),
        "kind": "bookmark",
        "selector": {"kind": "epub_cfi", "value": value},
    }


def highlight_payload(
    session: ReadingSession,
    *,
    value: str = "epubcfi(/6/2)",
    text: str = "hello",
    comment: str = "",
    color: str = "",
    quote: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "session": str(session.id),
        "kind": "highlight",
        "selector": {"kind": "epub_cfi", "value": value},
        "highlight_text": text,
    }
    if comment:
        payload["comment_text"] = comment
    if color:
        payload["highlight_color"] = color
    if quote is not None:
        payload["quote"] = quote
    return payload


class ReadingAnnotationsAPITest(ReadingAPITestBase):
    def _make_lost_access_session_with_annotation(self):
        user = User.objects.create_user(username="lostann", password="pass", email="lostann@example.com")
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])
        ensure_user_public_membership(user=user)
        group = LibraryGroup.objects.create(name="Lost Annotation Group")
        LibraryGroupMembership.objects.create(user=user, group=group)
        book = create_file_backed_book(title="Lost Annotation", assign_public=False).book
        BookGroupAssignment.objects.create(book=book, group=group)
        session = ReadingSession.objects.create(user=user, book=book)
        annotation = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=book,
            selector_value="epubcfi(/6/2)",
            highlight_text="owned",
            highlight_color="yellow",
            comment_text="old",
        )
        LibraryGroupMembership.objects.filter(user=user, group=group).delete()
        return user, session, annotation

    def test_annotation_create_bookmark_returns_spl_native_shape(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        resp = cast(
            Response,
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
        self.assertEqual(payload["selector"], {"kind": "epub_cfi", "value": "epubcfi(/6/2)"})
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

        resp = cast(
            Response,
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
        self.assertEqual(payload["selector"], {"kind": "epub_cfi", "value": "epubcfi(/6/6)"})
        self.assertEqual(payload["quote"], {"exact": "hello", "prefix": "pre-", "suffix": "-suf"})
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

        listing = cast(Response, self.client.get(f"/api/v1/reading/annotations/?session_id={session.id}"))
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        row = response_data_list(listing)[0]
        self.assertEqual(row["id"], str(ann.id))
        self.assertEqual(row["kind"], "highlight")
        self.assertNotIn("motivation", row)
        self.assertNotIn("target", row)
        self.assertNotIn("body", row)
        self.assertNotIn("profile_version", row)

        detail = cast(Response, self.client.get(f"/api/v1/reading/annotations/{ann.id}/"))
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

        resp = cast(
            Response,
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

        resp = cast(
            Response,
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
            resp = cast(
                Response,
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

    def test_annotations_list_includes_owned_annotations_after_book_access_lost(self):
        _user, session, annotation = self._make_lost_access_session_with_annotation()
        self.client.login(username="lostann", password="pass")

        resp = cast(Response, self.client.get(f"/api/v1/reading/annotations/?session_id={session.id}"))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response_data_list(resp)}
        self.assertIn(str(annotation.id), ids)

    def test_annotation_create_requires_current_book_access(self):
        _user, session, _annotation = self._make_lost_access_session_with_annotation()
        self.client.login(username="lostann", password="pass")

        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data=bookmark_payload(session, "epubcfi(/6/4)"),
                format="json",
            ),
        )

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Annotation.objects.filter(session=session).count(), 1)

    def test_annotation_patch_requires_current_book_access(self):
        _user, _session, annotation = self._make_lost_access_session_with_annotation()
        self.client.login(username="lostann", password="pass")

        resp = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/annotations/{annotation.id}/",
                data={"comment_text": "new"},
                format="json",
            ),
        )

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        annotation.refresh_from_db()
        self.assertEqual(annotation.comment_text, "old")

    def test_annotation_delete_requires_current_book_access_and_open_session(self):
        _user, session, annotation = self._make_lost_access_session_with_annotation()
        self.client.login(username="lostann", password="pass")

        no_access = cast(Response, self.client.delete(f"/api/v1/reading/annotations/{annotation.id}/"))
        self.assertEqual(no_access.status_code, status.HTTP_403_FORBIDDEN)
        annotation.refresh_from_db()
        self.assertFalse(annotation.is_deleted)

        session.status = ReadingSession.STATUS_COMPLETED
        session.is_active = False
        session.save(update_fields=["status", "is_active", "updated_at"])

        closed = cast(Response, self.client.delete(f"/api/v1/reading/annotations/{annotation.id}/"))
        self.assertEqual(closed.status_code, status.HTTP_400_BAD_REQUEST)
        annotation.refresh_from_db()
        self.assertFalse(annotation.is_deleted)

    def test_batch_create_multiple_annotations(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/batch/",
                data={
                    "session": str(session.id),
                    "annotations": [
                        {"client_id": "a", "kind": "bookmark", "selector": {"kind": "epub_cfi", "value": "/6/2"}},
                        {
                            "client_id": "b",
                            "kind": "highlight",
                            "selector": {"kind": "epub_cfi", "value": "/6/4"},
                            "highlight_text": "hello",
                        },
                    ],
                },
                format="json",
            ),
        )

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(resp)
        self.assertEqual([row["client_id"] for row in data["annotations"]], ["a", "b"])
        self.assertEqual(Annotation.objects.filter(session=session).count(), 2)

    def test_batch_create_is_all_or_nothing(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/batch/",
                data={
                    "session": str(session.id),
                    "annotations": [
                        {"kind": "bookmark", "selector": {"kind": "epub_cfi", "value": "/6/2"}},
                        {"kind": "highlight", "selector": {"kind": "epub_cfi", "value": "/6/4"}},
                    ],
                },
                format="json",
            ),
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Annotation.objects.filter(session=session).count(), 0)


class ReadingAnnotationsBearerAPITest(ReadingClientBearerAPITestBase):
    def test_soft_deleted_annotations_hidden_by_default_and_opt_in_include_deleted(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        a1 = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_COMMENTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/2)",
            highlight_text="keep",
            comment_text="keep",
        )
        a2 = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_COMMENTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/4)",
            highlight_text="delete",
            comment_text="delete",
        )

        deleted = cast(Response, self.client.delete(f"/api/v1/reading/annotations/{a2.id}/"))
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        a2.refresh_from_db()
        self.assertTrue(a2.is_deleted)

        listing = cast(Response, self.client.get(f"/api/v1/reading/annotations/?session_id={session.id}"))
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response_data_list(listing)}
        self.assertIn(str(a1.id), ids)
        self.assertNotIn(str(a2.id), ids)

        listing2 = cast(
            Response,
            self.client.get(f"/api/v1/reading/annotations/?session_id={session.id}&include_deleted=true"),
        )
        self.assertEqual(listing2.status_code, status.HTTP_200_OK)
        ids2 = {row["id"] for row in response_data_list(listing2)}
        self.assertIn(str(a1.id), ids2)
        self.assertIn(str(a2.id), ids2)

        self.assertEqual(
            self.client.get(f"/api/v1/reading/annotations/{a2.id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/reading/annotations/{a2.id}/?include_deleted=true").status_code,
            status.HTTP_200_OK,
        )

    def test_annotations_list_filters_by_motivation(self):
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
            "bookmarking": {str(a_bookmark.id)},
            "highlighting": {str(a_highlight.id), str(a_comment.id)},
            "commenting": {str(a_comment.id)},
        }
        for motivation, expected in expectations.items():
            response = cast(
                Response,
                self.client.get(f"/api/v1/reading/annotations/?session_id={session.id}&motivation={motivation}"),
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, motivation)
            self.assertEqual({row["id"] for row in response_data_list(response)}, expected)

        multi = cast(
            Response,
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&motivation=highlighting&motivation=bookmarking"
            ),
        )
        self.assertEqual(multi.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {row["id"] for row in response_data_list(multi)},
            {str(a_bookmark.id), str(a_highlight.id), str(a_comment.id)},
        )

        bad = cast(
            Response,
            self.client.get(f"/api/v1/reading/annotations/?session_id={session.id}&motivation=weird"),
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

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
            "modified": [str(annotations[0].id), str(annotations[2].id), str(annotations[1].id)],
            "-modified": [str(annotations[1].id), str(annotations[2].id), str(annotations[0].id)],
        }
        for ordering, ids in expected.items():
            response = cast(
                Response,
                self.client.get(f"/api/v1/reading/annotations/?session_id={session.id}&ordering={ordering}"),
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, ordering)
            self.assertEqual([row["id"] for row in response_data_list(response)], ids)

        bad = cast(
            Response,
            self.client.get(f"/api/v1/reading/annotations/?session_id={session.id}&ordering=weird"),
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_closed_session_rejects_progress_updates_and_annotation_create(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        session.is_active = False
        session.status = ReadingSession.STATUS_COMPLETED
        session.save(update_fields=["is_active", "status", "updated_at"])

        progress = cast(
            Response,
            self.client.put(
                f"/api/v1/reading/sessions/{session.id}/progress/",
                data={"current_location": {"cfi": "/6/2"}},
                format="json",
            ),
        )
        self.assertEqual(progress.status_code, status.HTTP_400_BAD_REQUEST)

        ann = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data=bookmark_payload(session),
                format="json",
            ),
        )
        self.assertEqual(ann.status_code, status.HTTP_400_BAD_REQUEST)


class ReadingBearerAuthenticationAPITest(ReadingClientBearerAPITestBase):
    def test_bearer_annotations_are_user_scoped(self):
        session1 = ReadingSession.objects.create(user=self.user1, book=self.book)

        create = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data=highlight_payload(session1),
                format="json",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        ann_id = response_data_dict(create)["id"]

        list_all = cast(
            Response,
            self.client.get(
                "/api/v1/reading/annotations/",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(list_all.status_code, status.HTTP_200_OK)
        ids = {a["id"] for a in response_data_list(list_all)}
        self.assertIn(ann_id, ids)
        self.assertNotIn(str(self.annotation2.id), ids)

        other_get = self.client.get(
            f"/api/v1/reading/annotations/{self.annotation2.id}/",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(other_get.status_code, status.HTTP_404_NOT_FOUND)
        other_del = self.client.delete(
            f"/api/v1/reading/annotations/{self.annotation2.id}/",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(other_del.status_code, status.HTTP_404_NOT_FOUND)

        bad_create = self.client.post(
            "/api/v1/reading/annotations/",
            data=highlight_payload(self.session2),
            format="json",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(bad_create.status_code, status.HTTP_400_BAD_REQUEST)

        bad_device_field = self.client.post(
            "/api/v1/reading/annotations/",
            data={**bookmark_payload(session1), "device": "nope"},
            format="json",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(bad_device_field.status_code, status.HTTP_400_BAD_REQUEST)
