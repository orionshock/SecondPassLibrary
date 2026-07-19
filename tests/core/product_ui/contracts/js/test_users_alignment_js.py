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
        const state = mod.usersListState("?role=librarian&ordering=-last_login&page=3&page_size=40");
        console.log(JSON.stringify({{ state, href: mod.usersListHref(state) }}));
        """
    )

    assert result["state"] == {
        "filter": "librarian",
        "sortKey": "last_login",
        "sortDirection": "desc",
        "page": 3,
        "pageSize": 40,
    }
    assert result["href"] == (
        "/users/?role=librarian&ordering=-last_login&page=3&page_size=40"
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
    assert "page: 1, pageSize: nextPageSize" in source
    assert ".user-row__actions { justify-content: flex-end; }" in css


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
