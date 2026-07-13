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
        self.assertNotIn("includeEmail: true", self.group_shared_js)

    def test_add_member_picker_uses_username_and_name_without_email(self):
        self.assertIn("[u.first_name, u.last_name]", self.group_memberships_js)
        self.assertIn("`${u.username} (${name})`", self.group_memberships_js)
        self.assertNotIn("u.email", self.group_memberships_js)

    def test_group_and_user_mutations_route_by_profile_uuid(self):
        self.assertIn('data-user-id="${escapeHtml(userId)}"', self.group_shared_js)
        self.assertIn('getAttribute("data-user-id")', self.group_memberships_js)
        self.assertIn('data-user-id="${escapeHtml(profileId)}"', self.user_memberships_js)
        self.assertIn('getAttribute("data-user-id")', self.user_memberships_js)

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
