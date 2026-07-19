from pathlib import Path

import pytest

from tests.core.product_ui.js import REPOSITORY_ROOT as ROOT
from tests.core.product_ui.js import run_node_json


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


def test_add_books_tab_restores_from_direct_url_and_history():
    module_uri = (ROOT / "web/static/web/js/groups/navigation.js").as_uri()
    result = run_node_json(
        f"""
        globalThis.window = {{
          location: {{
            origin: "http://example.test",
            href: "http://example.test/groups/group-1/edit/?view=add-books",
            search: "?view=add-books",
          }},
          history: {{
            pushed: null,
            pushState(_state, _title, href) {{ this.pushed = href; }},
            replaceState() {{}},
          }},
        }};
        const mod = await import("{module_uri}");
        const direct = mod.groupEditTabFromSearch();
        mod.setGroupEditUrl("group-1", "add-books");
        console.log(JSON.stringify({{ direct, pushed: window.history.pushed }}));
        """
    )

    assert result == {
        "direct": "add-books",
        "pushed": "/groups/group-1/edit/?view=add-books",
    }


def test_group_edit_keeps_members_shelves_and_no_new_axes_or_sensitive_book_fields():
    template = Path("web/templates/web/groups/edit.html").read_text(encoding="utf-8")
    navigation = Path("web/static/web/js/groups/navigation.js").read_text(
        encoding="utf-8"
    )
    shared = Path("web/static/web/js/groups/shared.js").read_text(encoding="utf-8")

    tabs = navigation.split("const GROUP_EDIT_TABS", 1)[1].split(";", 1)[0]
    assert '"details", "books", "add-books", "members", "shelves"' in tabs
    assert "authors" not in tabs
    assert "series" not in tabs
    assert "tags" not in tabs
    assert 'id="group-edit-add-member"' in template
    assert 'id="group-edit-shelves-results"' in template
    assert "includeDisplayName: false" in shared
    for sensitive_field in (
        "email",
        "first_name",
        "last_name",
        "membership_id",
        "download_url",
        "checksum",
        "storage_path",
        "source_filename",
        "file_key",
    ):
        assert sensitive_field not in shared
