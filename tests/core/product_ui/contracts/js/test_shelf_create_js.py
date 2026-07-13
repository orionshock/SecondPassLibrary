from pathlib import Path

import pytest

from tests.core.product_ui.helpers import ProductUiTestCase


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


class ProductUiShelfCreateJsContractsTests(ProductUiTestCase):
    def setUp(self):
        super().setUp()
        self.source = Path("web/static/web/js/shelves/new.js").read_text(
            encoding="utf-8"
        )

    def test_advanced_broad_roles_receive_all_manageable_group_options(self):
        self.assertIn("const broadAccess = canManageLibrary(me)", self.source)
        self.assertIn("broadAccess ||", self.source)
        self.assertNotIn("group.capabilities", self.source)

    def test_reader_curator_options_are_membership_scoped_and_non_public(self):
        self.assertIn("const curatedGroupIds = new Set", self.source)
        self.assertIn("membership.is_curator === true", self.source)
        self.assertIn("!membership.is_public_group", self.source)
        self.assertIn("curatedGroupIds.has(String(group.id))", self.source)

    def test_public_option_rules_preserve_advanced_and_simple_modes(self):
        self.assertIn("export function publicShelfGroup(me)", self.source)
        self.assertIn("group.is_public_group === true", self.source)
        self.assertIn("!groupUiEnabled && canManageLibrary(me) && !!publicGroup", self.source)
        self.assertIn("results = [publicGroup]", self.source)

    def test_group_options_load_every_paginated_api_page(self):
        self.assertIn("export async function loadAllShelfGroups()", self.source)
        self.assertIn('fetchAllPaginatedResults("/api/v1/library/groups/"', self.source)
        self.assertIn("Group pagination continuation repeated.", self.source)
        self.assertNotIn("page < 20", self.source)
        self.assertNotIn("page_size=200", self.source)

    def test_allowed_owner_group_deep_link_is_preselected(self):
        self.assertIn("export function requestedShelfGroup(search, groups)", self.source)
        self.assertIn('params.get("owner_group")', self.source)
        self.assertIn('ownerTypeEl.value = "group"', self.source)
        self.assertIn("ownerGroupEl.value = String(requestedGroup.id)", self.source)
        self.assertIn("requested owner group is not available", self.source)

    def test_group_create_payload_is_private_and_personal_payload_is_unchanged(self):
        self.assertIn("export function shelfCreatePayload", self.source)
        self.assertIn('owner_type: ownerType === "group" ? "group" : "user"', self.source)
        self.assertIn("body.owner_group = ownerGroup ||", self.source)
        self.assertIn('body.visibility = "private"', self.source)
        self.assertIn("body.visibility = visibility", self.source)
        self.assertIn('fetchJSONWithOptions("/api/v1/shelves/"', self.source)

    def test_failed_group_loading_shows_bounded_safe_error_and_keeps_personal_mode(self):
        self.assertIn("export function groupLoadErrorMessage(error)", self.source)
        self.assertIn("Unable to load owner groups", self.source)
        self.assertIn("Personal shelf creation is still available.", self.source)
        self.assertIn("groupShelfAvailable = false", self.source)
        self.assertIn("setErr(message)", self.source)
        self.assertNotIn("setErr(extractApiErrorMessage(error))", self.source)
