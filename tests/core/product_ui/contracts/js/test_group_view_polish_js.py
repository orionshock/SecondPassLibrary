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
    assert 'class="library-row__meta book-metadata"' in renderers
    assert "renderBookMetadataHtml(book" in renderers
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
    assert template.count("library-pager--sticky") == 3
    assert template.count("group-view-pager--top") == 3
    assert template.count("data-group-page-size=") == 6
    assert 'id="tab-books" class="tab-panel"' in template
    assert 'id="tab-members" class="tab-panel is-hidden"' in template
    assert 'id="tab-shelves" class="tab-panel is-hidden"' in template
    assert 'id="tab-books" class="card' not in template
    assert 'target="_blank"' not in template


def test_group_view_pagination_restores_page_size_and_resets_page_on_size_change():
    module_uri = (ROOT / "web/static/web/js/groups/view_pagination.js").as_uri()
    result = run_node_json(
        f"""
        globalThis.window = {{
          location: {{
            origin: "http://example.test",
            href: "http://example.test/groups/group-1/?view=members&page=3&page_size=30",
            search: "?view=members&page=3&page_size=30",
          }},
          history: {{
            pushed: null,
            pushState(_state, _title, href) {{ this.pushed = href; }},
            replaceState() {{}},
          }},
        }};
        const mod = await import("{module_uri}");
        const state = mod.groupViewPageState();
        const api = mod.groupViewPagedApiUrl("/api/v1/groups/group-1/members/?keep=yes");
        const resized = mod.groupViewPageSizeSearch("50");
        const range = mod.groupViewRangeText({{ count: 75 }}, 15, api);
        mod.syncGroupViewPageUrl("members", "/api/v1/groups/group-1/members/?page=2&page_size=50");
        console.log(JSON.stringify({{
          state, api, resized, range, pushed: window.history.pushed,
        }}));
        """
    )

    assert result["state"] == {"page": 3, "pageSize": 30}
    assert result["api"] == "/api/v1/groups/group-1/members/?keep=yes&page_size=30&page=3"
    assert result["resized"] == "?view=members&page_size=50"
    assert result["range"] == "Showing 61-75 of 75"
    assert result["pushed"] == "/groups/group-1/?view=members&page=2&page_size=50"


def test_group_view_all_tabs_use_url_backed_pager_without_catalog_controls():
    view = Path("web/static/web/js/groups/view.js").read_text(encoding="utf-8")
    template = Path("web/templates/web/groups/detail.html").read_text(encoding="utf-8")

    for tab in ("books", "members", "shelves"):
        assert f'tab: "{tab}"' in view
    assert "groupViewPageSizeSearch" in view
    assert 'reason: "page-size"' in view
    assert "loadFromLocation" in view
    assert "resetPage: true" in view
    assert "catalog-tag" not in template
    assert "Catalog Tag" not in template
