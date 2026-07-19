from pathlib import Path

import pytest

from tests.core.product_ui.js import REPOSITORY_ROOT as ROOT
from tests.core.product_ui.js import run_node_json


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


def test_group_edit_layout_copy_actions_and_pagers_follow_product_contract():
    template = Path("web/templates/web/groups/edit.html").read_text(encoding="utf-8")
    pager = Path("web/templates/web/groups/_edit_pager.html").read_text(
        encoding="utf-8"
    )
    css = Path("web/static/web/css/groups-shelves.css").read_text(encoding="utf-8")

    for tab in ("details", "books", "add-books", "members", "shelves"):
        assert f'id="tab-{tab}" class="card' not in template
    assert 'id="group-delete-root" class="card danger-zone' in template
    assert "BookVerse" not in template
    assert 'placeholder="Search the library..."' in template
    assert "group-edit-form-actions" in template
    assert "group-edit-member-add-row" in template
    assert "group-edit-section-actions" in template
    assert "library-pager--sticky" in pager
    assert "Per page" in pager
    assert ".group-edit-form-actions" in css
    assert "justify-content: flex-end" in css
    assert ".group-edit-member-add" in css
    assert ".group-edit-section-actions" in css


def test_group_edit_page_state_is_url_backed_and_page_size_resets_page():
    module_uri = (ROOT / "web/static/web/js/groups/edit_pagination.js").as_uri()
    state_module_uri = (ROOT / "web/static/web/js/groups/view_pagination.js").as_uri()
    result = run_node_json(
        f"""
        globalThis.window = {{
          location: {{
            origin: "http://example.test",
            href: "http://example.test/groups/group-1/edit/?view=members&page=3&page_size=30",
            search: "?view=members&page=3&page_size=30",
          }},
          history: {{
            pushed: null,
            pushState(_state, _title, href) {{ this.pushed = href; }},
            replaceState() {{}},
          }},
        }};
        globalThis.document = {{ getElementById() {{ return null; }} }};
        const mod = await import("{module_uri}");
        const stateMod = await import("{state_module_uri}");
        const resized = stateMod.groupViewPageSizeSearch("50");
        mod.syncGroupEditPageUrl("members", "/api/v1/members/?page=2&page_size=50");
        console.log(JSON.stringify({{ pushed: window.history.pushed, resized }}));
        """
    )

    assert result["pushed"] == "/groups/group-1/edit/?view=members&page=2&page_size=50"
    assert result["resized"] == "?view=members&page_size=50"


def test_group_edit_mutation_routes_and_safe_rendering_remain_unchanged():
    books = Path("web/static/web/js/groups/books.js").read_text(encoding="utf-8")
    memberships = Path("web/static/web/js/groups/memberships.js").read_text(
        encoding="utf-8"
    )
    shelves = Path("web/static/web/js/groups/shelves.js").read_text(encoding="utf-8")
    shared = Path("web/static/web/js/groups/shared.js").read_text(encoding="utf-8")

    assert "/api/v1/library/search?${params.toString()}" in books
    assert 'ordering: "title"' in books
    assert "exclude_group: String(groupId)" in books
    assert 'method: "POST"' in books
    assert 'method: "DELETE"' in books
    assert 'data-action="member-remove"' in shared
    assert 'data-action="member-curator"' in shared
    assert "include_preview_books=true" in shelves
    assert "includeDisplayName: false" in shared
    for field in (
        "email",
        "first_name",
        "last_name",
        "membership_id",
        "download_url",
        "checksum",
        "storage_path",
        "source_filename",
    ):
        assert field not in shared
    assert "groupMutationErrorMessage" in memberships
