from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from reading.models import Annotation, ReadingSession
from reading.profile import (
    CURRENT_READING_PROFILE_VERSION,
    EPUB_CFI_CONFORMS_TO,
    MAX_BODY_JSON_BYTES,
    MAX_BODY_VALUE_CHARS,
    MAX_SELECTOR_VALUE_CHARS,
    MAX_TARGET_JSON_BYTES,
)
from reading.serializers import AnnotationSerializer
from tests.reading.api_test_base import ReadingAPITestBase, ReadingClientBearerAPITestBase
from tests.utils.books import create_file_backed_book
from tests.utils.responses import response_data_dict
from tests.utils.responses import response_data_list


User = get_user_model()


class ReadingAnnotationValidationAPITest(ReadingAPITestBase):
    def test_annotations_create_requires_motivation_target_body(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        create = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_HIGHLIGHTING,
                    "target": {"source": {"id": f"urn:uuid:{self.book.id}"}, "selector": {"value": "epubcfi(/6/6)"}},
                    "body": [{"type": "TextualBody", "purpose": "describing", "value": "hello"}],
                },
                format="json",
            ),
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        payload = response_data_dict(create)
        self.assertEqual(payload["motivation"], [Annotation.MOTIVATION_HIGHLIGHTING])
        self.assertIn("target", payload)
        self.assertIn("body", payload)
        self.assertEqual(payload["profile_version"], CURRENT_READING_PROFILE_VERSION)

        ann = Annotation.objects.get(pk=payload["id"])
        self.assertEqual(ann.session_id, session.id)
        self.assertEqual(ann.book_id, self.book.id)
        self.assertEqual(ann.book_file_id, self.book.file.id)
        self.assertEqual(ann.selector_kind, "epub_cfi")
        self.assertEqual(ann.selector_value, "epubcfi(/6/6)")
        self.assertEqual(ann.highlight_text, "hello")
        self.assertEqual(ann.highlight_color, "yellow")
        self.assertEqual(ann.comment_text, "")

        # Reconstructed selector should be a FragmentSelector with EPUB CFI conformsTo.
        selector = payload["target"]["selector"]
        self.assertEqual(selector["type"], "FragmentSelector")
        self.assertEqual(selector["conformsTo"], EPUB_CFI_CONFORMS_TO)
        self.assertEqual(selector["value"], "epubcfi(/6/6)")

        # Highlight color defaults to yellow when omitted.
        bodies = payload["body"]
        self.assertEqual(bodies[0]["color"], "yellow")


    def test_annotation_create_text_quote_exact_mismatch_rejected(self):
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
                                "exact": "HELLO",
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
        self.assertEqual(create.status_code, status.HTTP_400_BAD_REQUEST)


    def test_annotation_create_text_quote_prefix_len_500_accepted(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        prefix = "p" * 500
        create = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_HIGHLIGHTING,
                    "target": {
                        "selector": [
                            {"value": "epubcfi(/6/6)"},
                            {"type": "TextQuoteSelector", "exact": "hello", "prefix": prefix},
                        ]
                    },
                    "body": [
                        {"type": "TextualBody", "purpose": "describing", "value": "hello"}
                    ],
                },
                format="json",
            ),
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        ann = Annotation.objects.get(pk=response_data_dict(create)["id"])
        self.assertEqual(ann.quote_prefix, prefix)


    def test_annotation_create_text_quote_suffix_len_500_accepted(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        suffix = "s" * 500
        create = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_HIGHLIGHTING,
                    "target": {
                        "selector": [
                            {"value": "epubcfi(/6/6)"},
                            {"type": "TextQuoteSelector", "exact": "hello", "suffix": suffix},
                        ]
                    },
                    "body": [
                        {"type": "TextualBody", "purpose": "describing", "value": "hello"}
                    ],
                },
                format="json",
            ),
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        ann = Annotation.objects.get(pk=response_data_dict(create)["id"])
        self.assertEqual(ann.quote_suffix, suffix)


    def test_annotation_create_text_quote_prefix_len_501_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        prefix = "p" * 501
        create = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_HIGHLIGHTING,
                    "target": {
                        "selector": [
                            {"value": "epubcfi(/6/6)"},
                            {"type": "TextQuoteSelector", "exact": "hello", "prefix": prefix},
                        ]
                    },
                    "body": [
                        {"type": "TextualBody", "purpose": "describing", "value": "hello"}
                    ],
                },
                format="json",
            ),
        )
        self.assertEqual(create.status_code, status.HTTP_400_BAD_REQUEST)


    def test_annotation_create_text_quote_suffix_len_501_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        suffix = "s" * 501
        create = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_HIGHLIGHTING,
                    "target": {
                        "selector": [
                            {"value": "epubcfi(/6/6)"},
                            {"type": "TextQuoteSelector", "exact": "hello", "suffix": suffix},
                        ]
                    },
                    "body": [
                        {"type": "TextualBody", "purpose": "describing", "value": "hello"}
                    ],
                },
                format="json",
            ),
        )
        self.assertEqual(create.status_code, status.HTTP_400_BAD_REQUEST)


    def test_annotation_patch_invalid_color_rejected(self):
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
                            "color": "red",
                        }
                    ]
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


    def test_annotation_patch_target_change_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        ann = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            book=self.book,
            selector_value="epubcfi(/6/2)",
        )

        resp = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/annotations/{ann.id}/",
                data={"target": {"selector": {"value": "epubcfi(/6/4)"}}},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


    def test_annotation_patch_motivation_change_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        ann = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            book=self.book,
            selector_value="epubcfi(/6/2)",
        )

        resp = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/annotations/{ann.id}/",
                data={"motivation": Annotation.MOTIVATION_HIGHLIGHTING},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


    def test_annotation_patch_comment_on_bookmark_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        ann = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            anchor_kind=Annotation.ANCHOR_KIND_BOOKMARK,
            book=self.book,
            selector_value="epubcfi(/6/2)",
        )

        resp = cast(
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
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


    def test_annotation_patch_text_quote_selector_change_rejected(self):
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
            quote_suffix="-suf",
        )

        resp = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/annotations/{ann.id}/",
                data={
                    "target": {
                        "selector": [
                            {"value": "epubcfi(/6/2)"},
                            {"type": "TextQuoteSelector", "exact": "hello", "prefix": "changed"},
                        ]
                    }
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


    def test_invalid_annotation_motivation_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": "not-a-real-motivation",
                    "target": {},
                    "body": [],
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


    def test_annotation_create_rejects_unsupported_profile_version(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {"value": "/6/2"}},
                    "body": [],
                    "profile_version": "9.9.9",
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class ReadingAnnotationValidationBearerAPITest(ReadingClientBearerAPITestBase):
    def test_annotation_target_size_limit_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        big = "x" * (MAX_TARGET_JSON_BYTES + 1024)
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"source": {"id": big}},
                    "body": [],
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


    def test_annotation_body_size_limit_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        big = "x" * (MAX_BODY_JSON_BYTES + 1024)
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_COMMENTING,
                    "target": {"selector": {"value": "/6/2"}},
                    "body": [
                        {"type": "TextualBody", "purpose": "describing", "value": "sel"},
                        {"type": "TextualBody", "purpose": "commenting", "value": big},
                    ],
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


    def test_annotation_missing_selector_value_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {}},
                    "body": [],
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


    def test_annotation_serializer_representation_does_not_raise_for_unknown_selector_kind(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        ann = Annotation(
            session=session,
            book=self.book,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            selector_kind="weird_kind",
            selector_value="epubcfi(/6/2)",
        )
        payload = cast(
            dict[str, Any], AnnotationSerializer(ann, context={"request": None}).data
        )
        self.assertEqual(payload["target"]["selector"]["type"], "UnknownSelector")
        self.assertEqual(payload["target"]["selector"]["value"], "epubcfi(/6/2)")
        self.assertNotIn("conformsTo", payload["target"]["selector"])


    def test_annotation_selector_type_optional_or_fragmentselector_only(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        ok1 = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {"value": "/6/2"}},
                    "body": [],
                },
                format="json",
            ),
        )
        self.assertEqual(ok1.status_code, status.HTTP_201_CREATED)

        ok2 = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {
                        "selector": {
                            "type": "FragmentSelector",
                            "value": "/6/4",
                        }
                    },
                    "body": [],
                },
                format="json",
            ),
        )
        self.assertEqual(ok2.status_code, status.HTTP_201_CREATED)

        bad = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {
                        "selector": {
                            "type": "TextQuoteSelector",
                            "value": "/6/6",
                        }
                    },
                    "body": [],
                },
                format="json",
            ),
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)


    def test_annotation_selector_conformsto_optional_or_epub_cfi_only(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        ok1 = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {"value": "/6/2"}},
                    "body": [],
                },
                format="json",
            ),
        )
        self.assertEqual(ok1.status_code, status.HTTP_201_CREATED)

        ok2 = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {
                        "selector": {
                            "conformsTo": EPUB_CFI_CONFORMS_TO,
                            "value": "/6/4",
                        }
                    },
                    "body": [],
                },
                format="json",
            ),
        )
        self.assertEqual(ok2.status_code, status.HTTP_201_CREATED)

        bad = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {
                        "selector": {
                            "conformsTo": "https://example.invalid/conformsTo",
                            "value": "/6/6",
                        }
                    },
                    "body": [],
                },
                format="json",
            ),
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)


    def test_annotation_selector_value_length_limit_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        big = "x" * (MAX_SELECTOR_VALUE_CHARS + 1)
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {"value": big}},
                    "body": [],
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


    def test_annotation_body_value_length_limit_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        big = "x" * (MAX_BODY_VALUE_CHARS + 1)
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_COMMENTING,
                    "target": {"selector": {"value": "/6/2"}},
                    "body": [
                        {"type": "TextualBody", "purpose": "describing", "value": "sel"},
                        {"type": "TextualBody", "purpose": "commenting", "value": big},
                    ],
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


    def test_reasonably_long_body_value_under_limit_succeeds(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        # Stay under both the per-string and total JSON size limits.
        ok_len = min(MAX_BODY_VALUE_CHARS - 10, (MAX_BODY_JSON_BYTES // 2))
        ok_value = "x" * ok_len
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_COMMENTING,
                    "target": {"selector": {"value": "/6/2"}},
                    "body": [
                        {"type": "TextualBody", "purpose": "describing", "value": "sel"},
                        {"type": "TextualBody", "purpose": "commenting", "value": ok_value},
                    ],
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

class AnnotationHighlightColorTokenTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pw", email="u1@example.com")
        self.client.login(username="u1", password="pw")
        self.book = create_file_backed_book(title="B").book
        from reading.models import ReadingSession

        self.session = ReadingSession.objects.create(user=self.user, book=self.book)

    def _create(self, *, motivation: str | list[str], body: list[dict[str, Any]]):
        return cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(self.session.id),
                    "motivation": motivation,
                    "target": {"selector": {"value": "epubcfi(/6/2)"}},
                    "body": body,
                },
                format="json",
            ),
        )

    def test_highlight_defaults_missing_color_to_yellow(self):
        resp = self._create(
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            body=[{"type": "TextualBody", "purpose": "describing", "value": "hello"}],
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        payload = cast(dict[str, Any], resp.data)
        bodies = cast(list[dict[str, Any]], payload["body"])
        self.assertEqual(bodies[0]["color"], "yellow")

        ann = Annotation.objects.get(pk=payload["id"])
        self.assertEqual(ann.highlight_color, "yellow")

    def test_highlight_blank_color_defaults_to_yellow(self):
        resp = self._create(
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            body=[{"type": "TextualBody", "purpose": "describing", "value": "hello", "color": ""}],
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        payload = cast(dict[str, Any], resp.data)
        bodies = cast(list[dict[str, Any]], payload["body"])
        self.assertEqual(bodies[0]["color"], "yellow")

        ann = Annotation.objects.get(pk=payload["id"])
        self.assertEqual(ann.highlight_color, "yellow")

    def test_highlight_accepts_valid_tokens(self):
        for token in ("yellow", "green", "blue", "pink", "purple", "orange"):
            resp = self._create(
                motivation=Annotation.MOTIVATION_HIGHLIGHTING,
                body=[{"type": "TextualBody", "purpose": "describing", "value": "hello", "color": token}],
            )
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, token)
            payload = cast(dict[str, Any], resp.data)
            bodies = cast(list[dict[str, Any]], payload["body"])
            self.assertEqual(bodies[0]["color"], token)

    def test_highlight_invalid_token_rejected(self):
        resp = self._create(
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            body=[{"type": "TextualBody", "purpose": "describing", "value": "hello", "color": "red"}],
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_note_without_highlight_color_is_accepted(self):
        resp = self._create(
            motivation=Annotation.MOTIVATION_COMMENTING,
            body=[{"type": "TextualBody", "purpose": "commenting", "value": "note"}],
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bookmark_without_highlight_color_is_accepted(self):
        resp = self._create(
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            body=[],
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        payload = cast(dict[str, Any], resp.data)
        self.assertEqual(payload["body"], [])
        self.assertEqual(payload["motivation"], [Annotation.MOTIVATION_BOOKMARKING])
