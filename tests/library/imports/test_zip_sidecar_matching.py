from __future__ import annotations

from django.test import TestCase

from library.imports.batches import import_zip_file
from library.imports.results import IMPORT_STATUS_IMPORTED, IMPORT_STATUS_SKIPPED
from tests.library.imports.helpers import metadata_xml, minimal_epub_bytes, sidecar_opf_xml, zip_bytes
from tests.testenv.filesystem import IsolatedMediaRootMixin


class ZipSidecarMatchingTests(IsolatedMediaRootMixin, TestCase):
    def test_metadata_opf_sidecar_overrides_epub_metadata(self):
        result = import_zip_file(
            zip_bytes(
                ("dir/book.epub", minimal_epub_bytes(metadata_xml=metadata_xml("EPUB Title"))),
                ("dir/metadata.opf", sidecar_opf_xml("Sidecar Title").encode()),
            ),
            source_filename="sidecar.zip",
        )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(result.items[0].book.title, "Sidecar Title")

    def test_same_basename_sidecar_fallback_overrides_epub_metadata(self):
        result = import_zip_file(
            zip_bytes(
                ("dir/book.epub", minimal_epub_bytes(metadata_xml=metadata_xml("EPUB Title"))),
                ("dir/book.opf", sidecar_opf_xml("Basename Sidecar").encode()),
            ),
            source_filename="sidecar.zip",
        )

        self.assertEqual(result.items[0].book.title, "Basename Sidecar")

    def test_single_same_directory_sidecar_fallback_overrides_epub_metadata(self):
        result = import_zip_file(
            zip_bytes(
                ("dir/book.epub", minimal_epub_bytes(metadata_xml=metadata_xml("EPUB Title"))),
                ("dir/random.opf", sidecar_opf_xml("Single Sidecar").encode()),
            ),
            source_filename="sidecar.zip",
        )

        self.assertEqual(result.items[0].book.title, "Single Sidecar")

    def test_ambiguous_sidecars_are_ignored(self):
        result = import_zip_file(
            zip_bytes(
                ("dir/book.epub", minimal_epub_bytes(metadata_xml=metadata_xml("EPUB Title"))),
                ("dir/a.opf", sidecar_opf_xml("A Sidecar").encode()),
                ("dir/b.opf", sidecar_opf_xml("B Sidecar").encode()),
            ),
            source_filename="sidecar.zip",
        )

        self.assertEqual(result.items[0].book.title, "EPUB Title")

    def test_sidecar_is_not_applied_when_planner_does_not_associate_one(self):
        result = import_zip_file(
            zip_bytes(
                ("books/book.epub", minimal_epub_bytes(metadata_xml=metadata_xml("EPUB Title"))),
                ("metadata.opf", sidecar_opf_xml("Wrong Directory").encode()),
            ),
            source_filename="unmatched-sidecar.zip",
        )

        self.assertEqual(result.items[0].book.title, "EPUB Title")

    def test_sidecar_collision_removes_sidecar_association(self):
        result = import_zip_file(
            zip_bytes(
                ("dir/book.epub", minimal_epub_bytes(metadata_xml=metadata_xml("EPUB Title"))),
                ("dir/metadata.opf", sidecar_opf_xml("Sidecar A").encode()),
                ("dir/./metadata.opf", sidecar_opf_xml("Sidecar B").encode()),
            ),
            source_filename="sidecar-collision.zip",
        )

        self.assertEqual(result.items[0].status, IMPORT_STATUS_SKIPPED)
        self.assertEqual(result.items[1].status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(result.items[1].book.title, "EPUB Title")
