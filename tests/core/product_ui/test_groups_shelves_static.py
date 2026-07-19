"""Tests for groups and shelves product UI pages."""
from pathlib import Path
from uuid import uuid4

from core import server_settings
from tests.core.product_ui.helpers import ProductUiTestCase


class ProductUiGroupsShelvesTests(ProductUiTestCase):
    """Test groups and shelves list, detail, new, and edit pages."""

    def test_unauthenticated_groups_redirects_to_login(self):
        response = self.client.get("/groups/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/groups/")

    def test_authenticated_groups_returns_404_when_advanced_groups_disabled(self):
        self.client.force_login(self.user)
        group_id = uuid4()
        for path in (
            "/groups/",
            "/groups/new/",
            f"/groups/{group_id}/",
            f"/groups/{group_id}/edit/",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)

    def test_authenticated_groups_returns_200_and_has_containers_when_enabled(self):
        server_settings.enable_advanced_library_groups()
        self.client.force_login(self.user)
        response = self.client.get("/groups/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="groups-status"')
        self.assertContains(response, 'id="groups-results"')
        self.assertContains(response, 'id="groups-prev"')
        self.assertContains(response, 'id="groups-next"')

    def test_unauthenticated_group_detail_redirects_to_login(self):
        group_id = uuid4()
        response = self.client.get(f"/groups/{group_id}/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"], f"/api-auth/login/?next=/groups/{group_id}/"
        )

    def test_unauthenticated_group_new_redirects_to_login(self):
        response = self.client.get("/groups/new/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/groups/new/")

    def test_authenticated_group_new_returns_200_and_has_form(self):
        server_settings.enable_advanced_library_groups()
        self.client.force_login(self.user)
        response = self.client.get("/groups/new/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-page="group-new"')
        self.assertContains(response, 'id="group-new-form"')
        self.assertContains(response, "<title>New Group -")
        self.assertContains(response, '<h1 class="page-title">New Group</h1>')
        self.assertContains(response, 'aria-current="page">New Group</li>')
        self.assertNotContains(response, "Owner and Manager only.")
        self.assertContains(response, 'id="group-new-root" class="group-new-root is-hidden"')
        self.assertNotContains(response, 'id="group-new-root" class="card')
        self.assertContains(response, 'class="form group-new-form"')
        self.assertContains(response, 'class="group-new-field"', count=2)
        self.assertContains(response, 'id="group-new-save"')
        self.assertContains(response, 'href="/groups/">Cancel</a>')

        html = response.content.decode("utf-8")
        form = html.split('id="group-new-form"', 1)[1].split("</form>", 1)[0]
        self.assertNotIn('class="kv"', form)
        self.assertLess(form.index('for="group-new-name"'), form.index('id="group-new-name"'))
        self.assertLess(
            form.index('for="group-new-description"'),
            form.index('id="group-new-description"'),
        )
        self.assertIn("group-new-actions", form)

    def test_authenticated_group_detail_returns_200_and_has_container(self):
        server_settings.enable_advanced_library_groups()
        self.client.force_login(self.user)
        group_id = uuid4()
        response = self.client.get(f"/groups/{group_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="group-view-root"')
        self.assertContains(response, f'data-group-id="{group_id}"')
        self.assertContains(response, 'id="group-view-books-results"')
        self.assertContains(response, 'aria-label="Group books pagination"')
        self.assertContains(response, 'id="group-view-members-results"')
        self.assertContains(response, 'id="group-view-shelves-results"')
        html = response.content.decode("utf-8")
        root_start = html.index('id="group-view-root"')
        tabs_start = html.index('aria-label="Group view tabs"', root_start)
        panel_start = html.index('id="tab-books" class="tab-panel"', root_start)
        self.assertLess(tabs_start, panel_start)
        self.assertNotIn('id="group-view-root" class="card', html)
        self.assertNotIn('id="tab-books" class="card', html)
        self.assertNotIn('id="tab-members" class="card', html)
        self.assertNotIn('id="tab-shelves" class="card', html)
        for tab in ("books", "members", "shelves"):
            self.assertContains(response, f'id="group-view-{tab}-prev-top"')
            self.assertContains(response, f'id="group-view-{tab}-next-top"')
            self.assertContains(response, f'id="group-view-{tab}-prev"')
            self.assertContains(response, f'id="group-view-{tab}-next"')
            self.assertContains(response, f'id="group-view-{tab}-page-size-top"')
            self.assertContains(response, f'id="group-view-{tab}-page-size"')
        self.assertNotIn(">Details</h2>", html)
        self.assertNotIn(">Books</h2>", html)
        self.assertNotIn(">Members</h2>", html)
        self.assertNotIn(">Shelves</h2>", html)

    def test_authenticated_group_detail_malformed_id_returns_404(self):
        self.client.force_login(self.user)

        response = self.client.get("/groups/not-a-uuid/", follow=False)

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_group_edit_redirects_to_login(self):
        group_id = uuid4()
        response = self.client.get(f"/groups/{group_id}/edit/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"], f"/api-auth/login/?next=/groups/{group_id}/edit/"
        )

    def test_authenticated_group_edit_returns_200_and_has_container(self):
        server_settings.enable_advanced_library_groups()
        self.client.force_login(self.user)
        group_id = uuid4()
        response = self.client.get(f"/groups/{group_id}/edit/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="group-edit-root"')
        self.assertContains(response, f'data-group-id="{group_id}"')
        self.assertContains(response, 'data-tab="details"')
        self.assertContains(response, 'data-tab="books"')
        self.assertContains(response, 'data-tab="add-books"')
        self.assertContains(response, 'data-tab="members"')
        self.assertContains(response, 'data-tab="shelves"')
        self.assertContains(response, 'id="group-edit-book-search-form"')
        self.assertContains(response, 'id="group-edit-book-search-results"')
        self.assertContains(response, 'aria-label="Assigned books top pagination"')
        self.assertContains(response, 'aria-label="Assigned books bottom pagination"')
        self.assertNotContains(response, "Debug: add book by UUID")
        self.assertNotContains(response, 'id="group-edit-book-uuid-debug"')
        self.assertNotContains(response, 'id="group-edit-add-book"')
        self.assertNotContains(response, 'id="group-edit-book-id"')
        self.assertContains(response, 'id="group-edit-shelves-results"')
        self.assertContains(response, 'id="group-edit-shelves-actions"')
        self.assertContains(response, 'id="group-delete-root"')
        self.assertContains(
            response, "Curator grants group-scoped management access to readers."
        )
        html = response.content.decode("utf-8")
        root_start = html.index('id="group-edit-root"')
        tabs_start = html.index('aria-label="Group edit tabs"', root_start)
        details_panel = html.index('id="tab-details" class="tab-panel"', root_start)
        self.assertLess(tabs_start, details_panel)
        self.assertNotIn('id="group-edit-root" class="card', html)
        for tab in ("details", "books", "add-books", "members", "shelves"):
            self.assertNotIn(f'id="tab-{tab}" class="card', html)
        books_panel = html[html.index('id="tab-books"'):html.index('id="tab-add-books"')]
        add_books_panel = html[html.index('id="tab-add-books"'):html.index('id="tab-members"')]
        self.assertNotIn('id="group-edit-book-search-form"', books_panel)
        self.assertIn('id="group-edit-book-search-form"', add_books_panel)

    def test_group_edit_books_js_has_no_manual_uuid_debug_path(self):
        books_js = Path("web/static/web/js/groups/books.js").read_text(
            encoding="utf-8"
        )
        edit_js = Path("web/static/web/js/groups/edit.js").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("uuidDebug", edit_js)
        self.assertNotIn("group-edit-book-uuid-debug", edit_js)
        self.assertNotIn("group-edit-add-book", edit_js)
        self.assertNotIn("group-edit-book-id", edit_js)
        self.assertNotIn("Enter a book UUID", books_js)
        self.assertNotIn("addBookForm", books_js)

    def test_group_edit_delete_is_visible_only_to_manager_or_owner_for_non_public_group(self):
        edit_js = Path("web/static/web/js/groups/edit.js").read_text(encoding="utf-8")

        self.assertIn("isManagerOrOwner", edit_js)
        self.assertIn("const canDeleteGroup = isManagerOrOwner(me) && !isPublicGroup", edit_js)
        self.assertIn("visible(deleteRoot, true)", edit_js)
        self.assertIn('method: "DELETE"', edit_js)
        self.assertIn("window.confirm", edit_js)
        self.assertIn("This cannot be undone.", edit_js)
        self.assertLess(edit_js.index("window.confirm"), edit_js.index('method: "DELETE"'))
        self.assertIn('window.location.href = "/groups/"', edit_js)

    def test_authenticated_group_edit_malformed_id_returns_404(self):
        self.client.force_login(self.user)

        response = self.client.get("/groups/not-a-uuid/edit/", follow=False)

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_shelves_redirects_to_login(self):
        response = self.client.get("/shelves/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/shelves/")

    def test_authenticated_shelves_returns_200_and_has_containers(self):
        self.client.force_login(self.user)
        response = self.client.get("/shelves/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'data-shelf-scope="personal"')
        self.assertContains(response, "Shared by Others")
        self.assertContains(response, 'data-shelf-scope="group"')
        self.assertContains(response, 'id="shelves-status"')
        self.assertContains(response, 'id="shelves-results"')
        self.assertContains(response, 'class="shelves-scope-header"')
        self.assertContains(response, 'class="button shelves-scope-header__new"')
        self.assertNotContains(
            response,
            "Shelves organize presentation and never grant book access.",
        )
        for position in ("top", "bottom"):
            self.assertContains(response, f'id="shelves-pager-{position}"')
            self.assertContains(response, f'id="shelves-range-{position}"')
            self.assertContains(response, f'id="shelves-page-size-{position}"')
            self.assertContains(response, f'id="shelves-prev-{position}"')
            self.assertContains(response, f'id="shelves-next-{position}"')
        self.assertContains(response, "library-pager--sticky", count=1)
        self.assertContains(response, 'href="/shelves/new/"')
        self.assertContains(response, "New shelf")

    def test_unauthenticated_shelf_new_redirects_to_login(self):
        response = self.client.get("/shelves/new/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/shelves/new/")

    def test_authenticated_shelf_new_returns_200_and_has_form(self):
        self.client.force_login(self.user)
        response = self.client.get("/shelves/new/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shelf-new-form"')
        self.assertContains(response, 'id="shelf-new-owner-type"')
        self.assertContains(response, 'id="shelf-new-owner-group"')
        self.assertContains(response, 'id="shelf-new-visibility"')
        self.assertContains(response, 'id="shelf-new-owner-type-row" class="kv__k is-hidden"')
        self.assertContains(response, 'id="shelf-new-owner-group-row" class="kv__k is-hidden"')
        self.assertContains(response, 'id="shelf-new-public-group-help"')

    def test_authenticated_shelf_new_shows_group_owner_controls_when_enabled(self):
        server_settings.enable_advanced_library_groups()
        self.client.force_login(self.user)
        response = self.client.get("/shelves/new/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="shelf-new-owner-type-row"')
        self.assertContains(response, 'id="shelf-new-owner-group-row"')

    def test_shelf_create_js_gates_group_owner_controls_by_current_user(self):
        new_js = Path("web/static/web/js/shelves/new.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("const me = await loadMeAndInitShell()", new_js)
        self.assertIn("export function canCreateGroupShelves(me)", new_js)
        self.assertIn("canManageLibrary(me)", new_js)
        self.assertIn("membership.is_curator === true", new_js)
        self.assertNotIn("group.capabilities", new_js)
        self.assertIn("!membership.is_public_group", new_js)
        self.assertNotIn("curated_group_ids", new_js)
        self.assertNotIn("membership_role", new_js)
        self.assertNotIn("can_create_shelf", new_js)
        self.assertIn("export function manageableShelfGroups(me, groups)", new_js)
        self.assertIn("export function publicShelfGroup(me)", new_js)
        self.assertIn("group.is_public_group === true", new_js)
        self.assertIn("availableGroups.filter", new_js)
        self.assertIn("visible(ownerTypeRow, canCreateGroupShelf)", new_js)
        self.assertIn("visible(ownerGroupRow, canCreateAdvancedGroupShelf)", new_js)
        self.assertIn("!groupUiEnabled && canManageLibrary(me) && !!publicGroup", new_js)
        self.assertIn("results = [publicGroup]", new_js)
        self.assertIn('ownerTypeEl.value = "user"', new_js)
        self.assertIn(
            'groupShelfAvailable && ownerTypeEl.value === "group"',
            new_js,
        )
        self.assertIn("owner_type: ownerType", new_js)
        self.assertIn('if (body.owner_type === "group")', new_js)
        self.assertIn("body.visibility = visibility", new_js)
        self.assertIn("body.owner_group = ownerGroup ||", new_js)
        self.assertIn('body.visibility = "private"', new_js)
        self.assertIn('fetchJSONWithOptions("/api/v1/shelves/"', new_js)

    def test_unauthenticated_shelf_detail_redirects_to_login(self):
        shelf_id = uuid4()
        response = self.client.get(f"/shelves/{shelf_id}/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/api-auth/login/?next=/shelves/{shelf_id}/")

    def test_authenticated_shelf_detail_returns_200_and_has_container(self):
        self.client.force_login(self.user)
        shelf_id = uuid4()
        response = self.client.get(f"/shelves/{shelf_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-shelf-id="{shelf_id}"')
        self.assertContains(response, 'id="shelf-view-summary"')
        self.assertContains(response, 'id="shelf-view-description"')
        self.assertContains(response, 'id="shelf-view-created-by"')
        self.assertContains(response, 'id="shelf-view-items-results"')
        self.assertContains(response, 'class="shelf-view-description is-hidden"')
        self.assertContains(response, 'class="library-results"')
        for position in ("top", "bottom"):
            self.assertContains(
                response,
                f'id="shelf-view-items-pager-{position}"',
            )
            self.assertContains(
                response,
                f'id="shelf-view-items-range-{position}"',
            )
            self.assertContains(
                response,
                f'id="shelf-view-items-page-size-{position}"',
            )
            self.assertContains(
                response,
                f'id="shelf-view-items-prev-{position}"',
            )
            self.assertContains(
                response,
                f'id="shelf-view-items-next-{position}"',
            )
        self.assertContains(response, 'id="shelf-view-edit-link"')
        self.assertNotContains(response, ">Details</h2>")
        self.assertNotContains(response, ">Books</h2>")

    def test_authenticated_shelf_detail_malformed_id_returns_404(self):
        self.client.force_login(self.user)

        response = self.client.get("/shelves/not-a-uuid/", follow=False)

        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_shelf_edit_redirects_to_login(self):
        shelf_id = uuid4()
        response = self.client.get(f"/shelves/{shelf_id}/edit/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"/api-auth/login/?next=/shelves/{shelf_id}/edit/")

    def test_authenticated_shelf_edit_returns_200_and_has_container(self):
        self.client.force_login(self.user)
        shelf_id = uuid4()
        response = self.client.get(f"/shelves/{shelf_id}/edit/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-shelf-id="{shelf_id}"')
        self.assertContains(response, 'id="shelf-edit-owner-context"')
        self.assertContains(response, 'id="shelf-edit-tabs"')
        self.assertContains(response, 'id="shelf-edit-tab-books"')
        self.assertContains(response, 'id="shelf-edit-tab-add"')
        self.assertContains(response, 'id="shelf-edit-tab-details"')
        self.assertContains(response, 'id="shelf-edit-panel-books"')
        self.assertContains(response, 'id="shelf-edit-panel-add"')
        self.assertContains(response, 'id="shelf-edit-panel-details"')
        self.assertContains(response, 'id="shelf-edit-form"')
        self.assertContains(response, 'id="shelf-edit-items-results"')
        self.assertContains(response, 'id="shelf-edit-book-search-form"')
        self.assertContains(response, 'id="shelf-edit-danger"')
        self.assertContains(response, 'id="shelf-edit-delete-btn"')

    def test_authenticated_shelf_edit_malformed_id_returns_404(self):
        self.client.force_login(self.user)

        response = self.client.get("/shelves/not-a-uuid/edit/", follow=False)

        self.assertEqual(response.status_code, 404)

    def test_shelf_items_js_has_move_controls(self):
        js = Path("web/static/web/js/shelves/items.js").read_text()
        self.assertIn('data-action="move-up"', js)
        self.assertIn('data-action="move-down"', js)
        self.assertIn('data-action="move-to"', js)
        self.assertIn('aria-label="Move ${escapeHtml(title)} to position"', js)
        self.assertIn("patchShelfItemPosition", js)
        self.assertIn("storedPosition >= currentItemTotal - 1", js)
