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
