from __future__ import annotations

from tempfile import TemporaryDirectory
from pathlib import Path

from django.test import SimpleTestCase

from tools.static_hygiene import (
    check_decorative_entities,
    check_line_endings,
    check_mojibake,
    check_trailing_whitespace,
    fix_line_endings,
    fix_trailing_whitespace,
)


class StaticHygieneToolTests(SimpleTestCase):
    def test_decorative_entity_scan_flags_ui_files(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "template.html"
            path.write_text("<span>A &middot; B</span>\n", encoding="utf-8")

            issues = check_decorative_entities([path])

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].line, 1)
        self.assertIn("&middot;", issues[0].message)

    def test_decorative_entity_scan_ignores_python_guardrail_files(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "test_contract.py"
            path.write_text('self.assertNotIn("&middot;", source)\n', encoding="utf-8")

            issues = check_decorative_entities([path])

        self.assertEqual(issues, [])

    def test_mojibake_scan_flags_markers(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.md"
            path.write_text("Broken: \u00c2\u00b7\n", encoding="utf-8")

            issues = check_mojibake([path])

        self.assertEqual(len(issues), 1)
        self.assertIn("mojibake", issues[0].message)

    def test_trailing_whitespace_scan_reports_file_and_line(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "style.css"
            path.write_text(".x { color: red; }  \n.ok {}\n", encoding="utf-8")

            issues = check_trailing_whitespace([path])

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].line, 1)

    def test_line_ending_scan_reports_crlf(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "script.js"
            path.write_bytes(b"const x = 1;\nconst y = 2;\r\n")

            issues = check_line_endings([path])

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].line, 2)
        self.assertIn("LF", issues[0].message)

    def test_fix_trailing_whitespace_trims_scanned_files(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "script.js"
            path.write_text("const x = 1;  \nconst y = 2;\t\n", encoding="utf-8")

            changed = fix_trailing_whitespace([path])
            text = path.read_text(encoding="utf-8")

        self.assertEqual(changed, 1)
        self.assertEqual(text, "const x = 1;\nconst y = 2;\n")

    def test_fix_line_endings_normalizes_to_lf(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "style.css"
            path.write_bytes(b".x {}\r\n.y {}\r.z {}\n")

            changed = fix_line_endings([path])
            data = path.read_bytes()

        self.assertEqual(changed, 1)
        self.assertEqual(data, b".x {}\n.y {}\n.z {}\n")
