from __future__ import annotations

from pathlib import Path

from tests.core.product_ui.css import product_ui_css_text
from tests.core.product_ui.helpers import ProductUiTestCase


class BookDetailLayoutTests(ProductUiTestCase):
    def test_edit_action_visibility_uses_me_role_contract(self):
        template = Path("web/templates/web/library/book_detail.html").read_text(
            encoding="utf-8"
        )
        detail_js = Path("web/static/web/js/library/detail.js").read_text(encoding="utf-8")
        views = Path("web/views.py").read_text(encoding="utf-8")

        self.assertEqual(template.count(">Edit book<"), 1)
        self.assertIn('id="book-edit-link-wrap" class="is-hidden"', template)
        self.assertIn("const canManage = canManageLibrary(me)", detail_js)
        self.assertIn("if (canManage && editWrapEl && editLinkEl)", detail_js)
        self.assertIn("visible(editWrapEl, true)", detail_js)
        self.assertNotIn("can_manage_library", template)
        self.assertNotIn("can_manage_library", views)

    def test_identity_precedes_full_width_tabs_and_cover_is_display_only(self):
        template = Path("web/templates/web/library/book_detail.html").read_text(
            encoding="utf-8"
        )

        identity_at = template.index('class="book-detail__identity"')
        sections_at = template.index('class="book-detail__sections"')
        tabs_at = template.index('aria-label="Book detail tabs"')
        self.assertLess(identity_at, sections_at)
        self.assertLess(sections_at, tabs_at)
        self.assertIn('id="book-cover" class="book-detail__cover"', template)
        self.assertIn('id="book-title"', template)
        self.assertIn('id="book-meta"', template)
        self.assertIn('id="book-summary"', template)
        self.assertIn('data-tab="shelves"', template)
        self.assertIn('data-tab="groups"', template)
        self.assertIn('data-tab="metadata"', template)
        self.assertNotIn('id="book-cover-edit"', template)
        self.assertNotIn('id="book-cover-modal"', template)
        self.assertNotIn('book-edit-cover-', template)

    def test_renderer_preserves_identity_metadata_links_and_missing_cover_fallback(self):
        detail_js = Path("web/static/web/js/library/detail.js").read_text(encoding="utf-8")
        covers_js = Path("web/static/web/js/ui/covers.js").read_text(encoding="utf-8")

        for contract in (
            "book.series.series_index",
            "book.authors",
            "book.publisher",
            "book.language",
            "book.catalog_tags",
            "book.description",
            "view=series&series=",
            "view=author&author=",
        ):
            self.assertIn(contract, detail_js)
        self.assertIn('ph.textContent = "Cover"', covers_js)
        self.assertIn("el.appendChild(placeholder(titleText))", covers_js)
        self.assertNotIn("cover_editor", detail_js)
        self.assertNotIn("/cover/", detail_js)

    def test_large_cover_and_responsive_stack_are_scoped_to_book_detail(self):
        css = product_ui_css_text()

        self.assertIn(".book-detail__identity {", css)
        self.assertIn("grid-template-columns: minmax(220px, 260px) minmax(0, 1fr)", css)
        self.assertIn(".book-detail__cover {", css)
        self.assertIn("max-width: 260px", css)
        self.assertIn("box-sizing: border-box", css)
        self.assertIn("padding: 8px", css)
        self.assertIn(".book-detail__cover .book__cover-img", css)
        self.assertIn("height: auto", css)
        self.assertIn("object-fit: contain", css)
        self.assertIn(".book-detail__cover .book__cover-ph", css)
        self.assertIn("aspect-ratio: 2 / 3", css)
        self.assertIn("@media (max-width: 720px)", css)
        self.assertIn(".book-detail__identity {\n    grid-template-columns: minmax(0, 1fr)", css)
        self.assertIn("width: min(68vw, 260px)", css)
        self.assertIn("overflow-wrap: anywhere", css)
