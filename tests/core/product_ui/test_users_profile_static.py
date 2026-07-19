"""Tests for users, profile, and account management pages."""
from pathlib import Path

from core import server_settings
from tests.core.product_ui.helpers import ProductUiTestCase


class ProductUiUsersProfileTests(ProductUiTestCase):
    """Test users list, profile, account management pages."""

    def test_unauthenticated_users_redirects_to_login(self):
        response = self.client.get("/users/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/users/")

    def test_unauthenticated_profile_redirects_to_login(self):
        response = self.client.get("/profile/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/profile/")

    def test_unauthenticated_profile_password_redirects_to_login(self):
        response = self.client.get("/profile/password/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/profile/password/")

    def test_unauthenticated_user_new_redirects_to_login(self):
        response = self.client.get("/users/new/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/?next=/users/new/")

    def test_unauthenticated_user_edit_redirects_to_login(self):
        profile_id = self.user.profile.id
        response = self.client.get(f"/users/{profile_id}/edit/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"], f"/api-auth/login/?next=/users/{profile_id}/edit/"
        )

    def test_authenticated_users_returns_200_and_has_containers(self):
        self.client.force_login(self.user)
        response = self.client.get("/users/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="users-results"')
        self.assertContains(response, 'id="users-filters"')
        self.assertContains(response, 'data-filter="all"')
        self.assertContains(response, 'data-filter="reader"')
        self.assertContains(response, 'data-filter="librarian"')
        self.assertContains(response, 'data-filter="manager"')
        self.assertContains(response, 'data-filter="inactive"')
        self.assertNotContains(response, 'data-filter="curator"')
        self.assertContains(response, 'id="users-create-link"')
        self.assertContains(response, 'class="users-list-section"')
        self.assertNotContains(response, '<section class="card">')
        self.assertNotContains(response, "Manage local users and roles")
        for position in ("top", "bottom"):
            self.assertContains(response, f'id="users-pager-{position}"')
            self.assertContains(response, f'id="users-range-{position}"')
            self.assertContains(response, f'id="users-page-size-{position}"')
            self.assertContains(response, f'id="users-prev-{position}"')
            self.assertContains(response, f'id="users-next-{position}"')
        self.assertNotContains(response, "Django users")

    def test_authenticated_users_shows_group_membership_filter_when_enabled(self):
        server_settings.enable_advanced_library_groups()
        self.client.force_login(self.user)
        response = self.client.get("/users/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-filter="curator"')
        self.assertNotContains(response, "Manage local users and roles")

    def test_authenticated_user_new_returns_200_and_has_form(self):
        self.client.force_login(self.user)
        response = self.client.get("/users/new/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="user-new-form"')
        self.assertContains(response, 'id="user-new-username"')
        self.assertContains(response, 'id="user-new-created-password"')
        self.assertContains(response, 'class="user-form-section"')
        self.assertContains(response, 'class="user-form__actions"')
        self.assertContains(response, 'href="/users/">Cancel</a>')
        self.assertNotContains(response, '<h2 class="card__title">New User</h2>')

    def test_authenticated_user_edit_returns_200_and_hides_memberships_by_default(self):
        self.client.force_login(self.user)
        response = self.client.get(f"/users/{self.user.profile.id}/edit/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="user-edit-form"')
        self.assertContains(response, 'data-profile-id="')
        self.assertNotContains(response, 'data-user-id="')
        self.assertContains(response, 'id="user-edit-title"')
        self.assertNotContains(response, 'id="user-edit-username"')
        self.assertContains(response, 'id="user-edit-must-change"')
        self.assertContains(response, 'id="user-reset-password-btn"')
        self.assertContains(response, 'class="user-form user-edit-form"')
        self.assertContains(response, 'class="user-form__actions"')
        self.assertNotContains(response, 'class="tabs"')
        self.assertNotContains(response, 'id="user-edit-groups"')
        self.assertNotContains(response, 'id="user-memberships-card"')
        self.assertNotContains(response, 'id="user-memberships-add-form"')
        self.assertNotContains(response, 'id="user-memberships-status"')
        self.assertNotContains(response, 'class="membership-add-tile"')
        self.assertNotContains(response, 'class="membership-add-tile__curator"')

    def test_authenticated_user_edit_shows_memberships_when_enabled(self):
        server_settings.enable_advanced_library_groups()
        self.client.force_login(self.user)
        response = self.client.get(f"/users/{self.user.profile.id}/edit/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="user-edit-groups"')
        self.assertContains(response, 'id="user-memberships-card"')
        self.assertContains(response, 'id="user-memberships-add-form"')
        self.assertContains(response, 'class="membership-add-tile"')
        self.assertContains(response, 'class="membership-add-tile__curator"')
        self.assertContains(
            response,
            "Manage this user's group membership and curator assignments.",
        )

    def test_authenticated_user_edit_malformed_profile_id_returns_404(self):
        self.client.force_login(self.user)

        response = self.client.get("/users/not-a-uuid/edit/", follow=False)

        self.assertEqual(response.status_code, 404)

    def test_authenticated_profile_returns_200_and_has_containers(self):
        self.client.force_login(self.user)
        response = self.client.get("/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="profile-edit-form"')
        self.assertContains(response, 'id="profile-edit-btn"')
        self.assertContains(response, 'id="profile-save-btn"')
        self.assertContains(response, ">Role</div>")
        self.assertContains(response, 'id="profile-role"')
        self.assertContains(response, ">Owner</div>")
        self.assertContains(response, 'id="profile-owner"')
        self.assertContains(response, 'id="profile-email-input"')
        self.assertContains(response, "Session management")
        self.assertContains(response, 'id="profile-logout-others-btn"')
        self.assertContains(response, "Device/API sessions")
        self.assertContains(response, 'href="/client-api/authorize/"')
        self.assertContains(response, 'id="profile-client-sessions"')
        self.assertContains(response, 'id="profile-client-sessions-status"')
        self.assertNotContains(response, 'id="profile-groups"')
        self.assertNotContains(response, "Show access details")
        self.assertNotContains(response, 'id="profile-access"')

        profile_js = Path("web/static/web/js/profile/main.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("function titleCaseRole", profile_js)
        self.assertIn("roleEl.textContent = titleCaseRole(me.role)", profile_js)
        self.assertIn('ownerEl.textContent = me.is_owner ? "Yes" : "No"', profile_js)

    def test_authenticated_profile_shows_groups_when_enabled(self):
        server_settings.enable_advanced_library_groups()
        self.client.force_login(self.user)
        response = self.client.get("/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="profile-groups"')

    def test_authenticated_profile_password_returns_200_and_has_form(self):
        self.client.force_login(self.user)
        response = self.client.get("/profile/password/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="profile-password-form"')
        self.assertContains(response, 'id="profile-password-current"')

    def test_logout_is_post_form(self):
        self.client.force_login(self.user)
        response = self.client.get("/dashboard/")
        self.assertContains(response, '<form class="userbox__logoutform" action="/api-auth/logout/" method="post">')

    def test_post_logout_logs_out_and_redirects(self):
        self.client.force_login(self.user)
        response = self.client.post("/api-auth/logout/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
