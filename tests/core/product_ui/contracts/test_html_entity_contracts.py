"""Tests for Product UI HTML entity and text guardrails."""
from pathlib import Path

from tests.core.product_ui.helpers import ProductUiTestCase

class ProductUiHtmlEntityContractsTests(ProductUiTestCase):
    """Test shared UI contracts and component helpers."""

    def test_product_ui_avoids_legacy_decorative_entities(self):
        source_paths = [
            *Path("web/templates/web").rglob("*.html"),
            *Path("web/static/web/js").rglob("*.js"),
        ]
        sources = {
            str(path): path.read_text(encoding="utf-8")
            for path in source_paths
        }
        forbidden = (
            "&middot;",
            "&#183;",
            "&larr;",
            "&rarr;",
            "&mdash;",
            "&ndash;",
            "&hellip;",
            "\u00c2\u00b7",
            "\u00b7",
            "\u2190",
            "\u2192",
            "\u2014",
            "\u2013",
        )

        for path, text in sources.items():
            for token in forbidden:
                self.assertNotIn(token, text, msg=f"{token!r} remains in {path}")

        template_text = "\n".join(
            text for path, text in sources.items() if path.endswith(".html")
        )
        self.assertNotIn('class="pill back-link"', template_text)
        self.assertNotIn("Back to Dashboard", template_text)

        css = Path("web/static/web/app.css").read_text(encoding="utf-8")
        self.assertNotIn(".back-link", css)
        self.assertIn(".meta-item + .meta-item::before", css)
        self.assertIn(".metadata-piece + .metadata-piece::before", css)
        self.assertIn(
            ".shelf-metadata-piece + .shelf-metadata-piece::before",
            css,
        )
