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
        self.assertContains(response, 'id="group-view-members-results"')
        self.assertContains(response, 'id="group-view-shelves-results"')
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(
            response,
            '<a class="breadcrumbs__link" href="/groups/">Groups</a>',
            html=False,
        )
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, "Group")
        self.assertNotContains(response, "Back to Groups")

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
        self.assertContains(response, 'data-tab="members"')
        self.assertContains(response, 'data-tab="shelves"')
        self.assertContains(response, 'id="group-edit-book-search-form"')
        self.assertContains(response, 'id="group-edit-book-search-results"')
        self.assertNotContains(response, "Debug: add book by UUID")
        self.assertNotContains(response, 'id="group-edit-book-uuid-debug"')
        self.assertNotContains(response, 'id="group-edit-add-book"')
        self.assertNotContains(response, 'id="group-edit-book-id"')
        self.assertContains(response, 'id="group-edit-shelves-results"')
        self.assertContains(response, 'id="group-edit-shelves-actions"')
        self.assertContains(response, 'id="group-delete-root"')
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(
            response,
            '<a class="breadcrumbs__link" href="/groups/">Groups</a>',
            html=False,
        )
        self.assertContains(
            response,
            f'<a class="breadcrumbs__link" href="/groups/{group_id}/">Group</a>',
            html=False,
        )
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, "Edit")
        self.assertNotContains(response, "Back to Group")
        self.assertContains(
            response,
            "Managers, librarians, and owners can already manage books globally.",
        )
        self.assertContains(response, "Curator identifies members who specifically steward this group")
        self.assertContains(
            response, "group-scoped management access to readers."
        )

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
        self.assertContains(response, "Personal Shelves")
        self.assertContains(response, "Shared Shelves")
        self.assertContains(response, 'id="personal-shelves-status"')
        self.assertContains(response, 'id="personal-shelves-results"')
        self.assertContains(response, 'id="personal-shelves-prev"')
        self.assertContains(response, 'id="personal-shelves-next"')
        self.assertContains(response, 'id="personal-shelves-page-note"')
        self.assertContains(response, 'id="shared-shelves-status"')
        self.assertContains(response, 'id="shared-shelves-results"')
        self.assertContains(response, 'id="shared-shelves-prev"')
        self.assertContains(response, 'id="shared-shelves-next"')
        self.assertContains(response, 'id="shared-shelves-page-note"')
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
        self.assertContains(response, 'id="shelf-view-items-prev"')
        self.assertContains(response, 'id="shelf-view-items-next"')
        self.assertContains(response, 'id="shelf-view-items-page-note"')
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(
            response,
            '<a class="breadcrumbs__link" href="/shelves/">Shelves</a>',
            html=False,
        )
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, "Shelf")
        self.assertNotContains(response, "Back to Shelves")
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
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(
            response,
            '<a class="breadcrumbs__link" href="/shelves/">Shelves</a>',
            html=False,
        )
        self.assertContains(
            response,
            f'<a class="breadcrumbs__link" href="/shelves/{shelf_id}/">Shelf</a>',
            html=False,
        )
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, "Edit")
        self.assertNotContains(response, "Back to Shelf")

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
