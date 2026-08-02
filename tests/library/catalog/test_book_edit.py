from __future__ import annotations

import hashlib
from decimal import Decimal
from uuid import uuid4

from django.core.files.base import ContentFile
from django.test import TestCase

from library.imports.normalization import normalize_identifier
from library.models import (
    BookAuthor,
    BookCatalogTag,
    BookIdentifier,
    BookSeries,
    CatalogTag,
    Series,
)
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
        self.assertNotIn("tags", payload)
        self.assertNotIn("file_format", payload)

    def test_patch_rejects_unknown_and_protected_fields_without_persisting(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        random = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"title": "Must not persist", "random_field": "nope"},
            content_type="application/json",
        )
        protected_fields = {field: "nope" for field in ("groups", "file", "checksum")}
        protected = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data=protected_fields,
            content_type="application/json",
        )

        self.assertEqual(random.status_code, 400)
        self.assertEqual(random.json(), {"random_field": ["Unknown field."]})
        self.assertEqual(protected.status_code, 400)
        self.assertEqual(set(protected.json()), set(protected_fields))
        self.visible_one.refresh_from_db()
        self.assertEqual(self.visible_one.title, "Visible One")

    def test_patch_and_partial_put_write_sort_title(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        patched = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"sort_title": "One, Visible"},
            content_type="application/json",
        )
        replaced = self.client.put(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"sort_title": "Visible One"},
            content_type="application/json",
        )
        cleared = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"sort_title": ""},
            content_type="application/json",
        )

        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["sort_title"], "One, Visible")
        self.assertEqual(replaced.status_code, 200)
        self.assertEqual(replaced.json()["sort_title"], "Visible One")
        self.assertEqual(replaced.json()["title"], "Visible One")
        self.assertEqual([author["id"] for author in replaced.json()["authors"]], [str(self.beta.id)])
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.json()["sort_title"], "")

    def test_patch_deduplicates_authors_in_first_occurrence_order(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"authors": [str(self.alpha.id), str(self.beta.id), str(self.alpha.id)]},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        expected = [str(self.alpha.id), str(self.beta.id)]
        self.assertEqual([author["id"] for author in response.json()["authors"]], expected)
        self.assertEqual(
            [str(author_id) for author_id in BookAuthor.objects.filter(book=self.visible_one).order_by("position").values_list("author_id", flat=True)],
            expected,
        )
        cleared = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"authors": []},
            content_type="application/json",
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.json()["authors"], [])

    def test_invalid_author_id_rolls_back_scalar_and_relationship_changes(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"title": "Must roll back", "authors": [str(self.alpha.id), str(uuid4())]},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("authors", response.json())
        self.visible_one.refresh_from_db()
        self.assertEqual(self.visible_one.title, "Visible One")
        self.assertEqual(
            list(BookAuthor.objects.filter(book=self.visible_one).values_list("author_id", flat=True)),
            [self.beta.id],
        )

    def test_series_index_accepts_positive_two_decimal_values_and_round_trips_exactly(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        whole = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"series_index": "1"},
            content_type="application/json",
        )
        decimal = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"series_index": "1.5"},
            content_type="application/json",
        )
        exact = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"series_index": "1.25"},
            content_type="application/json",
        )

        self.assertEqual(whole.status_code, 200)
        self.assertEqual(whole.json()["series"]["series_index"], "1.00")
        self.assertEqual(decimal.status_code, 200)
        self.assertEqual(decimal.json()["series"]["series_index"], "1.50")
        self.assertEqual(exact.status_code, 200)
        self.assertEqual(exact.json()["series"]["series_index"], "1.25")
        self.assertEqual(BookSeries.objects.get(book=self.visible_one).series_index, Decimal("1.25"))

    def test_invalid_series_indexes_return_field_errors_without_partial_changes(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        for value in ("1.555", "1.230", "0", "-1.0", "not-a-number"):
            with self.subTest(value=value):
                response = self.client.patch(
                    f"/api/v1/library/books/{self.visible_one.id}/",
                    data={"title": "Must roll back", "series_index": value},
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("series_index", response.json())
                self.visible_one.refresh_from_db()
                self.assertEqual(self.visible_one.title, "Visible One")

    def test_non_null_series_index_requires_a_target_series(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"title": "Must roll back", "series": None, "series_index": "1.0"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("series_index", response.json())
        self.visible_one.refresh_from_db()
        self.assertEqual(self.visible_one.title, "Visible One")
        self.assertTrue(BookSeries.objects.filter(book=self.visible_one, series=self.first_series).exists())

    def test_null_series_and_index_clear_the_relationship(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"series": None, "series_index": None},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["series"])
        self.assertFalse(BookSeries.objects.filter(book=self.visible_one).exists())

    def test_publication_date_uses_real_calendar_validation(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        valid = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={
                "published_year": 2025,
                "published_month": 2,
                "published_day": 28,
                "published_date_precision": "day",
            },
            content_type="application/json",
        )

        self.assertEqual(valid.status_code, 200)
        self.assertEqual(valid.json()["published_day"], 28)

    def test_invalid_publication_dates_return_field_errors_without_partial_changes(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))
        cases = (
            ({"published_year": 2025, "published_month": 2, "published_day": 31, "published_date_precision": "day"}, "published_day"),
            ({"published_year": 2025, "published_month": 13, "published_day": None, "published_date_precision": "month"}, "published_month"),
            ({"published_year": None, "published_month": 2, "published_day": None, "published_date_precision": "month"}, "published_year"),
            ({"published_year": None, "published_month": None, "published_day": None, "published_date_precision": "year"}, "published_year"),
            ({"published_year": 2025, "published_month": 2, "published_day": None, "published_date_precision": "year"}, "published_month"),
        )

        for date_payload, error_field in cases:
            with self.subTest(date_payload=date_payload):
                response = self.client.patch(
                    f"/api/v1/library/books/{self.visible_one.id}/",
                    data={"title": "Must roll back", **date_payload},
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(error_field, response.json())
                self.visible_one.refresh_from_db()
                self.assertEqual(self.visible_one.title, "Visible One")

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
        self.assertNotIn("tags", response.json())
        self.assertNotIn("file_format", response.json())

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
                "sort_title": "One, Visible",
                "subtitle": "Updated subtitle",
                "description": "Updated canonical description",
                "publisher": "Updated Publisher",
                "language": "en",
                "published_year": 2024,
                "published_month": None,
                "published_day": None,
                "published_date_precision": "year",
                "authors": [str(self.alpha.id)],
                "series": str(self.second_series.id),
                "series_index": "4.5",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["sort_title"], "One, Visible")
        self.assertEqual(payload["subtitle"], "Updated subtitle")
        self.assertEqual(payload["description"], "Updated canonical description")
        self.assertEqual(payload["publisher"], "Updated Publisher")
        self.assertEqual(payload["language"], "en")
        self.assertEqual(payload["published_year"], 2024)
        self.assertEqual(payload["published_date_precision"], "year")
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
            data={"series": {"name": "A Newly Entered Series"}, "series_index": "1.0"},
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

    def test_patch_rejects_unknown_nested_identifier_fields_without_partial_changes(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={
                "title": "Must roll back",
                "identifiers": [
                    {
                        "scheme": "doi",
                        "value": "10.1000/example",
                        "random_field": "ignored",
                    }
                ],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"identifiers": [{"random_field": ["Unknown field."]}]},
        )
        self.visible_one.refresh_from_db()
        self.assertEqual(self.visible_one.title, "Visible One")
        self.assertTrue(BookIdentifier.objects.filter(pk=self.identifier.id).exists())

    def test_identifier_owned_by_another_book_rolls_back_scalar_changes(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))
        normalized = normalize_identifier(scheme="doi", value="10.1000/claimed")
        assert normalized is not None
        BookIdentifier.objects.create(
            book=self.visible_two,
            scheme=normalized.scheme,
            value=normalized.value,
            normalized_value=normalized.normalized_value,
        )

        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={
                "title": "Must roll back",
                "identifiers": [
                    {"scheme": "doi", "value": "https://doi.org/10.1000/CLAIMED"}
                ],
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"identifiers": ["An identifier already belongs to another book."]},
        )
        self.visible_one.refresh_from_db()
        self.assertEqual(self.visible_one.title, "Visible One")
        self.assertTrue(BookIdentifier.objects.filter(pk=self.identifier.id).exists())

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

    def test_patch_omitted_identifiers_preserves_them(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/books/{self.visible_one.id}/",
            data={"description": "Identifiers stay"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["identifiers"][0]["id"], str(self.identifier.id))
        self.assertTrue(BookIdentifier.objects.filter(pk=self.identifier.id).exists())

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
