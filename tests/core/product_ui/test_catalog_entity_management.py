from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from tests.core.product_ui.helpers import ProductUiTestCase


class CatalogEntityManagementProductUiTests(ProductUiTestCase):
    def test_dedicated_list_and_detail_routes_redirect_to_library_axes(self):
        self.client.force_login(self.bootstrap_owner)
        entity_id = uuid4()
        redirects = {
            "/library/authors/": "/library/?view=authors",
            f"/library/authors/{entity_id}/": f"/library/?view=author&author={entity_id}",
            "/library/series/": "/library/?view=series",
            f"/library/series/{entity_id}/": f"/library/?view=series&series={entity_id}",
        }
        for path, target in redirects.items():
            with self.subTest(path=path):
                self.assertRedirects(self.client.get(path), target, fetch_redirect_response=False)

    def test_owner_can_open_new_and_edit_lifecycle_pages(self):
        self.client.force_login(self.bootstrap_owner)
        entity_id = uuid4()
        for path in (
            "/library/authors/new/",
            f"/library/authors/{entity_id}/edit/",
            "/library/series/new/",
            f"/library/series/{entity_id}/edit/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_reader_cannot_open_catalog_management_pages(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/library/authors/new/").status_code, 403)
        self.assertEqual(self.client.get("/library/series/new/").status_code, 403)

    def test_edit_forms_are_bounded_with_actions_and_delete_before_books(self):
        self.client.force_login(self.bootstrap_owner)
        entity_id = uuid4()
        author = self.client.get(f"/library/authors/{entity_id}/edit/")
        series = self.client.get(f"/library/series/{entity_id}/edit/")
        for response in (author, series):
            self.assertContains(response, 'id="catalog-entity-name"')
            self.assertContains(response, 'id="catalog-entity-sort-name"')
            self.assertContains(response, 'id="catalog-entity-prose"')
            self.assertContains(response, 'id="catalog-entity-duplicate-warning"')
            self.assertContains(response, 'class="catalog-entity-form-panel"')
            self.assertContains(response, 'class="form-actions catalog-entity-form__actions"')
            self.assertContains(response, 'id="catalog-entity-delete"')
            self.assertContains(response, 'class="card danger-zone catalog-entity-delete"')
            self.assertContains(response, 'class="danger-zone__summary"')
            self.assertContains(response, 'id="catalog-entity-delete-form"')
            self.assertContains(response, 'id="catalog-entity-delete-confirm"')
            self.assertContains(response, 'id="catalog-entity-delete-btn"')
            self.assertContains(response, 'id="catalog-entity-delete-btn" class="button button--danger" type="submit" disabled')
            self.assertContains(response, 'class="catalog-entity-book-grid"')
            self.assertLess(
                response.content.index(b'id="catalog-entity-delete"'),
                response.content.index(b'id="catalog-entity-attached-heading"'),
            )

    def test_new_forms_omit_delete_and_attached_books(self):
        self.client.force_login(self.bootstrap_owner)
        for path in ("/library/authors/new/", "/library/series/new/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertContains(response, 'class="catalog-entity-form-panel"')
                self.assertNotContains(response, 'id="catalog-entity-delete"')
                self.assertNotContains(response, 'id="catalog-entity-attached-books"')

    def test_library_axis_links_out_and_has_create_action(self):
        template = Path("web/templates/web/library/library.html").read_text(encoding="utf-8")
        source = Path("web/static/web/js/library/list.js").read_text(encoding="utf-8")
        prose = Path("web/static/web/js/library/prose.js").read_text(encoding="utf-8")
        self.assertIn('id="library-axis-create"', template)
        self.assertIn("/library/${createKind}/new/", source)
        self.assertIn('/library/${filter.kind === "author" ? "authors" : "series"}', source)
        self.assertNotIn('name="library-context-name"', prose)
        self.assertNotIn('data-action="save-library-context"', prose)

        search_start = template.index('id="library-search"')
        axis_start = template.index('class="library-axis-row"')
        create_start = template.index('id="library-axis-create"')
        self.assertLess(search_start, axis_start)
        self.assertLess(axis_start, create_start)
        header = template[template.index('class="page-header"'):axis_start]
        axis_row = template[axis_start:template.index('class="library-browse-layout"')]
        self.assertIn('class="search__input"', header)
        self.assertIn('type="submit">Search</button>', header)
        self.assertNotIn('id="library-axis-create"', header)
        self.assertIn('aria-label="Library browse views"', axis_row)
        self.assertIn('id="library-axis-create"', axis_row)
        self.assertIn('!allowContextEdit || !createKind', source)

    def test_delete_requires_exact_name_and_keeps_browser_confirmation(self):
        source = Path("web/static/web/js/catalog_entities/main.js").read_text(encoding="utf-8")
        self.assertIn("deleteConfirm.value !== entityName", source)
        self.assertIn("attachedCount > 0", source)
        self.assertIn("deleteConfirm.disabled = attachedCount > 0", source)
        self.assertIn("window.confirm", source)
        self.assertLess(source.index("window.confirm"), source.index('method: "DELETE"'))

    def test_attached_books_use_compact_cover_previews(self):
        source = Path("web/static/web/js/catalog_entities/main.js").read_text(encoding="utf-8")
        self.assertIn('row.className = "catalog-entity-book-preview"', source)
        self.assertIn('cover.className = "catalog-entity-book-preview__cover"', source)
        self.assertNotIn('row.className = "catalog-management-row"', source)

    def test_book_edit_is_assignment_focused(self):
        template = Path("web/templates/web/library/book_edit.html").read_text(encoding="utf-8")
        self.assertIn('id="book-edit-author-add-select"', template)
        self.assertIn('id="book-edit-series-select"', template)
        self.assertIn('id="book-edit-series-index"', template)
        self.assertIn('href="{{ product_ui_prefix }}/library/authors/new/"', template)
        self.assertIn('href="{{ product_ui_prefix }}/library/series/new/"', template)
        self.assertNotIn('id="book-edit-author-create"', template)
        self.assertNotIn('id="book-edit-series-new"', template)
