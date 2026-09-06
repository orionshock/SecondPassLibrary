from __future__ import annotations

from io import BytesIO
import zipfile
from unittest import TestCase

from library.imports.archives import (
    build_zip_index,
    plan_zip_import,
    resolve_zip_member_reference,
    safe_zip_member_name,
    zip_sidecar_opf_for_epub,
)
from library.imports.results import IMPORT_STATUS_FAILED, IMPORT_STATUS_SKIPPED
from tests.library.imports.helpers import zip_bytes


class ZipMemberSafetyTests(TestCase):
    def test_safe_zip_member_name_normalizes_safe_paths_and_rejects_unsafe_paths(self):
        cases = (
            ("Authors/Book/book.epub", "Authors/Book/book.epub"),
            ("Authors/./Book.epub", "Authors/Book.epub"),
            (r"dir\book.epub", "dir/book.epub"),
            ("", None),
            ("../book.epub", None),
            ("dir/../book.epub", None),
            ("/book.epub", None),
            ("\\book.epub", None),
            ("C:/books/book.epub", None),
            ("dir/book:bad.epub", None),
            ("https://example.test/book.epub", None),
            ("data:text/plain,book", None),
        )
        for candidate, expected in cases:
            with self.subTest(candidate=candidate):
                self.assertEqual(safe_zip_member_name(candidate), expected)


class ZipIndexTests(TestCase):
    def test_directory_entries_are_ignored(self):
        index = build_zip_index(_zip_infos(("dir/", b""), ("dir/book.epub", b"book")))

        self.assertEqual([member.safe_name for member in index.epub_members], ["dir/book.epub"])
        self.assertNotIn("dir/", index.members_index)

    def test_one_epub_member_becomes_one_candidate(self):
        plan = plan_zip_import(zip_bytes(("dir/book.epub", b"book")))

        self.assertEqual(len(plan.candidates), 1)
        self.assertEqual(plan.candidates[0].safe_name, "dir/book.epub")
        self.assertEqual(plan.candidates[0].source_label, "book.epub")
        self.assertEqual(plan.discovered_count, 1)

    def test_non_epub_ordinary_file_is_ignored(self):
        plan = plan_zip_import(zip_bytes(("notes.txt", b"notes")))

        self.assertEqual(plan.candidates, [])
        self.assertEqual(plan.item_results, [])
        self.assertEqual(plan.discovered_count, 0)

    def test_normalized_collisions_skip_all_colliding_entries(self):
        plan = plan_zip_import(zip_bytes(("dir/book.epub", b"a"), ("dir/./book.epub", b"b")))

        self.assertEqual(plan.candidates, [])
        self.assertEqual(plan.discovered_count, 0)
        self.assertEqual(plan.collisions, {"dir/book.epub": 2})
        self.assertEqual(plan.item_results[0].status, IMPORT_STATUS_SKIPPED)
        self.assertEqual(plan.item_results[0].source_label, "book.epub")
        self.assertNotIn("dir/./book.epub", plan.item_results[0].safe_message)

    def test_epub_opf_collision_removes_sidecar_from_association(self):
        plan = plan_zip_import(
            zip_bytes(
                ("dir/book.epub", b"book"),
                ("dir/metadata.opf", b"opf-a"),
                ("dir/./metadata.opf", b"opf-b"),
            )
        )

        self.assertEqual(len(plan.candidates), 1)
        self.assertIsNone(plan.candidates[0].sidecar_opf_name)
        self.assertEqual(plan.collisions, {"dir/metadata.opf": 2})

    def test_two_epub_collision_emits_no_candidate(self):
        plan = plan_zip_import(zip_bytes(("dir/book.epub", b"a"), ("dir/./book.epub", b"b")))

        self.assertEqual(plan.candidates, [])
        self.assertEqual(plan.collisions, {"dir/book.epub": 2})
        self.assertEqual(plan.item_results[0].status, IMPORT_STATUS_SKIPPED)

    def test_archive_with_zero_epub_candidates_is_empty_successful_plan(self):
        plan = plan_zip_import(zip_bytes(("notes.txt", b"notes"), ("dir/metadata.opf", b"opf")))

        self.assertEqual(plan.candidates, [])
        self.assertEqual(plan.item_results, [])
        self.assertEqual(plan.discovered_count, 0)


class ZipSidecarPlanningTests(TestCase):
    def test_opf_sidecar_is_associated_but_not_read(self):
        plan = plan_zip_import(zip_bytes(("dir/book.epub", b"book"), ("dir/metadata.opf", b"not xml")))

        self.assertEqual(plan.candidates[0].sidecar_opf_name, "dir/metadata.opf")

    def test_metadata_opf_same_directory_wins(self):
        index = build_zip_index(
            _zip_infos(
                ("dir/book.epub", b"book"),
                ("dir/book.opf", b"base"),
                ("dir/metadata.opf", b"metadata"),
            )
        )

        self.assertEqual(
            zip_sidecar_opf_for_epub(
                epub_member="dir/book.epub",
                opfs_by_dir=index.opfs_by_dir,
                members_index=index.members_index,
            ),
            "dir/metadata.opf",
        )

    def test_same_basename_opf_fallback(self):
        plan = plan_zip_import(zip_bytes(("dir/book.epub", b"book"), ("dir/book.opf", b"base")))

        self.assertEqual(plan.candidates[0].sidecar_opf_name, "dir/book.opf")

    def test_single_same_directory_opf_fallback(self):
        plan = plan_zip_import(zip_bytes(("dir/book.epub", b"book"), ("dir/random.opf", b"opf")))

        self.assertEqual(plan.candidates[0].sidecar_opf_name, "dir/random.opf")

    def test_ambiguous_multiple_same_directory_opfs_yields_no_sidecar(self):
        plan = plan_zip_import(
            zip_bytes(
                ("dir/book.epub", b"book"),
                ("dir/a.opf", b"a"),
                ("dir/b.opf", b"b"),
            )
        )

        self.assertIsNone(plan.candidates[0].sidecar_opf_name)


class ZipMemberReferenceTests(TestCase):
    def test_resolves_safe_asset_relative_to_opf_directory(self):
        index = build_zip_index(
            _zip_infos(
                ("author/book/metadata.opf", b"opf"),
                ("author/book/images/cover.jpg", b"cover"),
            )
        )

        member = resolve_zip_member_reference(
            base_member="author/book/metadata.opf",
            href="images/cover.jpg",
            members_index=index.members_index,
        )

        self.assertIsNotNone(member)
        self.assertEqual(member.safe_name, "author/book/images/cover.jpg")

    def test_rejects_unsafe_asset_references(self):
        index = build_zip_index(
            _zip_infos(
                ("author/book/metadata.opf", b"opf"),
                ("author/book/cover.jpg", b"cover"),
            )
        )
        unsafe_hrefs = [
            "../cover.jpg",
            "/cover.jpg",
            "C:/cover.jpg",
            "https://example.test/cover.jpg",
            "data:image/png,cover",
            r"..\cover.jpg",
        ]

        for href in unsafe_hrefs:
            with self.subTest(href=href):
                self.assertIsNone(
                    resolve_zip_member_reference(
                        base_member="author/book/metadata.opf",
                        href=href,
                        members_index=index.members_index,
                    )
                )

    def test_rejects_member_removed_by_normalized_collision_filter(self):
        index = build_zip_index(
            _zip_infos(
                ("author/book/metadata.opf", b"opf"),
                ("author/book/cover.jpg", b"first"),
                ("author/book/./cover.jpg", b"second"),
            )
        )

        self.assertIsNone(
            resolve_zip_member_reference(
                base_member="author/book/metadata.opf",
                href="cover.jpg",
                members_index=index.members_index,
            )
        )


class ZipPlannerLimitTests(TestCase):
    def test_too_many_zip_members_produces_failed_result(self):
        plan = plan_zip_import(
            zip_bytes(("a.epub", b"a"), ("b.epub", b"b")),
            max_zip_members=1,
        )

        self.assertEqual(plan.candidates, [])
        self.assertEqual(plan.item_results[0].status, IMPORT_STATUS_FAILED)
        self.assertIn("more than 1 entries", plan.item_results[0].safe_message)

    def test_oversized_epub_member_produces_failed_item(self):
        plan = plan_zip_import(
            zip_bytes(("big.epub", b"12345")),
            max_epub_member_bytes=4,
        )

        self.assertEqual(plan.candidates, [])
        self.assertEqual(plan.discovered_count, 1)
        self.assertEqual(plan.item_results[0].status, IMPORT_STATUS_FAILED)
        self.assertIn("uncompressed limit", plan.item_results[0].safe_message)

    def test_total_epub_size_limit_is_enforced(self):
        plan = plan_zip_import(
            zip_bytes(("a.epub", b"1111"), ("b.epub", b"22222")),
            max_epub_member_bytes=10,
            max_total_epub_bytes=8,
        )

        self.assertEqual([candidate.safe_name for candidate in plan.candidates], ["a.epub"])
        self.assertEqual(plan.discovered_count, 2)
        self.assertEqual(plan.item_results[0].status, IMPORT_STATUS_FAILED)
        self.assertIn("total uncompressed limit", plan.item_results[0].safe_message)

    def test_oversized_epub_member_does_not_consume_total_payload_budget(self):
        plan = plan_zip_import(
            zip_bytes(("oversized.epub", b"12345"), ("accepted.epub", b"2222")),
            max_epub_member_bytes=4,
            max_total_epub_bytes=4,
        )

        self.assertEqual([candidate.safe_name for candidate in plan.candidates], ["accepted.epub"])
        self.assertEqual(plan.discovered_count, 2)
        self.assertEqual(plan.item_results[0].status, IMPORT_STATUS_FAILED)
        self.assertEqual(plan.item_results[0].source_label, "oversized.epub")

    def test_extreme_outer_zip_compression_ratio_is_rejected_before_expansion(self):
        plan = plan_zip_import(
            zip_bytes(
                ("bomb.epub", b"x" * 10_000),
                ("ordinary.epub", b"not-compressible-enough-1234567890"),
            ),
            max_epub_compression_ratio=5,
        )

        self.assertEqual(
            [candidate.safe_name for candidate in plan.candidates],
            ["ordinary.epub"],
        )
        self.assertEqual(plan.discovered_count, 2)
        self.assertEqual(plan.item_results[0].source_label, "bomb.epub")
        self.assertIn("compression-ratio", plan.item_results[0].safe_message)

    def test_invalid_zip_produces_failed_result(self):
        plan = plan_zip_import(BytesIO(b"not a zip"))

        self.assertEqual(plan.candidates, [])
        self.assertEqual(plan.item_results[0].status, IMPORT_STATUS_FAILED)
        self.assertIn("invalid or unsupported", plan.item_results[0].safe_message)
        self.assertIn("try again", plan.item_results[0].safe_message)


def _zip_infos(*entries: tuple[str, bytes]) -> list[zipfile.ZipInfo]:
    with zipfile.ZipFile(zip_bytes(*entries), "r") as archive:
        return archive.infolist()
