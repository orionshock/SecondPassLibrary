from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from reading.models import Annotation
from tests.utils.books import create_file_backed_book


User = get_user_model()


class AnnotationHighlightColorTokenTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pw", email="u1@example.com")
        self.client.login(username="u1", password="pw")
        self.book = create_file_backed_book(title="B").book
        from reading.models import ReadingSession

        self.session = ReadingSession.objects.create(user=self.user, book=self.book)

    def _create(self, *, motivation: str, body: list[dict[str, Any]]):
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
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        payload = cast(dict[str, Any], resp.data)
        bodies = cast(list[dict[str, Any]], payload["body"])
        self.assertEqual(len(bodies), 1)
        self.assertNotIn("color", bodies[0])

        ann = Annotation.objects.get(pk=payload["id"])
        self.assertEqual(ann.highlight_color, "")

    def test_bookmark_without_highlight_color_is_accepted(self):
        resp = self._create(
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            body=[],
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        payload = cast(dict[str, Any], resp.data)
        self.assertEqual(payload["body"], [])
