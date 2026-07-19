from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]
REMOVED_LIBRARY_REWRITE = "LibraryReWrite2607"


class DocumentationReferenceTests(SimpleTestCase):
    def test_removed_library_rewrite_reference_is_absent(self):
        removed_path = (
            ROOT / "docs" / "internal" / "reference" / f"{REMOVED_LIBRARY_REWRITE}.md"
        )
        self.assertFalse(removed_path.exists())

        markdown_files = [
            ROOT / "README.md",
            *sorted((ROOT / "docs").rglob("*.md")),
        ]
        references = [
            path.relative_to(ROOT)
            for path in markdown_files
            if REMOVED_LIBRARY_REWRITE in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(references, [])

    def test_library_and_bearer_contract_terms_remain_distinct(self):
        api = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
        client = (ROOT / "docs" / "client-api-auth.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("/api/v1/library/search?q=<term>", api)
        self.assertIn("compact Catalog Tag field `tags`", api)
        self.assertIn("detail/write Catalog Tag field `catalog_tags`", api)
        self.assertIn("top-level `file_format`", api)
        self.assertIn("It does not repeat compact-row `tags`", api)
        self.assertIn(
            "annotations/batch/` accepts bearer authentication", client
        )
        self.assertIn(
            "Marginalia import/export endpoints are **session-only**", client
        )
        self.assertNotIn("BookVerse", api)
        self.assertNotIn("BookVerse", client)
