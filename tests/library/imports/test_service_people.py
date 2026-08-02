from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from library.imports.dto import ImportAuthor, ImportSeries
from library.imports.services import IMPORT_STATUS_CONFLICT, persist_imported_book
from library.models import Author, Book, BookAuthor, BookSeries, Series
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
        existing = Author.objects.create(
            name="Existing Author",
            sort_name="Author, Existing",
            normalized_name="existing author",
        )

        result = persist_imported_book(
            metadata=sample_metadata(
                authors=[ImportAuthor(name="existing author", sort_name="Different", position=0)]
            ),
            checksum="reuse-author",
        )

        self.assertEqual(Author.objects.count(), 1)
        self.assertEqual(BookAuthor.objects.get(book=result.book).author, existing)

    def test_existing_author_blank_sort_name_is_filled(self):
        existing = Author.objects.create(
            name="Existing Author", sort_name="", normalized_name="existing author"
        )

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
        existing = Author.objects.create(
            name="Existing Author",
            sort_name="Original Sort",
            normalized_name="existing author",
        )

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
        existing = Series.objects.create(
            name="Series Name", sort_name="", normalized_name="series name"
        )

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
        existing = Series.objects.create(
            name="Series Name",
            sort_name="Original Series Sort",
            normalized_name="series name",
        )

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

    def test_normalized_author_and_series_matches_are_reused(self):
        author = Author.objects.create(
            name="Ada Lovelace",
            sort_name="Lovelace, Ada",
            normalized_name="ada lovelace",
        )
        series = Series.objects.create(
            name="Example Series",
            sort_name="Example Series",
            normalized_name="example series",
        )

        result = persist_imported_book(
            metadata=sample_metadata(
                authors=[
                    ImportAuthor(
                        name="  Ａda\tLovelace ",
                        sort_name="Different",
                        position=0,
                    )
                ],
                series=ImportSeries(
                    name=" EXAMPLE   SERIES ",
                    sort_name="Different",
                    series_index=None,
                ),
            ),
            checksum="normalized-people",
        )

        self.assertEqual(BookAuthor.objects.get(book=result.book).author, author)
        self.assertEqual(BookSeries.objects.get(book=result.book).series, series)
        self.assertEqual(Author.objects.count(), 1)
        self.assertEqual(Series.objects.count(), 1)

    def test_ambiguous_author_match_returns_conflict_without_creating_a_book(self):
        for name in ("Shared Name", "SHARED NAME"):
            Author.objects.create(
                name=name,
                sort_name=name,
                normalized_name="shared name",
            )

        result = persist_imported_book(
            metadata=sample_metadata(
                authors=[
                    ImportAuthor(
                        name=" shared   name ",
                        sort_name="Shared Name",
                        position=0,
                    )
                ]
            ),
            checksum="ambiguous-author",
        )

        self.assertEqual(result.status, IMPORT_STATUS_CONFLICT)
        self.assertIsNone(result.book)
        self.assertFalse(Book.objects.filter(checksum="ambiguous-author").exists())
        self.assertEqual(Author.objects.count(), 2)

    def test_ambiguous_series_match_returns_conflict_without_creating_a_book(self):
        for name in ("Shared Series", "Ｓhared Series"):
            Series.objects.create(
                name=name,
                sort_name=name,
                normalized_name="shared series",
            )

        result = persist_imported_book(
            metadata=sample_metadata(
                series=ImportSeries(
                    name=" SHARED   SERIES ",
                    sort_name="Shared Series",
                    series_index=None,
                )
            ),
            checksum="ambiguous-series",
        )

        self.assertEqual(result.status, IMPORT_STATUS_CONFLICT)
        self.assertIsNone(result.book)
        self.assertFalse(Book.objects.filter(checksum="ambiguous-series").exists())
        self.assertEqual(Series.objects.count(), 2)
