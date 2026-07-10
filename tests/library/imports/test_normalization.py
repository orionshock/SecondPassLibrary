from __future__ import annotations

from unittest import TestCase

from library.imports.normalization import (
    DATE_PRECISION_DAY,
    DATE_PRECISION_MONTH,
    DATE_PRECISION_YEAR,
    build_import_tags,
    normalize_identifier,
    parse_partial_date,
)


class ImportNormalizationTests(TestCase):
    def test_duplicate_tag_labels_collapse_by_normalized_name(self):
        tags = build_import_tags(["Fantasy", " fantasy ", "FANTASY", "Urban Fantasy"])

        self.assertEqual(
            [(tag.name, tag.normalized_name) for tag in tags],
            [("Fantasy", "fantasy"), ("Urban Fantasy", "urban fantasy")],
        )

    def test_identifier_normalization_is_scheme_aware(self):
        isbn = normalize_identifier(scheme="ISBN-10", value="0-123456-47-9")
        asin = normalize_identifier(scheme="asin", value=" b00 test ")
        unknown = normalize_identifier(scheme="vendor", value="  Vendor  ID ")

        self.assertEqual((isbn.scheme, isbn.normalized_value), ("isbn_10", "0123456479"))
        self.assertEqual((asin.scheme, asin.normalized_value), ("asin", "B00TEST"))
        self.assertEqual((unknown.scheme, unknown.normalized_value), ("vendor", "vendor id"))

    def test_partial_date_year_only(self):
        self.assertEqual(parse_partial_date("1999"), (1999, None, None, DATE_PRECISION_YEAR))

    def test_partial_date_year_month(self):
        self.assertEqual(parse_partial_date("1999-07"), (1999, 7, None, DATE_PRECISION_MONTH))

    def test_partial_date_full_date(self):
        self.assertEqual(parse_partial_date("1999-07-31"), (1999, 7, 31, DATE_PRECISION_DAY))

    def test_invalid_date_does_not_fake_parts(self):
        self.assertEqual(parse_partial_date("1999-99"), (None, None, None, ""))
        self.assertEqual(parse_partial_date("1999-02-31"), (None, None, None, ""))
        self.assertEqual(parse_partial_date("not a date"), (None, None, None, ""))
