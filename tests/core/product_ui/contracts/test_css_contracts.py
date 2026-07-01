"""Tests for Product UI CSS contracts."""
from pathlib import Path

from tests.core.product_ui.helpers import ProductUiTestCase

class ProductUiCssContractsTests(ProductUiTestCase):
    """Test shared UI contracts and component helpers."""

    def test_product_ui_has_themed_controls_and_fixed_header(self):
        css = Path("web/static/web/app.css").read_text(encoding="utf-8")
        base_template = Path("web/templates/web/base.html").read_text(
            encoding="utf-8"
        )
        layout_js = Path("web/static/web/js/layout.js").read_text(
            encoding="utf-8"
        )
        main_js = Path("web/static/web/js/main.js").read_text(encoding="utf-8")

        self.assertIn("--control-bg:", css)
        self.assertIn("--control-text:", css)
        self.assertIn("--control-border:", css)
        self.assertIn("--control-disabled-bg:", css)
        self.assertIn("color-scheme: dark", css)
        self.assertIn('input:not([type="checkbox"])', css)
        self.assertIn("select,", css)
        self.assertIn("textarea", css)
        self.assertIn(":focus-visible", css)
        self.assertIn(":disabled", css)
        self.assertIn("[readonly]", css)
        self.assertIn("select option", css)
        self.assertIn('input[type="file"]::file-selector-button', css)

        self.assertIn(".topbar {", css)
        self.assertIn("position: fixed", css)
        self.assertIn("top: 0", css)
        self.assertIn("right: 0", css)
        self.assertIn("left: 0", css)
        self.assertIn("z-index: 100", css)
        self.assertIn("isolation: isolate", css)
        self.assertIn("border-bottom: 1px solid var(--border)", css)
        self.assertIn("--app-header-height:", css)
        self.assertIn("padding-top: var(--app-header-height)", css)
        self.assertIn(
            "scroll-padding-top: calc(var(--app-header-height) + 8px)",
            css,
        )
        self.assertIn("export function initAppHeaderLayout", layout_js)
        self.assertIn("new ResizeObserver(updateHeaderHeight)", layout_js)
        self.assertIn('"--app-header-height"', layout_js)
        self.assertIn("initAppHeaderLayout();", main_js)
        self.assertIn('<header class="topbar">', base_template)
        self.assertIn('<div class="container topbar__inner">', base_template)
        self.assertIn('data-nav="marginalia"', base_template)
        self.assertIn('{ key: "marginalia", prefix: "/reading/" }', layout_js)
