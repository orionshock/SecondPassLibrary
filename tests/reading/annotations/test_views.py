from datetime import timedelta
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from reading.models import Annotation, ReadingSession
from reading.profile import (
    EPUB_CFI_CONFORMS_TO,
)
from tests.reading.api_test_base import ReadingAPITestBase, ReadingClientBearerAPITestBase
from tests.utils.responses import response_data_dict
from tests.utils.responses import response_data_list


User = get_user_model()


class ReadingAnnotationsAPITest(ReadingAPITestBase):
    def test_annotation_create_bookmark_outputs_motivation_array(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {"value": "epubcfi(/6/2)"}},
                    "body": [],
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        payload = response_data_dict(resp)
        self.assertEqual(payload["motivation"], [Annotation.MOTIVATION_BOOKMARKING])


    def test_annotation_create_bookmark_body_omitted_defaults_empty_list(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": ["bookmarking"],
                    "target": {"selector": {"value": "epubcfi(/6/2)"}},
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        payload = response_data_dict(resp)
        self.assertEqual(payload["motivation"], [Annotation.MOTIVATION_BOOKMARKING])
        self.assertEqual(payload["body"], [])


    def test_annotation_create_highlight_with_comment_outputs_both_motivations(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": [Annotation.MOTIVATION_HIGHLIGHTING, Annotation.MOTIVATION_COMMENTING],
                    "target": {"selector": {"value": "epubcfi(/6/2)"}},
                    "body": [
                        {"type": "TextualBody", "purpose": "describing", "value": "hello"},
                        {"type": "TextualBody", "purpose": "commenting", "value": "note"},
                    ],
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        payload = response_data_dict(resp)
        self.assertEqual(
            payload["motivation"],
            [Annotation.MOTIVATION_HIGHLIGHTING, Annotation.MOTIVATION_COMMENTING],
        )


    def test_annotation_create_with_text_quote_selector_stores_prefix_suffix_and_emits_selector_array(
        self,
    ):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        create = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_HIGHLIGHTING,
                    "target": {
                        "source": {"id": f"urn:uuid:{self.book.id}"},
                        "selector": [
                            {
                                "type": "FragmentSelector",
                                "conformsTo": EPUB_CFI_CONFORMS_TO,
                                "value": "epubcfi(/6/6)",
                            },
                            {
                                "type": "TextQuoteSelector",
                                "exact": "hello",
                                "prefix": "pre-",
                                "suffix": "-suf",
                            },
                        ],
                    },
                    "body": [
                        {
                            "type": "TextualBody",
                            "purpose": "describing",
                            "value": "hello",
                        }
                    ],
                },
                format="json",
            ),
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        payload = response_data_dict(create)

        ann = Annotation.objects.get(pk=payload["id"])
        self.assertEqual(ann.highlight_text, "hello")
        self.assertEqual(ann.quote_prefix, "pre-")
        self.assertEqual(ann.quote_suffix, "-suf")

        selector = payload["target"]["selector"]
        self.assertIsInstance(selector, list)
        self.assertEqual(selector[0]["type"], "FragmentSelector")
        self.assertEqual(selector[0]["value"], "epubcfi(/6/6)")
        self.assertEqual(selector[1]["type"], "TextQuoteSelector")
        self.assertEqual(selector[1]["exact"], "hello")
        self.assertEqual(selector[1]["prefix"], "pre-")
        self.assertEqual(selector[1]["suffix"], "-suf")


    def test_annotation_patch_comment_without_selector_succeeds(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        ann = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_COMMENTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/2)",
            highlight_text="hello",
            comment_text="old",
        )

        resp = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/annotations/{ann.id}/",
                data={
                    "body": [
                        {
                            "type": "TextualBody",
                            "purpose": "commenting",
                            "value": "new",
                        }
                    ]
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ann.refresh_from_db()
        self.assertEqual(ann.comment_text, "new")
        payload = response_data_dict(resp)
        bodies = payload.get("body") or []
        self.assertTrue(any(b.get("purpose") == "commenting" and b.get("value") == "new" for b in bodies))


    def test_annotation_patch_highlight_color_without_selector_succeeds(self):
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
        )

        resp = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/annotations/{ann.id}/",
                data={
                    "body": [
                        {
                            "type": "TextualBody",
                            "purpose": "describing",
                            "color": "blue",
                        }
                    ]
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ann.refresh_from_db()
        self.assertEqual(ann.highlight_color, "blue")
        payload = response_data_dict(resp)
        bodies = payload.get("body") or []
        describing = [b for b in bodies if b.get("purpose") == "describing"]
        self.assertTrue(describing)
        self.assertEqual(describing[0].get("color"), "blue")


    def test_annotation_patch_add_and_remove_note_updates_motivations(self):
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
            comment_text="",
        )

        add = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/annotations/{ann.id}/",
                data={
                    "body": [
                        {"type": "TextualBody", "purpose": "commenting", "value": "note"}
                    ]
                },
                format="json",
            ),
        )
        self.assertEqual(add.status_code, status.HTTP_200_OK)
        payload_add = response_data_dict(add)
        self.assertEqual(
            payload_add["motivation"],
            [Annotation.MOTIVATION_HIGHLIGHTING, Annotation.MOTIVATION_COMMENTING],
        )

        remove = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/annotations/{ann.id}/",
                data={
                    "body": [
                        {"type": "TextualBody", "purpose": "commenting", "value": ""}
                    ]
                },
                format="json",
            ),
        )
        self.assertEqual(remove.status_code, status.HTTP_200_OK)
        payload_remove = response_data_dict(remove)
        self.assertEqual(payload_remove["motivation"], [Annotation.MOTIVATION_HIGHLIGHTING])


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

        listing = cast(
            Response, self.client.get(f"/api/v1/reading/annotations/?session_id={session.id}")
        )
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        data = cast(list[dict[str, Any]], response_data_list(listing))
        ids = {row["id"] for row in data}
        self.assertIn(str(a1.id), ids)
        self.assertNotIn(str(a2.id), ids)

        listing2 = cast(
            Response,
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&include_deleted=true"
            ),
        )
        self.assertEqual(listing2.status_code, status.HTTP_200_OK)
        data2 = cast(list[dict[str, Any]], response_data_list(listing2))
        ids2 = {row["id"] for row in data2}
        self.assertIn(str(a1.id), ids2)
        self.assertIn(str(a2.id), ids2)

        get_deleted = cast(Response, self.client.get(f"/api/v1/reading/annotations/{a2.id}/"))
        self.assertEqual(get_deleted.status_code, status.HTTP_404_NOT_FOUND)
        get_deleted2 = cast(
            Response, self.client.get(f"/api/v1/reading/annotations/{a2.id}/?include_deleted=true")
        )
        self.assertEqual(get_deleted2.status_code, status.HTTP_200_OK)


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

        r1 = cast(
            Response,
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&motivation=bookmarking"
            ),
        )
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        ids1 = {row["id"] for row in cast(list[dict[str, Any]], response_data_list(r1))}
        self.assertEqual(ids1, {str(a_bookmark.id)})

        r2 = cast(
            Response,
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&motivation=highlighting"
            ),
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        ids2 = {row["id"] for row in cast(list[dict[str, Any]], response_data_list(r2))}
        self.assertEqual(ids2, {str(a_highlight.id), str(a_comment.id)})

        r3 = cast(
            Response,
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&motivation=commenting"
            ),
        )
        self.assertEqual(r3.status_code, status.HTTP_200_OK)
        ids3 = {row["id"] for row in cast(list[dict[str, Any]], response_data_list(r3))}
        self.assertEqual(ids3, {str(a_comment.id)})

        r4 = cast(
            Response,
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&motivation=highlighting&motivation=bookmarking"
            ),
        )
        self.assertEqual(r4.status_code, status.HTTP_200_OK)
        ids4 = {row["id"] for row in cast(list[dict[str, Any]], response_data_list(r4))}
        self.assertEqual(ids4, {str(a_bookmark.id), str(a_highlight.id), str(a_comment.id)})

        bad = cast(
            Response,
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&motivation=weird"
            ),
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)


    def test_annotations_list_ordering_created_and_modified(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        a1 = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            book=self.book,
            selector_value="epubcfi(/6/2)",
        )
        a2 = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            book=self.book,
            selector_value="epubcfi(/6/4)",
        )
        a3 = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            book=self.book,
            selector_value="epubcfi(/6/6)",
        )

        base = timezone.now()
        Annotation.objects.filter(pk=a1.pk).update(
            created_at=base + timedelta(seconds=1), updated_at=base + timedelta(seconds=10)
        )
        Annotation.objects.filter(pk=a2.pk).update(
            created_at=base + timedelta(seconds=2), updated_at=base + timedelta(seconds=30)
        )
        Annotation.objects.filter(pk=a3.pk).update(
            created_at=base + timedelta(seconds=3), updated_at=base + timedelta(seconds=20)
        )

        created_asc = cast(
            Response,
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&ordering=created"
            ),
        )
        self.assertEqual(created_asc.status_code, status.HTTP_200_OK)
        ids_ca = [
            row["id"] for row in cast(list[dict[str, Any]], response_data_list(created_asc))
        ]
        self.assertEqual(ids_ca, [str(a1.id), str(a2.id), str(a3.id)])

        created_desc = cast(
            Response,
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&ordering=-created"
            ),
        )
        self.assertEqual(created_desc.status_code, status.HTTP_200_OK)
        ids_cd = [
            row["id"] for row in cast(list[dict[str, Any]], response_data_list(created_desc))
        ]
        self.assertEqual(ids_cd, [str(a3.id), str(a2.id), str(a1.id)])

        mod_asc = cast(
            Response,
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&ordering=modified"
            ),
        )
        self.assertEqual(mod_asc.status_code, status.HTTP_200_OK)
        ids_ma = [
            row["id"] for row in cast(list[dict[str, Any]], response_data_list(mod_asc))
        ]
        self.assertEqual(ids_ma, [str(a1.id), str(a3.id), str(a2.id)])

        mod_desc = cast(
            Response,
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&ordering=-modified"
            ),
        )
        self.assertEqual(mod_desc.status_code, status.HTTP_200_OK)
        ids_md = [
            row["id"] for row in cast(list[dict[str, Any]], response_data_list(mod_desc))
        ]
        self.assertEqual(ids_md, [str(a2.id), str(a3.id), str(a1.id)])

        bad = cast(
            Response,
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
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"source": {"id": f"urn:uuid:{self.book.id}"}, "selector": {"value": "epubcfi(/6/2)"}},
                    "body": [],
                },
                format="json",
            ),
        )
        self.assertEqual(ann.status_code, status.HTTP_400_BAD_REQUEST)


from typing import Any, cast

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from accounts.models import UserClientSession
from reading.models import Annotation, ReadingSession
from reading.profile import (
    CURRENT_READING_PROFILE_VERSION,
)
from tests.reading.api_test_base import ReadingAPITestBase, ReadingClientBearerAPITestBase
from tests.utils.responses import response_data_dict
from tests.utils.responses import response_data_list


User = get_user_model()

class ReadingBearerAuthenticationAPITest(ReadingClientBearerAPITestBase):
    def test_bearer_annotations_are_user_scoped(self):
        session1 = ReadingSession.objects.create(user=self.user1, book=self.book)

        create = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session1.id),
                    "motivation": Annotation.MOTIVATION_HIGHLIGHTING,
                    "target": {"source": {"id": f"urn:uuid:{self.book.id}"}, "selector": {"value": "epubcfi(/6/6)"}},
                    "body": [{"type": "TextualBody", "purpose": "describing", "value": "hello"}],
                },
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

        # Cross-user detail and delete should 404.
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

        # Cross-user creation should be rejected by serializer validation (invalid session).
        bad_create = self.client.post(
            "/api/v1/reading/annotations/",
            data={
                "session": str(self.session2.id),
                "motivation": Annotation.MOTIVATION_HIGHLIGHTING,
                "target": {"source": {"id": f"urn:uuid:{self.book.id}"}, "selector": {"value": "epubcfi(/6/6)"}},
                "body": [],
            },
            format="json",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(bad_create.status_code, status.HTTP_400_BAD_REQUEST)

        # Legacy device field should be rejected as unknown.
        bad_device_field = self.client.post(
            "/api/v1/reading/annotations/",
            data={
                "session": str(session1.id),
                "device": "nope",
                "motivation": Annotation.MOTIVATION_BOOKMARKING,
                "target": {"selector": {"value": "/6/2"}},
                "body": [],
            },
            format="json",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(bad_device_field.status_code, status.HTTP_400_BAD_REQUEST)
