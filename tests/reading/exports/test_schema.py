from __future__ import annotations

from copy import deepcopy

from jsonschema import Draft202012Validator
from rest_framework import status
from rest_framework.test import APITestCase

from tests.reading.exports.helpers import (
    AllExportFixtureMixin,
    SelectedExportFixtureMixin,
    SingleBookExportFixtureMixin,
)
from tests.reading.exports.schema_assertions import (
    load_marginalia_export_schema,
    SchemaValidationError,
)
from tests.reading.utils import IsolatedUserdataMixin
from tests.utils.responses import assert_response


class ReadingExportApiTests(
    SingleBookExportFixtureMixin, IsolatedUserdataMixin, APITestCase
):
    def setUp(self):
        self.set_up_single_book_export_world()

    def test_export_is_nested_and_omits_spl_session_and_annotation_ids(self):
        self.client.force_login(self.user)
        r = assert_response(self._post_book(sessions=[str(self.session1.id)]))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        session = r.data["books"][0]["sessions"][0]
        annotation = session["annotations"][0]
        self.assertIn("progress", session)
        self.assertIn("annotations", session)
        self.assertNotIn("id", session)
        self.assertNotIn("session", annotation)
        self.assertNotIn("id", annotation)

    def test_export_contract_key_sets(self):
        self.client.force_login(self.user)
        r = assert_response(self._post_book(sessions=[str(self.session1.id)]))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        top = r.data
        self.assertEqual(
            set(top.keys()),
            {
                "type",
                "schema_version",
                "profile",
                "generated_at",
                "generator",
                "scope",
                "books",
            },
        )
        book = top["books"][0]
        self.assertEqual(
            set(book.keys()),
            {
                "title",
                "subtitle",
                "authors",
                "series",
                "series_index",
                "language",
                "isbn",
                "epub_unique_identifier",
                "source",
                "file_hash",
                "sessions",
            },
        )
        session = book["sessions"][0]
        self.assertEqual(
            set(session.keys()),
            {
                "export_session_id",
                "name",
                "status",
                "started_at",
                "completed_at",
                "created_at",
                "updated_at",
                "notes",
                "progress",
                "annotations",
            },
        )
        self.assertEqual(
            set(session["progress"].keys()),
            {"current_location", "progression", "profile_version", "updated_at"},
        )
        self.assertEqual(
            set(session["annotations"][0].keys()),
            {"motivation", "target", "body", "is_deleted", "created_at", "updated_at"},
        )

    def test_text_quote_selector_context_exports_when_present(self):
        self.client.force_login(self.user)
        r = assert_response(self._post_book(sessions=[str(self.session1.id)]))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        selector = r.data["books"][0]["sessions"][0]["annotations"][0]["target"][
            "selector"
        ]
        self.assertIsInstance(selector, list)
        self.assertEqual(selector[0]["type"], "FragmentSelector")
        self.assertNotIn("conformsTo", selector[0])
        self.assertEqual(selector[1]["type"], "TextQuoteSelector")
        self.assertEqual(selector[1]["exact"], "selected text")
        self.assertEqual(selector[1]["prefix"], "before ")
        self.assertEqual(selector[1]["suffix"], " after")

    def test_deleted_annotations_excluded(self):
        self.client.force_login(self.user)
        r = assert_response(self._post_book(sessions=[str(self.session1.id)]))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        annotations = r.data["books"][0]["sessions"][0]["annotations"]
        self.assertEqual(len(annotations), 1)
        self.assertNotIn("deleted text", str(annotations))


class AllMarginaliaExportApiTests(
    AllExportFixtureMixin, IsolatedUserdataMixin, APITestCase
):
    def setUp(self):
        self.set_up_all_export_world()

    def test_all_export_uses_nested_shape_without_spl_session_ids(self):
        self.client.force_login(self.user)
        r = assert_response(self.client.get(self._url()))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        book = r.data["books"][0]
        session = book["sessions"][0]
        annotation = session["annotations"][0]
        self.assertIn("sessions", book)
        self.assertIn("annotations", session)
        self.assertNotIn("id", session)
        self.assertNotIn("id", annotation)
        self.assertNotIn("session", annotation)


class SelectedBookMarginaliaExportApiTests(
    SelectedExportFixtureMixin, IsolatedUserdataMixin, APITestCase
):
    def setUp(self):
        self.set_up_selected_export_world()

    def test_export_schema_rejects_local_session_and_annotation_ids(self):
        self.client.force_login(self.user)
        r = assert_response(
            self.client.post(
                self._url(),
                self._body(
                    {"book_id": str(self.book.id), "sessions": [str(self.session1.id)]}
                ),
                format="json",
            )
        )
        payload = deepcopy(r.data)
        session = payload["books"][0]["sessions"][0]
        annotation = session["annotations"][0]
        session["id"] = str(self.session1.id)
        annotation["database_id"] = "local-annotation-id"

        with self.assertRaises(SchemaValidationError):
            Draft202012Validator(load_marginalia_export_schema()).validate(payload)
