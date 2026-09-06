from __future__ import annotations

from django.test import TestCase

from library.catalog.tag_services import resolve_catalog_tag
from library.imports.dto import ImportIdentifier, ImportTag
from library.imports.services import IMPORT_STATUS_IMPORTED, persist_imported_book
from library.models import Book, BookCatalogTag, BookIdentifier, CatalogTag
from tests.library.imports.helpers import ImportPersistenceFixtureMixin, sample_metadata


class ImportPersistenceTagsIdentifierTests(ImportPersistenceFixtureMixin, TestCase):
    def test_creates_and_reuses_catalog_tags_by_normalized_name(self):
        existing = resolve_catalog_tag("Science Fiction")

        result = persist_imported_book(
            metadata=sample_metadata(
                tags=[
                    ImportTag(
                        name="SCIENCE FICTION",
                        sort_name="SCIENCE FICTION",
                        normalized_name="science fiction",
                    ),
                    ImportTag(name="Space Opera", sort_name="Space Opera", normalized_name="space opera"),
                ]
            ),
            checksum="tags123",
        )

        tags = list(
            BookCatalogTag.objects.filter(book=result.book)
            .select_related("catalog_tag")
            .order_by("catalog_tag__normalized_name")
        )
        self.assertEqual(
            [row.catalog_tag for row in tags],
            [existing, CatalogTag.objects.get(normalized_name="space opera")],
        )

    def test_creates_normalized_identifiers(self):
        result = persist_imported_book(
            metadata=sample_metadata(
                identifiers=[
                    ImportIdentifier(
                        scheme=BookIdentifier.SCHEME_ISBN_13,
                        value="978-0-00-000001-1",
                        normalized_value="9780000000011",
                    ),
                    ImportIdentifier(
                        scheme=BookIdentifier.SCHEME_DOI,
                        value="10.1000/abc",
                        normalized_value="10.1000/abc",
                    ),
                ]
            ),
            checksum="identifiers123",
        )

        self.assertEqual(
            list(
                BookIdentifier.objects.filter(book=result.book)
                .order_by("scheme")
                .values_list("scheme", "normalized_value")
            ),
            [
                (BookIdentifier.SCHEME_DOI, "10.1000/abc"),
                (BookIdentifier.SCHEME_ISBN_13, "9780000000011"),
            ],
        )

    def test_isbn_epub_uid_and_calibre_metadata_may_be_shared_across_books(self):
        existing_book = Book.objects.create(title="Existing", checksum="existing-identifier")
        identifiers = [
            ImportIdentifier(
                scheme=BookIdentifier.SCHEME_ISBN_13,
                value="978-0-00-000001-1",
                normalized_value="9780000000011",
            ),
            ImportIdentifier(
                scheme=BookIdentifier.SCHEME_EPUB_UID,
                value="urn:uuid:shared-epub",
                normalized_value="urn:uuid:shared-epub",
            ),
            ImportIdentifier(
                scheme=BookIdentifier.SCHEME_CALIBRE,
                value="42",
                normalized_value="42",
            ),
        ]
        for identifier in identifiers:
            BookIdentifier.objects.create(
                book=existing_book,
                scheme=identifier.scheme,
                value=identifier.value,
                normalized_value=identifier.normalized_value,
            )

        result = persist_imported_book(
            metadata=sample_metadata(identifiers=identifiers),
            checksum="different-file-checksum",
        )

        self.assertEqual(result.status, IMPORT_STATUS_IMPORTED)
        self.assertNotEqual(result.book, existing_book)
        self.assertEqual(
            set(
                BookIdentifier.objects.filter(book=result.book).values_list(
                    "scheme", "normalized_value"
                )
            ),
            {(item.scheme, item.normalized_value) for item in identifiers},
        )

    def test_duplicate_identifier_metadata_within_one_import_is_collapsed(self):
        identifier = ImportIdentifier(
            scheme=BookIdentifier.SCHEME_ISBN_13,
            value="978-0-00-000001-1",
            normalized_value="9780000000011",
        )

        result = persist_imported_book(
            metadata=sample_metadata(identifiers=[identifier, identifier]),
            checksum="local-identifier-deduplication",
        )

        self.assertEqual(result.status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(BookIdentifier.objects.filter(book=result.book).count(), 1)
