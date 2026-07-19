from pathlib import Path

import pytest

from tests.core.product_ui.js import REPOSITORY_ROOT as ROOT
from tests.core.product_ui.js import run_node_json


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


def test_group_view_tab_navigation_restores_url_state_and_history():
    module_uri = (ROOT / "web/static/web/js/groups/navigation.js").as_uri()
    result = run_node_json(
        f"""
        globalThis.window = {{
          location: {{
            origin: "http://example.test",
            href: "http://example.test/groups/group-1/?view=shelves&page=2",
            search: "?view=shelves&page=2",
          }},
          history: {{
            pushed: [],
            pushState(_state, _title, href) {{
              this.pushed.push(href);
              window.location.href = `http://example.test${{href}}`;
              window.location.search = new URL(window.location.href).search;
            }},
            replaceState() {{}},
          }},
        }};
        const mod = await import("{module_uri}");
        const direct = mod.groupViewTabFromSearch();
        mod.setGroupViewUrl("group-1", "members");
        const selected = {{}};
        const buttons = ["books", "members", "shelves"].map((tab) => ({{
          getAttribute(name) {{ return name === "data-tab" ? tab : null; }},
          classList: {{ toggle(_name, active) {{ selected[`button-${{tab}}`] = active; }} }},
          setAttribute(name, value) {{ if (name === "aria-selected") selected[`aria-${{tab}}`] = value; }},
        }}));
        const panels = ["books", "members", "shelves"].map((tab) => ({{
          getAttribute(name) {{
            if (name === "data-tab-panel") return tab;
            if (name === "role") return "tabpanel";
            return null;
          }},
          classList: {{ toggle(_name, hidden) {{ selected[`panel-${{tab}}`] = !hidden; }} }},
          setAttribute(name, value) {{ if (name === "aria-hidden") selected[`hidden-${{tab}}`] = value; }},
        }}));
        mod.selectGroupViewTab({{
          querySelectorAll(selector) {{ return selector.includes("tab-button") ? buttons : panels; }},
        }}, mod.groupViewTabFromSearch());
        console.log(JSON.stringify({{ direct, pushed: window.history.pushed, selected }}));
        """
    )

    assert result["direct"] == "shelves"
    assert result["pushed"] == ["/groups/group-1/?view=members&page=2"]
    assert result["selected"]["button-members"] is True
    assert result["selected"]["panel-members"] is True
    assert result["selected"]["hidden-members"] == "false"
    assert result["selected"]["button-books"] is False


def test_group_view_uses_safe_view_only_rows_and_shelf_previews():
    view = Path("web/static/web/js/groups/view.js").read_text(encoding="utf-8")
    renderers = Path("web/static/web/js/groups/view_renderers.js").read_text(
        encoding="utf-8"
    )

    assert "renderGroupViewBooks" in view
    assert "renderGroupViewMembers" in view
    assert "renderGroupViewShelves" in view
    assert "include_preview_books=true" in view
    assert 'class="library-row group-view-book-row"' in renderers
    assert 'class="library-row__title"' in renderers
    assert 'class="library-row__meta"' in renderers
    assert "/library/books/${encodeURIComponent(String(book.id))}/" in renderers
    assert "renderCoverPreviewStrip(shelf && shelf.preview_books" in renderers
    assert 'class="book shelf-list-card group-view-shelf-card"' in renderers
    assert "includeDisplayName: false" in renderers
    assert "renderUserIdentity" in renderers
    assert ">Edit<" not in renderers
    for private_field in (
        "email",
        "first_name",
        "last_name",
        "profile_id",
        "membership_id",
        "download_url",
        "checksum",
        "storage_path",
        "source_filename",
        "file_key",
    ):
        assert private_field not in renderers


def test_group_view_does_not_add_library_axes_and_keeps_pagination():
    template = Path("web/templates/web/groups/detail.html").read_text(encoding="utf-8")
    navigation = Path("web/static/web/js/groups/navigation.js").read_text(
        encoding="utf-8"
    )

    view_tabs = navigation.split("const GROUP_VIEW_TABS", 1)[1].split(";", 1)[0]
    assert '"books", "members", "shelves"' in view_tabs
    assert "authors" not in view_tabs
    assert "series" not in view_tabs
    assert "tags" not in view_tabs
    assert 'id="group-view-books-prev"' in template
    assert 'id="group-view-books-next"' in template
    assert 'aria-label="Group books pagination"' in template
    assert 'target="_blank"' not in template
