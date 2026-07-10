from __future__ import annotations

from decimal import Decimal
from unittest import TestCase

from library.imports.opf import parse_opf_metadata


def opf_metadata(body: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf"
         xmlns:opf="http://www.idpf.org/2007/opf"
         xmlns:dc="http://purl.org/dc/elements/1.1/">
  <metadata>
    {body}
  </metadata>
</package>
"""


class OpfImportMetadataTests(TestCase):
    def test_title_and_title_sort(self):
        metadata = parse_opf_metadata(
            opf_metadata(
                """
                <dc:title>The Left Hand of Darkness</dc:title>
                <meta name="calibre:title_sort" content="Left Hand of Darkness, The"/>
                """
            )
        )

        self.assertEqual(metadata.title, "The Left Hand of Darkness")
        self.assertEqual(metadata.sort_title, "Left Hand of Darkness, The")

    def test_author_display_and_author_sort(self):
        metadata = parse_opf_metadata(
            opf_metadata(
                """
                <dc:title>Book</dc:title>
                <dc:creator opf:file-as="Le Guin, Ursula K.">Ursula K. Le Guin</dc:creator>
                """
            )
        )

        self.assertEqual(metadata.authors[0].name, "Ursula K. Le Guin")
        self.assertEqual(metadata.authors[0].sort_name, "Le Guin, Ursula K.")
        self.assertEqual(metadata.authors[0].position, 0)

    def test_missing_author_sort_falls_back_to_display_name(self):
        metadata = parse_opf_metadata(
            opf_metadata(
                """
                <dc:title>Book</dc:title>
                <dc:creator>Octavia Butler</dc:creator>
                """
            )
        )

        self.assertEqual(metadata.authors[0].sort_name, "Octavia Butler")

    def test_series_sort_and_series_index(self):
        metadata = parse_opf_metadata(
            opf_metadata(
                """
                <dc:title>Book</dc:title>
                <meta name="calibre:series" content="Earthsea"/>
                <meta name="calibre:series_sort" content="Earthsea"/>
                <meta name="calibre:series_index" content="2.5"/>
                """
            )
        )

        self.assertIsNotNone(metadata.series)
        self.assertEqual(metadata.series.name, "Earthsea")
        self.assertEqual(metadata.series.sort_name, "Earthsea")
        self.assertEqual(metadata.series.series_index, Decimal("2.5"))

    def test_subjects_and_calibre_tags_collapse_to_one_tag_axis(self):
        metadata = parse_opf_metadata(
            opf_metadata(
                """
                <dc:title>Book</dc:title>
                <dc:subject>Science Fiction</dc:subject>
                <dc:subject> science   fiction </dc:subject>
                <meta name="calibre:tags" content="Space Opera, science fiction"/>
                """
            )
        )

        self.assertEqual(
            [(tag.name, tag.normalized_name) for tag in metadata.tags],
            [("Science Fiction", "science fiction"), ("Space Opera", "space opera")],
        )

    def test_identifiers_normalize_by_scheme_and_value(self):
        metadata = parse_opf_metadata(
            opf_metadata(
                """
                <dc:title>Book</dc:title>
                <dc:identifier opf:scheme="ISBN">978-0-00-000001-1</dc:identifier>
                <dc:identifier opf:scheme="DOI">https://doi.org/10.1000/ABC</dc:identifier>
                """
            )
        )

        self.assertEqual(
            [(identifier.scheme, identifier.normalized_value) for identifier in metadata.identifiers],
            [("isbn_13", "9780000000011"), ("doi", "10.1000/abc")],
        )

    def test_missing_sort_fields_fall_back_predictably(self):
        metadata = parse_opf_metadata(
            opf_metadata(
                """
                <dc:title>  A   Book  </dc:title>
                <dc:creator>  Jane   Writer </dc:creator>
                <meta name="calibre:series" content="  Series   Name "/>
                """
            )
        )

        self.assertEqual(metadata.sort_title, "A Book")
        self.assertEqual(metadata.authors[0].sort_name, "Jane Writer")
        self.assertEqual(metadata.series.sort_name, "Series Name")
