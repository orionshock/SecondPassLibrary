from pathlib import Path

import pytest

from tests.core.product_ui.css import product_ui_css_text
from tests.core.product_ui.helpers import ProductUiTestCase


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


class ProductUiDisplaySitesJsContractsTests(ProductUiTestCase):
    def test_product_ui_display_sites_use_shared_identity_helpers(self):
        user_identity_modules = {
            path: Path(path).read_text(encoding="utf-8")
            for path in (
                "web/static/web/js/layout.js",
                "web/static/web/js/profile/main.js",
                "web/static/web/js/users/list.js",
                "web/static/web/js/users/edit.js",
                "web/static/web/js/users/new.js",
                "web/static/web/js/groups/shared.js",
            )
        }
        group_badge_modules = {
            path: Path(path).read_text(encoding="utf-8")
            for path in (
                "web/static/web/js/profile/main.js",
                "web/static/web/js/library/detail.js",
                "web/static/web/js/book_edit/groups.js",
                "web/static/web/js/groups/list.js",
                "web/static/web/js/users/list.js",
                "web/static/web/js/users/memberships.js",
                "web/static/web/js/shelves/shared.js",
            )
        }
        users_shared_js = Path("web/static/web/js/users/shared.js").read_text(
            encoding="utf-8"
        )
        group_memberships_js = Path(
            "web/static/web/js/groups/memberships.js"
        ).read_text(encoding="utf-8")
        user_memberships_js = Path(
            "web/static/web/js/users/memberships.js"
        ).read_text(encoding="utf-8")
        layout_js = user_identity_modules["web/static/web/js/layout.js"]
        library_detail_js = group_badge_modules[
            "web/static/web/js/library/detail.js"
        ]
        book_edit_groups_js = group_badge_modules[
            "web/static/web/js/book_edit/groups.js"
        ]
        groups_list_js = group_badge_modules[
            "web/static/web/js/groups/list.js"
        ]
        groups_shared_js = user_identity_modules[
            "web/static/web/js/groups/shared.js"
        ]
        css = product_ui_css_text()

        for module_js in user_identity_modules.values():
            self.assertIn("renderUserIdentity", module_js)
        for module_js in group_badge_modules.values():
            self.assertIn("renderGroupBadge", module_js)

        self.assertIn("includeEmail: true", user_identity_modules["web/static/web/js/users/list.js"])
        self.assertNotIn("includeEmail: true", groups_shared_js)
        self.assertNotIn("includeEmail: true", layout_js)
        self.assertNotIn("includeEmail: true", user_identity_modules["web/static/web/js/profile/main.js"])
        self.assertNotIn("includeEmail: true", user_identity_modules["web/static/web/js/users/edit.js"])
        self.assertNotIn("includeEmail: true", user_identity_modules["web/static/web/js/users/new.js"])

        self.assertIn("includeDisplayName: false", layout_js)
        self.assertNotIn(
            ".user-identity--shell .user-identity__display-name",
            css,
        )
        self.assertIn("renderShelfMetadata(s)", library_detail_js)
        self.assertNotIn("meta.innerHTML", library_detail_js)
        self.assertNotIn("(user:", library_detail_js)
        self.assertNotIn("(group:", library_detail_js)
        self.assertNotIn('pill pill--owner", "Public"', library_detail_js)
        self.assertNotIn('pill pill--owner", "Public"', book_edit_groups_js)
        self.assertNotIn("pill--owner\">Public", groups_list_js)
        self.assertIn("renderUserIdentity(user)", groups_shared_js)
        self.assertNotIn("Role: <code>", groups_shared_js)
        self.assertIn('class="membership-row"', groups_shared_js)
        self.assertIn('class="membership-row__group membership-row__identity"', groups_shared_js)
        self.assertIn('class="membership-row__controls"', groups_shared_js)
        self.assertIn('class="membership-row__actions"', groups_shared_js)
        self.assertIn('class="membership-row__status muted"', groups_shared_js)
        self.assertIn('data-action="member-curator"', groups_shared_js)
        self.assertIn("Public fallback group; curator unavailable.", groups_shared_js)
        self.assertIn("remove_circle", groups_shared_js)
        self.assertIn('aria-label="Remove member"', groups_shared_js)
        self.assertIn("icon-button--danger", groups_shared_js)
        self.assertNotIn("user.is_owner", groups_shared_js)
        self.assertNotIn('data-action="member-save"', groups_shared_js)
        self.assertNotIn('<span class="pill">Member</span>', groups_shared_js)
        self.assertNotIn('<span class="pill">Curator</span>', groups_shared_js)
        self.assertIn("remove_circle", book_edit_groups_js)
        self.assertIn('aria-label", "Remove from group"', book_edit_groups_js)
        self.assertIn("remove_circle", user_memberships_js)
        self.assertIn('aria-label="Remove membership"', user_memberships_js)
        self.assertIn('data-action="membership-remove"', user_memberships_js)
        self.assertIn('class="membership-row__status muted"', user_memberships_js)
        self.assertIn("setRowStatus", user_memberships_js)
        self.assertNotIn("membershipsStatus", user_memberships_js)
        self.assertIn('window.confirm("Remove this user from the group?")', group_memberships_js)
        self.assertIn('input[data-action="member-curator"]', group_memberships_js)
        self.assertIn("clearLiveStatusLater", group_memberships_js)
        self.assertIn("5000", group_memberships_js)
        self.assertIn("target.disabled = true", group_memberships_js)
        self.assertIn("target.checked = !desired", group_memberships_js)
        self.assertIn("body: JSON.stringify({ is_curator: desired })", group_memberships_js)
        self.assertNotIn("member-save", group_memberships_js)
        self.assertNotIn('setStatus(membersStatus, "", false)', group_memberships_js)
        self.assertIn('closest("[data-action]")', group_memberships_js)
        self.assertIn('closest("[data-action]")', user_memberships_js)
        self.assertIn('class="identity-row"', groups_list_js)
        self.assertIn('class="badge-row"', groups_list_js)
        self.assertIn('from "../ui/cover_previews.js"', groups_list_js)
        self.assertIn("renderCoverPreviewStrip(g.preview_books", groups_list_js)
        self.assertIn("actionLabel: `View group ${name}`", groups_list_js)
        self.assertIn('data-group-url="${escapeHtml(href)}"', groups_list_js)
        self.assertIn('title="Open group ${escapeHtml(name)}"', groups_list_js)
        self.assertIn('href="${escapeHtml(href)}"', groups_list_js)
        self.assertIn("function isInteractiveElement", groups_list_js)
        self.assertIn('closest("a, button, input, select, textarea, label, summary, [role=\'button\'], [role=\'link\']")', groups_list_js)
        self.assertIn("function installGroupCardNavigation", groups_list_js)
        self.assertIn('source.closest("[data-group-url]")', groups_list_js)
        self.assertIn("window.location.assign(url)", groups_list_js)
        self.assertIn("installGroupCardNavigation(resultsEl)", groups_list_js)
        self.assertIn(
            'initialUrl: "/api/v1/library/groups/?include_preview_books=true"',
            groups_list_js,
        )
        self.assertIn('class="book group-list-card"', groups_list_js)
        self.assertIn('class="group-list-card__main"', groups_list_js)
        self.assertIn('group-list-card__description', groups_list_js)
        self.assertNotIn("href,", groups_list_js)
        self.assertIn('el("ul", "compact-list")', library_detail_js)
        self.assertIn('el("li", "compact-list__item")', library_detail_js)
        self.assertIn('el("ul", "compact-list")', book_edit_groups_js)
        self.assertIn('el("li", "compact-list__item")', book_edit_groups_js)
        self.assertNotIn("groupsSummary", users_shared_js)
        self.assertNotIn("curatedGroupsFromUser", users_shared_js)
        self.assertNotIn("escapeHtml(username)", groups_shared_js)

        # Choice controls remain plain text; user search results contain usernames only.
        self.assertIn("button.textContent = username", group_memberships_js)
        self.assertIn("opt.textContent", user_memberships_js)
