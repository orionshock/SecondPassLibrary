from __future__ import annotations

import hashlib

from django.core.files.base import ContentFile
from django.test import TestCase

from library.imports.normalization import normalize_identifier
from library.models import BookCatalogTag, BookIdentifier, BookSeries, CatalogTag, Series
from tests.library.helpers import LibraryCatalogApiFixtureMixin


class LibraryBookEditApiTests(LibraryCatalogApiFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        content = b"book edit contract epub"
        self.visible_one.checksum = hashlib.sha256(content).hexdigest()
        self.visible_one.file_size = len(content)
        self.visible_one.save(update_fields=["checksum", "file_size"])
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
        self.assertNotIn("source_filename", payload["file"])
        self.assertNotIn("book_file", payload["file"])
        self.assertEqual(payload["catalog_tags"][0]["name"], "Fantasy")
        self.assertEqual(payload["catalog_tags"][0]["slug"], "fantasy")

    def test_patch_omitted_catalog_tags_preserves_relationships(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"description": "Tags stay"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([tag["name"] for tag in response.json()["catalog_tags"]], ["Fantasy"])

    def test_patch_replaces_catalog_tags_and_deletes_orphan(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))
        orphan = CatalogTag.objects.create(
            name="Temporary Tag",
            normalized_name="temporary tag",
            slug="temporary-tag",
        )
        BookCatalogTag.objects.filter(book=self.visible_one).delete()
        BookCatalogTag.objects.create(book=self.visible_one, catalog_tag=orphan)

        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"catalog_tags": ["  Urban   Fantasy  ", "urban fantasy", "Mystery"]},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [tag["name"] for tag in response.json()["catalog_tags"]],
            ["Mystery", "Urban Fantasy"],
        )
        self.assertFalse(CatalogTag.objects.filter(pk=orphan.id).exists())
        self.assertEqual(CatalogTag.objects.get(normalized_name="urban fantasy").slug, "urban-fantasy")

    def test_patch_empty_catalog_tags_clears_and_deletes_orphan(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))
        orphan = CatalogTag.objects.create(
            name="Clear Me",
            normalized_name="clear me",
            slug="clear-me",
        )
        BookCatalogTag.objects.filter(book=self.visible_one).delete()
        BookCatalogTag.objects.create(book=self.visible_one, catalog_tag=orphan)

        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"catalog_tags": []},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["catalog_tags"], [])
        self.assertFalse(CatalogTag.objects.filter(pk=orphan.id).exists())

    def test_invalid_catalog_tag_rolls_back_entire_book_edit(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"description": "Must roll back tags", "catalog_tags": ["   "]},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.visible_one.refresh_from_db()
        self.assertEqual(self.visible_one.description, "dresden case file")
        self.assertTrue(BookCatalogTag.objects.filter(book=self.visible_one, catalog_tag=self.fantasy).exists())

    def test_reader_cannot_mutate_catalog_tags(self):
        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"catalog_tags": []},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(BookCatalogTag.objects.filter(book=self.visible_one, catalog_tag=self.fantasy).exists())

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
        self.assertEqual(BookIdentifier.objects.filter(book=self.visible_one).count(), 1)
        self.assertTrue(BookIdentifier.objects.filter(pk=self.identifier.id).exists())

    def test_librarian_patch_creates_and_assigns_new_series(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"series": {"name": "A Newly Entered Series"}, "series_index": "1.00"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        created = Series.objects.get(name="A Newly Entered Series")
        link = BookSeries.objects.get(book=self.visible_one)
        self.assertEqual(link.series, created)
        self.assertEqual(response.json()["series"]["id"], str(created.id))

    def test_patch_replaces_identifiers_when_supplied(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))
        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"identifiers": [{"scheme": "doi", "value": "https://doi.org/10.1000/edit"}]},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["identifiers"][0]["scheme"], "doi")
        self.assertEqual(
            response.json()["identifiers"][0]["value"],
            "https://doi.org/10.1000/edit",
        )
        self.assertFalse(BookIdentifier.objects.filter(pk=self.identifier.id).exists())
        self.assertEqual(
            BookIdentifier.objects.get(book=self.visible_one).normalized_value,
            "10.1000/edit",
        )

    def test_patch_empty_identifiers_clears_them(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"identifiers": []},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["identifiers"], [])
        self.assertFalse(BookIdentifier.objects.filter(book=self.visible_one).exists())

    def test_invalid_identifier_rolls_back_entire_book_edit(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={
                "description": "Must roll back",
                "identifiers": [{"scheme": "doi", "value": ""}],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.visible_one.refresh_from_db()
        self.assertEqual(self.visible_one.description, "dresden case file")
        self.assertTrue(BookIdentifier.objects.filter(pk=self.identifier.id).exists())

    def test_duplicate_identifiers_roll_back_entire_book_edit(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={
                "description": "Must also roll back",
                "identifiers": [
                    {"scheme": "doi", "value": "10.1000/duplicate"},
                    {"scheme": "doi", "value": "https://doi.org/10.1000/DUPLICATE"},
                ],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.visible_one.refresh_from_db()
        self.assertEqual(self.visible_one.description, "dresden case file")
        self.assertTrue(BookIdentifier.objects.filter(pk=self.identifier.id).exists())

    def test_reader_cannot_mutate_identifiers_through_book_patch(self):
        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"identifiers": []},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(BookIdentifier.objects.filter(pk=self.identifier.id).exists())
