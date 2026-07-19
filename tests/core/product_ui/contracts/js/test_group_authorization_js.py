from pathlib import Path

import pytest

from tests.core.product_ui.helpers import ProductUiTestCase


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


class ProductUiGroupAuthorizationJsContractTests(ProductUiTestCase):
    def setUp(self):
        super().setUp()
        self.shared = Path("web/static/web/js/groups/shared.js").read_text(
            encoding="utf-8"
        )
        self.edit = Path("web/static/web/js/groups/edit.js").read_text(
            encoding="utf-8"
        )
        self.view = Path("web/static/web/js/groups/view.js").read_text(
            encoding="utf-8"
        )
        self.list = Path("web/static/web/js/groups/list.js").read_text(
            encoding="utf-8"
        )
        self.memberships = Path(
            "web/static/web/js/groups/memberships.js"
        ).read_text(encoding="utf-8")
        self.shelf_new = Path("web/static/web/js/shelves/new.js").read_text(
            encoding="utf-8"
        )

    def test_curator_level_controls_use_me_role_and_exact_membership(self):
        self.assertIn("export function canCurateGroup", self.shared)
        self.assertIn("if (canManageLibrary(me)) return true", self.shared)
        self.assertIn("if (group.is_public_group === true) return false", self.shared)
        self.assertIn("String(membership.id) === String(group.id)", self.shared)
        self.assertIn("membership.is_curator === true", self.shared)

    def test_group_edit_separates_public_identity_from_other_curation(self):
        self.assertIn(
            "if (group && group.is_public_group === true) return false",
            self.shared,
        )
        self.assertIn(
            "return canCurateGroup({ me, group });", self.shared
        )
        self.assertIn("visible(editForm, allowDescriptionEdit)", self.edit)
        self.assertIn("allowBookManage", self.edit)
        self.assertIn(
            "const allowShelfManage = canManageGroupBooks({ me, group })",
            self.edit,
        )
        self.assertIn("const allowMembershipManage = canManageGroupMemberships(me)", self.memberships)
        self.assertIn("visible(addMemberForm, allowMembershipManage)", self.memberships)
        self.assertIn("renderMembersReadOnly(payload)", self.memberships)

    def test_reader_curator_can_reach_group_edit_from_group_view(self):
        self.assertIn("if (canEditGroupPage({ me, group }))", self.view)
        self.assertIn("/edit/`", self.view)
        self.assertIn("if (!canEditGroupPage({ me, group }))", self.edit)

    def test_group_displays_match_curator_badges_from_me_membership(self):
        self.assertIn("currentUserGroupMembership({ me, group })", self.view)
        self.assertIn("currentUserGroupMembership({ me, group })", self.edit)
        self.assertIn("currentUserGroupMembership({ me, group: g })", self.list)

    def test_stale_group_capability_and_curator_fields_are_absent(self):
        sources = "\n".join(
            [self.shared, self.edit, self.view, self.list, self.shelf_new]
        )
        self.assertNotIn("group.capabilities", sources)
        self.assertNotIn("group.is_curator", sources)
        self.assertNotIn("capabilities.can_curate", sources)
