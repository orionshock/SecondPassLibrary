from __future__ import annotations

import hashlib

from django.core.files.base import ContentFile
from django.test import TestCase

from library.imports.normalization import normalize_identifier
from library.models import BookIdentifier
from tests.library.helpers import LibraryCatalogApiFixtureMixin


class LibraryBookEditApiTests(LibraryCatalogApiFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        content = b"book edit contract epub"
        self.visible_one.checksum = hashlib.sha256(content).hexdigest()
        self.visible_one.file_size = len(content)
        self.visible_one.source_filename = "visible-one.epub"
        self.visible_one.save(update_fields=["checksum", "file_size", "source_filename"])
        self.visible_one.book_file.save(
            "visible-one.epub",
            ContentFile(content),
            save=True,
        )
        normalized = normalize_identifier(scheme="isbn_13", value="978-1-234567-89-7")
        assert normalized is not None
        self.identifier = BookIdentifier.objects.create(
            book=self.visible_one,
            scheme=normalized.scheme,
            value=normalized.value,
            normalized_value=normalized.normalized_value,
        )

    def test_detail_exposes_current_edit_contract(self):
        response = self.client.get(f"/api/v1/library/books/{self.visible_one.id}/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], str(self.visible_one.id))
        self.assertEqual(payload["description"], "dresden case file")
        self.assertEqual(payload["authors"][0]["id"], str(self.beta.id))
        self.assertEqual(payload["series"]["id"], str(self.first_series.id))
        self.assertEqual(payload["series"]["series_index"], "2.00")
        self.assertEqual(payload["identifiers"][0]["id"], str(self.identifier.id))
        self.assertEqual(payload["file"]["format"], "epub")
        self.assertEqual(payload["file"]["file_size"], len(b"book edit contract epub"))
        self.assertEqual(payload["file"]["checksum"], self.visible_one.checksum)
        self.assertEqual(payload["file"]["source_filename"], "visible-one.epub")
        self.assertNotIn("book_file", payload["file"])

    def test_librarian_level_patch_updates_description_authors_and_book_series(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={
                "description": "Updated canonical description",
                "authors": [str(self.alpha.id)],
                "series": str(self.second_series.id),
                "series_index": "4.50",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["description"], "Updated canonical description")
        self.assertEqual([author["id"] for author in payload["authors"]], [str(self.alpha.id)])
        self.assertEqual(payload["series"]["id"], str(self.second_series.id))
        self.assertEqual(payload["series"]["series_index"], "4.50")

    def test_book_scoped_identifier_crud_uses_uuid_routes_and_enforces_editor_role(self):
        url = f"/api/v1/library/books/{self.visible_one.id}/identifiers/"
        listed = self.client.get(url)
        denied = self.client.post(url, {"scheme": "doi", "value": "10.1000/reader"})

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["id"], str(self.identifier.id))
        self.assertEqual(denied.status_code, 403)

        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))
        created = self.client.post(url, {"scheme": "doi", "value": "https://doi.org/10.1000/edit"})
        self.assertEqual(created.status_code, 201)
        identifier_id = created.json()["id"]

        item_url = f"{url}{identifier_id}/"
        updated = self.client.patch(
            item_url,
            data={"scheme": "doi", "value": "10.1000/updated"},
            content_type="application/json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["value"], "10.1000/updated")
        self.assertEqual(self.client.delete(item_url).status_code, 204)
        self.assertFalse(BookIdentifier.objects.filter(pk=identifier_id).exists())
