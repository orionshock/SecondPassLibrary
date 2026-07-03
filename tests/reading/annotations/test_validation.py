from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from reading.annotation_views import BATCH_CREATE_LIMIT
from reading.models import Annotation, ReadingSession
from reading.profile import (
    MAX_BODY_VALUE_CHARS,
    MAX_SELECTOR_VALUE_CHARS,
    MAX_TEXT_QUOTE_CONTEXT_CHARS,
)
from reading.serializers import AnnotationSerializer
from tests.reading.api_test_base import ReadingAPITestBase
from tests.utils.books import create_file_backed_book
from tests.utils.responses import response_data_dict


User = get_user_model()


def bookmark_payload(session: ReadingSession, value: str = "/6/2") -> dict[str, Any]:
    return {
        "session": str(session.id),
        "kind": "bookmark",
        "selector": {"kind": "epub_cfi", "value": value},
    }


def highlight_payload(
    session: ReadingSession,
    *,
    text: str = "hello",
    value: str = "/6/2",
    color: str | None = None,
    comment: str | None = None,
    quote: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "session": str(session.id),
        "kind": "highlight",
        "selector": {"kind": "epub_cfi", "value": value},
        "highlight_text": text,
    }
    if color is not None:
        payload["highlight_color"] = color
    if comment is not None:
        payload["comment_text"] = comment
    if quote is not None:
        payload["quote"] = quote
    return payload


class ReadingAnnotationValidationAPITest(ReadingAPITestBase):
    def test_highlight_defaults_missing_or_blank_color_to_yellow(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        missing = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data=highlight_payload(session),
                format="json",
            ),
        )
        blank = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data=highlight_payload(session, value="/6/4", color=""),
                format="json",
            ),
        )

        self.assertEqual(missing.status_code, status.HTTP_201_CREATED)
        self.assertEqual(blank.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_data_dict(missing)["highlight_color"], "yellow")
        self.assertEqual(response_data_dict(blank)["highlight_color"], "yellow")

    def test_highlight_accepts_valid_color_tokens(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        for idx, token in enumerate(("yellow", "green", "blue", "pink", "purple", "orange"), start=1):
            response = cast(
                Response,
                self.client.post(
                    "/api/v1/reading/annotations/",
                    data=highlight_payload(session, value=f"/6/{idx}", color=token),
                    format="json",
                ),
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, token)
            self.assertEqual(response_data_dict(response)["highlight_color"], token)

    def test_highlight_invalid_color_rejected_on_create_and_patch(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        create = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data=highlight_payload(session, color="red"),
                format="json",
            ),
        )
        self.assertEqual(create.status_code, status.HTTP_400_BAD_REQUEST)

        ann = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/2)",
            highlight_text="hello",
            highlight_color="yellow",
        )
        for color in ("", "red"):
            patch = cast(
                Response,
                self.client.patch(
                    f"/api/v1/reading/annotations/{ann.id}/",
                    data={"highlight_color": color},
                    format="json",
                ),
            )
            self.assertEqual(patch.status_code, status.HTTP_400_BAD_REQUEST, color)

    def test_highlight_requires_highlight_text(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        response = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "kind": "highlight",
                    "selector": {"kind": "epub_cfi", "value": "/6/2"},
                },
                format="json",
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bookmark_rejects_highlight_comment_quote_and_color_payload(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        response = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    **bookmark_payload(session),
                    "highlight_text": "hello",
                    "comment_text": "note",
                    "highlight_color": "yellow",
                    "quote": {"exact": "hello"},
                },
                format="json",
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_quote_exact_must_match_highlight_text(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        response = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data=highlight_payload(session, quote={"exact": "HELLO"}),
                format="json",
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_selector_kind_and_value_validation(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        ok = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data=bookmark_payload(session, "/6/2"),
                format="json",
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_data_dict(ok)["selector"]["value"], "epubcfi(/6/2)")

        for selector in (
            {"kind": "css", "value": "/6/2"},
            {"kind": "epub_cfi"},
            {"kind": "epub_cfi", "value": ""},
            {"kind": "epub_cfi", "value": "x" * (MAX_SELECTOR_VALUE_CHARS + 1)},
        ):
            response = cast(
                Response,
                self.client.post(
                    "/api/v1/reading/annotations/",
                    data={"session": str(session.id), "kind": "bookmark", "selector": selector},
                    format="json",
                ),
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, selector)

    def test_quote_and_text_length_limits(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        cases = [
            highlight_payload(session, text="x" * (MAX_BODY_VALUE_CHARS + 1)),
            highlight_payload(session, quote={"exact": "x" * (MAX_BODY_VALUE_CHARS + 1)}),
            highlight_payload(session, quote={"prefix": "x" * (MAX_TEXT_QUOTE_CONTEXT_CHARS + 1)}),
            highlight_payload(session, quote={"suffix": "x" * (MAX_TEXT_QUOTE_CONTEXT_CHARS + 1)}),
            highlight_payload(session, comment="x" * (MAX_BODY_VALUE_CHARS + 1)),
        ]
        for payload in cases:
            response = cast(
                Response,
                self.client.post(
                    "/api/v1/reading/annotations/",
                    data=payload,
                    format="json",
                ),
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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

        payload = cast(dict[str, Any], AnnotationSerializer(ann, context={"request": None}).data)

        self.assertEqual(payload["selector"], {"kind": "weird_kind", "value": "epubcfi(/6/2)"})


class AnnotationBatchValidationAPITest(ReadingAPITestBase):
    def test_batch_rejects_too_many_annotations(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        response = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/batch/",
                data={
                    "session": str(session.id),
                    "annotations": [
                        {"kind": "bookmark", "selector": {"kind": "epub_cfi", "value": f"/6/{idx}"}}
                        for idx in range(BATCH_CREATE_LIMIT + 1)
                    ],
                },
                format="json",
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Annotation.objects.filter(session=session).count(), 0)


class AnnotationHighlightColorTokenTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pw", email="u1@example.com")
        self.client.login(username="u1", password="pw")
        self.book = create_file_backed_book(title="B").book
        self.session = ReadingSession.objects.create(user=self.user, book=self.book)

    def test_standalone_comment_is_not_supported(self):
        response = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(self.session.id),
                    "kind": "highlight",
                    "selector": {"kind": "epub_cfi", "value": "/6/2"},
                    "comment_text": "note",
                },
                format="json",
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bookmark_without_highlight_color_is_accepted(self):
        response = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data=bookmark_payload(self.session),
                format="json",
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = response_data_dict(response)
        self.assertEqual(payload["kind"], "bookmark")
        self.assertEqual(payload["highlight_color"], "")
