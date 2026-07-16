from pathlib import Path

import pytest

from tests.core.product_ui.helpers import ProductUiTestCase


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


class ProductUiMembershipManagementJsContractsTests(ProductUiTestCase):
    def setUp(self):
        super().setUp()
        self.group_memberships_js = Path(
            "web/static/web/js/groups/memberships.js"
        ).read_text(encoding="utf-8")
        self.group_shared_js = Path("web/static/web/js/groups/shared.js").read_text(
            encoding="utf-8"
        )
        self.user_memberships_js = Path(
            "web/static/web/js/users/memberships.js"
        ).read_text(encoding="utf-8")
        self.users_list_js = Path("web/static/web/js/users/list.js").read_text(
            encoding="utf-8"
        )
        self.group_edit_template = Path("web/templates/web/groups/edit.html").read_text(
            encoding="utf-8"
        )

    def test_group_and_user_add_membership_send_profile_uuid_as_user_id(self):
        self.assertIn(
            "JSON.stringify({ user_id: String(profileId), is_curator: isCurator })",
            self.group_memberships_js,
        )
        self.assertIn(
            "JSON.stringify({ user_id: String(profileId), is_curator: isCurator })",
            self.user_memberships_js,
        )

    def test_group_members_render_paginated_nested_user_payload(self):
        self.assertIn("payload && payload.results", self.group_shared_js)
        self.assertIn("m && m.user ? m.user : m", self.group_shared_js)
        self.assertIn("user.profile_id", self.group_shared_js)
        self.assertIn("renderUserIdentity(user)", self.group_shared_js)
        self.assertNotIn("user.first_name", self.group_shared_js)
        self.assertNotIn("user.last_name", self.group_shared_js)
        self.assertNotIn("includeEmail: true", self.group_shared_js)

    def test_add_member_picker_uses_narrow_username_choices(self):
        self.assertIn("/api/v1/accounts/user-choices/?", self.group_memberships_js)
        self.assertIn("exclude_group: String(groupId)", self.group_memberships_js)
        self.assertNotIn("/api/v1/accounts/users/", self.group_memberships_js)
        self.assertNotIn("/api/v1/accounts/users/", self.group_shared_js)
        self.assertIn("button.textContent = username", self.group_memberships_js)
        self.assertNotIn("first_name", self.group_memberships_js)
        self.assertNotIn("last_name", self.group_memberships_js)
        self.assertNotIn("choice.email", self.group_memberships_js)
        self.assertIn('type="search"', self.group_edit_template)
        self.assertIn('class="member-choice-picker"', self.group_edit_template)
        self.assertIn('class="member-choice-picker__menu is-hidden"', self.group_edit_template)
        self.assertIn('button.className = "member-choice-picker__option"', self.group_memberships_js)
        self.assertNotIn('<select id="group-edit-member-user"', self.group_edit_template)
        self.assertNotIn("loadAllManageableUsers", self.group_memberships_js)

    def test_add_member_autocomplete_submits_and_clears_selected_profile(self):
        self.assertIn('addMemberUser.value = profileId', self.group_memberships_js)
        self.assertIn(
            "JSON.stringify({ user_id: String(profileId), is_curator: isCurator })",
            self.group_memberships_js,
        )
        self.assertIn('addMemberUser.value = ""', self.group_memberships_js)
        self.assertIn('addMemberSearch.value = ""', self.group_memberships_js)
        self.assertIn('setAddMemberStatus("Searching...", false)', self.group_memberships_js)
        self.assertIn('setAddMemberStatus("No matching users.", false)', self.group_memberships_js)
        self.assertIn('setAddMemberStatus("Could not search users.", true)', self.group_memberships_js)

    def test_managed_users_ui_keeps_full_management_endpoint(self):
        self.assertIn('let currentUrl = "/api/v1/accounts/users/"', self.users_list_js)

    def test_group_and_user_mutations_route_by_profile_uuid(self):
        self.assertIn('data-user-id="${escapeHtml(userId)}"', self.group_shared_js)
        self.assertIn('getAttribute("data-user-id")', self.group_memberships_js)
        self.assertIn('data-user-id="${escapeHtml(profileId)}"', self.user_memberships_js)
        self.assertIn('getAttribute("data-user-id")', self.user_memberships_js)

    def test_user_edit_membership_rows_use_group_badges_and_public_curator_copy(self):
        self.assertIn('from "../ui/groups.js"', self.user_memberships_js)
        self.assertIn("renderGroupBadge(g", self.user_memberships_js)
        self.assertIn('class="membership-row"', self.user_memberships_js)
        self.assertIn('class="membership-row__group"', self.user_memberships_js)
        self.assertIn('class="membership-row__controls"', self.user_memberships_js)
        self.assertIn('class="membership-row__actions"', self.user_memberships_js)
        self.assertIn('class="membership-row__status muted"', self.user_memberships_js)
        self.assertIn("Public fallback group; curator unavailable.", self.user_memberships_js)
        self.assertIn("descriptionForGroup", self.user_memberships_js)
        self.assertIn("titleAttr", self.user_memberships_js)
        self.assertNotIn('<span class="pill">Member</span>', self.user_memberships_js)
        self.assertNotIn('<span class="pill">Curator</span>', self.user_memberships_js)
        self.assertNotIn("Public is the default/fallback group", self.user_memberships_js)

    def test_user_edit_membership_mutation_controls_stay_profile_scoped(self):
        self.assertIn('data-action="membership-curator"', self.user_memberships_js)
        self.assertIn('input[data-action="membership-curator"]', self.user_memberships_js)
        self.assertIn('method: "PATCH"', self.user_memberships_js)
        self.assertIn("clearLiveStatusLater", self.user_memberships_js)
        self.assertIn("5000", self.user_memberships_js)
        self.assertIn('window.confirm("Remove this user from the group?")', self.user_memberships_js)
        self.assertIn("icon-button--danger", self.user_memberships_js)
        self.assertNotIn('data-action="membership-save"', self.user_memberships_js)
        self.assertNotIn('disabled" : ""} />', self.user_memberships_js)
        self.assertNotIn("membership_role", self.user_memberships_js)
        self.assertNotIn("curated_group_ids", self.user_memberships_js)
        self.assertNotIn("me.capabilities", self.user_memberships_js)
        self.assertNotIn(
            "${escapeHtml(g.name || String(g.id || \"\"))}",
            self.user_memberships_js,
        )

    def test_curator_create_update_and_rendering_use_boolean_contract(self):
        for source in (self.group_memberships_js, self.user_memberships_js):
            self.assertIn("is_curator: isCurator", source)
            self.assertIn("is_curator: desired", source)
        self.assertIn("const isCurator = !!m.is_curator", self.group_shared_js)
        self.assertIn('${isCurator ? "checked" : ""}', self.group_shared_js)
        self.assertIn("(Curator)", self.group_shared_js)

    def test_public_curator_controls_remain_disabled_and_errors_are_specific(self):
        self.assertIn("addMemberRole.disabled = true", self.group_memberships_js)
        self.assertIn("const isCurator = !isPublicGroup", self.group_memberships_js)
        self.assertIn("Public cannot have curators.", self.group_memberships_js)
        self.assertIn("summarizeFieldErrors", self.group_memberships_js)
        self.assertIn("summarizeFieldErrors", self.user_memberships_js)
        self.assertIn("fieldMsg || msg", self.group_memberships_js)
        self.assertIn("fieldMsg || msg", self.user_memberships_js)

    def test_no_membership_create_payload_uses_profile_id_field(self):
        for source in (self.group_memberships_js, self.user_memberships_js):
            self.assertNotIn("JSON.stringify({ profile_id:", source)

    def test_membership_record_uuid_is_not_used_by_product_ui(self):
        for source in (
            self.group_memberships_js,
            self.group_shared_js,
            self.user_memberships_js,
        ):
            self.assertNotIn("membershipId", source)
            self.assertNotIn("data-membership-id", source)
