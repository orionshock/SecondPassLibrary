from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from tests.core.product_ui.helpers import ProductUiTestCase


class CatalogEntityManagementProductUiTests(ProductUiTestCase):
    def test_owner_can_open_canonical_author_and_series_pages(self):
        self.client.force_login(self.bootstrap_owner)
        entity_id = uuid4()
        paths = [
            "/library/authors/",
            "/library/authors/new/",
            f"/library/authors/{entity_id}/",
            f"/library/authors/{entity_id}/edit/",
            "/library/series/",
            "/library/series/new/",
            f"/library/series/{entity_id}/",
            f"/library/series/{entity_id}/edit/",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_reader_cannot_open_catalog_management_pages(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/library/authors/").status_code, 403)
        self.assertEqual(self.client.get("/library/series/").status_code, 403)

    def test_forms_and_safe_delete_controls_are_present(self):
        self.client.force_login(self.bootstrap_owner)
        entity_id = uuid4()
        author = self.client.get(f"/library/authors/{entity_id}/edit/")
        series = self.client.get(f"/library/series/{entity_id}/edit/")
        for response in (author, series):
            self.assertContains(response, 'id="catalog-entity-name"')
            self.assertContains(response, 'id="catalog-entity-sort-name"')
            self.assertContains(response, 'id="catalog-entity-prose"')
            self.assertContains(response, 'id="catalog-entity-duplicate-warning"')
            self.assertContains(response, 'id="catalog-entity-delete"')
            self.assertContains(response, 'id="catalog-entity-delete-btn"')

    def test_library_axis_links_out_and_has_create_action(self):
        template = Path("web/templates/web/library/library.html").read_text(encoding="utf-8")
        source = Path("web/static/web/js/library/list.js").read_text(encoding="utf-8")
        prose = Path("web/static/web/js/library/prose.js").read_text(encoding="utf-8")
        self.assertIn('id="library-axis-create"', template)
        self.assertIn("/library/${createKind}/new/", source)
        self.assertIn('/library/${filter.kind === "author" ? "authors" : "series"}', source)
        self.assertNotIn('name="library-context-name"', prose)
        self.assertNotIn('data-action="save-library-context"', prose)

    def test_book_edit_is_assignment_focused(self):
        template = Path("web/templates/web/library/book_edit.html").read_text(encoding="utf-8")
        self.assertIn('id="book-edit-author-add-select"', template)
        self.assertIn('id="book-edit-series-select"', template)
        self.assertIn('id="book-edit-series-index"', template)
        self.assertIn('href="/library/authors/new/"', template)
        self.assertIn('href="/library/series/new/"', template)
        self.assertNotIn('id="book-edit-author-create"', template)
        self.assertNotIn('id="book-edit-series-new"', template)
