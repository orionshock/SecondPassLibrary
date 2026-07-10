from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from library.imports.dto import ImportAuthor, ImportSeries
from library.imports.services import persist_imported_book
from library.models import Author, BookAuthor, BookSeries, Series
from tests.library.imports.helpers import ImportPersistenceFixtureMixin, sample_metadata


class ImportPersistencePeopleTests(ImportPersistenceFixtureMixin, TestCase):
    def test_creates_authors_and_book_author_positions(self):
        result = persist_imported_book(
            metadata=sample_metadata(
                authors=[
                    ImportAuthor(name="First Author", sort_name="Author, First", position=0),
                    ImportAuthor(name="Second Author", sort_name="Author, Second", position=1),
                ]
            ),
            checksum="authors123",
        )

        rows = list(BookAuthor.objects.filter(book=result.book).order_by("position"))
        self.assertEqual([row.author.name for row in rows], ["First Author", "Second Author"])
        self.assertEqual([row.position for row in rows], [0, 1])

    def test_reuses_existing_author_by_display_identity(self):
        existing = Author.objects.create(name="Existing Author", sort_name="Author, Existing")

        result = persist_imported_book(
            metadata=sample_metadata(
                authors=[ImportAuthor(name="existing author", sort_name="Different", position=0)]
            ),
            checksum="reuse-author",
        )

        self.assertEqual(Author.objects.count(), 1)
        self.assertEqual(BookAuthor.objects.get(book=result.book).author, existing)

    def test_existing_author_blank_sort_name_is_filled(self):
        existing = Author.objects.create(name="Existing Author", sort_name="")

        persist_imported_book(
            metadata=sample_metadata(
                authors=[
                    ImportAuthor(
                        name="existing author",
                        sort_name="Author, Existing",
                        position=0,
                    )
                ]
            ),
            checksum="fill-author-sort",
        )

        existing.refresh_from_db()
        self.assertEqual(existing.sort_name, "Author, Existing")

    def test_existing_author_nonblank_sort_name_is_preserved(self):
        existing = Author.objects.create(name="Existing Author", sort_name="Original Sort")

        persist_imported_book(
            metadata=sample_metadata(
                authors=[
                    ImportAuthor(
                        name="existing author",
                        sort_name="Different Sort",
                        position=0,
                    )
                ]
            ),
            checksum="preserve-author-sort",
        )

        existing.refresh_from_db()
        self.assertEqual(existing.sort_name, "Original Sort")

    def test_creates_series_and_book_series_index(self):
        result = persist_imported_book(
            metadata=sample_metadata(
                series=ImportSeries(
                    name="Series Name",
                    sort_name="Series Name",
                    series_index=Decimal("2.50"),
                )
            ),
            checksum="series123",
        )

        row = BookSeries.objects.get(book=result.book)
        self.assertEqual(row.series.name, "Series Name")
        self.assertEqual(row.series_index, Decimal("2.50"))

    def test_existing_series_blank_sort_name_is_filled(self):
        existing = Series.objects.create(name="Series Name", sort_name="")

        persist_imported_book(
            metadata=sample_metadata(
                series=ImportSeries(
                    name="series name",
                    sort_name="Series Sort",
                    series_index=None,
                )
            ),
            checksum="fill-series-sort",
        )

        existing.refresh_from_db()
        self.assertEqual(existing.sort_name, "Series Sort")

    def test_existing_series_nonblank_sort_name_is_preserved(self):
        existing = Series.objects.create(name="Series Name", sort_name="Original Series Sort")

        persist_imported_book(
            metadata=sample_metadata(
                series=ImportSeries(
                    name="series name",
                    sort_name="Different Sort",
                    series_index=None,
                )
            ),
            checksum="preserve-series-sort",
        )

        existing.refresh_from_db()
        self.assertEqual(existing.sort_name, "Original Series Sort")
