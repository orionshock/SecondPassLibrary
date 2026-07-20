from __future__ import annotations

from django.db.models import PROTECT
from django.test import SimpleTestCase

from library.catalog.names import normalize_catalog_entity_name
from library.models import Author, BookAuthor, BookSeries, Series


class CatalogEntityNameTests(SimpleTestCase):
    def test_normalization_is_nfkc_whitespace_collapsed_and_casefolded(self):
        self.assertEqual(normalize_catalog_entity_name("  Ａda\tLovelace  "), "ada lovelace")
        self.assertEqual(normalize_catalog_entity_name("A.B."), "a.b.")

    def test_normalized_fields_are_indexed_not_unique(self):
        for model in (Author, Series):
            field = model._meta.get_field("normalized_name")
            self.assertTrue(field.db_index)
            self.assertFalse(field.unique)

    def test_model_validation_populates_normalized_names(self):
        author = Author(name="  Ａda   Lovelace ")
        series = Series(name="  Example   SERIES ")
        author.clean()
        series.clean()
        self.assertEqual(author.normalized_name, "ada lovelace")
        self.assertEqual(series.normalized_name, "example series")

    def test_relationship_foreign_keys_use_protect(self):
        self.assertIs(BookAuthor._meta.get_field("author").remote_field.on_delete, PROTECT)
        self.assertIs(BookSeries._meta.get_field("series").remote_field.on_delete, PROTECT)
