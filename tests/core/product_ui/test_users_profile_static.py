"""Tests for users, profile, and account management pages."""
from pathlib import Path

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
        self.assertContains(response, 'data-filter="curator"')
        self.assertContains(response, 'data-filter="librarian"')
        self.assertContains(response, 'data-filter="manager"')
        self.assertContains(response, 'data-filter="inactive"')
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(response, "breadcrumbs--single")
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, "Users")
        self.assertContains(response, 'id="users-create-link"')
        self.assertContains(
            response,
            "Manage local users, roles, and group memberships.",
        )
        self.assertNotContains(response, "Django users")

    def test_authenticated_user_new_returns_200_and_has_form(self):
        self.client.force_login(self.user)
        response = self.client.get("/users/new/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="user-new-form"')
        self.assertContains(response, 'id="user-new-username"')
        self.assertContains(response, 'id="user-new-created-password"')

    def test_authenticated_user_edit_returns_200_and_has_form(self):
        self.client.force_login(self.user)
        response = self.client.get(f"/users/{self.user.profile.id}/edit/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/static/web/js/main.js")
        self.assertContains(response, "/static/web/app.css")
        self.assertContains(response, 'id="user-edit-form"')
        self.assertContains(response, 'data-profile-id="')
        self.assertNotContains(response, 'data-user-id="')
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(
            response,
            '<a class="breadcrumbs__link" href="/users/">Users</a>',
            html=False,
        )
        self.assertContains(response, "User")
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, "Edit")
        self.assertNotContains(response, "Back to users")
        self.assertContains(response, 'id="user-edit-username"')
        self.assertContains(response, 'id="user-edit-must-change"')
        self.assertContains(response, 'id="user-reset-password-btn"')
        self.assertContains(response, 'id="user-memberships-card"')
        self.assertContains(response, 'id="user-memberships-add-form"')
        self.assertNotContains(response, 'id="user-memberships-status"')
        self.assertContains(response, 'class="membership-add-tile"')
        self.assertContains(response, 'class="membership-add-tile__curator"')
        self.assertContains(
            response,
            "Managers, librarians, and owners can already manage books globally.",
        )
        self.assertContains(response, "Curator identifies members who specifically steward this group")
        self.assertContains(
            response, "group-scoped management access to readers."
        )

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
        self.assertContains(response, 'id="profile-groups"')
        self.assertNotContains(response, "Show access details")
        self.assertNotContains(response, 'id="profile-access"')

        profile_js = Path("web/static/web/js/profile/main.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("function titleCaseRole", profile_js)
        self.assertIn("roleEl.textContent = titleCaseRole(me.role)", profile_js)
        self.assertIn('ownerEl.textContent = me.is_owner ? "Yes" : "No"', profile_js)

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
        response = self.client.get("/app/")
        self.assertContains(response, '<form class="userbox__logoutform" action="/api-auth/logout/" method="post">')

    def test_post_logout_logs_out_and_redirects(self):
        self.client.force_login(self.user)
        response = self.client.post("/api-auth/logout/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
