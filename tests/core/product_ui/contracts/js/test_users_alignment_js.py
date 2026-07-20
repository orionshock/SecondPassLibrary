from pathlib import Path

import pytest

from tests.core.product_ui.js import REPOSITORY_ROOT as ROOT
from tests.core.product_ui.js import run_node_json


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


def test_users_list_filter_order_page_and_page_size_are_url_backed():
    module_uri = (ROOT / "web/static/web/js/users/list.js").as_uri()
    result = run_node_json(
        f"""
        const mod = await import("{module_uri}");
        const state = mod.usersListState("?q=ada&role=librarian&is_active=false&ordering=-role&page=3&page_size=40");
        console.log(JSON.stringify({{ state, href: mod.usersListHref(state), api: mod.usersApiUrl(state) }}));
        """
    )

    assert result["state"] == {
        "q": "ada",
        "role": "librarian",
        "isActive": "false",
        "ordering": "-role",
        "page": 3,
        "pageSize": 40,
    }
    assert result["href"] == (
        "/users/?q=ada&role=librarian&is_active=false&ordering=-role&page=3&page_size=40"
    )
    assert result["api"] == (
        "/api/v1/accounts/users/?q=ada&role=librarian&is_active=false&ordering=-role&page=3&page_size=40"
    )


def test_users_list_uses_library_pagers_history_and_right_aligned_rows():
    template = Path("web/templates/web/users/users.html").read_text(encoding="utf-8")
    pager = Path("web/templates/web/users/_pager.html").read_text(encoding="utf-8")
    source = Path("web/static/web/js/users/list.js").read_text(encoding="utf-8")
    css = Path("web/static/web/css/users.css").read_text(encoding="utf-8")

    assert '<section class="users-list-section">' in template
    assert '<section class="card">' not in template
    assert 'class="page-header"' in template
    assert 'id="users-create-link"' in template
    assert template.count('{% include "web/users/_pager.html"') == 2
    assert 'class="pager library-pager users-pager' in pager
    assert "library-pager--sticky" in pager
    assert "window.history.replaceState" in source
    assert "window.history.pushState" in source
    assert 'window.addEventListener("popstate"' in source
    assert "state = { ...state, ...changes, page: 1 }" in source
    assert "passesFilter" not in source
    assert "sortedUsers" not in source
    assert 'id="users-search"' in template
    assert 'id="users-is-active"' in template
    assert ".user-row__actions { justify-content: flex-end; }" in css
    assert '.users-filters .button[aria-pressed="true"]' in css
    assert "user-row--inactive" in source
    assert ".user-row--inactive" in css
    assert ".pill--inactive" in css


def test_create_user_form_is_bounded_vertical_without_redundant_card_heading():
    template = Path("web/templates/web/users/new.html").read_text(encoding="utf-8")
    css = Path("web/static/web/css/users.css").read_text(encoding="utf-8")

    assert '<h1 class="page-title">Create User</h1>' in template
    assert 'id="user-new-form-card" class="user-form-section"' in template
    assert 'id="user-new-form" class="user-form"' in template
    assert template.count('class="user-form__field"') == 5
    assert 'class="user-form__check"' in template
    assert '<h2 class="card__title">New User</h2>' not in template
    assert 'href="/users/">Cancel</a>' in template
    assert 'id="user-new-submit"' in template
    assert "width: min(100%, 720px)" in css
    assert ".user-form__actions" in css
    assert "justify-content: flex-end" in css


def test_edit_user_keeps_meaningful_cards_without_tabs_and_bounded_form():
    template = Path("web/templates/web/users/edit.html").read_text(encoding="utf-8")
    source = Path("web/static/web/js/users/edit.js").read_text(encoding="utf-8")
    css = Path("web/static/web/css/users.css").read_text(encoding="utf-8")

    assert 'id="user-edit-card" class="card is-hidden"' in template
    assert 'id="user-memberships-card" class="card is-hidden"' in template
    assert '<h2 class="card__title">Group Memberships</h2>' in template
    assert 'class="tabs"' not in template
    assert 'class="user-form user-edit-form"' in template
    assert 'class="user-form__actions"' in template
    assert 'id="user-edit-submit"' in template
    assert "Owner cannot be edited here." in source
    assert 'id="user-edit-title"' in template
    assert 'id="user-edit-username"' not in template
    assert 'id="user-edit-groups"' not in template
    assert 'document.createTextNode("Editing User: ")' in source
    assert 'renderUserIdentity(payload, { className: "user-edit-title__identity" })' in source
    assert "grid-template-columns: 132px minmax(0, 1fr)" in css

    first = template.index('for="user-edit-first"')
    last = template.index('for="user-edit-last"')
    email = template.index('for="user-edit-email"')
    role = template.index('for="user-edit-role"')
    active = template.index('for="user-edit-active"')
    password = template.index('for="user-edit-must-change"')
    assert first < last < email < role < active < password

    form_end = template.index("</form>", template.index('id="user-edit-form"'))
    password_card = template.index('id="user-password-card"')
    require_change = template.index('id="user-edit-must-change"')
    reset_result = template.index('id="user-reset-password-result"')
    copy_warning = template.index("Copy it now. It will not be shown again.")
    assert form_end < password_card < require_change
    assert "Require Password Change on next login." in template
    assert reset_result < copy_warning
    assert "Generate a secure temporary password. Copy it now" not in template


def test_password_change_requirement_saves_inline_outside_user_form():
    template = Path("web/templates/web/users/edit.html").read_text(encoding="utf-8")
    source = Path("web/static/web/js/users/edit.js").read_text(encoding="utf-8")

    form_end = template.index("</form>", template.index('id="user-edit-form"'))
    checkbox = template.index('id="user-edit-must-change"')
    assert form_end < checkbox
    assert 'id="user-edit-must-change-status"' in template
    assert 'aria-live="polite"' in template
    assert 'mustChangeInput.addEventListener("change"' in source
    assert "JSON.stringify({ must_change_password: desired })" in source
    assert 'setStatus(mustChangeStatus, "Saving...", false)' in source
    assert 'setStatus(mustChangeStatus, "Saved.", false)' in source
    assert "mustChangeInput.checked = !!original.must_change_password" in source

    main_form_payload = source.split(
        'form.addEventListener("submit"', 1
    )[1].split('mustChangeInput.addEventListener("change"', 1)[0]
    assert "must_change_password" not in main_form_payload


def test_user_edit_cards_and_membership_grid_are_compact_and_structured():
    template = Path("web/templates/web/users/edit.html").read_text(encoding="utf-8")
    memberships = Path("web/static/web/js/users/memberships.js").read_text(
        encoding="utf-8"
    )
    css = Path("web/static/web/css/users.css").read_text(encoding="utf-8")

    for card_id in ("user-edit-card", "user-password-card", "user-memberships-card"):
        assert f'id="{card_id}"' in template
    assert "#user-edit-card" in css and "#user-password-card" in css
    assert "width: min(100%, 760px)" in css
    assert 'class="user-password-card__body"' in template
    assert "width: min(100%, 680px)" in css

    assert 'class="membership-row membership-row--user-edit"' in memberships
    left = memberships.index('class="membership-row__left"')
    right = memberships.index('class="membership-row__right"')
    assert left < right
    assert 'class="membership-row__middle"' not in memberships
    assert "grid-template-columns: minmax(0, 1fr) minmax(220px, 280px)" in css
    assert ".membership-row__right" in css
    right_css = css.split(".membership-row__right {", 1)[1].split("}", 1)[0]
    assert "justify-content: flex-start" in right_css
    assert "max-width: 280px" in right_css
    assert ".membership-row__status {\n  min-width: 64px;" in css
    assert "#user-memberships-card" in css
    assert "width: min(100%, 760px)" in css

    assert 'class="membership-add-tile__group"' in template
    assert 'class="membership-add-tile__curator"' in template
    assert 'class="membership-add-tile__actions"' in template
    assert "JSON.stringify({ user_id: String(profileId), is_curator: isCurator })" in memberships

    groups_ui = Path("web/static/web/js/ui/groups.js").read_text(encoding="utf-8")
    assert 'help.setAttribute("title"' not in groups_ui
    assert 'help.setAttribute("aria-describedby", helpId)' in groups_ui
    assert ".public-curator-note__popover" in css
    assert "opacity: 0" in css
    assert ".public-curator-note__help:hover .public-curator-note__popover" in css
    assert ".public-curator-note__help:focus .public-curator-note__popover" in css
    popover_css = css.split(".public-curator-note__popover {", 1)[1].split("}", 1)[0]
    assert "left: 100%" in popover_css
    assert "bottom: 100%" in popover_css
    assert "transform:" not in popover_css
    assert "max-width:" not in popover_css
    assert "white-space: nowrap" in popover_css
    assert "font-weight: 600" in popover_css
    assert "rgba(125, 211, 252, 0.65)" in popover_css


def test_users_rendering_keeps_documented_identity_boundary():
    list_js = Path("web/static/web/js/users/list.js").read_text(encoding="utf-8")
    memberships_js = Path("web/static/web/js/users/memberships.js").read_text(
        encoding="utf-8"
    )

    assert "renderUserIdentity(user" in list_js
    assert "user.profile_id" in list_js
    assert "user.id" not in list_js
    assert "membership.id" not in memberships_js
    for sensitive in ("password", "client_token", "session_token"):
        assert sensitive not in list_js
        assert sensitive not in memberships_js
